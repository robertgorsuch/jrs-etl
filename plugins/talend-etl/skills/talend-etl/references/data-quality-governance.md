# Data Quality, Stewardship, Preparation, Catalog/Inventory and MDM

> Verification: doc-derived (help.qlik.com / help.talend.com search snippets, Talend GitHub, Maven Central) plus model knowledge. Not exercised against a live Studio/TAC/TMC in this build. Items marked (unverified) are from memory only and should be checked in Studio before relying on exact labels.

Scope: everything "governance" that touches Studio jobs or the Talend platform:
the Profiling perspective, the Data Quality component families (Standardization,
Matching, Survivorship, Validation, Privacy, Stewardship, Preparation), Talend
Data Stewardship (TDS), Talend Data Preparation, Talend Data Catalog (TDC) /
Data Inventory / Trust Score, Talend MDM, and the Qlik Talend Cloud quality
features. Component families owned elsewhere are only pointed to:
components-core.md (tUniqRow, tFilterRow, tReplace), tmap-expressions.md,
big-data-spark.md (Spark job frame these DQ components run in),
deployment-runtime.md (TMC engines), apis-sdks.md (REST details beyond pointers),
versions-licensing.md (edition/EOL matrix).

## Contents

- [Product map and licensing](#product-map-and-licensing)
- [Profiling perspective (Talend Data Quality in Studio)](#profiling-perspective-talend-data-quality-in-studio)
  - [DQ Repository tree](#dq-repository-tree)
  - [Analysis types](#analysis-types)
  - [Column analysis indicators](#column-analysis-indicators)
  - [Patterns, indicators and rules libraries](#patterns-indicators-and-rules-libraries)
  - [Match rules (VSR / T-Swoosh) in the repository](#match-rules-vsr--t-swoosh-in-the-repository)
  - [Execution engine, drill-down, export](#execution-engine-drill-down-export)
  - [Reports and the DQ datamart](#reports-and-the-dq-datamart)
  - [Semantic types and Talend Dictionary Service](#semantic-types-and-talend-dictionary-service)
- [Data Quality components](#data-quality-components)
  - [Standardization](#standardization)
  - [Address verification](#address-verification)
  - [Blocking and matching](#blocking-and-matching)
  - [tMatchGroup in depth](#tmatchgroup-in-depth)
  - [Machine-learning matching on Spark](#machine-learning-matching-on-spark)
  - [Survivorship](#survivorship)
  - [Validation and compliance](#validation-and-compliance)
  - [Synonyms, sampling, test data](#synonyms-sampling-test-data)
  - [Data privacy (masking, shuffling, encryption)](#data-privacy-masking-shuffling-encryption)
  - [Stewardship and Preparation components](#stewardship-and-preparation-components)
  - [Deduplication pipeline (ASCII)](#deduplication-pipeline-ascii)
- [Talend Data Stewardship](#talend-data-stewardship)
- [Talend Data Preparation](#talend-data-preparation)
- [Talend Data Catalog, Data Inventory, Trust Score](#talend-data-catalog-data-inventory-trust-score)
- [Talend MDM](#talend-mdm)
  - [Server and storage](#server-and-storage)
  - [Data model (XSD) and annotations](#data-model-xsd-and-annotations)
  - [Containers, views, roles, menus](#containers-views-roles-menus)
  - [Processes, triggers, event management](#processes-triggers-event-management)
  - [MDM components in jobs](#mdm-components-in-jobs)
  - [MDM APIs](#mdm-apis)
  - [Golden record pipeline (ASCII)](#golden-record-pipeline-ascii)
  - [MDM performance and operations](#mdm-performance-and-operations)
- [Governance on Qlik Talend Cloud](#governance-on-qlik-talend-cloud)
- [Gotchas](#gotchas)
- [Sources](#sources)

## Product map and licensing

| Product / feature | Where it lives | Edition / status (8.0, Qlik era) |
|---|---|---|
| Profiling perspective (analyses, reports, patterns, indicators, rules) | Studio, `Window > Perspective > Profiling` | Data Management Platform, Data Fabric, Big Data Platform, Real-Time Big Data Platform. Open Studio for Data Quality (free) discontinued with the 2022-2023 end of the Open Studio line (last 8.0.1 GA); no further downloads |
| DQ components (tMatchGroup, tDataMasking, tStandardizeRow, ...) | Palette: Data Quality family; many are Feature Manager installs in 8.0 ("not shipped with your Talend Studio by default") | Same platform editions. Standard + Spark Batch + Spark Streaming variants per component; MapReduce variants deprecated in 7.3, removed in 8.0 |
| Talend Dictionary Service (TDS, semantic types) | On-prem Docker/Kafka/MongoDB service in 7.x; built into Talend Cloud | Required for semantic-aware analysis and Data Preparation/Data Inventory semantic discovery |
| Talend Data Stewardship | Talend Cloud app ("Data Stewardship" in TMC launcher) or on-prem server (7.x, 8.0 on-prem) | Data Fabric / DMP; components tDataStewardship* (renamed tDS* in Studio 8.0 R2025-12) |
| Talend Data Preparation | Talend Cloud app or on-prem server; Free Desktop edition discontinued | tDataprepRun bridges to jobs |
| Talend Data Inventory / Trust Score | Talend Cloud only | Qlik Talend Cloud "Data Inventory", datasets with quality bar and Trust Score |
| Talend Data Catalog (TDC) | On-prem server (Tomcat, formerly Talend Metadata Manager / MIMM by Meta Integration) | Data Fabric add-on; Qlik continues it alongside Qlik Catalog (separate lineage, Podium Data origin) |
| Talend MDM | On-prem MDM server (Tomcat) + Studio MDM perspective | Talend MDM Platform / Data Fabric. Still shipped in 8.0 but no functional investment; Qlik positions it as legacy - verify current EOL notice in versions-licensing.md |
| Talend Trust Assessor | Free web tool (upload file, get Trust Score) | Marketing-grade; discontinued under Qlik (unverified) |
| Stitch | Qlik-owned ELT SaaS | Not governance; no DQ features |

## Profiling perspective (Talend Data Quality in Studio)

Open with `Window > Perspective > Profiling` (or the perspective toolbar). The
perspective adds two views: **DQ Repository** (tree) and **Detail View**, plus
the analysis editor and a **Pattern Test View** for regex testing. Analyses are
stored as items in the project (`.ana` XML under `TDQ_Data Profiling/Analyses`)
and versioned with the rest of the project when connected to TAC/Git.

### DQ Repository tree

```
DQ Repository
+-- Data Profiling
|   +-- Analyses              (.ana items; folders allowed)
|   +-- Reports               (.rep items; reports group analyses)
+-- Libraries
|   +-- Exchange              (download/upload patterns/indicators from Talend Exchange - mostly dead in 8.0)
|   +-- Indicators
|   |   +-- System Indicators  (read-only: Simple/Text/Summary/Advanced statistics, pattern/fraud/phone)
|   |   +-- User Defined Indicators (.definition items; SQL template per DB type and/or Java class jar)
|   +-- Patterns
|   |   +-- Regex             (Email Address, US Phone Number, Date patterns, Zip code, Credit card, ...)
|   |   +-- SQL               (LIKE patterns, e.g. for Teradata/engines without regex)
|   +-- Rules
|   |   +-- SQL               (business rules: WHERE clause + criticality level)
|   |   +-- Parser            (tStandardizeRow rule sets saved to repository)
|   |   +-- Match             (match rules: VSR or T-Swoosh; blocking + matching keys; survivorship)
|   +-- Source Files          (SQL/txt helper files)
+-- Metadata
    +-- DB connections        (shared with Integration perspective repository Metadata > Db Connections)
    +-- FileDelimited connections
    +-- Hadoop cluster / Hive / HDFS (platform editions)
    +-- MDM connections       (MDM editions)
```

Items are the same `.item/.properties` pairs as elsewhere (artifact-formats.md);
the DQ-specific folders are `TDQ_Data Profiling`, `TDQ_Libraries`, `TDQ_Reporting_db`.

### Analysis types

Create via right-click `Analyses > New Analysis`. Wizard offers the categories
below. Each analysis has `Analysis Metadata` (name, purpose, description),
`Analysis Settings` (engine, data filter / WHERE, row limit / sampling) and an
`Analysis Results` section after `Run` (F6).

| Category | Analysis | What it computes | Notes |
|---|---|---|---|
| Connection | Connection Overview (Connection analysis) | Per catalog/schema: table count, view count, row counts | Fast inventory; uses JDBC metadata + COUNT(*) |
| Catalog/Schema | Catalog Analysis / Schema Analysis | Same as above scoped to one catalog or schema; table/view/row counts and key counts | Reuses connection metadata |
| Table | Table Analysis (Business Rule Analysis) | Applies one or more SQL business rules (`Rules > SQL`) to a table; counts rows matching / not matching; optional JOIN condition between tables | Rule = WHERE clause fragment + criticality (`Low/Medium/High`); drill down to invalid rows |
| Table | Functional Dependency Analysis | For column pairs A -> B, % of A values that determine exactly one B | Finds candidate keys / denormalization errors |
| Table | Column Set Analysis (Simple statistics on column set) | Row count, distinct, unique, duplicate counts over the combination of selected columns; pattern frequency per column; "Store data" to allow drill-down | Java engine only when files or "Store data" selected |
| Table | Match Analysis | Runs a match rule (VSR or T-Swoosh) against a table/file sample: blocking key selection, matching key definition, thresholds; shows group size distribution and sample groups | Rule can be saved to `Rules > Match` and imported into tMatchGroup via `Import match rule from repository` |
| Table | Redundancy Analysis | Compares two sets of columns (two tables) for value overlap: rows in A not in B and vice versa (left/right redundancy) | Good for FK orphan detection |
| Column | Column Analysis (basic) | Indicators per column (see table below) | Default; most used |
| Column | Semantic-aware Analysis (semantic discovery) | Runs semantic discovery on a column set: proposes a semantic type per column from TDS, then validity % against that type | Requires TDS reachable (`Window > Preferences > Talend > Profiling > Semantic`) |
| Correlation | Numerical Correlation Analysis | Nominal column vs numeric column: avg/min/max per nominal value, bubble chart | |
| Correlation | Time Correlation Analysis | Nominal column vs date column: min/max dates per value, gantt chart | |
| Correlation | Nominal Correlation Analysis | Two nominal columns: co-occurrence counts | |
| File | Delimited file analyses | Column analysis / column set analysis on a `FileDelimited` metadata connection | Java engine only; no SQL |
| MDM | MDM entity analyses | Column analysis on an MDM data container entity (XPath columns) | MDM editions only; removed in later 8.0 R-releases (unverified) |

### Column analysis indicators

Attach indicators per column with the `Select indicators` dialog. Each indicator
has `Indicator Settings` (thresholds: expected range or % range, which colors
results red/green and feeds report evolution charts).

| Group | Indicators | Notes |
|---|---|---|
| Simple Statistics | Row Count, Null Count, Blank Count, Distinct Count, Unique Count, Duplicate Count, Default Value Count | Blank = empty or whitespace-only string; Default Value Count uses the column default |
| Text Statistics | Minimal Length, Maximal Length, Average Length (each with "with blank/null" variants: `Minimal Length With Blank`, `... With Null`, `... With Blank And Null`) | Length indicators on string columns only |
| Summary Statistics | Mean, Median, Lower Quartile, Upper Quartile, Inter Quartile Range, Range (min/max) | Numeric/date columns; Median/IQR need Java engine on some DBs (no percentile SQL) |
| Advanced Statistics | Mode, Value Frequency, Value Low Frequency, Pattern Frequency, Pattern Low Frequency, Date Pattern Frequency, Soundex Frequency, Soundex Low Frequency, Benford Law Frequency | Pattern frequency replaces letters with `A`/`a`, digits with `9`, keeps punctuation; Benford compares first-digit distribution to Benford's law (fraud/outlier detection) |
| Pattern Matching | one indicator per attached regex or SQL pattern: matching count / not matching count; plus `Regular Expression Matching` ad hoc | Patterns come from `Libraries > Patterns`; the SQL engine needs the DB to support regex (MySQL `REGEXP`, Oracle `REGEXP_LIKE`, Postgres `~`); otherwise Java engine or SQL LIKE pattern |
| Phone Number Statistics | Valid Phone Number Count, Possible Phone Number Count, Valid Region Code Count, Invalid Region Code Count, Well Formed E164 Phone Number Count, Well Formed International Phone Number Count, Well Formed National Phone Number Count, Format Frequency Pie | libphonenumber; default region taken from the indicator parameter (country code) |
| Fraud Detection | Benford Law Frequency (also listed under Advanced) | Shows expected vs actual first-digit distribution |
| User Defined | your UDIs (Count, Real value, Frequency, Match, Correlation categories) | SQL template per DB vendor plus optional Java class |
| Semantic | Semantic type validity indicators from semantic-aware analysis | Needs TDS |

### Patterns, indicators and rules libraries

- **Regex pattern** item: name, purpose, description, author, and one regex
  expression per DB type (`Default`, `MySQL`, `Oracle`, `PostgreSQL`, `Java`,
  ...). The `Default` expression is used when no vendor-specific one exists;
  the `Java` entry is used by the Java engine and by `tPatternCheck` when
  `Use pattern from repository` is selected. Test in `Pattern Test View`.
- **SQL pattern**: `LIKE` expression per vendor, used by the SQL engine on DBs
  lacking regex. Not usable by tPatternCheck.
- **System indicators** cannot be edited; **User Defined Indicators** are
  created via `New Indicator`: category (`Count`, `Real Value`, `Frequency
  Table`, `Match`, `Correlation`), one SQL template per vendor using
  placeholders `<%=__COLUMN_NAMES__%>`, `<%=__TABLE_NAME__%>`,
  `<%=__WHERE_CLAUSE__%>`, or a Java implementation (jar with a class
  extending `org.talend.dataquality.indicators.sql.impl.UserDefIndicatorImpl`)
  for the Java engine.
- **SQL business rule**: `WHERE` clause fragment (e.g. `age > 0 AND age < 120`),
  criticality level, optional `Join Condition` table; used by Business Rule
  Analysis and nowhere else (not a job component).
- **Parser rules**: tStandardizeRow rule sets saved via the component's
  `Save to repository` icon; reusable across jobs.
- **Exchange**: the Talend Exchange upload/download integration is effectively
  defunct since 7.x; keep patterns in the project and share through Git/TAC.

### Match rules (VSR / T-Swoosh) in the repository

A match rule item (`Rules > Match`) stores:

| Section | Content |
|---|---|
| Record linkage algorithm | `Simple VSR Matcher` or `T-Swoosh` |
| Generation of blocking key | table: `Input column`, `Pre-algorithm` (Remove diacritical marks, Lower case, Upper case, Remove diacritical marks and lower case, ...), `Algorithm` (First character of each word, First N characters, Last N characters, First N consonants, First N vowels, Pick characters, Exact, Soundex, Metaphone, Double Metaphone, Fingerprint key, Cologne phonetic), `Value`, `Post-algorithm` (Use default, Remove diacritical marks, Lower/Upper case, Add left/right character), `Value` |
| Matching key | table: `Match key name`, `Input column`, `Matching function` (Exact, Exact - ignore case, Soundex, Soundex FR, Levenshtein, Metaphone, Double Metaphone, Jaro, Jaro-Winkler, q-grams, Hamming, custom...), `Custom matcher` (class name), `Tokenized measure` (No, Any order, Same order, Same place), `Threshold` (T-Swoosh only, default 1.0), `Confidence weight`, `Handle null` (Null match null, Null match none, Null match all) |
| Survivorship rules (T-Swoosh only) | `Default survivorship rules` per data type (String/Number/Date: e.g. Longest, Largest, Most recent) and `Survivorship rules for columns` with `Survivorship function` (Most common (unverified for this editor), Longest, Shortest, Largest, Smallest, Most recent, Most ancient, Most trusted source, Concatenate), `Parameter` (source name for Most trusted source, separator for Concatenate), `Reference column` for Most recent/ancient |
| Match threshold / Confident match threshold | group-level cutoffs used by tMatchGroup when the rule is imported |

Only rules whose algorithm matches the component's selected `Matching
Algorithm` import cleanly; mismatched parameters fall back to defaults.
tGenKey can import blocking keys only from VSR rules.

### Execution engine, drill-down, export

| Setting | Values | Behaviour |
|---|---|---|
| `Analysis Settings > Execution engine` | `SQL` (default for DB connections) or `Java` | SQL pushes one query per indicator group to the DB (fast, exact, uses DB collation and regex dialect). Java pulls rows to Studio (needs memory; respects `Number of connections per analysis`; required for files, "Store data", Median/IQR on DBs without percentile functions, Java UDIs, Soundex on most DBs) |
| `Data filter` | SQL WHERE fragment | Appended to every indicator query |
| `Store data` (Java engine, column set) | checkbox | Keeps analyzed rows in the Studio-side DB so drill-down works without re-querying |
| `Number of connections per analysis` | int | Parallelism of SQL engine |
| Drill-down | right-click a result row: `View rows`, `View valid rows`, `View invalid rows`, `View valid values`, `View invalid values`, `View match rows`, `View duplicate rows` | SQL engine issues a `SELECT ... WHERE` using the indicator's expression; Java engine replays from stored data. Shows in the `Data Explorer` (SQL Explorer) perspective |
| Export | analysis editor toolbar `Export results` (CSV/XLS of indicator values); right-click analysis `Export item` to share .ana | Charts can be saved as PNG from the chart context menu |
| Context | analyses can use project context variables for connection params (7.1+) | Select context in `Analysis Settings` |

Result differences SQL vs Java: trailing-space handling, case sensitivity
(DB collation vs Java `equals`), regex dialect, NULL vs blank semantics on
`CHAR` columns. Pick one engine per analysis and keep it fixed when comparing
runs in evolution reports.

### Reports and the DQ datamart

- Report item (`Data Profiling > Reports > New Report`): add analyses, choose
  per analysis the template `Basic` (snapshot), `Evolution` (trend of each
  indicator across executions), or `User defined` (a JasperReports `.jrxml`
  template you supply; sample templates ship under
  `<Studio>/plugins/org.talend.dataquality.reporting_*/reports/...`).
- Output formats: PDF (default), HTML, XLS, XLSX, CSV (unverified list beyond
  PDF/HTML/XLS). Output folder set in report settings; `Generate report`
  toolbar button or F6.
- The report runs the analyses first (unless `Refresh` disabled), then writes
  indicator values to the **data mart** ("report database"): default is an
  embedded HSQLDB under the workspace; production setups point
  `Window > Preferences > Talend > Profiling > Reporting` (or the report's
  `Database settings`) to MySQL, Oracle, PostgreSQL or SQL Server. Studio creates
  the tables on first use; table names are prefixed `TDQ_` (e.g. `TDQ_ANALYSIS`,
  `TDQ_INDICATOR_VALUE`, `TDQ_INDIC_DEFINITION`, `TDQ_INDICATOR_THRESHOLD`
  (unverified exact names)). Report results are also logged per run under
  `TDQ_Reporting_db` in the project.
- Datamart schema changes between major Studio versions (6.x -> 7.x -> 8.0);
  migrate by letting the new Studio recreate tables in a fresh schema or run
  the provided migration scripts, not by pointing 8.0 at a 6.x datamart.
- `tDqReportRun` runs a repository report from a job (schedule reports via
  TAC/TMC): `Report` (repository selector), `Output folder`, `Generate report`
  (unverified property list). The job must be built with the Profiling items
  included (`Include Profiling items` is implicit when the report is referenced).
- The on-prem **Talend Data Quality Portal** (SpagoBI-based web portal that
  browsed the datamart) was discontinued in 7.0; use the datamart tables
  directly with any BI tool, or Jasper reports.

### Semantic types and Talend Dictionary Service

- Semantic types = named categories (e.g. `EMAIL`, `FR_PHONE`, `US_STATE_CODE`,
  `COUNTRY`, `IBAN`, `URL`, `FIRST_NAME`) defined as **dictionary** (value list,
  optionally with synonyms), **regex**, or **compound** types, plus a
  `Validation mode` (Exact / Exact ignore case / Simplified) and a flag whether
  the type can be used for discovery.
- Shipped as a Lucene index in the Studio (`org.talend.dataquality.semantic`)
  and served centrally by **Talend Dictionary Service** (TDS, Docker image
  `talend/dictionary-service`, needs MongoDB + Kafka in 7.x) so that Studio
  Profiling, Data Preparation, Data Stewardship data models, Pipeline Designer
  and Data Inventory share one list. In Talend Cloud the service is managed;
  semantic types are edited in the **Talend Cloud Management Console >
  Semantic types** (later moved under Data Inventory).
- Studio preference: `Window > Preferences > Talend > Data Quality > Semantic
  types` (or `Profiling > Semantic`) holds the TDS URL and Talend Cloud
  credentials; "Update semantic types" syncs the local index. Without TDS the
  semantic-aware analysis uses the frozen built-in index only (no custom types).
- Components that consume semantic types: tDataMasking (functions `Mask by
  semantic type` in 7.3+), tPatternMasking, Data Preparation functions,
  tDataStewardshipTaskOutput data models (type validation), Pipeline Designer
  (quality bar per column), Data Inventory (quality bar and Trust Score).

## Data Quality components

Palette family `Data Quality` (sub-families in docs: Address standardization,
Continuous matching, Data matching, Data privacy, Data stewardship, Data
preparation, Deduplication, Email validation, Fuzzy matching, Identification,
Matching with machine learning, Phone number standardization, Standardization,
Survivorship, Validation, Synonyms). In 8.0 most DQ components must be enabled
via `Feature Manager` (studio.md). Each table below lists the Standard variant;
`Spark` column = also available for Spark Batch (B) / Spark Streaming (S).

### Standardization

| Component | Purpose | Key settings | Notes / Spark |
|---|---|---|---|
| tStandardizeRow | Tokenize and normalize free text (addresses, product descriptions) with ANTLR grammar rules; outputs the parsed structure as XML or JSON in `STANDARDIZED_FIELD` | `Column to parse`; `Standardize this field` (lookup/normalize values via Index rules); `Conversion rules` table: `Name`, `Type`, `Value` (+ `Search mode` for Index: `Match exact`, `Match any`, `Match all`, `Match partial`, `Match any fuzzy`, `Match all fuzzy`; `Word distance` default 1); `Generate parser code in Routines` button (Spark: `Generate analyzer code as routine`); `Advanced settings > Output format` XML/JSON, `Max edits for fuzzy match`, `Advanced options for INDEX rules` | Rule types: basic = `Enumeration` (`'kg' | 'g' | 'lb'`), `Format` (sequence of tokens/rule names, e.g. `INT UNIT`), `Combination`; advanced (applied after basic, in order independent) = `RegExp`, `Index` (Lucene synonym index path, from tSynonymOutput), `Shape`. Predefined case-sensitive tokens: `INT`, `DECIMAL`, `CURRENCY`, `ALPHANUM`, `WORD`, `CAPWORD`, `UNDEFINED`, `WHITESPACE` (verify in rule-types doc). Regenerate parser code after adding a rule or editing Enumeration/Format/Combination rules; code lands in `Code > Routines` of the project. Spark B/S |
| tStandardizePhoneNumber | Parse and reformat phone numbers with Google libphonenumber | `Phone number` column; `Country code`: `Customize` (fixed ISO code string, e.g. `"US"`) or `Column` (per-row country column); `Phone number format`: `E164`, `International`, `National`, `RFC3966`; `Advanced settings > Phone number type` options (unverified) | Output columns auto-added: `StandardizedPhoneNumber`, `IsValidPhoneNumber`, `IsValidPhoneNumberForRegion` (7.3+), `IsPossiblePhoneNumber`, `IsAlreadyStandard`, `PhoneNumberType` (FIXED_LINE, MOBILE, FIXED_LINE_OR_MOBILE, TOLL_FREE, PREMIUM_RATE, VOIP, UNKNOWN...). A number can be valid globally yet false for the given region. Spark B/S |
| tReplaceList | Replace values from a lookup list (synonym style) | lookup flow with `Search`/`Replace` columns; `Case sensitive`, `Whole word` | Generic; often used after tStandardizeRow |
| tChangeFileEncoding | Convert a file's charset | `Input/Output file name`, `Input/Output encoding` | Technical helper (orchestration-logging.md may also list it) |

### Address verification

| Component | Purpose | Key settings | Notes |
|---|---|---|---|
| tAddressRowCloud | Verify/correct/geocode addresses through a cloud provider, one HTTP call per row (or batched internally) | `Address provider`: `Loqate`, `MelissaData`, `QAS` (Experian QAS Pro On Demand), `Google` (Google Places API; limited to search/geocode, deprecated in later 8.0 R-releases (unverified)); provider `License key` / `API key` / credentials; `Address` mapping table (`Address line`, `City`, `State`, `Postal code`, `Country`, ...); `Advanced settings > Output options` (geocode, formatted address, verification status), `Timeout`, `Number of rows per request` | Adds output columns such as `AVC` (Loqate Address Verification Code), `FormattedAddress`, `Latitude`, `Longitude`, `VerificationStatus`, `Results` (per provider; names differ). Provider accounts are metered: every row costs a transaction; test with `Limit` on input |
| tBatchAddressRowCloud | Same, but uploads a batch file to the provider and polls | `Address provider`: `Loqate` or `MelissaData` only; `Advanced settings > Use mockup mode` (replays previously created batch files; requires one real run first) | Better for millions of rows; results arrive asynchronously |
| tLoqateAddressRow | Local Loqate engine (on-prem data files) | `Loqate data path` (country reference data), `Process type` (Verify/Geocode), field mapping | Needs licensed Loqate data packs installed on the job server |
| tQASBatchAddressRow | Experian QAS Batch (on-prem QAS Pro/Batch API) | QAS server host/port, layout name | Legacy; Windows QAS install required |
| tMelissaDataAddress | Melissa Data on-prem Address Object | Melissa data path, license | Deprecated in 7.x, removed 8.0 (unverified) |
| tGoogleAddressRow / tGoogleGeocoder | Google Geocoding API (legacy) | API key | Deprecated; use tAddressRowCloud with Google or a REST call |

### Blocking and matching

| Component | Purpose | Key settings | Notes / Spark |
|---|---|---|---|
| tGenKey | Build a blocking key per row from one or more columns | `Algorithm` table: `Column`, `Pre-algorithm` (none, Remove diacritical marks, Lower case, Upper case, Remove diacritical marks and lower case, Remove diacritical marks and upper case, Add left character, Add right character), `Value`, `Algorithm` (First character of each word, First N characters of each word, First N characters of the string, Last N characters of the string, First N consonants, First N vowels, Pick characters (positions like `1;3-5`), Exact, Soundex, Metaphone, Double Metaphone, Fingerprint key, Cologne phonetic, Exact ignore case (unverified)), `Value`, `Post-algorithm` (same list as pre), `Value`; `Import blocking key from repository` (VSR rules only); `Advanced settings > Show help` | Output column `T_GEN_KEY` (String) appended (name from memory, unverified). Dates converted with schema pattern first, so `Pick characters 1-4` on `yyyy-MM-dd` gives the year. Spark B/S |
| tMatchGroup | Group duplicate records (see next section) | see below | Spark B (Simple VSR only in older Spark variants; T-Swoosh Standard only) |
| tRecordMatching | Match a main flow against a lookup (reference) flow using the same matching functions, outputs matched/unmatched with `SCORE` | `Key definition` table (Input key attribute, Lookup key attribute, Matching type, Confidence weight, Handle null), `Blocking selection` (lookup columns to block on), `Match threshold` | Lookup-based (dedup against a master), not intra-set grouping. Deprecated in favour of tMatchGroup + tMap or tMatchIndexPredict; still shipped |
| tFuzzyMatch | Compare one main column against one lookup column with a distance metric, output distance/matches | `Matching type`: `Levenshtein`, `Metaphone`, `Double Metaphone`; `Min distance` / `Max distance` (Levenshtein only; 0 = include exact); `Matching column` / `Lookup column`; `Case sensitive`; `Unique matching` (keep best only); `Matching item separator` (several lookup matches concatenated) | Adds `VALUE` (distance or phonetic code) and `MATCHING` (matched reference values) output columns (names unverified). Lookup is fully loaded in memory |
| tFuzzyJoin | Join on fuzzy key | Levenshtein/Metaphone, min/max distance, `Inner join` | Deprecated (7.x); use tMatchGroup/tRecordMatching |
| tFuzzyUniqRow | Fuzzy deduplicate a single flow (keeps first, routes near-duplicates to `Duplicates` output) | `Key attribute` table with `Matching type`, `Min/Max distance`; outputs `Uniques` and `Duplicates` | O(n^2) in memory; small files only |
| tBlockedFuzzyJoin | Fuzzy join with blocking | blocking + fuzzy key | Deprecated; removed in 8.0 (unverified) |
| tIntervalMatch | Lookup a value in `[min,max]` interval ranges (e.g. IP ranges, salary bands) | `Lookup column`, `Interval min/max columns`, `Output column`; `Include boundaries` | Listed under Data Quality (Deduplication/Matching family) in docs |
| tMatchIndex | Index a clean, deduplicated reference dataset into Elasticsearch for continuous matching | `Elasticsearch` host/port/index; `Pairing model folder`; columns to index | Spark Batch only; requires the pairing model from tMatchPairing. ES 5.x-6.4.2 supported in 7.3 (8.0 adds 7.x, verify); no ES authentication; not supported on Databricks |
| tMatchIndexPredict | Match new records against the ES index without re-running the full pairing: outputs `Uniques` and `Suspect duplicates` | `Elasticsearch` host/index, `Pairing model folder`, `Matching model folder`, `Max suspects per record` | Spark Batch; the usual "continuous matching" deployment: nightly tMatchIndex refresh + streaming/batch tMatchIndexPredict |

### tMatchGroup in depth

Standard component, `Data Quality > Data matching`. Also Spark Batch variant
(VSR; T-Swoosh added to Spark Batch in 7.x for single-pass, verify). Opens a
dedicated **Configuration wizard** (`...` button on `Key definition` or
double-click) with a preview on sample rows.

| Property | Values | Semantics |
|---|---|---|
| `Schema` | Built-in/Repository | Output = input + the generated columns below. Wizard offers `Edit schema` to add them |
| `Matching Algorithm` | `Simple VSR Matcher`, `T-Swoosh` | VSR: swoosh-like pass that compares each record to the master of each existing group; master = first record seen; groups never merge after formation; output rows are the input rows plus group metadata. T-Swoosh: compares records to merged (survivor) masters, so groups can merge and a new master record is *created* (not one of the inputs) using survivorship rules; MERGED_RECORD column marks the created record. T-Swoosh = Standard only |
| `Import match rule from repository` | repository selector | Fills key definitions and survivorship from `Rules > Match`; algorithm must match or incompatible parameters fall back to defaults |
| `Key definition` table | per key: `Input Key Attribute`, `Matching Function` (Exact, Exact - ignore case, Soundex, Soundex FR, Levenshtein, Metaphone, Double Metaphone, Jaro, Jaro-Winkler, q-grams, Hamming, custom), `Custom Matcher` (class in a user jar implementing `org.talend.dataquality.record.linkage.attribute.IAttributeMatcher` (unverified)), `Tokenized measure` (`No`, `Any order`, `Same order`, `Same place`), `Threshold` (T-Swoosh only, 0..1, default 1), `Confidence Weight` (integer weight in the weighted average), `Handle Null` (`nullMatchNull`, `nullMatchNone`, `nullMatchAll`) | Global score = weighted average of per-key similarity scores (0..1). With T-Swoosh each key score must also exceed its own threshold |
| `Blocking Selection > Input Column` | one column (typically `T_GEN_KEY`) | Only rows with equal blocking value are compared; mandatory for anything beyond tens of thousands of rows. Input must be sorted by the blocking key when `Sort the input data by GID / blocking key` is unchecked (the Standard component buffers one block at a time, verify) |
| `Match threshold` | 0..1 (default 0.85) | Minimum global score for a record to join a group |
| `Confident match threshold` | 0..1 (>= match threshold, default 0.95) | Above it the pair is a confident match (MATCHES output); between the two = SUSPECT when `Separate output` is on |
| `Survivorship Rules For Columns` / `Default Survivorship Rules` (T-Swoosh) | per data type and per column: `Most common` (verify availability), `Longest`, `Shortest`, `Largest`, `Smallest`, `Most recent`, `Most ancient`, `Most trusted source`, `Concatenate`, `Reference column`, `Parameter` | Default rule per type applies unless a column rule overrides; `Most trusted source` needs a source-name column and the trusted value in Parameter; `Concatenate` separator in Parameter |
| `Advanced settings > Separate output` | checkbox | Creates three output links: `Uniques` (GRP_SIZE = 1), `Matches` (score >= confident threshold), `Suspects` (between thresholds). Without it one output contains all rows |
| `Advanced settings > Sort the output data by GID` | checkbox | Groups rows together on output (needed before tRuleSurvivorship) |
| `Advanced settings > Output distance details` | checkbox | Adds `MATCHING_DISTANCES` (per-key scores string) |
| `Advanced settings > Display detailed labels` | checkbox | Adds attribute names into distance details |
| `Advanced settings > Multi-pass` / `Use a previous match result` (unverified labels) | checkbox | Chain several tMatchGroup components with different blocking keys; the second component reads GID/GRP_SIZE/MASTER from the first and only re-matches masters, merging groups across passes (T-Swoosh keeps MERGED_RECORD) |
| `Deactivate matching computation when opening the wizard` | checkbox | Speeds up the wizard on big samples |

Generated output columns:

| Column | Type | Meaning |
|---|---|---|
| `GID` | String | Group identifier (UUID). Same for all records of one duplicate group |
| `GRP_SIZE` | Integer | Number of records in the group; set on the master row (and 0 on non-masters in some versions, verify) |
| `MASTER` | Boolean | `true` for the group's reference/master record (VSR: first record of the group; T-Swoosh: the created survivor record) |
| `SCORE` | Double | Similarity of this record to its master (1.0 for master) |
| `GRP_QUALITY` | Double | Group quality on the master row only: VSR = minimal matching score in the group; T-Swoosh = minimal score across all record pairs |
| `MERGED_RECORD` | Boolean | T-Swoosh and more than one tMatchGroup in the job only: marks records created by merging |
| `MATCHING_DISTANCES` | String | Only with `Output distance details` |

Scaling rules: blocking key cardinality should give blocks of at most a few
thousand rows; use several passes with different keys rather than one loose
key. For Spark, prefer tMatchPairing/tMatchPredict beyond ~10M rows.

### Machine-learning matching on Spark

Spark Batch only (`Matching with machine learning` family; Feature Manager
install; Spark 2.4+ in local mode for 8.0).

| Component | Purpose | Key settings | Notes |
|---|---|---|---|
| tMatchPairing | Pass 1: generate suspect pairs from a blocking key, separate `Exact duplicates` and `Uniques`, emit a `Pairs sample` for labeling and a **pairing model** folder | `Blocking key` definition (same tGenKey-like table), `Suffix for pairing output`, `Pairing model folder`, `Sample size`, `Separate exact duplicates`; outputs `Pairs`, `Pairs sample`, `Uniques`, `Exact duplicates` | Send `Pairs sample` to a TDS **Grouping** campaign (tDataStewardshipTaskOutput) so stewards label pairs as duplicate / not duplicate; or label a CSV manually with a `LABEL` column |
| tMatchModel | Pass 2: train a Random Forest classifier from the labeled sample, write a **matching model** folder | `Matching key` columns, `Label column`, `Matching model folder`, `Number of trees`, `Max depth`, `Feature generation` options, `Model evaluation` output (precision/recall) | Re-train whenever sources or labeling change |
| tMatchPredict | Pass 3: label new pairs or whole datasets as duplicates/suspects/unique using both models | `Input type`: `paired` (from tMatchPairing) or `unpaired` (raw data; needs `Pairing model folder`), `Matching model folder`, `Clustering classes` (labels treated as matches, e.g. `duplicate`), `Output` links `Matches`/`Suspects`/`Uniques` | Groups are assigned `GID`-style ids like tMatchGroup; combine with tRuleSurvivorship |
| tMatchIndex / tMatchIndexPredict | Continuous matching against ES | see above | Reuse the same two model folders |

### Survivorship

| Component | Purpose | Key settings | Notes / Spark |
|---|---|---|---|
| tRuleSurvivorship | Compute one survivor (golden) record per group (GID) from a sorted flow of duplicates, using Drools rules generated from a rule table | `Group identifier` (GID column), `Group size` column (optional, GRP_SIZE), `Rule table`: `Rule Name`, `Reference Column`, `Function` (`Most common`, `Most recent`, `Most ancient`, `Longest`, `Shortest`, `Largest`, `Smallest`, `Most complete`, `Most trusted source`, `Concatenate`, `Fill empty` (survive non-blank only), `Expression` (custom Drools condition), `Match regex`, `No regex match`, `Match index`, `Survive as` sequencing), `Value` (parameter), `Target Column`, `Ignore blanks`; `Advanced settings > Generate rules and survivorship flow` button (writes `.drl` under `metadata/survivorship/<rulePackage>`), `Rule package name`, `Define survivorship rules on column level` vs multi-condition | Output = one row per group (`Survivor` flag column `SURVIVOR` plus `CONFLICT` list of columns whose values conflicted, unverified names). Input must be grouped by GID (use tMatchGroup `Sort the output data by GID` or tSortRow). The rule files are project items, so regenerate after changing the table and commit them. Spark B |
| tSurviveFields | Older fixed-function survivorship (per column function on an already sorted/grouped flow) | `Group identifier`, per-column function | Legacy; prefer tRuleSurvivorship or T-Swoosh |
| tDuplicateRow | Generate synthetic duplicates/typos for test data | `Number of duplicates`, `Modification functions` per column (soundex error, replace letter, add/remove char, exchange char, set blank) | Test/benchmark only |

### Validation and compliance

| Component | Purpose | Key settings | Notes / Spark |
|---|---|---|---|
| tSchemaComplianceCheck | Validate rows against a schema (type, nullable, length/precision, date pattern); rejects to `Rejects` link with `errorCode`/`errorMessage` | `Base Schema` mode: `Check all columns from schema`, `Custom defined` (per column: `Column`, `Type`, `Nullable`, `Date pattern`, `Length`, `Precision`, `Check`), `Use another schema for compliance check`; `Advanced settings`: `Check date pattern` / `Use fastest date check` (lenient), `Ignore TimeZone when check date` (7.x+), `Treat all empty string as NULL`, `Trim the excess content of column when length checking` (unverified label) | errorCode is a bit sum: 2 = type/parse, 4 = null or empty on non-nullable, 8 = length/precision (community-sourced; multi-error rows do not always add cleanly). errorCode is only a reject-flow field, not a globalMap variable. Date pattern defaults to the schema pattern; an input String that does not match the pattern is a type error. Spark B/S |
| tPatternCheck | Route rows whose column matches a regex to `Matching Data`, others to `Non-Matching Data` | `Column to check`, `Pattern`: `Use pattern from repository` (regex from `Libraries > Patterns > Regex`, Java expression) or custom `Pattern` string | Repository pattern is copied at design time (not live); re-select to refresh |
| tVerifyEmail | Validate and optionally correct email addresses | `Column to validate`; `Complete verification` vs `Regular expression`; `Email regex`; `LOCAL Part Options`: `Use column content` (rebuild local part from `First name`/`Last name` columns with a format like `f.lastname`), `Use local part rules` (allowed chars, min/max length); `DOMAIN Part Options`: `Check domain exists`/`Check TLD`, `Use black list`/`white list`, `Check with mail server callback` (SMTP RCPT TO probe; `Mail server`, `Timeout`) ; `Case sensitive` | Output columns `VerificationLevel` (`VALID`, `INVALID`, `CORRECTED` (only with Use column content), `VERIFIED`/`REJECTED` (only with mail server callback)), `Suggested_Email`. Domain checks need DNS egress from the job server; callbacks are often blocked by MTAs (false REJECTED). Spark B/S |
| tUniqRow / tFilterRow / tReplace | Exact dedup / filters / replace | see components-core.md | Core Processing family |
| tDqReportRun | Run a Profiling report from a job | repository `Report` selector; output folder | Platform editions; job build embeds the report + analyses |
| tReservoirSampling | Random sample of N rows from an unbounded flow (reservoir algorithm) | `Sample size`, `Random seed` | Used before tMatchGroup wizard or tDataprepRun testing |

### Synonyms, sampling, test data

| Component | Purpose | Key settings | Notes |
|---|---|---|---|
| tSynonymOutput | Build/update a Lucene **synonym index** (reference word + synonyms list) from a flow | `Index path`, `Mode` (`Create index`, `Append to index`, `Update index`), `Reference` column, `Synonyms` column, `Synonym separator` (default `|`) | Index consumed by tStandardizeRow `Index` rules, tSynonymSearch, Data Preparation `Lookup` (indirectly) |
| tSynonymSearch | Look up input values in a synonym index and return the reference word(s) with a score | `Index path`, `Columns to search` table (`Input column`, `Reference output column`, `Search mode`: Match exact / any / all / partial / fuzzy variants, `Limit of each search`, `Word distance`), outputs `NB_MATCHES`, `SCORE`, `MATCH_FIELD` per column (unverified exact names) | Lucene index must be rebuilt when upgrading Studio major versions (Lucene format change) |
| tFirstnameMatch | Standardize first names/nicknames to a canonical name via the bundled firstname index | `Column`, `Country`/gender options, outputs `Firstname`, `Gender` (unverified) | Uses `firstname.idx` index shipped with the DQ libs |
| tReservoirSampling | see above | | |
| tDuplicateRow | see above | | |

### Data privacy (masking, shuffling, encryption)

| Component | Purpose | Key settings | Notes / Spark |
|---|---|---|---|
| tDataMasking | Mask columns in place with per-column functions, optionally format-preserving and bijective | `Modifications` table: `Input Column`, `Category` (Character handling, Numeric, Date, Address/Email/Phone/..., Generation, Semantic type), `Function`, `Method` (`Basic` (random, format not guaranteed), `FF1 with AES`, `FF1 with SHA-2`), `Alphabet` (`Best guess`, `Digits`, `Lower/Upper case letters`, `Latin letters`, `Hiragana`, ... for FF1), `Extra Parameter` (e.g. `n` for Replace first n chars, list/file path for Generate from list/file), `Keep format`, `Keep empty`/`Keep null`; `Advanced settings`: `Seed for random generator` (makes Basic masking repeatable across runs), `Password or 256-bit key for FF1 methods` (8.0; 7.x `Password for FF1 method`), `Use tweaks with FF1 encryption` + `Column containing tweaks` (7.3+/8.0), `Output the original row` (adds a copy), `Should null input return null` | Function families (examples): `Replace all`, `Replace first n`/`last n`/`n first`/`between` characters, `Replace characters with character/numeric`, `Keep first/last n chars and replace`, `Replace by range`, `Numeric variance` (percent), `Date variance` (days), `Set to null`, `Generate from list`/`from file`, `Generate sequence`, `Generate credit card number` (Luhn-valid, keep issuer), `Generate SSN` (FR/US/UK/...), `Generate phone number`, `Generate account number` (IBAN-like), `Generate email`/`Mask email local part/domain`, `Mask address` fields, `Generate between`, `Bijective substitution` (semantic type dictionary-based 7.3+). FF1 methods: NIST FF1 format-preserving encryption using AES-CBC or SHA-2 as PRF, produce same-format, bijective, repeatable output given the same password/key and alphabet; input must have at least 2 characters in the alphabet (else null); Java 8u161+ (unlimited crypto). Without a password a random one is generated per execution so output differs every run and cannot be unmasked. Tweaks make masking non-bijective (tweak value changes per execution unless column tweaks). Spark B/S |
| tDataUnmasking | Reverse FF1-masked columns | Same table with the same `Function`, `Method`, `Alphabet` and the same `Password or 256-bit key`; `Column containing tweaks` if used | Only FF1 methods are reversible; `Basic` cannot be unmasked. Alphabet, function and extra parameter must match exactly |
| tPatternMasking | Mask values that follow a defined field pattern (e.g. SSN `999-99-9999`, license plates) while preserving structure, consistently | `Column to mask`; `Field` table: `Field name`, `Type` (`Enumeration` list of allowed values, `Interval` min..max numeric, `Date pattern` with range, `Word`/`Alphabet` (exact type list unverified)), `Values`/`Range`; `Method` `Basic`/`FF1 with AES`/`FF1 with SHA-2`; `Advanced settings` password, tweaks, `Separator` detection (space, slash, dash, dot), `Output null when input does not match` | Input not matching the composed pattern -> null output. Reversible with tPatternUnmasking using identical fields and password. Feature Manager install. Spark B |
| tPatternUnmasking | Inverse of tPatternMasking | identical field table + password | |
| tDataShuffling | Shuffle values among rows so columns stay realistic but rows are decoupled | `Shuffling columns` table: `Column`, `Group ID` (columns with same ID shuffle together as a tuple; `0` = not shuffled); `Advanced settings > Partitioning columns` (shuffle only within rows sharing the partition values, e.g. country); `Seed`, `Buffer size` (Standard: rows loaded per shuffle block) | Deterministic only with a seed. Spark B |
| tDataEncrypt | Encrypt columns (ciphertext as Base64 string) | `Secret method`: `Password` + `Cryptographic file path` (file holds PBKDF2 salt, random 256-bit key wrapped by AES with password, and method) or `Secret key` (Base64 256-bit); `Encryption method`: `AES-GCM` (AES-256) or `Blowfish`; `Columns to encrypt` table; `Generate cryptographic file` button (unverified) | Output columns become String regardless of input type. Java 8u161+. Spark B |
| tDataDecrypt | Decrypt tDataEncrypt output | same password + cryptographic file / same secret key; `Columns to decrypt` with target type | Must use the exact same cryptographic file |
| (no tDataPrivacyRule) | - | - | There is no data-privacy-rule component; privacy/quality rules are a Talend Cloud Data Inventory concept, see the Cloud section |

### Stewardship and Preparation components

| Component | Purpose | Key settings | Notes |
|---|---|---|---|
| tDataStewardshipTaskOutput (tDSOutput from 8.0 R2025-12) | Create tasks in a Talend Data Stewardship campaign from a flow | `URL` (on-prem `http://host:19999/data-stewardship/` or Talend Cloud regional TDS URL), `Username`/`Password` or `Use Talend Cloud token`; `Campaign` (fetched list; `Campaign type` shown: `RESOLUTION`, `MERGING`, `ARBITRATION`, `GROUPING`); `Task priority` (`Very low` .. `Very high`), `Tags`, `Assignee` (user/role), `Source` column; `Generate schema from data model` button; `Advanced settings > Batch size`, `Die on error` | For `MERGING`/`GROUPING` the component adds input columns `TDS_GID` (group id, e.g. tMatchGroup GID), for `MERGING` also `TDS_MASTER` (boolean master vs source record) and `TDS_RATING` (per-source trust rating); for `ARBITRATION` `TDS_ARBITRATION` holds the proposed choice. Task schema is generated from the campaign's data model and must match column names/types; a data model change invalidates existing jobs |
| tDataStewardshipTaskInput (tDSInput) | Read tasks (typically resolved ones) back from a campaign | same connection; `Campaign`; `Task state` filter (`New`, `Ready`, `To validate`, `Validated`, `Rejected`, `Resolved` (states depend on campaign workflow - verify in TDS), `Assignee`, `Priority`, `Tags`, `Last modified since`; `Advanced settings > Page size` | Adds output columns `TDS_ID` (task id), `TDS_STATE`, `TDS_ASSIGNEE`, `TDS_PRIORITY`, `TDS_TAGS`, `TDS_LAST_UPDATE`, plus per type `TDS_GID`, `TDS_MASTER`, `TDS_SCORE` (Grouping/Merging: distance to master), `TDS_ARBITRATION`, `TDS_ARBITRATION_LABEL` (Arbitration/Grouping), `TDS_RATING` |
| tDataStewardshipTaskDelete (tDSDelete) | Delete tasks (e.g. after export) | connection, campaign, `Task state` filter or IDs from input flow | Permanent |
| tDataprepRun | Execute a Data Preparation recipe on the flow inside a job | `URL` (`https://tdp.<region>.cloud.talend.com` or on-prem `http://host:9999`), `Email`/`Password` or `Use Talend Cloud token`; `Preparation` (`Choose...` dialog or `Preparation path` string / context var) and `Version` (`Current state` or a numbered version); `Fetch Schema` button; `Advanced settings > Encoding`, `Fail on error` | Output schema is all `String` by default and reflects the preparation's column additions/removals. Incompatible/ignored functions: `Make as header`, `Delete row`, single-cell edits, and in Standard also `Lookup`/`Join` and `Text clustering`-type functions that need the whole dataset (verify per version; the preparation list shows a warning icon). Re-run `Fetch Schema` after any preparation or dataset change. Spark B (Spark Streaming variant deprecated) |
| Talend Cloud dataset access | Read/write Talend Cloud Data Inventory datasets from a Studio job | Talend Cloud connection, dataset selector | Datasets are first-class sources/sinks in Pipeline Designer; Studio exposure (component names like tDatasetInput/tDatasetOutput) is unverified - check the Data Quality / Talend Cloud families in Feature Manager |

### Deduplication pipeline (ASCII)

```
source(s) --> tMap/tStandardizeRow/tStandardizePhoneNumber (normalize)
          --> tGenKey (T_GEN_KEY = Soundex(lastname)+First3(zip))
          --> tSortRow (T_GEN_KEY)                       [optional]
          --> tMatchGroup (VSR or T-Swoosh, blocking = T_GEN_KEY,
                           Separate output, Sort output by GID)
                | Uniques  --> golden output as-is
                | Matches  --> tRuleSurvivorship (GID, GRP_SIZE) --> golden output
                | Suspects --> tDataStewardshipTaskOutput (MERGING campaign)
                                   ... stewards resolve ...
                               tDataStewardshipTaskInput (state = Resolved) --> golden output
```

## Talend Data Stewardship

Web application for human-in-the-loop resolution of DQ tasks.

| Concept | Details |
|---|---|
| Deployments | **Talend Cloud**: `Data Stewardship` app in the TMC launcher (per region URL `https://tds.<region>.cloud.talend.com`); users/roles come from TMC (`Data Steward`, `Campaign Owner` roles / entitlements). **On-prem 7.x/8.0**: `Talend Data Stewardship` server (Spring Boot, default port `19999`, `data-stewardship.properties`), **MongoDB** (task/campaign store), **Kafka + Zookeeper** (history/events), **Talend Identity and Access Management** (Syncope-based IAM, port 9080, OIDC) and the **Talend Dictionary Service** for semantic types; Docker Compose and manual installs documented |
| Data model | Named schema: fields with `Type` (string, integer, decimal, boolean, date, ...), `Semantic type` (from TDS, validates values and shows quality bar), `Mandatory`, `Key`, `Default`, `Description`, `Validation` constraints (min/max, regex). Changing a model after a campaign has tasks is restricted (add optional fields only) and breaks existing tDataStewardshipTaskOutput schemas until regenerated |
| Campaign types | `Resolution`: one record per task; stewards correct/complete fields, must satisfy model validation to resolve. `Merging`: tasks contain N source records + a proposed master (from tMatchGroup/T-Swoosh); stewards pick survivor values per field or edit, result = golden record; `TDS_RATING` shows source trust. `Arbitration`: steward picks one of the campaign's predefined `Choices` (classification/approval) per record; `TDS_ARBITRATION` pre-fills. `Grouping`: pairs of records to label `duplicate`/`not duplicate` (feeds tMatchModel) |
| Workflow | Campaign has a configurable **workflow**: default states `New` (unassigned) -> `Ready` (assigned, editable) -> `To validate` (when a validation step is enabled) -> `Resolved`/`Validated`; `Rejected` sends back; task `Reject`/`Reopen` actions. Each transition is a role-bound step (`Data steward`, `Data steward validator`) |
| Roles | `Campaign owner` (creates data models, campaigns, assigns participants, sees all tasks), `Data steward` (works assigned tasks), steward **groups** (a task assigned to a group is claimable by any member) |
| Task attributes | `Priority` (`Very low`, `Low`, `Medium`, `High`, `Very high`), `Tags` (free text, filterable), `Assignee`, `Source` (record origin), `Due date` (Cloud), `Comments`, history/audit of changes |
| Bulk operations | Multi-select assign/priority/tag, `Choose a column value for all records` in Merging, CSV import of tasks, CSV export of resolved tasks |
| REST API | On-prem `http://host:19999/data-stewardship/api/v1/...` (campaigns, tasks, data models; Swagger UI at `/data-stewardship/swagger-ui.html`); Cloud: same resources behind `https://tds.<region>.cloud.talend.com/data-stewardship/api/v1/` with a TMC Personal Access Token. See apis-sdks.md |
| Studio integration | tDataStewardshipTask* (tDS*) components; TMC `Data Stewardship` tasks counted in license as named stewards |

## Talend Data Preparation

| Concept | Details |
|---|---|
| Deployments | Talend Cloud app (`Data Preparation` in TMC launcher) or on-prem server (7.x: Spring Boot `data-preparation` on port `9999`, MongoDB, Talend Dictionary Service, optional Spark Job Server for "Export to HDFS", Kafka in later versions; `application.properties`). The stand-alone **Data Preparation Free Desktop** (embedded MongoDB) was discontinued around 7.0 |
| Datasets | Uploaded files (CSV, Excel, JSON (flattened), Avro/Parquet via Cloud), database tables via Talend Cloud connections / Data Inventory, HDFS and S3 (on-prem via job-based import "Live dataset" produced by a Studio job with tDatasetOutput), "live datasets" refreshed by a job run on an engine. Sample of 10k rows by default; full run at export |
| Preparation | Ordered recipe of **functions** applied to a dataset; each step can be disabled/edited; `Versions` (`Current state` plus named versions created via `Save as version`); `Sharing` with users/groups (read or edit); `Folders` |
| Function catalog (grouped) | Text: `Trim`, `Change case` (upper/lower/title), `Remove trailing/leading chars`, `Remove part of the text`, `Replace the cells that match`, `Split the text in parts`, `Extract` (email parts, URL parts, number, date parts, string between), `Concatenate`, `Pad`, `Remove non alpha-numeric`, `Standardize values` (uses synonym/semantic dictionary), `Text clustering` / `Find and group similar text` (fuzzy clustering by Soundex/Metaphone/Fingerprint), `Mask data` (semantic-type aware); Numbers: `Compute` (+ - * / %), `Round`, `Absolute`, `Negate`, `Change number format`, `Min/Max` compare; Dates: `Change date format`, `Compute time since`, `Extract date parts`, `Standardize date`; Data quality: `Fill empty cells with`, `Delete rows with invalid/empty values`, `Keep rows that match`, `Delete the rows that match` (filters), `Remove duplicate rows`, `Clear invalid cells`, `Change type`, `Set semantic type`/`Change the domain`; Structure: `Rename`, `Delete column`, `Reorder`, `Copy column`, `Make as header`, `Split`, `Lookup` (join to another dataset on a key), `Flatten JSON`/`Nest`; Logical: `Negate boolean`, `Create new column` with formulas |
| Quality bar | per column: valid/invalid/empty % based on the inferred or assigned **semantic type** or data type; drives `Delete rows with invalid values` |
| Export | `CSV` (delimiter, enclosure, encoding), `Excel`, `Tableau` (TDE/Hyper; on-prem only), `Export to dataset` (new Data Inventory dataset), overwrite `live dataset` output (job-produced); on-prem `HDFS`/`Amazon S3` through Spark Job Server |
| Studio integration | tDataprepRun applies a preparation inside a job (runs the recipe engine in the job; no server round trip per row). Preparations referencing another dataset (`Lookup`) or whole-dataset statistics (`Text clustering`, `Make as header`, `Delete row`) are ignored/unsupported in jobs. "Export to Talend Studio" never existed as a menu; the integration is tDataprepRun pulling by name/version |
| API | On-prem `http://host:9999/api/...` (datasets, preparations, folders, export); Cloud `https://tdp.<region>.cloud.talend.com/dataprep/api/...` with PAT; Swagger at `/api/swagger-ui.html` (7.x). apis-sdks.md |

## Talend Data Catalog, Data Inventory, Trust Score

| Topic | Details |
|---|---|
| Talend Data Catalog (TDC) | On-prem Java web app (Tomcat, `MM` context: `http://host:11480/MM`), database PostgreSQL/Oracle/SQL Server for the repository, origin = Meta Integration Technology (MITI) Meta Integration Metadata Management (MIMM); previously branded **Talend Metadata Manager** (6.x). Versions 7.x, 8.0, then Qlik-era 8.1/8.2 (verify) |
| Harvesting | **Bridges** (MIMM import bridges, ~200): RDBMS (Oracle, SQL Server, Postgres, Snowflake, Redshift, BigQuery, ...), files (CSV, JSON, Avro, Parquet in HDFS/S3/ADLS), BI (Tableau, Power BI, Qlik Sense, MicroStrategy, Cognos), ETL (**Talend Data Integration** - imports Studio projects/jobs from the workspace export or TAC/Git and derives column-level lineage from tMap and DB components; also Informatica, DataStage, SSIS), data modeling (ERwin, PowerDesigner), cloud (AWS Glue, Azure Data Factory). Each harvested source = a **Model** with versions; `Configuration` = set of models stitched together (connection resolution between ETL and DB models) |
| Lineage / impact | Model-level and column-level lineage diagrams, data flow vs semantic lineage, `Trace Lineage`/`Trace Impact` on any object, connection stitching UI to map ETL connection names to harvested schemas |
| Business glossary | Terms, categories, relationships (synonym, related), term-to-asset classification, approval workflow (Draft -> Under review -> Approved) with roles `Steward`, `Owner`, `Approver`; `Semantic flow` lineage from glossary to physical columns |
| Data classification / sampling | Data profiling and sampling on harvested DBs (needs JDBC credentials); automatic **semantic type**-based classification using the same TDS dictionary; sensitivity labels for GDPR workflows |
| Stewardship workflow | Object-level workflows (review/approve metadata changes), comments, certifications (endorse/warn), custom attributes, tasks |
| REST API | `http://host:11480/MM/rest` (Swagger at `/MM/rest/swagger-ui.html` or `/MM/rest/api-docs`): operations on repository objects, imports (`/import`), lineage, glossary; token via `/MM/rest/v1/auth/...` (unverified path). apis-sdks.md |
| Studio -> TDC | Export a Studio project for TDC's `Talend Data Integration` bridge: `File > Export items` (project export zip) or point the bridge at the TAC/Git project; a Studio-side `Export to Data Catalog` menu is not confirmed (unverified); treat the bridge-side import as the supported path. Data Catalog can also push lineage of Talend Cloud pipelines (Pipeline Designer) in later releases |
| Talend Cloud Data Inventory | Cloud-native inventory of **connections** and **datasets** (sampled 10k rows): automatic semantic discovery, quality bar (valid/invalid/empty per column), **Trust Score** (0-5) aggregating `Validity`, `Completeness`, `Popularity`, `Usage`, `Discoverability` (a sixth `Timeliness` dimension was added later (unverified)); dataset sharing, tagging, certification/rating, documentation (Markdown); datasets consumed by Pipeline Designer, Data Preparation and Stewardship; **Data quality rules** (see Cloud section) attach to datasets and feed the Validity dimension |
| Data Catalog Explorer (Cloud) | TMC-launched read-only browser over an on-prem TDC instance via a Remote Engine ("TDC in the cloud" bridge), later superseded by Qlik Cloud catalog integration |
| Qlik Catalog | Separate on-prem product (ex Podium Data) with its own lineage/ingestion ("Qlik Catalog" and "Qlik Catalog for QVDs"); not the same code base as TDC. Qlik Cloud has its own built-in Catalog; Talend Data Catalog remained for on-prem Talend customers. Verify current roadmap in versions-licensing.md |

## Talend MDM

Talend MDM Platform (Talend Data Fabric). Studio **MDM perspective** +
**MDM Server** (web app `talendmdm` on Tomcat) + **MDM Web UI**. Still
shipped with 8.0 on-prem; no MDM in Talend Cloud. Status: maintenance only;
verify any Qlik end-of-support announcement before recommending new builds.

### Server and storage

| Item | Details |
|---|---|
| App server | Apache Tomcat (since 6.0; JBoss dropped at 6.0). Install via the Talend installer or `TalendInstaller`; context `/talendmdm` (web UI at `http://host:8180/talendmdm/ui` by default) |
| Configuration | `<mdm>/conf/mdm.conf`: `system.storage.*` (system DB), `default.storage.*` (master data), `staging.storage.*` (staging), per-container overrides, `admin.user`/`admin.password`, `mdm.routing.engine.*` (event manager), `mdm.ssl.*`; `<mdm>/conf/datasources.xml` lists JDBC datasources (`<datasource name="MDM">` with `<master>`, `<staging>`, `<system>` sections: `<rdbms-configuration>` url/user/password/dialect, `<init>` for auto-create) |
| Persistence | Hibernate-based RDBMS storage (since 5.x "SQL storage"): H2 (default demo), MySQL, PostgreSQL, Oracle, SQL Server, DB2. Each data container maps to a schema whose tables are generated from the data model (one table per entity/complex type, plus `X_TALEND_*` columns like `X_TALEND_TIMESTAMP`, `X_TALEND_TASK_ID`; staging adds `X_TALEND_STAGING_STATUS`, `X_TALEND_STAGING_ERROR`, `X_TALEND_STAGING_SOURCE`, `X_TALEND_STAGING_BLOCK_KEY`). The legacy XML DB storage (eXist) is gone |
| System containers | `PROVISIONING` (users, roles stored as XML `User`/`Role` items), `CONF` (server configuration: `AutoIncrement` counters, `Service` configs), `UpdateReport` (the journal, entity `Update`), `amaltoOBJECTS*` system objects (data models, views, menus, roles, triggers, transformers, routing orders) inside the `system` storage; `CrossReferencing`, `SearchTemplate` |
| Data containers | Named storage units bound to one data model. Each has a **master** area and optionally a **staging** area (`#STAGING` suffix in APIs, "Staging" checkbox in Studio). Staging stores raw/invalid records with status codes (`000` new, `200`+ error ranges, `205`? (unverified)) for validation runs and match & merge |
| Auto-increment | `AutoIncrement` concept: `xsd:string` fields typed `AUTO_INCREMENT` in the model; counters stored in `CONF` |

### Data model (XSD) and annotations

A data model is an **XML Schema** (`.xsd`) edited in the Studio `Data Model`
editor (tree form) or as source. Top-level `xsd:element`s = **business
entities** (each needs a `xsd:unique` constraint declaring the key with
`xsd:selector xpath="."` and `xsd:field xpath="Id"`). Reusable
`xsd:complexType`s = shared types; `xsd:simpleType` restrictions =
enumerations/patterns. Talend-specific metadata is carried in
`xsd:annotation/xsd:appinfo source="X_..."` elements (the `source` attribute
is case-sensitive):

| Annotation (`appinfo source`) | On | Meaning / value |
|---|---|---|
| `X_Label_EN`, `X_Label_FR`, ... | entity/element | UI label per language |
| `X_Description_EN` | entity/element | UI description |
| `X_Write` | entity/element | Role allowed to write (repeat per role) |
| `X_Hide` | entity/element | Role for which the element is hidden (no read) |
| `X_Deny_Create`, `X_Deny_LogicalDelete`, `X_Deny_PhysicalDelete` | entity | Roles denied these actions |
| `X_ForeignKey` | element | Target `Entity/Id` XPath making the element a FK (value stored as `[id]`, composite `[id1][id2]`) |
| `X_ForeignKeyInfo` | element | XPath(s) of target fields to display next to the FK (e.g. `Customer/Name`) |
| `X_ForeignKeyInfoFormat` | element | Format string for FK info display (`{0} - {1}`) |
| `X_ForeignKey_Filter` | element | XPath condition restricting selectable FK targets (`Product/Status$$=$$"Active"`, supports `xpath:` references to the current record) |
| `X_Retrieve_FKinfos` | element | `true` to fetch FK info in search results |
| `X_FKIntegrity` | element | `true`: block deleting a referenced target record |
| `X_FKIntegrity_Override` | element | allow user override of integrity check |
| `X_Lookup_Field` | element | mark field as lookup/search field in web UI |
| `X_PrimaryKeyInfo` | entity | XPath(s) shown as record title in the UI (e.g. `Customer/Name`) |
| `X_Visible_Rule` | element | XPath boolean expression; element shown only when true (`fn:string-length(../Name) > 0`) |
| `X_Default_Value_Rule` | element | XPath expression evaluated at creation (`fn:current-date()`, `fn:concat(...)`) |
| `X_Schematron` | entity/element | Embedded Schematron `<pattern>` rules for validation on save (error messages per assert) |
| `X_Workflow` | entity | Bonita process bound to the entity (`processName#version#roleName`); workflows deprecated in 7.x and removed in 8.0 |
| `X_AutoExpand` | element | expand complex element by default in the UI |
| `X_Display_Format` | element | number/date display format |
| `X_TargetSystem`, `X_SourceSystem` | element | documentation of system mapping (unverified) |
| `X_Lineage` | element | documentation of source lineage |
| `X_NoAdd`, `X_NoRemove` | repeating element | forbid add/remove of occurrences |
| `X_Deny_Physical_Delete` (legacy spelling) | - | 5.x spelling; current is `X_Deny_PhysicalDelete` (verify in your model, both appear in old projects) |

Field types: standard `xsd:string|int|long|decimal|boolean|date|dateTime|time|
base64Binary|anyURI`, Talend types `UUID`, `AUTO_INCREMENT`, `PICTURE`, `URL`,
`MULTI_LINGUAL`. Inheritance via `xsd:extension` creates polymorphic entities.
Deploy from Studio: right-click `MDM Repository > Data Model > Deploy to`
(server connection) which also (re)generates the container tables; destructive
schema changes (type change, removing elements with data) are refused unless
`Allow destructive changes`/drop-and-recreate is accepted.

### Containers, views, roles, menus

| Object | Repository node | Details |
|---|---|---|
| Data Container | `MDM Repository > Data Container` | Name, bound data model (`Data Model` property set at deploy), `Create staging area`. Export/import of records via `Import/Export` tools in web UI |
| View | `Data Model Views` | Named `Browse_items_<Entity>` (naming convention required: `Browse_items_` prefix + entity for the web UI browse); `Viewable Business Elements` (columns shown), `Searchable Business Elements` (filters), `Filters` (saved XPath where conditions), `Sort`; views can be restricted per role via roles |
| Role | `Role` | Per data model/entity/element read-write access; per menu entry visibility; per view visibility; `Ignore model/element restrictions`; system roles `System_Admin`, `System_Interactive`, `System_Web`, `administration`, `authenticated` |
| Menu | `Menu` | Web UI menu tree (`Browse records`, `Hierarchy`, `Journal`, `Staging Data Container`, `Tasks`, `Bonita Workflow Tasks`, `Smart View`, custom `Process` launches) |
| User | web UI `Manage Users` (stored in `PROVISIONING`) | Login, roles, language, universe (legacy), properties; `admin` default `talend` |
| Storage browser | web UI | `Browse records`, `Hierarchy` (tree by FK), `Staging Data Container` (status counts, validate button), `Journal` (Update Report viewer with before/after), `Reporting` (Jasper reports, legacy), `Tasks` (stewardship/Match & Merge review), `Data Container Management` |

### Processes, triggers, event management

| Concept | Details |
|---|---|
| Process (Transformer) | Ordered **steps**; each step calls a **plugin** with parameters: `callJob` (run a Talend job deployed to the MDM server `<mdm>/webapps/talendmdm/WEB-INF/jobs` or via TAC/JobServer; `callJob` config `protocol=...` `jobName/version`, `contextParam` mapping with `xpath:` or literal), `xslt`, `groovy`, `codec` (XML<->JSON/CSV), `logging`, `routingorder`, `callprocess`, `xpath`/`project` (verify plugin list on your server). Variables `_DEFAULT_` input/output pass the record XML between steps |
| Naming conventions | `beforeSaving_<Entity>` (synchronous pre-save hook; must return `<report><message type="info|error">...</message></report>` and optionally modified `<item>`), `beforeDeleting_<Entity>` (same for deletes), `Runnable#<Name>` (shows as a button/action in the web UI for the selected record), `Runnable_Standalone#<Name>` (menu-level, no record), `Smart View_<Entity>[#<name>]` (renders a record through XSLT into HTML in the `Smart View` tab). A `beforeSaving` returning an `error` message aborts the save |
| Trigger | Repository `Trigger`: `Condition` = XPath on the **Update Report** record (`/Update/Concept = 'Customer' and /Update/OperationType = 'CREATE'`, also `/Update/DataCluster`, `/Update/UserName`, `/Update/Item/path`), `Service` = `callprocess` / `callJob` / `logging` / `workflow` (legacy) (service JNDI names), `Parameters` XML (`<configuration><process>...</process><parameter name="..." value="xpath:..."/>` ) ; `Synchronous` flag (run in-transaction) |
| Event Manager | Every master-area save/delete writes an `UpdateReport` record; the **Routing Engine** evaluates triggers and creates **Routing Orders** (`ActiveRoutingOrder` -> `CompletedRoutingOrder`/`FailedRoutingOrder` queues, viewable in web UI `Routing Orders`); can be stopped/started via REST (`/talendmdm/services/rest/system/routing?action=start|stop` (unverified)). Staging-area writes do NOT emit update reports or fire triggers |
| Validation on save | Order: XSD validation (types, cardinality, enumerations) -> FK existence (and `X_ForeignKey_Filter`) -> Schematron (`X_Schematron`) -> `beforeSaving_` process -> persist -> UpdateReport -> triggers. Staging skips XSD/Schematron so that invalid raw data can land; `Validate staging` moves clean records to master |
| Match & Merge | Match rules defined in the Studio Profiling perspective (`Rules > Match`, VSR/T-Swoosh) attached to an entity (`Match & Merge` tab on the data model entity) run on the staging area: `Run match & merge` in the Staging UI or via `tMDMBulkLoad`/REST `?validate=true`; duplicates are grouped, survivorship applied, golden record written to master, group members linked via `X_TALEND_TASK_ID` for review in `Tasks`/`Data Stewardship` tab |
| Workflow | Bonita BPM-based process definitions designed in the Studio `Workflow` perspective, triggered by `X_Workflow` annotation or processes; deprecated 7.0, removed 8.0. Replace with Talend Data Stewardship tasks fed by jobs |
| Journal | `UpdateReport` records (`Update` entity: `UserName`, `Source`, `TimeInMillis`, `OperationType` CREATE/UPDATE/PHYSICAL_DELETE/LOGICAL_DELETE/RESTORED, `Concept`, `DataCluster`, `DataModel`, `Key`, `Item/path/oldValue/newValue`) viewable in `Journal` with before/after diff; grows unbounded unless purged (web UI `Journal > Purge` or job with tMDMDelete on `UpdateReport`) |
| Recycle bin | Logical delete moves records to `Recycle Bin` (`DroppedItem`); `Restore` or physical delete |

### MDM components in jobs

Palette family `Talend MDM`. All take a server connection (`URL`
`http://host:8180/talendmdm/services/soap` historically; 7.x/8.0 use the
same base and REST underneath; `Username`/`Password`; `Universe` legacy) or
`Use existing connection` from tMDMConnection. Schema for an entity: use the
`MDM Repository > Metadata > Talend MDM` wizard (Repository `Metadata > Talend
MDM` connection -> `Retrieve Entity` creates one schema per entity from the
XSD; repeating/complex elements become XML-typed `String` columns or are
flattened only one level).

| Component | Purpose | Key settings | Notes |
|---|---|---|---|
| tMDMConnection | Open a reusable server connection | `URL`, `Username`, `Password`, `Universe` (legacy) | Pair with tMDMClose |
| tMDMClose | Close a connection | `Component list` | |
| tMDMInput | Read records of one entity by XPath/filters | `Data Model`, `Data Container`, `Entity`, `Use staging area`? (`Data Container` + staging checkbox), `Use multiple conditions` (table: `XPath`, `Function` (Contains, Equals, Starts with, Joins with, Is greater than, ...), `Value`, `Predicate` AND/OR), else `XPath query`; `Skip rows`, `Max rows` (paging); `Advanced settings > XML field`/`Schema XPatterns` (`Loop XPath query`, mapping XPath to columns like tFileInputXML), `Batch size`, `Retrieve FK info` | Returns whole records as XML in one column unless XPath mapping to columns is configured; use the Retrieve Entity schema to get flat columns |
| tMDMOutput | Create/update/delete records one by one through the API (fires validation, beforeSaving, triggers) | `Data Model`, `Data Container`, `Use staging area`, `Action`: `Insert or update`/`Update`/`Logical delete`/`Physical delete` (per-version labels), `Entity`, `XML field` (input column holding the record XML) or `Build XML from schema` mapping (`Advanced settings > Use XML field` vs schema mapping with `Loop/Group` like tFileOutputXML), `Fire create event`, `Fire update event` (control UpdateReport generation), `Validate records` (unverified), `Partial update` (`Use partial update` with `Pivot` XPath and `Key` for merging repeating elements) | Slow (one call per row); for bulk use tMDMBulkLoad. Rejects link carries the server validation error message |
| tMDMBulkLoad | Stream many records into a container in one call (`/talendmdm/services/bulkload`) | `Data Model`, `Data Container`, `Entity`, `Use staging area`, `Validate` (XSD validation on load), `Generate update report`, `Insert only` (unverified), `Commit size`/`Chunk size`, `XML field` or built XML | Fastest load path (thousands of rows/s). Loading master directly with `Validate` off bypasses Schematron/beforeSaving; standard pattern is load to staging + `Validate staging` / match & merge |
| tMDMDelete | Delete records by key (logical or physical) | `Data Model`, `Data Container`, `Entity`, `Keys` (input columns), `Logical delete`/`Physical delete`, `Fire delete event` | Physical delete of referenced records fails with FK integrity error when `X_FKIntegrity` is set |
| tMDMViewSearch | Query through a View (`Browse_items_<Entity>`) with where conditions, returning viewable elements | `View name`, `Operations` table (XPath, Operator, Value), `Order by`, `Skip rows`, `Max rows`, `Data Container`, `Spell threshold` (unverified) | Honors view filters and role restrictions of the connecting user |
| tMDMSP | Call an MDM **stored procedure** (saved XQuery/SQL in `Stored Procedure` repository item) | `Stored procedure name`, `Parameters`, `Data Container` | Legacy from XML DB era; limited on RDBMS storage |
| tMDMRouteRecord | Push a record key into the event manager so triggers evaluate it (creates a routing order without saving) | `Data Container`, `Entity`, `Keys`, `Data Model` | Used to re-fire triggers from jobs |
| tMDMTriggerInput | Entry point of a job started by an MDM trigger (`callJob`): exposes the triggering record/update report XML | single-column schema holding the XML passed by the process (column name unverified) | The job is deployed to the MDM server; parameters arrive as context via `contextParam`; typical job: tMDMTriggerInput -> tExtractXMLField -> processing -> tMDMTriggerOutput |
| tMDMTriggerOutput | Return a result/report XML to the calling process | `XML field` | |
| tMDMReceive | Parse an MDM record XML (from a trigger, queue or tMDMInput XML column) into flat schema columns by XPath | `XML field`, `XPath` mappings | Equivalent to tExtractXMLField with MDM conveniences |
| tMDMCommit / tMDMRollback | Commit/rollback a transaction opened on a tMDMConnection (`Use transaction`) | `Component list` | Transactions span tMDMOutput calls (7.x+) |
| tMDMRestInput | Call MDM REST `/data/{container}/query` with a JSON query and return records (7.x+) | connection, `Data Container`, `Entity`, `Query` JSON (`{"select": {"from": ["Customer"], "where": {...}}}`), paging | Replaces XPath-only querying (unverified exact labels) |

### MDM APIs

| API | Path | Notes |
|---|---|---|
| REST (7.x/8.0) | `http://host:8180/talendmdm/services/rest/` with Basic auth. Main resources: `/data/{container}` (GET record by `?type=Entity&id=...` (unverified), PUT/POST XML record `/data/{container}` with `?updateReport=true&validate=true`, DELETE), `/data/{container}/query` (POST JSON query language: `select/from/where/order_by/limit/skip`), `/data/{container}/exists`, `/system/models`, `/system/models/{model}` (deploy XSD), `/system/containers`, `/system/views`, `/system/roles`, `/system/triggers`, `/system/transformers`, `/tasks/staging/{container}` (start/monitor staging validation and match & merge), `/system/routing` (event manager), `/bulkload` legacy at `/talendmdm/services/bulkload?cluster=...&concept=...&datamodel=...&validate=...&smartpk=...` | Swagger/WADL at `/talendmdm/services/rest/application.wadl` (JAX-RS). Full detail in apis-sdks.md |
| SOAP (legacy, `/talendmdm/services/soap`, WSDL `?wsdl`) | `getItem`, `putItem`, `putItemWithReport`, `deleteItem`, `viewSearch`, `xpathQuery`/`getItems`, `putDataModel`, `routeItemV2` | Used by old tMDM* components and third-party clients; still enabled in 8.0 for compatibility; prefer REST |
| Studio deploy | `Deploy to` on any MDM repository item, or `Export > MDM objects` zip, or the `commandline` MDM export/import (`exportMDMObjects` unverified) | CI: build jobs with MDM items; server import of `mdm_objects.zip` via web UI `Import/Export` |

### Golden record pipeline (ASCII)

```
   Source systems                Talend DI job (hub)                        Talend MDM server
   CRM --+                                                                 +-----------------------------+
   ERP --+--> tDBInput/tFileInput --> tMap (map to entity schema,          |  Data container: Customer   |
   Web --+        tStandardizeRow / tStandardizePhoneNumber /              |                             |
                  tAddressRowCloud (cleanse)                               |  STAGING area               |
                  --> tGenKey --> tMatchGroup (T-Swoosh)                   |   raw rows (status 000)     |
                  --> tRuleSurvivorship (one survivor per GID)             |     | Validate staging      |
                  --> tXMLMap / tWriteXMLField (entity XML)                |     | (XSD, FK, Schematron) |
                  --> tMDMBulkLoad (Use staging area, Validate off) ------>|     | Match & Merge         |
                                                                           |     v                       |
   Stewards ---- MDM web UI Tasks / Talend Data Stewardship (MERGING) ---->|  MASTER area                |
                                                                           |   golden Customer records   |
   Subscribers <-- tMDMInput / tMDMViewSearch / REST query <---------------|   UpdateReport journal      |
                   or Trigger (OperationType=UPDATE) -> callJob            |     | routing engine        |
                   -> tMDMTriggerInput job -> publish to Kafka/DB/ESB      |     v triggers -> callJob   |
                                                                           +-----------------------------+
```

Variant without staging: tMDMOutput per row directly to master (fires
beforeSaving and triggers synchronously; 10-50 rows/s) - acceptable for
trickle feeds from ESB routes, not for initial loads.

### MDM performance and operations

- Prefer `tMDMBulkLoad` into staging; validate in bulk; keep `Generate update
  report` off for initial loads (journal growth and routing-order storms),
  then re-enable for deltas.
- Index the RDBMS columns used in view filters (`X_TALEND_TIMESTAMP`, FK
  columns); Hibernate second-level cache settings live in `mdm.conf`
  (`hibernate.*` overrides) and `<mdm>/conf/datasources.xml`.
- Set `max.export.count`/paging in `mdm.conf` and always page with
  `Skip rows`/`Max rows` in tMDMInput; a no-filter XPath on a big entity loads
  everything.
- Purge `UpdateReport` and completed routing orders on a schedule (job with
  tMDMDelete on entity `Update` in container `UpdateReport`, or REST
  `/system/routing/orders` purge (unverified)); the journal is often the
  biggest table in the DB.
- Logs: `<mdm>/logs/mdm.log` (log4j2 in 8.0: `<mdm>/conf/log4j2.xml`), Tomcat
  `catalina.out`; verbose SQL via `org.hibernate.SQL=DEBUG`.
- Users/roles in `PROVISIONING` can be exported as XML from the web UI; LDAP
  integration via `<mdm>/conf/mdm-security-*.xml` Spring Security config
  (unverified file name).
- Schema evolution: additive changes are hot-deployable; renames/type changes
  need export records -> redeploy model with drop -> reload.

## Governance on Qlik Talend Cloud

| Feature | Details |
|---|---|
| Data quality rules (Talend Cloud) | Defined in **Data Inventory > Data quality rules** (formerly in Management Console): a rule has a name, a `Condition`/`Expression` built with the rule builder (column placeholders, operators, functions) or SQL-like syntax, criticality, and is applied to datasets by mapping rule columns to dataset columns. Rule results show a **rule-based quality bar** on the dataset and feed the **Validity** dimension of the Trust Score; rules can also run in Pipeline Designer (`Data quality rules` processor); Studio 8.0 R2022+ releases expose cloud DQ rules through a Data Quality family component (name unverified; check Feature Manager under Data Quality) |
| Trust Score | Dataset-level 0-5 score across Data Inventory, Data Preparation and Pipeline Designer views; dimensions `Validity` (semantic/rule validity %), `Completeness` (non-empty), `Popularity` (ratings/certification), `Usage` (how many preparations/pipelines use it), `Discoverability` (documentation, tags, description) ; Talend Trust Assessor was a free web uploader exposing the same score (retired) |
| Semantic types management | Data Inventory > `Semantic types` (dictionary/regex/compound, with `Validation mode`), synchronized to Studio via the Dictionary Service preference; custom types available in Pipeline Designer, Data Prep, Stewardship, Studio DQ components |
| Data privacy / sharing | Dataset sharing to users/groups, connection credential isolation, Remote Engine for on-prem data (sample never leaves unless shared), `Remote Engine Gen2` for pipelines |
| Qlik Talend Data Integration (2024-2026) | Qlik Cloud's **Data Integration** hub hosts "Data Quality" capabilities migrated from Talend Cloud: quality bar, Trust Score and rules on Qlik Cloud datasets ("Qlik Talend Cloud Data Quality", announced 2024) with a **Qlik Data Gateway** for on-prem sources; Talend Cloud apps (Data Inventory, Data Preparation, Data Stewardship, Pipeline Designer) continue as the "Talend Cloud" tenant while Qlik migrates capabilities - exact dates per versions-licensing.md and Qlik release notes (verify) |
| Stitch | Qlik-owned ELT (connectors into warehouses); no DQ/governance features; sometimes listed next to Talend Cloud in licensing, not relevant to this file |
| Qlik Catalog | Qlik's on-prem catalog (ex Podium); Qlik Cloud Catalog is the built-in cloud catalog; Talend Data Catalog stays as the Talend on-prem enterprise catalog. Three different products - do not conflate when a customer says "the catalog" |

## Gotchas

| Symptom | Cause | Fix |
|---|---|---|
| tMatchGroup runs for hours / OutOfMemory on a few hundred thousand rows | No `Blocking Selection` column, so every record is compared to every group master (O(n^2)) | Add tGenKey (e.g. Soundex of name + zip prefix) and set it as blocking column; split into multi-pass tMatchGroup with different keys instead of one loose key |
| Group count/masters differ between VSR and T-Swoosh on the same data | VSR keeps the first input record as master and never merges groups; T-Swoosh creates a new survivor record and can merge groups as it learns | Choose per use case: VSR when you must keep original rows only; T-Swoosh when you want the golden record created inline. Do not compare GRP_QUALITY across algorithms (defined differently) |
| MERGED_RECORD column missing from tMatchGroup output | Column only exists with T-Swoosh and more than one tMatchGroup in the job | Add it only in multi-pass T-Swoosh designs; otherwise remove from schema |
| Imported match rule changed thresholds/functions unexpectedly | Rule algorithm (VSR vs T-Swoosh) differs from the component's `Matching Algorithm`; incompatible parameters reset to defaults | Set the algorithm first, then import; keep separate rule items per algorithm |
| tRuleSurvivorship outputs several survivors per group or wrong values | Input not contiguous by GID, or `Concatenate` picks input order (not sorted) | Enable `Sort the output data by GID` on tMatchGroup or add tSortRow on GID (and a secondary sort for Concatenate order); regenerate rules after editing the table |
| tRuleSurvivorship job fails after Git pull with "rule package not found" | Generated `.drl` files under `metadata/survivorship/<package>` were not committed | Commit the generated survivorship folder; or regenerate with `Generate rules and survivorship flow` on each machine |
| tSchemaComplianceCheck rejects every date row | Input column is String with a pattern different from the schema `Date Pattern`, or `Check date pattern` strict vs lenient mismatch | Set the schema date pattern to the actual input format (e.g. `"yyyy-MM-dd HH:mm:ss"`), or convert with tConvertType/tMap first; consider `Ignore TimeZone when check date` |
| tSchemaComplianceCheck errorCode does not add up / not available in tJava | errorCode is a bit-sum field on the reject flow only (2 type, 4 null, 8 length; multi-error rows are not always summed) | Branch with tMap/tFilterRow on the reject link; log errorMessage rather than decoding codes |
| tStandardizePhoneNumber marks valid numbers invalid for region | Default `Country code` applied to all rows (or wrong per-row country column); `IsValidPhoneNumberForRegion` (7.3+) is stricter than `IsValidPhoneNumber` | Use `Column` mode with an ISO country column; treat `IsValidPhoneNumber=true, ForRegion=false` as "valid, wrong country" |
| tAddressRowCloud returns HTTP 401/403 or empty results after a few thousand rows | Provider API key invalid, or account transaction quota/rate limit exhausted; Google Places needs billing enabled | Verify key on the provider portal; add tReservoirSampling/`Limit` in tests; prefer tBatchAddressRowCloud for bulk; cache results in a DB keyed by normalized address |
| tDataUnmasking returns garbage or nulls | Different password/key, alphabet, function or extra parameter than tDataMasking; tweaks enabled; or input was masked with `Basic` method | Use identical FF1 method/alphabet/password; disable tweaks if bijectivity is required; `Basic` is irreversible by design |
| tDataMasking FF1 yields null for short values | FF1 requires at least 2 (sometimes more, alphabet-dependent) characters | Pre-filter short values or fall back to `Basic`/`Set to null` for them |
| Masked output changes on every run | No `Seed for random generator` (Basic) or no FF1 password set (random password per execution) | Set a seed / password; store the password in a context variable or vault |
| tDataStewardshipTaskOutput fails with schema/type mismatch or HTTP 400 | Campaign data model changed after the job schema was generated; or TDS_GID/TDS_MASTER missing for MERGING | Click `Generate schema from data model` again, re-map in tMap; make sure TDS_* technical columns are populated |
| tDataprepRun output has no lookup/cluster results and all columns are String | Preparation uses functions incompatible with job execution (Lookup, Text clustering, Make as header, Delete row, cell edits); default output types are String | Move those steps into the job (tMap join, tMatchGroup) and keep the preparation to row-level functions; set column types after tDataprepRun with tConvertType |
| MDM record saves fine via tMDMBulkLoad but violates rules | Bulk load to master with `Validate` off bypasses XSD, Schematron and beforeSaving | Load into staging and run `Validate staging`, or load with `Validate` on, or use tMDMOutput for rule-bound trickle feeds |
| MDM annotation ignored (label, FK, hide) | `appinfo source` value misspelled or wrong case (`X_foreignKey`, `X_Label_en`); annotations placed on the type instead of the element | Use the Studio Data Model editor to generate annotations; check exact `X_` spelling in XSD source |
| tMDMDelete / web UI delete fails with FK integrity error | Target record is referenced and `X_FKIntegrity=true` on the referencing element | Delete or re-point referencing records first; or set `X_FKIntegrity_Override` for admin roles; use logical delete |
| MDM database grows fast, UI Journal slow | `UpdateReport` journal and routing orders accumulate for every save | Schedule a purge job (tMDMDelete on `Update` entity / routing order purge); disable update reports for bulk reloads |
| Profiling results differ between SQL and Java engine | Collation/case rules, trailing spaces on CHAR, regex dialect, NULL vs blank differ between DB and JVM | Fix one engine per analysis; use Java engine for cross-DB comparability, SQL for exactness against the DB |
| Semantic-aware analysis shows only built-in types; custom types absent | Talend Dictionary Service not reachable or Studio not synchronized | Configure TDS URL/credentials in Studio preferences and click update; verify TDS/Kafka/MongoDB containers are running on-prem |
| Report generation fails: "table TDQ_... not found" or column mismatch after Studio upgrade | Datamart schema version differs between Studio versions; old HSQLDB/MySQL datamart reused | Point the upgraded Studio at a fresh datamart schema (it creates tables) or apply the Talend-provided migration scripts; keep one datamart per Studio major version |
| Column analysis on a file is greyed out / SQL engine unavailable | File (delimited) connections and `Store data` analyses require the Java engine | Switch `Execution engine` to Java; raise Studio heap in `Talend-Studio.ini` (`-Xmx`) for large files |
| tGenKey import of blocking key refused | Blocking keys import only from VSR match rules saved in the repository | Recreate the key manually or save the rule as VSR |
| tMatchIndexPredict cannot connect to Elasticsearch | Unsupported ES version (7.3 supports up to 6.4.2), authentication required by cluster, or job on Databricks | Use a supported ES version without auth (or a proxy), run on a supported Spark cluster |
| tVerifyEmail returns REJECTED for known-good addresses | `Check with mail server callback` blocked by corporate MTA/greylisting or outbound port 25 closed | Disable callback (use domain/TLD checks only) or route via an allowed SMTP relay; treat REJECTED as "unverified" |

## Sources

https://help.qlik.com/talend/en-US/components/8.0/data-matching/tmatchgroup-standard-properties
https://help.qlik.com/talend/en-US/data-matching/8.0/tmatchgroup-standard-properties
https://help.qlik.com/talend/en-US/data-matching/8.0/matching-two-records
https://help.qlik.com/talend/en-US/components/8.0/data-matching/matching-two-records
https://help.qlik.com/talend/en-US/data-matching/8.0/choosing-metrics-and-defining-matching-rules
https://help.qlik.com/talend/en-US/data-matching/7.3/tmatchgroup-mapreduce-properties-deprecated
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-09/defining-matching-key-with-t-swoosh-algorithm
https://help.qlik.com/talend/en-US/components/8.0/data-privacy/data-masking-functions-in-masking-components
https://help.qlik.com/talend/en-US/components/7.3/data-privacy/data-masking-functions-in-masking-components
https://help.qlik.com/talend/en-US/components/8.0/data-privacy/tdatamasking-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/data-privacy/tdatamasking-properties-for-apache-spark-structured-streaming
https://help.qlik.com/talend/en-US/components/8.0/data-privacy/replace-all
https://help.qlik.com/talend/en-US/components/8.0/phone-number-standardization/tstandardizephonenumber-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/phone-number-standardization/default-columns
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-09/phone-number-statistics
https://help.qlik.com/talend/en-US/components/8.0/validation/validating-data-against-schema
https://community.qlik.com/t5/Talend-Studio/tSchemaComplianceCheck-errorCode-Not-expected-behaviour/m-p/2352296/highlight/true
https://community.qlik.com/t5/Talend-Studio/tSchema-Compliance-Error-Code-missing-in-DI-6-3-1-using/m-p/2232901/highlight/true
https://help.qlik.com/talend/en-US/components/8.0/identification/tgenkey-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/identification/tgenkey-properties-for-apache-spark-batch
https://help.qlik.com/talend/en-US/data-matching/7.3/configuring-key-generation-for-first-pass
https://help.qlik.com/talend/en-US/components/8.0/email-validation/tverifyemail-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/email-validation/tverifyemail-properties-for-apache-spark-batch
https://help.qlik.com/talend/en-US/components/8.0/standardization/tstandardizerow-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/standardization/tstandardizerow-properties-for-apache-spark-batch
https://help.qlik.com/talend/en-US/components/8.0/standardization/tstandardizerow-tstandardizerow-rule-types-standard-component-enterprise-two
https://help.qlik.com/talend/en-US/components/7.3/standardization/tstandardizerow-tlogrow-tfilterrow-textractxmlfield-normalizing-data-using-rules-of-basic-types-standard-component-enterprise-in-this
https://help.qlik.com/talend/en-US/components/7.2/address-standardization/taddressrowcloud-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/address-standardization/taddressrowcloud
https://help.qlik.com/talend/en-US/components/7.3/address-standardization/tbatchaddressrowcloud-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/address-standardization/tbatchaddressrowcloud
https://help.qlik.com/talend/en-US/components/8.0/data-stewardship/tdatastewardshiptaskoutput-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/data-stewardship/tdsoutput
https://help.qlik.com/talend/en-US/components/7.3/data-stewardship/tdatastewardshiptaskinput-standard-properties
https://help.qlik.com/talend/en-US/data-stewardship-user-guide/Cloud/campaigns-and-tasks
https://help.qlik.com/talend/en-US/data-stewardship-user-guide/8.0/campaigns-and-tasks
https://help.qlik.com/talend/en-US/components/8.0/data-preparation/tdatapreprun-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/data-preparation/tdatapreprun-properties-for-apache-spark-batch
https://help.qlik.com/talend/en-US/components/8.0/data-preparation/tdatapreprun-properties-for-apache-spark-streaming
https://help.qlik.com/talend/en-US/components/8.0/data-preparation/tdatapreprun-tfileinputdelimited-tmysqloutput-tmysqloutput-dynamically-selecting-preparation-from-talend-data-preparation-standard-component-enterprise-in
https://help.qlik.com/talend/r/en-US/8.0/data-preparation/tdatapreprun-thdfsconfiguration-tlogrow-ts3configuration-accessing-preparation-from-talend-data-preparation-spark-batch-component-in
https://help.qlik.com/talend/en-US/components/8.0/matching-with-machine-learning/tmatchpairing-matching-on-spark-spark-batch-component
https://help.qlik.com/talend/en-US/components/8.0/matching-with-machine-learning/tmatchpredict
https://help.qlik.com/talend/r/en-US/7.3/data-matching/tmatchmodel
https://help.qlik.com/talend/en-US/components/8.0/data-privacy/tpatternmasking
https://help.qlik.com/talend/en-US/components/7.3/data-privacy/tpatternmasking
https://help.qlik.com/talend/en-US/components/8.0/data-privacy/tdatashuffling-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/data-privacy/tdatashuffling-properties-for-apache-spark-batch
https://help.qlik.com/talend/en-US/components/7.3/data-privacy/tdatashuffling-tdatamasking-tfixedflowinput-tfileoutputexcel-configuring-tdatashuffling-component-standard-component-enterprise
https://help.qlik.com/talend/en-US/components/8.0/continuous-matching/continuous-matching-component
https://help.qlik.com/talend/en-US/components/7.3/continuous-matching/doing-continuous-matching-using-tmatchindexpredict
https://help.qlik.com/talend/en-US/components/7.3/continuous-matching/tmatchindexpredict
https://help.qlik.com/talend/en-US/components/8.0/data-privacy/tdataencrypt-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/data-privacy/tdatadecrypt-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/data-privacy/tdataencrypt-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/fuzzy-matching/tfuzzymatch
https://help.qlik.com/talend/en-US/components/7.3/fuzzy-matching/tfuzzymatch-standard-properties
https://help.qlik.com/talend/en-US/data-matching/7.3/checking-levenshtein-distance-1-or-2-in-first-names
