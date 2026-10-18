# Core component families: Database, File, Processing, schema and data types (Standard Jobs)

> Verification: doc-derived (help.qlik.com / help.talend.com search snippets, Talend GitHub, Maven Central) plus model knowledge. Not exercised against a live Studio/TAC/TMC in this build. Items marked (unverified) are from memory only and should be checked in Studio before relying on exact labels.

Scope: Standard (Data Integration) Jobs only. Not here: tMap/tXMLMap/tELTMap expression
internals (tmap-expressions.md), Orchestration/Logs/Misc/System (orchestration-logging.md),
cloud/SaaS/NoSQL/messaging connectors incl. BigQuery, Databricks, Hive (connectors-catalog.md,
big-data-spark.md), Spark components (big-data-spark.md), DQ components (data-quality-governance.md).

## Contents
- [Conventions used below](#conventions-used-below)
- [1. Database family](#1-database-family)
  - [1.1 Unified tDB* components and the Database dropdown](#11-unified-tdb-components-and-the-database-dropdown)
  - [1.2 Component catalog](#12-component-catalog)
  - [1.3 Connection settings (shared by all tDB*)](#13-connection-settings-shared-by-all-tdb)
  - [1.4 tDBInput settings](#14-tdbinput-settings)
  - [1.5 tDBOutput settings](#15-tdboutput-settings)
  - [1.6 tDBRow / tDBSP / tParseRecordSet](#16-tdbrow--tdbsp--tparserecordset)
  - [1.7 Transactions: tDBConnection / tDBCommit / tDBRollback / tDBClose](#17-transactions-tdbconnection--tdbcommit--tdbrollback--tdbclose)
  - [1.8 Bulk loading](#18-bulk-loading)
  - [1.9 SCD components](#19-scd-components)
  - [1.10 CDC components](#110-cdc-components)
  - [1.11 ELT components (summary)](#111-elt-components-summary)
- [2. File family](#2-file-family)
  - [2.1 Delimited / positional / regex / raw](#21-delimited--positional--regex--raw)
  - [2.2 XML and JSON](#22-xml-and-json)
  - [2.3 Excel, properties, LDIF, ARFF, EBCDIC, Avro, Parquet](#23-excel-properties-ldif-arff-ebcdic-avro-parquet)
  - [2.4 File management](#24-file-management)
  - [2.5 Schema metadata for files: date patterns, decimal separators](#25-schema-metadata-for-files-date-patterns-decimal-separators)
- [3. Processing family (non-map)](#3-processing-family-non-map)
- [4. Data types in a component schema](#4-data-types-in-a-component-schema)
- [5. Schema propagation rules and Dynamic schema](#5-schema-propagation-rules-and-dynamic-schema)
- [6. Database-specific notes](#6-database-specific-notes)
- [Gotchas](#gotchas)
- [Sources](#sources)

## Conventions used below
- Settings labels are given as they appear in the Component view (Basic settings /
  Advanced settings tabs). Studio 8.0 (monthly R20xx-xx releases) is the baseline; 7.3 differences noted.
- globalMap variables are read as `((Integer)globalMap.get("tDBOutput_1_NB_LINE"))`. Type:
  NB_* are Integer, ERROR_MESSAGE / QUERY / CURRENT_FILE* are String. Variables are
  "After" variables (set after the component finishes its subjob) unless noted "Flow" (set per row).
- The Outline view (bottom-left of Studio) lists every component's exposed variables; Ctrl+Space in
  any expression field autocompletes them.
- "Reject" row = a second output link available on many input/output components; it carries the
  input schema plus two String columns `errorCode` and `errorMessage` (added automatically, must be
  kept at the end of the reject schema).

## 1. Database family

### 1.1 Unified tDB* components and the Database dropdown
Since Studio 7.x the Palette shows generic `tDBConnection`, `tDBInput`, `tDBOutput`, `tDBRow`, ...
under Databases > DB Specifics is replaced by a `Database` dropdown in Basic settings (for a new
component a dialog "Select the database type" opens first). Choosing a value swaps the component for
the legacy specific component underneath: the generated Java and the `.item` XML reference the
specific component name (e.g. `tMysqlInput`), and the component label in the Designer becomes
`tDBInput_1` but the Component view shows the specific component's settings. Legacy components can
still be placed via the Palette search and are 1:1 the same thing.

| `Database` dropdown value | Legacy component prefix | Notes |
|---|---|---|
| MySQL | tMysql* | DB Version: MySQL 5 / MySQL 8 / MariaDB 10 (8.0 R2020+); connector-j jar per version |
| Amazon Aurora | tAmazonAurora* | MySQL-compatible; DB Version Aurora MySQL 5.6/5.7/8 (unverified exact list) |
| Oracle | tOracle* | Connection type: Oracle SID / Oracle Service Name / Oracle OCI / Oracle Custom / Oracle RAC / WALLET; DB Version 11/12/18/19/21 |
| PostgreSQL | tPostgresql* | also PostgresPlus (tPostgresPlus*) for EDB |
| Microsoft SQL Server | tMSSql* | JDBC Provider: Open source JTDS / Microsoft; also Azure SQL |
| Azure Synapse | tAzureSynapse* | 8.0; bulk via tAzureSynapseBulkExec |
| Amazon Redshift | tRedshift* | plus tRedshiftBulkExec / tRedshiftUnload / tRedshiftOutputBulk |
| Snowflake | tSnowflake* | Account/Region/Warehouse/Schema/Role; tSnowflakeOutput has Table Action/Output Action |
| DB2 | tDB2* | db2jcc4 jar; Schema mandatory |
| Teradata | tTeradata* | plus TPT/FastLoad/MultiLoad/TPump/FastExport exec components |
| Vertica | tVertica* | Vertica 9/10/11/12; COPY via tVerticaBulkExec |
| Greenplum | tGreenplum* | gpload via tGreenplumGPLoad |
| Netezza | tNetezza* | nzjdbc jar; tNetezzaBulkExec uses external table |
| Exasol | tExasol* | 7.0+ (unverified first version) |
| SAP HANA | tSAPHana* | ngdbc jar |
| Sybase | tSybase* | ASE / IQ (jconn4); tSybaseIQ* for IQ-specific bulk |
| Informix | tInformix* | ifxjdbc jar; Server name required |
| AS400 | tAS400* | jt400 jar |
| SQLite | tSQLite* | file DB, Database = path |
| HSQLDb | tHSQLDb* | Running Mode: HSQLDb Server / WebServer / In Process Persistent / In Memory |
| Access | tAccess* | UCanAccess driver (8.0), Jet/ODBC earlier |
| Firebird | tFirebird* | Jaybird driver |
| Ingres / VectorWise | tIngres*, tVectorWise* | Actian Vector/Avalanche reached via JDBC generic or tVectorWise* (unverified current naming) |
| MaxDB | tMaxDB* | |
| Derby (JavaDB) | tJavaDB* | |
| SingleStore (MemSQL) | tSingleStore* | 7.3+ |
| JDBC | tJDBC* | generic: JDBC URL + Drivers table + Driver Class + Mapping |
| Hive, Impala, BigQuery, Databricks, Delta Lake | tHive*, tImpala*, tBigQuery*, tDeltaLake* | big-data-spark.md / connectors-catalog.md |

Not every component exists for every DB: e.g. tDBSCD exists for MySQL, Oracle, PostgreSQL, MSSQL, DB2,
Teradata, Sybase, Informix, Netezza, Greenplum, Vertica (unverified full list); tDBCDC only for
MySQL, Oracle, PostgreSQL, MSSQL, DB2, AS400, Sybase, Informix, Teradata, Ingres (unverified full list).
`tDBFetch` does not exist as a Standard component (there is no tDBFetch; the row-fetching variants are tDBInput and tDBRow with Propagate QUERY's recordset).

### 1.2 Component catalog

| Component | Purpose | Key settings | globalMap (After unless noted) | Notes |
|---|---|---|---|---|
| tDBConnection | Open a connection reused by downstream components | all connection fields (1.3), Auto Commit, Use or register a shared DB Connection | ERROR_MESSAGE | Place at start of subjob; connect with OnSubjobOk. Does not auto-close: use tDBClose or TAC/JobServer will leak connections |
| tDBInput | SELECT, emit rows on Main | Query, Guess Query, Guess schema, Use cursor / Fetch size, Trim all String/Char columns, Enable Mapping File for Dynamic | NB_LINE, QUERY, ERROR_MESSAGE | Schema columns must match query column order, not names |
| tDBOutput | INSERT/UPDATE/DELETE from Main | Table, Action on table, Action on data, Die on error, Use batch mode/Batch Size, Commit every, Additional Columns, Use field options | NB_LINE, NB_LINE_INSERTED, NB_LINE_UPDATED, NB_LINE_DELETED, NB_LINE_REJECTED, QUERY, ERROR_MESSAGE | Reject link with errorCode/errorMessage only when Die on error is off and batch mode is off |
| tDBRow | Execute arbitrary SQL (DDL/DML/call) per subjob or per incoming row | Query, Die on error, Propagate QUERY's recordset, Use PreparedStatement, Commit every | QUERY, ERROR_MESSAGE, NB_LINE (some DBs, unverified) | No NB_LINE_INSERTED etc.; count via tDBOutput or a SELECT ROW_COUNT() |
| tDBCommit | COMMIT on an existing connection | Component List, Close Connection (checked by default) | ERROR_MESSAGE | Uncheck Close Connection if more subjobs follow |
| tDBRollback | ROLLBACK on connection | Component List, Close Connection | ERROR_MESSAGE | Attach via OnComponentError / OnSubjobError |
| tDBClose | Close connection | Component List | ERROR_MESSAGE | Always run at job end (OnSubjobOk from last subjob) |
| tDBSP | Call stored procedure | SP Name, Is Function / Return result in, Parameters table (Schema column -> Type IN/OUT/IN OUT/RECORDSET) | ERROR_MESSAGE, NB_LINE (unverified) | RECORDSET parameter type (Oracle REF CURSOR, MSSQL result set) requires an Object column + tParseRecordSet |
| tDBBulkExec | Server-side bulk load of an existing file into table | Table, Action on table, File Name, Field/Row separator, encoding, DB-specific options (1.8) | NB_LINE (not for every DB), ERROR_MESSAGE | File must be reachable by the DB server (or client-side for MySQL LOCAL) |
| tDBOutputBulk | Write Main flow to a flat file formatted for the bulk loader | File Name, Append, Field separator, Include header, Row separator, Create directory | NB_LINE, ERROR_MESSAGE | Pair with tDBBulkExec via OnSubjobOk |
| tDBOutputBulkExec | tDBOutputBulk + tDBBulkExec in one | union of both | NB_LINE, ERROR_MESSAGE | Convenience; no reject flow |
| tDBSCD | Slowly Changing Dimension load (Type 0/1/2/3) | SCD Editor (Source keys, Surrogate key, Type 0/1/2/3 fields, start/end date, version, active), Use batch mode (unverified per DB) | NB_LINE, NB_LINE_INSERTED, NB_LINE_UPDATED, NB_LINE_REJECTED (unverified), ERROR_MESSAGE | Dimension table must already exist (Action on table: None / Create / ...) |
| tDBSCDELT | SCD executed as SQL on the DB (source and target tables in same DB) | Source table, Target table, SCD Editor, Use batch (unverified) | NB_LINE_INSERTED, NB_LINE_UPDATED, ERROR_MESSAGE | Only Type 1/2 (Type 3 unsupported in SCDELT, unverified) |
| tDBCDC | Read captured changes for a subscriber from CDC tables | Schema using CDC, Table using CDC, Subscriber, Events to catch (Insert/Update/Delete), Keep data in CDC table | NB_LINE, ERROR_MESSAGE | Subscription set up via Repository > Metadata > Db Connections > CDC Foundation |
| tDBCDCOutput | Publish changes into a CDC table (for DBs without trigger support, e.g. Teradata) | CDC Table, Source Table, Action on data | NB_LINE | Rare; mainly Teradata/AS400 (unverified) |
| tDBColumnList | Iterate over the columns of a table | Table Name | COLUMN_NAME (Flow), NB_COLUMN (unverified) | Use with Iterate link; access `globalMap.get("tDBColumnList_1_COLUMN_NAME")` |
| tDBTableList | Iterate over tables of a schema | Where clause, table type filter | CURRENT_TABLE (Flow), NB_TABLE | pairs with tDBColumnList for metadata-driven jobs |
| tDBLastInsertId | Return auto-increment id of last INSERT on a connection | Component List | LAST_INSERT_ID (unverified name) | Adds column `last_insert_id` (Long) to flow; MySQL `LAST_INSERT_ID()`, MSSQL `@@IDENTITY`/`SCOPE_IDENTITY` |
| tDBInvalidRows / tDBValidRows | Split rows by DQ validation rule / SQL pattern | Validation rule or Custom pattern | NB_LINE | DQ licence; see data-quality-governance.md |
| tCreateTable | Generate CREATE TABLE from schema | Database Type, Table Name, Action on table | ERROR_MESSAGE | Separate component in Databases family, maps Talend types via mapping file |
| tParseRecordSet | Explode an Object column holding a java.sql.ResultSet into rows | Prev. Comp. Column list, Attribute table (schema col -> result set column name) | NB_LINE | Required after tDBRow Propagate QUERY's recordset or tDBSP RECORDSET |

### 1.3 Connection settings (shared by all tDB*)
| Setting | Values / behaviour |
|---|---|
| Database | dropdown (1.1); the resulting specific component name is what the .item stores |
| Property Type | Built-In (type values here) or Repository (pick a Metadata > Db Connections item; fields become read-only and are generated as `context.xxx` if the metadata was exported to a context group) |
| Use an existing connection | checkbox + Component List of tDBConnection_N in the job (incl. parent job via shared connection). Hides host/port/login fields |
| DB Version | per database (e.g. MySQL 5 / MySQL 8, Oracle 12-21, Postgres V9.x-V15, MSSQL 2016-2022); drives which driver module is loaded |
| Host / Port / Database / Schema | String expressions (`"localhost"`, `context.db_port`); Schema mandatory on Oracle/DB2/Postgres/MSSQL for Guess Query to work |
| Username / Password | Password field encrypted in .item; use `context.db_pwd` typed Password |
| Additional JDBC Parameters | appended to URL: `"noDatetimeStringSync=true&useSSL=false&allowLoadLocalInfile=true"` (MySQL), `"ssl=true&sslmode=require"` (Postgres), `"encrypt=true;trustServerCertificate=true"` (MSSQL Microsoft driver uses `;`) |
| Mapping | Advanced: which type-mapping file to use (`mapping_mysql.xml` ...), see section 4 |
| Auto Commit | tDBConnection only: commit after each statement; with it off you must add tDBCommit |
| Use or register a shared DB Connection | tDBConnection: `Shared DB Connection Name` string; child jobs (tRunJob) pick it up with the same name. Incompatible with tRunJob "Use an independent process" and "Use dynamic job" |
| Specify a data source alias | tDBConnection in Talend Runtime/ESB only: JNDI alias; unavailable when shared connection is checked |
| Use Transactions / tDBConnection in ESB | (unverified label) |
| Enable debug mode | Advanced (Output/Row): prints every executed SQL statement to the console |
| Use PreparedStatement | tDBRow/tDBInput Advanced: `?` placeholders + Set PreparedStatement Parameters table (Parameter Index, Parameter Type, Parameter Value) |
| Encoding | Advanced on some DBs (Oracle/Postgres input): charset for string decoding |
| tStatCatcher Statistics | Advanced on every component: feed tStatCatcher |

### 1.4 tDBInput settings
| Setting | Behaviour |
|---|---|
| Schema (Built-In / Repository) + Edit schema | Column order must match the SELECT list order; names are irrelevant to JDBC fetch (`rs.getXXX(index)`). Use `Sync columns` only on downstream components |
| Table Name | used by Guess Query / Guess schema only; the Query is what runs |
| Query Type | Built-In / Repository (SQL from Metadata > Db Connections > Queries) |
| Guess Query | builds `SELECT <cols> FROM <table>` with DB-specific quoting (`` `col` `` MySQL, `"col"` Postgres/Oracle, `[col]` MSSQL) |
| Guess schema | runs the query, infers Talend types via the mapping file; review BigDecimal vs Long results |
| Query | Java String expression: `"SELECT id, name FROM customers WHERE created > '" + context.since + "'"`; multi-line editor via `...` button; use `\"` for embedded double quotes |
| Use cursor / Fetch size (Postgres, Oracle "Use cursor", MySQL "Enable stream") | sets `Statement.setFetchSize(n)` so rows stream instead of loading the whole result set; Postgres cursor only works with Auto Commit off (needs transaction) |
| Trim all the String/Char columns / Trim column table | per-column trim of leading/trailing whitespace (CHAR padding) |
| Enable Mapping File for Dynamic | Advanced: how Dynamic column types are inferred |
| Allow special name for schema column names (unverified label) | keep reserved words/spaces in column names |
| Die on error | default checked; unchecked = error logged, subjob continues to next component |
| Convert Timestamp to Date / Use Oracle date as timestamp | Oracle-specific (see section 6) |
| Advanced > Use the Repository query / Use Jdbc escape (unverified) | |

Lookup mode: when tDBInput feeds a tMap lookup input with "Reload at each row", the query may reference
`globalMap` keys set in the tMap lookup expression (see tmap-expressions.md).

### 1.5 tDBOutput settings
| Setting | Values / behaviour |
|---|---|
| Table | String expression; `context.schema + ".target"` works only if Schema field left empty (DB-dependent quoting) |
| Action on table | None / Drop and create table / Create table / Create table if does not exist / Drop table if exists and create / Clear table (DELETE) / Truncate table. Create uses the mapping file to derive DDL; Length/Precision from schema |
| Action on data | Insert / Update / Insert or update / Update or insert / Delete / Replace (MySQL `REPLACE INTO`) / Insert if not exist (MySQL `INSERT IGNORE`-like, unverified exact DBs) / Insert ignore (MySQL) / Upsert-merge on Oracle (`Insert or update` is implemented as INSERT then UPDATE on duplicate-key error, NOT MERGE, except Snowflake/Teradata which generate MERGE) |
| Schema | keys (checkbox `Key` in Edit schema) are what Update/Delete use for the WHERE clause unless Use field options overrides |
| Die on error | checked: first SQL error kills the job (exit code 1). Unchecked: failing row goes to Reject link, job continues, NB_LINE_REJECTED increments |
| Use batch mode / Batch Size (Advanced) | `addBatch()/executeBatch()` every N rows (default 10000 for MySQL, 100 for others, unverified). Only for Insert / Update / Delete actions. Disables per-row Reject rows (whole batch fails; only ERROR_MESSAGE) |
| Commit every | number of rows per `commit()` (default 10000). Only shown when Use an existing connection is off; with an existing connection the tDBConnection's Auto Commit / tDBCommit decides. Set Commit every >= Batch size and a multiple of it |
| Additional Columns | table: Name / SQL expression (e.g. `"NOW()"`, `"UPPER(?)"`, `"nextval('seq')"`) / Position (Before / After / Replace) / Reference column. Not available with Use batch mode on most DBs, nor with bulk actions |
| Use field options | table per schema column: Update Key / Deletion Key / Updatable / Insertable (column headers: Column / Update Key / Deletion Key / Updatable / Insertable). Lets you update on a non-PK column or exclude an auto-increment column from INSERT |
| Enable debug mode | print generated SQL per row |
| Support null in "SQL WHERE" statement | generates `col IS NULL` instead of `col = NULL` for key columns that are null in Update/Delete |
| Use Hint Options (Oracle) | `/*+ APPEND */` etc. |
| Convert columns and table to uppercase (Oracle/Snowflake, unverified label) | |
| Use Column Case Sensitive / Use schema keys for "Where" (unverified) | |
| Extend Insert (MySQL) | `INSERT ... VALUES (...),(...)` multi-row statement; `Number of rows per insert`; cannot be combined with Use batch mode or with Reject |
| Use duplicate key update (MySQL) | `ON DUPLICATE KEY UPDATE` with Column / Value table |
| Use existing dynamic schema (unverified exact label: "Use dynamic schema") | with a Dynamic column the component builds INSERT/CREATE TABLE at runtime from the Dynamic metadata |
| Use update statement without subqueries (MSSQL) / Identity insert (MSSQL `SET IDENTITY_INSERT ON`) | DB-specific |

Reject link: available only when Die on error is unchecked and (Use batch mode off or, on
some DBs, batch on but with per-batch rejects unsupported). Columns = input schema + `errorCode`
(String, vendor SQLState/error code) + `errorMessage` (String). Typical pattern: tDBOutput --reject--> tFileOutputDelimited.

### 1.6 tDBRow / tDBSP / tParseRecordSet
- tDBRow runs `Query` once per incoming row when connected via Main, once when started by a trigger.
  Each row can embed input values: `"UPDATE t SET x='" + row1.x + "' WHERE id=" + row1.id`, or safer with
  Use PreparedStatement (`"UPDATE t SET x=? WHERE id=?"` + parameters `row1.x` / `row1.id`; Parameter Type
  from the Talend type list: Int, String, Date, BigDecimal, Boolean, ...).
- Multiple statements in one Query: MySQL needs `allowMultiQueries=true` in Additional JDBC
  Parameters; Oracle needs an anonymous `BEGIN ... END;` block; Postgres accepts `;`-separated statements.
- `Propagate QUERY's recordset`: Advanced checkbox + `use column` (an Object-typed column of the
  output schema). The ResultSet is placed in that column; follow with tParseRecordSet (Prev. Comp.
  Column list = that column; Attribute table maps schema columns to result-set column names).
  tDBRow output schema may differ from input in this mode.
- tDBRow `Commit every` only shows without an existing connection; with Auto Commit off and no
  tDBCommit, DDL commits implicitly on most DBs but DML is lost.
- tDBSP: `SP Name`, `Is Function / Return result in` (pick the schema column receiving the return
  value), Parameters table: Schema Column, Type = IN / OUT / IN OUT / RECORDSET. Output columns for
  OUT params must exist in the schema. Oracle REF CURSOR -> RECORDSET into an Object column ->
  tParseRecordSet. MSSQL SPs returning result sets: use tDBInput with `"EXEC dbo.proc @p=1"` instead
  (simpler) or RECORDSET.
- tDBRow globalMap: QUERY (the last executed SQL text) and ERROR_MESSAGE. No reliable NB_LINE for
  affected rows; use `SELECT ROW_COUNT()` (MySQL) / `@@ROWCOUNT` (MSSQL) / `GET DIAGNOSTICS` in a follow-up
  tDBInput, or Propagate QUERY's recordset with `UPDATE ... RETURNING`.

### 1.7 Transactions: tDBConnection / tDBCommit / tDBRollback / tDBClose
```
tDBConnection_1 (Auto Commit off)
  --OnSubjobOk--> tFileInputDelimited_1 --Main--> tDBOutput_1 (Use an existing connection: tDBConnection_1)
                     --OnSubjobOk--> tDBCommit_1 (Component List: tDBConnection_1, Close Connection: checked)
                     --OnSubjobError--> tDBRollback_1 (Close Connection: checked)
```
- Without `Use an existing connection`, every tDB* component opens its own connection and commits
  per `Commit every`; there is no cross-component transaction.
- With an existing connection and Auto Commit off, nothing is committed until tDBCommit; a job
  that dies before tDBCommit loses everything (desired for all-or-nothing loads).
- tDBCommit/tDBRollback/tDBClose `Close Connection` default checked; a later subjob using the same
  connection then fails with "Connection is closed" / "No operations allowed after connection closed".
- Shared connection: tDBConnection `Use or register a shared DB Connection` + name; in the child job
  put a tDBConnection with the same name and the same checkbox (child-side fields otherwise ignored).
- MySQL `autoReconnect=true` and MSSQL `loginTimeout` go in Additional JDBC Parameters; long jobs with
  a single connection open at start may hit `wait_timeout` (MySQL) before the first write.

### 1.8 Bulk loading
| DB | Components | Mechanism | Key settings |
|---|---|---|---|
| MySQL | tMysqlOutputBulk, tMysqlBulkExec, tMysqlOutputBulkExec | `LOAD DATA [LOCAL] INFILE` | Local filename (Load data local infile needs `allowLoadLocalInfile=true` in JDBC params and `local_infile=1` server-side); Action on data: Insert / Update / Replace / Ignore; Field terminated by / Enclosed by / Lines terminated by; Set columns names; Records contain NULL value |
| PostgreSQL | tPostgresqlOutputBulk, tPostgresqlBulkExec, tPostgresqlOutputBulkExec | `COPY table FROM 'file'` executed server-side (file must be readable by the DB host; recent versions can stream via JDBC CopyManager, unverified) | Row separator, Field separator, Null string, File type CSV/Text, Enclosure |
| Oracle | tOracleOutputBulk, tOracleBulkExec, tOracleOutputBulkExec | SQL*Loader (`sqlldr`) invoked locally; Studio writes a `.ctl` control file | Action on data: Insert / Append / Replace / Truncate; `Use existing control file`, Control file path, Field separator, Specify .ctl file's INTO TABLE clause manually, Record format (Fixed/Delimited), Direct Path; requires Oracle client with sqlldr in PATH; NLS_LANG affects encoding |
| MSSQL | tMSSqlOutputBulk, tMSSqlBulkExec, tMSSqlOutputBulkExec | `BULK INSERT` (file must be visible to the SQL Server service) or `bcp` utility (`Use bcp` label unverified) | Action on table, Action on data Insert/Bulk insert, Field terminator, Row terminator, First row, Code page, Keep identity, Check constraints, Fire triggers, Batch size |
| Snowflake | tSnowflakeOutputBulk, tSnowflakeBulkExec, tSnowflakeOutputBulkExec | file -> stage (`PUT` to internal stage, or external S3/Azure stage) -> `COPY INTO` | Storage: Internal / S3 / Azure / GCS; Stage folder; Table Action; Output Action Insert/Update/Upsert/Delete (merge after copy via temp table); Compress by gzip; Use custom Snowflake field delimiter/Line separator; Purge after load; Copy command options (`ON_ERROR`, `FORCE`, `PURGE`) |
| Redshift | tRedshiftOutputBulk, tRedshiftBulkExec, tRedshiftOutputBulkExec, tRedshiftUnload | `COPY table FROM 's3://...'` with IAM role or access key/secret; `UNLOAD` to S3 | S3 bucket/key, Access Key/Secret Key or `Use IAM role` (Role ARN), Data file type Delimited/CSV/JSON/AVRO/Fixed width, Compressed (gzip/lzop/bzip2), Encrypt, Date format/Time format, Fill missing fields, Accept any date, Ignore blank lines, Load region, Truncate columns, Remove quotes, Round decimal; UNLOAD: Parallel, Allow overwrite, Add quotes, Escape, Delimiter, Max file size |
| Teradata | tTeradataFastLoad, tTeradataMultiLoad, tTeradataTPump, tTeradataTPTExec, tTeradataTPTUtility, tTeradataFastExport | invoke Teradata utilities installed locally (`fastload`, `mload`, `tpump`, `tbuild`, `fexp`) with generated scripts | Execution file path, Script generated/`Use existing script`, Load file, Error table, Log table, Work table, Checkpoint, Sessions, Max errors (TPT) |
| Vertica | tVerticaOutputBulk, tVerticaBulkExec, tVerticaOutputBulkExec | `COPY ... FROM LOCAL` / `FROM STDIN` | Exception file, Rejected data file, Direct/Auto/Trickle load method, Enforce length, Abort on error, Skip rows |
| Greenplum | tGreenplumGPLoad, tGreenplumOutputBulk, tGreenplumBulkExec | `gpload` utility (YAML control file generated) or `COPY` | gpload path, Port range, Error table, Local hostname, Insert/Update/Merge, Match columns, Update columns, Encoding, Log errors |
| Netezza | tNetezzaBulkExec, tNetezzaNzLoad, tNetezzaOutputBulk | External table `CREATE EXTERNAL TABLE ... USING (...)` then INSERT SELECT, or `nzload` | Delimiter, Escape char, Date style/Date delim, Max errors, Ctrl chars, Null value, Fill record, Log/Bad dir |
| DB2 | tDB2BulkExec (LOAD via db2 CLP, unverified), tDB2OutputBulk | `LOAD FROM ... OF DEL` | DB2 client required locally |
| Sybase IQ | tSybaseIQOutputBulkExec, tSybaseIQBulkExec | `LOAD TABLE` | |
| Informix | tInformixOutputBulkExec, tInformixBulkExec | `dbload` / `LOAD FROM` (unverified) | |
| Azure Synapse | tAzureSynapseBulkExec | file in Azure Blob/ADLS -> `COPY INTO` / PolyBase external table | Storage account, Container, Credential (Account key / SAS / Managed identity), File format, Identity insert (unverified list) |
| SQLite | tSQLiteOutput only (no bulk) | | |

Common pattern: `tFileInputDelimited --> tDBOutputBulk` (writes temp file) `--OnSubjobOk--> tDBBulkExec`.
Bulk components expose NB_LINE (rows written to file for OutputBulk; rows loaded for BulkExec on
DBs that report it) and ERROR_MESSAGE; no Reject link (rejected rows go to the loader's bad/error
files or error tables).

### 1.9 SCD components
tDBSCD (row-by-row from Studio) and tDBSCDELT (SQL executed inside the DB; source table must already
be in the same DB) share the **SCD Editor** (button in Basic settings). The dimension table must
exist or be created via `Action on table` (None / Create / Create if not exists / Drop and create ...).

| SCD Editor area | Settings | Notes |
|---|---|---|
| Unused | all input columns start here; drag into the other panes | |
| Source keys | one or more input columns that identify the business entity | natural key; drives lookup of the current dimension row |
| Surrogate keys | `name` of the dimension PK column + `creation`: Auto increment (DB identity) / Input field (take a column) / Routine (e.g. `Numeric.sequence("s1",1,1)`) / Table max + 1 / DB sequence (Oracle/Postgres/DB2: `sequence name`) | `complement` column: optional second technical key (unverified) |
| Type 0 fields | columns copied at insert and never updated afterwards | |
| Type 1 fields | overwrite in place (no history) | |
| Type 2 fields | change -> close current row and insert a new version. Versioning options: `start date` (column; creation = input field or job start / execution date), `end date` (column; null or a fixed date `9999-12-31` for current row, label "Set end date to" unverified), `version` (Integer column, increments), `active` (Boolean/String flag `true`/`1`) | Start/end are Date columns in the dimension schema; `L1/L2/L3` labels in older docs correspond to the three optional type-2 attributes start/end + version + active |
| Type 3 fields | keep current value and one previous value: `current value` column + `previous value` column | |

- Output schema of tDBSCD = dimension table schema (incl. surrogate key and SCD technical columns); the
  schema is defined by the SCD editor (not by Sync columns); set the schema before opening the editor.
- Reject link (unverified availability per DB) carries input rows whose source key is null.
- SCDELT additional settings: `Source table`, `Target table` (unverified exact labels), the SQL is a
  sequence of INSERT ... SELECT / UPDATE statements; Type 3 is not supported by SCDELT (unverified).
- Dates: start date default = execution start; for backdated loads use Input field.
- Performance: tDBSCD issues a SELECT per input row to find the current record; sort and
  deduplicate input first (tUniqRow on source key) because two rows with the same key in one run
  produce two type-2 versions with identical start dates.

### 1.10 CDC components
Change Data Capture (Enterprise feature) is configured in the Repository, not in the component:
Metadata > Db Connections > right-click connection > CDC > `Create CDC`, pick the **CDC
Foundation** connection (a schema where `TCDC_*` tables are created), then on each table
`Add CDC` -> `Create Subscriber and Execute SQL Script` dialog: Subscriber name, `Events to catch`
(Insert / Update / Delete), the generated SQL (triggers + change table) is executed. Source tables
need a primary key. Captured changes live in `TCDC_<table>` tables (one row per change with
`TALEND_CDC_SUBSCRIBERS_NAME`, `TALEND_CDC_STATE`, `TALEND_CDC_TYPE` (I/U/D), `TALEND_CDC_CREATION_DATE`
plus the PK columns) and a view per subscriber; subscribers are registered in `TSUBSCRIBERS`
(unverified exact names).

| Mode | DB | Notes |
|---|---|---|
| Trigger mode | MySQL, Oracle, PostgreSQL, MSSQL, DB2, Sybase, Informix, Ingres, Teradata (via tDBCDCOutput, no triggers), AS400 (journal) | default; triggers on source table write PK + operation into TCDC_ table |
| Redo/Archive log mode | Oracle only | reads Oracle redo/archive logs via LogMiner-based mechanism; needs `ARCHIVELOG`, supplemental logging; subscriber tables still used |
| XStream mode | Oracle 11.2+ only | uses Oracle XStream Out (GoldenGate licence); captures full row images |

tDBCDC Basic settings: Database, connection (usually Repository CDC connection), `Schema using CDC`,
`Table using CDC`, `Subscriber` (String), `Events to catch` Insert / Update / Delete checkboxes,
`Keep data in CDC table` (do not mark changes consumed; default off => rows are consumed/removed for
this subscriber), `Limit` (unverified). Output schema = source table columns (from the CDC view).
globalMap: NB_LINE, ERROR_MESSAGE. Trigger mode captures only the PK and operation type: the
component re-reads current values from the source table by joining on the PK, so a row deleted
after being updated appears once with type D and old values unavailable. See patterns-gotchas.md
for CDC design patterns.

### 1.11 ELT components (summary)
Per DB there is a trio tELT<Db>Input / tELT<Db>Map / tELT<Db>Output (generic `tELTInput`,
`tELTMap`, `tELTOutput` with a Database dropdown in 8.0). They generate one `INSERT INTO ... SELECT
... JOIN ...` executed on the DB, no data flows through the Job.
- tELTInput: `Default Table Name` (the table), `Default Schema Name`, schema = table columns
  (Repository metadata recommended). No `Query`. Connects to tELTMap with a link named after the
  table (the link name IS the table alias used in SQL; rename the link to match `Different table
  name` / alias).
- tELTOutput: `Action on data` Insert / Update / Delete / Merge (DB-dependent), `Default Table
  Name`, `Use different table name` + `Table name`, `Use different table alias` + `Table alias` (unverified: alias may be set on the tELTMap output table instead), `Action on table` (Create/Drop...), `Use WHERE conditions table`.
- tELTMap: `Use an existing connection`, `Style` of join (INNER/LEFT OUTER/...) per table, `Add
  alias` (table alias), `Generated SQL Select query` tab shows the SQL. Expression details in
  tmap-expressions.md.
- globalMap: tELTOutput NB_LINE, NB_LINE_INSERTED, ERROR_MESSAGE (docs list no UPDATED/DELETED).

## 2. File family

### 2.1 Delimited / positional / regex / raw
| Component | Purpose | Key Basic settings | Key Advanced settings | globalMap | Notes |
|---|---|---|---|---|---|
| tFileInputDelimited | read CSV/TSV | File name/Stream (String path or `(java.io.InputStream)globalMap.get(...)`), Row Separator (`"\n"`), Field Separator (`";"`), `CSV options` (enables Escape char `"\\"`/`"\""` and Text enclosure `"\""`), Header (rows to skip, 1 = header line), Footer, Limit, Skip empty rows, Uncompress as zip file, Die on error | Advanced separator (for numbers): Thousands separator / Decimal separator; Extract lines at random (+ Number of lines); Trim all columns / Check column to trim; Check each row structure against schema; Check date; Split row before field; Permit hexadecimal (0xNNN) or octal (0NNN) for numeric types; Encoding (ISO-8859-15 / UTF-8 / Custom); Enable parallel execution (Enterprise) | NB_LINE, ERROR_MESSAGE | Reject link (Die on error off): row + errorCode + errorMessage; type-conversion errors (bad date/number) go to reject, structural errors need Check each row structure. CSV options required for quoted fields containing separators or newlines; without it field separator may be a regex-like multi-char string, with it a single char |
| tFileOutputDelimited | write CSV | File Name, Row Separator, Field Separator, Append, Include Header, Compress as zip file, CSV options (Escape char, Text enclosure), Encoding (Advanced) | Advanced separator (for numbers); CSV options; Create directory if not exists (default on); Split output in several files + Rows in each output file; Custom the flush buffer size + Row number; Output in row mode (write line by line, needed for mixed Append writers); Encoding; Don't generate empty file; Throw an error if the file already exist; Use byte length as the cardinality (positional-style padding counts bytes, unverified placement); Row Separator (Advanced on 7.x) | NB_LINE, FILE_NAME (unverified on older versions) | Header is written only when the file is created/overwritten, not on Append to existing file (Include header + Append on existing non-empty file skips header since 6.x); Split names files `name_1.csv`, `name_2.csv` |
| tFileInputPositional | fixed-width read | File name, Row separator, Pattern `"10,20,15,*"` (column widths, `*` = rest), Header/Footer/Limit, Skip empty rows, Die on error, Uncompress as zip | Customize (per-column: Column / Size / Alignment / Padding char), Advanced separator, Trim all columns, Check each row structure, Permit hexadecimal, Encoding | NB_LINE, ERROR_MESSAGE | Widths are in characters; multi-byte encodings may need byte-based option |
| tFileOutputPositional | fixed-width write | File Name, Row separator, Formats table (Column, Size, Padding char, Alignment Left/Right, Keep), Use byte length as the cardinality, Append, Include header | Create directory, Custom flush buffer, Encoding, Don't generate empty file, Throw error if exists | NB_LINE | Values longer than Size are truncated silently unless Keep is checked (unverified semantics of Keep) |
| tFileInputRegex | parse lines with a regex | File name, Row separator, Regex `"^(\\d+);(\\w+)$"` (one capture group per schema column), Header/Footer/Limit, Skip empty rows, Die on error | Encoding, Trim | NB_LINE | Non-matching lines are dropped silently (no reject link, unverified) |
| tFileInputFullRow | each line as one String column `line` | File name, Row separator, Header, Footer, Limit, Skip empty rows, Die on error | Encoding | NB_LINE | Feed tExtractDelimitedFields / tExtractRegexFields |
| tFileInputRaw | whole file into one column `content` (String) or byte[] | Filename, Read the file as a string / as bytes, Encoding | | NB_LINE (1) | pairs with tExtractJSONFields/tExtractXMLField on `content` |
| tFileOutputRaw | write one column value to a file | Filename, Mode: Write a string / Write bytes, Append (labels unverified), Create directory | | NB_LINE | |
| tFileInputMSDelimited | multi-schema delimited (record type column) | File name, Row/Field separator, Multi Schema Editor (record-type cardinality, parent/child schemas) | | NB_LINE | one output link per schema |
| tFileInputMSPositional | multi-schema positional | Multi Schema Editor with patterns per record type | | NB_LINE | |
| tFileOutputMSDelimited | multi-schema delimited write | Schemas table (one per input link), Use Multi Field Separators | | NB_LINE | |
| tFileInputFullRow + tExtract* | preferred way to handle weird files | | | | |
| tFileStreamInputDelimited etc. | Spark Streaming only; not in Standard Palette | | | | big-data-spark.md |

Multi-char field separators: without CSV options the separator string is used literally in a
`split`-like parse; `"\t"` tab, `"\u00A7"` unicode escapes allowed. Row separator `"\r\n"` vs `"\n"`:
reading with `"\n"` on CRLF files leaves `\r` on the last column unless Trim is on (Studio's reader
actually normalizes CRLF in most versions; keep `"\n"`).

### 2.2 XML and JSON
| Component | Purpose | Key settings | globalMap | Notes |
|---|---|---|---|---|
| tFileInputXML | read XML by XPath | File name/Stream, Loop XPath query (`"/root/order"`), Mapping table: Column / XPath query (relative to loop, `"@id"`, `"customer/name"`, `"."`) / Get Nodes (return the XML fragment as String instead of text value), Limit, Die on error; Advanced: Ignore DTD file, Advanced separator, Ignore the namespaces, Generation mode: Fast with low memory consumption (SAX) / Slow and memory-consuming (Dom4j) / Xerces (streaming with namespaces, 7.x+), Validate date, Encoding | NB_LINE, ERROR_MESSAGE | SAX mode: no namespaces, Get Nodes limited, XPath functions unsupported, `..` parent axis unsupported; use Dom4j for small files, Xerces for large namespaced files |
| tFileInputMSXML | multi-schema XML (several loop elements -> several outputs) | Root XPath query, Outputs table (Schema, XPath loop expression), Mapping per output | NB_LINE | Dom4j only |
| tExtractXMLField | parse XML held in a String/Document column of the flow | XML field (column), Loop XPath query, Mapping, Get Nodes, Ignore DTD, Generation mode | NB_LINE | typical after tFileInputRaw / tRESTClient / tDBInput CLOB |
| tFileOutputXML | write flat XML (one element per row) | File name, Row tag (`"row"`), Root tags (list), Output format: Advanced (Split output per N rows), Encoding, Create directory, Compress as zip, Trim data, Remove empty element, Include header, Advanced > Output format: Use schema column name / Use custom label (labels unverified) | NB_LINE | For nested XML use tAdvancedFileOutputXML |
| tAdvancedFileOutputXML | nested XML via XML tree | File name, Configure XML tree editor (drag schema columns onto tree nodes; `Set As Loop Element` on repeating node; `Set As Group Element` on parent whose children are grouped by equal values; `As attribute`/`Set a namespace`/`Set a fixed value`; Create empty element if needed), Append the source xml file, Generate document (Document type output column on `Output` schema instead of file), Advanced: Split output in several files, Create directory, Encoding, Trim data, Remove empty element, Advanced separator, Row separator, Compress as zip, Don't generate empty file | NB_LINE | Group element requires input sorted by the grouping columns |
| tWriteXMLField | build XML into a Document/String column of the flow (same XML tree editor) | Output column, XML tree, Remove root element, Group by table | NB_LINE | combine with tFileOutputDelimited / tRESTClient |
| tFileInputJSON | read JSON file/URL | File name/URL/Stream, Read By: JsonPath (recommended) / Xpath / JsonPath without loop, Loop Json query (8.0 label; 7.3 "Loop Jsonpath query", e.g. `"$.orders[*]"`), Mapping: Column / Json query or XPath (`"id"`, `"customer.name"`, `"items[0].sku"`), Die on error; Advanced: Encoding, Use the loop node as root (label unverified), Validate date, Advanced separator | NB_LINE, ERROR_MESSAGE | XPath mode converts JSON to XML internally: field names starting with digits or containing `-`/`@` break; JsonPath uses Jayway JsonPath (`$..`, filters `[?(@.x>1)]`) |
| tExtractJSONFields | same, from a String/Document column | JSON field, Read By, Loop Jsonpath query, Mapping (Column, Json query), Die on error | NB_LINE | typical after tRESTClient / tHttpRequest / tDBInput JSON column |
| tFileOutputJSON | write flat JSON | Name of data block (`"data"`, empty for bare array), Generate an array json (array of objects without wrapper), File Name, Create directory, Encoding | NB_LINE | nested JSON: use tWriteJSONField (tree editor; arrays come from the loop element) |
| tWriteJSONField | build JSON into a column | Output Column, Configure JSON Tree (same editor as tAdvancedFileOutputXML; `Set As Loop Element`, `As attribute` has no meaning), Group by, Remove root node, Keep root node, Serialize: Json array/object (unverified label), `Convert empty string/null to ...` (unverified) | NB_LINE | integers/booleans are emitted as strings unless the schema column type is numeric/boolean (8.0 emits typed since R2021-xx, unverified) |
| tXMLMap | map-based XML, tmap-expressions.md | | | |

XPath/JsonPath for attributes: `"@attr"`; current loop node text `"."`; namespaces: declare in the
Mapping with `"ns:node"` only in Dom4j/Xerces mode, or check Ignore the namespaces.

### 2.3 Excel, properties, LDIF, ARFF, EBCDIC, Avro, Parquet
| Component | Purpose | Key settings | globalMap | Notes |
|---|---|---|---|---|
| tFileInputExcel | read xls/xlsx | File name/Stream, Read excel2007 file format(xlsx) (needed for .xlsx/.xlsm; enables Excel 2007+ password), Generation mode (xlsx only): Memory-consuming (User mode, 7.x) / Less memory consumed for large excel (Event mode, streaming via XSSF event API), All sheets / Sheet list (Sheet name or index, `Use Regex`), Header, Footer, Limit, Affect each sheet (header/footer), Die on error, First column / Last column (1-based), Stop reading on encountering empty rows (xls only), Advanced: Advanced separator (for numbers), Trim all columns, Encoding, Read real value for numbers, Don't validate the cells (unverified), Ignore warnings (unverified) | NB_LINE, CURRENT_SHEET (Flow) | Numeric cells read into String columns come as `1.0E7`/`123.0`: use `Read real value for numbers` or BigDecimal column + pattern; Date cells need Date column; xls = Apache POI HSSF (max 65536 rows), xlsx = XSSF; Event mode cannot read formulas' cached results in some versions |
| tFileOutputExcel | write xls/xlsx | File Name, Write excel2007 file format(xlsx), Sheet name, Include header, Append existing file / Append existing sheet, Is absolute Y pos / First cell X,Y, Keep existing cell format, Font, Define all columns auto size, Create directory, Password protection (xlsx), Use streaming mode (SXSSF, 7.3+ unverified label) | NB_LINE | Dates written as Excel dates when column is Date; `Keep existing cell format` + Append for templates |
| tFileInputProperties | read .properties / .ini | File Format: .properties / .ini (+ Section Name), File name, Encoding | NB_LINE | output schema fixed: `key`, `value` (String) |
| tFileOutputProperties | write .properties/.ini | File format, File name, Encoding | NB_LINE | input schema must be key/value |
| tFileInputLDIF | read LDIF | File name, Schema with LDAP attribute names, Value separator (for multi-valued attrs), Die on error | NB_LINE | base64 values decoded automatically |
| tFileOutputLDIF | write LDIF | File name, Change type: Add / Modify / Delete / Modrdn / Content (unverified set), Wrap (line wrap 78), Encoding, Append, Multi-values separator | NB_LINE | `dn` column required |
| tFileInputARFF / tFileOutputARFF | Weka ARFF | File name, Row separator, Header | NB_LINE | rarely used |
| tFileInputEBCDIC | mainframe EBCDIC with COBOL copybook | Copybook (file path or Repository Metadata > File EBCDIC), Data file, Record format (fixed/variable, RDW), Code page (`"cp037"`, `"cp1047"`, `"cp500"`), multi-schema outputs per copybook record | NB_LINE | There is no separate `tCopybook` component: the copybook is parsed by the File EBCDIC metadata wizard (Enterprise) |
| tFileInputAvro / tFileOutputAvro | Avro container files (Standard, 7.3+ in Standard palette; earlier Big Data only) | Folder/File, Compression (none/deflate/snappy), schema inferred by wizard | NB_LINE | Logical types (decimal, timestamp) map to BigDecimal/Date only in newer versions (unverified) |
| tFileInputParquet / tFileOutputParquet | Parquet files in Standard Jobs (8.0; local filesystem or S3/HDFS via tS3Configuration etc.) | Folder/File, Compression (uncompressed/gzip/snappy), `Merge result to single file` (output), Use Hadoop configuration (unverified) | NB_LINE | Pulls Hadoop client jars (large module download on first use); timestamp INT96 vs TIMESTAMP_MILLIS compatibility issues with Spark-written files |

### 2.4 File management
| Component | Purpose | Key settings | globalMap | Notes |
|---|---|---|---|---|
| tFileList | iterate files/dirs | Directory, FileList Type: Files / Directories / Both, Include subdirectories, Case Sensitive: Yes/No, Generate error if no file found, Use Glob Expressions as Filemask (default on; off = Java regex), Files (Filemask table: `"*.csv"`, `"data_??.txt"`), Order by: By default / By file name / By file size / By modified date, Order action: ASC / DESC; Advanced: Use Exclude Filemask, Format file path to slash(/) style | CURRENT_FILE (name with ext), CURRENT_FILEPATH (full path), CURRENT_FILEDIRECTORY, CURRENT_FILEEXTENSION, NB_FILE (After) | All CURRENT_* are Flow variables valid inside the Iterate; connect `tFileList --Iterate--> tFileInputDelimited` with File name `((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))`. Order action is a radio, cannot be context-driven |
| tFileExist | test existence | File name | EXISTS (Boolean, After), FILENAME | use `If` trigger: `((Boolean)globalMap.get("tFileExist_1_EXISTS"))` |
| tFileCopy | copy/move/rename | File Name, Destination directory, Rename (+ Destination filename), Remove source file (= move), Replace existing file, Create the directory if it doesn't exist, Copy a directory | DESTINATION_FILEPATH, DESTINATION_FILE (SOURCE_FILEPATH unverified) | there is no tFileRename component: use tFileCopy + Rename, or tSystem `mv` |
| tFileDelete | delete file/dir | File Name, Delete directory, Delete file, Fail on error (unverified) | DELETE_PATH, CURRENT_STATUS (`"File deleted."`) | silent when file missing unless Fail on error (unverified) |
| tFileArchive | zip/gzip/tar | Directory (source), Archive file, Compress level (Best/Normal/Fast), Encrypt files (zip password), All files / Files filemask, Subdirectories, Format: ZIP / GZIP / TAR (7.x+), Overwrite existing | ARCHIVE_FILEPATH, ARCHIVE_FILE (unverified) | gzip of a single file; zip of directory |
| tFileUnarchive | extract | Archive file, Extraction Directory, Use the archive name as root directory, Need password | UNARCHIVE_PATH (unverified) | supports zip, gz, tar, tgz |
| tFileCompare | byte compare two files | File to compare, Reference file, If differ output file, Print to console | DIFFERENCE (Boolean), MESSAGE | output schema fixed (differ flag) |
| tFileProperties | metadata of one file | File | emits one row: abs_path, dirname, basename, mode_string, size, mtime, mtime_string | NB_LINE | for timestamps/sizes |
| tFileRowCount | count lines | File Name, Row separator, Ignore empty rows, Encoding | COUNT (Integer) | cheap pre-check before processing |
| tFileTouch | create empty file / update mtime | File Name, Create directory if not exists | | |
| tCreateTemporaryFile | temp file | Remove file when execution is over, Use temporary system directory / Directory, Template (`"talend_XXXXXXX"`), Suffix | FILEPATH, FILE | |
| tChangeFileEncoding | re-encode | Input/Output file, Input encoding, Output encoding (ISO-8859-15/UTF-8/custom), Overwrite | | BOM is not stripped |
| tFileInputFullRow | see 2.1 | | | |

### 2.5 Schema metadata for files: date patterns, decimal separators
- In Edit schema, a `Date` column has a **Date Pattern** attribute (e.g. `"dd-MM-yyyy"`,
  `"yyyy-MM-dd HH:mm:ss"`, `"yyyy-MM-dd'T'HH:mm:ss.SSSXXX"`). Input components parse the String
  with `TalendDate.parseDate(pattern, value)` (lenient off by default on delimited inputs in recent
  versions; "Check date" enforces strict parsing); output components format with the same pattern.
  An empty pattern on a Date column in a file schema causes `Unparseable date` at runtime.
- Patterns use `java.text.SimpleDateFormat` syntax: `MM` month, `mm` minute, `yyyy` year, `HH` 24h,
  `hh` 12h, `SSS` millis, `XXX` ISO offset, `Z` RFC offset, `EEE`/`MMM` locale-dependent.
- Numeric columns: `Advanced separator (for numbers)` on delimited/positional/Excel components sets
  `Thousands separator` (default `","`) and `Decimal separator` (default `"."`) applied when
  converting String to numeric types; needed for `1.234,56` files. BigDecimal keeps scale as parsed.
- Length / Precision in a file schema are informational for files (used for DDL when the schema
  is propagated to tDBOutput Create table and for tFileOutputPositional sizes).
- Repository metadata (Metadata > File delimited wizard) stores the same attributes; a component
  with Property Type = Repository locks these fields and shows a "Repository" badge; `Guess` in the
  wizard infers types from sample rows (usually String + a few Integer) and must be corrected manually.

## 3. Processing family (non-map)
| Component | Purpose | Key settings | globalMap | Notes |
|---|---|---|---|---|
| tAggregateRow | GROUP BY in memory | Group by table (Output column / Input column position), Operations table (Output column / Function / Input column position / Ignore null values): count, min, max, avg, sum, first, last, list, list(objects), count(distinct), standard deviation (`std dev`); Advanced: Delimiter(only for list operation) (default `","`), Use financial precision, lose performance (BigDecimal math instead of double), Check type overflow (error on Integer overflow instead of wrap), Check ULP (unit in last place precision check for float/double) | NB_LINE | Holds all groups in memory (HashMap); unsorted input OK. Output schema is defined by the Group by + Operations output columns; `sum` of Integer may overflow (use Long/BigDecimal). `count` ignores nothing; `count(distinct)` keeps a Set per group |
| tAggregateSortedRow | GROUP BY on pre-sorted input, streaming | same Group by/Operations, `Input rows count` (exact total row count; mandatory, usually `((Integer)globalMap.get("tFileInputDelimited_1_NB_LINE"))` from an earlier subjob or tFileRowCount COUNT) | NB_LINE | Input MUST be sorted by the group-by columns; wrong row count => last group dropped or job hangs |
| tSortRow | ORDER BY | Criteria table: Schema column / sort num or alpha (`alpha` / `num` / `date`) / Order asc or desc; Advanced: Sort on disk (label "Sort external on disk" in older versions, unverified) + Temp data directory path + Create temp data directory if not exist + Buffer Size of External Sort (rows, default 1000000) | NB_LINE | In-memory sort by default (holds all rows; OOM on large data). `num` on String column fails at runtime if non-numeric. Date columns use `date` or `alpha` by comparable |
| tExternalSortRow | sort via OS `sort` command | Criteria, Sort command path, Temp dir | NB_LINE | needs external `sort` binary (Unix/Cygwin); rarely used since tSortRow disk sort |
| tUniqRow | DISTINCT / duplicate split | Unique key table: Column / Key attribute (checkbox) / Case sensitive; Advanced: Only once each duplicated key (Duplicates output gets one row per duplicated key instead of every extra occurrence), Use of disk (+ Buffer size in memory, Directory for temp files) | NB_UNIQUES, NB_DUPLICATES | Two outputs: `Uniques` (first occurrence of each key) and `Duplicates` (later occurrences). Unsorted input OK (HashSet of keys in memory). Key of String compares with equals (trim first) |
| tFilterRow | WHERE | Logical operator used to combine conditions: And / Or; Conditions table: Input column / Function (Empty, Length, Absolute value, Lower case, Upper case, Lower case first, Upper case first) / Operator (Equals, Not equal to, Greater than, Lower than, Greater or equal to, Lower or equal to, Matches (regex) ...) / Value (Java expression, `"ACTIVE"`, `42`); Use advanced mode: free Java boolean expression `input_row.age > 18 && input_row.name != null` (`input_row` is the fixed alias) | NB_LINE, NB_LINE_OK, NB_LINE_REJECT | Outputs `Filter` and `Reject` (reject = rows failing conditions, no errorCode columns). Null String with Equals throws NPE: use advanced mode with null check or Function "Empty" |
| tFilterColumns | project/reorder columns | Edit schema: remove unwanted columns from the output schema (columns match by name) | NB_LINE | renaming is better done in tMap |
| tJoin | inner/left join two flows (hash lookup) | Include lookup columns in output (+ Column mapping table), Inner join (unmatched Main rows -> Reject output), Key definition table (Input column / Lookup column; defaults to the schema Key columns) | NB_LINE, NB_LINE_REJECTED (unverified) | Lookup flow fully loaded in memory; prefer tMap for anything beyond a simple equi-join |
| tReplace | search/replace in String columns | Simple mode (Replace table: InputColumn / Search / Replace with / Whole word / Case sensitive) or Advanced mode (Regex / Replace with `$1` back-references); `Use advanced mode`: Input column / Pattern / Replace with | NB_LINE | Operates only on String columns; multiple rules apply in order |
| tReplaceList | replace using a lookup list | Lookup link provides (search, replace) pairs; Lookup search column / Lookup replace column; Columns to replace table (Column / Whole word / Case sensitive) | NB_LINE | dictionary-driven cleansing |
| tConvertType | change column types by name | Auto Cast (converts each input column to the output column type of the same name), Die on error, Set empty values to Null before converting (String "" -> null instead of NumberFormatException); manual mode table (Output column / Input column) | NB_LINE | Output schema holds the target types; Reject link available when Die on error is unchecked (errorCode/errorMessage) |
| tNormalize | split one delimited column into rows (UNNEST) | Column to normalize, Item separator (`";"`), Use CSV parameters (Escape char, Text enclosure), Discard the trailing empty strings, Trim resulting values | NB_LINE | other columns duplicated per item |
| tDenormalize | opposite: aggregate rows into one delimited column (needs all rows in memory) | To denormalize table: Column / Delimiter / Merge same value (dedupe) ; group = all other columns | NB_LINE | unsorted OK |
| tDenormalizeSortedRow | same, streaming, pre-sorted | To denormalize, Input rows count | NB_LINE | sorted by non-denormalized columns required |
| tExtractDelimitedFields | split a String column into columns | Field to split, Field separator, CSV options (Escape char, Text enclosure), Die on error, Advanced separator, Trim, Check each row structure, Check date | NB_LINE | typical after tFileInputFullRow or a DB column holding CSV |
| tExtractPositionalFields | split by Pattern `"5,10,*"` | Field, Customize (Column/Size/Alignment/Padding) | NB_LINE | |
| tExtractRegexFields | split by regex capture groups | Field to split, Regex (capture groups -> schema columns in order), Die on error | NB_LINE | non-matching rows yield null output columns (behaviour unverified), route with Die on error off + reject |
| tSplitRow | one input row -> N output rows via expression table | Columns mapping table: for each output row a set of expressions per output column | NB_LINE | manual unpivot |
| tSampleRow | keep rows by position range | Range `"1..10,20,30..40"` (1-based) | NB_LINE | |
| tReplicate | duplicate a flow to several outputs | none (just connect several Main outputs) | | all outputs share the same schema; order of execution is interleaved per row |
| tUnite | UNION ALL of several Main inputs | none | NB_LINE | all inputs need identical schema; inputs are consumed sequentially (first link fully, then second) |
| tWriteDynamicFields | pack several columns into one Dynamic column | Output column (Dynamic); all other input columns are packed | NB_LINE | |
| tExtractDynamicFields | unpack a Dynamic column into static columns | Dynamic field, Edit schema with the expected column names (matched by name, case-sensitive) | NB_LINE | missing names -> null |
| tPivotToColumnsDelimited | pivot rows to columns written directly to a delimited file | Pivot column, Aggregation column, Aggregation function (first/last/count/min/max/sum/avg), Group by, File Name, Field separator, Row separator, Encoding | NB_LINE | writes a file, not a flow; for in-flow pivot use tDenormalize or tMap |
| tMemorizeRows | keep the last N rows of selected columns in arrays accessible in downstream tJavaRow/tMap | Row count to memorize, Columns to memorize table | per column arrays `tMemorizeRows_1_<col>` (Flow) | `((String[])globalMap.get("tMemorizeRows_1_name"))[0]` is the current row, `[1]` previous; row-to-row comparisons (running totals, change detection) |
| tConvertType / tSchemaComplianceCheck / tIntervalMatch / tDataShuffling / tSqlRow | DQ or Spark | | | data-quality-governance.md / big-data-spark.md |

Sorted-input rules: tAggregateSortedRow, tDenormalizeSortedRow and tAdvancedFileOutputXML Group
element need input sorted on the group columns and the exact total row count; tUniqRow,
tAggregateRow, tDenormalize, tJoin, tSortRow do not need sorted input but hold data in memory
(tUniqRow: keys only; tAggregateRow: groups; tSortRow/tDenormalize/tJoin lookup: all rows). For
large data use tSortRow with Sort on disk, or push the operation to the database (ELT or SQL in
tDBInput).

## 4. Data types in a component schema
| Talend type (Edit schema `Type`) | Java type generated | Default when Nullable unchecked | Notes |
|---|---|---|---|
| String | java.lang.String | n/a (object) | Length informational; DB CREATE uses VARCHAR(Length), default length when empty varies (255 MySQL via mapping) |
| Integer | int (not nullable) / java.lang.Integer (Nullable) | 0 | overflow silently wraps unless tAggregateRow Check type overflow |
| Long | long / java.lang.Long | 0L | use for row counts, ids > 2^31 |
| Short | short / java.lang.Short | | |
| Byte | byte / java.lang.Byte | | |
| Double | double / java.lang.Double | 0.0 | binary float issues for money: use BigDecimal |
| Float | float / java.lang.Float | | |
| BigDecimal | java.math.BigDecimal | n/a | Length = precision, Precision = scale in Talend's schema naming (Length 18 / Precision 2 => DECIMAL(18,2)) |
| Boolean | boolean / java.lang.Boolean | false | file inputs parse `"true"`/`"false"` and `"1"`/`"0"` via `ParserUtils.parseTo_Boolean` (not Y/N) |
| Character | char / java.lang.Character | | CHAR(1) |
| Date | java.util.Date | n/a | Date Pattern per column; DB TIMESTAMP maps to Date (ms precision); no java.time types in schemas |
| byte[] | byte[] | n/a | BLOB/VARBINARY/BYTEA; tFileInputRaw bytes mode |
| Object | java.lang.Object | n/a | carrier for ResultSet (Propagate QUERY's recordset), arbitrary Java objects between tJava components, Avro records |
| List | java.util.List | n/a | from Spark/Big Data, rarely in Standard; tMap cannot expand |
| Document | routines.system.Document (wraps dom4j Document) | n/a | XML payload for tXMLMap, tESBConsumer, tAdvancedFileOutputXML Generate document, tWriteXMLField |
| Dynamic | routines.system.Dynamic | n/a | one per schema, must be the last column (Enterprise); see section 5 |

- `Nullable` checkbox: unchecked on Integer/Long/Double/Boolean/... generates a Java primitive; a
  null from the source (DB NULL, empty CSV field) then raises `NullPointerException`/`NumberFormatException`
  or is replaced by the `Default` value depending on component. Check Nullable on every column that
  can be NULL (DB Repository schemas import nullability from the catalog; file wizards default to nullable).
- `Default` column: Java expression used when the input is empty (delimited inputs) or when the
  column is added via Sync columns; for String use `"\"\""` style (the field expects Java literal).
- `Key` checkbox: used by tDBOutput Update/Delete WHERE, tUniqRow default keys, tJoin keys, tMap
  lookup matching proposals, and `Create table` PRIMARY KEY.
- `Length`/`Precision`: used only for DDL generation and positional/Excel formatting; Talend does not
  truncate Strings to Length on insert (the DB will error with "Data too long").
- `Date Pattern`: see 2.5; on DB components it is ignored for Date columns (JDBC binds Timestamp).
- `Comment`: free text stored in the .item.

DB type mapping: `<studio>/plugins/org.talend.core.runtime_<version>.jar!/mappings/mapping_<db>.xml`
(e.g. `mapping_Mysql.xml`, `mapping_Oracle.xml`, `mapping_Postgres.xml`, `mapping_MSSQL.xml`,
`mapping_Snowflake.xml`, `mapping_JDBC.xml` ... exact file-name casing varies by DB) with sections
`<dbTypes>`, `<dbToTalendTypes>` and `<talendToDbTypes>` mapping each DB type to a Talend type with
`default="true"` for the preferred one. The `Mapping` dropdown (Advanced settings of tDBInput/
tDBOutput/tJDBC*/tCreateTable and in the Db Connection metadata wizard) chooses which file to use
(e.g. `mapping_mysql` vs `mapping_mariadb`; for tJDBC pick the closest vendor or `mapping_jdbc`).
Window > Preferences > Talend > Specific Settings > Metadata of TalendType lets you edit/add
mappings in the Studio; edited files live in the workspace `.metadata` and must be re-applied after
Studio upgrades (unverified exact preference path).

## 5. Schema propagation rules and Dynamic schema
- Each component owns an output schema; a Main link carries the upstream component's output schema
  to the downstream input. Components whose output = input (tLogRow, tFilterRow, tReplace, tSortRow,
  tUniqRow, tDBOutput, file outputs) show a `Sync columns` button that copies the input schema into
  the component's schema; after any upstream schema change Studio prompts "Propagate changes?" and
  downstream components turn with a yellow warning until synced.
- Lookup links (into tMap/tJoin/tReplaceList/tXMLMap) carry the lookup component's own schema; they
  are not merged with Main unless the mapping component does it.
- Reject links: schema = input schema + `errorCode` (String) + `errorMessage` (String) appended by
  Studio; adding these to the parent schema manually breaks the reject.
- Repository schemas: a component with Schema = Repository shows the metadata item; `Built-In`
  detaches a copy. Changing a Repository schema and choosing "Update all jobs" rewrites the .item
  files of every job using it (Impact analysis in Enterprise).
- tFixedFlowInput / tRowGenerator / tFileInput* / tDBInput are schema sources; outputs and
  transformations consume. tUnite requires all inputs to match the tUnite schema exactly (name/type).
- Iterate links carry no schema (only globalMap).

Dynamic schema (Enterprise/Platform editions):
- Add one column of type `Dynamic`, it must be the LAST column of the schema; static columns before
  it are matched by name/position, everything else at runtime lands in the Dynamic column. Supported
  by tDBInput/tDBOutput (with Use dynamic schema / Enable Mapping File for Dynamic), tFileInput/
  OutputDelimited, tFileInputPositional, tFileInputExcel, tLogRow, tJavaRow,
  tMap (passes through on Main; a Dynamic column cannot be expanded into lookup join keys or
  individual expressions; only whole-column copy), tWriteDynamicFields/tExtractDynamicFields,
  tSetDynamicSchema (define columns at runtime from a tFixedFlowInput description).
- Runtime API (`routines.system.Dynamic` and `routines.system.DynamicMetadata`), typically in tJavaRow:
```java
routines.system.Dynamic dyn = input_row.dyn;              // Dynamic column named "dyn"
int n = dyn.getColumnCount();
for (int i = 0; i < n; i++) {
    routines.system.DynamicMetadata m = dyn.getColumnMetadata(i);
    String name = m.getName();          // column name
    String dbName = m.getDbName();      // original DB column name
    String type = m.getType();          // Talend type: "id_String", "id_Integer", "id_Date", "id_BigDecimal" ...
    String dbType = m.getDbType();      // "VARCHAR", "NUMBER", ...
    int length = m.getLength(); int precision = m.getPrecision();
    String format = m.getFormat();      // date pattern
    boolean key = m.isKey(); boolean nullable = m.isNullable();
    Object value = dyn.getColumnValue(i);     // also getColumnValue(name)
    dyn.setColumnValue(i, value);             // setColumnValue(name, value)
}
dyn.addColumn(meta); dyn.removeColumn(i); dyn.getIndex("name"); dyn.clearColumnValues(); dyn.getColumnValue("name");
```
  Metadata setters: `setName/setType/setDbName/
  setDbType/setLength/setPrecision/setFormat/setKey/setNullable`. Column types in Dynamic are decided
  by the input (DB catalog via mapping file; files default every column to String unless
  `Enable Mapping File for Dynamic` style options).
- tDBOutput with Dynamic: Action on table Create builds DDL from the Dynamic metadata; column
  order = static columns then dynamic ones; there is no separate "Use dynamic schema" checkbox on most DBs, the behaviour is implicit (unverified).

## 6. Database-specific notes
| DB | Driver module / jar (Studio fetches into `<studio>/configuration/.m2` or `lib/java`) | JDBC URL pattern generated | Specific settings and remarks |
|---|---|---|---|
| MySQL | `mysql-connector-java-5.1.x.jar` (MySQL 5), `mysql-connector-java-8.0.x.jar` (MySQL 8; driver class `com.mysql.cj.jdbc.Driver`), `mariadb-java-client` for MariaDB | `jdbc:mysql://host:port/db?<additional params>` | DB Version MySQL 5 / MySQL 8 / MariaDB 10; Enable stream (Input: `useCursorFetch`-style streaming, `setFetchSize(Integer.MIN_VALUE)`); Extend Insert; Use duplicate key update; batch requires `rewriteBatchedStatements=true` for real multi-row inserts; `zeroDateTimeBehavior=convertToNull`, `serverTimezone=UTC`, `allowPublicKeyRetrieval=true` common params; LOAD DATA LOCAL needs `allowLoadLocalInfile=true` |
| Amazon Aurora | MySQL / Postgres driver | `jdbc:mysql://cluster-endpoint:3306/db` | choose Aurora MySQL vs Aurora Postgres via DB Version / separate component families |
| Oracle | `ojdbc8.jar` / `ojdbc10/11` (DB Version 12c-21c), OCI needs client; wallet needs `oraclepki`, `osdt_*` jars | SID `jdbc:oracle:thin:@host:1521:ORCL`; Service Name `jdbc:oracle:thin:@//host:1521/service`; Custom URL for RAC/TNS | Connection Type: Oracle SID / Oracle Service Name / Oracle OCI / Oracle Custom / Oracle RAC / WALLET; Schema must be UPPERCASE; Oracle DATE has time: Talend maps DATE -> Date (java.util.Date) keeping time since 6.x but mapping file may propose `id_Date` with pattern; tOracleInput `Convert Timestamp to Date` (unverified label); tOracleSP RECORDSET param for `SYS_REFCURSOR`; tOracleOutput `Use Hint Options`, `Convert columns and table to uppercase`; NLS: set `-Duser.timezone` / `oracle.jdbc.timezoneAsRegion=false`; `Insert or update` does INSERT then UPDATE (no MERGE) |
| PostgreSQL | `postgresql-42.x.jar` | `jdbc:postgresql://host:5432/db?ssl=true` | Use cursor (+ Fetch size): requires Auto Commit off (Studio handles it when not using existing connection); `Support null in WHERE`; Schema default `"public"`; `Use batch mode` + Reject not available together; `stringtype=unspecified` param to let Postgres cast String columns to enum/json/uuid; Postgres `COPY` bulk requires file on server or `Use STDIN` (unverified) |
| Microsoft SQL Server | JDBC Provider: Open source JTDS (`jtds-1.3.1.jar`, URL `jdbc:jtds:sqlserver://host:1433/db;instance=X;domain=D`) or Microsoft (`mssql-jdbc-x.jre8/11.jar`, URL `jdbc:sqlserver://host:1433;databaseName=db;encrypt=true;trustServerCertificate=true`) | | DB Version SQL Server 2012-2022; Microsoft driver needed for `Always Encrypted`, Azure AD auth (`authentication=ActiveDirectoryPassword`), `datetime2`/`datetimeoffset` precision; JTDS for NTLM/Windows auth with `ntlmauth.dll`; Identity insert; `sendStringParametersAsUnicode=false` improves varchar index use; Azure SQL via MSSQL component with `hostNameInCertificate=*.database.windows.net` |
| Azure Synapse | Microsoft mssql-jdbc | `jdbc:sqlserver://<ws>.sql.azuresynapse.net:1433;database=pool` | tAzureSynapseBulkExec via Azure Blob/ADLS Gen2 + COPY INTO; dedicated SQL pool has no IDENTITY insert / limited MERGE (older versions) |
| Snowflake | `snowflake-jdbc-3.x.jar` | `jdbc:snowflake://<account>.<region>.snowflakecomputing.com/?warehouse=W&db=D&schema=S&role=R` | Account (`xy12345` or `xy12345.eu-west-1`, or org-account), Region (dropdown or custom; omitted for newer account URLs), Warehouse, Database, Schema, Role (Advanced, 8.0), Authentication: Basic / Key Pair (Private key file + password) / OAuth / SSO (externalbrowser); Login Timeout; tSnowflakeOutput: `Table Action` (None/Create/Create if not exists/Drop and create/Drop if exists and create/Clear/Truncate), `Output Action` Insert / Update / Upsert / Delete (MERGE through temp table), `Use custom DB Type` (per-column Snowflake type for Create), `Convert empty strings to null` (label unverified; Snowflake treats `''` as empty not null), `Use schema date pattern for Date type` (Advanced, unverified), `Custom Snowflake field delimiter`, `Allow Snowflake to convert columns and tables to uppercase` (unquoted identifiers are uppercased; unchecked = quoted case-sensitive identifiers that will not match `select * from mytable`) ; tSnowflakeRow/tSnowflakeCommit/tSnowflakeRollback/tSnowflakeClose exist; writes go through internal stage + COPY (fast) not row inserts |
| Amazon Redshift | `redshift-jdbc42-x.jar` (8.0) / postgres driver (older) | `jdbc:redshift://endpoint:5439/db` | tRedshiftOutput row inserts are slow: always use tRedshiftOutputBulkExec (S3 + COPY); tRedshiftUnload (UNLOAD to S3, Parallel/Allow overwrite/Delimiter/Escape/Add quotes/Null as); `Use IAM role`/Access key; SSL `ssl=true&sslfactory=com.amazon.redshift.ssl.NonValidatingFactory` |
| Teradata | `terajdbc4.jar` (+ `tdgssconfig.jar` < 16.20) | `jdbc:teradata://host/DATABASE=db,CHARSET=UTF8,TMODE=ANSI` | tTeradataTPTExec (TPT `tbuild`, operators Load/Update/Stream, `Script generated/Use existing script`, Max error rows, Checkpoint interval), tTeradataFastLoad / tTeradataMultiLoad / tTeradataTPump / tTeradataFastExport invoke the installed utilities (`fastload`, `mload`, `tpump`, `fexp`); tTeradataOutput `Action on data` includes `Insert or update` implemented with MERGE (unverified); tTeradataSCD/SCDELT and tTeradataCDCOutput exist; Query band via Additional params `QUERYBAND=...` |
| DB2 | `db2jcc4.jar` (+ `db2jcc_license_cu.jar`) | `jdbc:db2://host:50000/db` | Schema mandatory (uppercase); tDB2SCD, tDB2CDC exist; `Use batch mode` ok; LOAD requires DB2 client; `currentSchema` param |
| Vertica | `vertica-jdbc-x.jar` | `jdbc:vertica://host:5433/db` | DB Version Vertica 9-12; tVerticaBulkExec COPY with Exception file / Rejected data; `Direct` load method for large loads |
| Greenplum | postgres driver | `jdbc:postgresql://host:5432/db` | tGreenplumGPLoad (needs `gpload` installed, generates YAML; Insert/Update/Merge, Match columns, Error table); plain tGreenplumOutput row inserts are slow |
| Netezza | `nzjdbc.jar` (not in Maven: install manually via Modules view) | `jdbc:netezza://host:5480/db` | tNetezzaBulkExec external table; tNetezzaNzLoad (`nzload` binary); NPS case: identifiers uppercase by default |
| SAP HANA | `ngdbc.jar` (manual install) | `jdbc:sap://host:30015/?currentschema=S` | tSAPHana* family (Connection/Input/Output/Row/Commit/Close/BulkExec via IMPORT FROM CSV on server); column-store tables created via `Action on table` with COLUMN TABLE DDL (unverified) |
| Hive / Impala / Databricks / Delta Lake / BigQuery / Spanner / CockroachDB | see big-data-spark.md and connectors-catalog.md | | tBigQuery* is NOT in the tDB Database dropdown in 7.x (own family); Databricks via tDBConnection Database = Databricks in 8.0 |
| Sybase | `jconn4.jar` (ASE), Sybase IQ via same or jTDS `jdbc:jtds:sybase://` | `jdbc:sybase:Tds:host:5000/db` | DB Version ASE 15/16, IQ 15/16; tSybaseIQ* bulk (`LOAD TABLE`); tSybaseSCD, tSybaseCDC exist |
| Informix | `ifxjdbc.jar` | `jdbc:informix-sqli://host:1526/db:INFORMIXSERVER=srv` | `Server` field mandatory; DELIMIDENT param for quoted identifiers; tInformixSCD/CDC exist |
| AS400 (IBM i / Db2 for i) | `jt400.jar` | `jdbc:as400://host;libraries=LIB;prompt=false` | Database = library; tAS400CDC via journals (needs journaling on the physical file); `Use PreparedStatement` recommended to avoid CCSID issues; tAS400Row with `translate binary=true` param |
| SQLite | `sqlite-jdbc-3.x.jar` | `jdbc:sqlite:/path/file.db` | Database field = file path; no server; one writer at a time (`database is locked`); types are affinities so Guess schema gives String mostly |
| HSQLDB | `hsqldb.jar` | `jdbc:hsqldb:hsql://host/db`, `jdbc:hsqldb:file:/path`, `jdbc:hsqldb:mem:name` | Running Mode: HSQLDb Server / HSQLDb WebServer / HSQLDb In Process Persistent / HSQLDb In Memory; `DB Path`/`DB Name` for file mode; often used for unit-test jobs |
| Access | UCanAccess (`ucanaccess.jar` + hsqldb/jackcess/commons deps) in 7.x/8.0; JDBC-ODBC bridge in <=5.x | `jdbc:ucanaccess:///path/file.accdb` | DB Version Access 2003 (.mdb) / Access 2007 (.accdb); Windows only for ODBC-era |
| Firebird | `jaybird-x.jar` | `jdbc:firebirdsql://host:3050//path/db.fdb` | tFirebird* small family (Connection/Input/Output/Row/Commit/Rollback/Close/SP) |
| Ingres / Actian | `iijdbc.jar`; VectorWise (`tVectorWise*`) for Actian Vector | `jdbc:ingres://host:II7/db` | tIngres* family incl. tIngresCDC and tIngresSCD; Actian Avalanche/Vector: use tVectorWise* (legacy name, 7.x) or tJDBC* with the Actian driver (8.0, unverified availability of a dedicated family) |
| Exasol | `exajdbc.jar` | `jdbc:exa:host:8563;schema=S` | tExasol* family (Connection/Input/Output/Row/Commit/Rollback/Close/BulkExec via IMPORT); identifiers uppercase |
| Google Cloud SQL | MySQL/Postgres/MSSQL components over public IP or Cloud SQL Auth Proxy; or tJDBC with Cloud SQL socket factory jar (`cloud-sql-connector-jdbc`) and URL `jdbc:mysql:///db?cloudSqlInstance=p:r:i&socketFactory=com.google.cloud.sql.mysql.SocketFactory` | | no dedicated component |
| JDBC (generic) | Drivers table: add jar(s) via `Modules` dialog / Maven coordinates (`mvn:org.postgresql/postgresql/42.6.0`) ; Driver Class (`org.postgresql.Driver`); JDBC URL; User/Password; Advanced: `Mapping` dropdown (pick vendor mapping for correct type inference), `Enable Mapping File for Dynamic`, `Use cursor`, `Trim`, `Use batch mode`, `Commit every` | any | tJDBCInput/Output/Row/Connection/Commit/Rollback/Close/SP/ColumnList/TableList/SCD/SCDELT; tJDBCOutput has no `Action on table` DDL beyond Create via mapping; prefer vendor component when one exists (performance options like bulk/stream are missing in generic) |

## Gotchas
| Symptom | Cause | Fix |
|---|---|---|
| `tDBOutput_1_NB_LINE` equals rows received but the table has fewer rows | NB_LINE counts input rows; inserts are NB_LINE_INSERTED, rejects NB_LINE_REJECTED | Log NB_LINE_INSERTED/UPDATED/DELETED/REJECTED separately; with Use batch mode the per-action counters are still filled but rejects are not |
| Rows missing with no error, Die on error off, batch mode on | A failing batch aborts the whole `executeBatch()`; rows cannot be routed to Reject in batch mode | Turn off Use batch mode when you need a Reject link, or load to a staging table and validate with SQL |
| Partial load committed after a job failure | Commit every (default 10000) committed earlier batches; no transaction across components | Use tDBConnection (Auto Commit off) + Use an existing connection + tDBCommit on OnSubjobOk and tDBRollback on OnSubjobError |
| "Commit every" grayed out | Use an existing connection is checked | Commit is controlled by tDBConnection Auto Commit / tDBCommit |
| Batch inserts slow despite Use batch mode on MySQL | Connector/J sends one statement per row unless `rewriteBatchedStatements=true` | Add it to Additional JDBC Parameters; or use Extend Insert; Commit every should be >= Batch Size |
| `Insert or update` is very slow | Implemented as INSERT, catch duplicate-key error, then UPDATE per row (no MERGE except Snowflake/Teradata); exceptions are expensive | Use `Update or insert` when most rows exist, bulk-load to staging + SQL MERGE in tDBRow, or Snowflake Upsert / MySQL Use duplicate key update |
| Oracle DATE column loses time or comparisons off by a day | Oracle DATE mapped to Talend Date is fine, but older mapping/driver (`oracle.jdbc.V8Compatible`, ojdbc < 11) truncated to date; timezone shifts from JVM `user.timezone` | Use ojdbc8+, set `-Duser.timezone=UTC` consistently, check tOracleInput Convert Timestamp to Date / schema Date Pattern |
| Snowflake: `SQL compilation error: Object 'MYDB.PUBLIC.mytable' does not exist` after Create | Table created with quoted lower-case identifiers (case-sensitive) because "convert to uppercase" option unchecked | Check the uppercase conversion option on tSnowflakeOutput or always quote identifiers in your SQL |
| Snowflake: empty strings stored as `''`, not NULL | Snowflake COPY loads empty fields as empty strings | Enable the convert-empty-to-null option on tSnowflakeOutput / COPY option `EMPTY_FIELD_AS_NULL=TRUE`, or `NULLIF` in tMap |
| tFileInputDelimited splits a quoted field containing `;` or a newline into extra rows/columns | CSV options unchecked, so quotes are not interpreted | Check CSV options, set Text enclosure `"\""` and Escape char `"\""` (RFC4180 double-quote) or `"\\"` |
| First column of first data row has a strange prefix (`\uFEFF`) or header mismatch | UTF-8 BOM in the file | Encoding `"UTF-8"` does not strip BOM in older versions: use Header 1 to skip, or pre-process (tFileInputRaw + replace), (no "UTF-8-BOM" encoding option) or tJavaRow `.replace("\uFEFF","")` |
| Header line appears as a data row and causes `NumberFormatException` | Header left at 0 | Set Header = 1 (number of lines to skip, not a boolean) |
| Job still dies although Die on error is unchecked | Only data conversion errors go to Reject; schema/structure errors (wrong column count) or IO errors still throw | Check "Check each row structure against schema" to route structural errors to reject; wrap in a tRunJob or catch via OnSubjobError |
| `Unparseable date: "2024-01-05 10:00:00"` | Date Pattern on the schema column is `"dd-MM-yyyy"` (or empty) | Match pattern to data exactly (`"yyyy-MM-dd HH:mm:ss"`); for mixed formats read as String and use `TalendDate.parseDateInUTC`/custom routine |
| `OutOfMemoryError: Java heap space` in tSortRow / tUniqRow / tAggregateRow / tDenormalize | Whole input held in memory | tSortRow: enable Sort on disk + Buffer Size; tUniqRow: Use of disk; otherwise sort/aggregate in SQL or raise `-Xmx` in Run > Advanced settings > JVM arguments |
| tAggregateSortedRow emits one group short or hangs | Input not sorted on group columns, or Input rows count wrong | Insert tSortRow before; feed the exact count from a previous subjob NB_LINE or tFileRowCount COUNT |
| Update affects 0 rows for keys with NULL | Generated `WHERE col = NULL` | Check "Support null in SQL WHERE statement" (generates `IS NULL`), or filter nulls to a separate flow |
| Lookups / joins do not match although values look identical | CHAR padding or trailing spaces/CR from the file | Trim all the String/Char columns (DB input), Trim all columns (file input), or `.trim()` in tMap |
| tDBRow executes a SELECT but no rows reach the next component | tDBRow does not emit result rows by default | Check Advanced > Propagate QUERY's recordset into an Object column, then tParseRecordSet; or use tDBInput |
| tDBRow: `You have an error in your SQL syntax` with several statements | MySQL rejects multi-statement unless allowed | Add `allowMultiQueries=true` to Additional JDBC Parameters (MySQL); Oracle wrap in `BEGIN ... END;`; or one tDBRow per statement |
| Excel .xlsx read fails with OOM or "Zip bomb detected" | User/DOM mode loads whole workbook (POI); large xlsx | Use Generation mode "Less memory consumed for large excel (Event mode)"; split file; raise `-Xmx` |
| Excel numbers like `12345.0` or `1.2345E4` in String columns | POI returns numeric cells as double | Check "Read real value for numbers" or use numeric or BigDecimal column type with correct pattern, or format in tMap |
| Dynamic column error "the dynamic column must be the last one" / tMap lookup refuses Dynamic key | One Dynamic per schema, always last; tMap cannot join on fields inside a Dynamic column | Put Dynamic last; use tExtractDynamicFields to materialize needed columns before tMap |
| tFileOutputDelimited with Append and Include header writes header in the middle of the file | Header is written whenever the file is new; some versions write it on every Append | Uncheck Include header on append runs; standard pattern: write header only on first iteration via `((Integer)globalMap.get("tFileList_1_NB_FILE"))`/`tFileExist` If trigger |
| tFileList processes files in random order | Order by: By default (filesystem order) | Set Order by By file name/modified date + Order action ASC/DESC |
| tFileList finds no files although mask is right | Filemask is a glob (`*.csv`) while Use Glob Expressions as Filemask is off (regex expected), or Case Sensitive = Yes | Toggle Use Glob Expressions, or write regex `".*\\.csv"`; set Case Sensitive No |
| `Table 'x' doesn't exist` with Create table if not exists on a mixed-case name | DB quoting: Postgres/Oracle fold unquoted to lower/upper; Studio quotes identifiers in DDL | Use consistent case; on Oracle keep table/columns uppercase; on Postgres lowercase |
| Postgres `Use cursor` has no effect / OOM on big SELECT | Cursor fetch needs a transaction (Auto Commit off) and no `Use an existing connection` with Auto Commit on | Set tDBConnection Auto Commit off, or omit existing connection |
| `Integer` column NPE in tMap or tDBOutput on NULL | Nullable unchecked => primitive `int` | Check Nullable on all nullable columns (DB wizards import it; file wizards may not) |
| tUniqRow treats `"ABC"` and `"abc"` as different / same | Case sensitive checkbox per key column | Set per requirement; also trim before |
| Decimal values `1.234,56` parsed as 1.234 or error | Default Decimal separator `.` | Advanced separator (for numbers): Thousands `"."`, Decimal `","` |
| SCD creates a new Type-2 version for every run even without change | A Type-2 field containing a timestamp/last-modified column, or String vs Date compare with different formats | Move volatile columns to Type 0/1; normalize before tDBSCD |
| CDC subscriber returns no changes | Subscription for that subscriber/table not activated, events not checked, or changes already consumed by an earlier run without Keep data in CDC table | Re-check subscription in Repository CDC Foundation; verify `TCDC_` table and events; use Keep data in CDC table while testing |
| Oracle SQL*Loader bulk fails `sqlldr: command not found` / `SP2-0...` | Bulk components call client utilities on the Job host | Install Oracle client / Teradata TTU / gpload on the JobServer host and put them in PATH; set `Use existing control file` when needed |
| `BATCH_SIZE` / `Use Batch Size` has no visible effect | `Use Batch Size` applies to Insert, Update and Delete only; `Insert or update` / `Update or insert` run statement-by-statement (insert, catch duplicate, update) and ignore batching, as does a reject link | Load to a staging table with Insert in batches, then one MERGE / `INSERT ... ON CONFLICT` in tDBRow; or choose the single action that matches most rows |

## Sources
https://help.qlik.com/talend/en-US/components/8.0/sqlite/tsqliteoutput
https://help.qlik.com/talend/en-US/components/8.0/netezza/tnetezzaoutput
https://help.qlik.com/talend/en-US/components/7.3/netezza/tnetezzaoutput-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/vectorwise/tvectorwiseoutput-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/singlestore/tsinglestoreinput-standard-properties
https://help.qlik.com/talend/en-US/components/7.2/amazon-redshift/tredshiftinput-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/maxdb/tmaxdbinput
https://help.qlik.com/talend/r/en-US/8.0/components/amazon-redshift/tredshiftrow
https://help.qlik.com/talend/en-US/components/8.0/sqlite/tsqliterow
https://help.qlik.com/talend/en-US/components/7.3/mysql/tmysqlrow-tfixedflowinput-tparserecordset-tlogrow-configuring-components-standard-component
https://help.qlik.com/talend/en-US/components/7.3/javadb/tjavadboutput-standard-properties
https://help.qlik.com/talend/en-US/components/7.2/oledb/toledboutput-standard-properties
https://help.qlik.com/talend/en-US/components/7.2/sybase/tsybaseoutput-standard-properties
https://community.qlik.com/t5/Talend-Studio/Using-tDBOutput-as-a-MERGE/td-p/2377889
https://community.qlik.com/t5/Talend-Studio/How-to-use-SQL-expressions-in-tDBOutput-or-tJDBCOutput-component/td-p/2327537
https://help.qlik.com/talend/en-US/components/8.0/scd/scd-management-methodology
https://help.qlik.com/talend/fr-FR/components/8.0/scdelt/tjdbcscdelt
https://help.qlik.com/talend/fr-FR/components/8.0/scdelt/tteradatascdelt
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-07/configuring-cdc-in-trigger-mode
https://help.qlik.com/talend/en-US/studio-user-guide/7.3/step-4-subscribe-to-source-table-and-activate-subscription
https://help.qlik.com/talend/en-US/components/7.2/change-data-capture/tmysqlcdc-tlogrow-tmap-tmysqloutput-specify-which-table-subscriber-wants-to-subscribe-to-and-then-activate-subscription-standard-component-enterprise
https://help.qlik.com/talend/en-US/components/8.0/jdbc/tjdbcconnection
https://help.qlik.com/talend/en-US/components/8.0/mysql/tmysqlconnection
https://help.qlik.com/talend/en-US/components/8.0/db2/tdb2connection
https://help.qlik.com/talend/en-US/components/7.3/jdbc/tjdbcconnection-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/elt-mysql/teltmysqloutput
https://help.qlik.com/talend/en-US/components/7.3/elt-mysql/teltmysqloutput-standard-properties
https://help.qlik.com/talend/en-US/data-integration-job-examples/7.3/applying-validation-rule-and-viewing-job-execution-result
https://help.qlik.com/talend/en-US/components/7.2/mssql/tmssqloutputbulk-standard-properties
https://community.qlik.com/t5/Talend-Studio/How-to-get-NB-LINE-in-tPostgresPlusRow/td-p/2330906
https://community.qlik.com/t5/Talend-Studio/How-to-count-number-of-rows-affected-created-updated-by/m-p/2362336
https://help.qlik.com/talend/en-US/components/8.0/delimited/tfileinputdelimited-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/delimited/tfileinputdelimited-standard-properties
https://help.qlik.com/talend/en-US/job-script-reference-guide/8.0/component-specific-settings-for-tfileinputdelimited
https://help.qlik.com/talend/en-US/components/7.2/delimited/tfileoutputdelimited-standard-properties
https://help.qlik.com/talend/en-US/job-script-reference-guide/8.0/component-specific-settings-for-tfileoutputdelimited
https://help.qlik.com/talend/en-US/components/8.0/ms-delimited/tfileoutputmsdelimited
https://community.qlik.com/t5/Talend-Studio/Custom-the-flush-buffer-size-quot-on-the-tFileOutputDelimited/m-p/2295236
https://community.qlik.com/t5/Talend-Studio/tFileOutputDelimited-quot-don-t-create-empty-file-quot-on-but/m-p/2241160
https://help.qlik.com/talend/en-US/components/8.0/tfilelist/tfilelist
https://help.qlik.com/talend/en-US/components/7.3/tfilelist/tfilelist-standard-properties
https://community.qlik.com/t5/Talend-Studio/resolved-tFileList-Order-Action/m-p/2343229
https://community.qlik.com/t5/Talend-Studio/Can-we-get-the-current-filepath-without-the-filename/m-p/2324337
https://help.qlik.com/talend/en-US/components/7.2/xml-connectors/tfileinputxml-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/ms-xml-connectors/tfileinputmsxml
https://help.qlik.com/talend/en-US/components/7.3/ms-xml-connectors/tfileinputmsxml-standard-properties
https://community.qlik.com/t5/Talend-Data-Catalog/XML-iteration-is-slow/td-p/2343296
https://help.qlik.com/talend/en-US/components/8.0/json/tfileinputjson-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/json/tfileinputjson-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/processing/textractjsonfields-tfileinputjson-tlogrow-tlogrow-configuring-components-standard-component
https://help.qlik.com/talend/en-US/components/8.0/excel/tfileinputexcel
https://help.qlik.com/talend/en-US/components/7.3/excel/tfileinputexcel-standard-properties
https://help.qlik.com/talend/en-US/components/7.2/excel/tfileinputexcel-standard-properties
