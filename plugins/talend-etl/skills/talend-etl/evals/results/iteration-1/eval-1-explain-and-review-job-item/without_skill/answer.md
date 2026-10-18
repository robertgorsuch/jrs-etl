# LOAD_CUSTOMERS 0.1 — what it does, and what to fix before TMC

Source: `LOAD_CUSTOMERS_0.1.item` + `LOAD_CUSTOMERS_0.1.properties` (Studio 8 export, Standard job).

## TL;DR

It is a daily file-to-dimension load. It lists `customers_*.csv` files in a landing directory, reads each one, enriches every row with `country_name`/`region` from `dim_country`, upserts the result into `dim_customer` keyed on `customer_id`, and commits once at the very end. Rows whose country code is unknown are printed to the console; rows without a usable email are dropped.

It is **not ready to schedule**. The design is reasonable, but it has three silent data-loss paths and one transaction trap that can make the job exit 0 after loading nothing. Details and a prioritised fix list are in section 5.

---

## 1. Job metadata (from the .properties)

| Field | Value |
|---|---|
| Name / folder | `LOAD_CUSTOMERS`, in `dwh/dimensions` |
| Version / status | `0.1`, `DEV` |
| Purpose | "Load customer dimension" |
| Description | "Reads daily customer CSV drops, enriches with country, upserts dim_customer." |
| Created / last modified | 2026-05-02 / 2026-09-18 |
| Job note on canvas | "Loads customer CSV drops into dim_customer; rows without a known country go to the log." |

So the colleague's own description matches what the XML actually does. It has never been promoted past DEV.

---

## 2. End-to-end flow

Three subjobs, read top to bottom:

```
[Pre-job: "Open DWH connection"]
  tPrejob_1 --OnComponentOk--> tDBConnection_1 "DWH"  (PostgreSQL, autocommit OFF)

[Main: "Load customers"]
  tFileList_1 "list_csv"
     |  Iterate (one pass per file, sequential)
     v
  tFileInputDelimited_1 "read_customers" --row1-------------------------> tMap_1 "enrich" --out_ok---------> tDBOutput_1 "dim_customer"
     |                                                                      ^                                   (Insert or update, batched)
     |  rejects (REJECT link) --> tLogRow_2 "log_rejects"  [DEACTIVATED]    | lkp (lookup, Load once)
     |                                                                      |
     |                                       tDBInput_1 "lkp_country" ------+           --out_no_country--> tLogRow_1 "log_no_country"
     |
     +--OnSubjobOk----> tDBCommit_1                      (commit everything, keep connection open)
     +--OnSubjobError-> tDie_1  exit code 4              ("Load failed: " + tDBOutput_1_ERROR_MESSAGE)

[Post-job: "Cleanup"]
  tPostjob_1 --OnComponentOk--> tDBClose_1
```

### 2.1 Pre-job: open the warehouse connection

`tDBConnection_1` ("DWH"): PostgreSQL (driver profile `POSTGRESQL_12`), host/port/db/user/password all from context variables, default schema `"public"`, extra JDBC property `reWriteBatchedInserts=true`, **auto-commit off**, not a shared connection. Because auto-commit is off, every statement the job issues on this connection — the lookup query and all the upserts for *all* files — sits in a single transaction until `tDBCommit_1` runs.

### 2.2 Main subjob: list, read, enrich, upsert

**Input: `tFileList_1` ("list_csv")**
Lists files (not directories, no recursion) in `context.INPUT_DIR` matching `context.FILE_MASK` (`customers_*.csv`, glob syntax, case-sensitive), ordered **by name ascending**. Each match fires one Iterate; parallel iteration is off, so files are processed one at a time in filename order. If the files are named `customers_YYYYMMDD.csv` this gives chronological order, which matters because later files overwrite earlier ones on upsert.

**Reader: `tFileInputDelimited_1` ("read_customers")**
Reads `globalMap("tFileList_1_CURRENT_FILEPATH")`. Settings: CSV mode on, field separator `;`, text enclosure `"`, escape `\`, row separator `\n`, 1 header line, no footer, no limit, UTF-8, trim all columns, remove empty rows, check number of fields per row. Die on error is **off**, so a malformed row (wrong column count, non-integer `customer_id`, a `signup_date` not matching `yyyy-MM-dd`, a non-numeric `lifetime_value`) is pushed down the `rejects` link instead of killing the job.

Schema (the "contract" with the file):

| Column | Type | Notes |
|---|---|---|
| `customer_id` | Integer | key, not nullable |
| `full_name` | String(100) | |
| `email` | String(255) | |
| `country_code` | String | |
| `signup_date` | Date | pattern `yyyy-MM-dd` |
| `lifetime_value` | BigDecimal(12,2) | |

The REJECT link carries the same six columns plus `errorCode`/`errorMessage` to `tLogRow_2` — **which is deactivated** (`ACTIVATE=false`). See fix #2.

**Lookup source: `tDBInput_1` ("lkp_country")**
Runs on the shared connection: `SELECT country_code, country_name, region FROM dim_country WHERE active = true`, cursor fetch size 1000, no trimming. Schema: `country_code` bpchar(2) (key), `country_name` varchar(80), `region` varchar(40).

**Transform: `tMap_1` ("enrich")** — see section 3 for the lookup mechanics.

- Variables:
  - `clean_name = StringHandling.TRIM(row1.full_name)`
  - `clean_email = row1.email == null ? null : StringHandling.DOWNCASE(row1.email)`
- Output `out_ok` (filter: `Var.clean_email != null && Var.clean_email.contains("@")`):
  `customer_id`, `full_name`←`clean_name`, `email`←`clean_email`, `country_name`←`lkp.country_name`, `region`←`lkp.region`, `signup_date`, `lifetime_value`, `load_ts`←`TalendDate.getCurrentDate()`.
- Output `out_no_country` (inner-join reject): `customer_id`, `country_code` → `tLogRow_1` ("log_no_country"), table mode, printed to stdout (log4j off).
- tMap "Die on error" is **on**: any runtime exception in an expression (e.g. an NPE) aborts the subjob.

**Target: `tDBOutput_1` ("dim_customer")**
Uses the existing connection, table `dim_customer`, table action NONE (table must exist), data action **Insert or update**, update key `customer_id` (marked insertable, not updatable), batch mode on with batch size `context.BATCH_SIZE`, "commit every 10000" (ignored when using an existing connection — commit is controlled by `tDBCommit_1`), **die on error off**. Output columns = the `out_ok` schema (8 columns including `load_ts`).

**Completion**
- `tFileList_1 --OnSubjobOk--> tDBCommit_1`: fires once after *all* files have been iterated; commits the whole run as one transaction; leaves the connection open for the post-job.
- `tFileList_1 --OnSubjobError--> tDie_1`: message `"Load failed: " + tDBOutput_1_ERROR_MESSAGE`, exit code 4, priority 5, "exit JVM immediately" off (so the post-job still runs). There is no explicit `tDBRollback`; the uncommitted transaction is rolled back implicitly when `tDBClose_1` closes the connection.

### 2.3 Post-job: cleanup

`tPostjob_1 → tDBClose_1` closes the connection in both success and failure paths.

---

## 3. How the lookup works

`tMap_1` has one main flow (`row1`, the CSV rows) and one lookup flow (`lkp`, from `dim_country`), configured as:

| Setting | Value | Meaning |
|---|---|---|
| Lookup model | `LOAD_ONCE` | `dim_country` is queried once per job run and held in memory as a hash; it is **not** re-read for every file in the Iterate loop. This is the correct choice inside an iterate. |
| Match model | `UNIQUE_MATCH` | For each main row, take the single (last) matching lookup row. If `dim_country` has two active rows with the same code, one silently wins. |
| Join model | `innerJoin=true` | A main row without a match is excluded from `out_ok` ... |
| `out_no_country.rejectInnerJoin=true` | | ... and is instead routed to `out_no_country` ("Catch lookup inner join reject"). |
| Join key | `StringHandling.UPCASE(row1.country_code) == lkp.country_code` | The file's code is upper-cased, then compared for string equality to the warehouse code as stored. |

Practical consequences:

- **Normalisation is one-sided.** Only the file side is upper-cased. If `dim_country.country_code` holds lowercase values, or the column is really `char(3)` and JDBC returns a space-padded `"US "`, nothing will ever match and *every* customer goes to `out_no_country`. The lookup schema says bpchar(2), which is fine only if that is really the DDL.
- **Null country code blows up the job.** `StringHandling.UPCASE(null)` throws a NullPointerException; with tMap die-on-error on, the whole subjob aborts and `tDie_1` fires with the message `Load failed: null` (because the failing component was tMap, not tDBOutput). The colleague null-guarded `DOWNCASE(email)` but not `UPCASE(country_code)` or `TRIM(full_name)`.
- **Filter happens after the join.** A row that *did* match a country but has no `@` in its email is dropped from `out_ok` and does not go to `out_no_country` either. It just disappears (fix #3).
- Memory: the lookup is the whole active `dim_country` — a few hundred rows — so `ROWS_BUFFER_SIZE=2000000` and the 2 GB heap are irrelevant for it.

---

## 4. What the contexts are for

There are two contexts, both populated from a **repository context group** (`repositoryContextId="_ctxGroup01"`), which is *not* in the export you have. `Default` is the development/local profile; `PROD` is the production profile. TMC picks one per task.

| Variable | Type | Default | PROD | Used by |
|---|---|---|---|---|
| `INPUT_DIR` | Directory | `/data/in` | `/mnt/landing/customers` | `tFileList_1` directory; also the implicit context-load path |
| `FILE_MASK` | String | `customers_*.csv` | `customers_*.csv` | `tFileList_1` file mask |
| `DB_HOST` | String | `localhost` | `dwh-prod.internal` | `tDBConnection_1` |
| `DB_PORT` | Integer | `5432` | `5432` | `tDBConnection_1` |
| `DB_NAME` | String | `dwh` | `dwh` | `tDBConnection_1` |
| `DB_USER` | String | `etl` | `etl_prod` | `tDBConnection_1` |
| `DB_PASS` | Password | encrypted | encrypted | `tDBConnection_1` |
| `BATCH_SIZE` | Integer | `1000` | `5000` | `tDBOutput_1` JDBC batch size |

Notes on the contexts and the job-level settings around them:

- **Both passwords are encrypted with `system.encryption.key.v1`** — Studio's built-in default key. Anyone who opens the item in Studio (or has the default key) can recover the prod DB password. Treat the production password as exposed: it has been sitting in an exported file.
- **Implicit `tContextLoad` is enabled** (`IMPLICIT_TCONTEXTLOAD=true`, from file): at startup the job reads `context.INPUT_DIR + "/../conf/job.properties"` (in PROD: `/mnt/landing/conf/job.properties`) as `key=value` pairs and overrides any context variable found there. This runs *after* command-line `--context_param` values are applied, so a value in that file **wins over whatever you set on the TMC task**. It also means a file sitting next to the inbound data landing zone can redirect the job to a different database.
- **JVM arguments** `-Xms256M -Xmx2048M -Dfile.encoding=UTF-8` are in `JOB_RUN_VM_ARGUMENTS`, which is the Studio *Run* tab. They are not part of the built artifact; TMC will not apply them unless you set them on the task.
- **Stats/Logs**: `STATS_LOG_USE_PROJECT_SETTINGS=true` with the stat and log catchers on — where those rows go (a table? a file? nowhere?) is decided by the *project* settings, which you also don't have. `ON_METERCATCHER` is off, so no row counts are captured. Log4j is active.
- **Routines**: `TalendDate` and `StringHandling` are used. `CustomerUtils` (`_routine_Custom01`) is declared as a dependency but **never referenced** in any expression. If it does not exist in your project the job will not build; if it does, it is dead weight.
- `PARALLELIZE_UNIT_SIZE`, multi-thread execution and iterate parallelism are all defaults/off — the job is strictly sequential.

---

## 5. What I would fix before scheduling in TMC

### Blockers — these cause silent data loss or false success

**1. `tDBOutput_1` has die-on-error OFF inside a single manual transaction on PostgreSQL.**
This is the worst one. PostgreSQL aborts the *entire* transaction on the first SQL error (e.g. one `full_name` longer than the column, a `NOT NULL` violation). Because autocommit is off and the job commits only at the very end, every subsequent statement fails with `current transaction is aborted, commands ignored until end of transaction block`. With die-on-error off, Talend catches each failure, prints it to stderr, increments `NB_LINE_REJECTED` and keeps going. The subjob finishes "OK", `tDBCommit_1` runs (committing an aborted transaction is a no-op rollback), and the job **exits 0 having loaded nothing**. TMC shows green. `tDie_1` never fires because nothing threw.
Also, because batch mode is on, the tDBOutput reject link is unavailable, so there is no way to catch those rows anyway.
*Fix:* set `DIE_ON_ERROR=true` on `tDBOutput_1` so the first failure aborts the subjob and goes through `OnSubjobError → tDie_1` (exit 4). Add an explicit `tDBRollback` before `tDie_1`. If you really want "best effort" behaviour, switch to per-file commits plus a post-load check that fails the job when `tDBOutput_1_NB_LINE_REJECTED > 0`.

**2. File-level rejects are routed to a deactivated component.**
`tFileInputDelimited_1` has die-on-error off and its `rejects` link goes to `tLogRow_2`, which is `ACTIVATE=false`. Rows with the wrong column count, bad dates, non-numeric values etc. are silently thrown away — not even printed.
*Fix:* re-activate the branch and send it to a `tFileOutputDelimited` (rejects file per run, including `errorCode`/`errorMessage`) or a reject table; after the loop, fail or at least warn when `tFileInputDelimited_1_NB_LINE_REJECTED > 0`.

**3. The `out_ok` email filter drops rows with no trace.**
`Var.clean_email != null && Var.clean_email.contains("@")` means a customer with a known country but a missing or malformed email is excluded from `dim_customer` and appears nowhere else. Nobody will know it happened. It is also debatable business logic: a dimension load normally keeps the customer and nulls/flag the bad attribute rather than dropping the entity.
*Fix:* either drop the filter and keep the row (null email), or add a dedicated reject output (`Catch output reject` → `out_rejects` with a `reason` column) and persist it alongside the no-country rejects. Make the rule explicit and auditable.

**4. "No country" rows only go to stdout.**
`tLogRow_1` in TABLE mode buffers every reject in memory and dumps them at the end of the flow. In TMC that text ends up in the task log and is never acted upon. For a dimension load those rows are a data-quality signal someone needs to see.
*Fix:* write them to a `dim_customer_reject` table or a rejects file with `run_id`/`load_ts`, and consider still loading the customer with `country_name`/`region` = `'UNKNOWN'` (left join) so the fact tables can still join.

**5. No file archiving / idempotency.**
Nothing moves or renames a processed file. Every scheduled run re-reads *every* `customers_*.csv` still in `/mnt/landing/customers`, re-upserting everything (and rewriting `load_ts`). This grows linearly, and a failed run cannot distinguish "already loaded" from "new".
*Fix:* inside the Iterate, after `tFileInputDelimited_1` finishes (`OnSubjobOk`), move the file to `.../archive/<yyyyMMdd>/` with `tFileCopy` (and to `.../error/` on failure). Decide whether you want one transaction per file or per run (per-file commit + archive gives clean restartability). Also log/alert when `tFileList_1_NB_FILE == 0` — a day with no file is usually an upstream failure, not a success.

**6. Remove the implicit context load.**
A `conf/job.properties` next to the landing directory can override `DB_HOST`, `DB_USER`, `DB_PASS` and beats TMC task parameters. It is a security hole and an operational mystery ("why is it connecting to the wrong DB?"). In TMC, parameters belong on the task.
*Fix:* `IMPLICIT_TCONTEXTLOAD=false`; put every environment-specific value on the TMC task.

**7. Secrets.**
The exported item carries the PROD database password encrypted with Studio's default key. *Fix:* rotate `etl_prod`'s password now; in TMC define `DB_PASS` as a task parameter flagged sensitive (or move the connection to a TMC connection object); never ship a real value in the context group.

### Should fix

8. **`tDie_1` message is misleading.** It hard-codes `tDBOutput_1_ERROR_MESSAGE`, so a failure in tMap, tDBInput or tFileList prints `Load failed: null`. Add a `tLogCatcher → tLogRow/log4j` (or log table) so the real exception is captured, and make the tDie message generic. Keep the non-zero exit code (4) so TMC marks the task failed.
9. **Null-safety in tMap.** Guard `TRIM(row1.full_name)` and `UPCASE(row1.country_code)` the same way email is guarded (or use `Relational.ISNULL`), otherwise a blank country code kills the run instead of going to `out_no_country`.
10. **Normalise the lookup key on both sides.** Use `StringHandling.TRIM(StringHandling.UPCASE(...))` on the main side and `upper(trim(country_code))` in the lookup SQL (or at least confirm `dim_country.country_code` is really `char(2)` uppercase). Also confirm there are no duplicate active codes (unique match hides them).
11. **Upsert performance.** "Insert or update" issues a `SELECT` per row before batching the insert/update, and `reWriteBatchedInserts` does not help the selects. Fine for tens of thousands of rows per day; for larger volumes load into a staging table and run `INSERT ... ON CONFLICT (customer_id) DO UPDATE` in a `tDBRow`. Verify `dim_customer` has a PK/unique index on `customer_id`; verify the field options for the other seven columns are set updatable (the export only lists `customer_id`).
12. **`load_ts` = engine local time.** `TalendDate.getCurrentDate()` depends on the Remote Engine's timezone. Use UTC explicitly or a DB default `now()`.
13. **Observability.** Turn on the meter catcher or log, at the end of the run, `tFileList_1_NB_FILE`, `tFileInputDelimited_1_NB_LINE`, `NB_LINE_REJECTED`, `tDBOutput_1_NB_LINE_INSERTED/UPDATED/REJECTED`, and the no-country count. Switch `tLogRow` to log4j so it is levelled and timestamped.
14. **Housekeeping.** Remove the unused `CustomerUtils` routine dependency (or confirm it exists), bump the version from 0.1 to 1.0 and status from DEV to PROD, and get the job and its context group into Git before publishing.

### TMC-specific checklist

- **Engine**: this must run on a **Remote Engine** that has `/mnt/landing/customers` mounted and network access to `dwh-prod.internal:5432`; a Cloud Engine cannot see either.
- **Task configuration**: publish the artifact, select context `PROD`, override `DB_PASS` (and ideally `DB_HOST`/`DB_USER`) as task parameters, mark the password sensitive.
- **JVM parameters**: set `-Xmx2048m -Dfile.encoding=UTF-8` on the task; the Studio Run-tab values do not travel with the build.
- **Concurrency**: disallow parallel execution of the task; two overlapping runs would double-load the same files and block each other on `dim_customer` row locks.
- **Schedule**: run after the file drop window (or trigger on file arrival) and only after fix #5 so retries are safe; configure retries once idempotent.
- **Alerting**: alert on exit code != 0 (only meaningful after fix #1) and on non-zero reject counts.
- **Project settings**: confirm what the project-level Stats/Logs settings point to in the production project (`STATS_LOG_USE_PROJECT_SETTINGS=true`); if it is a DB table, that connection also needs to exist on the Remote Engine.
- **Import dependencies**: the item references context group `_ctxGroup01`, routine `CustomerUtils` and the PostgreSQL driver module. Import the context group with the job or Studio will downgrade the contexts to built-in.

### Things the item cannot tell you — verify before go-live

- `dim_customer` DDL: primary key on `customer_id`, column lengths vs the schema's 100 / 255 / numeric(12,2), nullability of `country_name`/`region`.
- `dim_country.country_code`: data type, case, padding, uniqueness of active rows.
- Contents (and existence) of `/mnt/landing/conf/job.properties` on the engine host — it may currently be the real source of the prod settings.
- A sample input file: `;` separator, header row, `yyyy-MM-dd` dates, UTF-8, and whether empty fields are empty strings or missing columns.
- Expected daily volume (drives the upsert-strategy decision in #11).
- Whether "customers without an email are not loaded" is an intended business rule or an accident (#3).

---

### Suggested order of work

1. Fixes #1, #2, #3, #4 (correctness: nothing may disappear silently; failures must exit non-zero).
2. Fixes #5, #6, #7 (idempotency and configuration/secret hygiene for TMC).
3. Fixes #8–#14 (robustness and operability), then version bump, publish, create the TMC task per the checklist, run once against a copy of a real file with `PROD` context pointing at a non-prod schema, check counts, then schedule.
