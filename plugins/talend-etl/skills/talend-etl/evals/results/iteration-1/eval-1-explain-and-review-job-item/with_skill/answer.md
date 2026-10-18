# LOAD_CUSTOMERS 0.1 - what it does, and what to fix before TMC

**Job** `LOAD_CUSTOMERS` v0.1, Standard (DI) job, folder `dwh/dimensions`, status **DEV**, last modified 2026-09-18 (Studio 8 item format).
**Purpose (from the Main tab):** "Load customer dimension - reads daily customer CSV drops, enriches with country, upserts dim_customer."

I read the `.item`/`.properties` directly and ran the skill's `inspect_job_item.py --review` on it; everything below is from the XML, not from running the job.

---

## 1. End-to-end flow

```
tPrejob_1 --OnComponentOk--> tDBConnection_1 "DWH"        (PostgreSQL 12, Auto Commit OFF)

tFileList_1 "list_csv"  (context.INPUT_DIR, mask context.FILE_MASK, by name ASC)
   |--Iterate (one pass per file)-->
   tFileInputDelimited_1 "read_customers"  (file = tFileList_1_CURRENT_FILEPATH)
      |--row1 (Main)------------------> tMap_1 "enrich"
      |--rejects ----------------------> tLogRow_2 "log_rejects"   [DEACTIVATED]
   tDBInput_1 "lkp_country" --lkp (Lookup)--> tMap_1
                                   tMap_1 --out_ok---------> tDBOutput_1 "dim_customer" (Insert or update)
                                   tMap_1 --out_no_country-> tLogRow_1 "log_no_country" (stdout)
   |--OnSubjobOk ---> tDBCommit_1   (commit once, after ALL files)
   |--OnSubjobError-> tDie_1        (code 4, "Load failed: " + tDBOutput_1_ERROR_MESSAGE)

tPostjob_1 --OnComponentOk--> tDBClose_1
```

Three subjobs, run in this order regardless of canvas position:

1. **"Open DWH connection" (tPrejob).** Opens one PostgreSQL connection with `Auto Commit` off and the JDBC property `reWriteBatchedInserts=true`. Every DB component downstream uses this connection (`Use an existing connection`), so the whole run is one transaction until `tDBCommit_1`.
2. **"Load customers" (tFileList, the main work).** Lists `customers_*.csv` in `INPUT_DIR` (no subdirectories, case-sensitive, sorted by file name ascending) and runs the entire read -> map -> write chain once per file.
3. **"Cleanup" (tPostjob).** Closes the connection. Runs even after a failure (tDie has `Exit the JVM immediately` off), so a failed run is rolled back implicitly when PostgreSQL sees the connection close with an open transaction.

### Inputs

| Input | What | Settings that matter |
|---|---|---|
| `tFileInputDelimited_1` | Each CSV drop | `;` field separator, `\n` row separator, CSV options on (text enclosure `"`, escape `\`), header = 1, UTF-8, `Trim all columns`, `Check each row structure against schema`, `Die on error` **off** (bad rows go to the reject link). Schema: `customer_id` Integer **key, not nullable**; `full_name`(100), `email`(255), `country_code`, `signup_date` Date `yyyy-MM-dd`, `lifetime_value` BigDecimal(12,2). |
| `tDBInput_1` (lookup) | `SELECT country_code, country_name, region FROM dim_country WHERE active = true` | Shared connection, cursor fetch 1000, `Trim all columns` off. `country_code` is `bpchar` (CHAR(2)) in the DB. |

### Outputs

| Output | What | Settings that matter |
|---|---|---|
| `tDBOutput_1` -> `public.dim_customer` | The dimension | `Action on table` None, `Action on data` **Insert or update**, `Use field options` on: `customer_id` is the update key, insertable, **not updatable**; all other columns insert+update. `Use Batch Size` ticked with `context.BATCH_SIZE`, `Commit every` 10000, `Die on error` **off**, no reject link. |
| `tLogRow_1` (stdout, table mode) | Customers whose country code is not in `dim_country` | Only `customer_id` + `country_code`. These rows are **not** written to `dim_customer`. |
| `tLogRow_2` | Would print rows the CSV reader rejected | **Deactivated**, so the reject link is dead. |

### The tMap ("enrich")

- **Lookup `lkp`** = `dim_country` (active rows only). `Lookup Model` = **Load once**, `Match Model` = **Unique match**, `Join Model` = **Inner Join**.
  Join key: `lkp.country_code == StringHandling.UPCASE(row1.country_code)` - the file's code is upper-cased and compared with the DB code as stored. Load once means the whole active country list is pulled into memory before the first row of each file (and, because the tMap sits inside the Iterate loop, it is re-queried **for every file**, which is fine for a small table). Unique match returns the *last* matching lookup row if `dim_country` ever has two active rows for one code. Inner join means a customer with no matching country is **dropped** from `out_ok` and only appears in the reject output.
- **Var table** (computed once per row, reused by outputs):
  - `clean_name = StringHandling.TRIM(row1.full_name)`
  - `clean_email = row1.email == null ? null : StringHandling.DOWNCASE(row1.email)`
- **Output `out_ok`** (-> dim_customer), with the **expression filter** `Var.clean_email != null && Var.clean_email.contains("@")`:
  `customer_id`, `full_name = Var.clean_name`, `email = Var.clean_email`, `country_name = lkp.country_name`, `region = lkp.region`, `signup_date`, `lifetime_value`, `load_ts = TalendDate.getCurrentDate()`.
- **Output `out_no_country`** has `Catch lookup inner join reject` = true: receives the main rows that found no active country.
- tMap `Die on error` = **on**: any exception inside an expression kills the subjob (that is what triggers `OnSubjobError -> tDie`).

So the business rule as built is: *a customer is loaded only if its country code is an active row in `dim_country` AND its email contains "@". Everything else is either printed to stdout (unknown country) or vanishes (bad email, unparsable row).*

### What the contexts are for

Both contexts come from one repository context group (`repositoryContextId="_ctxGroup01"`, i.e. a shared `Contexts/...` item - make sure you also have that item, not just the job):

| Variable | Type | `Default` | `PROD` | Used by |
|---|---|---|---|---|
| `INPUT_DIR` | Directory | `/data/in` | `/mnt/landing/customers` | tFileList directory, **and** the implicit context-load file path |
| `FILE_MASK` | String | `customers_*.csv` | same | tFileList filemask |
| `DB_HOST` / `DB_PORT` / `DB_NAME` | String / Integer / String | `localhost` / 5432 / `dwh` | `dwh-prod.internal` / 5432 / `dwh` | tDBConnection |
| `DB_USER` / `DB_PASS` | String / **Password** | `etl` / `enc:system.encryption.key.v1:...` | `etl_prod` / `enc:system.encryption.key.v1:...` | tDBConnection |
| `BATCH_SIZE` | Integer | 1000 | 5000 | tDBOutput batch size (see finding 4 - it is not actually in effect) |

`Default` holds dev-safe values (localhost) - good: a run that forgets `--context=PROD` cannot hit production.

**Job-level settings (Job view > Extra / Stats & Logs):**
- **Implicit tContextLoad from file**: `context.INPUT_DIR + "/../conf/job.properties"`. At start-up the job reads `key=value` lines from that file and overwrites the context variables of the same name. With `PROD` that resolves to `/mnt/landing/conf/job.properties`; with `Default` to `/data/conf/job.properties`. This is the colleague's mechanism for per-server values and probably the real `DB_PASS`.
- Stats & Logs: `Use Project Settings`, statistics + logs on (where they go - console, file or AMC tables - is defined in the *project* settings, not in this file).
- log4j active; Studio JVM args `-Xms256M -Xmx2048M -Dfile.encoding=UTF-8` (Studio-only, see finding 10).
- Routines referenced: `TalendDate`, `StringHandling`, plus a user routine **`CustomerUtils`** that no expression in this job actually calls; it must still exist in the project or the job will not compile.

---

## 2. What I would fix before scheduling it in TMC

Ordered by risk. The first four are blockers in my view (they are the "0 = blocker" lines of the design-review scorecard: error handling, transactions, data loss, secrets).

### 1. Three places where rows disappear silently (exit code 0, TMC shows green)

a. **CSV rejects go nowhere.** `tFileInputDelimited_1` has `Die on error` off, so a row with a non-numeric/empty `customer_id`, a date not in `yyyy-MM-dd`, a bad `lifetime_value` or the wrong number of fields is sent to the reject link - whose target `tLogRow_2` is deactivated. The row is lost and nothing is counted.
b. **The email filter drops rows with no reject.** `out_ok`'s filter `clean_email != null && contains("@")` is the only output those rows could reach; there is no output with `Catch output reject`. A customer with a blank or malformed email never reaches `dim_customer` and is not logged. For a dimension table that is almost certainly wrong: you usually want the customer row with `email = null` (or flagged), not a missing dimension member.
c. **DB write errors do not fail the job.** `tDBOutput_1` has `Die on error` off and no reject link (a reject link is not even possible with batch on). A failed statement/batch only sets `tDBOutput_1_ERROR_MESSAGE` and the component carries on; the subjob ends "OK", `tDBCommit_1` commits whatever did get in, and the exit code is 0. The `OnSubjobError -> tDie_1` branch - whose message is built from `tDBOutput_1_ERROR_MESSAGE` - will **never** fire for a DB error. It only fires for exceptions elsewhere (tMap, tDBInput, tFileList), and then the message is `"Load failed: null"`.

**Fix:** tick `Die on error` on `tDBOutput_1` (so a DB error raises, `OnSubjobError` fires, nothing is committed), or untick batch and route its reject link to a reject table/file. Route the tFileInputDelimited reject link to a persisted sink (`tFileOutputDelimited` under a `REJECT_DIR` context var, or a `stg_customer_reject` table) and add a second tMap output with `Catch output reject` for the email filter. Replace the tDie message with a tLogCatcher-based one (or a generic message); finish with `tWarn` when reject counts are > 0 so TMC logs show it.

### 2. Transaction and error path

The design intent is good (one shared connection, `Auto Commit` off, one `tDBCommit` after all files, `tDBClose` in tPostjob) and, because the write is an upsert, a re-run is idempotent. Two gaps:

- No explicit rollback on the error branch. Make it `OnSubjobError -> tDBRollback_1 -> tDie_1` instead of relying on the connection close.
- `Commit every = 10000` on `tDBOutput_1` is ignored when `Use an existing connection` is on; the real commit boundary is the whole run. That is fine for a daily dimension load, but be aware that a long multi-file run holds one open transaction on `dim_customer` for its whole duration. If volume grows, commit per file (`tDBCommit` inside the iteration, `Close` off) and archive each file after its commit (see 3).

### 3. Files are never archived, and "no files" is a silent success

Nothing moves or renames a processed file, so every scheduled run re-processes **every** `customers_*.csv` still sitting in `/mnt/landing/customers`. Upsert keeps it correct, but run time grows daily and the "last match wins" order depends on file names sorting correctly (`By file name ASC`). Add `tFileCopy`/`tFileMove` (or rename to `.done`) after the commit, driven from the same iterate or a second `tFileList`; and guard against half-written drops (a `.done` marker or a size check with `tFileProperties`).

`Generate error if no file found` is not set and there is no check on `tFileList_1_NB_FILE`, so a day with no drop ends green with 0 rows. Add a `Run if` on `((Integer)globalMap.get("tFileList_1_NB_FILE")) == 0` -> `tWarn` (or `tDie` if the daily file is an SLA).

### 4. Secrets and the implicit context-load file

- `DB_PASS` values in the item are `enc:system.encryption.key.v1:...`. That is AES encrypted with the **stock Studio key**, which is identical on every Studio install of that version - treat it as obfuscation, not protection. Those values are in Git (the `.item`) and would be in the build zip's `contexts/PROD.properties`. For TMC, blank the passwords in the context group and supply `DB_PASS` as a **sensitive task parameter** in TMC (or bind the DB parameters to a TMC `Connection`). TMC stores it encrypted and masks it in logs.
- The implicit context file `context.INPUT_DIR + "/../conf/job.properties"` is (i) located relative to the **data landing share**, which is typically broadly writable - a bad place for a file that holds a production DB password; (ii) a dependency that must exist on the **Remote Engine host** (it cannot work on a Cloud Engine at all); (iii) a second override mechanism competing with TMC task parameters - which one wins for a key present in both is version-dependent (the generated code's `tContextLoad` block tells you). Pick one: for TMC, turn the implicit load off and let the task parameters be the single source of truth. If you must keep the file (e.g. for Studio/dev runs), give it its own `CONFIG_FILE` context var pointing at a locked-down path, keep `Print operations` on outside PROD, and leave it empty/absent in PROD.

### 5. `Insert or update` + batch: the batch size does nothing, and it is the performance hot-spot

`Use Batch Size` is only effective for `Insert`, `Update` and `Delete` actions; with `Insert or update` Talend goes row by row (existence check + INSERT or UPDATE, two round trips per row) and `BATCH_SIZE` (1000/5000) has no effect - nor does `reWriteBatchedInserts=true`. For a few thousand customers a day this is acceptable; beyond ~100k rows it will be the slow part. The PostgreSQL-native fix is: `tDBOutput_1` as plain `Insert` with batch into `stg_customer` (truncate first) `--OnSubjobOk-->` `tDBRow` with `INSERT INTO dim_customer (...) SELECT ... FROM stg_customer ON CONFLICT (customer_id) DO UPDATE SET ...` (PostgreSQL 12 has `ON CONFLICT`; `MERGE` only from 15). Either way, confirm `dim_customer` has a **unique index on `customer_id`** - the Talend upsert's existence check does not guarantee uniqueness by itself.

### 6. Null-safety in the tMap (the job will die on a blank name or country)

`StringHandling.TRIM(row1.full_name)` and `StringHandling.UPCASE(row1.country_code)` throw `NullPointerException` on a null argument; the author guarded `clean_email` but not these two, even though both columns are nullable in the schema. With tMap `Die on error` on, one such row aborts the entire run (exit code 4, message "Load failed: null"). Use `row1.full_name == null ? null : StringHandling.TRIM(row1.full_name)` and `row1.country_code == null ? null : StringHandling.UPCASE(row1.country_code)` (whether an empty CSV field arrives as `null` or `""` depends on the reader settings - guard regardless).

### 7. Lookup-key hygiene

The file side is upper-cased; the DB side is not. `dim_country.country_code` is `CHAR(2)` (`bpchar`) and `Trim all columns` is off on the lookup, so any code stored lower-case or shorter than 2 chars (space-padded) will never match and the customer silently goes to `out_no_country`. Make both sides canonical: `SELECT UPPER(TRIM(country_code)) AS country_code, ...` in the lookup query. Also decide whether "unknown country" should really exclude the customer; the usual dimension pattern is `Left Outer Join` + `lkp.region == null ? "UNKNOWN" : lkp.region`, with the unmatched codes written to a reject table and a `tWarn`, rather than dropping the member. Add `ORDER BY` (or a uniqueness check) if duplicate active codes are possible, since `Unique match` returns the last one loaded.

### 8. Debug leftovers

`tLogRow_1` prints every unmatched row to stdout in table mode - on TMC that lands in the task log, is not queryable and bloats log retention. Replace with a persisted reject sink (see 1). Remove the deactivated `tLogRow_2` once the reject link has a real target. `Print unique name` etc. are noise in production logs.

### 9. Observability

Stats & Logs are on via project settings - find out *where* they go (Project Settings > Job Settings > Stats & Logs). If they target AMC tables, that DB must be reachable from the Remote Engine and the tables must exist; TMC has no AMC. If they are "On Console" they are only in the task log. Add a `tWarn` with row counts (`tFileInputDelimited_1_NB_LINE`, `tDBOutput_1_NB_LINE_INSERTED/UPDATED`, reject counts) at the end so a run is auditable from the TMC log, and consider a control-table row per run.

### 10. TMC-specific setup

- **Engine:** this job reads a local directory and reaches `dwh-prod.internal`, so it needs a **Remote Engine** (or Remote Engine Cluster) on a host that mounts `/mnt/landing/customers`; a Cloud Engine cannot see either.
- **JVM:** the Studio JVM arguments (`-Xms256M -Xmx2048M -Dfile.encoding=UTF-8`) are *not* carried into TMC. Define a **Run profile** on the engine with the same (or `-XX:MaxRAMPercentage`) and `-Dfile.encoding=UTF-8`; also pin `-Duser.timezone` because `load_ts = TalendDate.getCurrentDate()` uses the engine's clock/zone.
- **Task:** set `Parameters` (`DB_*`, `INPUT_DIR`, `FILE_MASK`, `BATCH_SIZE`) explicitly - do not rely on the baked `PROD` context; mark `DB_PASS` sensitive. Set `Allow parallel run of this task` **off** (two overlapping runs would double-process the landing directory and fight over the same rows), set a `Timeout`, and give the schedule an explicit **time zone**.
- **Artifact hygiene:** bump the version (0.1 -> 1.0) and change status from DEV before publishing; TMC tasks pin an artifact version. Make sure the context group item and the `CustomerUtils` routine are in the project you publish from, or the build fails.
- **Encoding:** the reader sets UTF-8 explicitly, good; the Run profile `-Dfile.encoding=UTF-8` covers stdout/log output.

---

## 3. Things that are fine as they are

- Correct tPrejob/tPostjob pattern: connection opened once, closed in tPostjob, `tDie` with `Exit the JVM immediately` off so cleanup still runs and the exit code (4) is non-zero for TMC.
- `Default` context is dev-safe; all hosts/paths/credentials are context variables, nothing hard-coded; `DB_PASS` is typed `Password`.
- Iterate is sequential (`Enable parallel execution` off) - the right choice with a shared connection.
- Lookup query is already filtered (`active = true`) and projects only the three columns used.
- CSV options are set properly (`;` delimiter, `"` enclosure, header 1, `Check each row structure`), and the Date column has a pattern.
- `Insert or update` makes re-runs idempotent, which is the right default for a dimension.

## 4. Suggested order of work

1. Error path: `Die on error` on `tDBOutput_1`, `tDBRollback` before `tDie`, meaningful failure message. (half a day)
2. Reject handling: persist CSV rejects, catch the email-filter rejects, decide the unknown-country rule (left join + UNKNOWN vs. reject). (half a day + a decision from the data owner)
3. Null guards in the Var table and canonical lookup key. (an hour)
4. Secrets/config: blank passwords in the context group, disable implicit load for TMC, define task parameters. (an hour, plus TMC admin)
5. Archive-after-load and the no-file check. (half a day)
6. Optional: staging + `ON CONFLICT` upsert if volumes justify it.

Caveat: this is read from the exported XML, not from a run; exact Studio labels are from the Talend 8 documentation and should be confirmed in your Studio release's Component view. If you can share the context-group item (`Contexts/*.item`), `CustomerUtils.item` and the project settings export, I can check the Stats & Logs target and the routine for you.
