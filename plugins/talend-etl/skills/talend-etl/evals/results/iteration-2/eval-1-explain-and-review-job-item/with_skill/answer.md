# LOAD_CUSTOMERS 0.1 - what it does, and what to fix before TMC production

Source: `LOAD_CUSTOMERS_0.1.item` + `LOAD_CUSTOMERS_0.1.properties` (Standard job, Studio 8 shape,
status `DEV`, folder `dwh/dimensions`, purpose "Load customer dimension - Reads daily customer CSV
drops, enriches with country, upserts dim_customer"). I parsed the XML with the skill's
`inspect_job_item.py --review` and then read every node and link by hand. What is **not** in these
two files and therefore unverified here: the repository context group `_ctxGroup01` the contexts
point at, the user routine `CustomerUtils`, Project Settings (Stats & Logs destination, log4j
template), and the `conf/job.properties` file the job loads at start-up.

## 1. One-paragraph summary

Once per run the job opens one PostgreSQL connection (autocommit off), then iterates over every
file in `context.INPUT_DIR` matching `context.FILE_MASK` (`customers_*.csv`). Each file is read as
a `;`-delimited UTF-8 CSV with one header line, cleaned in a `tMap` (trim name, lower-case email),
inner-joined to `dim_country` on an upper-cased country code, filtered to rows whose email
contains `@`, and written to `dim_customer` with `Insert or update` keyed on `customer_id`.
Rows with an unknown country are printed to the console. One `COMMIT` is issued after **all**
files are processed; on any uncaught error the job dies with exit code 4; the connection is
closed in `tPostjob` either way.

## 2. Canvas, as the XML describes it

```
[tPrejob_1] --OnComponentOk--> [tDBConnection_1 "DWH"]   PostgreSQL 12, Auto Commit OFF,
                                                         Additional params "reWriteBatchedInserts=true"

[tFileList_1 "list_csv"] --Iterate--> [tFileInputDelimited_1 "read_customers"] --row1--> [tMap_1 "enrich"] --out_ok--------> [tDBOutput_1 "dim_customer"]
  dir context.INPUT_DIR                 file = tFileList_1_CURRENT_FILEPATH          ^  lkp (lookup)     --out_no_country--> [tLogRow_1 "log_no_country"]
  mask context.FILE_MASK (glob)         ';' sep, header 1, UTF-8, CSV options        |
  case-sensitive, order by name ASC     Die on error OFF, Trim all,                  [tDBInput_1 "lkp_country"]
                                        Check each row structure                     SELECT country_code, country_name, region
                                           --rejects--> [tLogRow_2 "log_rejects"]    FROM dim_country WHERE active = true
                                                        (DEACTIVATED)
  --OnSubjobOk-----> [tDBCommit_1]  (Close Connection OFF)
  --OnSubjobError--> [tDie_1]  "Load failed: " + tDBOutput_1_ERROR_MESSAGE, code 4, Exit JVM OFF

[tPostjob_1] --OnComponentOk--> [tDBClose_1]
```

Job-level settings: `Implicit tContextLoad` ON from file
`context.INPUT_DIR + "/../conf/job.properties"`; Stats & Logs ON (statistics + logs, **using
Project Settings**, so the destination is whatever the project says); log4j active; JVM args
`-Xms256M -Xmx2048M -Dfile.encoding=UTF-8`; multi-thread execution OFF.

## 3. Inputs

| Input | Where | Details |
|---|---|---|
| Customer CSV drops | `tFileList_1` -> `tFileInputDelimited_1` | Directory `context.INPUT_DIR`, mask `context.FILE_MASK` as a glob (`Use Glob Expressions as Filemask` on), files only, no sub-directories, `Case Sensitive = Yes`, `Order by = By file name ASC`. Each file: field separator `";"`, row separator `"\n"`, text enclosure `"`, escape `\`, `Header = 1`, `Footer = 0`, `CSV options` on, `Encoding "UTF-8"`, `Remove empty row`, `Trim all columns`, `Check each row structure against schema`, **`Die on error` OFF**. Schema: `customer_id` Integer (key, not nullable), `full_name` String(100), `email` String(255), `country_code` String, `signup_date` Date `"yyyy-MM-dd"`, `lifetime_value` BigDecimal(12,2). |
| Country reference (lookup) | `tDBInput_1` on the shared connection | `SELECT country_code, country_name, region FROM dim_country WHERE active = true`, cursor 1000. Schema `country_code` String(2) key not-null (source type `bpchar`), `country_name` String(80), `region` String(40). |
| Runtime configuration | Implicit Context Load | `key=value` file at `<INPUT_DIR>/../conf/job.properties` (so `/data/conf/job.properties` for `Default`, `/mnt/landing/conf/job.properties` for `PROD`), loaded before `tPrejob`. |

## 4. Outputs

| Output | Component | Details |
|---|---|---|
| `dim_customer` | `tDBOutput_1` | Shared connection, `Action on table = None`, **`Action on data = Insert or update`**, `Die on error` OFF, `Use Batch Size` ON with `context.BATCH_SIZE`, `Commit every = 10000` (ignored: with an existing connection the commit is controlled by `tDBConnection`/`tDBCommit`). `Use field options`: `customer_id` is the Update Key, insertable, **not updatable**; every other column is inserted and updated. Columns written: customer_id, full_name, email, country_name, region, signup_date, lifetime_value, load_ts. **No reject link.** |
| Console | `tLogRow_1` (Table mode) | `customer_id` + `country_code` of rows whose country was not found in `dim_country`. |
| Console (nothing) | `tLogRow_2` | Target of the file reject link, but **deactivated** - malformed CSV rows go nowhere. |
| Transaction | `tDBCommit_1` | One commit after the whole `tFileList_1` subjob (all files) succeeds. Nothing is committed if any file fails. |
| Exit code | `tDie_1` | 4 on `OnSubjobError` of the load subjob; otherwise 0. |

## 5. Transformations and how the lookup works

**Per row of each file**, inside `tMap_1 "enrich"` (`Die on error` ON, so an exception in any
expression kills the job):

1. **Lookup `lkp`** (dashed link from `tDBInput_1`): `Lookup Model = Load once`, `Match Model =
   Unique match`, `Join Model = Inner Join`. Key expression: `lkp.country_code ==
   StringHandling.UPCASE(row1.country_code)`.
   - *Load once* means the whole `dim_country` result set is read into an in-memory hash **before
     the first main row of that flow**. Because the flow sits inside the `tFileList` Iterate, the
     lookup query is re-executed **once per file**, not once per job. Cheap here (a country table),
     but worth knowing.
   - *Unique match* returns the last loaded match; fine because `country_code` is the key.
   - *Inner Join* means a main row with no matching active country is **removed from `out_ok`**
     and offered to the output that has `Catch lookup inner join reject` = true, which is
     `out_no_country`. Note the business consequence: a customer whose country is missing or has
     `active = false` in `dim_country` is **not loaded at all**, only printed.
   - Matching is `String.equals`: only the main side is upper-cased, so `dim_country.country_code`
     must already be stored upper-case and un-padded (it is `bpchar(2)`, so no padding issue for
     2-letter codes).
2. **Var table** (evaluated after the lookup, before outputs):
   `clean_name = StringHandling.TRIM(row1.full_name)`;
   `clean_email = row1.email == null ? null : StringHandling.DOWNCASE(row1.email)`.
3. **Output `out_ok`** (filter `Var.clean_email != null && Var.clean_email.contains("@")`):
   `customer_id`, `full_name = Var.clean_name`, `email = Var.clean_email`,
   `country_name = lkp.country_name`, `region = lkp.region`, `signup_date`, `lifetime_value`
   pass-through, `load_ts = TalendDate.getCurrentDate()`.
   Rows that fail the filter are **silently discarded**: there is no output with
   `Catch output reject`. So customers with a missing or malformed email never reach
   `dim_customer` and are not logged anywhere.
4. **Output `out_no_country`** (`Catch lookup inner join reject`): `customer_id`, `country_code`
   -> `tLogRow_1`.

Then `tDBOutput_1` upserts: for each row it runs the generated `Insert or update` logic (per the
references this is two statements per row on PostgreSQL - an existence check / insert then
update - not a `MERGE` or `INSERT ... ON CONFLICT`; confirm the exact shape in the Code view).
Because `Insert or update` is row-by-row, `Use Batch Size` and the connection's
`reWriteBatchedInserts=true` have **no effect**.

Error path: any exception in the load subjob (file unreadable, tMap NPE, SQL error with
`Die on error` ON...) triggers `OnSubjobError -> tDie_1`, exit code 4, `tPostjob` still runs and
closes the connection (uncommitted work is rolled back by the close). The `tDie` message
appends `tDBOutput_1_ERROR_MESSAGE`, which is only populated when `tDBOutput_1` itself failed;
for every other failure it prints `Load failed: null`.

## 6. Contexts - what they are for

All eight variables come from one repository context group (`repositoryContextId="_ctxGroup01"`,
whose `.item` is not in your export). Two contexts exist: `Default` (the job's default) and `PROD`.

| Variable | Type | Default | PROD | Used by |
|---|---|---|---|---|
| `INPUT_DIR` | Directory | `/data/in` | `/mnt/landing/customers` | `tFileList_1` directory; also the base of the implicit context file path |
| `FILE_MASK` | String | `customers_*.csv` | `customers_*.csv` | `tFileList_1` filemask (glob) |
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` | String/Integer/String/String | `localhost` / 5432 / `dwh` / `etl` | `dwh-prod.internal` / 5432 / `dwh` / `etl_prod` | `tDBConnection_1` |
| `DB_PASS` | **Password** | `enc:system.encryption.key.v1:...` | `enc:system.encryption.key.v1:...` | `tDBConnection_1` |
| `BATCH_SIZE` | Integer | 1000 | 5000 | `tDBOutput_1` batch size (currently a no-op, see above) |

Good things: no host, path or credential is hard-coded in any component; `Default` points at
`localhost`, so a run that forgets `--context=PROD` cannot hit production; the password is typed
`Password` (stored AES-GCM encrypted, masked in TAC/TMC).

Things to understand about them:

- The `enc:system.encryption.key.v1:` values can only be decrypted by a Studio/CommandLine that
  has the **same `studio.keys`** as your colleague's installation. If you import the item into
  a Studio with a different key the password field will decrypt to garbage. The stock v1 key is
  the same in every Studio download, so treat these as obfuscated, not secret. Plan to set the
  real password in TMC task `Parameters` (marked sensitive) and never rely on the baked-in value.
- **Implicit Context Load** re-reads `key=value` pairs from `<INPUT_DIR>/../conf/job.properties`
  at start-up and overwrites matching context variables. Two consequences for TMC:
  (a) the file must exist on the **Remote Engine host** (not the Studio machine) or the job
  silently runs on the compiled context values and only warns; (b) depending on the Studio
  release, implicit-load values can **override** the `--context_param` values that TMC task
  Parameters are delivered as, so a value you set in TMC may be silently replaced by what is in
  that file (confirm in the generated code block in the Code view). The path is computed from
  the *pre-load* `INPUT_DIR`, so the file cannot relocate itself. Putting configuration
  (potentially a plaintext DB password) one level above the landing directory is also a weak place
  for it.

## 7. Dependencies

- Routines: `TalendDate`, `StringHandling` (system) and **`CustomerUtils`** (user routine,
  `_routine_Custom01`). Nothing in the job references `CustomerUtils`, but it is declared as a
  dependency, so the routine must exist in the project for the job to build. Ask for it (or remove
  the dependency in Job Settings) before publishing.
- Context group `_ctxGroup01` (see above).
- DB objects: `public.dim_customer` (must have a unique key/PK on `customer_id`; `Action on table =
  None`, so the table is never created), `public.dim_country(country_code, country_name, region,
  active)`.
- Filesystem: `INPUT_DIR` and `INPUT_DIR/../conf/job.properties` reachable from the engine.
- No `tRunJob` children, no joblets, no repository metadata connection (everything is built-in).
- No test cases in the export.

## 8. What I would fix before scheduling it in TMC

### Blockers (the job can report success while loading the wrong thing)

1. **`tDBOutput_1` has `Die on error` OFF and no reject link.** A row that fails (constraint
   violation, `full_name` longer than 100, bad date) is swallowed; the job continues and exits 0.
   On PostgreSQL this is worse: with autocommit off, the first failed statement puts the
   transaction in the aborted state, so **every subsequent row fails too** (also swallowed), and
   the final `COMMIT` behaves as a rollback. You can end a "successful" run with nothing loaded.
   Fix: either check `Die on error` (then the error reaches `OnSubjobError -> tDie_1`, whose
   message finally makes sense), or keep it off **and** add a reject link to a
   `tFileOutputDelimited`/`tDBOutput` reject table and fail the job when `NB_LINE_REJECTED > 0`.
   Also add `tDBRollback_1` on the `OnSubjobError` path before `tDie_1` for explicitness.
2. **Silent data loss in `tMap_1`.** Customers without a valid email are dropped by the `out_ok`
   filter with no `Catch output reject` output; customers with an unknown/inactive country are
   only printed to the console. Decide the business rule (load with `email = null` / `region =
   'UNKNOWN'` via a Left Outer Join, or genuinely exclude), and in all cases **persist** the
   excluded rows (reject table or file keyed by file name + `load_ts`) and reconcile counts
   (`tFileInputDelimited_1_NB_LINE` vs `tDBOutput_1_NB_LINE_INSERTED + NB_LINE_UPDATED` + rejects).
3. **File-level rejects are thrown away.** `tFileInputDelimited_1` has `Die on error` OFF and
   `Check each row structure against schema` ON, so wrong-column-count and unparseable rows go to
   the `rejects` link - whose target `tLogRow_2` is **deactivated**. Route rejects to a file/table
   (they carry `errorCode`/`errorMessage`) or check `Die on error` so a broken file fails the run.
4. **No archive step, so every run re-reads every file ever dropped.** Nothing moves or deletes
   processed files. The upsert makes this idempotent for `dim_customer`, but run time, console
   noise and risk grow with every day. Add, after `tDBCommit_1` (`OnSubjobOk`), a second
   `tFileList` + `tFileCopy` (`Remove source file`) into an archive dir per run date, or write a
   processed-file control table and skip known files. Move files only after the commit.
5. **Zero files is not detected.** `tFileList` with no match simply does not iterate and the job
   exits 0; TMC will show green on the day the upstream drop fails. Add
   `tFileList_1 --OnSubjobOk--> tJava/Run if` on
   `((Integer)globalMap.get("tFileList_1_NB_FILE")) == 0` -> `tWarn` or `tDie` depending on
   whether a missing daily file is an error.

### Should fix (robustness and performance)

6. **Null-safety in `tMap_1`.** `Die on error` is ON, so any NPE aborts the run.
   `StringHandling.TRIM(row1.full_name)` and `StringHandling.UPCASE(row1.country_code)` are
   called on nullable columns without a guard, while `clean_email` is guarded - the author knew
   nulls occur. Make them consistent:
   `row1.full_name == null ? null : row1.full_name.trim()` and
   `row1.country_code == null ? null : row1.country_code.trim().toUpperCase()` (the lookup then
   lands cleanly in `out_no_country` instead of crashing). Confirm whether empty CSV fields arrive
   as `null` or `""` in the Code view; `""` also needs handling for the join.
7. **`Insert or update` on PostgreSQL is row-by-row and ignores batching.** At daily-dimension
   volumes it will work, but it is the slowest option and defeats both `Use Batch Size` and
   `reWriteBatchedInserts=true`. Preferred: `tDBOutput` **Insert** in batch mode into a truncated
   `stg_customer`, then one `tDBRow` with `INSERT INTO dim_customer ... SELECT ... FROM stg_customer
   ON CONFLICT (customer_id) DO UPDATE SET ...` (set-based, transactional, and `BATCH_SIZE` becomes
   meaningful again). If you keep the component as is, at least switch to `Update or insert` if
   most customers already exist, and remove the misleading `Commit every = 10000`.
8. **Transaction boundary = whole run.** One commit after all files is correct for
   all-or-nothing, but a failure on file 7 of 7 rolls back files 1-6 and the restart redoes
   everything. Decide deliberately: commit per file (move `tDBCommit` to
   `OnComponentOk` of `tFileInputDelimited_1` and archive that file right after) is the usual
   choice for daily drops; if you keep run-level commit, keep the archive step after it.
9. **`tDie_1` message.** `"Load failed: " + tDBOutput_1_ERROR_MESSAGE` reads `Load failed: null`
   for every non-`tDBOutput` failure. Use a `tLogCatcher --> tDBOutput/tFileOutputDelimited`
   subjob (catches Java exceptions, `tDie`, `tWarn`) and let `tDie` print
   `tFileList_1_CURRENT_FILE` plus a generic text. Also check whether Project Settings actually
   point Stats & Logs at a database/file - the job only says "use project settings".
10. **`tLogRow_1` in the flow.** Fine in DEV; in production it fills TMC logs. Replace with a
    reject file/table (item 2) or deactivate.
11. **Lookup semantics.** Inner join + `WHERE active = true` means deactivating a country in
    `dim_country` silently stops loading its customers. For a dimension load a Left Outer Join
    with `lkp.region == null ? "UNKNOWN" : lkp.region` is normally safer; keep the inner-join
    reject output only if exclusion is the intended rule. Also decide whether `tFileList`
    `Case Sensitive = Yes` is intended (`Customers_20261018.CSV` would be ignored).
12. **Housekeeping before publish.** Bump the version (0.1 -> 1.0) and set status from `DEV`;
    remove or obtain the unused `CustomerUtils` routine dependency; delete the deactivated
    `tLogRow_2`; `customer_id` not updatable is correct (it is the key) - keep it. Add a
    `.screenshot`-independent description to the `tMap` (Documentation tab) for the next person.

### TMC task configuration (operations, not design)

- **Engine:** this job reads a local filesystem (`/mnt/landing/customers`), so it needs a
  **Remote Engine** (or Remote Engine Cluster with identical mounts) in the PROD environment; a
  Cloud Engine cannot see `/mnt/landing` and will fail with `FileNotFoundException`.
- **Run profile:** the Studio JVM args (`-Xmx2048M -Dfile.encoding=UTF-8`) are *not* applied by
  the Remote Engine by default; create a Run profile with `-Xms256M -Xmx2048M -Dfile.encoding=UTF-8
  -Duser.timezone=<zone>` and assign it (the timezone pins `load_ts`).
- **Parameters:** select `PROD` as the context, then set `DB_HOST`, `DB_USER`, `DB_PASS` (mark
  sensitive) and `INPUT_DIR` in the task - or bind the DB fields to a TMC `Connection`. Then
  either **disable the Implicit Context Load** (Job view > Extra) so TMC is the single source of
  truth, or make sure `/mnt/landing/conf/job.properties` on the engine does not contain keys
  TMC also sets. Do not depend on the `enc:` values baked into the artifact.
- **Allow parallel run of this task: OFF.** Two overlapping runs read the same files and upsert
  the same rows; expect lock waits/deadlocks and duplicated no-country logs.
- **Trigger:** explicit time zone on the schedule; set a task `Timeout`; consider a `tFileExist`
  on a `.done` sentinel or an mtime check (`tFileProperties`) so a file still being written is not
  picked up.
- **Log level:** `Info` (not `Debug`, which logs every SQL statement) once item 10 is done.
- **Smoke test** the published artifact on the Remote Engine with `Default`-like test values
  against a non-production DB first; verify exit code 4 on a forced failure actually marks the task
  `Execution failed`.

## 9. Scorecard (skill reference section 5)

| Area | Score 0-2 | Why |
|---|---|---|
| Schema / nullability | 1 | Nullable flags set and date patterns present; unguarded `TRIM`/`UPCASE` on nullable columns |
| Error handling* | 0 | `tDBOutput` errors swallowed, rejects to a deactivated component, misleading `tDie` message |
| Transactions* | 1 | Shared connection, autocommit off, single commit; no explicit rollback; PostgreSQL aborted-transaction trap with Die on error off |
| Context & secrets* | 2 | Everything in context, `Password` type, safe `Default`; TMC override/implicit-load interplay to sort out |
| Performance | 1 | Row-by-row upsert, batch settings inert, `tLogRow` in flow |
| Logging & monitoring | 1 | Stats & Logs via project settings; no reject persistence; console only |
| Idempotency / restart | 1 | Upsert is rerun-safe, but files are never archived and zero files = success |
| Documentation | 1 | Purpose/description and labelled components; no tMap comments |
| Naming | 2 | Meaningful labels and flow names |
| Tests | 0 | None in the export |
| Deployment readiness | 1 | JVM args set; version 0.1 / status DEV; unused routine dependency; Remote Engine + run profile needed |

Roughly 11/22 (50%) - below the 70% line the skill's checklist uses for "ready for PROD". Items 1-5
above are the ones I would not schedule without.
