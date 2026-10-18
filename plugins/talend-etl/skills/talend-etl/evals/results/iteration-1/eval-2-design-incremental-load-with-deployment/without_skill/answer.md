# Incremental PostgreSQL -> Snowflake orders load (Talend Studio 8.0 Standard job, TMC + Remote Engine)

## 1. Design decisions up front

| Concern | Decision | Why |
|---|---|---|
| Where the watermark lives | A control table **in Snowflake** (`ETL_CONTROL.LOAD_WATERMARK`), one row per job | Survives JVM restarts, engine rebuilds, engine clusters and promotion between environments. A file on the Remote Engine is lost if the engine is reinstalled or you add a second engine; TMC context parameters are read-only at run time (a job cannot write them back); `globalMap` dies with the JVM. |
| Window boundaries | `updated_at > low_wm AND updated_at <= high_wm`, where `high_wm = now() - safety_lag` is taken **from the PostgreSQL clock at job start** and frozen | Avoids engine/DB clock skew, avoids missing rows that are committed late by long transactions (the lag), and guarantees no gaps: the next run's `low_wm` is exactly this run's `high_wm`. The watermark advances even when zero rows are found. |
| Write mode | `tSnowflakeOutput` with **Output Action = UPSERT**, key `ORDER_ID` (Talend stages the batch to a temp table and runs `MERGE`) | Idempotent, so re-running an overlapping window after a failure is harmless. |
| Restartability | Watermark is only advanced **after** the upsert finished; on any error the job rolls back, emails ops, exits non-zero | A failed run leaves the watermark unchanged; the next scheduled run (15 min later) simply replays the same window. No manual intervention needed. |
| Alerting | `tLogCatcher` captures the exception text, `OnSubjobError` -> `tSendMail` -> `tDie` | Email contains the actual error; `tDie` makes TMC show the run as failed. Add TMC's own "task failed" notification as a second channel. |
| Time zones | `timestamptz` in PostgreSQL, `TIMESTAMP_TZ` in Snowflake, watermark exchanged as a UTC **string** (`YYYY-MM-DD HH24:MI:SS.ffffff +00:00`), JVM run with `-Duser.timezone=UTC` | Talend's `Date` type has no zone; passing the watermark as text removes a whole class of DST/offset bugs. |

Prerequisites on the source: `orders.order_id` is the PK (so each key appears once per batch; `MERGE` fails on duplicate keys), `updated_at` is maintained by a trigger (not the application), and there is an index on `orders(updated_at)`. Hard deletes are not captured by an `updated_at` design: use a soft-delete flag or a periodic reconciliation job.

## 2. Snowflake objects

```sql
CREATE SCHEMA IF NOT EXISTS ETL_CONTROL;

CREATE TABLE IF NOT EXISTS ETL_CONTROL.LOAD_WATERMARK (
  JOB_NAME        VARCHAR(100)  NOT NULL PRIMARY KEY,
  WATERMARK_TS    TIMESTAMP_TZ  NOT NULL,
  LAST_RUN_TS     TIMESTAMP_TZ,
  LAST_ROW_COUNT  NUMBER,
  LAST_STATUS     VARCHAR(20)
);
-- seed once (or let the job fall back to context.initial_watermark)
INSERT INTO ETL_CONTROL.LOAD_WATERMARK VALUES ('orders_pg_to_sf', '1970-01-01 00:00:00 +00:00', NULL, NULL, 'INIT');

CREATE TABLE IF NOT EXISTS SALES.ORDERS (
  ORDER_ID        NUMBER        NOT NULL,
  CUSTOMER_ID     NUMBER,
  STATUS          VARCHAR(30),
  TOTAL_AMOUNT    NUMBER(18,2),
  CURRENCY        VARCHAR(3),
  CREATED_AT      TIMESTAMP_TZ,
  UPDATED_AT      TIMESTAMP_TZ,
  ETL_LOAD_TS     TIMESTAMP_TZ
);
```

Use a dedicated `TYPE = SERVICE` Snowflake user with its own role (USAGE on warehouse/db/schemas, SELECT/INSERT/UPDATE on both tables, CREATE TABLE on the target schema because the UPSERT mode creates a temp table). Prefer key-pair auth: Snowflake is phasing out single-factor passwords.

## 3. Job layout (Standard job `orders_pg_to_sf`)

```
tPrejob ──OnComponentOk──> tPostgresqlConnection_1 ──OnComponentOk──> tSnowflakeConnection_1

[Subjob A: read low watermark]
tSnowflakeInput_1 (control table) ──row Main──> tJavaRow_1   (globalMap "low_wm")
        │ OnSubjobOk
[Subjob B: freeze high watermark from PG clock]
tPostgresqlInput_1 (SELECT now()-lag) ──row Main──> tJavaRow_2 (globalMap "high_wm")
        │ OnSubjobOk
[Subjob C: extract + upsert]
tPostgresqlInput_2 (orders window) ──row Main──> tMap_1 ──row out──> tSnowflakeOutput_1 (UPSERT on ORDER_ID)
        │ OnSubjobOk
[Subjob D: advance watermark]
tSnowflakeRow_1 (MERGE control table) ──OnComponentOk──> tWarn_1 ("loaded N rows up to <high_wm>")

[Subjob E: error path]   (OnSubjobError links from A, B, C and D all point here)
tSnowflakeRollback_1 ──OnComponentOk──> tSendMail_1 ──OnComponentOk──> tDie_1

[Subjob F: event-driven]
tLogCatcher_1 ──row Main──> tJavaRow_3   (globalMap "err_msg" = origin + message)

tPostjob ──OnComponentOk──> tSnowflakeClose_1 ──OnComponentOk──> tPostgresqlClose_1
```

All triggers in the main chain are **OnSubjobOk** (not OnComponentOk) so each step runs only after the whole previous subjob finished. Every DB component has **Die on error** checked, otherwise `tLogCatcher`/`OnSubjobError` never fire and you would advance the watermark over a silently failed load.

### Component settings

**tPostgresqlConnection_1**: Host `context.pg_host`, Port `context.pg_port`, Database `context.pg_database`, Schema `context.pg_schema`, User/Password `context.pg_user` / `context.pg_password`; Additional JDBC parameters `"sslmode=" + context.pg_sslmode`. Advanced: Auto Commit on (read-only).

**tSnowflakeConnection_1**: Account `context.sf_account`, User `context.sf_user`, Authentication = Key Pair (keystore alias/password; the keystore file must exist on the Remote Engine host and be referenced via JVM parameters in the TMC task) or Basic with `context.sf_password`; Warehouse `context.sf_warehouse`, Database `context.sf_database`, Schema `context.sf_schema`, Role `context.sf_role`.

**tSnowflakeInput_1** (Subjob A): Use existing connection; Manual query, schema one column `LOW_WM` (String):

```java
"SELECT COALESCE(TO_VARCHAR(MAX(WATERMARK_TS), 'YYYY-MM-DD HH24:MI:SS.FF6 TZH:TZM'), '"
 + context.initial_watermark + "') AS LOW_WM FROM " + context.sf_control_table
 + " WHERE JOB_NAME = '" + context.job_name + "'"
```
(`COALESCE(MAX(...))` always returns exactly one row, so the first run works without a seed.)

**tJavaRow_1**: `globalMap.put("low_wm", input_row.LOW_WM);`

**tPostgresqlInput_1** (Subjob B): schema one column `HIGH_WM` (String):

```java
"SELECT to_char((now() - (" + context.safety_lag_seconds + " * interval '1 second')) AT TIME ZONE 'UTC',"
 + " 'YYYY-MM-DD HH24:MI:SS.US') || ' +00:00' AS high_wm"
```

**tJavaRow_2**: `globalMap.put("high_wm", input_row.HIGH_WM);`

**tPostgresqlInput_2** (Subjob C): Use existing connection; schema = source columns; query:

```java
"SELECT order_id, customer_id, status, total_amount, currency, created_at, updated_at"
 + " FROM " + context.pg_schema + ".orders"
 + " WHERE updated_at >  '" + (String)globalMap.get("low_wm")  + "'::timestamptz"
 + "   AND updated_at <= '" + (String)globalMap.get("high_wm") + "'::timestamptz"
 + " ORDER BY updated_at, order_id"
```
Advanced: **Use cursor**, Cursor size `context.fetch_size` (e.g. 10000) so a large catch-up window streams instead of loading into memory. (Both bound values come from the databases, not from user input, so string concatenation is safe here; `Use PreparedStatement` in Advanced settings is the alternative.)

**tMap_1**: pass-through with upper-case Snowflake column names, plus `ETL_LOAD_TS = TalendDate.getCurrentDate()`. If your extract could ever contain the same `order_id` twice, put a `tUniqRow` on `order_id` before the output; `MERGE` rejects multi-row matches.

**tSnowflakeOutput_1**: Use existing connection; Table `context.sf_target_table`; **Table Action = NONE**; **Output Action = UPSERT**; **Upsert Key Column = ORDER_ID**; Die on error checked. Advanced: Convert empty strings to null as needed. Expected volume at 15-minute cadence is small, so this one component is enough. For bulk catch-ups (millions of rows) switch to `tSnowflakeOutputBulkExec` into a staging table followed by your own `MERGE` in `tSnowflakeRow`.

**tSnowflakeRow_1** (Subjob D):

```java
"MERGE INTO " + context.sf_control_table + " t"
 + " USING (SELECT '" + context.job_name + "' AS JOB_NAME) s ON t.JOB_NAME = s.JOB_NAME"
 + " WHEN MATCHED THEN UPDATE SET"
 + "   WATERMARK_TS = TO_TIMESTAMP_TZ('" + globalMap.get("high_wm") + "', 'YYYY-MM-DD HH24:MI:SS.FF6 TZH:TZM'),"
 + "   LAST_RUN_TS = CURRENT_TIMESTAMP(), LAST_ROW_COUNT = " + ((Integer)globalMap.get("tSnowflakeOutput_1_NB_LINE"))
 + ",  LAST_STATUS = 'SUCCESS'"
 + " WHEN NOT MATCHED THEN INSERT (JOB_NAME, WATERMARK_TS, LAST_RUN_TS, LAST_ROW_COUNT, LAST_STATUS)"
 + " VALUES ('" + context.job_name + "', TO_TIMESTAMP_TZ('" + globalMap.get("high_wm") + "', 'YYYY-MM-DD HH24:MI:SS.FF6 TZH:TZM'),"
 + " CURRENT_TIMESTAMP(), " + ((Integer)globalMap.get("tSnowflakeOutput_1_NB_LINE")) + ", 'SUCCESS')"
```

**tWarn_1**: `"orders_pg_to_sf: " + globalMap.get("tSnowflakeOutput_1_NB_LINE") + " rows upserted, window (" + globalMap.get("low_wm") + ", " + globalMap.get("high_wm") + "]"` -- shows up in the TMC run log.

**tLogCatcher_1 / tJavaRow_3** (Subjob F): catch Java Exception, tDie and tWarn; in tJavaRow_3:
`globalMap.put("err_msg", (globalMap.get("err_msg") == null ? "" : globalMap.get("err_msg") + "\n") + input_row.origin + ": " + input_row.message);`

**tSnowflakeRollback_1**: Use existing connection, do not close.

**tSendMail_1**: SMTP host/port `context.smtp_host` / `context.smtp_port`, STARTTLS or SSL as your relay requires, auth `context.smtp_user` / `context.smtp_password`; From `context.mail_from`; To `context.mail_to_ops`;
Subject: `"[" + context.env_name + "] Talend job orders_pg_to_sf FAILED"`;
Body:
```java
"Job: " + jobName + "  pid: " + pid + "\nTime: " + TalendDate.getDate("yyyy-MM-dd HH:mm:ss")
 + "\nWindow: (" + globalMap.get("low_wm") + ", " + globalMap.get("high_wm") + "]"
 + "\nWatermark NOT advanced; next scheduled run will retry the same window."
 + "\n\nError:\n" + globalMap.get("err_msg")
```

**tDie_1**: Code `4`, message `"orders_pg_to_sf failed"`. Leave "Exit the JVM immediately" unchecked so `tPostjob` still closes connections. The non-zero exit code is what TMC uses to mark the execution as Failed.

Optional hardening (test before relying on it): make the upsert and the watermark update one Snowflake transaction by turning off auto-commit on `tSnowflakeConnection_1` and adding `tSnowflakeCommit_1` after `tSnowflakeRow_1`. Not strictly necessary: without it, a crash between C and D only means the window is replayed, and the upsert is idempotent.

Optional run lock: if you ever enable engine clusters or parallel runs, add a Subjob A2 that sets `LAST_STATUS='RUNNING'` and aborts (`tDie`) when the row is already RUNNING and `LAST_RUN_TS` is younger than, say, 60 minutes (a lease, so a killed run cannot deadlock the job). With TMC's "allow parallel runs" disabled (below) this is belt-and-braces.

## 4. Context variables (context group `ORDERS_LOAD`, environments Default / Prod)

| Variable | Type | Example default | Notes |
|---|---|---|---|
| `env_name` | String | `DEV` | Used in email subject |
| `job_name` | String | `orders_pg_to_sf` | Key in control table |
| `initial_watermark` | String | `1970-01-01 00:00:00.000000 +00:00` | First run only |
| `safety_lag_seconds` | Integer | `120` | Covers long transactions / replica lag |
| `fetch_size` | Integer | `10000` | PG cursor size |
| `pg_host`, `pg_port`, `pg_database`, `pg_schema`, `pg_user` | String/Integer | | |
| `pg_password` | **Password** | | Masked in Studio and TMC |
| `pg_sslmode` | String | `require` | |
| `sf_account`, `sf_user`, `sf_role`, `sf_warehouse`, `sf_database`, `sf_schema` | String | | |
| `sf_password` | **Password** | | Only if not using key pair |
| `sf_target_table` | String | `SALES.ORDERS` | |
| `sf_control_table` | String | `ETL_CONTROL.LOAD_WATERMARK` | |
| `smtp_host`, `smtp_port`, `smtp_user`, `mail_from`, `mail_to_ops` | String/Integer | | `mail_to_ops` can be a comma-separated list |
| `smtp_password` | **Password** | | |

Keep real production values out of the Studio project; set them as task parameters in TMC (section 5, step 4).

In the job's Run tab > Advanced settings add JVM parameter `-Duser.timezone=UTC` (and `-Xmx1g` or whatever the catch-up volume needs). You will set the same JVM parameters on the TMC task so the deployed run matches Studio.

## 5. Deploy and schedule on TMC with a Remote Engine

1. **Prepare the Remote Engine.** TMC > Management > Engines > Add > Remote Engine: name it (e.g. `re-prod-etl-01`), choose the workspace/environment, copy the **pairing key**, download the installer. On a Linux VM with network access to PostgreSQL, Snowflake (`<account>.snowflakecomputing.com`, port 443) and your SMTP relay, plus outbound HTTPS to your Talend Cloud region, install it (e.g. `/opt/talend/remote-engine`), put the key in `etc/preauthorized.key.cfg` (`remote.engine.pre.authorized.key=<key>`), start `bin/start` (install as a systemd service). The engine should show **Paired / Available** in TMC. Keep the engine on the current version: an artifact built with a given Studio 8.0 monthly update needs an engine release that supports it, and TMC reports that incompatibility at run time. If you use Snowflake key-pair auth, place the keystore file on this host and reference it via the task's JVM parameters.

2. **Publish the job from Studio.** The project must be a Talend Cloud (remote) project and Studio connected to the cloud account (Preferences > Talend > Cloud / project connection). Right-click the job > **Publish to Cloud**, pick the workspace and bump the version (e.g. `0.1`). The job plus the Snowflake/PostgreSQL JDBC drivers and the `ORDERS_LOAD` context group are packaged into the artifact, which appears under Management > Artifacts. (For CI, the equivalent is the Talend CI Builder Maven `cloud-publisher` profile or the TMC API; TMC has no manual zip upload.)

3. **Create the task.** Management > Tasks > Add task > select the artifact and version, name `orders_pg_to_sf (prod)`, workspace/environment Prod.

4. **Parameters step.** TMC shows every context variable with the published defaults; override the production values here (hosts, users, passwords, `env_name=PROD`, `mail_to_ops`). Password-type variables are stored masked. Nothing sensitive needs to be committed to the project. If you later promote the task Dev -> Prod with TMC Promotions, the parameter overrides travel with the task and you only edit what differs.

5. **Processing step.** Run profile: **Engine** -> `re-prod-etl-01` (a Cloud Engine cannot reach your private PostgreSQL). Log level `Info` (or `Warn`; `tWarn` output is still visible). **JVM parameters**: `-Duser.timezone=UTC -Xmx1g` (plus keystore properties if applicable). **Timeout: 14 minutes**, so a hung run is killed before the next trigger and never overlaps. **Allow parallel runs: OFF**, so if a run is still going when the trigger fires, that trigger is skipped rather than starting a second JVM against the same watermark.

6. **Schedule.** Trigger type **Simple**: start at the next quarter hour in your operating time zone, **repeat every 15 minutes**, no end date (or a CRON trigger if you prefer an explicit expression). Save; the task shows status Scheduled and the next run time.

7. **First run and verification.** Run once manually from the task page. Check Run history > logs for the `tWarn` line, then in Snowflake: `SELECT * FROM ETL_CONTROL.LOAD_WATERMARK WHERE JOB_NAME='orders_pg_to_sf'` -- `WATERMARK_TS` should equal the run's `high_wm`. Update a row in PostgreSQL, wait one cycle, and confirm it is upserted (same `ORDER_ID`, new values, no duplicate).

8. **Failure alerting, second channel.** Besides the job's own `tSendMail`, subscribe the ops users in TMC (user menu > Notifications) to "Task execution failed" for the Prod environment, so you also get an email when the job never starts (engine down, artifact incompatible) -- cases the in-job email cannot cover.

## 6. How the watermark survives between runs

Each TMC execution is a fresh JVM on the Remote Engine: `globalMap`, Java variables and context values are discarded at exit, and TMC parameters are inputs only. The job therefore externalises its state:

- At the start of every run it **reads** `WATERMARK_TS` from `ETL_CONTROL.LOAD_WATERMARK` (Subjob A) -- falling back to `context.initial_watermark` if the row does not exist yet.
- It freezes `high_wm` from the PostgreSQL clock minus the safety lag (Subjob B) and extracts exactly `(low_wm, high_wm]` (Subjob C).
- Only after the upsert has finished does it **write** `high_wm` back as the new `WATERMARK_TS` (Subjob D).

Because the state is in Snowflake, it is identical whichever engine runs the task, survives engine reinstallation or a move to an engine cluster, is visible to ops for monitoring (`LAST_RUN_TS`, `LAST_ROW_COUNT`, `LAST_STATUS`), and can be reset for a backfill with one `UPDATE` (set `WATERMARK_TS` back in time; the upsert makes replays safe). If any step fails, Subjob E rolls back, emails ops and exits with code 4 -- the watermark row is untouched, so the next 15-minute trigger retries the same window automatically.
