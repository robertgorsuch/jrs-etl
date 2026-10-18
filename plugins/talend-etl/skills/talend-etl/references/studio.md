# Talend Studio (IDE) reference

> Verification: doc-derived (help.qlik.com / help.talend.com search snippets, Talend GitHub, Maven Central) plus model knowledge. Not exercised against a live Studio/TAC/TMC in this build. Items marked (unverified) are from memory only and should be checked in Studio before relying on exact labels.

Scope: Talend Open Studio for Data Integration (TOS DI, 5.x-8.0.1, EOL 2024-01-31)
through subscription Talend Studio 7.3 / 8.0 (monthly patches R20xx-xx, now
"Qlik Talend Studio"). Covers the IDE only: perspectives, projects/repository,
metadata wizards, designer views, job design semantics, Project Settings,
Preferences, Build/Publish dialogs, test cases, debugging, Feature Manager and
internals. Component parameters live in components-core.md and siblings; build
artifacts and their runtime in deployment-runtime.md / artifact-formats.md;
CommandLine in apis-sdks.md; edition/version history in versions-licensing.md.

## Contents
- [Editions, licenses and perspectives](#editions-licenses-and-perspectives)
- [Login window, workspace and projects](#login-window-workspace-and-projects)
- [Git/SVN remote projects, locking, branches](#gitsvn-remote-projects-locking-branches)
- [Item lifecycle: versions, status, save as, documentation, compare](#item-lifecycle-versions-status-save-as-documentation-compare)
- [Import / Export items](#import--export-items)
- [Repository tree](#repository-tree)
- [Metadata wizards and schema propagation](#metadata-wizards-and-schema-propagation)
- [DB type mapping files](#db-type-mapping-files)
- [Designer: Palette and canvas](#designer-palette-and-canvas)
- [Component view](#component-view)
- [Run view](#run-view)
- [Contexts, Outline, Code viewer, Job view, Problems, Modules, Jobscript](#contexts-outline-code-viewer-job-view-problems-modules-jobscript)
- [Job design concepts](#job-design-concepts)
- [Project Settings](#project-settings)
- [Preferences](#preferences)
- [Studio .ini, JVM, workspace, -clean](#studio-ini-jvm-workspace--clean)
- [Build Job / Build Route / Build Service](#build-job--build-route--build-service)
- [Publish: Cloud, Nexus/Artifactory](#publish-cloud-nexusartifactory)
- [Test cases](#test-cases)
- [Debugging](#debugging)
- [Feature Manager, patches, licenses, custom components](#feature-manager-patches-licenses-custom-components)
- [Studio under the hood](#studio-under-the-hood)
- [Keyboard shortcuts and productivity](#keyboard-shortcuts-and-productivity)
- [Gotchas](#gotchas)
- [Sources](#sources)

## Editions, licenses and perspectives

Studio is one Eclipse RCP binary; the license key (subscription) or the
download flavour (Open Studio) decides which perspectives, repository nodes and
palette families are visible. Switch perspectives with the icons top-right or
`Window > Perspective > Open Perspective > Other...`.

| Perspective | What it is | Exposed by |
|---|---|---|
| Integration | Default. Job Designs (Standard, Big Data Batch/Streaming), Joblets, Routes/Services (if ESB licensed), Contexts, Code, Metadata, Business Models. Big Data has no separate perspective; it adds nodes and palette families to Integration. | All products |
| Profiling | Data Quality analyses (column, table, correlation, match, redundancy), patterns, indicators, rules, DQ Repository tree; Data Explorer perspective (SQL explorer) comes with it | Open Studio for DQ, Data Management Platform, Big Data Platform, Data Fabric, MDM Platform; in 8.0 installed via Feature Manager (DQ not shipped by default) |
| Data Explorer | SQL editor / data browser used by Profiling to drill into analysis results | Same as Profiling |
| Mediation | Camel route designer (Routes, Routelets, Beans, Resources), Talend Runtime launch | Open Studio for ESB, ESB, Data Services Platform, Real-Time Big Data Platform, Data Fabric |
| MDM | Data models, views, triggers, processes, event management, MDM server connection | MDM Platform, Data Fabric |
| Mapping (Talend Data Mapper) | Hierarchical structure/map editor behind tHMap, tHConvertFile; EDI/COBOL/JSON/XML/Avro structures | Data Services Platform, Big Data Platform, Data Fabric (feature in 8.0) |
| Debug | Standard Eclipse Java debug perspective, opened by Run view > Debug Run > Java Debug | All |

Product-to-perspective (7.2 "Licenses and perspectives in Studio" page): DI, Big
Data and ESB licenses give Integration only; Data Management Platform gives
Profiling + Integration; MDM Platform gives MDM + Profiling + Integration. For a
local project the license decides; for a remote project the project type on
TAC/TMC also decides (a plain DI remote project opens Integration only).

Open Studio vs subscription Studio:

| Capability | Open Studio (TOS) | Subscription Talend Studio |
|---|---|---|
| License | Apache 2.0 download per flavour (DI, BD, ESB, DQ, MDM); no key. EOL 2024-01-31 (last 8.0.1) | License key / cloud login at first start; one installer, features unlocked by key |
| Projects | Local only | Local + remote (TAC Git/SVN, Talend Cloud Git) |
| Reference projects, Joblets, Test cases, Dynamic schema, tParallelize/partitioners, CDC, Change-impact (Items relation), Metadata bridge, Publish to Nexus/Cloud, Remote run on JobServer | No | Yes (platform tiers add DQ, TDM, MDM, ESB) |
| Feature Manager / monthly R patches | Limited (component updates only) | Yes |
| Build Job (standalone zip, OSGi), Docker image, Business Models, SQL templates, routines, context groups | Yes | Yes |

Talend Cloud login from Studio: login window > `Manage Connections` > Repository
`Talend Cloud` (7.x: per-region entries such as "Talend Cloud (AWS US)",
"(AWS EU)", "(Azure)"; 8.0: pick region/URL). Authenticate with TMC
user/password (SSO users use a personal access token from TMC > Profile
preferences). The Studio then lists TMC projects (Git repositories registered in
TMC > Management > Projects) and later offers `Publish to Cloud`. Cloud
licenses are validated online; the Studio periodically re-checks the token.

## Login window, workspace and projects

Startup sequence: pick workspace (`-data` / `Talend-Studio*.ini` default
`<studio>/workspace`) -> license (first start) -> login window:

| Login window element | Behaviour |
|---|---|
| `Manage Connections` | Add/edit connections: Name, Description, Repository = `Local` / `Remote` (TAC URL `http://tac:8080/org.talend.administrator`, user/password) / `Talend Cloud`; `Workspace` path per connection |
| Project list | Local: projects in the workspace. Remote: projects the user is authorised for on TAC/TMC (project type must match license) |
| `Create a new project` | Name (letters/digits/underscore; stored upper-case internally in `talend.project`), language Java |
| `Import a demo project` | Ships DI/BD/ESB demos (unverified list per version) |
| `Import an existing project` | From a project folder or an exported project archive (.zip); creates `<workspace>/<PROJECT>/` |
| `Open` | Local: open. Remote: shows branch/tag selection (`Select an existing branch`, `Create a new branch`, tags read-only) then checks out into `<workspace>/<PROJECT>_<branch>` (unverified folder naming) |

Workspace layout (one per connection):

```
<workspace>/
  <PROJECT>/                 one folder per project (remote: per project+branch)
    talend.project           project descriptor (name, language, item version, author)
    process/                 Standard jobs: <Name>_<M>.<m>.item + .properties (+ .screenshot)
    process_mr/ process_storm/ process_spark/ ...  Big Data jobs (version-dependent)
    joblets/ routes/ routelets/ services/ businessProcess/
    context/ code/routines/ code/beans/ code/pigudfs/ sqlPatterns/
    metadata/connections/ metadata/fileDelimited/ ... metadata/genericSchema/
    documentations/ recycle_bin/ (deleted items keep their files, flagged in .properties)
    poms/                    generated Maven poms (code/, jobs/ ...) since 6.x/7.x
  .Java/                     generated project (src/main/java/<project>/<job>_<ver>/*.java, pom.xml)
  .metadata/                 Eclipse workspace metadata; .metadata/.log = Studio log
  .JETEmitters/              compiled javajet templates (safe to delete, regenerated)
```

Item file format and `talend.project` XML are documented in artifact-formats.md.

Migrating a workspace: never copy `.metadata` between Studio versions. Either
(a) `Export items` from the old Studio and `Import items` in the new one, (b)
`Import an existing project` pointing at the old `<workspace>/<PROJECT>` folder
(Studio runs migration tasks and raises the item version), or (c) for remote
projects just log in from the new Studio and pull; TAC/TMC migrates the project
metadata and Studio runs per-item migration tasks on first open (commit them).

Reference projects (subscription): a project can reference other projects whose
items (routines, context groups, metadata, Joblets, Jobs for tRunJob) appear
read-only under a `Referenced projects` node / greyed folders. Configure in
`Project Settings > General > Project References` (TAC: Projects > References;
TMC: project references in the project settings) choosing project + branch.
Referenced routines are compiled into dependent jobs; referenced Jobs can be
called by tRunJob and show up in `Build Job > Items`. Reference chains are
resolved transitively; circular references are refused.

## Git/SVN remote projects, locking, branches

| Topic | Studio behaviour |
|---|---|
| VCS support | 6.x/7.x: SVN and Git via TAC. 8.0: Git only (SVN removed; migrate repositories before upgrading). Talend Cloud: Git only (GitHub, GitLab, Bitbucket, Azure Repos, generic Git over HTTPS/SSH) |
| Branches/tags | Chosen at login. Git: `branches/<name>`, `tags/<name>`; `Create a new branch` from current. In-Studio switch: `File > Switch Project or Branch` (returns to login window). Tags are read-only checkouts |
| Commit model | Git projects: Studio auto-commits each saved item locally (default "Automatic commit" behaviour, configurable in `Preferences > Talend > Repository`/Git section (unverified)) and pushes on demand. Views: `Git Staging` (stage, commit, Compare, Reset), `Git History` (commit log of the project), `Git Repository` (unverified name) |
| Push / Pull | Toolbar Git menu (`Project > Git` / top bar Git icons): `Push`, `Pull`, `Fetch`, `Commit`, `Merge`, `Rebase` (unverified), `History`. Push rejected (non-fast-forward) -> dialog offers to update local repository (pull) then push again |
| Merge / conflicts | Pull with conflicts opens a conflict resolution dialog listing conflicting items; choose `Keep local` / `Use remote` per item (labels approximate). Conflicts are per `.item`/`.properties`; Studio refuses to leave an item half-merged. Never hand-edit a conflicted `.item` outside Studio unless you understand the XML (artifact-formats.md) |
| Locking | Remote projects lock an item when opened for edit (`Preferences > Talend > Repository`: lock mode Automatic / Ask / Manual (unverified exact names)). Lock icon on the item; `Locker` shown in Job view > Main. Others open read-only ("Job is locked by <user>"). Unlock: close the editor, right-click > `Unlock` (own locks), TAC > `Lock administration`/`Locks` page (admin), TMC: project settings (unverified) |
| Change tracking | Modified-not-pushed items are decorated (`>` / `*` prefix) in the Repository tree; `Git Staging > Compare` shows a text diff of the item XML; right-click a Job > `Compare`/`Compare with` on history is version dependent (unverified) |
| Credentials | TAC stores the Git credentials per project; Studio asks on first pull if TAC lets users supply their own (`Use custom Git credentials` in TAC user settings (unverified)). SSH keys: Eclipse `Preferences > General > Network Connections > SSH2` |
| Git ignore | Studio-generated `.gitignore` excludes `.Java`, `.metadata`, `poms/` artefacts (unverified); do not commit `.Java` |

SVN specifics (<= 7.3): same login/branch flow (`trunk`, `branches/`, `tags/`),
no local commit; each save commits to SVN ("Save = commit"). Locks are managed
by TAC, not SVN locks.

## Item lifecycle: versions, status, save as, documentation, compare

| Feature | Where | Detail |
|---|---|---|
| Version `M.m` | Job view > Main > `Version` (`M` / `m` buttons), or right-click item > `Edit properties` | Default `0.1`. Incrementing creates a new `.item`/`.properties` pair; old versions stay on disk and in `Open another version` / `Delete versions`. Build Job lets you choose the version. tRunJob can target `Latest` or a fixed version |
| `Save as` | `File > Save as` on an open Job | Copies the Job under a new name/version; use for forks; dependencies (contexts, metadata) are shared not copied |
| Status | Job view > Main > `Status` | Values come from `Project Settings > Status management` (technical statuses such as DEV/TEST/PROD and documentation statuses, editable code/label lists (defaults unverified)) |
| Properties | Right-click > `Edit properties` | Name, Purpose, Description, Author, Status, Version, Path |
| `Open another version` | Right-click Job | Opens an older version read-only unless you make it current |
| Items relation / impact | Right-click > `Impact Analysis` (subscription, unverified label), `Detect Dependencies` when deleting | Lists Jobs using a metadata/context/routine/Joblet before you change or delete it |
| Compare items | `Git Staging` view > `Compare` (text diff of item XML against HEAD/remote) | No semantic diff of two arbitrary Jobs in Studio; export Jobscript (`Repository > right-click Job > Export Jobscript` (unverified)) or `.item` XML and diff externally |
| Change Items | In remote projects the repository decorates changed items; `Project > Git > Commit` lists them. In 7.x there was a `Change Items` wizard to move items between folders/projects (unverified) | |
| Generate documentation | Right-click Job/folder > `Generate Doc As HTML`; `Documentation` node > `Generated` | HTML with screenshot, component settings, schemas, context values; optional source code (`Preferences > Talend > Documentation > Source code to HTML generation`) and custom CSS (`Use CSS file to generate documentation`). Export: right-click generated doc > `Export documentation` (.zip/.html) |
| Documentation node | Repository > `Documentation` | Attach arbitrary files (`Create documentation`: specs, DDL) to the project; versioned like items |
| Recycle bin | Repository > `Recycle bin` | Deleted items; `Restore` or `Empty recycle bin` (permanent) |

## Import / Export items

| Action | Path | Options |
|---|---|---|
| Export items | Right-click item/folder/root > `Export items` | Target: `Select archive file` (.zip) or `Select root directory`; `Export Dependencies` (adds referenced contexts, metadata, routines, Joblets, child Jobs); `Browse` select tree |
| Import items | Right-click root/folder > `Import items` | Source: `Select root directory` or `Select archive file`; list shows items with version and `Overwrite existing items` check box; errors listed per item (e.g. missing routine, newer item version than Studio supports); items from a newer major version are refused |
| Import from older version | Same dialog | Migration tasks run on import (item XML upgraded); imports from 6.x/7.x into 8.0 are supported, from 5.x partially |
| Export vs Build | `Export items` = design-time XML (.item/.properties + talend.project snippet) for moving between projects/Studios. `Build Job` = compiled runnable artifact (jar + launchers + context .properties) for execution |
| Export project | Login window > project context (`Export`) or TAC | Whole project folder as .zip; import with `Import an existing project` |

The export zip layout (`<PROJECT>/process/..., talend.project`) is in
artifact-formats.md.

## Repository tree

| Node | Contains | Notes |
|---|---|---|
| Business Models | Diagram-only process models (.bpm) with assignment to Jobs | All editions; documentation only |
| Job Designs | `Standard` (DI jobs); `Big Data Batch` (Spark; MapReduce removed in 8.0); `Big Data Streaming` (Spark Streaming; Storm removed in 7.x) | Folders per framework appear only with Big Data license. Create: right-click > `Create Standard Job` / `Create Big Data Batch Job`. Convert: right-click Job > `Edit Big Data Batch properties` / `Convert to ...` (framework change) |
| Joblets | Reusable fragments with input/output triggers (tJobletInput/Output, Trigger input/output) | Subscription. Appear in the Palette under `Joblets` family; inlined at code generation |
| Routes / Routelets / Resources | Camel routes, reusable route pieces, route resource files (xml, properties) | Mediation perspective; see esb-routes-services.md |
| Services | WSDL-first SOAP services: a Service item wraps a WSDL and binds operations to Jobs (tESBProviderRequest/Response) | ESB license |
| Test Cases | Child node under each Job (`Test Cases`) | Subscription; see Test cases |
| Contexts | Context groups (name, variables with type/value per context such as Default/Dev/Prod) | Drag onto a Job or `Contexts view > Select context variables` |
| Code | `Routines` (System folder read-only: Numeric, StringHandling, TalendDate, TalendDataGenerator, TalendString, Relational, Mathematical, DataOperation...; user folders). 8.0 splits `Global Routines` (project-wide, auto-dependency) and `Inner/Custom routines` attached per Job via `Setup routine dependencies` (unverified wording). `Beans` (Java beans for Routes, cBean/cProcessor). `Pig UDFs` (<= 7.3; Pig removed in 8.0) | Routine jars: right-click routine > `Edit Routine Libraries` to attach third-party jars |
| SQL Templates | `Generic`, `Hive`, `MySQL`, `Netezza`, `Oracle`, `ParAccel`, `Teradata`, each `System` (read-only) and `UserDefined` | Used by tELT*/tSQLTemplate* components; templates use `<%=` placeholders bound to component parameters |
| Metadata | `Db Connections`, `SAP Connections`, `Hadoop Cluster` (+ HDFS/HBase/Hive/HCatalog/Oozie children), `NoSQL Connections` (MongoDB, Cassandra, Neo4j, Couchbase), `File delimited`, `File positional`, `File regex`, `File xml`, `File Excel`, `File ldif`, `File JSON`, `LDAP`, `Salesforce`, `Web Service` (WSDL), `FTP`, `Generic schemas`, `Azure Storage`, `Google Drive`, `Marketo`, `Snowflake`, `Talend MDM`, `UN/EDIFACT` and `Copybook`/Data Mapper structures (TDM), `Validation Rules`, `Rules` (Drools, platform), `Survivorship rules` (DQ). 8.0 adds TCK-based connection wizards (e.g. `Snowflake`, `Kafka` (unverified), `Workday`) | Each connection holds child `Table schemas`/`Queries` (saved SQL from SQL Builder) |
| Documentation | Generated HTML and user-attached docs | |
| Recycle bin | Deleted items | |
| Referenced projects | Read-only tree of each referenced project | Subscription |

Filtering: Repository toolbar funnel (`Filter settings`: by name regex, status,
author, hide Standard/Big Data etc.); `Link with editor`. Big repositories:
collapse `Metadata` and `Code` nodes, use the funnel.

## Metadata wizards and schema propagation

Common wizard structure: Step 1 `Name`, `Purpose`, `Description`, `Status`,
`Path` -> Step 2 connection details with `Check`/`Test connection` -> Step 3
retrieve or guess schema -> Step 4 edit schema (`Guess`, `Retrieve Schema`,
`Refresh Preview`). Every connection wizard has `Export as context` which turns
host/port/user/password into a context group and rewires the connection to
`context.*` variables.

| Wizard | Key fields | Schema step |
|---|---|---|
| Db Connection | `DB Type` (MySQL, Oracle (SID/Service Name/OCI/RAC), MSSQL (JTDS/MS driver), PostgreSQL, DB2, Teradata, Snowflake, Redshift, Hive, Impala, Vertica, SAP HANA, JDBC generic ...), `Db Version`, `Login`, `Password`, `Server`, `Port`, `DataBase`, `Additional parameters`, `String of Connection` (auto), `Mapping file` (type mapping) | Right-click connection > `Retrieve Schema`: filter by name/type (table/view/synonym), select tables -> `Table schemas` children. `Retrieve Schema` again re-reads and shows `Modification` diff |
| File delimited / positional / regex | File path, `Encoding`, `Field Separator`, `Row Separator`, `CSV options` (escape/text enclosure), `Header`/`Footer`/`Limit`, `Skip empty rows`, preview | `Guess` infers types from preview rows (often all `String`; fix lengths/types by hand); `Retrieve Schema` re-reads header |
| File xml / JSON | Input vs Output mode; `Loop XPath query` (loop element) + `Fields to extract` (relative XPath/JSONPath); for Output: link schema columns to nodes | Schema derived from mapped nodes |
| File Excel | `.xls/.xlsx`, `Read excel2007 file format(xlsx)`, `Generation mode` (Memory-consuming vs Less memory), sheet list / `All sheets`, header/footer/first column | Guess from sheet |
| File ldif / LDAP | LDIF: attributes list; LDAP: host, port, protocol (LDAP/LDAPS/TLS), auth, `Base DN`, filter, attributes | Retrieve attributes |
| Salesforce | Login type `Basic`/`OAuth`, user/password+token, endpoint URL, API version, proxy | Retrieve modules (objects) as schemas |
| Web Service (WSDL) | WSDL URL/file, port/operation, input/output mapping | Request/response schema |
| FTP | Host, port, user, password, `Connection mode` (Active/Passive), `SFTP`/`FTPS` options, proxy | No schema |
| Hadoop Cluster | `Import from Ambari/Cloudera Manager` or manual: distribution/version, NameNode URI, Resource Manager, scheduler, Kerberos (`Use kerberos authentication`, keytab), user name; children HDFS/Hive/HBase/HCatalog | Hive tables via `Retrieve Schema` (big-data-spark.md) |
| NoSQL | MongoDB (replica set, auth DB, SSL), Cassandra (API/CQL version), Neo4j, Couchbase | Collection schema retrieval (MongoDB sampling) |
| Generic schemas | Name only, then `Edit schema`; `Import from CSV` (unverified exact label; CSV describing columns) / `Import from XML` (schema XML exported from any `Edit schema` dialog via its export button) | Reusable column lists for any component |
| SAP | SAP connection (ASHOST/SYSNR/client/user/language; JCo3 jars via Modules) | BAPI/Table/IDoc metadata |
| Azure Storage / Google Drive / Marketo / Snowflake | Account/key, OAuth or service account, endpoint, role/warehouse | Table/object retrieval where applicable |

Built-In vs Repository in components:

| Setting | Built-In | Repository |
|---|---|---|
| `Property Type` | Connection values typed in the component (editable, may use `context.*`) | Points to a Metadata item; fields read-only; changing the metadata offers propagation; `Built-In` button copies the values locally and breaks the link |
| `Schema` | Local columns, editable via `Edit schema` (`...`) | Points to a metadata schema (`Repository: <connection> - <table>`); read-only in the component; `Edit schema` offers to switch to Built-In |
| `Guess schema` | Button on tDBInput and other inputs (file inputs: version dependent (unverified)); executes/inspects the source to build columns | n/a |
| `Guess Query` | tDBInput/tELTInput: builds `SELECT col1, col2 FROM table` from schema + `Table Name` with DB-specific quoting | Query stored as `Repository` query possible (SQL Builder) |
| `Sync columns` | tMap, output components: copies the incoming link schema | |

Propagation: on `Finish` in a wizard after a schema/connection change, Studio
shows `Modification` / `Update Detection` listing every Job, Joblet and test
case that uses the item with check boxes; confirm to rewrite their `.item`
files (they must not be locked by others). You can also right-click a Metadata
connection > `Update all jobs/joblets using this connection` (unverified
wording; 7.x had `Propagate the changes` in the dialog). Jobs whose components
were switched to Built-In are not updated. tMap does not auto-adapt expressions
to removed/renamed columns: open the map editor and fix red cells.

SQL Builder: `...` next to `Query` opens the SQL Builder (tables tree of the
repository connection, `Generate select statement`, run query to preview,
`Save as repository query`). Requires a repository connection.

## DB type mapping files

Java-to-DB type mapping used by `Edit schema` (`DB Type`/`Length`/`Precision`
columns), `Retrieve Schema` and tCreateTable/tDBOutput DDL generation.

- Edit in `Window > Preferences > Talend > Specific Settings > Metadata of
  TalendType` (`Mapping files` list: `mapping_mysql.xml`, `mapping_oracle.xml`,
  `mapping_mssql.xml`, `mapping_postgres.xml`, `mapping_snowflake.xml`, ...).
  Each has `Edit`/`Import`/`Export`.
- File structure (artifact-formats.md has a full example): `<dbms product=
  "MYSQL" id="mysql_id" label="Mapping Mysql" default="true">` containing
  `<dbTypes>` (`<dbType type="VARCHAR" defaultLength="255" .../>`),
  `<language name="java">` with `<talendToDbTypes>` (`<talendType type=
  "id_String"><dbType type="VARCHAR" default="true"/>...`) and
  `<dbToTalendTypes>` (`<dbType type="INT"><talendType type="id_Integer"
  default="true"/>`).
- Talend types are `id_String`, `id_Integer`, `id_Long`, `id_Float`,
  `id_Double`, `id_BigDecimal`, `id_Boolean`, `id_Date`, `id_byte[]`,
  `id_Character`, `id_Short`, `id_Byte`, `id_Object`, `id_List`, `id_Document`
  (XML), `id_Dynamic` (subscription).
- A connection's `Mapping file` field (Db Connection wizard step 2, or
  component `Mapping` in Advanced settings for generic JDBC) selects which
  mapping applies. Generic JDBC defaults to `mapping_mysql.xml`-like generic
  mapping (`Mapping Generic`) unless changed.
- Edited mapping files are stored in the workspace/user area and override the
  copies shipped in the `org.talend.core.runtime` plugin (location unverified).

## Designer: Palette and canvas

Palette (right side, `Window > Show View > Talend > Palette` if closed):

| Element | Detail |
|---|---|
| Families | Big Data, Business, Business Intelligence, Cloud, Custom Code, Data Quality, Databases (sub-folders per vendor; 7.x+ also generic `DB` components with `Database` list), DotNET, ELT, ESB, File, Internet, Logs & Errors, Misc, Orchestration, Processing, System, Talend MDM, Technical, Unstructured, XML, plus `Joblets`, `Routelets` and user-component families |
| Search | Text field at the top of the Palette (name or description); clear with the x |
| Favorites | Right-click component > `Add To Favorite`; Palette toolbar `Show Favorites` / `Show Standard`. Hide families: `Palette Settings` (Preferences or Project Settings > Palette Settings) |
| Quick insert | Click an empty canvas spot and start typing: a filtered component list appears; `Enter` drops it. Dropping a component on a row link splices it in |
| Metadata drag | Drag a repository table/file schema onto the canvas -> choose input/output component type; Property/Schema set to Repository |
| Note tool | Palette/canvas toolbar `Note` (free text, colour, font); also `Documentation` tab per component |
| Canvas toolbar | Zoom, `Alignment`, `Show/Hide subjobs`, `Collapse/Expand subjob`, `Grid`, export image (`Export to image` right-click canvas) |
| Tabs under canvas | `Designer` / `Code` (generated Java, read-only; breakpoints allowed in Java Debug) and `Jobscript` (version dependent) |

Component colouring: start component of each subjob gets a green title bar;
subjob background blue (rename/colour via subjob title right-click > `Show/Hide
subjob title`, `Subjob properties`); deactivated components greyed; errors
shown by a red x badge (hover for message) and warnings by yellow triangle.

## Component view

Opened by selecting a component (`Window > Show View > Talend > Component`,
F2 toggles in some versions (unverified)).

| Tab | Contents |
|---|---|
| Basic settings | Mandatory parameters: Property Type, connection, Schema (`Edit schema`, `Sync columns`), table/file, query, `Die on error`, etc. Fields are Java expressions ("literal" strings are quoted) unless typed as list/check |
| Advanced settings | Optional/performance parameters (`tStatCatcher Statistics`, batch sizes, commit every, encoding, additional JDBC parameters, `Enable parallel execution` on outputs, log4j level) |
| Dynamic settings | Make a check box/list parameter runtime-driven: `+` then choose the parameter (e.g. `Die on error`, `Use existing connection`) and type a Java boolean/expression such as `context.dieOnError`. The Basic field becomes read-only with a dynamic marker |
| View | `Label format` (default `__UNIQUE_NAME__`), `Hint format` (tooltip), `Connection format`; variables: `__UNIQUE_NAME__`, `__COMPONENT_NAME__`, and any parameter name of the component in uppercase such as `__TABLE__`, `__FILENAME__`, `__QUERY__` (list varies per component). `Show hint` check |
| Documentation | `Comment` free text; `Show Information` check displays a `i` badge with the comment; comments appear in generated HTML documentation |
| Validation Rules | Attach a repository Validation rule to the flow (subscription) |

Field helpers: `...` opens editors (Schema editor, Expression Builder, SQL
Builder); `Ctrl+Space` in any text field lists `context.*`,
`globalMap.get("...")` keys of upstream components and routines; red-underlined
field = compile error in that expression; a field whose value starts with
`context.` is shown with a different icon when driven from a context variable.

## Run view

`Window > Show View > Talend > Run (Job <name>)`.

| Tab | Controls |
|---|---|
| Basic Run | `Run` (F6), `Kill`, `Clear`, `Context` combo (which context to execute), console with `Line limit`, `Wrap`. Execution status line shows `Job <name> ended at ... [Exit code = 0]` |
| Debug Run | `Traces Debug` (data viewer on each row link, `Next Breakpoint`, `Next Row`, `Pause`), `Java Debug` (switches to Debug perspective, Eclipse debugger attached to the generated code) |
| Advanced settings | `Statistics` (row counts and throughput shown on links while running), `Exec time` (per-component time), `Save Job before execution`, `Clear before run`, `JVM Setting > Use specific JVM arguments` (`-Xms256M -Xmx1024M`, `-Dfile.encoding=UTF-8`, `-Djavax.net.ssl.trustStore=...`), `Enable Log4j in components` (version dependent), `Use project settings` |
| Target Exec | `Local` (Studio JVM) or a remote JobServer defined in `Preferences > Talend > Run/Debug > Remote` (host, command port 8000, file transfer port 8001, monitoring port 8888, user/password). The Job is built, shipped and run on the JobServer with console/statistics streamed back. 8.0 TMC: run on a Remote Engine from Studio is not available; use Publish to Cloud then run in TMC |
| Memory Run | 5.x-7.x: live JVM heap/thread graph of the running Job (`Preferences > Talend > Performance` to enable) (unverified in 8.0) |

Run console is also where `tLogRow`, `System.out.println`, log4j appender
`CONSOLE` and uncaught exception stack traces appear. `Statistics` and `Exec
time` inject tFlowMeter-style counters and slow large jobs; turn them off for
timing tests.

## Contexts, Outline, Code viewer, Job view, Problems, Modules, Jobscript

| View | Purpose / key elements |
|---|---|
| Contexts (Job <name>) | `Variables` tab: Name, Type, Comment, `Prompt?`, per-context Value columns; `+`/`-`, `Select context variables` (import from a repository group, keeps the link: group changes propagate, variables greyed), `Default context` combo. `Values` tab (older versions) lists context names (`Default`, add `Dev`, `Prod`...). Variables referenced as `context.<name>` (typed getters, e.g. `context.port` is `Integer`) |
| Outline | Tree of components with their exported globalMap variables (`NB_LINE`, `ERROR_MESSAGE`, `CURRENT_FILE`, `QUERY` ...). Drag a variable into a field to insert `((Integer)globalMap.get("tFileInputDelimited_1_NB_LINE"))` |
| Code Viewer | Read-only generated Java of the selected component (helps understand `Die on error`, connection handling) |
| Job (Job <name>) | `Main`: Name, Purpose, Description, Author, Locker, Version (M/m), Status, Creation/Modification. `Extra`: `Multi thread execution`, `Implicit tContextLoad` (From File / From Database, `Print operations`, `Disable warnings`, `Die on error`, query condition), `Use Project Settings`. `Stats & Logs`: `Use statistics (tStatCatcher)`, `Use logs (tLogCatcher)`, `Use volumetrics (tFlowMeterCatcher)`, `On Console`, `On Files` (file path per type), `On Databases` (connection + table names), `Catch components statistics`, `Catch runtime errors`, `Catch user errors`, `Catch user warnings`, `Use Project Settings`. `Version`: per-version history list (unverified in 8.0) |
| Problems | Compile errors/warnings of the generated code mapped to component/field; double-click jumps to the component. Red x in Repository tree = item has errors |
| Modules | All third-party jars required by components in the project/opened Job: `Status` (installed / not installed), `Module`, `Context`/`Required by`, `Jar name`, `Maven URI` (e.g. `mvn:org.talend.libraries/ojdbc8/6.0.0`), `License` (click to accept). `Install external module` (upload a local jar: Studio copies it to the local Maven repository under `org.talend.libraries:<name>:6.0.0` or the declared Maven URI) and `Download` (fetch from Talend's module update site when the license allows). `Show only not installed` filter. Red x on a component = missing module |
| Jobscript (`Component Jobscript` / `Jobscript`) | Shows the Jobscript (text DSL) for the selected component or whole Job; Jobscript can be edited and converted back (`Repository > right-click Job > Generate Jobscript` / `Convert Jobscript to Job` (unverified wording)). Format in artifact-formats.md |
| Error Log (Eclipse) | `Window > Show View > General > Error Log` = `.metadata/.log` with filters; first place to look when Studio misbehaves |

## Job design concepts

Subjobs and start components

- A subjob is a connected set of components linked by row connections; it has
  one start component (first one dropped or the one with no incoming row). All
  components of a subjob are generated into one Java method and run as one
  unit; `OnSubjobOk/Error` fires once the whole subjob ends.
- Independent subjobs with no trigger between them run sequentially in canvas
  creation order (not position) unless `Multi thread execution` is on.

Row connections (right-click component > `Row` > type, or drag from the
component's right edge):

| Row type | From | Semantics |
|---|---|---|
| Main | Any flow component | Primary data flow; one per output except multi-output components |
| Lookup | Second+ input into tMap, tJoin | Loaded before main (or per row with `Reload at each row`); drawn dashed with a key icon |
| Reject | Components with `Die on error` unchecked (tDBOutput, tFileInputDelimited...) | Rows failing with `errorCode`, `errorMessage` columns added |
| ErrorReject | tDBOutput, tSchemaComplianceCheck, tMap (`Die on error` off / `Catch output reject`) | Component-specific error flow |
| Output (named) | tMap, tMultiOutput, tXMLMap | One link per output table; names come from the map editor |
| Filter / Reject | tFilterRow, tFilterColumns | Matching vs rejected |
| Uniques / Duplicates | tUniqRow | Two outputs |
| Iterate | tFileList, tFlowToIterate, tLoop, tForeach, tDBInput (`Iterate` not available), tMsgBox | Dashed link carrying a loop context (globalMap variables such as `tFileList_1_CURRENT_FILEPATH`), one iteration = one start of the downstream subjob; cannot connect to a Main-only component |
| Combine | Big Data streaming/batch merges (version dependent) | |

Trigger (subjob/component) links:

| Trigger | Fires when | Notes |
|---|---|---|
| OnSubjobOk | Whole source subjob finished without error | Most common sequencing link; source must be the start component |
| OnSubjobError | Source subjob threw / `Die on error` | Runs error handling then job exit code 1 unless handled |
| OnComponentOk | The source component (not subjob) finished | Allowed from non-start components; fires before the rest of the subjob completes |
| OnComponentError | The source component errored | |
| Run if | Source component ends; link `Condition` (Component view of the link) is a Java boolean, e.g. `((Integer)globalMap.get("tFileInputDelimited_1_NB_LINE")) > 0` or `context.loadFlag.equals("Y")` | Evaluated when OnComponentOk would fire; multiple Run if links can be true at once |
| Synchronize (tParallelize) | After parallel subjobs end | tParallelize `Synchronize` output (subscription) |
| Trigger input/output (Joblets) | | |

Link ordering: when a component has several trigger or Iterate links, Studio
numbers them (badge on the link); execution follows the number. Change order
via right-click on the source component > ordering entry (label differs:
`Set the order of connections` / drag in the dialog (unverified)); an
`OnSubjobOk` chain is the explicit alternative.

Parallelism

| Mechanism | Where | Notes |
|---|---|---|
| `Multi thread execution` | Job view > Extra | Starts every independent subjob (no incoming trigger) in its own thread; use with care for connections shared via tDBConnection |
| Parallel Iterate | Select an Iterate link > Basic settings > `Enable parallel execution`, `Number of Parallel executions` (expression, e.g. `4` or `context.threads`) | Each iteration runs the downstream subjob in a thread pool; globalMap collisions require `tFlowToIterate` variables read immediately. Not available on Big Data jobs |
| tParallelize / tPartitioner / tCollector / tRecollector / tDepartitioner | Orchestration palette (subscription) | Subjob parallelisation and row-level partitioning; see orchestration-logging.md |
| `Enable parallel execution` on outputs | tDBOutput Advanced settings (subscription) | Parallel insert threads |
| tRunJob `Use an independent process to run subJob` | Child in separate JVM | Memory isolation |

Implicit context load (Job view > Extra or Project Settings > Job Settings):
`Implicit tContextLoad` reads `key=value` or `key;value` pairs `From File`
(`File Name`, `Field Separator`) or `From Database` (connection, `Table Name`,
`Query Condition` e.g. `"env='PROD'"`) at job start, before any component, and
overrides context defaults. Options `Print operations` (log each assignment),
`Disable warnings`, `Die on error`. Equivalent to a leading tContextLoad but
without editing every Job; prefer repository context groups + `--context_param`
for build artifacts (deployment-runtime.md).

Stats & logs (Job view > Stats & Logs or Project Settings): adds implicit
tStatCatcher/tLogCatcher/tFlowMeterCatcher consumers writing to console, files
(one file per catcher) or a database (tables auto-created, same layout as the
explicit components; these feed the Activity Monitoring Console). `Catch
runtime errors` / `Catch user errors` (tDie) / `Catch user warnings` (tWarn) /
`Catch components statistics` select what tLogCatcher/tStatCatcher record.
Component-level `tStatCatcher Statistics` check boxes (Advanced settings) are
what `Catch components statistics` enables globally.

`Use Project Settings` (check box on each Job view tab): the Job follows the
project-wide value; untick to override per Job. Project Settings > Job Settings
has `Use project settings when create a new job` for Implicit Context Load and
Stats & Logs, plus an `Apply` dialog to push the project values onto selected
existing Jobs.

## Project Settings

`File > Edit Project Properties` or toolbar `Project Settings` icon.

| Node | Settings |
|---|---|
| General | Name, Description, Technical status; `Project References` (reference projects + branch, subscription); `Language` (Java) |
| Build | `Build > Maven`: pom templates for `Project`, `Code` (routines), `Standalone Job`, `OSGI Bundle`, `Microservice`/`Docker` (7.3+), each `Default` or custom text; `Build > Java version` / `Enable Java 17 compatibility` (R2024-xx+, needed to build/run Jobs on Java 17 locally); `Build > Export` defaults (shell launcher, context scripts, `Add Maven script`) (unverified grouping); `Build > Docker` (default image base, maven plugin options) |
| Design | `Palette Settings` (families/components hidden for the project), `Component Settings`/`Default values` (project defaults for some component parameters, e.g. `tFileInputDelimited` encoding) (unverified), `Designer` display options |
| Job Settings | `Implicit Context Load` and `Stats & Logs` project defaults (same fields as the Job view), `Use project settings when create a new job`, `Apply` to existing Jobs via a picker |
| Log4j | `Activate log4j in components` (default on since 7.x), log level (`Standard` level), log4j2.xml template editor (7.x+: log4j2; 6.x: log4j 1.x); template is copied into each build |
| Maven | `Maven > Settings`: use default `~/.m2/settings.xml` or custom; `Maven > Repository` behaviour (7.3+); shows the local repository path used by Studio |
| Security | `Hide passwords` in Studio (mask in Component view) and `Encrypt passwords`/`Store passwords encrypted in items` options (labels approximate); 8.0 uses the `enc:` encryption format in `.item` files (artifact-formats.md) |
| Stats & Logs | (under Job Settings) see above |
| Status management | Two editable lists: technical statuses (code + label) and documentation statuses; drives the `Status` combo of every item |
| Version management | Mass version bump: select items/folders, choose `Major`/`Minor`/explicit version, `Apply`; `Fix tRunJob versions`/`Update child job versions` (unverified) to re-point parents |
| Code / Routines dependencies | `Setup routine dependencies` defaults: whether all user routines are added to every Job (`Add all user routines to job dependencies by default`), global vs custom routines (8.0) |
| Metadata bridge | Enable/configure Talend Metadata Bridge (MIMB, platform license) import/export of metadata from other tools (ERwin, Informatica, PowerDesigner...) into `Metadata` and `Business Models` |
| Palette Settings | Also at project level (see Design) |
| Deployment / Artifact repository | For remote TAC projects the Nexus/Artifactory settings are inherited from TAC; local: `Preferences > Talend > Artifact Repository` |

## Preferences

`Window > Preferences`. Talend-specific nodes under `Talend`; Eclipse nodes
(`General`, `Java`, `Maven`) also matter.

| Node | Key settings |
|---|---|
| Talend (root) | `Java Interpreter` (path to `java`/`java.exe` used to compile and run Jobs locally; must be a JDK, major version must match `Build > Java version`), `Studio temp folder`, `Default language` (Java), `Automatically generate code on save`/`Preview code` behaviour (unverified), `Enable Java 17 compatibility` in some patches |
| Components | `User components folder` (javajet custom components; Palette reloads on restart or `Preferences > Apply`), `Components Update site` / `Talend Exchange` settings (<= 7.3), `Default components folder`, data viewer row limit (`Row limit for Traces/Data viewer`) |
| Performance | `Deactivate automatic update of schema` (skip propagation prompts), `Check only the last version when updating jobs or joblets`, `Propagate add/delete variable changes in repository Contexts`, `Add all user routines to job dependencies by default`, `Generate code when opening the job`, memory/`Memory Run` enable |
| Run/Debug (Debug and Job execution) | `Job Run VM arguments` (`-Xms256M -Xmx1024M` default) applied when `Use specific JVM arguments` is on, `Remote` JobServers list (name, host, port 8000/8001/8888, credentials), console encoding, `Job script execution` logging |
| Exchange | Talend Exchange account and `Check for component updates on startup` (deprecated 7.x, removed 8.0) |
| Code Generation / Designer | Auto-update of components after library changes, `Show component hint by default`, label fonts, `Automatic layout`, zoom (names approximate) |
| Documentation | `Source code to HTML generation` (include generated Java in HTML docs), `Use CSS file to generate documentation` + `CSS file` |
| Palette Settings | Hide/show component families and components in the Palette (user level) |
| Repository | Lock behaviour on open (automatic/manual), `Checkout/Update on startup` (SVN), Git `Automatic commit`/pull on open (unverified), `Refresh` interval |
| SQL Builder | Default behaviour: `Add quotes when you generate SQL statement`, `Enable check queries in the database components` |
| Specific Settings | `Metadata of TalendType` (mapping files), `Default Type and Length` per DB (e.g. Oracle `VARCHAR2(50)`), `Default type for Dynamic column` |
| Usage Data Collector | Telemetry opt-in/out |
| Import/Export | `Export dependencies by default`, exported item folder behaviour |
| Artifact Repository (Talend > Artifact Repository / Nexus) | Type (`Nexus 2`, `Nexus 3`, `Artifactory`), URL, user, password, `Release`/`Snapshot` repositories, `Custom libraries` repositories (`talend-custom-libs-release`/`-snapshot`) |
| General > Network Connections (Eclipse) | `Active Provider` Native/Manual/Direct; manual HTTP/HTTPS/SOCKS proxy host, port, auth, `Proxy bypass`; used by Feature Manager, module downloads, Git over HTTPS, Talend Cloud login. For Jobs run from Studio set `-Dhttp.proxyHost=...` in JVM arguments instead |
| General > Network Connections > SSH2 | Private keys / known hosts for Git over SSH |
| Java > Installed JREs / Compiler | Eclipse JDK list; `Compiler compliance level` is managed by Studio per `Build > Java version`; do not hand-edit |
| Maven > User Settings | `settings.xml` used by Studio's embedded Maven (mirrors, proxies, offline); `Maven > Offline` to stop remote resolution attempts |

## Studio .ini, JVM, workspace, -clean

Launcher files: `Talend-Studio-win-x86_64.exe` + `Talend-Studio-win-x86_64.ini`,
`Talend-Studio-linux-gtk-x86_64` + `.ini` (also `Talend-Studio-gtk-aarch64.ini`),
`Talend-Studio-macosx-cocoa.app` + `.ini` (TOS: `TOS_DI-win-x86_64.ini` etc.).

```
-vm
C:/jdk-17/bin/javaw.exe            # optional, must precede -vmargs; else PATH/JAVA_HOME java is used
-data
C:/talend/workspace                 # optional workspace override (else prompt / default <studio>/workspace)
-clean                              # optional: rebuild OSGi bundle cache (slow first start; use after patches / odd UI)
-vmargs
-Xms512m
-Xmx1536m                           # raise to 4096m+ for large projects; docs suggest -Xms1024m -Xmx4096m on an 8 GB box
-XX:MaxMetaspaceSize=512m           # Java 8+; replaces the historic -XX:MaxPermSize=512m still present in some templates
-Dfile.encoding=UTF-8
-Dosgi.requiredJavaVersion=11       # 8.0 initial; 17 from R2024-05 repackaged Studio
-Duser.timezone=UTC                 # optional
-Dhttps.proxyHost=proxy -Dhttps.proxyPort=8080   # optional Studio-side proxy
-Dtalend.studio.p2.base=file:///opt/updates/base      # optional local update repository (unverified property names)
-Dtalend.studio.p2.update=file:///opt/updates/patches
```

Defaults shipped in 8.0 ini are small (`-Xms64m -Xmx768m` historically); raise
them first when Studio is slow or throws `OutOfMemoryError`/`GC overhead`. The
`.ini` affects Studio only; Job memory is `Run view > Advanced settings > JVM
Setting` or `Preferences > Talend > Run/Debug`.

Java requirements: 7.3 Studio runs on Java 8 (11 supported later); 8.0 GA
requires Java 11 to start; Java 17 supported "with limitations" from monthly
patch R2023-10; from R2024-05 (repackaged 8.0.1 R2024-05 download) Java 17 is
the only supported JVM to start Studio and Java 11 works only up to R2024-04.
Jobs can still be built for Java 8/11 by pointing `Java Interpreter` at that
JDK and setting the project `Java version`; Java 17 Jobs need `Enable Java 17
compatibility` in Project Settings. Qlik announced that during 2025 Studio
would require Java 17 to build and run all artifacts. OpenJDK (Zulu, Temurin,
Amazon Corretto) and Oracle JDK are supported; JRE alone is not enough for code
compilation. Details in versions-licensing.md.

Workspace switching: `File > Switch Workspace` (unverified in 8.0; usually via
login window `Manage Connections > Workspace`). Keep the workspace path short,
ASCII, no spaces, and outside synced folders (OneDrive/Dropbox corrupt
`.metadata`). Windows path length (260) bites in `.Java/target` with long Job
names.

## Build Job / Build Route / Build Service

Right-click Job > `Build Job` (Routes: `Build Route`; Services: `Build
Service`; Joblets cannot be built). Dialog fields:

| Field | Values / meaning |
|---|---|
| `To archive file` | Output `.zip` path (`<Job>_<version>.zip`) |
| `Select the Job version` | Which M.m to build |
| `Build Type` | `Standalone Job` (default), `OSGI Bundle For ESB` (jar for Talend Runtime/Karaf; Jobs with tESB*/tREST* components; label `Talend Runtime (OSGI)` in recent docs), `Docker Image`, `Microservice (Spring Boot)` (Routes and Data Service Jobs: executable jar with embedded Camel/CXF; 7.1+). There is no test-container build type: test cases run through Maven (see Test cases) |
| `Extract the zip file` | Also unpack into the target directory |
| `Shell launcher` | `All` (.sh + .bat), `Unix` (.sh), `Windows` (.bat); 8.0 adds `Add Maven script`/`Add .ps1 launcher` in some patches (unverified) |
| `Context scripts` | Export `contexts/<Context>.properties` for the selected contexts; `Apply to children` writes child-job contexts too; `Only export the default context` (older label) |
| `Log4j level` / `Log4j`-related | Override level baked into `log4j2.xml` |
| `Items` | Include the design items (`.item`, `.properties`) in the zip; `Export Dependencies`/`Include child jobs` (unverified) |
| `Source files` / `Java sources` | Include generated `.java` sources |
| `Execute as script` / `Exec as script` | (unverified; some versions) generate a launcher that runs the job class via `java -cp` built from the lib folder vs. a classpath jar |
| `Java version` | Target Java for compilation (8/11/17) when the license/patch exposes it; otherwise taken from Project Settings |
| `Build with Maven`/`Add Maven script` | Include `pom.xml` and settings so the zip can be rebuilt with `mvn` |

Docker Image build type (feature `Build Docker image` installed via Feature
Manager in 8.0; uses the Jib maven plugin, no local Docker daemon needed when
pushing to a registry; 7.x used fabric8/docker-maven-plugin with a Docker host):

| Field | Meaning |
|---|---|
| `Image name` | default `<project>/<job>` lowercase |
| `Image tag` | default Job version (`0.1`) or `latest` |
| `Docker host` | `Local` (needs Docker daemon / Docker Desktop) or `Remote` (`tcp://host:2375`, TLS cert path) |
| `Registry` | `Registry host`, `Username`, `Password`, `Push image` |
| `Additional properties` | Base image override, JVM args (`-Xmx`) etc. (e.g. `docker.baseImage`) |

Resulting image runs `<job>_run.sh`; context params via `--context_param`
args or environment (deployment-runtime.md).

`Build Route` types: `OSGI Bundle For ESB` (Karaf feature/kar), `Microservice
(Spring Boot)`, `Docker Image`. `Build Service`: builds the WSDL-first service
and bound Jobs as one OSGi bundle/kar. See esb-routes-services.md.

Export items vs Build Job: see Import / Export items. The build runs Maven
(`mvn package` on `.Java/pom.xml` with per-job poms) using the Studio's local
repository; failures surface in the dialog log and `.metadata/.log`. Same
mechanism is driven headlessly by CI Builder (deployment-runtime.md).

## Publish: Cloud, Nexus/Artifactory

| Action | Where | Fields |
|---|---|---|
| `Publish` (to artifact repository) | Right-click Job/Route/Service > `Publish` (feature `Publish to artifact repository` in 8.0) | Repository from `Preferences > Talend > Artifact Repository` or TAC; `Build Type` (Standalone/OSGi/Microservice/Docker); `Publish as Snapshot` (version `0.1.0-SNAPSHOT` to snapshots repo) vs release (`0.1.0` to releases); `Group ID` default `org.example.<project>` (editable per Job), `Artifact ID` = Job name, `Version` derived from M.m plus `.0`. TAC then references the artifact when creating a task (`Publisher`/Nexus task) |
| `Publish to Cloud` | Right-click Job/Route/Data Service > `Publish to Cloud` (Studio logged in with a Talend Cloud connection) | `Workspace` (environment/workspace in TMC), `Artifact type` (Standard Job / Route / Data Service / Big Data), `Build type`, `Publish as new version` vs overwrite, optional Docker/Java options. Creates/updates the artifact in TMC > Management > Artifacts; the publisher then creates a task/plan for a Cloud or Remote Engine (deployment-runtime.md). Requires `Publish to Cloud` feature and TMC role rights |
| `Deploy to Cloud` shortcut | 8.0 Studio offers `Publish to Cloud` only; task creation happens in TMC or via TMC API (apis-sdks.md) |
| `Export job as Test Container` | Not a build type; CI Builder with `-Dmaven.test.skip=false` / `mvn test` runs test cases. Studio 7.x offered `Export Job as Test container` in some Build dialogs for Nexus test containers (unverified) |

## Test cases

Subscription feature (`Test Cases` node under each Job).

Create: right-click a component (or selected subjob) in the Job > `Create Test
Case` -> `Name`, `Purpose`, `Description`, keep `Create test skeleton`
(default). Studio generates a test Job under `Test Cases` containing:

```
tFileInputDelimited (reads context.INPUT)            <- input instance file
   -> [tested components copied as a test "instance" of the subjob]
   -> tCreateTemporaryFile + tFileOutputDelimited (temp result)
tFileCompare (temp result vs context.REFERENCE) -> tAssert (status OK/Fail)
```

- The tested piece is shown as a boxed instance; its components mirror the
  parent Job and are refreshed from it (`Test Case view > Update` (unverified)).
- `Test Case` view (`Window > Show View > Talend > Test Case`): `Instances`
  table (Default plus added ones) with a data set per instance: `Input` and
  `Reference` file paths (and extra inputs if the subjob has several). Each
  instance maps to context values of a `Test` context group auto-created in the
  Contexts view.
- Running: Run view of the test case (`Run`/F6) executes the selected instance;
  console prints `tAssert` result; `Run all instances` button (unverified).
  Status per instance (OK/Fail) shown in the Test Case view.
- Assertions: edit the generated tAssert `Description`/`Expression`
  (e.g. `((Boolean)globalMap.get("tFileCompare_1_DIFFERENCE")) == false`);
  add tAssertCatcher to log results; replace tFileCompare with tDBInput +
  tMap comparisons for DB targets.
- Maven/CI: test cases are generated into `.Java/src/test/java/...` and run by
  `mvn test` (surefire) inside the Job build; CI Builder runs them unless
  `-Dmaven.test.skip=true`; results in `target/surefire-reports`. Nexus
  snapshot publication can be made conditional on tests passing.
- Coverage: Studio shows test coverage of the Job's components in the Test Case
  view / `Repository` decorations (unverified); no JaCoCo integration out of the
  box.

Best practice: keep input/reference files under the project
(`<PROJECT>/metadata/...` or a `testdata/` folder committed with Git) and
reference them via the `Test` context so CI machines resolve the same paths.

## Debugging

| Technique | How | Notes |
|---|---|---|
| Traces Debug | Run view > Debug Run > `Traces Debug` | Each row link shows a live data table (`Trace` enabled per link: right-click link > `Show/Hide traces`, and `Trace Debug` filter: `Monitor this connection`); controls `Pause`, `Next Row`, `Next Breakpoint`. Very slow: only for small samples |
| Conditional breakpoints | Select a row link > Component view > `Breakpoint` tab: `Activate conditional breakpoint`, conditions (`Input column`, `Operator`, `Value`, logical `And/Or`) | Traces Debug stops when a row matches |
| Java Debug | Run view > Debug Run > `Java Debug` | Opens Debug perspective; set breakpoints in the `Code` tab of the Job (generated Java) or in routines; step with F5/F6/F7/F8 (Eclipse); inspect `globalMap`, `context`, row structs (`row1.id`) |
| Statistics / Exec time | Run view > Advanced settings | Row counts per link and ms per component on the canvas; find the bottleneck component |
| tLogRow | Modes `Basic`, `Table` (print values in cells of a table), `Vertical` (print each row as key/value list); `Print header`, `Print unique name`, `Separator`, `Print content with log4j` | Remove before production or route to log4j; owned by orchestration-logging.md |
| Console | `Clear before run`, `Line limit` to keep Studio responsive | Stack traces point at `<Job>.java:<line>`; open `Code` tab to map to component |
| Memory issues | `Run view > Advanced settings > JVM Setting` (`-Xmx`), `Memory Run` tab (<= 7.x) | OOM in Studio run != OOM in deployed Job: deployed launcher has its own `-Xmx` in `<job>_run.sh` |
| Partial runs | Right-click component > `Deactivate` (and dependents) or `Deactivate` a whole subjob; temporarily change `Context` | Deactivated components are not generated |
| Data viewer | Right-click a row link > `Data Viewer` (7.1+, Preferences `Row limit`) | Shows sample rows without full run (executes upstream subjob) |
| Problems view | Compile errors before run | Red x on component |

## Feature Manager, patches, licenses, custom components

Studio 8.0 ships a minimal core; optional features (component families,
perspectives, build/publish features, connectors) are installed on demand.

| Item | Detail |
|---|---|
| Open | Top bar `Feature Manager` button or `Help > Feature Manager` (older 8.0 patches) |
| Tabs | `Features` / `Install features` (check boxes with dependency review on `Next`), `Installed features` (list, `Uninstall`), `Updates`/`Patches` (monthly Studio patch, e.g. `R2024-05`) (tab names vary by patch) |
| Sources | Default: Talend/Qlik official update site (needs internet + valid license token). Configurable in `Preferences > Talend > Update settings` / "Configuring update repositories" (local p2 repository served by TAC `Update settings`, TMC `Studio update repository`, or a local folder/HTTP mirror). Air-gapped: download the update repository zip from the customer portal and point the Studio at it |
| Automatic install | When logging into a project whose items need features (e.g. DQ components), Studio prompts to install them. Features independent of items (`Build Docker image`, `Publish to artifact repository`) must be installed manually |
| Patch model | 8.0.1 + monthly cumulative patches `R20YY-MM` (Studio, TAC, Runtime, JobServer patched separately); install from Feature Manager/Updates; remote projects: TAC can enforce a minimum patch; a repackaged full Studio download exists for major jumps (e.g. 8.0.1 R2024-05 for Java 17). Patch level shown in `Help > About Talend Studio` |
| License | First start: paste the license key text or `Browse` the license file; stored under `<studio>/configuration/` (file name version dependent). Expired/renewed: `Help > Manage licenses`/`License` or the login window license link (labels vary); cloud licenses refresh their token online and show `Your license will expire in N days` warnings. Features are filtered by license: a component missing from the Palette with the feature installed usually means the license does not cover it |
| Talend Exchange | Community component marketplace (`Exchange` tab/perspective, `Preferences > Talend > Exchange`) deprecated in 7.x and gone in 8.0. Install community javajet components via `User components folder` |
| Custom components (javajet) | Unzip `tXxx/` folder (with `tXxx_java.xml`, `*.javajet`, `tXxx_messages.properties`) into the `User components folder` (Preferences > Talend > Components); restart or re-apply; appear under their declared `FAMILY` (e.g. `User Components/...`). Jars referenced by `<IMPORT>` in the XML must be installed via Modules |
| Component Kit (TCK) components | `.car` archives: `java -jar my-component-1.0.0.car studio-deploy --location <studio_root>` (copies into `configuration/.m2` and registers in `configuration/config.ini`), or Feature Manager in 8.0 for Talend-provided TCK connectors. Details in apis-sdks.md |
| Component availability | Big Data, DQ, ESB, MDM, TDM families appear only with the matching license and installed feature; cloud-only connectors require Talend Cloud license |

## Studio under the hood

| Aspect | Detail |
|---|---|
| Platform | Eclipse RCP (p2 provisioning, OSGi). 6.x on Eclipse 4.x/Java 8; 7.x on Eclipse 4.x (approx. 4.6-4.8); 8.0 on a newer Eclipse 4.x platform with Java 11, then Java 17 (exact Eclipse versions unverified). Plugin ids `org.talend.*` under `<studio>/plugins/`, OSGi config in `<studio>/configuration/` |
| Code generation | Each Job -> Java class `<project>.<job>_<M>_<m>.<Job>` with one method per subjob; components are rendered by JET templates (`*_begin.javajet`, `*_main.javajet`, `*_end.javajet`) compiled on first use into `.JETEmitters`; TCK components use the Component Kit runtime (`org.talend.sdk.component`) and a generic emitter. Routines compile into `<project>.routines`. Regenerate: close/reopen Job, or delete `<workspace>/.Java/src` + `.JETEmitters` (Studio recreates) |
| Generated code location | `<workspace>/.Java/src/main/java/<project_lowercase>/<job_lowercase>_<M>_<m>/<Job>.java` plus `contexts/*.properties` under resources; tests in `.Java/src/test/java`. `.Java/pom.xml` aggregates per-job poms copied from `<PROJECT>/poms/` |
| Maven | Embedded Maven (m2e) with local repository `<studio>/configuration/.m2/repository` by default (TOS/Studio 6.x-8.0; older 6.x used `<workspace>/.m2` (unverified)). Third-party jars installed through Modules land in `org/talend/libraries/<jar>/6.0.0/`. Talend's own runtime libs are `org.talend.libraries:*:6.0.0` or real Maven coordinates. Nexus set up by TAC exposes `talend-custom-libs-release`, `talend-custom-libs-snapshot` (shared custom jars), `talend-updates` (patches), `releases`, `snapshots`. Settings: `Preferences > Maven > User Settings`; set `<offline>true</offline>` or a mirror for air-gapped sites |
| Logs | `<workspace>/.metadata/.log` (Studio/Eclipse log, also `Error Log` view); `<studio>/configuration/<timestamp>.log` on launcher/OSGi failures; Job run console = stdout of the forked Job JVM; build logs in the Build dialog and `.Java/target` |
| Launch internals | Studio forks a separate JVM per Job run (`Java Interpreter`), classpath from `.Java/target/classes` + m2 jars; remote run ships a zip to the JobServer |
| CommandLine | Headless Studio: `Talend-Studio-*.exe -nosplash -application org.talend.commandline.CommandLine -consoleLog -data commandline-workspace startServer -p 8002` (shell/script/server modes; `initRemote`, `logonProject`, `exportJob`, `publishJob`...). Owned by apis-sdks.md |
| Config files | `<studio>/configuration/config.ini` (OSGi bundles, TCK registrations `component.java.registry`), `configuration/.settings`, `<workspace>/.metadata/.plugins/org.eclipse.core.runtime/.settings/org.talend.*.prefs` (Preferences persistence; safe to delete to reset prefs) |
| Studio-side encryption | Passwords in `.item` stored encrypted (`enc:system.encryption.key.v1:...` in 8.0); key files under `<studio>/configuration/studio.keys` (unverified) are needed when copying projects between Studios outside Git |

## Keyboard shortcuts and productivity

| Shortcut / action | Effect |
|---|---|
| `F6` | Run the current Job (same as Run view > Run) |
| `Ctrl+Space` | Autocomplete in any expression/Java field: `context.*`, `globalMap.get("...")`, routines, row columns (`row1.col`) |
| `Ctrl+S` / `Ctrl+Shift+S` | Save / Save all (triggers code generation) |
| `Ctrl+Z` / `Ctrl+Y` | Undo / Redo on the canvas |
| `Ctrl+C` / `Ctrl+V` / `Ctrl+X` | Copy/paste components (with links and settings) within or across Jobs; pasted components get the next free unique name (`tMap_1` -> `tMap_2`); context variables referenced must exist in the target Job (Studio offers to add missing ones (unverified)) |
| `Ctrl+A`, `Delete` | Select all / delete selection |
| `Ctrl+Shift+F` | Format in Java editors (routines, tJava code via `...` editor) (Eclipse) |
| `Ctrl+click` / `Shift+drag` | Multi-select; drag selection rectangle |
| Type on canvas | Quick component search/insert (no modifier needed); `Esc` cancels |
| Double-click component | Opens its editor (tMap/tXMLMap map editor, tJava code) or the Component view |
| `F2` on a component / Note | Rename label inline (unverified) |
| Right-click > `Deactivate` | Excludes a component and everything downstream from generation; `Activate` reverses; also `Deactivate subjob` from the subjob title (unverified) |
| Right-click > `Duplicate` | Clone component with settings |
| Right-click canvas > `Paste`/`Export to image`/`Arrange` | Layout helpers |
| Note | Palette `Note` or canvas toolbar; attach to a component by dragging over it (sticky) |
| Labels / hints | Component view > View: `Label format` `__UNIQUE_NAME__` (+ parameter variables like `__TABLE__`), `Hint format`; show hints globally via `Preferences > Talend > Designer` |
| Metadata drag | Drop a repository schema/connection on the canvas; `Shift`+drop forces output component (unverified) |
| `Alt+Enter` | Edit properties of selected repository item (Eclipse convention) (unverified) |
| `Ctrl+H` | Eclipse search (searches item XML text in the workspace: useful to find which Jobs reference a table name) |
| Repository funnel + `Link with editor` | Keep the tree in sync with the open Job |

Productivity habits: use repository metadata + context groups so that one
change propagates; keep Job names without spaces/accents (they become Java
identifiers); set `Save Job before execution`; disable `Statistics`/`Exec time`
for performance runs; use Joblets for repeated logging/error patterns; use
`Dynamic settings` instead of duplicating components for `Die on error`
toggles; export items with dependencies before risky refactors.

## Gotchas

| Symptom | Cause | Fix |
|---|---|---|
| Studio hangs at splash, blank Repository, or `An error has occurred. See the log file ... .metadata/.log` | Corrupted `<workspace>/.metadata` (crash, sync folder, Studio upgrade over old workspace) | Start with `-clean`; if still broken, rename `.metadata`, create a new workspace and `Import an existing project` from the old `<PROJECT>` folder (or re-login for remote projects). Never share a workspace between Studio versions |
| `Job is locked by <user>` / item opens read-only | Remote project item locked by another user or a stale lock from a crashed Studio | Ask the owner to close it; admin: TAC `Lock administration` / TMC project item unlock; own stale lock: right-click > `Unlock`. Set lock mode to Ask/Manual in Preferences > Talend > Repository if locks are a constant problem |
| Build/run fails `Could not resolve dependencies` / `Failure to find org.talend.libraries:...` / endless `Downloading` | Studio embedded Maven cannot reach Talend update site or Maven Central (no proxy, air-gapped, expired license token), or local `configuration/.m2` has stale `.lastUpdated` files | Configure `Preferences > General > Network Connections` and `Maven > User Settings` (mirror to Nexus `talend-custom-libs-*`); delete `*.lastUpdated` under `configuration/.m2/repository`; set Maven offline once jars are present; install missing jars via Modules > `Install external module` |
| Component shows red x; Modules view `Module not installed` (e.g. `ojdbc8.jar`, `sapjco3.jar`, `mysql-connector-java`) | Licensed/third-party driver not redistributable or not downloaded | Modules view > select > `Install external module` (local jar) or `Download` where allowed; for remote teams upload once to Nexus `talend-custom-libs-release` via TAC so every Studio resolves it |
| Studio `java.lang.OutOfMemoryError: Java heap space` / `GC overhead limit exceeded` / freezes with many Jobs open | Default `-Xmx768m` in `.ini`; huge tMap/JSON metadata; many editors open | Raise `-Xmx` (2-4 GB) and `-XX:MaxMetaspaceSize=512m` in `Talend-Studio-*.ini`; close editors; disable `Statistics`; split giant Jobs |
| Job run in Studio hits OOM but production is fine (or vice versa) | Studio run uses `Run view > Advanced settings > JVM Setting`, deployed job uses launcher `-Xmx` | Set `Use specific JVM arguments` for Studio tests; adjust `<job>_run.sh` or TAC/TMC task JVM parameters separately |
| Git `Pull` reports conflicts on `.item`/`.properties`; Studio shows conflict dialog each login | Two users changed the same Job (or Studio migration tasks rewrote items on one side) | Resolve in the Studio dialog choosing local or remote version per item; re-apply the lost change by hand; avoid parallel edits on one Job (use Joblets/child Jobs); commit migration-task changes immediately after upgrading |
| `Unsupported class file major version` / `invalid target release: 17` / Studio refuses to start with `Version 17 or greater is required` | Java mismatch: Studio patch requires Java 17 (R2024-05+) or 11 (<= R2024-04); `Java Interpreter` points to a JRE or wrong JDK; project `Java version` higher than installed JDK | Install the right JDK, set `-vm` in `.ini`, set `Preferences > Talend > Java Interpreter` to a JDK, align `Project Settings > Build > Java version`; enable `Enable Java 17 compatibility` for Java 17 Jobs |
| Feature Manager: `Unable to read repository` / `No repository found` / install stuck at 0% | Proxy not configured for Studio, update site URL blocked, license token invalid, or local update repository misconfigured | Set proxy in `Preferences > General > Network Connections`; verify license is valid and online; for air-gapped Studios configure the local update repository (TAC/TMC update repository or downloaded p2 zip) |
| Talend Cloud login fails / `Publish to Cloud` greyed out | Wrong region URL, SSO account needs a personal access token, missing `Publish to Cloud` feature, or user lacks publisher role in TMC | Use the region-specific Talend Cloud connection; generate a token in TMC profile; install the feature; check TMC roles |
| `Your license has expired` / Studio starts in restricted mode | Subscription key past end date or cloud token revoked | Get the renewed key from the Qlik/Talend customer portal, enter via `Help > Manage licenses`/login window; for cloud, re-login |
| Palette slow / search takes seconds / Studio sluggish after installing many features | All component families loaded; indexing of hundreds of jars; antivirus scanning `.Java` and `configuration/.m2` | Hide unused families in `Palette Settings`; exclude Studio and workspace folders from real-time antivirus; raise `-Xmx`; use SSD |
| Component greyed/missing after importing items from another Studio (`Component tXxx is not available`) | Feature/license for that component not installed/covered, or custom component folder not configured | Install the feature via Feature Manager (Studio prompts on project login), copy custom components into `User components folder`, or replace the component |
| Compilation errors in every Job after editing a routine | Routine syntax error or removed method; all Jobs depend on global routines | Fix the routine (Problems view points to it); for 8.0 limit blast radius by using custom (per-Job) routines |
| Schema change in Metadata did not reach a Job; tMap shows red expressions | Component switched to `Built-In`, Job was locked during propagation, or `Deactivate automatic update of schema` is on | Re-link the component to the Repository schema, re-run propagation, open tMap and fix mappings (`Sync columns` on outputs) |
| `Guess schema` returns all `String` / wrong lengths; `Retrieve Schema` lists no tables | Guessing is sample-based; DB user lacks catalog privileges or wrong schema/catalog filter | Set types/lengths manually or via mapping file; grant metadata rights; use the schema filter in the Retrieve Schema wizard |
| Run on remote JobServer fails `Connection refused` / `Unable to transfer file` | JobServer ports 8000/8001/8888 blocked, credentials in `Preferences > Talend > Run/Debug > Remote` wrong, or JobServer Java version older than build target | Open ports, fix credentials, align Java |
| Build Job produces zip but running `<job>_run.sh` says `ClassNotFoundException` | Third-party jar installed in Studio but not included (module marked as provided, or jar only in Studio classpath) | Check Modules view status before build; re-install via `Install external module`; rebuild; compare `lib/` of the zip |
| `Docker Image` build: `Cannot connect to the Docker daemon` or push `401` | Local Docker not running, `Docker host` misconfigured, registry credentials missing | Start Docker / set remote host; fill `Registry` credentials; Jib builds without daemon when pushing to a registry |
| Imported project shows items with version `0.1` duplicates or `Item already exists` errors | Importing an export that contains multiple versions or into a project with same-name items | Tick `Overwrite existing items` deliberately or import into a fresh project; delete old versions first |
| Studio UI unreadable/high DPI, or crashes on Linux with GTK errors | GTK3/Wayland/scaling issues with the Eclipse version | Run with `GDK_BACKEND=x11`, set `-Dswt.autoScale=100` / `150` in `.ini`; on Windows use `-Dswt.autoScale=exact` (approximate) |
| Changes in `Preferences` not applied / lost after restart | Preferences stored per workspace in `.metadata/.plugins/org.eclipse.core.runtime/.settings`; different workspace per connection | Set them in the workspace you actually use; copy `.settings/org.talend.*.prefs` to replicate |

## Sources

https://help.qlik.com/talend/en-US/installation-guide-windows/8.0/talend-studio
https://help.qlik.com/talend/en-US/installation-guide-mac/8.0/talend-studio
https://help.qlik.com/talend/en-US/studio-user-guide/7.2/licenses-and-perspectives-in-studio
https://help.qlik.com/talend/r/en-US/7.3/studio-user-guide
https://help.qlik.com/talend/en-US/studio-user-guide/8.0/profiling-and-data-quality
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-08/install-features-to-talend-studio
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-04-and-earlier/install-features-to-talend-studio
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-04/building-jobs
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-05/building-jobs
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-07/applying-project-settings
https://help.qlik.com/talend/en-US/studio-user-guide/7.3/applying-project-settings
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-06/job-settings
https://help.qlik.com/talend/en-US/installation-guide-windows/8.0/optimizing-talend-studio-performance
https://help.qlik.com/talend/en-US/installation-guide-linux/8.0/optimizing-talend-studio-performance
https://help.qlik.com/talend/en-US/installation-guide-mac/8.0/optimizing-talend-studio-performance
https://help.qlik.com/talend/en-US/installation-guide-mac/7.2/editing-memory-and-jvm-settings
https://help.qlik.com/talend/en-US/supported-java-versions-before-may-2024/8.0
https://help.qlik.com/talend/en-US/release-notes/8.0/r2024-03-upcoming-software-requirements
https://help.qlik.com/talend/en-US/release-notes/8.0/r2024-05-studio-new-features-shared-features
https://help.qlik.com/talend/en-US/release-notes/8.0/r2024-05-software-requirements
https://help.qlik.com/talend/en-US/installation-guide-mac/8.0/compatible-java-environments
https://community.qlik.com/t5/Official-Support-Articles/Qlik-Talend-Products-Java-17-Migration-Guide/tac-p/2471620/highlight/true
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-08/pushing-changes-on-local-branch-to-remote-end-git-only
https://help.qlik.com/talend/fr-FR/studio-user-guide/8.0/committing-changes-to-a-local-branch
https://community.qlik.com/t5/Talend-Studio/Talend-Studio-Comparing-Changes-when-using-Git/m-p/2297776
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2025-07/creating-test-case
https://help.qlik.com/talend/en-US/studio-user-guide/7.3/creating-test-case?id=447
https://help.qlik.com/talend/en-US/software-dev-lifecycle-best-practices-guide/8.0/example-of-test-case-based-on-job
https://help.qlik.com/talend/en-US/components/8.0/logs-and-errors/tassert-tassertcatcher-tfileoutputdelimited-setting-up-assertive-condition-for-job-execution-standard-component-this
