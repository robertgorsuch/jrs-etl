# LOAD_ORDERS_INCR - PostgreSQL -> Snowflake incremental upsert, every 15 min on a Remote Engine

Target: Talend Studio 8.0 (R2025-xx, subscription), Talend Cloud / TMC, Standard (DI) Job,
Remote Engine (Gen1, Java 17). Component labels below are Studio 8.0 labels; the few that
the documentation does not pin down are marked `(confirm in Component view)`.

## 0. Design decisions in one paragraph

The watermark lives in a **control table in Snowflake** (`ETL_CTRL.ETL_WATERMARK`), not in a
file on the engine and not in a context variable: a TMC run is a fresh JVM on the Remote Engine,
globalMap/context are rebuilt from the artifact plus the task's Parameters on every run, and the
Job cannot write back to the TMC task. Putting the watermark in the *target* database lets the
upsert and the watermark UPDATE sit in **one Snowflake transaction** committed by a single
`tSnowflakeCommit`: a crash anywhere before the commit rolls both back, so the next 15-minute
run simply re-extracts the same window. The extract window is
`updated_at > (last_watermark - overlap) AND updated_at <= (source_now - safety_lag)`, capped
to a maximum width so a backlog is caught up in chunks; the overlap plus the ORDER_ID upsert
make re-processing idempotent. Failure path: `tLogCatcher` records the message, `OnSubjobError`
-> `tSnowflakeRollback` -> `tSendMail` -> `tDie` (exit code 4) so TMC marks the run
`Execution failed` and can also notify.

## 1. Prerequisites (outside Talend)

**Source (PostgreSQL)** - `orders(order_id PK, ..., updated_at timestamptz NOT NULL)`;
`updated_at` must be maintained on every INSERT *and* UPDATE (a `BEFORE UPDATE` trigger
setting `updated_at = now()` is the usual way - an application-set column is not reliable
enough for a watermark), and indexed: `CREATE INDEX orders_updated_at_idx ON orders(updated_at);`.
Hard deletes are **not** captured by a watermark design; use a soft-delete flag (`is_deleted`,
also bumping `updated_at`) or accept it. Read-only DB user is enough.

**Target (Snowflake)**

```sql
CREATE SCHEMA IF NOT EXISTS ETL_CTRL;
CREATE TABLE IF NOT EXISTS ETL_CTRL.ETL_WATERMARK (
  JOB_NAME        VARCHAR(100)      NOT NULL,
  LAST_WATERMARK  TIMESTAMP_NTZ(6)  NOT NULL,   -- UTC
  LAST_RUN_ID     VARCHAR(50),
  LAST_RUN_AT     TIMESTAMP_NTZ(6),
  LAST_ROWS       NUMBER,
  CONSTRAINT PK_ETL_WATERMARK PRIMARY KEY (JOB_NAME)
);
-- seed once per environment; for a first load set it to a date before the oldest order
INSERT INTO ETL_CTRL.ETL_WATERMARK (JOB_NAME, LAST_WATERMARK)
VALUES ('LOAD_ORDERS_INCR', '2000-01-01 00:00:00');

CREATE TABLE IF NOT EXISTS DWH.ORDERS (
  ORDER_ID NUMBER(38,0) NOT NULL, CUSTOMER_ID NUMBER(38,0), STATUS VARCHAR(30),
  ORDER_TOTAL NUMBER(18,2), CURRENCY VARCHAR(3),
  CREATED_AT TIMESTAMP_NTZ(6), UPDATED_AT TIMESTAMP_NTZ(6),
  ETL_RUN_ID VARCHAR(50), ETL_LOADED_AT TIMESTAMP_NTZ(6),
  CONSTRAINT PK_ORDERS PRIMARY KEY (ORDER_ID)
);
```
(Snowflake does not enforce the PK; uniqueness comes from the upsert on ORDER_ID.) Use a small
dedicated warehouse with `AUTO_SUSPEND = 60`: a 15-minute cadence otherwise keeps a warehouse
billing continuously. Grant the ETL role `SELECT, INSERT, UPDATE` on both schemas.

**Remote Engine host** - outbound 443 to `*.cloud.talend.com`, to the Snowflake account URL,
to PostgreSQL (5432) and to the SMTP relay (587/465). Java 17 (bundled/required by current
RE versions). JDBC drivers are not installed by hand: the published artifact carries the
PostgreSQL and Snowflake driver jars from Studio's Modules.

## 2. Job layout (Standard Job `LOAD_ORDERS_INCR`, folder `load/`)

Labels on the canvas are the readable names; the **unique names** in brackets are what
globalMap keys use (`tSnowflakeOutput_1_NB_LINE`, not the label).

```
tPrejob_1 --OnComponentOk--> tSnowflakeConnection_1 --OnComponentOk--> tDBConnection_1 [PostgreSQL]
                                                                        --OnComponentOk--> tJava_1 "init"

S1  tSnowflakeInput_1 "read watermark" --row1(Main)--> tJavaRow_1 (globalMap WM_LOW)
       |OnSubjobOk
S2  tDBInput_1 "source clock" --row2(Main)--> tJavaRow_2 (globalMap WM_HIGH)
       |OnSubjobOk
S3  tJava_2 "compute window"  (WM_LOW_EFF, capped WM_HIGH, log the window)
       |OnSubjobOk
S4  tDBInput_2 "orders delta" --row3(Main)--> tMap_1 --out(Main)--> tSnowflakeOutput_1 "UPSERT ORDERS"
       |OnSubjobOk
S5  tSnowflakeRow_1 "advance watermark"
       |OnSubjobOk
S6  tSnowflakeCommit_1 (Close Connection unchecked)
       |OnSubjobOk
S7  tJava_3 "summary line"

ERR tLogCatcher_1 (Catch Java Exception) --row4(Main)--> tJavaRow_3 (globalMap ERR_TEXT)

    S1, S2, S3, S4, S5 start components --OnSubjobError--> tSnowflakeRollback_1 (Close Connection unchecked)
    tSnowflakeRollback_1 --OnComponentOk--> tSendMail_1 "ops alert"
    tSnowflakeRollback_1 --OnComponentError--> tSendMail_1          (mail even if rollback itself fails)
    tSendMail_1 --OnComponentOk--> tDie_1 (Error code 4)
    tSendMail_1 --OnComponentError--> tDie_1                          (die even if SMTP is down)

tPostjob_1 --OnComponentOk--> tSnowflakeClose_1 --OnComponentOk--> tDBClose_1 [PostgreSQL]
```

Link rules used: `OnSubjobOk` (not `OnComponentOk`) between subjobs so S5 only runs after
`tSnowflakeOutput_1` has flushed; `OnSubjobError` is drawn from each subjob's *start*
component; tPrejob/tPostjob only take `OnComponentOk` links; the tLogCatcher subjob has no
incoming trigger (it is fired by the exception itself, synchronously, before `OnSubjobError`).
Several `OnSubjobError` links may target the same `tSnowflakeRollback_1`.

## 3. Component settings

### tPrejob chain

| Component | Setting | Value |
|---|---|---|
| **tSnowflakeConnection_1** | Account | `context.SF_ACCOUNT` (full `org-account` identifier) |
| | User Id / Authentication Type | `context.SF_USER`; `Basic` with `context.SF_PASSWORD`, or `Key Pair` (`Private Key` content/path, passphrase) - key pair is preferred for a service user |
| | Warehouse / Database / Schema / Role | `context.SF_WAREHOUSE`, `context.SF_DATABASE`, `context.SF_SCHEMA`, `context.SF_ROLE` |
| | Advanced > Auto Commit | **unchecked** (confirm the label exists in your R-release; if absent, add `tSnowflakeRow_0` right after it with Query `"ALTER SESSION SET AUTOCOMMIT = FALSE"`, `Use an existing connection`) |
| | Advanced > Additional JDBC Parameters | `"application=TALEND_LOAD_ORDERS"` (optional tagging in `QUERY_HISTORY`) |
| **tDBConnection_1** | Database | `PostgreSQL`; DB Version per your server |
| | Host / Port / Database / Schema | `context.PG_HOST`, `context.PG_PORT`, `context.PG_DB`, `context.PG_SCHEMA` |
| | Username / Password | `context.PG_USER`, `context.PG_PASSWORD` |
| | Additional JDBC Parameters | `"sslmode=require"` (plus `&ApplicationName=talend_load_orders`) |
| | Auto Commit | **unchecked** - required for `Use cursor` streaming on PostgreSQL; the Job never writes to PG |
| **tJava_1** | Code | `System.out.println(jobName + " v" + jobVersion + " start pid=" + pid + " env=" + context.ENV + " engine=" + java.net.InetAddress.getLocalHost().getHostName());` |

### S1 - read the watermark

| Component | Setting | Value |
|---|---|---|
| **tSnowflakeInput_1** | Use an existing connection | `tSnowflakeConnection_1` |
| | Manual Query (checked) / Query | `"SELECT LAST_WATERMARK FROM " + context.SF_CTRL_SCHEMA + ".ETL_WATERMARK WHERE JOB_NAME = '" + context.JOB_KEY + "'"` |
| | Schema | `LAST_WATERMARK` : Date, nullable |
| | Die on error | checked |
| **tJavaRow_1** | Code | `globalMap.put("WM_LOW", input_row.LAST_WATERMARK);` |

### S2 - take the upper bound from the *source* clock (no engine clock skew)

| Component | Setting | Value |
|---|---|---|
| **tDBInput_1** | Database / Use an existing connection | `PostgreSQL` / `tDBConnection_1` |
| | Query | `"SELECT now() - make_interval(secs => " + context.WM_SAFETY_LAG_SEC + ") AS wm_high"` |
| | Schema | `wm_high` : Date |
| **tJavaRow_2** | Code | `globalMap.put("WM_HIGH", input_row.wm_high);` |

### S3 - compute the window (tJava_2)

```java
java.util.Date wmLow  = (java.util.Date) globalMap.get("WM_LOW");
java.util.Date wmHigh = (java.util.Date) globalMap.get("WM_HIGH");
if (wmLow == null)  throw new RuntimeException("No ETL_WATERMARK row for " + context.JOB_KEY + " - seed it (section 1)");
if (wmHigh == null) throw new RuntimeException("Could not read the PostgreSQL clock");

// cap the window so a backlog is caught up in chunks and every run commits progress
long maxMs = context.WM_MAX_WINDOW_MIN * 60000L;
if (wmHigh.getTime() - wmLow.getTime() > maxMs) {
    wmHigh = new java.util.Date(wmLow.getTime() + maxMs);
    globalMap.put("WM_HIGH", wmHigh);
    System.out.println("WARN backlog: window capped at " + context.WM_MAX_WINDOW_MIN + " min");
}
// overlap: re-read a little of the previous window; the upsert makes it harmless
java.util.Date wmLowEff = TalendDate.addDate(wmLow, -context.WM_OVERLAP_SEC, "ss");
globalMap.put("WM_LOW_EFF", wmLowEff);
globalMap.put("WM_LOW_EFF_STR", TalendDate.formatDate("yyyy-MM-dd HH:mm:ss.SSS", wmLowEff));
globalMap.put("WM_HIGH_STR",    TalendDate.formatDate("yyyy-MM-dd HH:mm:ss.SSS", wmHigh));
System.out.println("window (" + globalMap.get("WM_LOW_EFF_STR") + " , " + globalMap.get("WM_HIGH_STR") + "]");
```
A `RuntimeException` thrown in tJava is a normal Java exception: tLogCatcher sees it,
`OnSubjobError` fires, exit code is non-zero.

### S4 - extract and upsert

| Component | Setting | Value |
|---|---|---|
| **tDBInput_2** | Database / Use an existing connection | `PostgreSQL` / `tDBConnection_1` |
| | Query | `"SELECT order_id, customer_id, status, order_total, currency, created_at, updated_at FROM " + context.PG_SCHEMA + ".orders WHERE updated_at > ? AND updated_at <= ? ORDER BY updated_at, order_id"` |
| | Advanced > Use PreparedStatement | checked; Set PreparedStatement Parameters: `1, Date, (java.util.Date) globalMap.get("WM_LOW_EFF")` and `2, Date, (java.util.Date) globalMap.get("WM_HIGH")` (confirm the option is present on the PostgreSQL flavour of tDBInput; fallback below) |
| | Advanced > Use cursor / Cursor Size | checked / `context.FETCH_SIZE` (streams rows instead of loading the result set; needs Auto Commit off on tDBConnection_1) |
| | Schema | columns in **SELECT order**: `order_id` Long (Key), `customer_id` Long, `status` String, `order_total` BigDecimal, `currency` String, `created_at` Date, `updated_at` Date - mark every nullable source column `Nullable` |
| | Die on error | checked |
| **tMap_1** | out (Main) | pass-through renames to Snowflake upper-case names: `ORDER_ID = row3.order_id` (**Key** checked in the output schema), `CUSTOMER_ID`, `STATUS = row3.status == null ? null : row3.status.trim()`, `ORDER_TOTAL`, `CURRENCY`, `CREATED_AT`, `UPDATED_AT`; audit: `ETL_RUN_ID = pid`, `ETL_LOADED_AT = TalendDate.getCurrentDate()` |
| **tSnowflakeOutput_1** | Use an existing connection | `tSnowflakeConnection_1` |
| | Table | `context.SF_TARGET_TABLE` (e.g. `"DWH.ORDERS"`, or `"ORDERS"` with Schema set on the connection) |
| | Table Action | `None` |
| | Output Action | **`Upsert`** |
| | Upsert Key Column | `ORDER_ID` |
| | Die on error | checked (a batch failure must roll back the whole run, no Reject link) |
| | Advanced > Convert columns and table to uppercase | checked if your schema column names are not already upper case; `Convert empty strings to null` as needed |

Fallback without PreparedStatement (string query; relies on the JVM running in UTC, see
section 6):
`"... WHERE updated_at > TIMESTAMP '" + globalMap.get("WM_LOW_EFF_STR") + "' AT TIME ZONE 'UTC' AND updated_at <= TIMESTAMP '" + globalMap.get("WM_HIGH_STR") + "' AT TIME ZONE 'UTC'"`.

Volume note: `tSnowflakeOutput` `Upsert` sends JDBC batches and merges per batch; it is
right for 15-minute deltas up to roughly 100k rows per run. Above that switch S4's output to
`tSnowflakeOutputBulkExec` (`Storage = Internal`, `Output Action = Upsert`, `Upsert Key
Column = ORDER_ID`, `Compress by gzip`) which stages a file and runs `COPY INTO` + `MERGE`,
or load a staging table with `Insert` and run your own `MERGE ... USING (SELECT ... QUALIFY
ROW_NUMBER() OVER (PARTITION BY ORDER_ID ORDER BY UPDATED_AT DESC) = 1)` in a `tSnowflakeRow`
before S5. Transaction semantics stay identical as long as everything uses
`tSnowflakeConnection_1`.

### S5 - advance the watermark (same transaction)

**tSnowflakeRow_1**: `Use an existing connection` = `tSnowflakeConnection_1`, `Die on error`
checked, Query:

```java
"UPDATE " + context.SF_CTRL_SCHEMA + ".ETL_WATERMARK SET "
+ " LAST_WATERMARK = GREATEST(LAST_WATERMARK, TO_TIMESTAMP_NTZ('" + globalMap.get("WM_HIGH_STR") + "', 'YYYY-MM-DD HH24:MI:SS.FF3')),"
+ " LAST_RUN_ID = '" + pid + "', LAST_RUN_AT = CURRENT_TIMESTAMP(),"
+ " LAST_ROWS = " + String.valueOf(globalMap.get("tSnowflakeOutput_1_NB_LINE"))
+ " WHERE JOB_NAME = '" + context.JOB_KEY + "'"
```
`GREATEST` guarantees the watermark never moves backwards (clock skew, manual reruns). The
new watermark is the run's **upper bound** (`WM_HIGH`), never `MAX(updated_at)` of the loaded
rows - late-arriving rows with equal timestamps would otherwise be skipped.

### S6 / S7

**tSnowflakeCommit_1**: Component List `tSnowflakeConnection_1`, `Close Connection`
**unchecked** (tPostjob closes). **tJava_3**:
`System.out.println(jobName + " OK rows=" + globalMap.get("tSnowflakeOutput_1_NB_LINE") + " new watermark=" + globalMap.get("WM_HIGH_STR"));`

### Error path

| Component | Setting | Value |
|---|---|---|
| **tLogCatcher_1** | Catch Java Exception | checked; `Catch tDie` and `Catch tWarn` unchecked (otherwise the final tDie re-enters the catcher and you get a second mail) |
| **tJavaRow_3** | Code | `globalMap.put("ERR_TEXT", input_row.origin + ": " + input_row.message); output_row.message = input_row.message;` (any column copy; tJavaRow may be the last component of the flow) |
| **tSnowflakeRollback_1** | Component List / Close Connection | `tSnowflakeConnection_1` / unchecked |
| **tSendMail_1** | To / From | `context.ALERT_TO` / `context.ALERT_FROM` |
| | Subject | `"[" + context.ENV + "] " + jobName + " FAILED (pid " + pid + ")"` |
| | Message (MIME subtype plain) | `"Job: " + jobName + " v" + jobVersion + "\nEnv: " + context.ENV + "\nHost: " + java.net.InetAddress.getLocalHost().getHostName() + "\nWindow: (" + globalMap.get("WM_LOW_EFF_STR") + " , " + globalMap.get("WM_HIGH_STR") + "]\nError: " + globalMap.get("ERR_TEXT") + "\nRows attempted: " + globalMap.get("tSnowflakeOutput_1_NB_LINE") + "\nTransaction rolled back; watermark unchanged. Next scheduled run will retry the same window.\nSee TMC > Operations > Task runs for the log."` |
| | SMTP host / Port | `context.SMTP_HOST` / `context.SMTP_PORT` (587 + `STARTTLS support`, or 465 + `SSL support`) |
| | Need authentication | `context.SMTP_USER` / `context.SMTP_PASSWORD` (if your relay needs it; Office 365 basic SMTP auth is disabled - use an authenticated relay) |
| | Die on error | **unchecked** (an SMTP outage must not hide the real failure) |
| **tDie_1** | Error message | `"LOAD_ORDERS_INCR failed: " + globalMap.get("ERR_TEXT")` |
| | Error code | `4` (keep 1..255) |
| | Exit the JVM immediately | **unchecked** so tPostjob still closes the connections |

### tPostjob chain

**tSnowflakeClose_1** (Component List `tSnowflakeConnection_1`) then **tDBClose_1**
(`tDBConnection_1`). Closing an uncommitted Snowflake session also rolls it back, so even a
failure *inside* the error path cannot persist a half-run.

## 4. Context group `CTX_ORDERS_SF` (Repository > Contexts; import into the Job in Repository mode)

Contexts (columns): `Default` | `DEV` | `TEST` | `PROD`. Put **DEV values in `Default`** so a
forgotten context never hits PROD. Leave PROD passwords empty in the group and set them in the
TMC task Parameters (masked) - that keeps secrets out of the `.item` and the Git history.

| Variable | Type | Example / purpose |
|---|---|---|
| `ENV` | String | `DEV` / `TEST` / `PROD` - appears in mail subject |
| `JOB_KEY` | String | `LOAD_ORDERS_INCR` - `JOB_NAME` in `ETL_WATERMARK` |
| `PG_HOST`, `PG_PORT`, `PG_DB`, `PG_SCHEMA`, `PG_USER` | String, Integer, String, String, String | source connection |
| `PG_PASSWORD` | **Password** | masked in TMC and `Print Parameters` |
| `SF_ACCOUNT`, `SF_USER`, `SF_WAREHOUSE`, `SF_DATABASE`, `SF_SCHEMA`, `SF_ROLE` | String | target connection |
| `SF_PASSWORD` (or `SF_PRIVATE_KEY`, `SF_PRIVATE_KEY_PASSPHRASE`) | **Password** | |
| `SF_CTRL_SCHEMA` | String | `ETL_CTRL` |
| `SF_TARGET_TABLE` | String | `DWH.ORDERS` |
| `WM_OVERLAP_SEC` | Integer | `120` - re-read this much of the previous window |
| `WM_SAFETY_LAG_SEC` | Integer | `30` - upper bound = source `now()` minus this, so transactions still in flight at `now()` are not missed; raise it if the source has long-running write transactions |
| `WM_MAX_WINDOW_MIN` | Integer | `1440` - backlog chunk size |
| `FETCH_SIZE` | Integer | `5000` |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER` | String, Integer, String | relay |
| `SMTP_PASSWORD` | **Password** | |
| `ALERT_FROM`, `ALERT_TO` | String | `"etl-noreply@..."`, `"ops@..."` (comma-separated list) |

No `Date`-typed context variable is used on purpose: TMC passes every parameter as a string
and Date parsing (`yyyy-MM-dd HH:mm:ss`) is a classic start-up failure; the window lives in
globalMap as `java.util.Date`.

Also set: Job view > Main > `Purpose`/`Description`; Job view > `Extra` > nothing (no implicit
context load needed - TMC Parameters are the override mechanism); Project Settings > Log4j >
`Activate log4j in components` so the TMC `Log level` has an effect.

## 5. Deploy and schedule on a Remote Engine via TMC

1. **Studio: test, then publish.** Run with the `DEV` context from the Run view; check the
   console shows the window and a sane row count; run twice in a row and confirm the second
   run upserts the overlap only (no duplicates in `DWH.ORDERS`). Then right-click the Job >
   **`Publish to Cloud`**: pick the TMC *environment* and *workspace* (e.g. `DEV` /
   `Orders`), Artifact type `Standard Job`, `Publish as new version`. Studio must be logged in
   to Talend Cloud with the region-specific connection; if it is greyed out install the
   `Publish to Cloud` feature (Feature Manager) and check your TMC role. The artifact appears
   under **TMC > Management > Artifacts** with an auto-incremented version
   (`0.1.0.<timestamp>`).

2. **Remote Engine.** TMC > **Management > Engines > Add > Remote Engine**: name it, copy the
   **Pre-authorized key**. On the host: unzip `Talend-RemoteEngine-V2.x`, put the key and name
   in `etc/preauthorized.key.cfg` (`remote.engine.pre.authorized.key=...`,
   `remote.engine.name=...`), start `bin/start` (install as a systemd unit / Windows service).
   Status must show `Paired` and `Available`. Create a **Run profile** (Management > Run
   profiles) for it: `-Xms512m -Xmx2g -Duser.timezone=UTC -Dfile.encoding=UTF-8` - `UTC` is
   load-bearing here (section 6). Use a **Remote Engine Cluster** (2 engines) if you need
   failover; nothing in this design is engine-local, so the cluster is safe. A Cloud Engine is
   not an option: it cannot reach your PostgreSQL network.

3. **Task.** TMC > **Management > Tasks and plans > Add task** (or `Create task` from the
   artifact):
   - *Artifact*: `LOAD_ORDERS_INCR`, the published version (pin it in PROD; in DEV you may
     tick auto-upgrade to latest).
   - *Parameters*: the context variables are discovered from the artifact. Set the
     environment's values; `Password`-typed ones are masked. Set `ENV=PROD` etc.
   - *Processing*: Engine = your Remote Engine or cluster; Run profile = the one above;
     `Log level` = `Info`; `Timeout` = something generous (e.g. 120 min - see note below);
     **`Allow parallel run of this task` = off** so a slow run causes the next trigger to be
     skipped rather than two JVMs fighting over the same window.
   - *Schedule*: add a trigger with an explicit time zone (`UTC`): either `Daily` with
     "repeat every 15 minutes" between 00:00 and 23:45, or `CRON`. The TMC CRON dialog shows
     the next executions - use that preview to confirm the syntax your release expects
     (Quartz-style `0 0/15 * * * ?` with a seconds field, or 5-field `*/15 * * * *`). 15 min is
     well above TMC's 5-minute minimum spacing. Save; `Run now` once and read the run log
     (`Operations > Task runs` > run > `Logs`): you should see the window line from tJava_2
     and the summary from tJava_3.
   - Timeout vs backlog: TMC's `Timeout` kills the JVM, the Snowflake session dies and the
     transaction rolls back, so the watermark stays - correct but it means a tight timeout can
     make a backlog *never* catch up. `WM_MAX_WINDOW_MIN` bounds the work per run instead;
     keep the TMC timeout loose.

4. **Failure notification.** The Job emails ops itself (tSendMail). As a backstop that does
   not depend on the engine reaching SMTP, subscribe the ops users to task-failure
   notifications in TMC (user profile / Notifications: task execution failed, engine
   unavailable). The run shows `Execution failed` with the Job's exit code 4 and the tDie
   message in the log.

5. **Promotion.** TMC > Management > Environments > **Promotions**: `DEV -> TEST`,
   `TEST -> PROD`. Promote the artifact + task; engines are *not* promoted, so after the first
   promotion open the PROD task and set engine, run profile, schedule and parameters once. On
   later promotions choose the option that keeps the target task's parameter values so PROD
   passwords/hosts are not overwritten with DEV ones, and re-check the task after every
   promotion. Rollback = edit the task and pick the previous artifact version.

6. **Optional automation** (`scripts/tmc_api.py` from the skill, or curl with a service-account
   token): `tasks list --environment-id ...`, `tasks run <taskId> --wait` for a manual
   catch-up run, and `PUT /orchestration/executables/tasks/{taskId}/run-config` with
   `{"trigger":{"type":"CRON","timeZone":"UTC","cronExpression":"0 0/15 * * * ?"},"runtime":{"type":"REMOTE_ENGINE","id":"<engineId>"},"parallelExecutionAllowed":false,"logLevel":"INFO"}`;
   `GET .../run-config/events?limit=5` lists the next fire times to verify the expression.

## 6. How the watermark survives between runs (and why it is restartable)

**What a TMC run is.** Every trigger makes the Remote Engine fetch (or reuse its cached copy
of) the artifact, unpack it under its `TalendJobServersFiles` work area and start a **new
JVM** with `--context=Default --context_param K=V ...` built from the task Parameters.
globalMap, `context.*`, tHash buffers and anything in memory start empty each time; the Job
cannot modify the task's parameters; files written under the job folder are not guaranteed to
be there next time and are never shared across the engines of a cluster. So state must live
outside the Job - here, the `ETL_WATERMARK` row in Snowflake.

**Per run:**
1. S1 reads `LAST_WATERMARK` (the previous run's upper bound) - this is the only input that
   changes between runs.
2. S2 takes `now() - safety_lag` from PostgreSQL's clock (not the engine's).
3. S4 upserts rows with `updated_at` in `(LAST_WATERMARK - overlap, WM_HIGH]`.
4. S5 sets `LAST_WATERMARK = GREATEST(LAST_WATERMARK, WM_HIGH)` **on the same Snowflake
   connection, inside the same uncommitted transaction**.
5. S6 commits once. Only now do the data and the new watermark become visible - together.

**Failure cases:**

| Failure point | Effect | Next scheduled run |
|---|---|---|
| Cannot connect to PG or Snowflake, S1-S3 exception | nothing written, watermark unchanged, mail + exit 4 | retries the identical window |
| Mid-S4 (network blip, bad row, Snowflake error) | `OnSubjobError` -> rollback: upserted batches and the watermark are discarded | retries the identical window |
| Between S5 and S6 (JVM killed, TMC timeout, engine crash) | session dies, Snowflake rolls back the open transaction | retries the identical window |
| After S6 commit (tJava_3, tPostjob, SMTP) | data + watermark already consistent; run may show failed | moves on from the new watermark |
| Run skipped because the previous one is still running (`Allow parallel run` off) | nothing happens | next trigger processes a 30-minute window - no gap |
| Engine down for hours/days | triggers do not run | the first run back caps the window at `WM_MAX_WINDOW_MIN`; successive runs catch up chunk by chunk, each committing progress |

Idempotency comes from the `Upsert` on `ORDER_ID`: re-processing a window (overlap, rerun,
manual replay) rewrites the same rows. Missed-row protection comes from `WM_SAFETY_LAG_SEC`
(write transactions that were open at `now()` have an `updated_at` slightly in the past; the
lag keeps them inside the *next* window) and from the fact that the new watermark is the upper
bound, not the max loaded timestamp. If a source transaction can be open longer than the lag
(bulk back-office updates), raise the lag or the overlap - both are TMC parameters, no rebuild.

**Time zone contract.** PostgreSQL returns `timestamptz` instants; Snowflake stores
`TIMESTAMP_NTZ` which is zone-less; the JVM converts between the two via `java.util.Date` and
formats the watermark as text once (S5). Pinning `-Duser.timezone=UTC` in the Remote Engine
run profile makes every conversion UTC, so an engine replaced by one in another zone, or a
cluster spanning zones, cannot shift the watermark. Also give the TMC trigger an explicit
`UTC` zone so DST does not fire the task twice or skip it.

**Operations cookbook.**
- Replay from a point in time: `UPDATE ETL_CTRL.ETL_WATERMARK SET LAST_WATERMARK = '2026-10-17 00:00:00' WHERE JOB_NAME = 'LOAD_ORDERS_INCR';` then `Run now` in TMC (or wait for the trigger). Safe because of the upsert.
- Initial/full backfill: seed `LAST_WATERMARK` before the oldest order and let the capped window catch up, or run a one-off full-load Job and seed the watermark with that load's start time.
- Health check: `SELECT JOB_NAME, LAST_WATERMARK, LAST_RUN_AT, LAST_ROWS, DATEDIFF('minute', LAST_WATERMARK, CURRENT_TIMESTAMP()) AS lag_min FROM ETL_CTRL.ETL_WATERMARK;` - alert if `lag_min > 60`. Optional: add an `ETL_RUN_LOG` insert in S6/S7 (or enable Project Settings > Stats & Logs `On Databases`) for per-run history beyond TMC's log retention.
- Do **not** store the watermark in a file on the engine, in a context variable, or in the source database unless the target refuses writes - the single-transaction guarantee above only holds when the watermark and the data commit together.

## 7. Review checklist before PROD (skill scorecard, blockers only)

- Schema: every nullable PG column `Nullable`; `ORDER_ID` marked `Key` on the tMap output / tSnowflakeOutput schema; `order_total` as BigDecimal.
- Error handling: `Die on error` checked on tDBInput_2, tSnowflakeOutput_1, tSnowflakeRow_1; unchecked only on tSendMail_1; Job ends in tDie (exit 4) on any failure.
- Transactions: Auto Commit off on tSnowflakeConnection_1; exactly one tSnowflakeCommit, after the watermark UPDATE; rollback on error; `Close Connection` unchecked on commit/rollback, close in tPostjob.
- Secrets: all passwords typed `Password`; PROD values only in TMC task Parameters; `Default` context = DEV.
- No `tLogRow` left in the main flow (three `System.out` lines per run are fine).
- Build/runtime: Java 17 on the engine, run profile with `-Duser.timezone=UTC`, `Allow parallel run` off, trigger time zone explicit, task pinned to a version in PROD.
