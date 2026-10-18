# LOAD_ORDERS_PG_TO_SF - incremental PostgreSQL -> Snowflake every 15 minutes (Studio 8.0 R2025-xx, Talend Cloud / Remote Engine)

Assumptions: Standard (DI) Job; `orders.order_id` is the business key and `orders.updated_at` is
maintained on every insert/update; a few hundred to a few hundred thousand changed rows per
15-minute window (the first run is a full backfill); you run on a Remote Engine (Gen1, 2.13+/2.14,
Java 17) that can reach PostgreSQL, Snowflake and your SMTP relay. Labels below are Studio 8
Component-view labels; where the references I used mark a label `(unverified)`, I say so - confirm
it in the Component view of your R-release.

## 1. Design in one picture

```
S0  tPrejob_1 --OnComponentOk--> tDBConnection_pg (PostgreSQL, Auto Commit OFF)
              --OnComponentOk--> tSnowflakeConnection_sf (Auto Commit OFF)

S1  tSnowflakeInput_ctl ("SELECT LAST_WATERMARK FROM ETL_CONTROL WHERE JOB_NAME = ...")
        --row_ctl--> tJavaRow_wm            (globalMap WM_RAW, WM_LOW = watermark - overlap)
    tSnowflakeInput_ctl --OnSubjobOk--> S2

S2  tDBInput_pg_now ("SELECT now() AS run_start")
        --row_now--> tJavaRow_runstart      (globalMap RUN_START = source-DB clock; fail if WM_LOW missing)
    tDBInput_pg_now --OnSubjobOk--> S3

S3  tSnowflakeRow_truncate_stg ("TRUNCATE TABLE STG_ORDERS")        <- DDL, autocommits, nothing pending yet
    tSnowflakeRow_truncate_stg --OnSubjobOk--> S4

S4  tDBInput_pg_orders (WHERE updated_at > WM_LOW AND updated_at <= RUN_START, Use cursor)
        --row_orders--> tMap_orders --out_stg--> tSnowflakeOutput_stg (Insert into STG_ORDERS)
    tDBInput_pg_orders --OnSubjobOk--> S5

S5  tSnowflakeRow_merge (MERGE INTO ORDERS USING STG_ORDERS ON ORDER_ID)
        --OnComponentOk--> tSnowflakeRow_ctl_update (UPDATE ETL_CONTROL SET LAST_WATERMARK = RUN_START ...)
        --OnComponentOk--> tSnowflakeCommit_sf (Close Connection: unchecked)

ERR S1, S2, S3, S4, S5 start components --OnSubjobError--> tSendMail_fail --OnComponentOk--> tDie_1 (Error code 4)

S6  tLogCatcher_1 (Catch Java Exception, Catch tDie) --row_err--> tJavaRow_err   (collects error text for the mail)

S7  tPostjob_1 --OnComponentOk--> tDBClose_pg --OnComponentOk--> tSnowflakeClose_sf
```

Why this shape:

- Everything is one `OnSubjobOk` chain (S1 -> S5), so a failure anywhere stops the chain, fires one
  `OnSubjobError` handler, mails ops, and exits non-zero (`tDie` code 4). TMC marks the run
  `Execution failed`.
- The watermark is written **after** the MERGE and in the **same Snowflake connection /
  transaction** (`Auto Commit` off, one `tSnowflakeCommit` at the very end). If anything fails, the
  commit never happens, `tSnowflakeClose` in `tPostjob` discards the open transaction, and the
  control row still holds the previous watermark, so the next 15-minute run simply retries the same
  window. That is the restartability.
- Even if the TCK Snowflake output turned out to auto-commit its COPY regardless of the connection
  setting (the reference marks this `unverified`), the design stays safe: staging is truncated at
  the start of every run, MERGE is idempotent, and the watermark moves only on success.
- The upper bound of the window is the **source database clock** (`now()` from PostgreSQL), not the
  engine clock, and it becomes the new watermark. Never use `MAX(updated_at)` of the loaded rows.
- A small **overlap** (`WATERMARK_OVERLAP_SEC`, default 300) is subtracted from the stored watermark
  on read. It covers PostgreSQL transactions that set `updated_at = now()` but committed a minute
  or two later than a previous extract's upper bound. Re-reading those rows is harmless because
  the MERGE is an upsert.

## 2. Context group `CTX_ORDERS_INC` (contexts: `Default` = DEV values, `DEV`, `TEST`, `PROD`)

| Variable | Type | Example (DEV) | Notes |
|---|---|---|---|
| `ENV` | String | `"DEV"` | Used in mail subject only |
| `PG_HOST`, `PG_PORT`, `PG_DB`, `PG_SCHEMA` | String | `"pg-dev"`, `"5432"`, `"shop"`, `"public"` | Keep port as String (no parse failure when overridden from TMC) |
| `PG_USER` | String | | read-only DB user |
| `PG_PASS` | **Password** | | masked in Studio, `.item`, TMC |
| `PG_JDBC_PARAMS` | String | `"sslmode=require"` | goes to `Additional JDBC Parameters` |
| `SRC_TABLE` | String | `"orders"` | |
| `SF_ACCOUNT` | String | `"myorg-myaccount"` | full org-account identifier, leave Region empty |
| `SF_USER` | String | | |
| `SF_PASS` | **Password** | | or Key Pair auth, see section 6 |
| `SF_WAREHOUSE`, `SF_DB`, `SF_SCHEMA`, `SF_ROLE` | String | `"WH_ETL"`, `"DW_DEV"`, `"SALES"`, `"ETL_ROLE"` | |
| `CTL_SCHEMA`, `CTL_TABLE` | String | `"ETL"`, `"ETL_CONTROL"` | control table lives in Snowflake, same connection as the data |
| `STG_TABLE` | String | `"STG_ORDERS"` | transient staging table |
| `TGT_TABLE` | String | `"ORDERS"` | |
| `WATERMARK_OVERLAP_SEC` | Integer | `300` | overlap subtracted from the stored watermark |
| `WATERMARK_OVERRIDE` | String | `""` | leave empty; set to `"2025-10-01 00:00:00"` on a one-off `Run now` to replay from a date |
| `FETCH_SIZE` | Integer | `10000` | PostgreSQL cursor fetch size |
| `SMTP_HOST`, `SMTP_PORT` | String | `"smtp.corp"`, `"587"` | |
| `SMTP_USER` | String | | |
| `SMTP_PASS` | **Password** | | |
| `ALERT_FROM`, `ALERT_TO` | String | `"talend@corp"`, `"ops@corp"` | `ALERT_TO` may be a comma-separated list |

Rules: `Default` must hold DEV values (a forgotten `--context` must never hit PROD); no literal
host/credential anywhere in the job; every variable above surfaces automatically as a TMC task
parameter, Password-typed ones masked.

## 3. Snowflake objects (run once per environment, before the first execution)

```sql
CREATE SCHEMA IF NOT EXISTS ETL;

CREATE TABLE IF NOT EXISTS ETL.ETL_CONTROL (
  JOB_NAME        VARCHAR(100)     NOT NULL PRIMARY KEY,
  LAST_WATERMARK  TIMESTAMP_NTZ(3) NOT NULL,
  LAST_RUN_ID     VARCHAR(50),
  LAST_RUN_START  TIMESTAMP_NTZ(3),
  LAST_RUN_END    TIMESTAMP_NTZ(3),
  LAST_STATUS     VARCHAR(20),
  ROWS_READ       NUMBER,
  UPDATED_AT      TIMESTAMP_NTZ(3) DEFAULT CURRENT_TIMESTAMP()
);
-- seed row: the first run loads everything after this timestamp
INSERT INTO ETL.ETL_CONTROL (JOB_NAME, LAST_WATERMARK, LAST_STATUS)
VALUES ('LOAD_ORDERS_PG_TO_SF', '1970-01-01 00:00:00', 'INIT');

CREATE TRANSIENT TABLE IF NOT EXISTS SALES.STG_ORDERS (
  ORDER_ID NUMBER(38,0), CUSTOMER_ID NUMBER(38,0), STATUS VARCHAR(30),
  ORDER_TOTAL NUMBER(18,2), CURRENCY VARCHAR(3),
  CREATED_AT TIMESTAMP_NTZ(3), UPDATED_AT TIMESTAMP_NTZ(3),
  LOAD_TS TIMESTAMP_NTZ(3), RUN_ID VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS SALES.ORDERS (
  ORDER_ID NUMBER(38,0) NOT NULL PRIMARY KEY, CUSTOMER_ID NUMBER(38,0), STATUS VARCHAR(30),
  ORDER_TOTAL NUMBER(18,2), CURRENCY VARCHAR(3),
  CREATED_AT TIMESTAMP_NTZ(3), UPDATED_AT TIMESTAMP_NTZ(3),
  ETL_LOAD_TS TIMESTAMP_NTZ(3), ETL_RUN_ID VARCHAR(50)
);
```

Adjust the column list to your real `orders` table; keep `UPDATED_AT` in the target, the MERGE uses
it as a guard.

## 4. Component-by-component settings

### S0 - connections (tPrejob)

| Component | Setting | Value |
|---|---|---|
| `tDBConnection_pg` (`Database` = PostgreSQL) | Host / Port / Database / Schema | `context.PG_HOST` / `context.PG_PORT` / `context.PG_DB` / `context.PG_SCHEMA` |
| | Username / Password | `context.PG_USER` / `context.PG_PASS` |
| | Additional JDBC Parameters | `context.PG_JDBC_PARAMS` |
| | **Auto Commit** | **unchecked** (required for `Use cursor` streaming; we never write to PG) |
| `tSnowflakeConnection_sf` | Account / User Id | `context.SF_ACCOUNT` / `context.SF_USER` |
| | Authentication Type | `Basic` + Password `context.SF_PASS` (or `Key Pair`, section 6) |
| | Warehouse / Database / Schema / Role | `context.SF_WAREHOUSE` / `context.SF_DB` / `context.SF_SCHEMA` / `context.SF_ROLE` |
| | Advanced > **Auto Commit** | **unchecked** `(unverified label; present on the TCK connection in 7.3+/8)` |
| | Advanced > Additional JDBC Parameters | `"application=TALEND_ORDERS_INC"` (optional, shows in Snowflake query history) |
| | Advanced > Login Timeout | 2 (minutes) |

Link: `tPrejob_1 --OnComponentOk--> tDBConnection_pg --OnComponentOk--> tSnowflakeConnection_sf`.

### S1 - read the watermark

`tSnowflakeInput_ctl`: `Use an existing connection` = `tSnowflakeConnection_sf`; `Manual Query`
checked; Query (schema: one column `LAST_WATERMARK`, type `Date`, nullable):

```java
"SELECT LAST_WATERMARK FROM " + context.CTL_SCHEMA + "." + context.CTL_TABLE
+ " WHERE JOB_NAME = '" + jobName + "'"
```

`tJavaRow_wm` (input and output schema = the same one column; Code):

```java
java.util.Date wm = input_row.LAST_WATERMARK;
if (context.WATERMARK_OVERRIDE != null && !context.WATERMARK_OVERRIDE.trim().isEmpty()) {
    wm = TalendDate.parseDate("yyyy-MM-dd HH:mm:ss", context.WATERMARK_OVERRIDE.trim());
    System.out.println("WATERMARK_OVERRIDE in effect: " + context.WATERMARK_OVERRIDE);
}
globalMap.put("WM_RAW", wm);
globalMap.put("WM_LOW", TalendDate.addDate(wm, -context.WATERMARK_OVERLAP_SEC, "ss"));
output_row.LAST_WATERMARK = wm;
```

Link: `tSnowflakeInput_ctl --row_ctl (Main)--> tJavaRow_wm`; `tSnowflakeInput_ctl --OnSubjobOk--> tDBInput_pg_now`.

### S2 - capture the upper bound from the source clock

`tDBInput_pg_now` (`Database` = PostgreSQL, `Use an existing connection` = `tDBConnection_pg`),
Query `"SELECT now() AS run_start"`, schema: `run_start` Date.

`tJavaRow_runstart`:

```java
if (globalMap.get("WM_LOW") == null) {
    throw new RuntimeException("No ETL_CONTROL row for job " + jobName + " - seed it before the first run");
}
globalMap.put("RUN_START", input_row.run_start);
System.out.println("Window: " + TalendDate.formatDate("yyyy-MM-dd HH:mm:ss.SSS", (java.util.Date) globalMap.get("WM_LOW"))
    + " -> " + TalendDate.formatDate("yyyy-MM-dd HH:mm:ss.SSS", input_row.run_start));
output_row.run_start = input_row.run_start;
```

With `Auto Commit` off, `now()` is the start of the PostgreSQL transaction the connection opened,
which is at or before the extract's snapshot - a safe (slightly conservative) upper bound.

Link: `tDBInput_pg_now --row_now--> tJavaRow_runstart`; `tDBInput_pg_now --OnSubjobOk--> tSnowflakeRow_truncate_stg`.

### S3 - empty the staging table (outside the transaction)

`tSnowflakeRow_truncate_stg`: `Use an existing connection`; Query
`"TRUNCATE TABLE IF EXISTS " + context.SF_SCHEMA + "." + context.STG_TABLE`; `Die on error` checked.

Snowflake DDL auto-commits (and would commit anything pending), which is why the truncate is its own
step before any DML. Link: `--OnSubjobOk--> tDBInput_pg_orders`.

### S4 - extract changed rows and stage them

`tDBInput_pg_orders` (PostgreSQL, `Use an existing connection` = `tDBConnection_pg`):

- Schema: `order_id` Long (Key, not nullable), `customer_id` Long, `status` String, `order_total`
  BigDecimal(18,2), `currency` String, `created_at` Date, `updated_at` Date (all others nullable).
  Column order must match the SELECT list.
- Query:

```java
"SELECT order_id, customer_id, status, order_total, currency, created_at, updated_at"
+ " FROM " + context.PG_SCHEMA + "." + context.SRC_TABLE
+ " WHERE updated_at >  '" + TalendDate.formatDate("yyyy-MM-dd HH:mm:ss.SSS", (java.util.Date) globalMap.get("WM_LOW"))   + "'"
+ "   AND updated_at <= '" + TalendDate.formatDate("yyyy-MM-dd HH:mm:ss.SSS", (java.util.Date) globalMap.get("RUN_START")) + "'"
```

- Advanced settings: `Use cursor` checked, `Fetch size` = `context.FETCH_SIZE` (streams the first-run
  backfill instead of loading the whole result set into heap).

`tMap_orders`: one input `row_orders`, one output `out_stg` (schema = STG_ORDERS, uppercase names).
Expressions: `ORDER_ID = row_orders.order_id` ... `UPDATED_AT = row_orders.updated_at`,
`LOAD_TS = (java.util.Date) globalMap.get("RUN_START")`, `RUN_ID = pid`. No lookup, no filter.
(If you do not need the two audit columns you can wire `tDBInput_pg_orders` straight into
`tSnowflakeOutput_stg`.)

`tSnowflakeOutput_stg`: `Use an existing connection` = `tSnowflakeConnection_sf`; `Table` =
`context.STG_TABLE`; `Table Action` = `None`; `Output Action` = `Insert`; Advanced: `Convert empty
strings to null` checked (Snowflake keeps `''` as a non-null empty string otherwise), `Allow
Snowflake to convert columns and tables to uppercase` checked (so your `STG_ORDERS`/`ORDER_ID`
unquoted identifiers match); `Die on error` checked. The TCK output stages a file and runs
`COPY INTO` internally, so it scales to the full-history first run.

Links: `tDBInput_pg_orders --row_orders--> tMap_orders --out_stg--> tSnowflakeOutput_stg`;
`tDBInput_pg_orders --OnSubjobOk--> tSnowflakeRow_merge`.

### S5 - upsert, move the watermark, commit (one transaction)

`tSnowflakeRow_merge` (`Use an existing connection`, `Die on error` checked), Query:

```java
"MERGE INTO " + context.SF_SCHEMA + "." + context.TGT_TABLE + " t"
+ " USING (SELECT * FROM " + context.SF_SCHEMA + "." + context.STG_TABLE
+ "        QUALIFY ROW_NUMBER() OVER (PARTITION BY ORDER_ID ORDER BY UPDATED_AT DESC) = 1) s"
+ " ON t.ORDER_ID = s.ORDER_ID"
+ " WHEN MATCHED AND (t.UPDATED_AT IS NULL OR s.UPDATED_AT >= t.UPDATED_AT) THEN UPDATE SET"
+ "   t.CUSTOMER_ID = s.CUSTOMER_ID, t.STATUS = s.STATUS, t.ORDER_TOTAL = s.ORDER_TOTAL,"
+ "   t.CURRENCY = s.CURRENCY, t.CREATED_AT = s.CREATED_AT, t.UPDATED_AT = s.UPDATED_AT,"
+ "   t.ETL_LOAD_TS = s.LOAD_TS, t.ETL_RUN_ID = s.RUN_ID"
+ " WHEN NOT MATCHED THEN INSERT (ORDER_ID, CUSTOMER_ID, STATUS, ORDER_TOTAL, CURRENCY, CREATED_AT, UPDATED_AT, ETL_LOAD_TS, ETL_RUN_ID)"
+ "   VALUES (s.ORDER_ID, s.CUSTOMER_ID, s.STATUS, s.ORDER_TOTAL, s.CURRENCY, s.CREATED_AT, s.UPDATED_AT, s.LOAD_TS, s.RUN_ID)"
```

The `QUALIFY` guards against duplicate keys in staging (Snowflake MERGE errors on them) and the
`s.UPDATED_AT >= t.UPDATED_AT` guard makes a `WATERMARK_OVERRIDE` replay safe: older rows never
overwrite newer ones.

`tSnowflakeRow_ctl_update` (`Use an existing connection`, `Die on error` checked), Query:

```java
"UPDATE " + context.CTL_SCHEMA + "." + context.CTL_TABLE + " SET"
+ " LAST_WATERMARK = '" + TalendDate.formatDate("yyyy-MM-dd HH:mm:ss.SSS", (java.util.Date) globalMap.get("RUN_START")) + "'::TIMESTAMP_NTZ,"
+ " LAST_RUN_ID = '" + pid + "',"
+ " LAST_RUN_START = '" + TalendDate.formatDate("yyyy-MM-dd HH:mm:ss.SSS", (java.util.Date) globalMap.get("RUN_START")) + "'::TIMESTAMP_NTZ,"
+ " LAST_RUN_END = CURRENT_TIMESTAMP(), LAST_STATUS = 'SUCCESS', UPDATED_AT = CURRENT_TIMESTAMP(),"
+ " ROWS_READ = " + ((Integer) globalMap.get("tDBInput_pg_orders_NB_LINE"))
+ " WHERE JOB_NAME = '" + jobName + "'"
```

(Check the type of `tDBInput_pg_orders_NB_LINE` in the Outline view before casting - Integer on
most tDBInput flavours.)

`tSnowflakeCommit_sf`: `Component List` = `tSnowflakeConnection_sf`, `Close Connection`
**unchecked** (tPostjob closes it).

Links: `tSnowflakeRow_merge --OnComponentOk--> tSnowflakeRow_ctl_update --OnComponentOk--> tSnowflakeCommit_sf`.

### ERR - alert and fail

Draw an `OnSubjobError` link from each chain start component (`tSnowflakeInput_ctl`,
`tDBInput_pg_now`, `tSnowflakeRow_truncate_stg`, `tDBInput_pg_orders`, `tSnowflakeRow_merge`) to the
**same** `tSendMail_fail` (several triggers may target one component).

`tSendMail_fail`:

| Setting | Value |
|---|---|
| To / From | `context.ALERT_TO` / `context.ALERT_FROM` |
| Subject | `"[" + context.ENV + "] Talend job " + jobName + " FAILED (" + pid + ")"` |
| Message | see below |
| SMTP host / Port | `context.SMTP_HOST` / `context.SMTP_PORT` |
| `STARTTLS support` (587) or `SSL support` (465) | per your relay `(label varies by release)` |
| Need authentication | checked, `context.SMTP_USER` / `context.SMTP_PASS` |
| **Die on error** | **unchecked** - an SMTP outage must not mask the real failure |

Message expression:

```java
"Job " + jobName + " context " + contextStr + " failed.\n"
+ "Run id (pid): " + pid + "\n"
+ "Window: " + globalMap.get("WM_LOW") + " -> " + globalMap.get("RUN_START") + "\n"
+ "Rows read from PostgreSQL: " + globalMap.get("tDBInput_pg_orders_NB_LINE") + "\n"
+ "Errors:\n" + globalMap.get("ERR_LOG") + "\n"
+ "Watermark was NOT advanced; the next scheduled run retries the same window. Logs: TMC task run page."
```

`tSendMail_fail --OnComponentOk--> tDie_1` (`Error message` `"LOAD_ORDERS_PG_TO_SF failed"`,
`Error code` 4, `Exit the JVM immediately` unchecked so tPostjob still closes connections). TMC sees
exit code 4 and marks the run failed.

`tLogCatcher_1` (`Catch Java Exception` + `Catch tDie` checked, `Catch tWarn` unchecked)
`--row_err--> tJavaRow_err` with:

```java
String prev = (String) globalMap.get("ERR_LOG");
globalMap.put("ERR_LOG", (prev == null ? "" : prev + "\n")
    + input_row.origin + " [" + input_row.type + "] " + input_row.message);
```

The catcher subjob runs synchronously when the exception is raised, before the `OnSubjobError`
chain, so the mail body has the real `Exception in component ...` text. Do **not** put tSendMail or
tDie in the catcher subjob itself (one mail per event, and a tDie there re-enters the catcher).

### S7 - cleanup (tPostjob)

`tPostjob_1 --OnComponentOk--> tDBClose_pg (Component List tDBConnection_pg) --OnComponentOk--> tSnowflakeClose_sf`.
tPostjob runs after success and after a normal `tDie`; closing the Snowflake connection with an
uncommitted transaction discards it (that is the rollback for the failure path).

### Job-level settings

- Job view > `Extra`: nothing special (no `Multi thread execution`).
- Job view > `Stats & Logs`: optional `Use statistics` / `Use logs` `On Databases` into Snowflake if
  you want a TALEND_LOGS history; the ETL_CONTROL row already gives you last status.
- Run view > Advanced settings > `Use specific JVM arguments`: `-Xmx2048M -Duser.timezone=UTC
  -Dfile.encoding=UTF-8`. Use UTC on **every** runtime (Studio and the Remote Engine run profile):
  the window literals are formatted by the JVM, pgjdbc sets the PostgreSQL session time zone from
  the JVM, and the Snowflake columns are `TIMESTAMP_NTZ`, so UTC everywhere makes the comparison
  exact whether `updated_at` is `timestamp` or `timestamptz`, and immune to DST.
- Job `Purpose`/`Description`: write the window logic and the reset procedure (section 7) there.

Simpler alternative for S4/S5: drop the staging table and set `tSnowflakeOutput` to `Output Action`
= `Upsert`, `Upsert Key Column` = `ORDER_ID`, writing straight into `ORDERS` (Talend generates a
temp table + MERGE internally). You lose the `UPDATED_AT >= ` guard and the QUALIFY dedup, and the
watermark update then runs in a separate `tSnowflakeRow` after the output's `OnSubjobOk`; still
restart-safe, two components fewer.

## 5. How the watermark survives between runs

- **Where it lives**: the `ETL.ETL_CONTROL` row in Snowflake, not on the engine. A Remote Engine's
  working directory (`TalendJobServersFiles/...`) is per deployed artifact version, is not shared
  across a Remote Engine Cluster and is not something TMC backs up; `globalMap` dies with the JVM;
  TMC task parameters are static configuration, a job cannot rewrite them. A database row is the
  only state that is durable, visible to ops, shared by every engine in a cluster, and committable
  together with the data it describes.
- **Read**: S1 selects it at the start of each run and subtracts the overlap.
- **Write**: S5 updates it to `RUN_START` only after the MERGE succeeded, in the same transaction,
  committed by the final `tSnowflakeCommit`. Failure before that point = row unchanged = the next
  run re-extracts the same window. Because the load is an upsert, re-processing is harmless.
- **Overlap in both directions**: late-committing source transactions are caught by the
  `WATERMARK_OVERLAP_SEC` look-back; nothing is lost at the upper bound because the bound is the
  source clock captured before the extract.
- **Why not PostgreSQL for the control table**: the watermark and the MERGE would then live in two
  databases and could not be committed atomically.
- **Why not a file on the engine**: see the first bullet; it also breaks the moment you move the task
  to another engine or a cluster.

## 6. Deploy and schedule on a Remote Engine via TMC

1. **Prepare**: run the section 3 DDL in each Snowflake environment. In Studio, run the job once
   against DEV (`Run` view, context `DEV`), then run the plugin's review helper on the exported
   `.item` if you want a second pair of eyes (`python3 scripts/inspect_job_item.py LOAD_ORDERS_PG_TO_SF_0.1.item --review`).
2. **Publish**: Studio must be logged in to your Talend Cloud connection (region URL + personal
   access token or credentials). Right-click the job > `Publish to Cloud` > choose environment
   (`DEV`) and a shared workspace, `Artifact type` Standard Job, bump the version. The artifact
   appears under TMC > `Management > Artifacts`; every context variable becomes a task parameter.
3. **Remote Engine**: TMC > `Management > Engines > Add > Remote Engine` > copy the
   `Pre-authorized key`. On a host that can reach PostgreSQL, Snowflake (443) and your SMTP relay
   and that has outbound 443 to `*.cloud.talend.com`: unzip `Talend-RemoteEngine-V2.1x`, Java 17,
   put the key and a name in `etc/preauthorized.key.cfg`, `bin/start` (or install as a service).
   The engine shows `Paired`/`Available`. Create a **Run profile** (`Management > Run profiles`)
   with `-Xmx2048M -Duser.timezone=UTC -Dfile.encoding=UTF-8` and assign it to the task. For HA
   put two engines in a `Remote Engine Cluster`; the design needs no local files, so it is
   cluster-safe.
4. **Task**: `Management > Tasks and plans > Add task`, pick the artifact version.
   - `Parameters`: fill DEV values; `PG_PASS`, `SF_PASS`, `SMTP_PASS` are masked (Password type);
     leave `WATERMARK_OVERRIDE` empty. Optionally bind the Snowflake and PostgreSQL parameters to a
     TMC `Connection` object per environment instead of typing them.
   - `Processing`: `Engine` = your Remote Engine or cluster, the run profile, `Log level` INFO,
     `Timeout` 60 min (a first-run backfill can take longer: raise it for that run),
     **`Allow parallel run of this task` = off**. With it off a run that is still going when the
     next trigger fires is not started twice (new run rejected/queued), which is what you want for
     a watermarked load.
   - `Schedule > Add trigger`: either `Daily`, repeat every 15 minutes from 00:00 to 23:59, or
     `CRON` with an every-15-minutes expression; set the time zone explicitly (UTC). TMC's minimum
     spacing is 5 minutes. The exact cron syntax (5-field `*/15 * * * *` vs Quartz
     `0 0/15 * * * ?`) differs between the UI and the API in the docs - copy the format the UI
     tooltip shows for your tenant.
   - `Notifications`: subscribe ops to `Execution failed`/`Timeout` for this task in TMC as a
     second channel; it costs nothing and still fires if the engine itself is down (tSendMail
     cannot cover that case).
5. **Promote to PROD**: `Management > Environments > Promotions`, DEV -> PROD, scope = this
   artifact + task. Then open the PROD task: set PROD parameter values, assign the PROD engine and
   run profile (engines are never promoted), re-create the trigger if it did not carry over.
   Pin the artifact version in PROD; let DEV auto-upgrade.
6. **API/CI option** (same thing scripted; token in `TALEND_CLOUD_TOKEN`): the plugin's
   `scripts/tmc_api.py --region <us|eu|ap|...> tasks list --environment-id <id>` finds the task,
   `tasks run <taskId> --param WATERMARK_OVERRIDE="2025-10-01 00:00:00" --wait` runs a replay, and
   `PUT /orchestration/executables/tasks/{taskId}/run-config` with
   `{"trigger":{"type":"CRON","cronExpression":"...","timeZone":"UTC"},"runtime":{"type":"REMOTE_ENGINE","id":"<engineId>"},"parallelExecutionAllowed":false,"logLevel":"INFO"}`
   sets engine + schedule in one call (`tasks run-config <taskId>` reads it back). Executions end in
   `EXECUTION_SUCCESSFUL` / `EXECUTION_FAILED`.

Snowflake authentication: `Basic` with the password as a masked TMC parameter is the quickest.
Better: `Authentication Type` = `Key Pair` with a PKCS8 private key (`openssl pkcs8 -topk8 -nocrypt`,
`ALTER USER ... SET RSA_PUBLIC_KEY`); ship the key file as a TMC `Resource` bound to a context
parameter if the component wants a path, or paste the PEM into a Password-typed parameter if your
release accepts key content `(unverified which forms your R-release accepts - check the component)`.

## 7. Operations

- **Replay from a date**: TMC > task > `Run now` with `WATERMARK_OVERRIDE = "2025-10-01 00:00:00"`
  (or the API call above). The run re-extracts from that date to now; the MERGE guard keeps newer
  target rows; on success the watermark is set to that run's `RUN_START`. Clear the parameter
  afterwards (a scheduled run with it set would replay every 15 minutes).
- **Full reload**: `UPDATE ETL.ETL_CONTROL SET LAST_WATERMARK = '1970-01-01' WHERE JOB_NAME = 'LOAD_ORDERS_PG_TO_SF'`
  and let the next run happen (raise the task timeout first).
- **Monitoring**: `SELECT * FROM ETL.ETL_CONTROL` tells you the last good window; TMC task history
  shows duration and logs per run; `LAST_RUN_END - LAST_RUN_START` trending towards 15 minutes means
  you need a bigger warehouse or a `Remote Engine Cluster`.
- **Cost**: a 15-minute cadence resumes the Snowflake warehouse 96 times a day; set
  `AUTO_SUSPEND = 60` on `WH_ETL` and keep it X-Small unless the backfill needs more.
- **Hard deletes** in PostgreSQL are not detected by a timestamp watermark (a soft-delete flag or a
  periodic key-compare job covers that).

## 8. Checks before PROD (from the plugin's design-review scorecard)

- Nullability: every nullable PG column marked `Nullable` in the input schema; `order_id` marked
  `Key`; BigDecimal precision set for `order_total`.
- Error handling: `OnSubjobError` from every chain start; `tSendMail` `Die on error` off; job ends in
  `tDie` (exit 4) - verify once by pointing `SF_PASS` at a wrong value in DEV and checking the mail
  and the `Execution failed` status in TMC.
- Transactions: `Auto Commit` off on both connections; a single `tSnowflakeCommit` after the
  watermark update; `Close Connection` unchecked on the commit, closes in tPostjob.
- Idempotency: run the job twice in a row against DEV; the second run must read 0-N overlap rows
  and change nothing in `ORDERS` (row counts identical).
- Time zones: `-Duser.timezone=UTC` in Studio JVM args and in the engine run profile; trigger time
  zone UTC.
- No `tLogRow` left on the flow; `Fetch size` set; `Allow parallel run` off; artifact version pinned
  in PROD.

Doc pages to confirm labels for your exact R-release: help.qlik.com/talend `components/8.0/snowflake/`
(tSnowflakeConnection/Input/Output/Row), `components/8.0/postgresql/tpostgresqlinput`,
`management-console-user-guide/Cloud` (tasks, triggers, run profiles, promotions, notifications).
