# Incremental PostgreSQL -> Snowflake orders load (Talend Studio 8.0 / Talend Cloud)

Standard Job `ORDERS_INCREMENTAL_LOAD`, run every 15 minutes on a Remote Engine from Talend Management Console (TMC). It extracts only rows whose `updated_at` moved since the last successful run, upserts them into Snowflake on `order_id`, persists a watermark in a Snowflake control table so any run can be killed and restarted safely, and emails ops on failure.

---

## 1. Design decisions (read these first, they drive the component choices)

| Decision | Choice | Why |
|---|---|---|
| Where the watermark lives | A control table in Snowflake (`ETL_CTRL.JOB_WATERMARK`), not a context variable or a file on the engine | A job cannot write back to TMC context parameters; a file on the Remote Engine is lost when the host is rebuilt and is not shared across an engine cluster. A DB row survives redeploys, artifact version changes, engine re-pairing and host moves. |
| High watermark | `wm_to = source now() - lag` (captured from PostgreSQL at the start of the run), not `max(updated_at)` of the extracted rows | Window is closed and deterministic: `updated_at > wm_from AND updated_at <= wm_to`. The lag (default 120 s) covers rows whose transaction started (and set `updated_at = now()`) before extraction but committed after it, which `max(updated_at)` can never catch. |
| When the watermark is advanced | Only after the Snowflake upsert subjob finished OK (`OnSubjobOk`) | If the job dies between load and watermark update, the next run simply re-extracts the same window. |
| Why re-extraction is safe | Load is an UPSERT keyed on `order_id` | Replaying a window is idempotent, so "restartable" needs no manual cleanup. |
| Watermark data type in the job | Strings, not Talend `Date` | Talend `Date` is `java.util.Date` (millisecond precision); PostgreSQL `timestamptz` has microseconds. Passing watermarks as text avoids rounding at the window boundary. |
| Clock / time zone | `timestamptz` in PostgreSQL, `TIMESTAMP_TZ` in Snowflake, JVM forced to UTC | Removes DST and engine-local-time surprises. |
| Overlap protection | TMC task "Allow parallel run" = off | Two overlapping runs would both read the same watermark; with it off, the second trigger is skipped/queued and the next run picks up the backlog anyway. |

---

## 2. Database objects

### Snowflake

```sql
CREATE SCHEMA IF NOT EXISTS DWH.ETL_CTRL;

CREATE TABLE IF NOT EXISTS DWH.ETL_CTRL.JOB_WATERMARK (
  JOB_NAME      STRING        NOT NULL PRIMARY KEY,
  WATERMARK_TS  STRING        NOT NULL,          -- ISO-8601 text with microseconds and offset
  LAST_RUN_TS   TIMESTAMP_TZ,
  LAST_STATUS   STRING,
  ROWS_LOADED   NUMBER
);

-- seed once; the job never deletes this row
INSERT INTO DWH.ETL_CTRL.JOB_WATERMARK (JOB_NAME, WATERMARK_TS, LAST_STATUS)
SELECT 'ORDERS_INCREMENTAL_LOAD', '1900-01-01 00:00:00.000000+00', 'SEEDED';

CREATE TABLE IF NOT EXISTS DWH.SALES.ORDERS (
  ORDER_ID        NUMBER(19,0)  NOT NULL PRIMARY KEY,
  CUSTOMER_ID     NUMBER(19,0),
  STATUS          STRING,
  AMOUNT          NUMBER(18,2),
  CURRENCY        STRING,
  CREATED_AT      TIMESTAMP_TZ,
  SRC_UPDATED_AT  TIMESTAMP_TZ,
  DW_LOADED_AT    TIMESTAMP_TZ  DEFAULT CURRENT_TIMESTAMP()
);
```

Grant the Talend Snowflake role `USAGE` on the warehouse/database/schemas and `SELECT, INSERT, UPDATE` on both tables. If you use the staging-table variant (section 4, option B) also grant `CREATE TABLE` on `ETL_CTRL` or pre-create the stage table.

### PostgreSQL

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS orders_updated_at_idx ON public.orders (updated_at);
```

Without this index every 15-minute run is a full scan. Also confirm that every code path that modifies an order maintains `updated_at` (ideally a `BEFORE UPDATE` trigger setting `updated_at = now()`); hard deletes are not detected by this design (use soft deletes or a separate delete feed).

---

## 3. Context variables

Create a repository context group `CTX_ORDERS_INC` with contexts `Default`, `DEV`, `PROD` and attach it to the job. Everything marked *Password* uses the Password type so it is masked in Studio, in the built artifact and in TMC.

| Variable | Type | Example / default | Notes |
|---|---|---|---|
| `pg_host` | String | `pg-prod.internal` | |
| `pg_port` | String | `5432` | |
| `pg_db` | String | `shop` | |
| `pg_schema` | String | `public` | |
| `pg_user` | String | `talend_ro` | read-only role |
| `pg_password` | Password | | |
| `sf_account` | String | `myorg-myaccount` | account identifier, no `.snowflakecomputing.com` |
| `sf_user` | String | `TALEND_ETL` | |
| `sf_password` | Password | | or switch tSnowflakeConnection to Key Pair auth and point `sf_private_key_path` at a file on the engine |
| `sf_role` | String | `TALEND_ETL_ROLE` | |
| `sf_warehouse` | String | `ETL_XS` | |
| `sf_db` | String | `DWH` | |
| `sf_schema` | String | `SALES` | target schema |
| `sf_ctrl_schema` | String | `ETL_CTRL` | |
| `sf_target_table` | String | `ORDERS` | |
| `wm_job_name` | String | `ORDERS_INCREMENTAL_LOAD` | key in `JOB_WATERMARK` |
| `wm_lag_seconds` | Integer | `120` | safety lag, >= longest expected writer transaction |
| `wm_override_from` | String | `""` (empty) | set in TMC for a one-off backfill (`2026-10-01 00:00:00+00`); empty = use the control table |
| `fetch_size` | Integer | `10000` | PostgreSQL cursor size |
| `smtp_host` | String | `smtp.company.com` | |
| `smtp_port` | String | `587` | |
| `smtp_user` | String | `etl-alerts@company.com` | |
| `smtp_password` | Password | | |
| `mail_from` | String | `etl-alerts@company.com` | |
| `mail_to` | String | `ops@company.com` | comma-separated list allowed |
| `env_name` | String | `PROD` | shown in the alert subject |

Runtime values that are computed inside the job (`wm_from`, `wm_to`, row counts) go in `globalMap`, not in context, so they can never be accidentally overridden from TMC.

---

## 4. Job layout: components, links and key settings

The job has seven subjobs. Links are named exactly as Studio shows them.

```
[tPrejob] --OnComponentOk--> [tDBConnection_PG] --OnComponentOk--> [tDBConnection_SF]
      |
      OnSubjobOk (from tPrejob subjob is implicit: the next subjob below is chained from tDBConnection_SF)
      v
Subjob 1  [tDBInput_SF_ReadWatermark] --Main--> [tJavaRow_SetWmFrom]
      | OnSubjobOk
      v
Subjob 2  [tDBInput_PG_HighWatermark] --Main--> [tJavaRow_SetWmTo]
      | OnSubjobOk
      v
Subjob 3  [tDBInput_PG_Orders] --Main--> [tMap_Orders] --out1--> [tDBOutput_SF_Orders]
      | OnSubjobOk
      v
Subjob 4  [tDBRow_SF_SaveWatermark]
      | OnSubjobOk
      v
Subjob 5  [tDBCommit_SF]   (only if the Snowflake connection is not auto-commit; see note)

Subjob 6  [tLogCatcher] --Main--> [tJavaRow_BuildAlert] --Main--> [tSendMail_Ops]
          (not linked to anything; it fires on any tDie / Java exception / tWarn)

Subjob 7  [tPostjob] --OnComponentOk--> [tDBClose_SF] --OnComponentOk--> [tDBClose_PG]
```

In Talend 8 the database components are the generic `tDBConnection`, `tDBInput`, `tDBOutput`, `tDBRow`, `tDBClose`, `tDBCommit` with the **Database** drop-down set to *PostgreSQL* or *Snowflake*. (They are the same as the legacy `tPostgresqlConnection` / `tSnowflakeConnection` etc. after you pick the database type.)

### Subjob 0 - connections

**tPrejob** -> **tDBConnection_PG** (Database = PostgreSQL)
- Host `context.pg_host`, Port `context.pg_port`, Database `context.pg_db`, Schema `context.pg_schema`, Username `context.pg_user`, Password `context.pg_password`.
- Advanced: Additional JDBC parameters `"ApplicationName=talend_orders_inc&connectTimeout=30"`.
- Auto Commit: checked (we only read from PostgreSQL).

**tDBConnection_SF** (Database = Snowflake)
- Account `context.sf_account`, User `context.sf_user`, Password `context.sf_password` (or *Key Pair* authentication), Warehouse `context.sf_warehouse`, Database `context.sf_db`, Schema `context.sf_schema`, Role `context.sf_role`.
- Advanced: Login Timeout 60 s; Additional JDBC Parameters `"CLIENT_SESSION_KEEP_ALIVE=true"`.
- Auto Commit: see "Transaction note" below.

### Subjob 1 - read the low watermark

**tDBInput_SF_ReadWatermark** (Snowflake, *Use an existing connection* = tDBConnection_SF)
- Schema: one column `WATERMARK_TS` String.
- Query:
  ```java
  "SELECT WATERMARK_TS FROM " + context.sf_db + "." + context.sf_ctrl_schema + ".JOB_WATERMARK WHERE JOB_NAME = '" + context.wm_job_name + "'"
  ```
- Die on error: checked.

**tJavaRow_SetWmFrom**
```java
String wm = (context.wm_override_from != null && !context.wm_override_from.trim().isEmpty())
            ? context.wm_override_from.trim()
            : input_row.WATERMARK_TS;
globalMap.put("wm_from", wm);
System.out.println("wm_from = " + wm);
```
If the row is missing (someone deleted the seed) the job must fail loudly rather than reload history by accident: add a **Run if** link from the subjob to a **tDie** with condition `((Integer)globalMap.get("tDBInput_SF_ReadWatermark_NB_LINE")) == 0` and message `"No watermark row for " + context.wm_job_name`.

### Subjob 2 - compute the high watermark on the source clock

**tDBInput_PG_HighWatermark** (PostgreSQL, existing connection)
- Schema: `WM_TO` String.
- Query (microsecond precision, explicit offset, computed by the *source* server so there is no clock skew with the engine):
  ```java
  "SELECT to_char((now() - make_interval(secs => " + context.wm_lag_seconds + ")) AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS.US') || '+00' AS wm_to"
  ```

**tJavaRow_SetWmTo**
```java
globalMap.put("wm_to", input_row.WM_TO);
System.out.println("wm_to = " + input_row.WM_TO);
```

### Subjob 3 - extract and upsert

**tDBInput_PG_Orders** (PostgreSQL, existing connection)
- Schema (Talend types): `order_id` Long (key), `customer_id` Long, `status` String, `amount` BigDecimal, `currency` String, `created_at` Date (`yyyy-MM-dd HH:mm:ss.SSS`), `updated_at` Date (`yyyy-MM-dd HH:mm:ss.SSS`).
- Query:
  ```java
  "SELECT order_id, customer_id, status, amount, currency, created_at, updated_at " +
  "FROM " + context.pg_schema + ".orders " +
  "WHERE updated_at >  '" + globalMap.get("wm_from") + "'::timestamptz " +
  "  AND updated_at <= '" + globalMap.get("wm_to")   + "'::timestamptz " +
  "ORDER BY updated_at, order_id"
  ```
- Advanced: **Use cursor** checked, Cursor size `context.fetch_size`; Trim all String columns checked. Die on error checked.

**tMap_Orders** (one output `out1`, target column names in upper case):
`ORDER_ID <- order_id`, `CUSTOMER_ID <- customer_id`, `STATUS <- status`, `AMOUNT <- amount`, `CURRENCY <- currency`, `CREATED_AT <- created_at`, `SRC_UPDATED_AT <- updated_at`, `DW_LOADED_AT <- TalendDate.getCurrentDate()`.
Mark `ORDER_ID` as **Key** in the output schema (the upsert key is taken from the schema).

**tDBOutput_SF_Orders** (Snowflake, existing connection) - **option A, simplest**
- Table `context.sf_target_table`, Table Action *NONE*, Output Action **UPSERT**, Upsert Key Column `ORDER_ID`.
- Advanced: Convert columns and table to uppercase = checked; Die on error = checked.
- The Snowflake output component bulk-loads the batch through an internal stage into a temporary table and runs a `MERGE`, so one run costs one COPY + one MERGE regardless of row count. `tDBOutput_SF_Orders_NB_LINE` is available afterwards for the audit row.

**Option B - staging table + explicit MERGE (use when you want full control, e.g. dedup, type casting, or >1M rows per run)**
Replace tDBOutput_SF_Orders by **tDBOutputBulkExec** (Snowflake, Table Action *CREATE_IF_NOT_EXISTS* on `ETL_CTRL.ORDERS_STG`, Table Action per run: *TRUNCATE* first via a tDBRow) followed `OnSubjobOk` by **tDBRow_SF_Merge**:
```sql
MERGE INTO DWH.SALES.ORDERS t
USING (
  SELECT * FROM DWH.ETL_CTRL.ORDERS_STG
  QUALIFY ROW_NUMBER() OVER (PARTITION BY ORDER_ID ORDER BY SRC_UPDATED_AT DESC) = 1
) s
ON t.ORDER_ID = s.ORDER_ID
WHEN MATCHED AND s.SRC_UPDATED_AT >= t.SRC_UPDATED_AT THEN UPDATE SET
  CUSTOMER_ID = s.CUSTOMER_ID, STATUS = s.STATUS, AMOUNT = s.AMOUNT, CURRENCY = s.CURRENCY,
  CREATED_AT = s.CREATED_AT, SRC_UPDATED_AT = s.SRC_UPDATED_AT, DW_LOADED_AT = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (ORDER_ID, CUSTOMER_ID, STATUS, AMOUNT, CURRENCY, CREATED_AT, SRC_UPDATED_AT, DW_LOADED_AT)
  VALUES (s.ORDER_ID, s.CUSTOMER_ID, s.STATUS, s.AMOUNT, s.CURRENCY, s.CREATED_AT, s.SRC_UPDATED_AT, CURRENT_TIMESTAMP());
```
The `QUALIFY` guards against Snowflake's "nondeterministic MERGE" error if the stage ever holds the same `order_id` twice (e.g. after a manual backfill overlap), and the `>=` guard makes an out-of-order replay harmless.

### Subjob 4 - persist the watermark (only reached on success)

**tDBRow_SF_SaveWatermark** (Snowflake, existing connection), linked from subjob 3 with **OnSubjobOk**:
```java
"UPDATE " + context.sf_db + "." + context.sf_ctrl_schema + ".JOB_WATERMARK " +
"SET WATERMARK_TS = '" + globalMap.get("wm_to") + "', " +
"    LAST_RUN_TS  = CURRENT_TIMESTAMP(), " +
"    LAST_STATUS  = 'OK', " +
"    ROWS_LOADED  = " + ((Integer)globalMap.get("tDBOutput_SF_Orders_NB_LINE")) + " " +
"WHERE JOB_NAME = '" + context.wm_job_name + "'"
```
A run with zero changed rows still advances the watermark; otherwise a quiet period would make the window grow forever.

**Transaction note.** Two valid choices:
1. *Auto-commit on* (default, simpler). Correctness still holds because the load is idempotent: a crash between subjob 3 and 4 only causes a replay of the same window.
2. *Auto-commit off* on tDBConnection_SF and a **tDBCommit_SF** (Snowflake, Close connection = unchecked) as subjob 5. Then the upsert and the watermark update commit atomically and a failure rolls both back. Snowflake supports this (the MERGE and the UPDATE are DML in one transaction). Pick 2 if auditors want "watermark and data always consistent"; pick 1 if you want fewer moving parts.

### Subjob 6 - failure alert

**tLogCatcher**: Catch Java exceptions, Catch tDie, Catch tWarn all checked. It is a standalone subjob (no incoming link); Talend starts it automatically and feeds it a row for every error in the job.

**tJavaRow_BuildAlert** (schema in = tLogCatcher schema, out adds `SUBJECT` and `BODY` Strings):
```java
output_row.SUBJECT = "[" + context.env_name + "] FAILED: " + jobName + " (pid " + pid + ")";
output_row.BODY =
    "Job        : " + jobName + " v" + jobVersion + "\n" +
    "Context    : " + contextStr + "\n" +
    "Engine host: " + java.net.InetAddress.getLocalHost().getHostName() + "\n" +
    "Time       : " + TalendDate.getDate("yyyy-MM-dd HH:mm:ss") + " (" + java.util.TimeZone.getDefault().getID() + ")\n" +
    "Component  : " + input_row.origin + "\n" +
    "Window     : " + globalMap.get("wm_from") + "  ->  " + globalMap.get("wm_to") + "\n" +
    "Error code : " + input_row.code + "\n" +
    "Message    : " + input_row.message + "\n\n" +
    "Watermark was NOT advanced; the next scheduled run will retry the same window.";
```

**tSendMail_Ops**
- To `context.mail_to`, From `context.mail_from`, Subject `row2.SUBJECT`, Message `row2.BODY`.
- SMTP host `context.smtp_host`, Port `context.smtp_port`, **SSL/STARTTLS** as your relay requires (STARTTLS for 587), Need authentication checked, Username `context.smtp_user`, Password `context.smtp_password`.
- Advanced: Die on error **unchecked** on tSendMail itself (a broken mail relay must not mask the original error), and do not put a `tDie` downstream of tLogCatcher (it would be caught again by the same tLogCatcher and loop).

With *Die on error* checked on every DB component, the job still exits with a non-zero code after the mail is sent, so TMC marks the task run **Failed**, which you can also wire to TMC's own notifications (section 6) as a second channel.

### Subjob 7 - cleanup

**tPostjob** -> **tDBClose_SF** -> **tDBClose_PG**. tPostjob runs whether the main flow succeeded or failed, so connections are always released on the engine.

### Studio job-level settings
- Job view > Extra: *Use project settings* for stats/logs is fine; nothing special needed.
- Job view > Stats & Logs: optionally enable **tStatCatcher** statistics into a Snowflake table (`ETL_CTRL.JOB_STATS`) for run history outside TMC.
- Component "Die on error" checked on every tDBInput / tDBOutput / tDBRow; unchecked only on tSendMail.

---

## 5. Restartability and the watermark life cycle

1. Run starts, reads `WATERMARK_TS` (`wm_from`) from Snowflake, computes `wm_to = now_pg - lag`.
2. Extracts `(wm_from, wm_to]`, upserts on `ORDER_ID`.
3. Only after the upsert subjob returns OK does it write `wm_to` into `JOB_WATERMARK`.

Failure matrix:

| Failure point | Effect on next run |
|---|---|
| Cannot connect / read watermark | Nothing changed; next run retries identical window. |
| Extraction or upsert fails midway | Some orders may already be upserted (auto-commit variant). Watermark unchanged, so the whole window is replayed; the upsert overwrites them with identical values. |
| Upsert OK, watermark update fails | Window replayed next run, same outcome. |
| Engine down for hours | Next successful run has a bigger window; no data is skipped because `wm_from` is still the last *committed* watermark. |
| Task killed by TMC timeout | Same as "fails midway". |

Operational levers:
- **Backfill / replay**: set TMC parameter `wm_override_from` to a timestamp for a single *Run now*, then clear it. The run writes a normal `wm_to` afterwards, so you are back on schedule without touching the table. Alternatively `UPDATE ETL_CTRL.JOB_WATERMARK SET WATERMARK_TS = '...'`.
- **Full reload**: set the watermark to `1900-01-01 00:00:00.000000+00` and run once (consider a larger warehouse for that run).
- **Why no local file / TMC variable**: the watermark is independent of which Remote Engine (or engine-cluster member) runs the task, of artifact versions, and of TMC task recreation. Promoting the task Dev -> Prod does not carry a watermark across environments because each environment points at its own Snowflake control table via context.

---

## 6. Deploying and scheduling on a Remote Engine via TMC

### 6.1 Prepare the Remote Engine
1. TMC > **Processing > Engines > Add > Remote Engine**: give it a name (`re-prod-etl-01`), choose the environment (`PROD`), copy the **pre-authorization key**.
2. On a Linux VM that can reach PostgreSQL (TCP 5432), Snowflake (`*.snowflakecomputing.com`:443 plus the account's internal stage bucket endpoints), your SMTP relay, and Talend Cloud over HTTPS (443) outbound only: install the Remote Engine package for your Talend Cloud region (download from TMC's engine page), Java 17 runtime as required by Talend 8 R2025, put the key into `etc/preauthorized.key.cfg`, start the engine service. Status in TMC turns **Paired**.
3. Optional but recommended: pair a second engine and group both in an **Engine Cluster**; the task then fails over automatically. The watermark design is cluster-safe because nothing is stored on the engine host.
4. Create a **Run profile** for Standard jobs on the engine if you want dedicated JVM sizing (`-Xms256m -Xmx1024m -Duser.timezone=UTC`).

### 6.2 Publish the job artifact
Option 1 (Studio, interactive): right-click the job > **Publish to Cloud** > select the TMC **Workspace** (in the DEV environment first), keep *Standard Job*, version `0.1`-> auto-increment, Publish. The artifact appears in **Management > Artifacts**.

Option 2 (CI/CD, recommended for Prod): Talend CI Builder (Maven) builds from the Git-backed project and publishes with the Cloud publisher goal using a TMC **Service Account token** (`-Dcloud.publisher.token`, `-Dservice.url=https://api.<region>.cloud.talend.com`, `-Dcloud.publisher.environment=... -Dcloud.publisher.workspace=...`). Same artifact, no Studio on the build box.

### 6.3 Create the task
TMC > **Management > Tasks > Add task**:
1. **Artifact**: pick `ORDERS_INCREMENTAL_LOAD`, version = specific (or *Always use latest* in Dev only).
2. **Parameters**: choose context `PROD`; override host/user values; enter the Password-type parameters here (they are masked and encrypted). If your job uses repository DB metadata instead of raw context, TMC will show them as **Connections** you can bind to shared Connection objects instead.
3. **Processing**: Runtime = *Remote Engine* `re-prod-etl-01` (or the cluster); Run profile / JVM parameters `-Xms256m -Xmx1024m -Duser.timezone=UTC`; Log level *Info*; **Timeout** 14 minutes (so a hung run is killed before the next slot); **Allow parallel run of this task: OFF**.
4. **Run type**: *Schedule* > **Daily** trigger, Repeat **every 15 minutes** from 00:00 to 23:59, time zone UTC (equivalently a *Cron* trigger of "every 15 minutes"; TMC previews the next executions so you can verify the cadence). Save.
5. Click **Run now** once, watch **Run history > logs** for `wm_from = ...` / `wm_to = ...`, then check `SELECT * FROM ETL_CTRL.JOB_WATERMARK` advanced.

### 6.4 Promotion Dev -> Prod
Use **Management > Promotions** (or redo *Add task* in the Prod workspace pointing at the Prod engine and Prod context). The Prod task gets its own parameter values; the Prod Snowflake control table starts from the seed row.

### 6.5 Second alerting channel
In TMC enable **Notifications** for the task (task execution failed -> email to the ops distribution list; a webhook can push to Slack/PagerDuty). That alert fires even if the job itself died before `tSendMail` could run (e.g. JVM start failure, engine offline), which the in-job email cannot cover.

### 6.6 Smoke tests before go-live
- Update one order in PostgreSQL, run the task, confirm the row changed in Snowflake and `ROWS_LOADED = 1`.
- Kill the task mid-run from TMC; confirm `WATERMARK_TS` did not move and the next run reloads the window cleanly.
- Point `smtp_host` at a wrong value and break a query on purpose: verify the task shows *Failed* in TMC and the ops mail arrives (first test) or the TMC notification arrives (second test).

---

## 7. Known limitations and how to handle them later
- **Hard deletes** in PostgreSQL are invisible to `updated_at`. Use soft-delete flags, a delete-audit table processed by a sibling job, or periodic key reconciliation.
- **Backdated `updated_at`** (manual data fixes with explicit old timestamps) will be skipped; forbid it or run a nightly wide-window catch-up (`wm_override_from = now - 1 day`), which is harmless thanks to the idempotent upsert.
- **Very large catch-up after an outage**: the Snowflake output component handles millions of rows via stage/COPY, but you may raise `fetch_size`, the JVM heap, and the warehouse size for that one run; the 14-minute timeout may need a temporary bump.
