# Talend patterns, performance tuning and troubleshooting playbook

> Verification: doc-derived (help.qlik.com / help.talend.com search snippets, Talend GitHub, Maven Central) plus model knowledge. Not exercised against a live Studio/TAC/TMC in this build. Items marked (unverified) are from memory only and should be checked in Studio before relying on exact labels.

Scope: Standard (DI) jobs first; Spark and ESB pointers at the end. Component
parameter catalogs live in components-core.md / tmap-expressions.md; this file is
about how to assemble, tune, review and debug real jobs. Diagram notation:
`tA_1 --row1(Main)--> tB_1`, `--Iterate-->`, `--OnSubjobOk-->`, `--OnComponentError-->`,
`--lookup-->` (tMap lookup input), `--reject-->`.

## Contents

- [1. Job architecture patterns](#1-job-architecture-patterns)
  - [1.1 Orchestrator job and tRunJob children](#11-orchestrator-job-and-trunjob-children)
  - [1.2 Subjob layout rules](#12-subjob-layout-rules)
  - [1.3 Naming conventions](#13-naming-conventions)
  - [1.4 Repository folder organization by layer](#14-repository-folder-organization-by-layer)
  - [1.5 Joblets](#15-joblets)
  - [1.6 Reference projects](#16-reference-projects)
  - [1.7 Generic jobs: Dynamic schema and dynamic tRunJob](#17-generic-jobs-dynamic-schema-and-dynamic-trunjob)
- [2. Load and transformation patterns](#2-load-and-transformation-patterns)
  - [2.1 Full load (truncate and insert)](#21-full-load-truncate-and-insert)
  - [2.2 Incremental load by watermark](#22-incremental-load-by-watermark)
  - [2.3 Upsert](#23-upsert)
  - [2.4 Delete detection](#24-delete-detection)
  - [2.5 Slowly changing dimensions](#25-slowly-changing-dimensions)
  - [2.6 Change data capture](#26-change-data-capture)
  - [2.7 Bulk loading](#27-bulk-loading)
  - [2.8 ELT pushdown](#28-elt-pushdown)
  - [2.9 Lookups](#29-lookups)
  - [2.10 Deduplication](#210-deduplication)
  - [2.11 Pivot, unpivot, aggregation](#211-pivot-unpivot-aggregation)
  - [2.12 File ingestion](#212-file-ingestion)
  - [2.13 File generation](#213-file-generation)
  - [2.14 XML and JSON shaping](#214-xml-and-json-shaping)
  - [2.15 REST API pagination](#215-rest-api-pagination)
  - [2.16 Email and alerting](#216-email-and-alerting)
  - [2.17 Control tables and audit](#217-control-tables-and-audit)
  - [2.18 Restartability](#218-restartability)
  - [2.19 Parallelism and thread safety](#219-parallelism-and-thread-safety)
  - [2.20 Scheduling patterns](#220-scheduling-patterns)
  - [2.21 Environments, contexts and secrets](#221-environments-contexts-and-secrets)
  - [2.22 Logging](#222-logging)
  - [2.23 Unit testing](#223-unit-testing)
  - [2.24 Code review checklist](#224-code-review-checklist)
- [3. Performance tuning](#3-performance-tuning)
- [4. Troubleshooting index](#4-troubleshooting-index)
- [5. Design review scorecard](#5-design-review-scorecard)
- [6. Template: explain a Talend job](#6-template-explain-a-talend-job)
- [7. Procedure: generate a job from a spec](#7-procedure-generate-a-job-from-a-spec)
- [8. Spark and ESB pointers](#8-spark-and-esb-pointers)
- [Gotchas](#gotchas)
- [Sources](#sources)

## 1. Job architecture patterns

### 1.1 Orchestrator job and tRunJob children

```
ORCH_DAILY_SALES
  tPrejob_1 --OnComponentOk--> tDBConnection_ctl
  tRunJob_extract (LOAD_STG_ORDERS)   --OnSubjobOk--> tRunJob_dim (LOAD_DIM_CUSTOMER)
                                      --OnSubjobOk--> tRunJob_fact (LOAD_FACT_SALES)
  tRunJob_extract --OnSubjobError--> tSendMail_fail --OnComponentOk--> tDie_1
  tPostjob_1 --OnComponentOk--> tDBClose_ctl
```

| Concern | Setting / pattern | Notes |
|---|---|---|
| Pass all context | tRunJob Basic settings: check `Transmit whole context` | Child receives every parent context value whose name matches; unmatched child vars keep their own defaults. Uncheck and fill the `Context Param` table to pass a subset or rename. |
| Choose child context group | `Context` drop-down on tRunJob (e.g. `Default`, `PROD`) | Normally leave `Default` and let the parent `--context=PROD` flow through via Transmit whole context. |
| Memory isolation | `Use an independent process to run subJob` | Child runs in its own JVM (`java -cp ...`); frees parent heap after child ends; globalMap / tHash / tBuffer NOT shared; add extra class paths in the adjacent field (`;` on Windows, `:` on Linux). Not compatible with JobServer job cache. |
| Failure propagation | `Die on child error` (checked by default) | Checked: parent throws and OnSubjobError/OnComponentError fire. Unchecked: parent continues; test `((Integer)globalMap.get("tRunJob_1_CHILD_RETURN_CODE")) != 0` on a `Run if` trigger. |
| Exit codes | Child `tDie` `Error code` (default 4); uncaught exception = 1; success = 0 | The orchestrator's own exit code is what TAC/TMC/cron sees. Re-raise with a parent tDie whose code copies `CHILD_RETURN_CODE`. |
| Child stack trace | `((String)globalMap.get("tRunJob_1_CHILD_EXCEPTION_STACKTRACE"))` | Only populated when Die on child error is unchecked (unverified: exact name, check Outline view). |
| Return rows to parent | Child `tBufferOutput`; parent tRunJob has an outgoing `Main` row; check `Copy Child Job Schema` | Whole buffer kept in memory until child ends. Fine for a few thousand rows, not for data volumes. |
| Debug parameters | `Print Parameters` | Dumps the child context to stdout at start. Disable in PROD if contexts hold secrets (Password type values print masked in 7.3+/8, but verify). |
| Child version | `Version` drop-down, prefer `Latest` | Pinning a version freezes the child even after you edit it; `Latest` is resolved at build time, not at run time. |

Rules: one orchestrator per schedulable unit; children are self-contained (own
tPrejob/tPostjob, own connections) so they can also be run alone; never let a
child depend on parent tHash/globalMap unless both run in the same JVM AND you
accept the coupling; keep orchestrators free of tMap logic.

### 1.2 Subjob layout rules

- One logical step per subjob (one input chain -> one or more outputs). Chain
  subjobs with `OnSubjobOk` from the subjob's start component, never with
  `OnComponentOk` from a mid-flow component (fires before the flow finished for
  downstream components).
- `tPrejob` --OnComponentOk--> connections (`tDBConnection_*`, `tFTPConnection`,
  `tSetKeystore`), context fixes (`tJava`: derive paths, `System.getenv`), run id
  (`tSetGlobalVar`). tPrejob runs before everything else; a failure here aborts.
- `tPostjob` --OnComponentOk--> `tDBClose_*`, `tFileDelete` temp files,
  `tFTPClose`. tPostjob runs even if the main flow fails (so it is the only safe
  place for cleanup), but NOT if a tDie executed with `Exit the JVM immediately`
  (unverified label; default tDie lets tPostjob run).
- Error handling: `OnSubjobError` from the subjob start component -> `tDie` or
  alert chain. A separate always-present subjob `tLogCatcher_1 --row--> tDBOutput_log`
  catches tDie/tWarn/Java exceptions across the whole job.
- Transactions: `tDBConnection` (Auto Commit unchecked) -> all tDBOutput with
  `Use an existing connection` -> `tDBCommit` on `OnSubjobOk`, `tDBRollback` on
  `OnSubjobError`. One tDBCommit per connection; check `Close Connection` only on
  the last one, or close in tPostjob.
- Max ~10 subjobs per job canvas; beyond that split into children.

```
tPrejob_1 --OnComponentOk--> tDBConnection_dwh
tFileList_1 --Iterate--> tFileInputDelimited_1 --row1(Main)--> tMap_1 --out1--> tDBOutput_1
tFileList_1 --OnSubjobOk--> tDBCommit_1
tFileList_1 --OnSubjobError--> tDBRollback_1 --OnComponentOk--> tDie_1
tPostjob_1 --OnComponentOk--> tDBClose_1
tLogCatcher_1 --row2(Main)--> tDBOutput_log
```

### 1.3 Naming conventions

| Object | Convention | Example | Why |
|---|---|---|---|
| Job | `UPPER_SNAKE`, verb + layer + entity | `LOAD_DIM_CUSTOMER`, `EXTRACT_SAP_BKPF`, `ORCH_DAILY_FINANCE` | Job names must be unique project-wide (not per folder), letters/digits/underscore only, cannot start with a digit; become Java class names. |
| Component | keep the generated `tType_N` prefix, add a suffix via `Label format` (Component view > View tab) `__UNIQUE_NAME__ : purpose` or rename to `tDBInput_customers` | `tDBOutput_dim_customer` | Globals use the UNIQUE NAME (`tDBOutput_dim_customer_NB_LINE`); renaming after the fact breaks tJava code that references the old name. |
| Flow (row) | `row_<content>` or `<src>_<tgt>` | `row_customers`, `lkp_country` for lookups, `rej_customers` for rejects | Flow names become Java variable names in tMap expressions and tJavaRow (`row_customers.id`). |
| Context var | `UPPER_SNAKE` for environment-ish values, `camelCase` for runtime values; pick one per project | `DB_HOST`, `DB_PASS` (Password type), `LAST_RUN`, `fileDate` | Java identifier rules; context group name e.g. `CTX_DWH`. |
| Context group / env | one group per connection or domain, values per environment `DEV`/`TEST`/`PROD` inside the group | `CTX_DWH` with contexts Default, DEV, TEST, PROD | Environment is the context NAME, not a variable. |
| Routine | `PascalCase` class, static methods | `DateUtils.toIsoDate()` | Routines are classes under `routines/`. |
| Joblet | `JL_<purpose>` | `JL_AUDIT_START`, `JL_ARCHIVE_FILE` | Shows up in the palette under Joblets. |
| Metadata | `<system>_<object>` | `DWH_PG`, `SAP_PRD`, schema `stg_orders` | Repository > Metadata > Db Connections / File delimited. |

### 1.4 Repository folder organization by layer

```
Job Designs/
  00_orchestrate/   ORCH_DAILY_*, ORCH_HOURLY_*         (tRunJob only)
  10_ingest/        EXTRACT_<SRC>_<OBJ>                 (source -> landing files / stg tables)
  20_stage/         LOAD_STG_<OBJ>                      (typing, dedup, rejects)
  30_transform/     BUILD_<SUBJECT>                     (business rules, SCD)
  40_load/          LOAD_DIM_*, LOAD_FACT_*             (targets)
  90_utils/         UTIL_*, maintenance, one-offs
Joblets/            JL_*
Contexts/           CTX_*
Code/Routines/      <Project>Utils, DateUtils
Metadata/           Db Connections, File delimited, Generic schemas (shared stg schemas)
```

Use Generic schemas (Metadata > Generic schemas) for layouts shared by several
jobs; a schema change then propagates on `Repository` mode schemas (a yellow
prompt asks to propagate). Keep `Built-in` schemas only for throwaway jobs.

### 1.5 Joblets

| Item | Detail |
|---|---|
| Create | Repository > Joblet Designs > Create Joblet, or select components in a job > right-click > `Refactor to Joblet` (unverified label; 7.x shows "Create Joblet from selection"). |
| Data ports | `INPUT` and `OUTPUT` joblet components (one or more each); schema defined on them. |
| Trigger ports | `TRIGGER_INPUT` / `TRIGGER_OUTPUT` joblet components so the joblet can be chained with OnSubjobOk/OnComponentOk in the host job. |
| Context | Joblet has its own context variables; when dropped into a job, its variables are added to the job's context (same names). A joblet reads `context.X` of the host job at run time. |
| Runtime | Inlined into the host job's generated Java: same JVM, same `globalMap`, same connections. Component unique names inside the joblet get the joblet instance as prefix. |
| Versioning | The host job compiles the joblet version selected at build time; rebuild hosts after changing the joblet. |
| Good uses | audit start/end block, file archive block, standard error mail, connection setup. Avoid putting tDBConnection inside a joblet used twice in one job (duplicate connection names). |

### 1.6 Reference projects

Enterprise only. TAC > Projects > `Project references` (or Studio 8 Project
Settings > `Project References` with Git) makes project B's routines, metadata,
context groups, joblets and jobs visible read-only in project A (`Referenced
Projects` node in the Repository). Put shared routines, generic schemas, standard
joblets and context groups there; branch/tag the reference project so consumers
pin a version (reference projects are branch-aware). Jobs in a reference project
can be called by tRunJob from the consumer.

### 1.7 Generic jobs: Dynamic schema and dynamic tRunJob

Dynamic schema (Enterprise): set a column type `Dynamic` as the LAST column of the
schema (only one allowed). Supported by tDBInput/tDBOutput, tFileInputDelimited /
tFileOutputDelimited, tLogRow, tMap (pass-through of the dynamic column, no
per-field expressions), tJavaRow (`row1.dyn.getColumnCount()`,
`row1.dyn.getColumnMetadata(i).getName()`, `row1.dyn.getColumnValue(i)`),
tFilterColumns, tReplicate, tUnite, tFileInputPositional (unverified list).

```
tDBInput_src (Query: "SELECT * FROM " + context.TABLE, schema: [dyn: Dynamic])
  --row1--> tDBOutput_tgt (Table: context.TABLE, Action on table: Create table if does not exist,
                           Action on data: Insert, schema [dyn: Dynamic])
```

Limits: no column-level transformation; types are inferred from the source
metadata (DB) or all String (files); `Action on table: Create table` with a
Dynamic column maps types via the DB-specific mapping file (Window > Preferences
> Talend > Specific Settings > Metadata of TalendType). Performance roughly equal
to static schema for DB-to-DB copies.

Dynamic tRunJob: check `Use dynamic job`; the `Context job` field becomes an
expression (`context.CHILD_JOB`), and a list of candidate child jobs must be
entered so all of them are compiled into the build. Removes the `Context` and
`Use an independent process` options; incompatible with JobServer cache.

Other generic-job tools: `Dynamic settings` tab on components (bind a parameter
such as `Die on error` or a connection to a context/global expression), tDBRow
with `context.SQL`, tJavaFlex for schema-agnostic code, `Metadata > Generic
schemas` plus `tSchemaComplianceCheck` for validation.

## 2. Load and transformation patterns

### 2.1 Full load (truncate and insert)

```
tDBInput_src --row1--> tMap_1 --out1--> tDBOutput_tgt
   tDBOutput_tgt: Action on table = Truncate table (or Clear table), Action on data = Insert,
   Use Batch Size = checked (1000-10000), Commit every = 10000 (or Use an existing connection)
```

| Choice | Notes |
|---|---|
| `Truncate table` vs `Clear table` | Truncate is DDL (implicit commit on Oracle, cannot roll back, resets identity on MSSQL); Clear is `DELETE FROM` (logged, slow, rollbackable). |
| Blast-radius | Truncate happens when the component initializes, i.e. before the first row arrives; a source failure leaves an empty target. Prefer load-to-staging then swap (`ALTER TABLE ... RENAME` in tDBRow) or truncate inside the same transaction (Clear + tDBCommit) when the DB supports transactional DDL (PostgreSQL does; Oracle/MySQL do not). |
| `Drop table if exists and create` | Recreates with Talend's type mapping; loses indexes, grants, constraints. Avoid in PROD. |
| Indexes | Drop or disable before bulk insert, rebuild after (tDBRow before/after via OnSubjobOk). |

### 2.2 Incremental load by watermark

```
tDBInput_ctl ("SELECT last_run FROM etl_control WHERE job_name='" + jobName + "'")
   --row1--> tFlowToIterate_1 (or tSetGlobalVar / tJavaRow: context.LAST_RUN = row1.last_run)
tFlowToIterate_1 --Iterate--> tDBInput_src (Query below) --row2--> tMap --> tDBOutput_tgt
tDBInput_src --OnSubjobOk--> tDBRow_ctl ("UPDATE etl_control SET last_run = ? WHERE job_name = ?",
                                        Use PreparedStatement, params = new watermark)
```

Query expression (Date context var):

```java
"SELECT * FROM orders WHERE updated_at > TO_TIMESTAMP('"
  + TalendDate.formatDate("yyyy-MM-dd HH:mm:ss", context.LAST_RUN)
  + "', 'YYYY-MM-DD HH24:MI:SS') AND updated_at <= TO_TIMESTAMP('"
  + TalendDate.formatDate("yyyy-MM-dd HH:mm:ss", (java.util.Date)globalMap.get("RUN_START"))
  + "', 'YYYY-MM-DD HH24:MI:SS')"
```

Rules: capture `RUN_START` once in tPrejob (`tSetGlobalVar` RUN_START =
`TalendDate.getCurrentDate()`) and use it as the upper bound AND as the new
watermark; never use `MAX(updated_at)` of loaded rows alone (late-arriving rows
with equal timestamps are skipped) - use `>=` plus dedup, or subtract an overlap
window (`TalendDate.addDate(context.LAST_RUN, -1, "HH")`) and make the load an
upsert. Write the new watermark only after the target commit succeeded (same
transaction or after tDBCommit). Prefer a numeric/sequence watermark when
available (`id > ?`) over timestamps. Use `Use PreparedStatement` on tDBRow to
avoid date formatting issues. In Talend 8, context vars of type Date in a
`.properties` context file are parsed from the pattern `yyyy-MM-dd HH:mm:ss`
(unverified: check `ParserUtils`).

### 2.3 Upsert

| Option | Where | Behaviour | Cost |
|---|---|---|---|
| `Insert or update` | tDBOutput Action on data | Per row: checks existence (SELECT by key, or INSERT then fallback depending on DB), then INSERT or UPDATE. Batch disabled. | 2 round trips per row; slow beyond ~100k rows. |
| `Update or insert` | tDBOutput | Per row: UPDATE first, INSERT if 0 rows affected. Batch disabled. | Faster when most rows exist. |
| Native upsert | tDBOutput MySQL `Replace` / `Insert Ignore` (unverified for 8.0 generic tDBOutput; present on tMysqlOutput); `Additional Columns` + `ON DUPLICATE KEY` not configurable | `REPLACE` deletes+inserts (fires delete triggers, resets other columns). | Batchable. |
| Staging + MERGE | tDBOutput Insert into `stg_x` (batch, truncate first) --OnSubjobOk--> tDBRow `MERGE INTO dim_x USING stg_x ON (...) WHEN MATCHED ... WHEN NOT MATCHED ...` (Oracle/MSSQL/Snowflake/Postgres 15+; `INSERT ... ON CONFLICT DO UPDATE` Postgres; `INSERT ... ON DUPLICATE KEY UPDATE` MySQL) | Set-based in the DB. | Fastest; recommended default for > 50k rows. |
| tELTOutput | ELT family | `Action on data` Insert/Update/Delete, generates SQL; no native MERGE (unverified for 8.0; tELTMap has no merge). | Pushdown. |
| tDBSCD type 1 | SCD component | Type 1 columns overwrite in place. | Row-by-row. |

Key management: tDBOutput uses the schema `Key` checkbox for UPDATE/DELETE WHERE
clauses. For a different update key than the table PK, Advanced settings > `Use
field options` -> per column `Key`, `Updatable`, `Insertable`. `Update`/`Delete`
require at least one key column or the component fails at generation.

### 2.4 Delete detection

```
tDBInput_tgt_keys ("SELECT business_key FROM dim_x WHERE is_deleted = 0") --row1(Main)--> tMap_1
tDBInput_src_keys ("SELECT business_key FROM src")                        --lookup--> tMap_1
   tMap_1: join on business_key, Join Model = Inner Join, Match Model = Unique match,
           output `deleted` = "Catch lookup inner join reject" = true
tMap_1 --deleted--> tDBOutput_tgt (Action on data: Update, column is_deleted = 1 / deleted_at)
```

Make the TARGET the main flow and the SOURCE the lookup when the source is
smaller, otherwise swap and use `tMap` output with inner-join reject the other
way, or do it set-based: load source keys into `stg_keys` then tDBRow
`UPDATE dim_x SET is_deleted=1 WHERE business_key NOT IN (SELECT business_key FROM stg_keys)`.
Never run delete detection on an incremental (watermarked) extract: it only sees
changed rows.

### 2.5 Slowly changing dimensions

tDBSCD (and per-DB `tOracleSCD`, `tMysqlSCD`, ELT variants `tDB2SCDELT`,
`tOracleSCDELT`...). Open the `SCD Editor`:

| Panel | Setting |
|---|---|
| Unused / Source keys | drag business key column(s) to `Source keys`. |
| Surrogate keys | `name` of the surrogate column; `creation` = `Auto-increment` (DB identity), `Input field`, `Routine` (e.g. `Numeric.sequence("s1",1,1)`), `Table max + 1`, `DB sequence` (name). |
| Type 0 fields | ignored changes. |
| Type 1 fields | overwrite in place. |
| Type 2 fields | new version row on change; set `start` and `end` date columns (`SCD_START`, `SCD_END`), `Versioning`: `version` column (integer increments) and `active` flag (true/false) checkboxes. |
| Type 3 fields | `current` and `previous` value columns. |

tDBSCD rules: it reads the whole current dimension into memory at start (fits
small/medium dimensions, tens of millions of rows will not); one row at a time
to the DB (no batch); requires `Use an existing connection` for transactional
behaviour; end date for the closed version is set to the processing timestamp
(no business effective date) unless you precompute it; type 2 detection compares
all Type 2 columns as strings/objects - trim and normalize before the component.
Alternative manual approach for large or custom dimensions:

```
src --row1--> tMap_scd <--lookup-- tDBInput_dim_current ("... WHERE is_current = 1")
   tMap_scd: Left Outer Join on business_key, Unique match
     out_insert_new   : filter lookup.sk == null                       -> tDBOutput Insert (new sk)
     out_close_old    : filter lookup.sk != null && changed(Type2 cols) -> tDBOutput Update (is_current=0, end_dt)
     out_insert_ver   : same filter                                    -> tDBOutput Insert (new version)
     out_type1        : filter only Type1 cols differ                  -> tDBOutput Update
   changed(): Var.hash_src = MD5 of concatenated Type2 cols vs dim.row_hash (store a hash column)
```

Use a staging table + SQL MERGE/INSERT for very large dims (ELT); keep a
`row_hash` column to avoid comparing 30 columns in expressions.

### 2.6 Change data capture

| Approach | Components / product | Notes |
|---|---|---|
| Talend trigger-based CDC (Studio, Enterprise) | Repository > Metadata > Db Connections > right-click > `CDC` (create CDC connection, `Create CDC` on a table, add `Subscriber`), then `tDBCDC` (`tOracleCDC`, `tMysqlCDC`, `tMSSqlCDC`, `tPostgresqlCDC`, `tDB2CDC`, `tAS400CDC`, `tInformixCDC`, `tSybaseCDC`, `tTeradataCDC`) | Modes: `Trigger mode` (Talend creates `TCDC_<table>` change tables + triggers in a CDC schema), `Redo/Archive log mode` (Oracle only, via LogMiner / Streams, deprecated), `XStream mode` (Oracle, unverified availability in 8.0). tDBCDC reads changes for one `Subscriber`; events `TALEND_CDC_TYPE` = I/U/D, `TALEND_CDC_SUBSCRIBERS_NAME`, `TALEND_CDC_STATE`; `Keep data in CDC table` unchecked consumes (deletes) them after read. Triggers add write load on the source; DBAs often refuse. Each subscriber gets its own view of the change table. |
| Log-based alternative | Qlik Replicate, "Talend Change Data Capture" (ex Gamma Soft, bundled with Data Fabric 7.x-8.x as a separate product), Debezium/Kafka | Reads redo/WAL/binlog without triggers; Talend jobs then consume Kafka (`tKafkaInput`) or landing tables. Prefer for high-volume OLTP sources. |
| Timestamp/version columns | see 2.2 | Cheapest, misses hard deletes. |
| Full compare | see 2.4 plus tMap compare of hashes | Expensive but source-agnostic. |

### 2.7 Bulk loading

Pattern is always: write a flat file (local or object storage) -> run the DB's
native loader. `*OutputBulk` writes the file, `*BulkExec` loads it,
`*OutputBulkExec` does both in one component.

| Target | Components | Mechanism / requirement |
|---|---|---|
| MySQL / MariaDB | `tMysqlOutputBulk` + `tMysqlBulkExec` or `tMysqlOutputBulkExec` | `LOAD DATA [LOCAL] INFILE`; needs `local_infile=1` on server and `allowLoadLocalInfile=true` in Additional JDBC Parameters for LOCAL. |
| PostgreSQL | `tPostgresqlOutputBulk` + `tPostgresqlBulkExec` | `COPY ... FROM` via JDBC CopyManager (file read by the job machine) (unverified mechanism; older versions needed the file on the DB server). |
| Oracle | `tOracleOutputBulk` + `tOracleBulkExec` / `tOracleOutputBulkExec` | Generates a `.ctl` and runs `sqlldr` (Oracle client must be installed on the job machine, `Oracle sqlldr path` setting). Direct path options in Advanced settings (unverified labels). |
| SQL Server | `tMSSqlOutputBulk` + `tMSSqlBulkExec` | `BULK INSERT` - the file path is read BY THE SQL SERVER, so the file must be on a share visible to the DB. Alternative: tMSSqlOutput `Use Batch Size` + Additional JDBC param `useBulkCopyForBatchInsert=true` (MS JDBC 7.2+). |
| Snowflake | `tSnowflakeOutputBulk` + `tSnowflakeBulkExec`, `tSnowflakeOutputBulkExec` | File to internal stage (`PUT`) or S3/Azure/GCS external stage, then `COPY INTO`; options `Storage` (Internal/S3/Azure/Google), `Stage Folder`, `Table action`, `Data file format` (CSV compressed). tSnowflakeOutput alone also stages+COPY internally in batches (`Use Custom Stage Path` unverified). Column names are upper-cased unless quoted. |
| Redshift | `tRedshiftOutputBulk` (to S3) + `tRedshiftBulkExec` (`COPY FROM 's3://...'`) or `tRedshiftOutputBulkExec` | Needs IAM/keys with S3 read, same region recommended; `COPY` options (delimiter, `IGNOREHEADER`, `GZIP`). |
| BigQuery | `tBigQueryOutput` (writes to GCS bucket then loads) / `tBigQueryBulkExec` | Needs a GCS bucket and service account JSON; set `Location`. |
| Teradata | `tTeradataFastLoad`, `tTeradataMultiLoad`, `tTeradataTPump`, `tTeradataFastExport` | TTU utilities on job machine. |
| DB2 | `tDB2BulkExec` (`LOAD`), Netezza `tNetezzaBulkExec`, Vertica `tVerticaOutput` with `COPY` mode, Greenplum `gpload` | Vendor tooling required. |
| Generic JDBC | none | Use tDBOutput batch + staging table. |

Design rules: generate the file with the exact `Field separator`, `Encoding`,
null representation and date format the loader expects (set `Null string` /
`Row separator` identically on both components); gzip when crossing a network;
load into a staging table then `MERGE`/`INSERT SELECT`; bulk loaders ignore
`Commit every` and triggers behave differently (MySQL LOAD DATA fires triggers,
Oracle direct path does not fire them).

### 2.8 ELT pushdown

```
tELTInput_orders (Table name "orders", schema cols) --orders--> tELTMap_1 --out--> tELTOutput_stg_orders
tELTInput_customers                                  --customers--> tELTMap_1
   tELTMap_1: drag tables, define join (INNER/LEFT OUTER), WHERE clause, expressions with DB SQL functions
   tELTOutput_stg_orders: Action on data = Insert (INSERT INTO ... SELECT), Table name, schema
```

- Components are DB-specific: `tELTOracleInput/Map/Output`, `tELTMysql*`,
  `tELTPostgresql*`, `tELTMSSql*`, `tELTTeradata*`, `tELTNetezza*`, `tELTVertica*`,
  `tELTGreenplum*`, `tELTHive*`, plus generic `tELTInput/tELTMap/tELTOutput` (8.0,
  JDBC-generic; unverified exact name set). The whole chain executes ONE SQL
  statement in the DB; no rows flow through Java.
- Table names are expressions: `context.SCHEMA + ".orders"`; mark `Use different
  table name` on tELTOutput when target differs from schema name.
- tELTMap expression editor is SQL, not Java: `UPPER(orders.name)`,
  `NVL(c.region,'NA')`; the tELTMap `Generated SQL Select query` tab shows the
  statement for review.
- Alternative pushdown: `tDBRow` with `Use PreparedStatement` or a parameterized
  string; `tDBRow` returns no rows unless `Propagate QUERY's recordset` is set
  (then read with `tParseRecordSet`). Use `tDBSP` for stored procedures.
- Use ELT when both sides live in the same DB and data > a few million rows;
  use Standard when you need Java routines, cross-system joins, rejects per row
  or data quality components.

### 2.9 Lookups

```
tDBInput_main --row1(Main)--> tMap_1 --out1--> tDBOutput_1
tDBInput_country --lkp_country(Lookup)--> tMap_1
```

| Setting (tMap, click the lookup table header) | Values | Use |
|---|---|---|
| `Lookup Model` | `Load once` (default), `Reload at each row`, `Reload at each row (cache)` | Load once: whole lookup read into memory before main rows flow. Reload at each row: lookup query re-executed per main row; use with a `globalMap` key set in the main flow (`Expr. key` section in tMap, tDBInput query `"... WHERE id = " + globalMap.get("cur_id")`) when the lookup table is huge and the main flow small. `(cache)` keeps already-fetched keys; cannot be combined with `Store temp data`. |
| `Match Model` | `Unique match` (default, returns the LAST matching row), `First match`, `All matches` (one output row per match = fan-out) | Duplicate output rows almost always mean `All matches` or duplicate lookup keys. |
| `Join Model` | `Inner Join`, `Left Outer Join` | Inner join rejects are captured by setting `Catch lookup inner join reject` = true on an output table. |
| `Store temp data` | true/false + `Temp data directory path` (tMap Basic settings, also `Max buffer size (nb of rows)`, default 2,000,000) | Spills lookup data to disk files; 5-20x slower than in-memory but survives big lookups. |
| `Lookup in parallel` | tMap Advanced settings (unverified label) | Loads several lookups concurrently. |

Alternatives: `tDBInput` lookup with a WHERE on keys from the main flow (via
Reload at each row); `tHashOutput` (fill once in a first subjob) +
`tHashInput` as lookup in later subjobs (same JVM, keyed by `Link with a
tHashOutput`; `tHashOutput` option `Append` accumulates across iterations,
`tHashInput` `Clear cache after reading` frees memory); `tJoin` for a simple
single-key inner/left join with rejects (`Include lookup columns in output`);
`tDBLookupInput`? no such thing - use tMap Reload; DB-side join/ELT when both
sides are in the DB.

Memory budget: in-memory lookup size ~= rows x (sum of column bytes + ~16
bytes per object + ~40 per String + ~32 per map entry) ~= rows x avg raw row
bytes x 3. A 10M-row lookup of 100 raw bytes needs ~3 GB heap. Keep only the
columns you use (lookup schema can be narrower than the table) and filter the
lookup query (`WHERE active = 1`).

### 2.10 Deduplication

| Component / pattern | How | Memory | When |
|---|---|---|---|
| `tUniqRow` | tick `Key attribute` per column (optionally `Case sensitive`); outputs `Uniques` and `Duplicates`; keeps the FIRST occurrence | Hash of keys in memory; Advanced `Use of disk (suitable for processing large row set)` with `Buffer size in memory` + `Directory for temp files` | Default choice. |
| `tAggregateRow` | Group by key, operations `first`/`last`/`max` on other columns | Full groups in memory (all keys) | When you need "latest record per key" by a sort column: `tSortRow` (key asc, updated_at desc) then `tAggregateRow` first. |
| `tAggregateSortedRow` | Same but requires sorted input and exact `Input rows count` (`((Integer)globalMap.get("tSortRow_1_NB_LINE"))`) | Streaming, tiny memory | Very large sorted inputs. |
| `tSortRow` + tMap previous-row vars | tMap Var table evaluated top to bottom; `Var.isDup = row1.key.equals(Var.prevKey)` placed ABOVE `Var.prevKey = row1.key` sees the previous row's key; filter outputs on `!Var.isDup` | O(1) | Custom "first of group" logic with side computations. |
| DB side | `ROW_NUMBER() OVER (PARTITION BY key ORDER BY ts DESC) = 1` in tDBInput query or tELTMap | DB | Preferred when source is a DB. |
| `tDBOutput` `Insert Ignore`/`Replace` (MySQL) or `Insert or update` | Lets the DB enforce uniqueness | - | Small volumes. |

### 2.11 Pivot, unpivot, aggregation

| Need | Component | Key settings |
|---|---|---|
| Unpivot (one row -> many rows, e.g. `tags = "a;b;c"`) | `tNormalize` | `Column to normalize`, `Item separator` `";"`, Advanced `Use CSV parameters`, `Discard the trailing empty strings`, `Trim resulting values`. |
| Pivot (many rows -> one delimited cell) | `tDenormalize` | `To denormalize` column(s) with `Delimiter`, `Merge same value`; input must be grouped (sort first). |
| Pivot to columns (rows -> fixed columns) | `tPivotToColumnsDelimited` | `Pivot column`, `Aggregation column`, `Aggregation function` (first/last/count/sum/min/max...), `Group by`; writes a FILE (no output flow): read it back with tFileInputDelimited. For in-flow pivot with a known column set use tMap with `tAggregateRow` (`Group by` key, operations `max(CASE)` style via tMap pre-computed columns). |
| Columns -> rows (unpivot fixed columns) | `tSplitRow` | `Columns mapping`: one row per mapping line of expressions. |
| Aggregation | `tAggregateRow` | `Group by` (output col <- input col), `Operations`: `count`, `count(distinct)`, `sum`, `avg`, `min`, `max`, `first`, `last`, `list`, `list(object)`, `std dev`; Advanced `Delimiter(only for list operation)`, `Use financial precision, this is the max precision for "sum" and "avg" operations` (BigDecimal), `Check type overflow (slower)`, `Check ULP (Unit in the Last Place), ensure that a value will be incremented or decremented correctly, only for float and double`. Memory: one entry per distinct group key. |
| Streaming aggregation | `tAggregateSortedRow` | input sorted by group key; `Input rows count` mandatory. |
| Running totals / rank | tMap Var (`Var.total = Var.total + row1.amt` with `Var.total` declared Double initialised via `Relational.ISNULL`) or `tMemorizeRows` (keeps last N rows: `row1_tMemorizeRows_1[1]` arrays) | - |
| Dynamic column pivot (unknown values) | SQL in DB (`PIVOT`, `crosstab`) or tJavaFlex with Dynamic schema | - |

### 2.12 File ingestion

```
tFileList_1 (Directory context.IN_DIR, Files mask "orders_*.csv", Use Glob Expressions as Filemask,
             Case Sensitive = No, Order by = By file name, Order action = ASC)
  --Iterate--> tFileInputDelimited_1 (File name ((String)globalMap.get("tFileList_1_CURRENT_FILEPATH")),
               Row Separator "\n", Field Separator ";", CSV options checked, Header 1, Footer 0,
               Encoding "UTF-8", Die on error unchecked, Advanced: Trim all columns, Check each row structure against schema)
  --row1(Main)--> tMap_1 --out1--> tDBOutput_stg
  tFileInputDelimited_1 --reject--> tFileOutputDelimited_rej (context.REJ_DIR + "/" + CURRENT_FILE + ".rej")
  tFileInputDelimited_1 --OnComponentOk--> tFileCopy_1 (Remove source file, target context.ARCHIVE_DIR + "/" + TalendDate.getDate("yyyyMMdd"))
tFileList_1 --OnSubjobOk--> tFileArchive_1 (zip yesterday's archive dir, optional) / tDBCommit
```

| Topic | Setting / rule |
|---|---|
| tFileList globals | `tFileList_1_CURRENT_FILE` (name), `CURRENT_FILEPATH` (full path), `CURRENT_FILEDIRECTORY`, `CURRENT_FILEEXTENSION`, after loop `NB_FILE` (Integer). |
| Mask semantics | With `Use Glob Expressions as Filemask` checked: `*.csv`, `orders_??.csv`; unchecked: Java regex `orders_\d{8}\.csv` (escape the dot). `Case Sensitive` Yes/No. `Include subdirectories`. `FileList Type` Files/Directories/Both. |
| No files = not an error | tFileList with 0 matches just does not iterate; add `tFileList_1 --OnSubjobOk--> tJava` test on `NB_FILE == 0` -> tWarn/tDie if a file is mandatory. |
| Header / footer | `Header` n lines skipped, `Footer` n lines dropped (requires reading to end; disables streaming for huge files), `Limit`. Header with column names is NOT validated against the schema (use `tSchemaComplianceCheck` or compare first row via tFileInputFullRow). |
| Encoding | set `Encoding` (`UTF-8`, `ISO-8859-15`, `windows-1252`); a UTF-8 BOM is not stripped -> first header column starts with `\uFEFF`; skip header by count, do not match by name, or pre-process (`tFileInputRaw` + `replace("\uFEFF","")`). |
| Zip | `Uncompress as zip file` on tFileInputDelimited (reads first entry) or `tFileUnarchive` (`Archive file`, `Extraction Directory`, `Extract path from archive`) then tFileList. gzip: `tFileUnarchive` does not handle `.gz` single files - use `tFileInputDelimited` with `java.util.zip.GZIPInputStream` via tJava stream, or `gunzip` in tSystem. |
| Archive | `tFileCopy` (`Rename`, `Remove source file` = move, `Replace existing file`, `Create the directory if it doesn't exist`); `tFileArchive` (`Archive format` zip/tar/tar.gz, `Compress level`, `Encrypt files` zip); `tFileDelete`. Move the file only after the DB commit (place tFileCopy after tDBCommit via OnSubjobOk and reiterate, or use a staging "processed" list). |
| Partial files | Producers may still be writing: check `tFileProperties` mtime older than N minutes, or require a `.done`/`.ok` sentinel file via `tFileExist`. |
| Row structure | `Check each row structure against schema` + reject link catches wrong column count; `Die on error` unchecked is required for the reject link to be used. |
| Excel | `tFileInputExcel`: `Read excel2007 file format(xlsx)`, `Generation mode`: `Memory-consuming (User mode)` vs `Less memory consumed for large excel (Event mode)` (streaming SAX; some cell types/formulas differ), `All sheets`/`Sheet list`, `Header`, `First column`/`Last column`, `Stop reading on encountering empty rows`. |
| Positional / regex / full row | `tFileInputPositional` (`Pattern` "10,5,*"), `tFileInputRegex`, `tFileInputFullRow` (one String per line, parse in tMap/tExtractDelimitedFields). |
| Parquet / Avro / ORC in Standard | `tFileInputParquet`, `tAvroInput` (Standard variants exist in 7.3+/8.0; need Hadoop libs in lib). |

### 2.13 File generation

| Need | Setting |
|---|---|
| Split big output | tFileOutputDelimited Advanced `Split output in several files` + `Rows in each output file` (default 1000) -> `file_1.csv`, `file_2.csv`...; not compatible with `Use Output Stream`. |
| No empty file when 0 rows | `Don't generate empty file` (header-only prevention when `Include Header` is set). |
| Append / header once | `Append` + `Include Header` writes a header only when file is created (check behaviour per version; older versions wrote the header on every append (unverified)). |
| Flush memory | `Custom the flush buffer size` + `Row number` (lines before flush). Without it the component buffers the whole output in memory until close for some writers; set 1000-10000 for large files. |
| Encoding / separators / enclosure | `Encoding`, `Row Separator` `"\n"` vs `"\r\n"` for Windows consumers, `Field Separator`, Advanced `CSV options` (`Escape char`, `Text enclosure`), `Throw an error if the file already exist`, `Create directory if not exists`. |
| Dynamic file name per group | `tFlowToIterate` over distinct keys then a subjob writing one file per key; or `tFileOutputDelimited` inside an Iterate with `((String)globalMap.get("row1.key"))` in the path. |
| Compress after write | `tFileArchive` on OnSubjobOk; `tFileOutputDelimited` has `Compress as zip file` option. |
| Fixed-width | `tFileOutputPositional` (`Formats` padding/alignment). |
| Deliver | `tFTPPut` / `tS3Put` / `tAzureStoragePut` / `tSCPPut`; write to a `.tmp` name then rename (`tFileCopy` Rename or `tFTPRename`) so consumers never read a partial file. |

### 2.14 XML and JSON shaping

| Task | Component | Notes |
|---|---|---|
| Flat -> nested XML | `tXMLMap` (or `tAdvancedFileOutputXML`, `tWriteXMLField`) | In tXMLMap output, right-click the tree node > `As loop element` on the repeating element; `All in one` on the output table groups all rows in one document; `Create empty element` per node; `Group by` to nest children under parents (sort input by the parent key first). Output type `Document`. Write with `tFileOutputXML` or `tFileOutputRaw`. |
| XML -> rows | `tFileInputXML` (`Loop XPath query` "/root/order", `Mapping` relative XPaths, `Get Nodes` for sub-trees), `tExtractXMLField`, `tXMLMap` input with loop | For > 100 MB files set `Generation mode` = `Xerces` -> `SAX` on tFileInputXML; DOM (`Dom4j`) loads whole file. |
| Flat -> JSON | `tWriteJSONField` (`Output Column`, `Configure JSON Tree`, loop element, `Group by`, `Remove root node`) then `tFileOutputJSON`/`tFileOutputRaw`, or build with tJavaRow + Jackson (`routines` dependency) | `tFileOutputJSON` itself only writes one object per row with `Generate an array json` option (unverified). |
| JSON -> rows | `tFileInputJSON` / `tExtractJSONFields` | `Read By` = `JsonPath` (default, Jayway), `Xpath`, `JsonPath without loop`; `Loop Jsonpath query` `"$.data[*]"`, mapping `Json query` relative `"id"`, `"customer.name"`, `"$.meta.total"` absolute with JsonPath; nested arrays need a second tExtractJSONFields on a `String` column containing the sub-array (`Json query` `"items"` returns the array as a string). |
| Large JSON | `tFileInputJSON` / `tExtractJSONFields` (JsonPath) | Both load the whole document into memory; split upstream (one object per line, read with tFileInputFullRow then tExtractJSONFields per row) or use `tJavaFlex` with Jackson streaming. |
| Document type | `tFileInputXML` / `tXMLMap` output, `tRESTClient` body | tMap cannot edit `Document` columns; pass through or convert with `row1.doc.toString()` / `routines.system.Document` methods; `tConvertType` does not handle Document. |

### 2.15 REST API pagination

```
tSetGlobalVar_init (page = 1, hasMore = true)
  --OnSubjobOk--> tLoop_1 (Loop Type = While, Declaration "int i = 0", Condition
                          "((Boolean)globalMap.get(\"hasMore\"))", Iteration "i++")
  --Iterate--> tRESTClient_1 (URL context.API_URL, Relative path "/orders",
               HTTP Method GET, Accept Type JSON, Query parameters: page = ((Integer)globalMap.get("page")).toString(),
               Headers: Authorization = "Bearer " + context.API_TOKEN, Die on error unchecked)
  --Response--> tExtractJSONFields_1 (JSON field body, Loop Jsonpath "$.data[*]", mapping ...)
  --row1--> tMap_1 --out1--> tDBOutput_1
tRESTClient_1 --Response--> tReplicate -> second branch tExtractJSONFields_meta ("$.meta.next_cursor", "$.meta.has_more")
  --row2--> tJavaRow_1: globalMap.put("hasMore", row2.has_more); globalMap.put("page", ((Integer)globalMap.get("page")) + 1);
tRESTClient_1 --Error--> tLogRow_err --> tDie (or retry: tSleep + tLoop counter)
```

Rules: use `tLoop` While for cursor APIs (store `next_cursor` in globalMap; stop
when null) and For (`From 1 To ((Integer)globalMap.get("totalPages"))`) when
the first call returns a total. `tRESTClient` response schema: `statusCode`
(Integer), `body` (Document/String depending on Accept type), `string`. Handle
HTTP 429 with `tSleep` and a retry counter; honour `Retry-After`. Prefer
`tRESTClient` over `tHttpRequest` (which only writes to file). Set `Connection
timeout` / `Receive timeout` (Advanced). For OAuth2 use `tRESTClient` with
`Authentication` = `OAuth2 Bearer` (unverified) or fetch the token in a first
tRESTClient and put it in globalMap. `tExtractJSONFields` returns an empty flow
(not an error) when the loop path matches nothing; count with `_NB_LINE` to
detect the end when the API has no `has_more`.

### 2.16 Email and alerting

```
tFileInputDelimited_1 --OnSubjobError--> tSendMail_fail
   tSendMail_fail: To context.ALERT_TO, From context.ALERT_FROM, Subject jobName + " FAILED on " + context.ENV,
     Message "Component: " + ((String)globalMap.get("tDBOutput_1_ERROR_MESSAGE")) + "\nPID: " + pid,
     SMTP host context.SMTP_HOST, Port 587, STARTTLS support, Need authentication, Die on error unchecked
tSendMail_fail --OnComponentOk--> tDie_1 (Error code 4, Error message "load failed")
```

- `<component>_ERROR_MESSAGE` is set on the component that failed with `Die on
  error` checked; with `tLogCatcher` you get `message`, `origin`, `type`
  (`Java Exception`, `tDie`, `tWarn`), `priority`, `code` for every error in the
  job - route tLogCatcher to tSendMail with `tAggregateRow`/`tJavaRow` to build
  one message instead of one mail per error.
- Alert content: job name (`jobName`), context name (`contextStr`), `pid`,
  host (`java.net.InetAddress.getLocalHost().getHostName()`), row counts
  (`_NB_LINE`, `_NB_LINE_INSERTED`, `_NB_LINE_UPDATED`, `_NB_LINE_REJECTED`),
  link to TAC/TMC task.
- `tSendMail` with `Die on error` unchecked so an SMTP outage does not mask the
  original failure; always finish with tDie so the scheduler sees a non-zero
  exit. Attach the log via `Attachments` only if small.
- Other channels: Slack/Teams webhook with `tRESTClient` POST JSON; PagerDuty
  Events API; TMC natively notifies on task failure (Users/notifications) so
  jobs on TMC can skip tSendMail.

### 2.17 Control tables and audit

| Element | Implementation |
|---|---|
| Run id | `pid` (String, `yyyyMMdd_HHmmss_xxxxx`, unique per JVM run), `root_pid`/`father_pid` for tRunJob trees; or a DB sequence fetched in tPrejob into `globalMap("RUN_ID")`. |
| Automatic stats | Project Settings > Job Settings > `Stats & Logs`: `Use statistics (tStatCatcher)`, `Use logs (tLogCatcher)`, `Use volumetrics (tFlowMeterCatcher)` with `On Console`/`On Files`/`On Databases` (tables `TALEND_STATS`, `TALEND_LOGS`, `TALEND_FLOWMETER`, created automatically); per job override in Job view > `Stats & Logs` tab. |
| Component stats | each component Advanced settings `tStatCatcher Statistics` checkbox -> begin/end events per component into tStatCatcher. |
| tStatCatcher schema | `moment`, `pid`, `father_pid`, `root_pid`, `system_pid`, `project`, `job`, `job_repository_id`, `job_version`, `context`, `origin`, `message_type` (begin/end), `message` (success/failure), `duration` (ms). |
| tLogCatcher schema | `moment`, `pid`, `root_pid`, `father_pid`, `project`, `job`, `context`, `priority`, `type`, `origin`, `message`, `code`. Options `Catch Java Exception`, `Catch tDie`, `Catch tWarn`. |
| Row counts | `((Integer)globalMap.get("tDBOutput_1_NB_LINE"))`, `_NB_LINE_INSERTED`, `_NB_LINE_UPDATED`, `_NB_LINE_DELETED`, `_NB_LINE_REJECTED`; `tFlowMeter` on a flow (`Use input connection name as label`) with `tFlowMeterCatcher` for volumetrics. Types differ per component (Integer vs Long): read from the Outline view before casting. |
| Control table | `etl_control(job_name, run_id, context, status, started_at, ended_at, rows_read, rows_written, rows_rejected, last_watermark, host, error_msg)`: INSERT `RUNNING` in tPrejob (own auto-commit connection so it is visible), UPDATE `SUCCESS` in last subjob, UPDATE `FAILED` in the tLogCatcher/OnSubjobError path. |
| AMC | Activity Monitoring Console (Studio perspective or TAC page) reads the TALEND_* tables; TMC shows run history and logs per task. |

### 2.18 Restartability

- Idempotent subjobs: truncate-and-load per partition, upsert instead of
  insert, delete-then-insert by run date (`DELETE FROM fact WHERE load_date = ?`
  before insert in the same transaction).
- Checkpoints: a control table row per step (`step_name, status`); each step
  starts with `tDBInput_step --row--> tJavaRow --> Run if (status != 'DONE')`
  or wraps the step in a child job the orchestrator skips with `Run if`
  `!((Boolean)globalMap.get("step1_done"))`.
- File guards: `tFileExist` (`tFileExist_1_EXISTS` Boolean) to skip work
  already produced; write outputs to `.tmp` and rename at the end.
- Transactions sized to the restart unit: one commit per file/partition, not
  one giant transaction (undo/redo pressure) nor per 1000 rows without a way
  to resume.
- Enterprise `Recovery checkpoints`: in a REMOTE project only, select an
  `OnSubjobOk` trigger > Component view > `Error recovery` tab > check `Recovery
  Checkpoint`, write `Failure instructions`; run via TAC Job Conductor /
  Execution plan; after failure TAC > Job Conductor > `Error Recovery
  Management` > `Recovery checkpoints` tab > launch recovery from the last
  validated checkpoint (statuses: validated / invalidated / fatal error). The job
  resumes at the subjob after the checkpoint, so everything before must be
  idempotent or stateless. Not available on TMC.
- Resume after failure without TAC: orchestrator reads `etl_control` and skips
  children already `SUCCESS` for today's `batch_date` context value.

### 2.19 Parallelism and thread safety

| Mechanism | Setting | Threads / isolation | Notes |
|---|---|---|---|
| Parallel Iterate | click the Iterate link > Basic settings > `Enable parallel execution`, `Number of parallel executions` (expression, e.g. `context.THREADS`) (Enterprise) | N threads run the iterated subjob concurrently | Each thread gets its own copy of iteration globals (unverified for all versions); do not rely on `_NB_LINE` after the loop except via synchronized accumulation. Order of processing is undefined. |
| Multi thread execution | Job view > `Extra` tab > `Multi thread execution` | Independent subjobs (no trigger between them) start simultaneously | Makes `globalMap` synchronized (slower, deadlock risk per docs); subjobs chained with OnSubjobOk still run in sequence. Keep threads <= cores. |
| tParallelize | `tParallelize_1 --Parallelize--> subjobA / subjobB`; `Wait for` = `End of first subJob` or `End of all subJobs`; `Sleep duration` | Fork/join of subjobs | Cleaner than Multi thread execution; follow with `--Synchronize-->` link to the join subjob. |
| Automatic parallelization | right-click a component > `Set Parallelization`, or `tPartitioner` --> N x processing --> `tDepartitioner`, `tCollector`/`tRecollector` (Enterprise) | Row-level partitioning by hash/round robin, `Number of Child Threads`, `Buffer Size` | Works for CPU-bound tMap/tJavaRow chains; components must be thread-safe (no tJava statics, no shared connections). |
| Independent processes | tRunJob `Use an independent process` inside parallel Iterate, or N TAC/TMC tasks with different context params | Separate JVMs | Safest isolation; costs JVM startup (~2-5 s) and memory per process. |
| JobServer/TMC level | several tasks / Execution plan parallel steps | Processes | Preferred for coarse parallelism. |

Thread-safety rules:
- `globalMap` is a plain `HashMap` unless Multi thread execution is on; with
  parallel Iterate use `java.util.concurrent` structures you create yourself
  in tJava (`globalMap.put("counter", new java.util.concurrent.atomic.AtomicLong())`).
- `Numeric.sequence(name, start, step)` is synchronized across threads in the
  same JVM but NOT across independent processes -> use DB sequences/identity.
- Do NOT share one `tDBConnection` across parallel iterations or parallel
  subjobs: a JDBC `Connection` is not safe for concurrent statements/commits
  ("connection is busy", lost updates, deadlocks). Give each parallel branch
  its own tDBConnection (name it with the thread, or use built-in connection
  settings on tDBOutput so each component opens its own) or an external pool
  (`tDBConnection` with `Use or register a shared DB Connection` is for SHARING
  BETWEEN parent/child jobs in one JVM, not for concurrency).
- `tSortRow` sort on disk / `tUniqRow` disk / tMap `Store temp data` in
  parallel: give each thread its own directory (`context.TMP + "/" +
  Thread.currentThread().getId()`), per docs.
- Static fields in routines are shared by all threads of the JVM; make
  `SimpleDateFormat` per-call or `ThreadLocal`, or use `java.time`.
- tHashOutput/tHashInput and tBufferOutput are JVM-global per job class:
  parallel iterations writing the same tHashOutput interleave.

### 2.20 Scheduling patterns

| Platform | Unit | Pattern |
|---|---|---|
| TAC (on-prem, 7.x/8.0) | Job Conductor task (one job + context + JVM parameters + `Log4j level`), triggers: `Simple trigger`, `CRON trigger`, `File trigger` (`Folder path`, `File mask`, polling interval) | Prefer one task per orchestrator job plus Execution Plans (`Add OnOk child`, `Add OnError child`, parallel children) for dependencies across orchestrators; task statuses `Ready to generate` -> `Ready to deploy` -> `Ready to run` -> `Running`. Enable `Regenerate job on change` only in TEST. |
| TMC (Talend Cloud) | Task (artifact version + parameters + engine/run profile + `Log level`), Plan (steps with `On error` handler steps, parallel steps), Triggers: `Once`, `Daily`, `Weekly`, `Monthly`, `CRON`, `Webhook` (task API) | Task per job published from Studio (`Publish to Cloud`) or CI; plans replace orchestrator jobs when children must be independently monitored; webhooks replace file triggers (no native file trigger: use a tiny polling job or external trigger via TMC public API `POST /processing/executions`). |
| Orchestrator job vs plan | Orchestrator = one process, shared context, fine-grained triggers, one log; plan/execution plan = separate processes, per-step retry/logs, engine spreading | Use orchestrator for tightly-coupled steps (<30 min), plans for coarse pipelines and cross-team dependencies. |
| External scheduler (Control-M, Airflow, cron) | call the built launcher `JOB_run.sh --context=PROD --context_param DATE=...` or TAC MetaServlet `runTask` / TMC API | Exit code is the contract; keep stdout for logs. |
| Overlap protection | TAC task option `Allow concurrent execution`? no: TAC queues/fails by default ("task already running"); TMC: tasks cannot overlap (run is `Dispatching`/`Executing`, new trigger is skipped or queued depending on version) | Add a lock row in `etl_control` for external schedulers. |

### 2.21 Environments, contexts and secrets

```
Contexts/CTX_DWH   variables: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS (type Password), IN_DIR, ENV
   contexts (columns): Default | DEV | TEST | PROD
Job: Contexts view > import CTX_DWH (repository mode) -> expressions use context.DB_HOST
Run: Studio Run view > Context drop-down; launcher: JOB_run.sh --context=PROD --context_param DB_PASS=secret
TAC: Job Conductor task > Context parameters tab (override values, `Active` checkbox); TMC: task > Parameters
```

- Never hardcode hosts, paths, credentials, dates. Even `localhost` in
  `Default`: put `Default` = DEV values so a forgotten `--context` hits DEV,
  never PROD.
- `Implicit Context Load`: Project Settings > Job Settings > `Implicit Context
  Load` (or per job: Job view > Extra tab > `Implicit tContextLoad`): `From
  File` (`From File` path expression like `"/etc/talend/" + context.ENV +
  ".properties"`, `Field Separator`) or `From Database` (connection, table,
  `Query condition`); options `Print operations`, `Disable warnings`, `Disable
  errors` (unverified exact labels). Loads `key=value` lines into matching
  context vars at job start; unmatched keys warn. Lets the same build run per
  server with server-local files. Explicit `tContextLoad` does the same inside
  a subjob (`Print operations`, `Die on error` when a variable is missing).
- Secrets: context type `Password` (stored encrypted in the `.item`, masked in
  TAC/TMC UI and `Print Parameters`); pass at run time with `--context_param
  DB_PASS=...` (visible in `ps`!), or read from env in tPrejob:
  `context.DB_PASS = System.getenv("DB_PASS");` in a tJava (context values
  are plain strings in Studio 8, so `System.getenv()` cannot be a default
  value expression). Studio 8 supports `--context_param` values encrypted
  with the Studio encryption utility (unverified). Alternatives: `tSetKeystore`
  for TLS client certs/truststores, HashiCorp Vault / AWS Secrets Manager via
  `tRESTClient` or `tSystem` call in tPrejob, TAC/TMC task parameters marked
  as password, Remote Engine `--context_param` from TMC task parameters
  (passwords are sent encrypted and masked in logs).
- SSL/TLS: JDBC URL params via `Additional JDBC Parameters` (`sslmode=require`,
  `useSSL=true&requireSSL=true`, `encrypt=true;trustServerCertificate=false`),
  truststore via JVM args `-Djavax.net.ssl.trustStore=... -Djavax.net.ssl.trustStorePassword=...`
  or `tSetKeystore` (`TrustStore type` JKS/PKCS12, `TrustStore file`, password,
  `Need Client authentication` + KeyStore).
- Built artifact contexts: build zip contains `<job>/<Job>/contexts/<Ctx>.properties`
  when `Context scripts` is selected in the Build Job dialog; TAC/TMC override
  values at task level; the build's default context is the one chosen at
  build time (`--context` overrides).

### 2.22 Logging

| Topic | Guidance |
|---|---|
| tLogRow | Development only. `Mode`: Basic / Table (`Print values in cells of a table`) / Vertical. Writes to stdout; on 1M rows it dominates run time and fills TAC/TMC logs. Remove or deactivate (`Deactivate` right-click) before build; TAC/TMC log retention is finite and huge logs slow the console. |
| log4j2 | Project Settings > Log4j > `Activate log4j in components`; Studio 7.3+/8 use log4j2 (`log4j2.xml` template editable in Project Settings). Component messages go to loggers named after components; level set per run: Studio Run view > Advanced settings `log4jLevel` drop-down, TAC task `Log4j level`, TMC task `Log level`, launcher `--log4jLevel=INFO`? (flag unverified; the generated launcher passes it when set in Studio). Levels TRACE/DEBUG/INFO/WARN/ERROR/OFF; DEBUG logs every SQL statement and row count per component (verbose). |
| tWarn / tDie | `tWarn`: `Warn message`, `Code`, `Priority` (Trace/Debug/Info/Warning/Error/Fatal); `tDie`: `Error message`, `Error code`, `Priority`, `Exit the JVM immediately` (unverified label). Both caught by tLogCatcher. Use tWarn for business anomalies (0 rows, late files) so they land in the log table without failing. |
| Structured logs | tJavaRow or tLogRow replaced by `tFileOutputDelimited`/`tDBOutput` on a tLogCatcher flow; or log JSON lines via a routine using `org.apache.logging.log4j.LogManager.getLogger(jobName)` for ingestion by ELK/Splunk. |
| System.out in tJava | Goes to stdout like tLogRow; acceptable for a few summary lines per run, never per row. |
| Studio console | Run view console truncates (Preferences > Talend > Run/Debug > `Console buffer size`? (unverified)); use `On Files` stats/logs for full traces. |
| TAC/TMC logs | TAC: Job Conductor > task > `Logs`; JobServer keeps logs under `TalendJobServersFiles/repository/<task>/...`; TMC: task run > `Logs` (download), retention ~ 30 days (unverified); Remote Engine local logs under its `data/log` (Karaf) (unverified). |

### 2.23 Unit testing

- Enterprise Studio: right-click a component (typically the tMap or the subjob
  start) in a job > `Create Test Case`. Studio generates a test job skeleton:
  `INPUT` instances fed by `tFileInputDelimited` reading test files, the tested
  components, `REFERENCE` output compared with `tFileCompare` /
  `tCreateTemporaryFile` + `tAssert` (`Assertive condition`, `Description`),
  results caught by `tAssertCatcher` (`status` Ok/Failed, `substatus`,
  `errorMessage`, `description`, `origin`). `Test Cases` view: `Test instances`
  (several input/reference data sets per test case), run with `Run Test`.
- Test data: stored in the project repository with the test case (under the
  job's `Test Cases` node; files under the project `process/test` area
  (unverified exact folder)); keep them small (10-100 rows) and deterministic
  (no `getCurrentDate()` in expected output).
- CI: Talend CI Builder (Maven plugin `org.talend.ci:builder-maven-plugin`)
  `mvn org.talend.ci:builder-maven-plugin:<ver>:generateAllPoms` then `mvn test`
  / `mvn deploy -Dlicense.path=... -Dupdatesite.path=...` runs test cases as
  JUnit (`-DskipTests`/`-Dtalend.skipTest` unverified) and fails the build.
  Reports under `target/surefire-reports`.
- Without Enterprise: build a `TEST_<JOB>` job that runs the real job via tRunJob
  against a test DB/files, then `tDBInput` expected vs actual with `tMap` inner
  join rejects and `tAssert`/`tDie` on mismatches.
- Assertions in production jobs: `tAssert` with `tAssertCatcher` --> tDie;
  `tSchemaComplianceCheck` (reject flow for type/length/nullability violations)
  as a gate after ingestion.

### 2.24 Code review checklist

| Check | Look for |
|---|---|
| Schema nullability | `Nullable` unchecked on a column that can be null -> primitive `int`/`long`/`double` -> NPE in tMap. Nullable on PK/key columns used for joins. Lengths/precision set for DB `Create table`. |
| Error handling | Every subjob start has OnSubjobError or the job relies on a tLogCatcher + tDie; `Die on error` deliberately set (checked for load components without reject links, unchecked only when a reject link exists). |
| Transactions / commit | `Commit every` sized (10k) or `Use an existing connection` + tDBCommit/tDBRollback; truncate placed safely; no tDBCommit inside Iterate with shared connection in parallel. |
| Batch | `Use Batch Size` on inserts/updates/deletes (not possible with reject link or Insert or update); `rewriteBatchedStatements=true` for MySQL. |
| Hardcoded values | paths (`C:\...`, `/home/user`), hosts, credentials, dates, environment names in expressions; all should be `context.*`. |
| Connections closed | tDBClose/tFTPClose in tPostjob; `Close Connection` on the last tDBCommit; no leaked cursors in Iterate (tDBInput with own connection inside loops opens/closes per iteration - acceptable but slow; shared connection + no close = cursor leak on Oracle). |
| Lookups | `Reload at each row` only with a key expression and large lookup; lookup schema trimmed; `Match Model` deliberate (Unique vs First vs All). |
| Debug leftovers | tLogRow, `Print Parameters`, Statistics/Traces, tJava `System.out`, deactivated components left on the canvas, `Enable debug mode` on tDBOutput. |
| Secrets | context password vars typed `Password`; no password literal in JDBC URL / tSendMail; `Print operations` off for context load in PROD. |
| Versioning | job version bumped (M/m) on breaking change; tRunJob child version `Latest`; Git branch matches environment. |
| Documentation | Job view > `Main` tab `Purpose` and `Description` filled; component `Documentation` tab or labels for tMap/tJava logic; generated HTML doc (right-click job > `Generate Doc as HTML`). |
| Parallel safety | parallel Iterate with shared connection / tHash / globalMap counters. |
| Performance smells | tMap chains that could be one tMap; tSortRow without disk on big data; `tAggregateRow` on unbounded keys; row-by-row `tDBRow` in flow (use `Use PreparedStatement` + batch or tDBOutput). |
| Dates / types | `Date Pattern` set on every Date column of file schemas; BigDecimal compared with `compareTo`; timezone assumptions documented. |
| Restart | idempotency per subjob; watermark updated after commit; files moved after commit. |
| Build readiness | all `Modules` installed (no red "missing module" marker), routines dependencies set, context `Default` safe, job compiles in `Code` view with no warnings about unused links. |

## 3. Performance tuning

Measure first: Run view > Advanced settings > `Exec time` (per run total) and
`Statistics` (rows/s on each link), `tChronometerStart`/`tChronometerStop`
(`Caption`, `Display duration in console`, `Display current time`), Stats & Logs
`On Databases` (component durations), `--stat_port=<n>` on the launcher to feed
Studio's statistics remotely (unverified flag usage), AMC for history, DB-side
wait events, OS `top`/`vmstat`. Find the slowest link: the component AFTER a
full-speed link that reports low rows/s is the bottleneck (Talend runs a
pipeline inside one subjob; the slowest component throttles all).

Typical Standard-job throughput on one core (order of magnitude):
file -> tMap -> file 50k-300k rows/s; file -> tDBOutput batch 5k-50k rows/s;
tDBOutput `Insert or update` 200-2k rows/s; bulk loaders 100k-1M rows/s; REST
API calls 5-50 rows/s per thread; tDBSCD 500-5k rows/s.

| Area | Setting | Guidance |
|---|---|---|
| JVM heap | Studio: Run view > Advanced settings > `Use specific JVM arguments` (`-Xms256M -Xmx1024M` defaults; these are written into the built launcher `JOB_run.sh`/`.bat`); TAC task: `JVM parameters` field (`Active`); TMC: Remote Engine run profile `JVM parameters`; Studio itself: `Talend-Studio.ini` `-Xmx`. | Size `-Xmx` to the largest in-memory structure (lookups, tHash, tSortRow, tAggregateRow) + 500 MB; set `-Xms` = `-Xmx` for long jobs to avoid resizes; leave 20% of the machine for the OS and other tasks. 32-bit JVM caps ~1.5 GB (irrelevant in 8.0, 64-bit only). |
| GC | Java 11/17 default is G1 (`-XX:+UseG1GC`); Java 8 default Parallel GC. `-XX:MaxGCPauseMillis=500`, `-XX:+UseStringDeduplication` (G1, many duplicate strings in lookups), `-XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/var/tmp` | GC logs: Java 9+ `-Xlog:gc*:file=/var/log/talend/gc_%p.log:time,uptime:filecount=5,filesize=20m`; Java 8 `-XX:+PrintGCDetails -XX:+PrintGCDateStamps -Xloggc:/path/gc.log`. Analyse with GCViewer/GCEasy. |
| Metaspace / threads | `-XX:MaxMetaspaceSize=512m` for huge jobs (thousands of generated classes); `-Xss` rarely. | Big tMap expressions generate large methods; Studio 8 splits code (`Code generation` > `Generate code in several methods`? unverified) to avoid `code too large`. |
| tMap lookups | narrow lookup schema, filter lookup query, `Load once` by default, `Store temp data` + `Temp data directory path` on fast local disk when heap is short; `Reload at each row` only with key expressions; move the join to the DB when both sides are in the same DB (`WHERE a.id = b.id` in tDBInput or ELT). | A lookup of 50M rows is a DB job, not a tMap job. Several tMaps in sequence each with lookups all load at subjob start (sum their memory). |
| tHash | fill once, read many; `tHashInput` `Clear cache after reading` on the last reader; prefer `tHashOutput` over re-querying the DB for each subjob. | Keyed data structure, same memory rule as lookups. |
| DB input | `Fetch size`/cursor: MySQL `Enable stream` (tMysqlInput Advanced; sets fetch size `Integer.MIN_VALUE` - one open streaming result set per connection, cannot run other statements on it); PostgreSQL `Use cursor` + `Cursor size` (e.g. 10000; requires autocommit off, so use tDBConnection); Oracle `defaultRowPrefetch=5000` in Additional JDBC Parameters (or `Use cursor` unverified for tOracleInput); MSSQL `selectMethod=cursor` (jTDS) / `responseBuffering=adaptive` (MS driver). | Without streaming the driver may buffer the whole result set (MySQL, MSSQL default) -> OOM on big tables. Select only needed columns; push filters into SQL; `Trim all the String/Char columns` costs CPU, enable per column instead (`Trim column`). |
| DB output | `Use Batch Size` 1000-10000; `Commit every` 10000-100000 (one commit per batch multiple); MySQL `rewriteBatchedStatements=true` (multi-row INSERT, 5-20x); MySQL tMysqlOutput `Extend Insert` + `Number of rows per insert`; Oracle batch via driver (standard), `defaultBatchValue`; PostgreSQL `reWriteBatchedInserts=true`; MSSQL `useBulkCopyForBatchInsert=true`; Snowflake/Redshift/BigQuery: ALWAYS bulk components for > 10k rows (row inserts are 10-100 rows/s). | Disable/drop indexes and constraints during load; avoid `Insert or update` (two statements, no batch); a reject link disables batch mode -> validate upstream (tSchemaComplianceCheck) and keep the reject link off on the hot path; `Die on error` unchecked with no reject link also disables batch in some versions (unverified). |
| Bulk | 2.7 | File on local SSD, gzip across network, `Row separator`/`Null string` consistent. |
| Partition parallelism | parallel Iterate on a partition list (date ranges, hash buckets, file list) with N = cores or DB connection budget; tPartitioner/tDepartitioner for CPU-bound transforms; `Multi thread execution` for independent subjobs; separate JVMs for > 4-8 GB heaps. | Parallel inserts into one table contend on indexes/locks; measure. |
| Sorting | `tSortRow` Advanced `Sort on disk` + `Temp data directory path` (+ `Create temp data directory if not exist`) and buffer size setting (unverified label `Buffer size of external sort`); sort in the DB (`ORDER BY`) whenever source is a DB. | In-memory sort needs 3-5x data size heap. |
| Dedup / aggregation | `tUniqRow` `Use of disk`, `tAggregateSortedRow` after sorted input, DB-side `GROUP BY`. | tAggregateRow memory = distinct groups x row size. |
| tMap expressions | avoid regex (`matches`, `replaceAll`, `split`) per row in hot paths; precompile in a routine `static final Pattern`; avoid `String.format`; `StringHandling.*` routines are plain Java (fine); avoid repeated `TalendDate.parseDate` on the same format (creates a `SimpleDateFormat` per call - cache a `FastDateFormat`/`DateTimeFormatter` in a routine, `SimpleDateFormat` is NOT thread-safe so never a shared static); avoid autoboxing in `Var` section (declare primitive types). | Combine consecutive tMaps; tMap is faster than tJavaRow with reflection; tFilterRow/tReplace are fine. |
| File I/O | tFileOutputDelimited `Custom the flush buffer size` (1000-10000 rows), avoid `Append` for many small writes, write to local disk then `tFileCopy`/`tFTPPut`; read with `CSV options` only when needed (CSV parser is slower than plain split); `Uncompress as zip file` streaming; avoid `Footer` on huge files. | NFS/SMB targets are 5-10x slower; antivirus scanning on Windows job servers kills small-file throughput. |
| Network | Batch and compress (gzip on bulk files, `useCompression=true` MySQL), reduce round trips (no `Reload at each row` over WAN), co-locate JobServer/Remote Engine with the DB. | - |
| Excel | `Event mode` for xlsx > 50k rows; CSV export instead of Excel when possible. | POI user mode can need 1 GB for a 100k-row workbook. |
| XML/JSON | SAX (`Generation mode`) for tFileInputXML; split large JSON arrays; avoid `Document` columns through tMap. | DOM = 5-10x file size in heap. |
| Studio vs deployed | Studio adds Statistics/Traces sockets, `Save Job before execution`, runs on the Studio JVM with its own `-Xmx` (Run view setting wins); deployed jobs run the launcher's JVM args; Studio compiles in `Code` view with debug info. | Benchmarks only in a deployed run on the real engine with Statistics off. |
| Remote Engine (TMC) | Run profile: `JVM parameters` (`-Xmx`), `Maximum number of concurrent executions`? (unverified) per engine; Cloud Engine has fixed memory (8.0: ~ 8 GB total per Cloud Engine, several tasks share it (unverified)). | Use Remote Engines for memory-heavy jobs. |
| Spark | Run view > `Spark Configuration`: `Driver memory`, `Executor memory`, `Executor cores`, `Number of executors` / `Dynamic allocation`, `Advanced properties` (`spark.sql.shuffle.partitions`, `spark.executor.memoryOverhead`) | See big-data-spark.md; Spark UI (`:4040` / history server) for stages/skew. |

Memory leak suspects (job RSS grows over hours or across iterations):
`tHashOutput` with `Append` filled every iteration and never cleared;
`tBufferOutput` in a long-running child (whole buffer retained); large values
parked in `globalMap` per iteration (`globalMap.put("file_" + i, bytes)`);
`Document` (DOM) objects per row kept in lists; `Reload at each row (cache)`
on an unbounded key space; routines with static `List`/`Map` caches; tJava
opening JDBC statements/streams without close inside Iterate; log4j DEBUG with
`On Files` stats on million-row jobs (disk, not heap); unclosed
`tFileInputDelimited` inside Iterate on Windows (file handles).

## 4. Troubleshooting index

| Symptom / error text | Likely cause | Fix / where to look |
|---|---|---|
| `java.lang.OutOfMemoryError: Java heap space` | Lookup/tHash/tSortRow/tAggregateRow/tBufferOutput larger than `-Xmx`; MySQL/MSSQL result set buffered; Excel user mode | Raise `-Xmx` (Run view > Advanced settings; TAC JVM parameters; run profile); tMap `Store temp data`; narrow lookup; `Enable stream`/`Use cursor`; `Sort on disk`; `Use an independent process` for children; take a heap dump (`-XX:+HeapDumpOnOutOfMemoryError`) and look at the dominator tree. |
| `java.lang.OutOfMemoryError: GC overhead limit exceeded` | Heap nearly full, GC spinning (same causes as above) | Same fixes; do not "fix" with `-XX:-UseGCOverheadLimit` (just delays). |
| `java.lang.OutOfMemoryError: Metaspace` / `PermGen space` | Huge job (hundreds of components) or many child jobs in one JVM; Studio with many projects | `-XX:MaxMetaspaceSize=1g`; split job; Studio `.ini` `-XX:MaxMetaspaceSize`. |
| `Exception in component tMap_1 (JOB) java.lang.NullPointerException` | Non-nullable column mapped from null (primitive `int`); method call on null String (`row1.name.trim()`); lookup column used without null check on Left Outer Join | Tick `Nullable` in schema (Integer instead of int); guard: `row1.name == null ? null : row1.name.trim()` or `Relational.ISNULL(row1.name)`; for lookups test `lkp.id != null` before using `lkp.x`. Look at the generated `Code` view line in the stack trace. |
| `java.lang.ClassCastException: java.lang.Long cannot be cast to java.lang.Integer` (or reverse) | Casting a `globalMap` value (`_NB_LINE`, `CURRENT_VALUE`, custom) to the wrong boxed type; components differ (Integer vs Long) | Check the type in Studio Outline view (hover the variable) and cast accordingly, or `Long.parseLong(String.valueOf(globalMap.get("...")))`; `((Number)globalMap.get("x")).longValue()` is type-agnostic. |
| `java.lang.ClassCastException: java.lang.String cannot be cast to java.util.Date` | `tFlowToIterate` / tSetGlobalVar stored a String; context var type mismatch; `--context_param` always arrives as String and is parsed by declared type | Cast to the actual stored type; set context type to Date and pass `yyyy-MM-dd HH:mm:ss`. |
| `java.text.ParseException: Unparseable date: "2024-01-05T10:00:00Z"` | Schema `Date Pattern` or `TalendDate.parseDate` pattern mismatch; empty string instead of null; locale month names | Fix pattern (`"yyyy-MM-dd'T'HH:mm:ss'Z'"`, `"dd/MM/yyyy"`); `Check date` in tFileInputDelimited to reject; `TalendDate.parseDateLocale(pattern, s, "EN")`; treat `""` as null (`Advanced` `Set empty values to Null before processing`? unverified -> use tMap). |
| `java.lang.NumberFormatException: For input string: "1,234.00"` | Thousands separator/decimal comma; empty string to Integer | tFileInputDelimited Advanced `Advanced separator (for numbers)` (`Thousands separator`, `Decimal separator`); read as String and convert in tMap. |
| `java.sql.SQLException: ORA-01000: maximum open cursors exceeded` | tDBInput/tDBRow inside Iterate on a shared connection without closing; `Propagate QUERY's recordset`; batch of many PreparedStatements | Use tDBRow `Commit every` / close; avoid per-iteration tDBInput on shared connection or add tDBCommit per iteration; DBA raise `OPEN_CURSORS`; redesign loop into set-based query. |
| `ORA-01555: snapshot too old` | Long-running tDBInput cursor while source is updated | Smaller extracts, larger undo, extract to staging first. |
| `com.mysql.cj.jdbc.exceptions.CommunicationsException: Communications link failure` / `The last packet successfully received from the server was N milliseconds ago` | Connection idle beyond `wait_timeout` (e.g. open in tPrejob, used after a 2 h lookup load); firewall idle timeout; `max_allowed_packet` exceeded by big batch | Open the connection right before use (separate subjob), raise `wait_timeout`/`interactive_timeout`, `tcpKeepAlive=true`, smaller `Batch Size`/`max_allowed_packet`; do not rely on `autoReconnect=true`. |
| `The method foo(String) is undefined for the type Routines` / `cannot be resolved to a type` at compile | Routine missing from job dependencies, renamed routine, wrong Java version, missing module jar | Right-click Job > `Setup routine dependencies` (user routines tab); check Routines node compiles (red X); install module; check `Window > Preferences > Java > Compiler` level vs JDK. |
| `Job compile error: The import routines.X cannot be resolved` | Routine deleted/renamed or not shared from reference project; project not fully synced | Re-add routine, `Setup routine dependencies`, Project Settings > `Build` > re-sync; in Git projects pull routines folder. |
| `Module <jar> not installed` / orange or red marker on a component / `missing jars` on build | External driver not in Studio (Oracle ojdbc, MSSQL, SAP JCo, Snowflake) | Window > Show View > Talend > `Modules`: `Install all required modules` or `Install external modules` (browse jar); or component Basic settings `Driver JAR` table add `mvn:org.talend.libraries/<name>/6.0.0` style URI; corporate Nexus mirror via Preferences > Talend > Artifact repository. |
| `row1 cannot be resolved` / `cannot find symbol` / `Variable 'out1' not found` after renaming a link | tMap/tJavaRow/tJava expressions still reference the old link or component name | Open tMap: expressions in red; `Ctrl+F` in Code view for the old name; rename links before writing code; use `__UNIQUE_NAME__` placeholders carefully. |
| `Error: Could not find or load main class <project>.<job>_<ver>.<Job>` when running the launcher | Zip extracted into a path with spaces/special chars (Linux `_run.sh` classpath), jar missing from `lib`, launched from wrong working directory, `ROOT_PATH` changed | Keep path simple; run the `.sh` from its own directory (script uses `ROOT_PATH=$(cd $(dirname $0); pwd)` in 7.3+/8); rebuild; check `lib/` contains `<job>_<ver>.jar`. |
| `java.lang.UnsupportedClassVersionError: ... has been compiled by a more recent version of the Java Runtime (class file version 61.0), this version ... recognizes up to 55.0` | Built with Java 17 (61), run on Java 11 (55) / Java 8 (52) | Install the matching JDK on JobServer/engine or set Studio Preferences > Java > Compiler compliance to the runtime level; Studio 8 requires Java 11 or 17 (R2023+ supports 17). |
| `java.net.BindException: Address already in use` | `tRESTRequest`/`tHttpRequest` endpoint port taken; Studio stats/trace port (`--stat_port`) collision; two JobServers on one host | Change port (`Endpoint` `http://0.0.0.0:8088/`), kill stale JVM (`lsof -i :8088`), change JobServer `conf/TalendJobServer.properties` ports (8000/8001/8888). |
| `Access denied for user 'x'@'host'` / `Login failed for user 'x'` / `FATAL: password authentication failed` | Wrong credentials/context, host-specific grant (MySQL `'x'@'%'`), MSSQL Windows auth (`integratedSecurity=true` needs `mssql-jdbc_auth-*.dll`), Postgres `pg_hba.conf` | Check which context ran (`contextStr` print), test with DB client from the job host, fix grants/pg_hba; TAC context overrides. |
| `ERROR: character with byte sequence 0xe2 0x80 0x99 in encoding "UTF8" has no equivalent in encoding "LATIN1"` / `Incorrect string value: '\xF0\x9F...'` (MySQL) / `???` in output | Source/target encoding mismatch; file read with wrong `Encoding`; MySQL `utf8` (3-byte) vs `utf8mb4` emoji; DB `client_encoding` | Set `Encoding` on file components; JDBC `characterEncoding=UTF-8&useUnicode=true`; Postgres target column/DB `UTF8`; MySQL `utf8mb4` column + `connectionCollation=utf8mb4_unicode_ci`; `tReplace` to strip. |
| `java.io.FileNotFoundException: data/in.csv (No such file or directory)` | Relative path resolved against the JVM working directory, which differs between Studio (workspace), launcher (where you ran it) and TAC JobServer; Windows path on Linux | Use absolute paths from context (`context.IN_DIR + "/in.csv"`); forward slashes work on Windows; check `tFileList` `Format file path to Unix style`. |
| `java.io.IOException: Permission denied` on JobServer | Service account lacks rights on output dir; `_run.sh` not executable; SELinux | `chown`/`chmod` directories for the JobServer/engine user; `chmod +x *.sh` (TAC does this on deploy); check `getenforce`. |
| TAC task stuck `Ready to deploy` / `Deploying` | JobServer unreachable (ports 8000/8001), disk full on JobServer, previous deploy locked | TAC > Servers page status (green/red), JobServer `logs/`, `TalendJobServersFiles/` disk space, restart JobServer, re-generate task. |
| TAC `Job generation failed` / `CommandLine: Connection refused` / `Ready to generate` forever | TAC CommandLine not running or wrong version, wrong port (8002), Git credentials expired for the CommandLine workspace, job references missing modules | Start CommandLine (`Talend-Studio ... -application org.talend.commandline.CommandLine startServer -p 8002`), TAC > Configuration > `CommandLine/primary`, check `commandline-workspace` logs, `Settings > Projects` credentials; errors show in TAC > Job Conductor task `Error status`. |
| TMC run `EXECUTION_FAILED` / `DEPLOY_FAILED` with no job log | Engine down or unpaired, run profile heap too small (JVM died before logging), artifact missing dependencies for the engine's Java, task timeout | TMC Processing > Engines status; engine `data/log` (unverified path); run profile `JVM parameters`; redeploy artifact; check `Execution timeout`. |
| Remote Engine shows `Unpaired` / `Not paired` | Pre-authorization key not applied, expired key, proxy blocking `*.cloud.talend.com` | TMC > Engines > Add/`Pre-authorization key`; put it in `etc/preauthorized.key.cfg` (`remote.engine.pre.authorized.key=...`), restart engine; check `etc/org.talend.ipaas.rt.*.cfg` proxy settings; one key per engine. |
| Job runs slowly loading a lookup, then OOM: `tMap_1 ... lookup` | Lookup too large for heap | `Store temp data` + temp dir, narrow schema/filter, DB join, tHash reuse, `Reload at each row` with key. |
| Duplicate rows in tMap output | Lookup `Match Model` = `All matches`, or duplicate keys in lookup with `All matches`; main flow duplicated by two outputs sharing the same target | Set `Unique match`/`First match`; dedup lookup (`tUniqRow` or `SELECT DISTINCT`); check output filters. |
| Wrong lookup value picked | `Unique match` returns the LAST match, `First match` the first; lookup order not controlled | Sort the lookup query (`ORDER BY updated_at DESC` for First match) or dedup upstream. |
| Values compare unequal though they look the same (`CHAR(10)` columns) | Trailing spaces in CHAR columns; invisible chars | tDBInput Advanced `Trim all the String/Char columns` or per-column `Trim column`; `StringHandling.TRIM`; compare with `.trim()`. |
| `BigDecimal` `equals` false for `1.0` vs `1.00` / tUniqRow not deduping decimals | `BigDecimal.equals` includes scale | Use `a.compareTo(b) == 0`; `setScale(2, RoundingMode.HALF_UP)` before dedup; tMap `Ignore trailing zeros for BigDecimal` (unverified) option. |
| Timestamps shift by hours between source and target | JVM default timezone differs between Studio machine and server; MySQL `serverTimezone`; `Date` vs `Timestamp` with DST; Snowflake `TIMESTAMP_NTZ` vs `_TZ` | Set `-Duser.timezone=UTC` in JVM params on every runtime (Studio Run view, TAC, run profile); JDBC `serverTimezone=UTC`; store UTC, format at the edges; `TalendDate.formatDateInUTC`. |
| CSV rows split in the middle of a quoted field with newlines | `CSV options` unchecked (plain split on row separator) | Check `CSV options` on tFileInputDelimited, set `Text enclosure` `"\""` and `Escape char`; same on output. |
| Last column has a trailing `\r` / `^M` or header mismatch on Windows files | `Row Separator` `"\n"` on a CRLF file | Set `"\r\n"`, or enable `CSV options` (handles both), or `Trim all columns`. |
| First column of a UTF-8 file is `\uFEFFid` / lookup on first column fails | Byte order mark not stripped | Skip header by count, do not match by header names; `tFileInputRaw` + `replaceFirst("^\uFEFF","")`; ask producer to write without BOM; (UTF-16 files: set `Encoding` `UTF-16` which does strip BOM). |
| Excel read OOM / very slow / `Zip bomb detected` (POI) | User mode DOM parse of big xlsx; POI ratio protection | `Read excel2007 file format(xlsx)` + `Less memory consumed for large excel (Event mode)`; convert to CSV; raise POI `ZipSecureFile.setMinInflateRatio` in tJava (unverified need). |
| `tFileList` iterates 0 files though files exist | Mask uses regex while `Use Glob Expressions as Filemask` is checked (or vice versa); `Case Sensitive` Yes vs mixed-case extensions; `Include subdirectories` off; path with trailing slash issues; `FileList Type` Directories | Match mask type to option (`*.csv` glob vs `.*\.csv` regex); set `Case Sensitive` No; print `tFileList_1_NB_FILE`. |
| Child job cannot see parent `tHashOutput` / `globalMap` values | tHash/tBuffer/globalMap are per job class instance; `Use an independent process` = separate JVM | Pass data via context (`Transmit whole context`), files, DB or child `tBufferOutput` -> parent tRunJob output row; parent -> child: write to file/`tHashOutput` is not shared, use tRunJob input? (tRunJob has no input flow: use files or DB). |
| `Die on error` unchecked yet job stops with exception | `Die on error` covers only the component's own handled errors (DB execution). Parse/type errors in tMap, NPEs, `ClassCastException` are uncaught Java exceptions | Use reject links on input components, `tSchemaComplianceCheck`, null guards in tMap, `tLogCatcher` to log; a `try/catch` in tJavaRow for custom conversions. |
| `Commit every` = 0 behaviour unclear | 0 means commit only at the end (one transaction) in most components (unverified for all) | Set explicit 10000 or use tDBConnection + tDBCommit for clear semantics. |
| tDBOutput became slow after adding a reject link | Reject link forces row-by-row execution (batch disabled) and per-row error handling | Validate upstream and remove reject; or keep reject only on a small pre-validated flow; use bulk + DB-side validation. |
| `Insert or update` loads at 300 rows/s | Two statements per row, no batch | Staging + MERGE/`ON CONFLICT`; `Update or insert` if mostly updates; bulk. |
| Snowflake `SQL compilation error: error line 1 at position N invalid identifier '"customer_id"'` | Snowflake upper-cases unquoted identifiers; Talend quotes lower-case schema names | Use upper-case column names in schema or Advanced `Convert columns and table to uppercase` (tSnowflake* components); match the table definition. |
| Snowflake `Object does not exist, or operation cannot be performed` | Wrong `Database`/`Schema`/`Warehouse`/`Role` in connection; role lacks USAGE | Check connection Advanced settings `Role`; `USE` statements don't persist in Talend pooled sessions. |
| S3 `403 Forbidden: SignatureDoesNotMatch` / `The request signature we calculated does not match` | Wrong region/endpoint (`s3.eu-west-1.amazonaws.com` vs global), clock skew > 15 min on the job host, secret with special chars mangled in context, Signature V2 on V4-only region | Set `Region` on tS3Connection, `ntpdate`/chrony, re-enter key, enable `Use Signature V4` (unverified label), use IAM role (`Inherit credentials from AWS role`). |
| Salesforce `INVALID_SESSION_ID: Session expired or invalid` | Session reused after timeout; token revoked; wrong endpoint (`login` vs `test.salesforce.com`) | Reconnect with `tSalesforceConnection` per subjob; `Use or register a shared connection` off for long jobs; sandbox URL; OAuth refresh. |
| Salesforce `REQUEST_LIMIT_EXCEEDED: TotalRequests Limit exceeded` | Daily API call quota exhausted by row-by-row operations | `tSalesforceInput` `Query Mode` = `Bulk` (Bulk API), `tSalesforceOutputBulkExec`, bigger `Batch Size` (200 SOAP / 10000 Bulk), fewer runs. |
| Kafka `org.apache.kafka.clients.consumer.CommitFailedException: ... the poll loop was spending too much time` | Processing per poll exceeds `max.poll.interval.ms` (default 5 min); too many records per poll | `tKafkaInput` Advanced `Consumer properties`: `max.poll.records=500`, `max.poll.interval.ms=900000`; make downstream faster; commit manually less often. |
| Spark `Container killed by YARN for exceeding memory limits. 5.5 GB of 5.5 GB physical memory used` | Executor off-heap/overhead too small; skewed partitions | Spark Configuration > Advanced properties `spark.executor.memoryOverhead=2g`, raise `Executor memory`, more partitions (`spark.sql.shuffle.partitions`), salt skewed keys; see big-data-spark.md. |
| `java.lang.NoSuchMethodError` / `NoClassDefFoundError` / `AbstractMethodError` at run time only | Two versions of a library in `lib/` (guava, jackson, httpclient, log4j) brought by different components/drivers; driver compiled for newer Java | List `lib/` duplicates (`ls -1 lib/` sorted by name), remove conflicting jar from the component `Driver JAR`, isolate the component in a child job with `Use an independent process` and specific classpath; Modules view `Exclude`? (unverified). |
| `ERROR StatusLogger No Log4j 2 configuration file found. Using default configuration (logging only errors to the console)` | log4j2.xml missing from job resources, log4j activated only partially; mixed log4j1 jars | Project Settings > Log4j > `Activate log4j in components`, reset template, rebuild; remove `log4j-1.x` from `lib` if log4j2 bridge present; harmless if you only use stdout. |
| Studio: `Workspace in use or cannot be created, choose a different one` | Another Studio instance (or crashed one) holds `workspace/.metadata/.lock`; network drive workspace | Close other instance; delete `.metadata/.lock` (and `.metadata/.plugins/org.eclipse.core.resources/.snap` if corrupt); keep workspace on local disk. |
| Git: merge conflict in `*.item` / `*.properties` / `*.screenshot` | Two users edited the same job; XML diff is not mergeable by hand | In Studio's conflict dialog take one side (Mine/Theirs) entirely, re-apply the other change manually in Studio, re-save; never hand-edit conflicted XML; delete and regenerate `.screenshot`; keep one owner per job per sprint, commit small. |
| `The project <X> is locked by another user` / `Job is locked by user Y` / cannot edit (read-only lock icon) | Remote project item lock held by another Studio session (Enterprise) | Ask Y to close the job; admin: TAC > Settings > `Lock`? (unverified page; in 8.0 locks are listed under `Projects` > `Lock`); locks also clear when the user logs out of the project. |
| TAC `Projects`: `SVN authentication failed` / `Git: not authorized` / CommandLine cannot fetch | Expired token/password in TAC project settings; 2FA on GitHub/GitLab requires PAT; proxy | TAC > Settings > Projects > edit credentials (`Technical Git user` in 8.0) and `Check connection`; Studio: Preferences > Talend > `Repository` connection credentials; use PAT/deploy key. |
| Studio very slow / freezes on startup or palette | Online update/Maven checks behind a proxy, antivirus scanning `workspace` and `configuration/.m2`, huge project, Windows Defender | `Talend-Studio.ini`: `-Dtalend.disable.internet=true`, `-Xmx4096m`, `-XX:MaxMetaspaceSize=512m`; exclude Studio dirs from AV; Preferences > Talend > Performance (`Deactivate auto detect/update`); Help > Feature Manager offline. |
| `javax.net.ssl.SSLHandshakeException: PKIX path building failed: unable to find valid certification path to requested target` | Self-signed/corporate CA not in the JVM truststore used by the job | `keytool -importcert -alias corp -file ca.cer -keystore $JAVA_HOME/lib/security/cacerts -storepass changeit` on every runtime, or `tSetKeystore` (TrustStore file/password) at job start, or `-Djavax.net.ssl.trustStore=...` JVM params; never `trustAllCerts`. |
| FTP `java.net.SocketException: Connection reset` / hangs on `LIST` / `425 Can't open data connection` | Active mode through firewall/NAT; FTPS implicit vs explicit; wrong `Encoding` | tFTPConnection `Connection Mode` = `Passive`; `SFTP` instead of FTP when possible; set `Transfer mode` Binary; increase `Timeout`? (unverified). |
| `javax.mail.AuthenticationFailedException` from tSendMail | Provider requires app password / OAuth2 (Gmail, Office365 basic auth disabled), wrong port/TLS combo | Use app password or relay without auth; `Port` 587 + `STARTTLS support` (not `SSL support` 465 with STARTTLS); Office365: SMTP AUTH enabled per mailbox; check `Need authentication`. |
| `java.sql.SQLException: No suitable driver found for jdbc:...` | Driver jar not in build (`Driver JAR` empty), JDBC URL typo, generic tJDBC without `Driver Class` | Fill `Driver JAR` (Modules) and `Class Name` (`org.postgresql.Driver`); check URL prefix. |
| `java.sql.SQLRecoverableException: IO Error: The Network Adapter could not establish the connection` (Oracle) | Host/port/service name wrong, listener down, firewall | `tnsping`, check `SERVICE_NAME` vs `SID` in connection (`Connection type` `SID`/`Service Name`); context values. |
| `Lock wait timeout exceeded` / `deadlock detected` during load | Parallel inserts/updates on the same table/rows; long-open transaction from another tDBConnection in the same job | Serialize loads to one table; commit more often; one connection per table; avoid Iterate + shared connection with uncommitted rows. |
| `Data truncation: Data too long for column` / `ORA-12899: value too large for column` / `String or binary data would be truncated` | Schema length smaller/larger than table; multi-byte chars | Align schema `Length` with DB (`Retrieve Schema`); `tSchemaComplianceCheck` to reject; `SUBSTR` in tMap `StringHandling.LEFT`. |
| `Duplicate entry` / `ORA-00001: unique constraint violated` / `duplicate key value violates unique constraint` | Source has duplicates, rerun without idempotency, parallel loads | `tUniqRow` upstream, upsert, delete-by-run-date before insert, reject link to a quarantine table. |
| Rows silently missing from target with `Die on error` checked and no exception | Filter in tMap output (`Expression filter`), inner join rejects dropped, `Limit` on input, `Footer` eating rows, `Skip empty rows` | Count `_NB_LINE` at every link (Statistics), add `Catch lookup inner join reject` and `Catch output reject` outputs. |
| Job succeeds in Studio, fails on JobServer with `Context parameter ... not set` or null context | Context values only in Studio's `Default`, deployed with another context; TAC overrides; implicit context file missing on server | Build with correct context, set TAC/TMC parameters, check implicit load file path per host; `Print Parameters`. |
| `java.lang.IllegalArgumentException: Illegal group reference` / `PatternSyntaxException` in tReplace/tMap | Replacement string contains `$`; regex metachars in a literal pattern | `java.util.regex.Matcher.quoteReplacement()` / `Pattern.quote()`; untick `Use regular expression` in tReplace. |
| `code too large` compile error | Giant tMap/tJava generates a method > 64 KB | Split tMap, move logic to routines, split job; Studio 8 code splitting option. |
| TMC publish from Studio fails `Artifact already exists` / `409` | Same version already published | Bump job version (M/m) or enable overwrite in Publish dialog (allowed for `-SNAPSHOT`? unverified); use CI with `-Dtalend.cloud...` params. |
| Job output differs between Windows Studio and Linux server (sorting, upper/lower case, decimals) | Locale/collation differences, `TalendDate.getDate` formats, `String.toUpperCase()` locale, path case sensitivity | Set `-Duser.language=en -Duser.country=US -Dfile.encoding=UTF-8` in JVM params; use `toUpperCase(Locale.ROOT)`; sort in DB with explicit collation. |

## 5. Design review scorecard

Score each line 0 (missing), 1 (partial), 2 (good). Below 70% of max = rework
before PROD. Items marked `*` are blockers at 0.

| # | Area | Question | 0 / 1 / 2 criteria |
|---|---|---|---|
| 1* | Schema / nullability | Every nullable source column is `Nullable`; keys marked `Key`; lengths/precision realistic; file Date columns have `Date Pattern` | 2 = all; 1 = minor; 0 = NPE risk or missing keys for Update |
| 2* | Error handling | OnSubjobError/tLogCatcher present; `Die on error` deliberate; rejects routed; job exits non-zero on failure | 0 = silent swallow or error path missing |
| 3* | Transactions | Commit boundaries match restart unit; rollback on error; no truncate before successful source read unless acceptable | 0 = partial loads possible without detection |
| 4* | Context & secrets | No hardcoded host/path/credential; passwords typed `Password`; `Default` context safe; env override mechanism (`--context_param`/implicit load/TAC) documented | 0 = any secret literal or PROD default |
| 5 | Performance | Batch on outputs; lookups sized; streaming inputs; bulk for > 1M rows; no row-by-row tDBRow; no tLogRow | 0 = known > 1 h for < 1M rows |
| 6 | Logging & monitoring | Stats & Logs or control table; alert on failure; log level configurable; useful tWarn for anomalies | 0 = stdout only |
| 7 | Idempotency / restart | Rerun safe (upsert/truncate/delete-by-date); watermark after commit; files moved after commit; checkpoints or skip logic | 0 = rerun duplicates data |
| 8 | Documentation | Job `Purpose`/`Description`; tMap/tJava comments; README or generated HTML doc; data lineage of inputs/outputs | 0 = nothing |
| 9 | Naming | Jobs/components/flows/contexts follow 1.3; no `tMap_7`/`row12` on non-trivial jobs | 0 = default names everywhere |
| 10 | Tests | Test case or TEST_ job with reference data; edge cases (nulls, empty file, duplicates) | 0 = none |
| 11 | Deployment readiness | Builds with no missing modules; JVM args set; version bumped; tRunJob children `Latest`; TAC/TMC task parameters listed; runtime Java matches | 0 = build fails or Java mismatch |
| 12 | Parallel safety | No shared connection/tHash/globalMap across parallel branches; temp dirs per thread | n/a if sequential |
| 13 | Dependencies | External jars via Modules with versions; routines in reference project; no duplicate libs | - |
| 14 | Data quality gates | tSchemaComplianceCheck or equivalent on ingest; rejects persisted; counts reconciled (source vs target) | - |

## 6. Template: explain a Talend job

Fill after reading the `.item` (see artifact-formats.md for XML structure; use
`../scripts/inspect_job_item.py <path>.item` to list components, links,
contexts and parameters). Keep to one screen.

```
JOB <NAME> v<M.m>  (project <P>, folder <layer>, type Standard|Spark Batch|Route)
Purpose: <one sentence from Main tab Purpose/Description, or inferred>

INPUTS
  - <tDBInput_x>  <DB/connection> table/query: <summary>, filter: <where>, incremental? <watermark var>
  - <tFileInputDelimited_y> <path expr>, mask, encoding, header, CSV options
  - lookups: <tDBInput_z> (<rows est>), model Load once/Reload, join Left/Inner, match Unique/First/All

OUTPUTS
  - <tDBOutput_t> <table>, Action on table <..>, Action on data <..>, batch <n>, commit <n>, rejects -> <where>
  - files/APIs/mails: <...>

TRANSFORMATIONS (per subjob, in trigger order)
  1. <subjob start> -> ... : <what it does>; notable tMap expressions: <3-5 bullets>; filters; aggregations; dedup keys
  2. ...
  Error path: <OnSubjobError -> ...>; Die on error settings: <...>

CONTEXTS
  - group <CTX_...>: <VAR>=<type> (<purpose>), ... ; environments: Default/DEV/TEST/PROD; implicit load: <yes/no, from>
  - secrets: <vars typed Password>

DEPENDENCIES
  - child jobs (tRunJob): <names + Transmit whole context? independent process?>
  - joblets, routines, metadata connections, external jars (Modules), DB objects (tables/sequences/procs)
  - scheduler: TAC task / TMC task / plan; trigger; JVM params; expected runtime; row volumes

RISKS / REVIEW NOTES
  - <scorecard findings: nullability, hardcoded values, commit sizes, Reload misuse, tLogRow, missing close ...>
```

## 7. Procedure: generate a job from a spec

1. Clarify the spec into the template of section 6 (inputs, outputs,
   transformations, contexts, dependencies, volumes, schedule). Pick the
   pattern(s) from section 2 and the review constraints from section 5.
2. Choose the authoring route:
   - Studio by hand (default for anything with tMap logic): the user drags
     components; give them the exact component list, link types, settings
     table per component (label/value), tMap expressions, context group and
     subjob order as an ASCII diagram.
   - Jobscript (`.jobscript`, Enterprise): generate text (`addComponent {...}`
     `setSettings {...}` `addConnection {...}` blocks) and import via
     Repository > Job Designs > right-click > `Import Jobscript`? (in 7.x the
     Jobscript view is opened via Job > `Jobscript` tab; paste then `Create job
     from script` (unverified label)). Syntax and component-specific setting
     names: artifact-formats.md (Jobscript section) and help.qlik.com
     "Job Script Reference Guide" (e.g. tFileOutputDelimited settings
     `SPLIT`, `SPLIT_EVERY`, `FLUSHONROW`, `FLUSHONROW_NUM`).
   - Direct `.item` + `.properties` XML (no Enterprise needed, but fragile):
     copy an existing similar job's `.item`, change `<node componentName=...>`
     elements, `<elementParameter>` values, `<metadata>` schemas and
     `<connection>` links; keep ids/`xmi:id` consistent; drop into
     `<project>/process/<folder>/` with a new `.properties` (`id`, `label`,
     `version`); Studio: right-click project > `Refresh`? or re-import via
     File > `Import items`. Validate with `inspect_job_item.py`. See
     artifact-formats.md for element names and the `.properties` id/version
     contract.
   - Component Kit / custom code only when no component fits (apis-sdks.md).
3. Always generate: context group with all environments, tPrejob/tPostjob
   skeleton, tLogCatcher subjob, OnSubjobError path, control-table hooks,
   `Purpose`/`Description` text, and a TEST job or test case data.
4. Hand over the build/deploy steps (deployment-runtime.md): Build Job with
   `Context scripts`, launcher JVM args, TAC/TMC task parameters, and the
   section 5 scorecard filled in.

## 8. Spark and ESB pointers

- Spark Batch/Streaming jobs (big-data-spark.md): patterns map to
  `tFileInputDelimited` (HDFS/S3) -> `tMap`/`tAggregateRow`/`tSqlRow` ->
  `tFileOutputParquet`/`tDeltaLakeOutput`/`tJDBCOutput`; lookups in tMap become
  broadcast or shuffle joins (`Lookup Model` is irrelevant; use `tCacheOut/In`
  for reuse); partitioning via `tPartition`, `tRepartition`? and
  `spark.sql.shuffle.partitions`; checkpointing in Streaming (`Checkpoint
  directory`); memory errors are YARN/K8s container kills (see index); no
  tPrejob/tPostjob semantics on executors (driver only); `tRunJob` from a
  Standard orchestrator submits the Spark job as a child (needs cluster libs).
- ESB Routes and Data Services (esb-routes-services.md): Camel routes
  (`cMessagingEndpoint`, `cProcessor`, `cTalendJob` to call a DI job per
  message), error handling with `cOnException`/`cErrorHandler`, idempotency via
  `cIdempotentConsumer`; REST services with `tRESTRequest`/`tRESTResponse` in a
  DI job deployed to Talend Runtime (Karaf) or as a microservice (Spring Boot
  jar): keep per-request work small, no tPrejob connection sharing across
  requests unless `Use or register a shared DB Connection`; port conflicts and
  TLS truststore issues follow the same fixes as the index.

## Gotchas

| Symptom | Cause | Fix |
|---|---|---|
| Stack trace line numbers point into generated code you cannot see | Error is in `<Job>.java`, not in the design | Open the `Code` view in Studio, `Ctrl+L` to the line number from the trace; the comment block above shows the component unique name; in deployed jobs unzip `lib/<job>.jar` sources? (not included) - rebuild locally and read Code view with the same version. |
| Exception names tMap_1 but the real culprit is upstream | tMap is where a null/type issue is first dereferenced; input components pass nulls through | Add tLogRow/tFilterRow before tMap in DEV, check schema nullability of the input, not the tMap. |
| Job "works in Studio, fails deployed" and you debug the job | Differences are environmental: JVM args, working dir, context, Java version, modules, timezone, file permissions | Diff: `java -version`, `--context`, `Print Parameters`, `pwd`, `lib/` listing, env vars; reproduce by running the built launcher on your machine first. |
| Debugging with `Traces Debug` on million-row flows | Trace mode slows execution 100x and can hang Studio | Use `Limit` on inputs or `Extract lines at random`, or `tSampleRow`, and a DEV context pointing to small data. |
| Reproducing a PROD failure with PROD context from Studio | Risk of writing to PROD; Studio machine lacks network/jars | Clone the context group to `DEBUG` with read-only credentials and local output paths; never run with `--context=PROD` from a workstation. |
| Error message from TAC/TMC is only `Job failed with exit code 1` | The useful text is in the job stdout/stderr, not the task status | Open the task `Logs`; search for `Exception in component`; enable `tStatCatcher`/`tLogCatcher` to DB for history; raise `Log4j level` to DEBUG for one run only. |
| Searching the error text finds nothing because it includes dynamic values | Message contains table/file names, pids | Search the stable part (`Unparseable date`, `cannot be cast to`, `ORA-01000`) and the component type. |
| Fixing by adding `try/catch` in tJavaRow hides data loss | Swallowed exceptions drop rows silently | Route caught rows to a reject output (`tJavaRow` cannot, use tMap with validation expressions or `tSchemaComplianceCheck`) and count them; fail the job above a threshold. |
| Multiple fixes applied at once (heap + batch + driver) and the job runs: unknown which worked | No baseline measurement | Record `Exec time`/rows per second before, change one setting at a time, keep the Statistics screenshot in the ticket. |
| Component help page does not list the option you see (or vice versa) | Options differ per version (7.3 vs 8.0 Rxxxx) and per DB flavour (tMysqlOutput vs generic tDBOutput with `Database` type) | Check the page for your exact version at help.qlik.com `components/8.0/<family>/<component>-standard-properties`; prefer the DB-specific component when an option is missing on generic tDBOutput. |

## Sources

https://help.qlik.com/talend/en-US/components/8.0/orchestration/trunjob-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/orchestration/trunjob-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/system/trunjob-properties-for-apache-spark-batch
https://help.qlik.com/talend/en-US/components/8.0/tmap/tmap-lookup-models
https://help.qlik.com/talend/en-US/components/7.3/tmap/tmap-lookup-models
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-09/handling-lookups
https://community.qlik.com/t5/Talend-Studio/resolved-Getting-rows-which-not-gets-updated/td-p/2333377
https://help.qlik.com/talend/en-US/components/8.0/scd/scd-management-methodology
https://help.qlik.com/talend/en-US/components/8.0/scdelt/tdb2scdelt
https://help.qlik.com/talend/en-US/components/8.0/scd/tmysqlscd-tfixedflowinput-tmysqlinput-tmysqlclose-inserting-employee-data-into-mysql-table-using-scd-standard-component
https://help.qlik.com/talend/en-US/components/7.2/sqlite/tsqliteoutput-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/netezza/tnetezzaoutput
https://help.qlik.com/talend/en-US/components/8.0/ingres/tingresoutput
https://help.qlik.com/talend/en-US/components/7.2/informix/tinformixoutput-standard-properties
https://help.qlik.com/talend/en-US/administration-center-user-guide/8.0/accessing-error-recovery-management-page
https://help.qlik.com/talend/en-US/administration-center-user-guide/7.2/what-are-recovery-checkpoints
https://help.qlik.com/talend/en-US/administration-center-user-guide/8.0/how-to-access-checkpoint-list
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-05/recovering-job-execution-in-case-of-failure
https://help.qlik.com/talend/en-US/restart-failed-job/8.0/restartability-example
https://help.qlik.com/talend/en-US/talend-glossary/Cloud/recovery-checkpoint
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-09/executing-multiple-subjobs-in-parallel
https://community.qlik.com/t5/Talend-Studio/Multithread-Looping/td-p/2271316
https://community.qlik.com/t5/Talend-Studio/Multithread-with-tflowtoiterate-in-TOS-to-process-set-of-rows/m-p/2321400
https://community.qlik.com/t5/Talend-Studio/Parallel-execution-takes-more-time-than-the-non-parallel/m-p/2270846
https://community.qlik.com/t5/Talend-Studio/parallel-execution-of-jobs-or-components/td-p/2256864
https://community.qlik.com/t5/Talend-Studio/improve-job-performance-and-execution-time/td-p/2223099
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-04/sorting-input-records
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-11/sorting-input-records
https://help.qlik.com/talend/en-US/components/7.2/delimited/tfileoutputdelimited-standard-properties
https://help.qlik.com/talend/en-US/job-script-reference-guide/8.0/component-specific-settings-for-tfileoutputdelimited
https://help.qlik.com/talend/en-US/components/8.0/ms-delimited/tfileoutputmsdelimited
https://help.qlik.com/talend/en-US/components/8.0/mysql/tmysqloutputbulk
https://help.qlik.com/talend/en-US/components/7.3/xml-connectors/tfileoutputxml-standard-properties
https://community.qlik.com/t5/Talend-Studio/Custom-the-flush-buffer-size-quot-on-the-tFileOutputDelimited/m-p/2295236
