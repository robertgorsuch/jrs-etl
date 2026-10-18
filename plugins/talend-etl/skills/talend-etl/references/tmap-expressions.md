# tMap, tXMLMap, tELTMap, expression language, routines, globalMap, data types

> Verification: doc-derived (help.qlik.com / help.talend.com search snippets, Talend GitHub, Maven Central) plus model knowledge. Not exercised against a live Studio/TAC/TMC in this build. Items marked (unverified) are from memory only and should be checked in Studio before relying on exact labels.

Scope: mapping components and the Java expression surface of Standard (DI) Jobs.
Spark tMap differences are noted only where they bite. Component parameters for
non-mapping components live in components-core.md; job-level orchestration and
error handling in orchestration-logging.md; design patterns in patterns-gotchas.md.

## Contents
- [tMap: editor layout](#tmap-editor-layout)
- [tMap: inputs, joins, lookups](#tmap-inputs-joins-lookups)
- [tMap: Reload at each row with globalMap](#tmap-reload-at-each-row-with-globalmap)
- [tMap: Var table](#tmap-var-table)
- [tMap: outputs, filters, rejects](#tmap-outputs-filters-rejects)
- [tMap: settings (Property Settings and Component view)](#tmap-settings-property-settings-and-component-view)
- [tMap: mapping behaviours (types, null, dates, keys)](#tmap-mapping-behaviours-types-null-dates-keys)
- [tMap: performance](#tmap-performance)
- [tXMLMap](#txmlmap)
- [tELTMap family](#teltmap-family)
- [Expression language](#expression-language)
- [globalMap, context and job variables](#globalmap-context-and-job-variables)
- [System routines](#system-routines)
- [routines.system internals (ParserUtils, FormatterUtils, Dynamic, Document)](#routinessystem-internals-parserutils-formatterutils-dynamic-document)
- [User routines](#user-routines)
- [Data types and conversions](#data-types-and-conversions)
- [tJava, tJavaRow, tJavaFlex code context](#tjava-tjavarow-tjavaflex-code-context)
- [Mapping recipes](#mapping-recipes)
- [Gotchas](#gotchas)
- [Sources](#sources)

## tMap: editor layout

Open with double-click on tMap or Component view > Basic settings > `Map Editor`.

| Zone | Content | Notes |
|---|---|---|
| Left: input area | One table per incoming row link. Top table = Main flow (the link marked `Main`). Every other table = Lookup (link turns to `Lookup` automatically when a second row link is connected). | Table header carries Match Model, Join Model, Lookup Model, Store temp data, Expression filter button, globalMap Key (Reload modes only). Each column row has an `Expr. key` cell (join key expression) and the column name. |
| Middle: Var table | Named, typed intermediate expressions. | Referenced as `Var.<name>` in outputs and in later Var rows. |
| Right: output area | One table per outgoing row link (`+` creates a new output; name becomes the link name). | Header: `tMap settings` (wrench), expression filter button, `Catch output reject`, `Catch lookup inner join reject`. Each column row has an `Expression` cell. |
| Bottom: Schema editor tab | Columns: Column, Key, Type, Nullable, Date Pattern, Length, Precision, Default, Comment, for the table selected above. Input schemas are read-only when driven by the upstream component; output schemas are editable. | `Length` = total digits (DB precision), `Precision` = scale for BigDecimal (Talend's naming is inverted relative to SQL). |
| Bottom: Expression editor tab | Free-text editor for the selected cell; `...` button opens the Expression Builder. | Same content as the cell; multi-line allowed (it is Java). |
| Toolbar | `Auto map!` (maps same-named input columns onto the selected output), Property Settings (wrench), search, zoom, `Export`/`Import` of the map (unverified label), `Enable/disable preview` (Data Viewer in Enterprise). | Auto map is name-based, case-sensitive, type-blind. |

Expression Builder (`...`): left `Categories` (All, User Defined, Mathematical, Numeric, Relational, StringHandling, TalendDataGenerator, TalendDate, TalendString, plus your routines), middle `Functions`, bottom `Expression` text, `Test!` panel where each `row1.x` / `Var.x` / `context.x` token gets a sample value and the expression is compiled and evaluated in Studio. Routine Javadoc tags `{talendTypes}`, `{Category}`, `{param}`, `{example}` populate the Builder.

Mapping gestures: drag an input column to an output cell (copies `row1.col`); Ctrl/Shift drag for several; drag input column to a lookup column to create the join key (`Expr. key` cell filled with `row1.col`); drag to the Var table to create a typed variable. Rename columns in the Schema editor, not in the cell. Changing an output schema inside tMap prompts `Propagate changes` to the downstream component; conversely upstream schema changes prompt propagation into tMap. On the downstream component `Sync columns` (Component view) re-aligns its schema to the incoming link.

## tMap: inputs, joins, lookups

Main vs Lookup:
- Exactly one Main. All rows of the Main drive the per-row evaluation. Lookups are loaded (per Lookup Model) and probed by key.
- The Main cannot be re-loaded; a lookup cannot drive output rows unless `All matches` fans out.
- Lookup order matters only for Reload at each row chains and for which lookup's reject you see first.

Join key (`Expr. key`): any Java expression on the lookup column cell, evaluated against the Main row and earlier lookups, e.g. `row1.customer_id`, `row1.code.trim().toUpperCase()`, `Var.key`. Several `Expr. key` cells on one lookup = composite key, all must match (AND). Matching uses `equals()`/`hashCode()` on the key value(s): type must be identical (`Integer` 1 never matches `Long` 1L, `"1"` never matches 1), Strings are case- and whitespace-sensitive, Dates compare to the millisecond, BigDecimal compares scale too (see `Ignore trailing zeros for BigDecimal`). A lookup with no `Expr. key` but with an expression filter is a filtered cross join (every main row scans every lookup row). Indirect joins: lookup B keyed on a column of lookup A (`row2.col`) are allowed; order the tables top-down.

Older Studios (<= 4.x) labelled the key cell `Hash key`; the semantics are the same (in-memory hash on the key).

| Setting (lookup table header) | Values | Semantics |
|---|---|---|
| Match Model | `Unique match` (default), `First match`, `All matches` | Unique match returns the LAST loaded matching lookup row (docs: "functions as a Last match"). First match returns the first loaded. All matches emits one output row per matching lookup row (fan-out, cartesian within the key). Load order is the lookup component's read order (DB: unordered unless `ORDER BY`). |
| Join Model | `Left Outer Join` (default), `Inner Join` | Left Outer: unmatched main rows pass with lookup columns `null`. Inner Join: unmatched main rows are dropped from normal outputs and are available to an output with `Catch lookup inner join reject = true`. |
| Lookup Model | `Load once` (default), `Reload at each row`, `Reload at each row (cache)` | Load once: whole lookup flow executed once, before the first main row, into memory (or disk with Store temp data). Reload at each row: the entire lookup branch (all upstream components of the lookup link) re-executes for every main row; `globalMap Key` field appears. Reload at each row (cache): same but results accumulate in an in-memory cache keyed by the globalMap key; only unseen keys trigger a reload; incompatible with Store temp data. |
| Store temp data | `false` (default), `true` | Spill the lookup to disk under `Temp data directory path`, in chunks of `Max buffer size (nb of rows)`. Needed for lookups larger than heap. Not usable with Reload at each row (cache). |
| Expression filter (funnel icon) | Java boolean | Applied to lookup rows at load time (Load once) or to the join result (per doc it filters the lookup data before matching). On the Main table it filters main rows: rows failing it are dropped silently and are NOT catchable by any reject output. |
| globalMap Key | expression + key name | Only with Reload models. See next section. |

Typical multi-lookup pattern: Main `row1` -> lookup `row2` (customers, key `row1.cust_id`) -> lookup `row3` (regions, key `row2.region_id`). Set `row2`/`row3` columns Nullable so a Left Outer miss does not blow up primitives.

## tMap: Reload at each row with globalMap

Purpose: parameterize the lookup query per main row (large reference table, small main flow, or data that changes while the Job runs).

Steps:
1. Lookup table header: Lookup Model = `Reload at each row` (or `(cache)`). A `globalMap Key` area appears with `+`.
2. Add a key: `Expression` = value taken from the main row, e.g. `row1.id`; `globalMap Key` = the name, e.g. `"id"` (docs example uses `"people.Age"`). tMap performs `globalMap.put("id", row1.id)` before (re)running the lookup branch for that main row.
3. In the lookup input component (tMysqlInput, tDBInput, tFileInputDelimited, tRESTClient, ...), reference it with a cast:

```java
"SELECT id, name, email FROM person WHERE id = " + ((Integer)globalMap.get("id"))
"SELECT * FROM people WHERE age > " + ((Integer)globalMap.get("people.Age"))
"... WHERE code = '" + ((String)globalMap.get("code")) + "'"
```

4. Keep the lookup's `Expr. key` populated (e.g. `row1.id` on `row2.id`) so tMap still matches the reloaded rows; with (cache) the key is what the cache is indexed by.

Alternative placement of the put: a `Var` row in tMap cannot put into globalMap in a way that precedes the lookup (Vars are evaluated after lookups are resolved for the row), so use the globalMap Key area, or a tJavaRow/tJavaFlex before tMap doing `globalMap.put("id", input_row.id);` (works because the main row passes that component before tMap reloads the lookup).

Behaviour notes:
- The whole lookup branch re-runs: a tDBInput reopens a statement per main row (use a prepared/indexed query and `Use an existing connection`); a tFileInput re-reads the file; a tMap in the lookup branch re-executes.
- `Load once` with a `globalMap.get` in the query runs the query once, before any main row, so the key is `null` -> `WHERE id = null` returns nothing or a SQL error. That is the classic "lookup query not updated" symptom.
- Reload at each row (cache) assumes the lookup data for a given key is stable for the Job's duration.
- Spark Streaming: Reload at each row only supported for Lookup Input components; Spark Batch tMap has no Reload at each row.

## tMap: Var table

- Click `+` in the Var table, set Type and Nullable, name it (Java identifier), write the Expression. Refer to it as `Var.name` in outputs and in LATER Var rows (order top to bottom is evaluation order; use the arrows to reorder).
- Vars are evaluated once per main row (per fan-out row with All matches), after lookups are resolved, BEFORE output expressions and output filters. Side effects (`Numeric.sequence`, `globalMap.put`) happen even for rows later rejected by an output filter.
- Vars are the place for: expensive sub-expressions reused across outputs, trimmed/normalized keys, running totals and previous-row memory (via globalMap), surrogate keys.
- Var type must match the expression's Java type exactly (no auto-conversion); `Nullable` unchecked on Integer/Long/Double/... makes the field primitive.

```java
// Var table rows, in order
Var.fullName   (String)  : (row1.first == null ? "" : row1.first.trim()) + " " + (row1.last == null ? "" : row1.last.trim())
Var.ageOk      (boolean) : row1.age != null && row1.age >= 18
Var.sk         (Integer) : Numeric.sequence("cust_sk", 1, 1)
Var.amountNet  (BigDecimal): row1.amount == null ? java.math.BigDecimal.ZERO : row1.amount.subtract(row1.discount == null ? java.math.BigDecimal.ZERO : row1.discount)
```

## tMap: outputs, filters, rejects

Add an output: `+` on the output side -> `Add an output` dialog: `New output` (name = link name, must be a valid Java identifier), or `Create join table from` an existing output with a `Named` name (unverified label details). A join table output is bound to its parent output: it receives the parent's rows and adds its own `Inner join` filter check box (unverified), used for the "same rows, extra projection" pattern; most designs simply use separate outputs with filters.

| Output header setting | Effect |
|---|---|
| Expression filter (funnel) | Java boolean; `true` rows go to this output. Several outputs can be true for the same row (a row can be emitted to many outputs; tMap is not a switch). |
| `Catch output reject` = true | This output receives rows for which EVERY other (non-reject) output's filter was false (rows filtered out). Columns are whatever you map (usually drag all main columns). Filters on a reject output itself are also applied. |
| `Catch lookup inner join reject` = true | Receives main rows dropped by any lookup set to `Inner Join` (lookup columns are null for the missing lookup). Requires at least one lookup with Join Model = Inner Join, otherwise it never receives rows. |
| `tMap settings` (wrench) | Opens the two check boxes above as a property table (6.x+). |
| ErrorReject link (component level) | Only when Property Settings > `Die on error` is unchecked: right-click tMap > Row > `ErrorReject`. Carries the input columns plus `errorMessage` and `errorStackTrace` (String). Rows whose expressions throw (NPE, NumberFormatException, ...) go there instead of killing the Job. |

Output expression cells: any Java expression of the column's type.

```java
row1.name == null ? null : row1.name.trim().toUpperCase()
row2.region == null ? "UNKNOWN" : row2.region            // lookup miss default
row1.qty * (row1.unitPrice == null ? 0d : row1.unitPrice) // Double column
TalendDate.formatDate("yyyy-MM-dd", row1.created)          // Date -> String
row1.active ? "Y" : "N"                                     // boolean (primitive) -> String
Var.sk                                                      // from Var table
```

Schema of a reject output: define it yourself (Schema editor); nothing is auto-populated except for the ErrorReject link. Drag the main table header onto the output to copy all columns.

Row ordering of outputs: each main row is processed fully (all outputs) before the next; outputs are written in table order.

## tMap: settings (Property Settings and Component view)

Property Settings dialog (wrench in the editor toolbar), Standard Job:

| Setting | Default | Notes |
|---|---|---|
| `Die on error` | checked | Unchecked enables the ErrorReject output link and continues on expression exceptions. |
| `Lookup in parallel` | unchecked | Loads several lookups in parallel threads (Load once). Helps with many large lookups; more heap pressure. |
| `Temp data directory path` | empty | Folder for spilled lookups when any lookup has Store temp data = true. Use a context var; must be writable and large. |
| `Max buffer size (nb of rows)` | 2000000 | Rows per spill chunk; lower it when rows are wide. |
| `Ignore trailing zeros for BigDecimal` | unchecked | Normalizes BigDecimal keys/values (`stripTrailingZeros`) so `1.0` and `1.00` compare equal in joins. |

Component view > Basic settings: `Map Editor` button, `Mapping links display as` (Auto / Curves / Lines), `Preview`. Advanced settings: `Temp data directory path`, `Max buffer size (nb of rows)`, `Ignore trailing zeros for BigDecimal` (mirrors of the dialog), `tStatCatcher Statistics`. There is no `Enable parallelize` on tMap; parallel execution belongs to tParallelize / the Job's `Multi thread execution` / tPartitioner (Enterprise).

Dynamic schema: a column of type `Dynamic` can traverse tMap; map it whole (`row1.dyn`) or address columns via the Dynamic API in a routine. Expression filters cannot see inside it.

## tMap: mapping behaviours (types, null, dates, keys)

Type rules (generated Java, compiled by Studio):
- No implicit conversion beyond Java's: widening (`int`->`long`->`double`), boxing/unboxing. Anything else (String->Integer, Date->String, Integer->String) needs an explicit expression; otherwise `Type mismatch: cannot convert from ...` at compile.
- `Nullable` checkbox: for Boolean, Byte, Character, Double, Float, Integer, Long, Short the generated field is primitive when unchecked (`int`) and boxed when checked (`Integer`). String, Date, BigDecimal, byte[], Object, List, Document, Dynamic are always references.
- Consequences: `row1.age == null` on a non-nullable Integer -> compile error `incomparable types: int and <nulltype>`; writing `null` into a non-nullable output column -> compile error; a Left Outer lookup miss into a non-nullable lookup column yields a NullPointerException at unboxing (or Studio refuses to compile, depending on version). Rule: every lookup column you read and every optional source column is Nullable.
- Ternaries must have both branches of compatible type: `cond ? null : 1` compiles to Integer; `cond ? 0 : null` compiles but unboxes to NPE if the target is `int`.
- Output `Default` column (schema editor) is only used by some writers (tFileOutput*), not by tMap when the expression is null.

Null handling idioms:

```java
row1.s == null ? "" : row1.s                           // default empty
Relational.ISNULL(row1.s) ? "" : row1.s                // same via routine
row1.i == null ? 0 : row1.i                            // Integer -> int target
(row1.d == null) ? null : TalendDate.formatDate("yyyyMMdd", row1.d)
row2.name == null ? "NA" : row2.name                   // lookup miss: columns are null; `row2 == null` is not a usable test
```

Date comparisons: never `==`/`<`. Use `row1.d1.after(row1.d2)`, `row1.d1.before(d2)`, `row1.d1.compareTo(d2) > 0`, `TalendDate.compareDate(d1, d2)` (returns -1/0/1), `TalendDate.compareDate(d1, d2, "yyyy-MM-dd")` for date-part only. `java.util.Date.equals` requires identical millis.

String comparisons: `"A".equals(row1.s)` (null-safe when the literal is on the left), `row1.s != null && row1.s.equalsIgnoreCase("a")`, `java.util.Objects.equals(row1.a, row2.a)`. `==` compares references and is wrong except for interned literals.

String trimming/normalization of keys on BOTH sides: `row1.code.trim().toUpperCase()` in the lookup `Expr. key` and the same on the lookup column via its own Var or upstream tMap; a key mismatch due to trailing spaces from CHAR columns is the most common silent lookup miss.

Multi-column keys: fill `Expr. key` on each lookup column that participates; or build a single composite key in a Var (`row1.a + "|" + row1.b`) and match on a precomputed column of the lookup.

## tMap: performance

- Load once lookups live in heap as hash structures: cost ~ rows x width. Project only the columns you need in the lookup component's schema (tMap loads every schema column, not only mapped ones) and filter rows at the source (`WHERE`), not with the tMap expression filter.
- Keep lookup keys small and of simple types; avoid building keys with string concatenation per row when a typed composite is possible.
- `Store temp data` turns memory into disk I/O (sorted chunks + merge). Use it when the lookup is far larger than heap; otherwise raise `-Xmx` (Run view > Advanced settings > JVM arguments, or the launcher script).
- `Reload at each row` is O(main rows x lookup query cost): only with an indexed, selective query and `Use an existing connection`; prefer `(cache)` when keys repeat.
- `All matches` multiplies rows; combine with Inner Join and an aggregation downstream only when intended.
- `Lookup in parallel` helps when you have several big lookups from slow sources.
- Multiple tMaps in series each cost a row copy; collapse when possible, but a tMap per concern is still readable and cheap compared to a lookup load.
- Spark tMap: joins compile to Spark joins (shuffle unless the lookup is broadcast; broadcast is picked when the lookup is small); no Store temp data, no Reload at each row (batch), `Numeric.sequence` is not globally monotonic across partitions, `globalMap` per-row tricks do not work. Use tPartition / Spark config, not tMap settings, to tune.

## tXMLMap

Role: tMap for hierarchical data. Columns of type `Document` (routines.system.Document, a dom4j DOM wrapper) show as editable XML trees in the editor; flat columns behave as in tMap. Handles XML-to-flat, flat-to-XML, XML-to-XML, and joins between documents. Component is Standard only (Spark has no tXMLMap).

Setting up a Document column: in the input/output schema set Type = `Document`. In the editor the column appears as a root node; right-click menu (names approximate across versions):

| Action | Effect |
|---|---|
| `Import From File` / `Import From Repository` | Build the tree from an XML/XSD file or from Metadata > File xml / XSD. |
| `Create Sub-Element`, `Create Attribute`, `Create Name Space` | Add nodes. Attributes show as `@name`; namespaces as `xmlns:prefix` nodes whose fixed value is the URI; a default namespace is a node named `xmlns`. |
| `Set A Fix Value` | Constant output (quoted String expression). |
| `Set As Loop Element` | Node tXMLMap iterates over. At least one loop per Document flow; the root is the default loop. Input may have several loops; `Set As Optional Loop` falls back to the parent when the element is missing. |
| `As group element` | Output: wraps rows that share the values of its non-loop sub-elements into one group; must be an ancestor of the loop element; root cannot be a group. Keeps a single flow (one Document). |
| `As aggregate element` | Output: like group but each aggregate value yields a separate, complete XML Document (splits the flow). Disables `All in one`. |
| `Add Choice` / `Add Substitution` | xs:choice / substitution group support (unverified labels). |
| Loop sequence (multiple input loops) | When an input Document has several loop elements, a `Loop sequence` / multi-loop dialog defines the iteration order and whether loops are nested or independent (unverified label). |

Output-side `tMap settings` (wrench on the output table):

| Setting | Values | Meaning |
|---|---|---|
| `All in one` | true/false | true: all generated XML for the flow goes into one Document (one output row). false: one Document per loop iteration (one output row per loop). Disabled when an aggregate element exists. |
| `Create empty element` | true/false | Emit elements whose mapped value is null/empty (needed for tWriteXMLField/fixed structures). |
| `Catch output reject`, `Catch lookup inner join reject` | true/false | As tMap. |
| `Die on error` (Property Settings) | checked | As tMap. |

Expressions on XML nodes use bracketed XPath-like references, not dots:

```java
[row1.payload:/order/customer/@id]            // attribute
[row1.payload:/order/items/item/price]        // element under the loop
[row2.ref:/ns1:catalog/ns1:product/ns1:name]  // namespaced (prefix declared via xmlns:ns1 node)
```

Dragging an input node onto an output node creates such an expression; you can wrap it in Java (`[row1.doc:/a/b] == null ? "" : [row1.doc:/a/b].trim()` is NOT supported in all versions: the bracket token is substituted as a String variable, so plain Java around it generally works, but keep logic in a Var where possible) (unverified edge).

Joins between documents: drag a node of the main Document onto a node of the lookup Document to fill its `Expr. key`; lookup header has `Match Model` (Unique/First/All matches), `Join Model` (Left Outer/Inner), `Lookup Model` (`Load once`, `Reload at each row`, `Reload at each row (cache)`) with the same semantics as tMap.

Namespaces in output: declare via `Create Name Space` on the element that should carry `xmlns:prefix`; child element names then use `prefix:name`. `[xmlns]`-style literal attributes are not needed. Mapping a whole subtree: drag the parent node; tXMLMap copies the subtree when the structures match (unverified).

Reading/writing Documents: tFileInputXML with a single Document output column and Loop XPath `/` + mapping `.` (or `tFileInputRaw` -> tExtractXMLField), tExtractXMLField/tWriteXMLField convert between String and Document, tFileOutputXML and tFileOutputRaw accept a Document column (unverified for tFileOutputRaw), tRESTClient/tESBProviderRequest exchange Documents, tJava can build one: `routines.system.Document d = new routines.system.Document(); d.setDocument(org.dom4j.DocumentHelper.parseText(xmlString));`.

Memory: each Document is a full DOM; a 2 GB XML file cannot be one Document. Split at the source (tFileInputXML loop on the repeating element, `Generation mode: Xerces/SAX` and per-record Documents) or use tFileInputMSXML / tExtractXMLField per field.

## tELTMap family

Concept: ELT components generate one SQL statement executed in the database; no rows pass through the Job. Three components per DB connected by links whose NAMES ARE TABLE NAMES.

| DB / family | Components | Notes |
|---|---|---|
| Generic JDBC (7.x+/8.0, help folder `elt-jdbc`) | tELTInput, tELTMap, tELTOutput | `Database` / mapping dropdown picks the SQL dialect; use with tDBConnection. |
| MySQL | tELTMysqlInput, tELTMysqlMap, tELTMysqlOutput | |
| Oracle | tELTOracleInput/Map/Output | tELTOracleOutput: `Use Merge Update`, `Use Merge Insert` (MERGE INTO); `NB_LINE_MERGED` global var; Hints supported. |
| PostgreSQL | tELTPostgresqlInput/Map/Output | |
| MS SQL | tELTMSSqlInput/Map/Output | |
| Teradata | tELTTeradataInput/Map/Output | MERGE / `Use Merge` option (unverified label); query banding in connection. |
| DB2, Sybase, Netezza, Vertica, Greenplum, Exasol (unverified for Exasol) | tELT<DB>Input/Map/Output | Same editor; dialect differences in quoting and join syntax. |
| Hive (Big Data) | tELTHiveInput, tELTHiveMap, tELTHiveOutput | Generates `INSERT [OVERWRITE] TABLE ... SELECT`; partitions via output settings. |
| Snowflake, Redshift, BigQuery | No tELT* family; use tDBRow / tSnowflakeRow / tRedshiftRow with handwritten SQL, or Qlik Talend Cloud pipelines (unverified: no tELTSnowflakeMap in 8.0 R-releases checked). | |

tELTInput: `Default Table Name` (must equal the outgoing link name), `Default Schema Name`, `Schema` (column list used by the map editor; `Edit schema` to define or pull from repository Metadata > Db Connections). No connection: it only describes a table.

tELTMap: `Use an existing connection` / connection parameters (the DB where the SQL runs), `ELT <DB> Map Editor` button. Editor:
- Input area: one table per incoming link; `+` adds a table or an ALIAS of an existing one (`Add alias` dialog: pick table, type alias) = "different table alias" for self-joins.
- Join: drag a column from one input table onto a column of another; tick `Explicit join` on the target column; `Join` dropdown per table: `INNER JOIN` (default), `LEFT OUTER JOIN`, `RIGHT OUTER JOIN`, `FULL OUTER JOIN`, `CROSS JOIN`, `LEFT INNER JOIN`/`RIGHT INNER JOIN` (dialect-dependent list; unverified exact set). Non-explicit joins become `WHERE a.x = b.y`.
- Join order = GUI order top-down; a LEFT JOIN placed before an INNER JOIN can lose rows (docs warn).
- Output area: one table per outgoing link (name = target table). Filter button adds `Where clauses` rows (free SQL fragments, ANDed) and `Other clauses` rows (`GROUP BY ...`, `ORDER BY ...`, `HAVING ...`, `LIMIT ...`). Expressions in output cells are SQL, e.g. `UPPER(cust.name)`, `SUM(ord.amount)`, `CASE WHEN ... END`; you may also write `tablename.column`.
- `Generated SQL Select query` tab at the bottom shows the SELECT for the selected output; copy it to test in a SQL client.
- Column expression referencing uses the table/alias name as it appears in the editor (link name or alias), e.g. `customers.id`.

tELTOutput:

| Setting | Values / notes |
|---|---|
| `Action on table` | None, Drop and create table, Create table, Create table if not exists, Drop table if exists and create, Clear table, Truncate table (set varies by DB). |
| `Action on data` | `Insert` (INSERT INTO target (cols) SELECT ...; duplicates on a unique key abort), `Update` (UPDATE ... SET ... from the mapped SELECT; needs WHERE), `Delete` (DELETE ... WHERE), `Merge` where the DB has MERGE (Oracle/Teradata/MSSql variants as `Use Merge ...` check boxes). |
| `Default Table Name` / `Default Schema Name` | Target when `Use different table name` is unchecked; otherwise `Table name` (and schema) fields override the link name. |
| `Use different table name` | Lets the link keep a logical name while writing to another physical table (staging, `tmp_...`). |
| `Where clauses (for UPDATE and DELETE only)` or `Use WHERE conditions table` (Column / Function / Value rows) | Filter for Update/Delete. |
| `Mapping` | DB type mapping file for create-table DDL. |
| `Use update set table` | Choose which columns go into SET (unverified label). |
| Globals | `NB_LINE_INSERTED`, `NB_LINE_UPDATED`, `NB_LINE_DELETED`, `NB_LINE_MERGED`, `QUERY` (the statement actually executed), `ERROR_MESSAGE`. |

Generated statement shape:

```sql
INSERT INTO target_sales (cust_id, region, total)
(SELECT c.id, UPPER(r.name), SUM(o.amount)
 FROM customers c INNER JOIN orders o ON (o.cust_id = c.id)
      LEFT OUTER JOIN regions r ON (r.id = c.region_id)
 WHERE o.status = 'OK'
 GROUP BY c.id, r.name)
```

ELT vs ETL: ELT = set-based, no network hop, uses DB indexes and parallelism, auditable SQL; but all sources must be in one DB (or linked), expressions are SQL (no routines, no Java null-handling), no row-level rejects, no per-row logging, DDL/dialect coupling, and tELTMap cannot mix with tMap in the same flow (no row link out of ELT components; use OnSubjobOk triggers). Pattern: bulk-load files to staging with tDBBulkExec/tDBOutput, then ELT joins/aggregates in-DB.

## Expression language

Expressions in tMap cells, component parameters (double-quoted fields), tJava* bodies and routines are Java compiled into the Job class. Component text fields expect a Java String expression, so literals are `"like this"`; concatenation with `+`; backslash escapes (`"C:\\data\\in.csv"`, `"\t"`, `"\n"`); char literals `'x'` for Character fields; numbers unquoted in numeric fields; booleans via check boxes.

| Token | Type | Example |
|---|---|---|
| `row1.col` | schema type of the column on link `row1` | `row1.amount * 1.2` |
| `Var.name` | Var table type | `Var.key` |
| `context.name` | context variable's declared type (`String`, `Integer`, `Long`, `Double`, `Boolean`, `Date`, `BigDecimal`, `Character`, `Short`, `Float`, `Byte`, `List`/`Object`; `Directory`, `File`, `Password`, `Resource` are Strings) | `context.inputDir + "/" + context.fileName`, `context.batchSize.intValue()` |
| `context.getProperty("name")` | String (ContextProperties extends `java.util.Properties`) | `context.getProperty("env")`; also `context.setProperty("k", "v")`, `context.getProperty(name, default)`, `context.toString()` to dump all |
| `globalMap.get("key")` | `Object`, cast required | `((Integer)globalMap.get("tFileInputDelimited_1_NB_LINE"))`, `((String)globalMap.get("tFileList_1_CURRENT_FILE"))`, `((java.sql.Connection)globalMap.get("conn_tDBConnection_1"))` |
| Routine calls | `RoutineName.method(...)` | `TalendDate.getDate("CCYY-MM-DD hh:mm:ss")`, `StringHandling.UPCASE(row1.s)`, `Numeric.sequence("s1",1,1)`, `MyRoutine.foo(row1.x)` |
| Job constants | `jobName`, `jobVersion`, `projectName` (String), `pid`, `rootPid`, `fatherPid` (String), `contextStr` (String, current context name), `errorCode` (Integer), `resuming_logs_dir_path`, `resuming_checkpoint_path` (String), `startTime`? (unverified) | `"Job " + jobName + " v" + jobVersion + " [" + contextStr + "] pid " + pid` |
| Ternary | Java | `row1.x == null ? "" : row1.x` |
| Static Java | fully qualified unless imported | `java.util.UUID.randomUUID().toString()`, `java.lang.Math.round(row1.d)`, `String.format("%05d", row1.i)`, `new java.math.BigDecimal("0.1")` |

Component label placeholders (Component view > View > Label format): `__UNIQUE_NAME__` (default), `__COMMENT__`, and any parameter name as `__PARAMNAME__` (e.g. `__TABLE__`, `__FILENAME__`, `__QUERY__`), useful to show the table on the canvas. Hint format uses the same tokens.

Outline view (Window > Show view > Talend > Outline): lists each component's exposed variables (After/Flow): `tFileList_1.CURRENT_FILE`, `tFileList_1.CURRENT_FILEPATH`, `.CURRENT_FILEDIRECTORY`, `.CURRENT_FILEEXTENSION`, `.NB_FILE`, `tFileInputDelimited_1.NB_LINE`, `tDBOutput_1.NB_LINE_INSERTED/UPDATED/DELETED/REJECTED`, `<comp>.ERROR_MESSAGE`, `tDBInput_1.QUERY`, `tAggregateRow_1.NB_LINE`, etc. Dragging one into a text field inserts the cast form `((String)globalMap.get("tFileList_1_CURRENT_FILE"))` (dot in the Outline, underscore in the key). Flow variables are valid while the component runs; After variables after it finishes (so `NB_LINE` is read in the next subjob via OnSubjobOk or in a tJava after the component).

Imports: in tMap expressions, routines are visible without import (`import routines.*;` and `import routines.system.*;` are generated). Other classes: fully qualify, or add imports in tJava*/tJavaFlex Advanced settings > `Import` (`import org.apache.commons.lang3.StringUtils;`). The jar must be on the classpath: tLibraryLoad in the Job, or the routine's `Edit Routine Libraries`, or Modules view.

Thread-safety: Var and row objects are per-tMap instance in one thread; `globalMap` is shared by the whole Job (and with `Multi thread execution` enabled on the Job > Extra tab all subjobs run concurrently against the same map; Talend generates a synchronized/concurrent map in that case (unverified), but your read-modify-write sequences are not atomic). Child Jobs (tRunJob) have their OWN `globalMap`; pass data via context params in and tBufferOutput / `Propagate` out.

## globalMap, context and job variables

`globalMap` is `java.util.Map<String, Object>` declared in the Job class; the Job itself puts component results (`NB_LINE`, `CURRENT_FILE`, `ERROR_MESSAGE`, `conn_<name>`, `QUERY`, `tFileList_1_NB_FILE`, `tLoop_1_CURRENT_VALUE`, `tForeach_1_CURRENT_VALUE`, `tSetGlobalVar` entries, `tFlowToIterate_1` entries named after columns or `<row>.<col>`, `tContextLoad_1_...`). Put your own with `globalMap.put("k", v)` (tJava*, tSetGlobalVar, tMap Var `(globalMap.put("k", v) == null) ? ... ` trick returns previous value; prefer tJavaRow). Keys are plain Strings; `get` returns `Object`, hence the casts. Missing key -> `null` -> NPE on unboxing (`((Integer)null).intValue()`), so guard: `globalMap.get("x") == null ? 0 : (Integer)globalMap.get("x")`.

tFlowToIterate exposes each column of the current row as `globalMap.get("row1.col")` (default `Use the default (key, value) in global variables`) or custom keys. tSetGlobalVar takes Key/Value expressions. tGlobalVarExplorer dumps the map at debug time.

Context: `context` is an instance of the generated `ContextProperties` (extends `java.util.Properties`) with a typed public field per variable and typed getters (`context.getX()` (unverified)). Values come from the `.item` defaults, `--context_param name=value`, tContextLoad (key=value rows; `Print operations`, `Disable warnings`), implicit context load (Project/Job settings), or `context.name = ...` assignments in tJava (allowed, variables are not final). Type coercion at load uses `ParserUtils.parseTo_<Type>`: Date expects `yyyy-MM-dd HH:mm:ss` (unverified default), Integer/Long/Double parse strictly, empty -> `null`, Boolean via `Boolean.parseBoolean`. Password-type values are stored encrypted in `.item`/context files and decrypted in `context` (plain String at runtime).

Job class fields usable anywhere: `jobName`, `jobVersion`, `projectName`, `pid`, `rootPid`, `fatherPid`, `contextStr`, `errorCode` (set when the Job ends in error; also `status` String `"end"`/`"failure"`), `resuming_logs_dir_path`, `resuming_checkpoint_path`, `parent_part_launcher`, `log4jLevel`, `startTime`/`end_Hash`/`start_Hash` (long timestamps per component, used by tStatCatcher) (unverified names). `resumeUtil` (`ResumeUtil`) writes checkpoint logs when `--resuming_logs_dir_path` is given (Enterprise recovery checkpoints).

## System routines

All are `public static` in package `routines`, visible from any expression. Signatures from docs plus memory; items marked (unverified) are memory only.

### TalendDate

| Method | Returns | Notes |
|---|---|---|
| `getDate()` / `getDate(String pattern)` | String | Current timestamp. Legacy Talend pattern tokens: `CC` century, `YY` year, `MM` month, `DD` day, `hh` hour (24h), `mm` minute, `ss` second: `getDate("CCYY-MM-DD hh:mm:ss")`. Default without pattern `dd/MM/yyyy` (docs) (unverified). |
| `getCurrentDate()` | Date | `new Date()`. |
| `parseDate(String pattern, String s)` / `parseDate(pattern, s, boolean lenient)` | Date | Java `SimpleDateFormat` pattern. Throws `RuntimeException` wrapping ParseException on bad input: guard with `isDate`. Not thread-safe issues avoided internally (caches formatters per thread). |
| `parseDateLocale(String pattern, String s, String languageOrCountryCode)` (+ lenient variant) | Date | `"EN"`, `"fr"`, `"de_DE"`. Needed for month names. |
| `parseDateInUTC(String pattern, String s)` (+ lenient) | Date | Treat string as UTC (unverified exact name). |
| `formatDate(String pattern, Date d)` | String | `formatDate("yyyy-MM-dd'T'HH:mm:ss.SSSXXX", d)`. Null date -> null (unverified). |
| `formatDateLocale(String pattern, Date d, String languageOrCountryCode)` | String | |
| `formatDateInUTC(String pattern, Date d)` | String | (unverified) |
| `addDate(Date d, int n, String dateType)` / `addDate(String dateString, String pattern, int n, String dateType)` | Date | `dateType` in `"yyyy"`, `"MM"`, `"dd"`, `"HH"`, `"mm"`, `"ss"`, `"SSS"`. Negative n subtracts. |
| `diffDate(Date d1, Date d2)` / `diffDate(Date d1, Date d2, String dateType)` | long | d1 - d2 in units; default `"dd"`. Months/years are calendar-based differences, not floored. |
| `diffDateFloor(Date d1, Date d2, String dateType)` | long | Floored difference (completed units). 6.x+. |
| `diffDateIgnoreDST(Date d1, Date d2, String dateType)` | long | 8.0 R2020+ (docs list it). |
| `compareDate(Date d1, Date d2)` / `compareDate(Date d1, Date d2, String pattern)` | int | -1/0/1; pattern variant compares only the formatted part (`"yyyy-MM-dd"` = date-only compare). |
| `getFirstDayOfMonth(Date d)` / `getLastDayOfMonth(Date d)` | Date | Docs for 7.2 spell them `getFirstDayMonth`/`getLastDayMonth`; check in Studio which spelling your version has (unverified). |
| `getPartOfDate(String partName, Date d)` | int | `"YEAR"`, `"MONTH"` (0-based like Calendar), `"DAY_OF_MONTH"`, `"HOUR"`, `"MINUTE"`, `"SECOND"`, `"DAY_OF_YEAR"`, `"DAY_OF_WEEK"`, `"WEEK_OF_YEAR"`, `"WEEK_OF_MONTH"`, `"TIMEZONE"`, `"ERA"`, `"AM_PM"` (unverified for the last two). |
| `isDate(String s, String pattern)` / `isDate(s, pattern, String languageOrCountryCode)` | boolean | Lenient by default: `"2024-02-30"` may pass. `isDateStrict(...)` (8.0 R2025+) uses java.time strict resolution. |
| `setDate(Date d, int value, String dateType)` | Date | Set one field. |
| `getRandomDate(String minDate, String maxDate)` | Date | Strings in `"yyyy-MM-dd"`. |
| `TO_CHAR(Date d, String pattern)` / `TO_DATE(String s, String pattern)` | String / Date | Oracle-style aliases of formatDate/parseDate (unverified). |
| `getDateFromString`? / `isWeekend`? | - | Do not exist; write your own. |

### TalendString

| Method | Returns | Notes |
|---|---|---|
| `replaceSpecialCharForXML(String s)` | String | `& < > " '` -> entities. |
| `checkCDATAForXML(String s)` | String | Leaves `<![CDATA[...]]>` intact, escapes the rest. |
| `talendTrim(String s, char fillChar, int alignment)` | String | Strip `fillChar` from end (-1), start (1), both (0). |
| `removeAccents(String s)` | String | NFD-based accent stripping. |
| `getAsciiRandomString(int length)` | String | Random printable ASCII. |
| `unionString(String delimiter, Object... parts)` | String | Joins with delimiter, skipping nulls (8.0 R2023+; signature unverified). |
| `addEscapeChars(String s, String... chars)` | String | Escapes given characters (8.0 R2024+; unverified). |
| `getRandomString`, `escapeRegex` | - | Not present (unverified). |

### StringHandling

| Method | Returns | Notes |
|---|---|---|
| `UPCASE(String)` / `DOWNCASE(String)` | String | |
| `LEN(String)` | int | NPE on null. |
| `LEFT(String s, int n)` / `RIGHT(String s, int n)` | String | n > length returns whole string. |
| `SUBSTR(String s, int start, int length)` | String | 0-based start (Java substring semantics) (unverified base). |
| `TRIM(String)` / `LTRIM(String)` / `RTRIM(String)` | String | ASCII whitespace only; not NBSP. |
| `INDEX(String s, String sub)` | int | -1 if absent. |
| `COUNT(String s, String sub)` | int | Occurrences. |
| `CHANGE(String s, String oldSub, String newSub)` | String | Literal replace-all (`String.replaceAll` with regex-quoted? treats as regex in older versions: escape `.`) (unverified). |
| `EREPLACE(String s, String regex, String replacement)` | String | Regex replace-all. |
| `ALPHA(String)` | boolean | True when characters are in alphabetical order (docs wording); rarely what you want. |
| `IS_ALPHA(String)` | boolean | All letters. |
| `DQUOTE(String)` / `SQUOTE(String)` | String | Wraps in `"` / `'`. |
| `SPACE(int n)` | String | n spaces. |
| `STR(char c, int n)` | String | Repeat char. |
| `TO_INTEGER`, `CHARAT` | - | Do not exist; use `Integer.parseInt`, `s.charAt(i)`. |

### Numeric

| Method | Returns | Notes |
|---|---|---|
| `sequence(String name, int start, int step)` | Integer | Static map keyed by name, shared by the whole JVM: parent and tRunJob children in the same JVM share `"s1"`; in Talend Runtime/JobServer-embedded or tests the counter persists across runs of the same classloader. First call returns `start`. |
| `resetSequence(String name, int start)` | void | Creates or resets. |
| `removeSequence(String name)` | void | |
| `random(Integer min, Integer max)` | Integer | Inclusive bounds (unverified). |
| `convertImpliedDecimalFormat(String targetFormat, String value)` | BigDecimal | COBOL-style implied decimals: `convertImpliedDecimalFormat("9V99", "123")` -> 1.23. |

### Relational

| Method | Returns |
|---|---|
| `ISNULL(Object o)` | boolean |
| `NOT(boolean b)` | boolean |
| `AND(boolean a, boolean b)`, `OR(boolean a, boolean b)` | not in the routine; use `&&`, `\|\|` (unverified absence). |

### Mathematical

Doubles in, double out unless noted: `ABS`, `ACOS`, `ASIN`, `ATAN`, `COS`, `SIN`, `TAN`, `EXP`, `LN`, `SQRT`, `PWR(double base, double exp)`, `MOD(double, double)`, `NEG`, `INT(double)` (truncates; returns long/int (unverified)), `FFLT` (truncate to float precision (unverified)), `NUM(String)` (true if numeric (unverified return type)), `REAL(String)`/`FIX` (unverified), `BITAND(long, long)`, `BITOR`, `BITXOR`, `BITNOT(long)`. Prefer `java.lang.Math` and `BigDecimal` for money.

### TalendDataGenerator

`getFirstName()`, `getLastName()`, `getUsStreet()`, `getUsCity()`, `getUsState()`, `getUsStateId()` (unverified) : String, from built-in fictitious lists; no parameters. Used in tRowGenerator functions. Edit the routine copy to change the lists.

### DataOperation

Legacy routine present in older Studios (5.x/6.x) with a handful of boolean/number helpers; contents not confirmed (unverified). Do not rely on it.

### Other visible routines

`ResumeUtil` (checkpoint/recovery logging, internal), `TalendThreadPool`/`TalendThreadUtils`? (unverified), `SharedDataSource` does not exist; shared DB connections are tDBConnection + `conn_` globalMap keys or `Use or register a shared DB Connection` (SharedDBConnection, 5.x) on the connection component.

## routines.system internals (ParserUtils, FormatterUtils, Dynamic, Document)

Package `routines.system` (generated into every Job; import is implicit). Useful, stable-ish helpers:

```java
// ParserUtils: what generated readers use to convert file strings to schema types
routines.system.ParserUtils.parseTo_Integer(String)            // null/empty -> null; NumberFormatException otherwise
routines.system.ParserUtils.parseTo_Long(String)
routines.system.ParserUtils.parseTo_Double(String)
routines.system.ParserUtils.parseTo_Float(String)
routines.system.ParserUtils.parseTo_Short(String)
routines.system.ParserUtils.parseTo_Byte(String)
routines.system.ParserUtils.parseTo_Boolean(String)            // "true"/"1" -> true (unverified for "1")
routines.system.ParserUtils.parseTo_Character(String)
routines.system.ParserUtils.parseTo_BigDecimal(String)
routines.system.ParserUtils.parseTo_Date(String s, String pattern)           // lenient=false
routines.system.ParserUtils.parseTo_Date(String s, String pattern, boolean lenient)
routines.system.ParserUtils.parseTo_Number(String s, Character thousandsSep, Character decimalSep)  // -> String normalized (unverified)
routines.system.ParserUtils.parseTo_Integer(String s, boolean isDecode, Character thousandsSep, Character decimalSep) // "Advanced separator" readers (unverified)

// FormatterUtils: what generated writers use
routines.system.FormatterUtils.format_Date(java.util.Date d, String pattern)
routines.system.FormatterUtils.format_Date_Locale(java.util.Date d, String pattern, String locale)
routines.system.FormatterUtils.format_Number(String value, Character thousandsSep, Character decimalSep)
routines.system.FormatterUtils.format_Number_Locale(String value, String locale)  (unverified)

// Document (type Document)
routines.system.Document doc = new routines.system.Document();
doc.setDocument(org.dom4j.DocumentHelper.parseText("<a><b>1</b></a>"));
org.dom4j.Document dom = doc.getDocument();
String xml = doc.toString();                                    // serialized XML

// Dynamic (type Dynamic) and DynamicMetadata
routines.system.Dynamic dyn = row1.dynCol;
int n = dyn.getColumnCount();
for (int i = 0; i < n; i++) {
  routines.system.DynamicMetadata md = dyn.getColumnMetadata(i);
  String name = md.getName();        // column name
  String type = md.getType();        // "id_String", "id_Integer", "id_Date", "id_BigDecimal", ...
  String dbType = md.getDbType();    // native type, when read from a DB
  Object v = dyn.getColumnValue(i);  // or dyn.getColumnValue(name) (unverified overload)
  dyn.setColumnValue(i, v);
}
int idx = dyn.getIndex("CUST_ID");   // -1 if absent
dyn.removeColumn(idx);
dyn.clearColumnValues();
// add a column
routines.system.DynamicMetadata m = new routines.system.DynamicMetadata();
m.setName("NEW_COL"); m.setType("id_String"); m.setDbType("VARCHAR"); m.setLength(50); m.setNullable(true); m.setKey(false); m.setFormat("");
dyn.metadatas.add(m); dyn.addColumnValue("x");
```

`RowState` (used by tFileInput* in generated code to flag parse errors per row) and `BigDataParserUtils` are internal; do not depend on them.

## User routines

- Repository > Code > Routines > right-click > `Create routine` (or `Create folder`). Dialog: Name (class name, PascalCase), Purpose, Description, Author, Version, Status. Generates `routines/<Name>.java` with a sample `helloExample` and the Javadoc tag convention.
- Rules: package `routines`; one `public class <Name>`; methods `public static`; keep them stateless or deliberately static (shared JVM-wide, like `Numeric.sequence`). Javadoc tags drive the Expression Builder:

```java
package routines;

public class StringUtilsX {
    /**
     * nz: returns the default when the input is null or blank.
     *
     * {talendTypes} String
     *
     * {Category} User Defined
     *
     * {param} string("abc") s: input
     * {param} string("N/A") dflt: default
     *
     * {example} nz(null, "N/A") # N/A
     */
    public static String nz(String s, String dflt) {
        return (s == null || s.trim().isEmpty()) ? dflt : s;
    }
}
```

- Use anywhere Java is accepted: `StringUtilsX.nz(row1.s, "N/A")` in tMap, tJava*, component fields, context defaults (not), Spark Jobs (routines are shipped to executors).
- Dependencies: right-click the routine > `Edit Routine Libraries` > `New...` > `Browse a library file` (jar from disk; copied into the workspace `lib/java` and registered in Modules) or `Platform` (Studio-bundled jar). The jar then travels with every Job that depends on the routine. Equivalent for a single Job: tLibraryLoad. Studio 7.x+ also offers Repository > Code > `Custom routine jars`?/Modules view install (unverified label).
- Job dependency: right-click Job > `Setup routine dependencies` -> two lists, System routines (always all) and User routines (`+` to add). Studio 6.x+ adds all user routines by default to new Jobs; deselecting trims the build. A routine used but not listed gives `cannot find symbol` / `<Routine> cannot be resolved` at build time (works in Studio run because the whole project is on the classpath).
- Beans (Repository > Code > Beans): same mechanism for Routes (Camel bean classes, package `beans`); see esb-routes-services.md. Pig UDFs (Code > Pig UDF, Big Data, removed in 8.0) are Pig-specific routine templates; see big-data-spark.md.
- Versioning: routines have m.m versions like Jobs (right-click > `Open another version`, `Save as`). Jobs reference the latest routine version at build time (no pinning).
- Testing: no routine-level test runner. Use a scratch Job with tJava/tFixedFlowInput + tAssert, or a Job `Test Case` (Enterprise testing framework) around a tJavaRow calling the routine. Unit tests with JUnit are possible by exporting routines as a jar and testing outside Studio.
- Packaging: builds put compiled routines in a `routines.jar` / `<project>_routines-<ver>.jar` under `lib/`; see artifact-formats.md.
- Git/SVN: `.item` + `.properties` under `<project>/code/routines/`. Shared across all Jobs of the project; a change affects every Job on next build.

## Data types and conversions

Schema editor Type -> generated Java (non-nullable / nullable):

| Talend type | Java (Nullable off / on) | Null-capable | Typical parse from String | Typical format to String |
|---|---|---|---|---|
| Boolean | `boolean` / `Boolean` | only nullable | `Boolean.parseBoolean(s)` (anything not "true" -> false); `"1".equals(s) \|\| "Y".equalsIgnoreCase(s)` | `String.valueOf(b)`, `b ? "Y" : "N"` |
| Byte | `byte` / `Byte` | only nullable | `Byte.parseByte(s)` | `String.valueOf(b)` |
| byte[] | `byte[]` | yes | `s.getBytes("UTF-8")`, Base64 `java.util.Base64.getDecoder().decode(s)` | `new String(b, "UTF-8")`, Base64 encode. Used for BLOB/BINARY/VARBINARY. |
| Character | `char` / `Character` | only nullable | `s.charAt(0)`; `ParserUtils.parseTo_Character(s)` | `String.valueOf(c)` |
| Date | `java.util.Date` | yes | `TalendDate.parseDate("yyyy-MM-dd", s)`; `ParserUtils.parseTo_Date(s, "yyyy-MM-dd HH:mm:ss")` | `TalendDate.formatDate("yyyy-MM-dd HH:mm:ss.SSS", d)`. DB TIMESTAMP, DATE, TIME all map to Date; `java.sql.Timestamp` is a Date subclass and flows through. Schema `Date Pattern` (default `dd-MM-yyyy`) is used by file readers/writers and tLogRow, not by tMap. |
| Double | `double` / `Double` | only nullable | `Double.parseDouble(s)` (accepts "1e3", rejects ","); `Double.valueOf(s.replace(",", "."))` | `String.valueOf(d)` (scientific for large), `String.format("%.2f", d)`, `new java.text.DecimalFormat("#0.00").format(d)` |
| Float | `float` / `Float` | only nullable | `Float.parseFloat(s)` | `String.valueOf(f)` |
| BigDecimal | `java.math.BigDecimal` | yes | `new java.math.BigDecimal(s)` (rejects blanks/commas), `ParserUtils.parseTo_BigDecimal(s)` | `d.toPlainString()` (never `toString()` for money: it may give `1E+3`), `d.setScale(2, java.math.RoundingMode.HALF_UP)`. Schema Length = precision, Precision = scale; writers may round to scale. Use `compareTo` for equality. |
| Integer | `int` / `Integer` | only nullable | `Integer.parseInt(s.trim())`, `ParserUtils.parseTo_Integer(s)` | `String.valueOf(i)`, `Integer.toString(i)`, `String.format("%08d", i)` |
| Long | `long` / `Long` | only nullable | `Long.parseLong(s)` | `String.valueOf(l)` |
| Object | `Object` | yes | cast | `String.valueOf(o)`. Used for CLOB/ARRAY/STRUCT/unknown DB types; Oracle CLOB read as String when the driver allows. |
| Short | `short` / `Short` | only nullable | `Short.parseShort(s)` | |
| String | `String` | yes | - | - |
| List | `java.util.List` | yes | `java.util.Arrays.asList(s.split(","))` | `String.join(",", list)` |
| Document | `routines.system.Document` | yes | parse via dom4j (see above) | `doc.toString()` |
| Dynamic | `routines.system.Dynamic` | yes | - | - |

Cross-type idioms:

```java
Integer -> String   : row1.i == null ? null : String.valueOf(row1.i)
String  -> Integer  : (row1.s == null || row1.s.trim().isEmpty()) ? null : Integer.parseInt(row1.s.trim())
String  -> Date     : TalendDate.isDate(row1.s, "dd/MM/yyyy") ? TalendDate.parseDate("dd/MM/yyyy", row1.s) : null
Date    -> String   : row1.d == null ? "" : TalendDate.formatDate("yyyy-MM-dd", row1.d)
Date    -> long     : row1.d.getTime()            ;  long -> Date : new java.util.Date(row1.l)
Date    -> sql.Timestamp : new java.sql.Timestamp(row1.d.getTime())
Double  -> BigDecimal: java.math.BigDecimal.valueOf(row1.dbl)   // not new BigDecimal(double): binary noise
BigDecimal -> Double : row1.bd.doubleValue()
BigDecimal -> Integer: row1.bd.intValueExact()      // throws on fraction/overflow; intValue() truncates
Integer -> Long     : row1.i == null ? null : row1.i.longValue()   // Long.valueOf(int) also fine; (Long) cast on Integer fails
Long    -> Integer  : row1.l.intValue()
boolean -> Integer  : row1.b ? 1 : 0
String  -> Boolean  : "1".equals(row1.s) || "true".equalsIgnoreCase(row1.s) || "Y".equalsIgnoreCase(row1.s)
String  -> Character: row1.s == null || row1.s.isEmpty() ? null : row1.s.charAt(0)
Object  -> String   : row1.o == null ? null : row1.o.toString()
```

SimpleDateFormat letters: `yyyy` year, `MM` month, `dd` day, `HH` 0-23 hour, `hh` 1-12, `mm` minute, `ss` second, `SSS` millis, `a` AM/PM, `EEE`/`EEEE` weekday, `MMM`/`MMMM` month name (locale), `Z` `+0100`, `XXX` `+01:00`, `z` zone name, `'T'` literal. `YYYY` is week-year (wrong around New Year); `DD` is day-of-year; `mm` vs `MM` is the #1 pattern bug. Patterns in component fields are Java strings: `"yyyy-MM-dd'T'HH:mm:ss"`.

Date/time zone: `java.util.Date` is an instant; formatting uses the JVM default zone (`-Duser.timezone=UTC` in JVM args makes Jobs deterministic). DB DATE columns without time read as midnight local.

## tJava, tJavaRow, tJavaFlex code context

| Component | Flow | Visible variables | Code sections | Notes |
|---|---|---|---|---|
| tJava | None (trigger-only: OnSubjobOk/OnComponentOk/Iterate). | `globalMap`, `context`, job fields (`jobName`, `pid`...), routines, any class imported in Advanced settings > `Import`. No `row1`. | Single `Code` box, executed once when triggered. | Use for setup/teardown, logging, `globalMap.put`, computing context values. Cannot read the current row of a flow; place a tJavaRow in the flow instead. |
| tJavaRow | Row in, row out (one output link, same or different schema). | `input_row.<col>`, `output_row.<col>`, plus `globalMap`, `context`, `routines`. Also the actual link names work (`row1.col`) but `input_row`/`output_row` are the portable aliases. | `Code` executed once per row. `Generate code` button writes `output_row.c = input_row.c;` for matching columns (run it after schema changes). | Must assign every output column you need; unassigned = null/0. To drop a row you cannot `return`: set a flag column and filter after, or use tJavaFlex. `nb_line`/`NB_LINE` global after. |
| tJavaFlex | Row in (optional) and/or row out (optional). Can be a generator (no input). | Input link name (`row1.col`), output link name (`row2.col`), `globalMap`, `context`. | `Start code` (before the first row; open loops `for (...) {`, init counters), `Main code` (per row; inside the loop you opened), `End code` (close braces, flush, `globalMap.put`). `Data Auto Propagate` check box copies input columns to the same-named output columns before Main code. | The three sections are concatenated into the generated class; unbalanced braces give cryptic compile errors. As a generator: Start `for (int i=0;i<10;i++) {`, Main `row2.id = i;`, End `}`. |

Common code:

```java
// tJava: read component results, log, store a connection
int n = ((Integer)globalMap.get("tFileInputDelimited_1_NB_LINE"));
System.out.println(jobName + ": read " + n + " rows from " + ((String)globalMap.get("tFileList_1_CURRENT_FILE")));
java.sql.Connection conn = (java.sql.Connection)globalMap.get("conn_tDBConnection_1");  // key = "conn_" + unique name
java.sql.PreparedStatement ps = conn.prepareStatement("UPDATE batch SET status=? WHERE id=?");
globalMap.put("batchId", java.util.UUID.randomUUID().toString());
context.outFile = context.outDir + "/out_" + TalendDate.getDate("CCYYMMDD") + ".csv";   // context fields are writable

// tJavaRow: transform + previous-row memory
output_row.id = input_row.id;
output_row.name = input_row.name == null ? null : input_row.name.trim();
String prev = (String)globalMap.get("prevName");
output_row.isDup = prev != null && prev.equals(output_row.name);
globalMap.put("prevName", output_row.name);

// tJavaFlex: running total with Start/Main/End
// Start:
double total = 0d;
int count = 0;
// Main:
total += (row1.amount == null ? 0d : row1.amount);
count++;
row2.id = row1.id;
row2.runningTotal = total;
// End:
globalMap.put("grandTotal", total);
globalMap.put("rowCount", count);
```

Imports go in Advanced settings > `Import` as full statements (`import java.util.*;`). The jar must be present (tLibraryLoad with `Load library` in the same Job, or a routine dependency). Static/instance state across rows in tJavaRow: declare it in a tJava earlier + globalMap, or in tJavaFlex Start code (local to the component's generated block), or as a static field in a routine.

Connection sharing: tDBConnection registers `conn_<name>` (and `db_<name>` for some, plus `conn_<name>_<ds>` with datasource aliases (unverified)); tDBCommit/tDBRollback/tDBClose act on it. Transactions span components only through `Use an existing connection`. In Talend Runtime/ESB, prefer datasource aliases over raw connections.

## Mapping recipes

```java
// 1. Null-safe concatenation (tMap output or Var)
(row1.first == null ? "" : row1.first.trim()) + (row1.last == null ? "" : " " + row1.last.trim())

// 2. Date reformat with validation (String -> String)
TalendDate.isDate(row1.dt, "MM/dd/yyyy") ? TalendDate.formatDate("yyyy-MM-dd", TalendDate.parseDate("MM/dd/yyyy", row1.dt)) : null

// 3. Conditional default / coalesce chain
row1.phone != null ? row1.phone : (row1.mobile != null ? row1.mobile : "UNKNOWN")

// 4. Lookup with fallback (Left Outer Join lookup row2)
row2.category == null ? "UNCATEGORIZED" : row2.category
// detect miss explicitly for a flag column (boolean)
row2.id == null

// 5. Split a string: Var parts (String[]) = row1.addr == null ? new String[0] : row1.addr.split(";", -1)
// outputs:
Var.parts.length > 0 ? Var.parts[0] : null
Var.parts.length > 1 ? Var.parts[1].trim() : null
// (Var table cannot hold String[] in all versions: use type Object and cast ((String[])Var.parts)[0]) (unverified)

// 6. Trim + upper for keys (do it on BOTH sides of the join)
row1.code == null ? null : row1.code.trim().toUpperCase()

// 7. Regex extraction (first capture group, null-safe)
row1.s != null && row1.s.matches(".*\\b(\\d{5})\\b.*") ? row1.s.replaceAll(".*\\b(\\d{5})\\b.*", "$1") : null
// heavier but clearer in a routine:
//   java.util.regex.Matcher m = java.util.regex.Pattern.compile("(\\d{5})").matcher(s); return m.find() ? m.group(1) : null;

// 8. Surrogate key (Var sk, Integer) ; reset per run; offset from DB max via globalMap
Numeric.sequence("sk", ((Integer)globalMap.get("maxId")) + 1, 1)
// tJava before: globalMap.put("maxId", ((Integer)globalMap.get("tDBInput_1_...")) ...) or use a tDBInput -> tJavaRow that puts input_row.maxid

// 9. Running total via Var + globalMap (single-threaded tMap); two Vars, in this order
// Var newTotal (Double): (globalMap.get("runTotal") == null ? 0d : (Double)globalMap.get("runTotal")) + (row1.amount == null ? 0d : row1.amount)
// Var store    (Object): globalMap.put("runTotal", Var.newTotal)     // Map.put returns the previous value; ignore it
// output column runningTotal: Var.newTotal
// Cleaner alternatives: tJavaFlex (Start/Main/End), tAggregateRow, tMemorizeRows.

// 10. Previous-row memory / change detection (sorted input)
// Var prevKey (String): (String)globalMap.get("prevKey")
// Var isNew   (boolean): Var.prevKey == null || !Var.prevKey.equals(row1.key)
// Var store   (Object):  globalMap.put("prevKey", row1.key)          // declared after isNew so it runs after
// output filter: Var.isNew

// 11. Dedup flag inside tMap (first occurrence wins, unsorted input)
// Var seen (boolean): globalMap.containsKey("seen_" + row1.key)
// Var mark (Object):  globalMap.put("seen_" + row1.key, Boolean.TRUE)
// output filter: !Var.seen           // memory grows with distinct keys; tUniqRow is the normal tool

// 12. Type guards before parsing
row1.qty != null && row1.qty.trim().matches("-?\\d+") ? Integer.parseInt(row1.qty.trim()) : null
row1.amt != null && row1.amt.trim().matches("-?\\d+(\\.\\d+)?") ? new java.math.BigDecimal(row1.amt.trim()) : null

// 13. Age in years, date-only compare
(int) TalendDate.diffDateFloor(TalendDate.getCurrentDate(), row1.birth, "yyyy")
TalendDate.compareDate(row1.d, context.cutoff, "yyyy-MM-dd") >= 0

// 14. Boolean from Y/N with default false (output column boolean non-nullable)
row1.flag != null && (row1.flag.equalsIgnoreCase("Y") || row1.flag.equals("1"))

// 15. Padding / fixed width
String.format("%-20s", row1.name == null ? "" : row1.name)        // left-justified
String.format("%010d", row1.id)                                      // zero-padded (Integer, non-null)
org.apache.commons.lang3.StringUtils.leftPad(row1.s, 8, '0')          // commons-lang3 is on the classpath of most Jobs (unverified)

// 16. Hash of a row for CDC compare
org.apache.commons.codec.digest.DigestUtils.md5Hex((row1.a == null ? "" : row1.a) + "|" + (row1.b == null ? "" : row1.b))  // needs commons-codec; or tAddCRCRow
```

## Gotchas

| Symptom | Cause | Fix |
|---|---|---|
| Compile error `incomparable types: int and <null>` or `cannot convert from null to int` in tMap | Column type Integer/Long/Double/Boolean with `Nullable` unchecked generates a primitive. | Tick Nullable on the column (input and output as needed) or stop testing it for null. |
| `NullPointerException` at tMap `.intValue()`/`.doubleValue()` line in the generated code | Boxed null (lookup miss, empty source field) unboxed into a primitive output column or arithmetic. | Make the output column Nullable or default it: `row2.x == null ? 0 : row2.x`. |
| Lookup query with `globalMap.get("id")` runs with `null` / returns no rows / SQL syntax error `= null` | Lookup Model left on `Load once`, so the query ran once before any main row set the key. | Set Lookup Model `Reload at each row` (or `(cache)`) on that lookup and fill the `globalMap Key` area. |
| Reload at each row set but values still stale / NPE in query | Key put via a tMap Var instead of the `globalMap Key` area; Vars run after lookups resolve. | Use the `globalMap Key` field or a tJavaRow before tMap. |
| Lookup never matches although values look equal | Type mismatch (`Integer` vs `Long`, `String` "007" vs Integer 7), trailing spaces from CHAR columns, case differences, BigDecimal scale (`1.0` vs `1.00`), Date with time component. | Align types in the schemas; `.trim().toUpperCase()` both sides; enable `Ignore trailing zeros for BigDecimal`; truncate dates. |
| Output row count much larger than input | Lookup `Match Model` = `All matches` with duplicate keys in the lookup, or a lookup with no `Expr. key` (cross join). | Use Unique/First match, dedup the lookup (tUniqRow or `SELECT DISTINCT`), or set the key. |
| Wrong lookup row chosen "randomly" | `Unique match` returns the LAST loaded duplicate; `First match` returns the first; DB load order is unordered. | Dedup the lookup or `ORDER BY` in the lookup query; filter duplicates with the lookup expression filter. |
| `Catch lookup inner join reject` output stays empty | Lookups are all `Left Outer Join`. | Set Join Model `Inner Join` on the lookup that defines the rejection. |
| `Catch output reject` gets nothing while rows disappear | Rows dropped by the MAIN input expression filter, not by output filters; input filter rejects are not catchable. | Move the condition to an output filter and catch rejects there. |
| `Catch lookup inner join reject` cannot tell which lookup failed | One reject output collects rejects from all Inner Join lookups. | Add flag columns `row2.id == null`, `row3.id == null` on the reject output, or chain tMaps one lookup each. |
| Rows that failed an output filter still consumed a `Numeric.sequence` value (gaps in keys) | Var table runs before output filters, for every main row. | Generate the sequence in a downstream tMap/tJavaRow after filtering, or filter upstream (tFilterRow). |
| `Unparseable date` / `java.lang.RuntimeException: ... ParseException` from TalendDate.parseDate | Pattern does not match data (`mm` vs `MM`, `yyyy` vs `yy`, locale month names, `T` not quoted). | Fix the pattern; guard with `TalendDate.isDate(s, pattern)`; use `parseDateLocale` for names. |
| Build/export fails `cannot find symbol: variable MyRoutine` while it runs in Studio | Routine not in the Job's routine dependencies; Studio run uses the whole project classpath. | Right-click Job > `Setup routine dependencies` > add the routine (and its libraries via `Edit Routine Libraries`). |
| `The method X(String) is undefined for the type Y` after a routine edit | Routine signature changed; Jobs still reference the old one; or two routines with the same class name in different folders. | Re-save/regenerate the Job (Code tab) or fix the name clash; routine class names are global in the project. |
| `row1.s == "ABC"` never true | Reference comparison. | `"ABC".equals(row1.s)`. |
| `BigDecimal` equality fails, `1.10 != 1.1`; or DB rejects `1E+3` | `equals` includes scale; `toString` uses scientific notation. | `compareTo(...) == 0`; `toPlainString()`; `setScale(2, RoundingMode.HALF_UP)`; `Ignore trailing zeros for BigDecimal` for keys. |
| Output filter `row1.age > 18` throws NPE instead of rejecting the row | Unboxing null in the filter. | `row1.age != null && row1.age > 18`. Unchecked `Die on error` + ErrorReject link to collect such rows. |
| tXMLMap/tFileInputXML `OutOfMemoryError` on big files | Whole XML held as one Document (DOM). | Loop on the repeating element in tFileInputXML (SAX generation mode) producing many small Documents or flat rows; raise `-Xmx` only as a stopgap. |
| tXMLMap produces one Document with all records instead of one per record (or vice versa) | `All in one` true/false mismatch with expectation; aggregate element present. | Set `All in one` on the output's tMap settings; use group/aggregate elements deliberately. |
| tXMLMap output missing elements whose value is null | `Create empty element` = false. | Set it to true, or supply a fixed value. |
| tELTMap SQL fails with unknown table or `INSERT INTO row2` | Link names must be table names; the output link name is used as the target table. | Rename the links (tELTInput -> tELTMap link = source table; tELTMap -> tELTOutput link = target table) or use `Use different table name`. |
| tELT* LEFT JOIN loses rows | Join clause order = GUI order; a LEFT JOIN before an INNER JOIN is filtered by the inner join. | Reorder input tables so INNER JOINs come first. |
| `Duplicate local variable`/`ambiguous` compile error in tMap | Var or output column named like a Java keyword or an existing local (`row1`, `out`, `class`, `int`, `count`?). | Rename the column/Var to a plain identifier (`rowCount`). |
| Two inputs with identical column names map wrong after `Auto map!` | Auto map is name-based and picks the first matching input. | Map manually or rename columns upstream. |
| Sequence restarts from 1 in a child Job / continues across runs | `Numeric.sequence` state is static per JVM: tRunJob child in the same JVM shares names; embedded runtimes keep state. | Use distinct sequence names per Job; `Numeric.resetSequence` at start; or DB sequences. |
| `ClassCastException: java.lang.Integer cannot be cast to java.lang.String` on `globalMap.get` | Wrong cast; `NB_LINE` is Integer, `CURRENT_FILE` is String, dates are Date. | Check the Outline view type; cast accordingly (`String.valueOf(globalMap.get(...))` when you only need text). |
| Multi thread execution Job: globalMap values overwritten | Subjobs run concurrently and share one `globalMap`. | Namespace keys per subjob/thread; or disable `Multi thread execution`. |
| Timestamp shifts by hours between source and target | JVM default time zone differs from DB session/host; DST. | `-Duser.timezone=UTC` in JVM args on all engines; `formatDateInUTC`/`parseDateInUTC`; store as UTC. |
| `Type mismatch: cannot convert from String to Integer` after changing a source schema | tMap does not convert; expression type must match output type. | Add explicit conversion (`Integer.parseInt`) or change the output type and `Sync columns` downstream. |
| Spark Job: tMap `Reload at each row` / `Store temp data` greyed out, `Numeric.sequence` gives duplicates | Spark tMap has no per-row reload or disk spill; sequence is per-executor. | Redesign as broadcast join; use `monotonically_increasing_id` via tSqlRow or zipWithIndex pattern; see big-data-spark.md. |
| Lookup query runs N times (one per file) and the run is slow | The tMap and its `Load once` lookup sit inside a subjob driven by an `Iterate` link (e.g. tFileList); `Load once` means once per subjob execution, so the lookup reloads on every iteration | Move the lookup data into tHashOutput in an earlier subjob and read it with tHashInput as the lookup, or restructure so the iterated subjob only reads the file and a later subjob does the join |

## Sources

https://help.qlik.com/talend/en-US/components/8.0/tmap/tmap-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/tmap/tmap-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/tmap/tmap-lookup-models
https://help.qlik.com/talend/en-US/components/8.0/tmap/differences-between-unique-match-first-match-and-all-matches
https://help.qlik.com/talend/en-US/components/8.0/tmap/example-job-implementing-different-match-models
https://help.qlik.com/talend/en-US/components/8.0/tmap/tmap-tfileinputdelimited-tfileoutputdelimited-tfileoutputdelimited-advanced-mapping-using-filters-explicit-joins-and-rejections-standard-component-this
https://help.qlik.com/talend/en-US/components/8.0/tmap/tmap-tfileinputdelimited-tfileoutputdelimited-tfileoutputdelimited-configuring-how-to-map-data-standard-component
https://help.qlik.com/talend/en-US/components/8.0/tmap/tmap-tmysqlinput-tmysqloutput-tmysqlcommit-advanced-mapping-with-lookup-reload-at-each-row-standard-component-the
https://help.qlik.com/talend/en-US/components/7.3/tmap/tmap-tmysqlinput-tmysqloutput-tmysqlcommit-configuring-components-standard-component
https://help.qlik.com/talend/en-US/studio-user-guide/8.0/reloading-data-at-each-row
https://help.qlik.com/talend/en-US/studio-user-guide/8.0/handling-lookups
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-09/using-explicit-join
https://help.qlik.com/talend/en-US/components/8.0/tmap/tmap-properties-for-apache-spark-batch
https://help.qlik.com/talend/en-US/components/8.0/tmap/tmap-properties-for-apache-spark-structured-streaming
https://help.qlik.com/talend/en-US/components/8.0/txmlmap/txmlmap
https://help.qlik.com/talend/en-US/components/8.0/txmlmap/txmlmap-tfileinputxml-tlogrow-tlogrow-catching-data-rejected-by-lookup-and-filter-standard-component-the-data
https://help.qlik.com/talend/en-US/components/8.0/txmlmap/txmlmap-tfileinputxml-tlogrow-tlogrow-collecting-rejected-data-standard-component
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-09/defining-output-mode
https://help.qlik.com/talend/en-US/studio-user-guide/8.0/grouping-output-data
https://help.qlik.com/talend/en-US/studio-user-guide/7.3/aggregating-output-data
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-04/setting-up-document-type
https://help.qlik.com/talend/en-US/components/8.0/elt-jdbc/teltmap
https://help.qlik.com/talend/en-US/components/8.0/elt-jdbc/teltoutput
https://help.qlik.com/talend/en-US/components/8.0/elt-jdbc/teltmysqlinput
https://help.qlik.com/talend/en-US/components/7.3/elt-jdbc/teltoutput-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/elt-jdbc/teltmysqlinput-teltmysqlmap-teltmysqloutput-building-job-add?id=1790
https://help.qlik.com/talend/en-US/components/8.0/elt-oracle/teltoracleoutput
https://help.qlik.com/talend/en-US/components/8.0/elt-oracle/teltoraclemap-teltoracleinput-teltoracleoutput-configuring-components-standard-component
https://help.qlik.com/talend/en-US/components/8.0/elt-teradata/teltteradatamap
https://help.qlik.com/talend/en-US/components/8.0/elt-teradata/teltteradataoutput
https://help.qlik.com/talend/en-US/components/8.0/elt-vertica/teltverticaoutput
https://help.qlik.com/talend/en-US/components/8.0/elt-netezza/teltnetezzaoutput
https://help.qlik.com/talend/en-US/components/8.0/elt-sybase/teltsybaseoutput
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-06/talenddate-routines
https://help.qlik.com/talend/en-US/studio-user-guide/7.2/talenddate-routines
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-06/stringhandling-routines
https://help.qlik.com/talend/en-US/studio-user-guide/7.3/stringhandling-routines
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-05/talendstring-routines
https://help.qlik.com/talend/en-US/studio-user-guide/7.3/numeric-routines
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2025-09/numeric-routines
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-06/mathematical-routines
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-07/talenddatagenerator-routines
https://community.qlik.com/t5/Design-and-Development/tMap-Match-Model-Problem-with-design-of-this-option/m-p/2464795
https://community.qlik.com/t5/Talend-Studio/Tmap-how-to-output-rejections/m-p/2235858
https://community.qlik.com/t5/Talend-Studio/globalmap-cannot-be-resolved/td-p/2276658
