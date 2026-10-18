# LOAD_CUSTOMERS 0.1 — what it does, and what to fix before TMC production

Source reviewed: `LOAD_CUSTOMERS_0.1.item` (Studio 8 Standard job) and `LOAD_CUSTOMERS_0.1.properties`.

## 1. Identity (from the .properties)

| Field | Value |
|---|---|
| Job | `LOAD_CUSTOMERS`, version **0.1**, status **DEV** |
| Repository path | `dwh/dimensions` |
| Purpose / description | "Load customer dimension" — "Reads daily customer CSV drops, enriches with country, upserts dim_customer." |
| Created / last modified | 2026-05-02 / 2026-09-18 |
| Routines it depends on | `TalendDate`, `StringHandling` (system) and **`CustomerUtils`** (custom routine `_routine_Custom01`) |
| Context group | all 8 variables come from repository context group `_ctxGroup01` |

Note: `CustomerUtils` is declared as a dependency but is **not used in any expression** in the job. If it is missing from your import the job will not compile; if it is present it is probably a leftover and can be unlinked.

## 2. End-to-end flow

The job is one Standard job with three subjobs:

```
PREJOB  "Open DWH connection"
  tPrejob_1 --OnComponentOk--> tDBConnection_1 "DWH"
                              PostgreSQL 12, context.DB_HOST:DB_PORT/DB_NAME, schema "public",
                              user context.DB_USER, pass context.DB_PASS,
                              JDBC prop reWriteBatchedInserts=true, AUTO-COMMIT OFF

MAIN  "Load customers"
  tFileList_1 "list_csv"           dir = context.INPUT_DIR, mask = context.FILE_MASK (glob, case-sensitive,
      |                            files only, no subdirs, ordered by name ASC)
      | Iterate (sequential, not parallel)
      v
  tFileInputDelimited_1 "read_customers"   file = tFileList_1_CURRENT_FILEPATH
      |   CSV mode, sep ";", enclosure ", escape \, 1 header row, UTF-8, trim all fields,
      |   check field count, remove empty rows, die-on-error OFF
      |   schema: customer_id Integer (key, not null) | full_name String(100) | email String(255)
      |           country_code String | signup_date Date "yyyy-MM-dd" | lifetime_value BigDecimal(12,2)
      |
      |-- rejects (REJECT) --> tLogRow_2 "log_rejects"   <<< DEACTIVATED
      |
      |-- row1 (main) --> tMap_1 "enrich"  <-- lkp (lookup) <-- tDBInput_1 "lkp_country"
      |                                       SELECT country_code, country_name, region
      |                                       FROM dim_country WHERE active = true
      |                                       (same DWH connection, server cursor 1000)
      |
      |     tMap outputs:
      |       out_ok          --> tDBOutput_1 "dim_customer"  INSERT_OR_UPDATE on key customer_id,
      |                                                        table action NONE, die-on-error OFF,
      |                                                        batch = context.BATCH_SIZE, commit every 10000
      |       out_no_country  --> tLogRow_1 "log_no_country"  (table mode, stdout)
      |
  tFileList_1 --OnSubjobOk-----> tDBCommit_1   (single commit after ALL files, connection kept open)
  tFileList_1 --OnSubjobError--> tDie_1        exit code 4, "Load failed: " + tDBOutput_1_ERROR_MESSAGE

POSTJOB "Cleanup"
  tPostjob_1 --OnComponentOk--> tDBClose_1
```

The note on the canvas sums it up: *"Loads customer CSV drops into dim_customer; rows without a known country go to the log."*

### Inputs
1. **CSV files** in `context.INPUT_DIR` matching `context.FILE_MASK` (`customers_*.csv`). Semicolon-delimited, double-quote enclosed, one header row, UTF-8. Six columns in the order above; `signup_date` must be `yyyy-MM-dd`. Files are processed one at a time in name order (so `customers_20260101.csv` before `customers_20260102.csv`; a later file wins on the same `customer_id`).
2. **`public.dim_country`** in the DWH — the lookup/reference table. Only rows with `active = true` are loaded; `country_code` is `bpchar(2)` in the DB.
3. **A properties file** at `context.INPUT_DIR + "/../conf/job.properties"` (see Contexts below) — this is a hidden third input.

### Transformations in tMap "enrich"
Variables:
- `clean_name = StringHandling.TRIM(row1.full_name)` (redundant with "trim all" on the reader, but harmless).
- `clean_email = row1.email == null ? null : StringHandling.DOWNCASE(row1.email)` (emails lower-cased).

Lookup join (`lkp`):
- Mode **Load once**, **Unique match**, **Inner join**.
- Condition: `lkp.country_code == StringHandling.UPCASE(row1.country_code)` — the CSV code is upper-cased and matched exactly against `dim_country.country_code`. Because it is an inner join, a customer whose code is not an active row in `dim_country` does not reach `out_ok`.
- "Unique match" means if `dim_country` ever has two active rows with the same code, the last one loaded wins silently.
- Because the tMap sits inside the `tFileList` Iterate loop, "Load once" means once *per file*, not once per job — the lookup query is re-run for every CSV. Harmless for a small country table, but worth knowing.

Outputs:
- **`out_ok`** (filter: `Var.clean_email != null && Var.clean_email.contains("@")`): `customer_id`, `full_name=clean_name`, `email=clean_email`, `country_name` and `region` from the lookup, `signup_date`, `lifetime_value`, and `load_ts = TalendDate.getCurrentDate()` (engine JVM clock, not DB clock).
- **`out_no_country`** ("Catch lookup inner join reject"): `customer_id` + raw `country_code` for rows with no country match → printed to stdout by `tLogRow_1`.
- There is **no output** for rows that match a country but fail the email filter. Those rows vanish.

### Outputs
1. **`public.dim_customer`** — upserted (Type-1 overwrite) on `customer_id`. Field options: `customer_id` is the update key and *not updatable*; every other column (including `signup_date` and `load_ts`) is overwritten on each run. The table must already exist (table action NONE). Note the raw `country_code` is **not** stored — only the resolved `country_name`/`region`.
2. **stdout** — table of `customer_id`/`country_code` for unmatched countries (`tLogRow_1`, log4j off, so plain stdout, which TMC captures in the task log).
3. **Exit code** — 0 on success, 4 via `tDie_1` when the main subjob throws.
4. Stats/log catchers are enabled using *project settings* (`STATS_LOG_USE_PROJECT_SETTINGS=true`, StatCatcher + LogCatcher on, MeterCatcher off). Where those go (DB table, file, console) is defined in the project, not in this item — you need to check it.

### Transaction model
Auto-commit is off and both the lookup and the output use the single `tDBConnection_1`. There is exactly one `tDBCommit` after the whole file loop, so a run is intended to be all-or-nothing across all files. `COMMIT_EVERY=10000` on `tDBOutput_1` is ignored when "use existing connection" is on, so that number is decorative. On error, nothing explicitly rolls back — `tDie` runs, then the postjob closes the connection, and the uncommitted transaction is discarded by the server on close. It works, but it is implicit.

## 3. Contexts

Two contexts, same 8 variables, both bound to repository context group `_ctxGroup01`. No prompts / no confirmation (good — a prompt would hang a TMC run).

| Variable | Type | Default (dev) | PROD | Used by |
|---|---|---|---|---|
| `INPUT_DIR` | Directory | `/data/in` | `/mnt/landing/customers` | tFileList, implicit context load path |
| `FILE_MASK` | String | `customers_*.csv` | `customers_*.csv` | tFileList |
| `DB_HOST` | String | `localhost` | `dwh-prod.internal` | tDBConnection |
| `DB_PORT` | Integer | `5432` | `5432` | tDBConnection |
| `DB_NAME` | String | `dwh` | `dwh` | tDBConnection |
| `DB_USER` | String | `etl` | `etl_prod` | tDBConnection |
| `DB_PASS` | Password | `enc:system.encryption.key.v1:…` | `enc:system.encryption.key.v1:…` | tDBConnection |
| `BATCH_SIZE` | Integer | `1000` | `5000` | tDBOutput (see below — effectively unused) |

Two things about how contexts are *actually* resolved at runtime:

1. **Implicit tContextLoad is on** (`IMPLICIT_TCONTEXTLOAD=true`, from file `context.INPUT_DIR + "/../conf/job.properties"`). At start-up the job picks the selected context (e.g. PROD), then **overrides any of these variables with whatever is in `/mnt/landing/conf/job.properties` on the engine**. So the values you see in Studio or in the TMC task are not necessarily what runs — the landing-zone config file is the real source of truth, and it can override `DB_HOST`/`DB_USER`/`DB_PASS` too. None of the implicit-load safety options (print operations, behaviour when a variable is undefined) are set, so defaults apply.
2. `DB_PASS` is encrypted with Studio's **default key** (`system.encryption.key.v1`). That key ships with every Studio 8 install, so anyone with the item file and a Studio can recover the PROD password. Treat it as exposed.

## 4. What I would fix before scheduling in TMC

Ordered by risk.

### Blockers (data loss / correctness / security)

1. **Silent partial loads: `tDBOutput_1` has Die on error = false and no reject link.** A row that fails to insert/update (value too long for `varchar(100)`/`(255)`, constraint violation, bad type) is printed to stderr and skipped; the subjob still ends "OK", `tDBCommit_1` commits the rest, and the job exits 0. TMC will show green while rows are missing. The `tDie` message even references `tDBOutput_1_ERROR_MESSAGE`, which suggests the author expected it to fire on output errors — it will not, because `OnSubjobError` only fires on an exception that kills the subjob. Fix: set Die on error = true on the output (then the error → OnSubjobError → tDie path actually works), **or** add a Reject flow from `tDBOutput_1` to a reject table/file and fail the job if the reject count > 0.

2. **CSV parse rejects are thrown away.** `tFileInputDelimited_1` has Die on error = false and its REJECT link goes to `tLogRow_2`, which is **deactivated**. Rows with the wrong field count, an unparsable `signup_date`/`lifetime_value`/`customer_id`, or an empty `customer_id` (non-nullable) disappear with only a stderr line. Reactivate and route rejects to a file/table (`errorCode`/`errorMessage` are already in the reject schema), and fail or alert when there are any.

3. **Rows with a bad or missing email disappear with no trace.** The `out_ok` filter drops anything without `@`; there is no third output or counter for them. If a customer file legitimately has customers without email, you are silently losing dimension members. Decide with the business: either load them with `email = null`, or add an `out_bad_email` output that is logged/rejected like the country rejects.

4. **Production credential leaked in the export.** Rotate the `etl_prod` password now. Going forward do not keep PROD `DB_PASS` as a value in the context group/job; set it in TMC as a password-type context parameter on the task (or environment) and leave the item value blank. Keep the item out of git history with the real value in it.

5. **Hidden config override via implicit context load.** Remove `IMPLICIT_TCONTEXTLOAD` (or make it an explicit `tContextLoad` in the prejob with "print operations" on and a hard failure on a missing file). In TMC the context values should come from the task/environment parameters so what you see in the console is what runs. If you must keep a properties file, do not derive its path from `INPUT_DIR` (that couples DB config to the landing directory) and never allow it to carry credentials.

6. **No file lifecycle.** Nothing moves or renames processed files, so every run reprocesses every `customers_*.csv` still in the landing directory, and a file being written while the job is running will be read half-finished. Add: process only completed files (e.g. `.csv` renamed from `.tmp`, or a `.done` marker), and move each processed file to an `archive/` (or `error/`) folder after a successful commit. Also decide what "zero files found" means — today the job commits nothing and exits 0; you probably want a warning or a non-zero code.

### Should fix (robustness / performance)

7. **Explicit rollback and useful error message.** Add `tDBRollback_1` on the `OnSubjobError` branch before `tDie_1`. The die message `"Load failed: " + tDBOutput_1_ERROR_MESSAGE` will read `Load failed: null` when the error came from the reader or tMap; use a `tLogCatcher` (already enabled via project settings — check where it writes) or build the message from the actual failing component.

8. **The "batch" settings do nothing.** `INSERT_OR_UPDATE` in tDBOutput is row-by-row (one SELECT by key, then INSERT or UPDATE per row); Talend's batch mode does not apply to that action, so `BATCH_SIZE`, `reWriteBatchedInserts=true`, and `COMMIT_EVERY` are all inert. At 5,000+ rows/day it is fine; at hundreds of thousands it will be slow. If volumes are material, load to a staging table with plain batched INSERTs and finish with `INSERT … ON CONFLICT (customer_id) DO UPDATE` in a `tDBRow`. At minimum confirm `dim_customer` has a PK/unique index on `customer_id`, otherwise every row's existence check is a full scan.

9. **Null-safety in tMap.** `StringHandling.UPCASE(row1.country_code)` and `StringHandling.TRIM(row1.full_name)` throw `NullPointerException` on null. With tFileInputDelimited an empty string field normally arrives as `""` not null, so this usually works, but if a null ever gets through (schema change, different source component), tMap has Die on error = true and the whole run dies. Use `row1.country_code == null ? null : …` guards (as was already done for email) or `Relational.ISNULL`.

10. **Reference data and lookup semantics.** `UNIQUE_MATCH` hides duplicate active codes in `dim_country`; use "All matches" with a check, or enforce a unique constraint on `dim_country(country_code) WHERE active`. The DB column is `bpchar(2)`; if the files ever carry 3-letter ISO codes nothing will match. Consider storing the raw `country_code` on `dim_customer` as well, so rows can be re-enriched if `dim_country` changes.

11. **Observability.** `tLogRow_1` in TABLE mode buffers all rows in memory and prints to stdout — switch to a reject file/table (or at least basic mode with log4j on). Log `tFileList_1_NB_FILE`, `tFileInputDelimited_1_NB_LINE`, `tDBOutput_1_NB_LINE_INSERTED/UPDATED` and the two reject counts at the end of the run so TMC history is meaningful. Verify what the project-level Stats/Logs settings actually point at — if they target a dev-machine file path or a dev DB they will fail or spam in prod.

12. **Timestamps.** `load_ts = TalendDate.getCurrentDate()` uses the Remote Engine's JVM time zone; set `-Duser.timezone=UTC` (or use `now()` in the DB) so it is consistent across engines.

### Housekeeping for TMC

13. **JVM arguments** (`-Xms256M -Xmx2048M -Dfile.encoding=UTF-8`) are a Studio run configuration; set them on the TMC task (JVM parameters) and make sure the Remote Engine host has the memory.
14. **Promote the artifact properly**: lock/bump the version (0.1 → 1.0), set status from DEV to production-ready, and include the context group `_ctxGroup01` and the `CustomerUtils` routine in the publish so it compiles identically. Verify `dim_customer` (with PK) and `dim_country.active` exist in the target schema since table action is NONE.
15. **Engine prerequisites**: the Remote Engine must mount `/mnt/landing/customers` (and `/mnt/landing/conf` while implicit load exists) and reach `dwh-prod.internal:5432`. The job is sequential (`MULTI_THREAD_EXECATION=false`, Iterate not parallel) and uses one DB connection, so keep it that way — do not enable parallel iterate.
16. **Document the contract**: file naming/encoding/delimiter, column order, date format, upsert semantics (Type-1 overwrite, no deletes propagated, no history), and the behaviour for unknown countries and bad emails. This file is currently the only documentation.

## 5. One-paragraph summary

`LOAD_CUSTOMERS` opens one PostgreSQL connection, loops over `customers_*.csv` files in a landing directory, parses each with a fixed 6-column semicolon CSV schema, upper-cases the country code and inner-joins it against active rows in `dim_country`, lower-cases/validates the email, and upserts the enriched rows into `dim_customer` keyed on `customer_id`, committing once at the end; unmatched countries are only printed to stdout. It is a reasonable DEV prototype but not production-safe as exported: output and parse errors are swallowed (exit 0 with missing rows), bad-email rows vanish, processed files are never archived, the PROD password is recoverable from the item, and a hidden properties file can override every context value at runtime. Fix items 1-6 before the first scheduled run; 7-12 before you call it done.
