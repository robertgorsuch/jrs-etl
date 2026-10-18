# Talend artifact formats: .item/.properties XML, workspace, Jobscript, generated Java, build outputs

> Verification: doc-derived (help.qlik.com / help.talend.com search snippets, Talend GitHub, Maven Central) plus model knowledge. Not exercised against a live Studio/TAC/TMC in this build. Items marked (unverified) are from memory only and should be checked in Studio before relying on exact labels.

Additional evidence used for this file: real Studio-produced items pulled from
public GitHub repos (TOS DI 6.1, 7.1, 8.0.1; Talend Cloud DMP 8.0.1 R2025-02;
TOS ESB 7.1), the `TalendFile.ecore`, `mapper.ecore`, `EConnectionType.java`,
`FileConstants.java` and OSGi blueprint templates from the open-source Studio
code (`toscollection/tcommon-studio-se`, `toscollection/tdi-studio-se` mirrors of
Talend's repos), a Studio-exported `.jobscript`, a generated job Java class and
`PasswordEncryptUtil.java` from exported jobs, and `CarBundler.java` from
`Talend/component-runtime`. Facts taken from those files are stated without a
marker; anything else from memory is marked (unverified).

## Contents
- [1. Workspace and project layout](#1-workspace-and-project-layout)
- [2. Job item XML (.item)](#2-job-item-xml-item)
- [3. Property files, contexts, routines, metadata, joblets](#3-property-files-contexts-routines-metadata-joblets)
- [4. Password encryption in items](#4-password-encryption-in-items)
- [5. Jobscript](#5-jobscript)
- [6. Generated Java](#6-generated-java)
- [7. Build outputs](#7-build-outputs)
- [8. Context and properties files at runtime](#8-context-and-properties-files-at-runtime)
- [9. Route, Service, Big Data and other item kinds](#9-route-service-big-data-and-other-item-kinds)
- [10. Reading, writing and diffing items programmatically](#10-reading-writing-and-diffing-items-programmatically)
- [Gotchas](#gotchas)
- [Sources](#sources)

## 1. Workspace and project layout

A Studio workspace is an Eclipse workspace. Each project is a folder named by its
technical label (upper-case, e.g. `LOCAL_PROJECT`). Repository folders you create
in Studio become sub-folders under the type folder (e.g. `process/finance/Load_0.1.item`).

```
<workspace>/
  .metadata/                      Eclipse workspace state (never commit)
  <PROJECT>/                      one folder per project, technical label
    talend.project                project descriptor (XMI)
    .project                      Eclipse project file (natures: org.talend.repository.talendnature)
    .classpath                    Eclipse classpath (regenerated)
    .settings/
      project.settings            Project Settings (implicit context, stats/logs, log4j, maven) as XMI (unverified structure)
      relationship.index          item relation graph (job -> context/metadata/routine/joblet ids); rebuilt by Studio
      migration_task.index        migration tasks already applied
      recycle_bin.index           items in the Recycle bin
    process/                      Standard jobs  (<Job>_<M>.<m>.item + .properties [+ .screenshot])
    process_mr/                   Big Data Batch jobs (Spark, formerly MapReduce) - jobType="Big_Data_Batch"
    process_storm/                Big Data Streaming jobs (Spark Streaming, formerly Storm) - jobType="Big_Data_Streaming"
    joblets/                      Joblets (JobletProcessItem)
    routes/                       Mediation routes (CamelProcessItem)
    routelets/                    Routelets (unverified folder name)
    route_resources/              Route resources (files embedded in route bundles)
    services/                     Data services (ServiceItem: .item + .wsdl + .properties)
    context/                      Context groups (ContextItem)
    code/routines/                User routines; code/routines/system/ holds built-in routines (builtIn="true")
    code/beans/                   ESB beans (BeanItem)
    code/snippets/                SQL/Java snippets (legacy)
    code/pigudf/                  Pig UDFs (legacy Big Data)
    metadata/connections/         DatabaseConnectionItem
    metadata/fileDelimited/       DelimitedFileConnectionItem
    metadata/filePositional/  fileRegex/  fileXml/  fileExcel/  fileLdif/  fileJson/
    metadata/genericSchema/       GenericSchemaConnectionItem
    metadata/wsdl/  salesforce/  ldap/  ftp/  sap/  hadoopcluster/  noSQLConnections/
    metadata/MDMconnections/  edifact/  validationRules/  rules/   (edition dependent)
    documentation/                DocumentationItem (linked files)
    businessProcess/              Business models
    sqlPatterns/                  SQLPatternItem (system + user)
    poms/                         7.x+: generated Maven project tree (see below)
    .Java/ or ../.Java/           generation project (see below)
  .Java/                          <= 6.x: hidden Eclipse Java project with generated code
```

Folder names above that are confirmed from items on disk: `process`,
`process_mr`, `process_storm`, `joblets`, `routes`, `services`, `context`,
`code/routines`, `code/routines/system`, `code/snippets`, `metadata`,
`metadata/connections`, `metadata/fileDelimited`, `metadata/genericSchema`,
`route_resources`, `components` (custom components). The rest follow the same
pattern and are from memory.

### talend.project

```xml
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:TalendProperties="http://www.talend.org/properties">
  <TalendProperties:Project xmi:id="_6SpgcJxiEe2tbq-HlRgJpg" label="main1" description="" language="java"
      technicalLabel="MAIN1" local="true" author="_6SpgcZxiEe2tbq-HlRgJpg"
      productVersion="Talend Open Studio for Data Integration-8.0.1.20211109_1610"
      itemsRelationVersion="1.3" bigData="false">
    <migrationTask xmi:id="_6S7NQJxiEe2tbq-HlRgJpg"
        id="org.talend.repository.model.migration.CheckProductVersionMigrationTask" breaks="7.1.0" version="7.1.1"/>
    <!-- optional, one per component ever dropped on a canvas in this project: -->
    <componentsSettings xmi:id="..." name="DI|tHashInput" family="Technical"/>
  </TalendProperties:Project>
  <TalendProperties:User xmi:id="_6SpgcZxiEe2tbq-HlRgJpg" login="user@talend.com" password="D41D8CD98F00B204E9800998ECF8427E"/>
</xmi:XMI>
```

| Attribute | Meaning |
|---|---|
| `label` / `technicalLabel` | display name / folder + Java package root (upper-case, `[A-Z0-9_]`) |
| `language="java"` | always java since 5.x (perl projects are long dead) |
| `local="true"` | local (non-TAC/TMC) project; remote projects omit it and carry `url="{...json...}"` with `"storage":"git"` and the repo `location` |
| `productVersion` | `"<Product full name>-<M.m.p>.<yyyyMMdd_HHmm>[-patch]"`, e.g. `Talend Cloud Data Management Platform-8.0.1.20250625_0954-patch` |
| `itemsRelationVersion="1.3"` | version of the relation index format in `.settings/relationship.index` |
| `type="DQ"` | present on DQ-capable editions (8.0 Data Fabric/DMP) |
| `migrationTask` | list of applied migration task ids; Studio appends on open. Diff noise. |
| `User.password` | MD5 hex of the login password (`D41D8CD9...` = MD5 of empty string) |

In 5.x `<itemsRelations>` children lived inside `talend.project`; since 6.x the graph is
`.settings/relationship.index` (confirmed by `FileConstants.RELATIONSHIP_FILE_NAME`).

### Generation project (.Java) and poms

| Version | Where generated code lives |
|---|---|
| <= 6.x | `<workspace>/.Java/src/main/java/<project_lower>/<job_lower>_<M>_<m>/<Job>.java`, routines in `.Java/src/main/java/routines/`, `.Java/pom.xml`, `.Java/target/` |
| 7.x / 8.x | `<workspace>/<PROJECT>/poms/` holds the Maven tree: `poms/pom.xml` (aggregator), `poms/code/routines/pom.xml` + `src/main/java/routines/*.java`, `poms/code/beans/`, `poms/jobs/process/<job>_<M>_<m>/pom.xml` + `src/main/java/<project_lower>/<job_lower>_<M>_<m>/<Job>.java` + `src/main/resources/<project_lower>/<job_lower>_<M>_<m>/contexts/<Ctx>.properties`, `poms/jobs/process_mr/...`, `poms/jobs/routes/...`; `.Java/` remains as the Eclipse project that links them (unverified detail: exact `poms/jobs/<type>` sub-folder names) |

Java naming rules (confirmed from generated code): package = `<project technical label lower-case>.<job name lower-case>_<major>_<minor>`; class = job name with original case; e.g. project `LOCAL_PROJECT`, job `rancher2text_3` v0.1 -> `local_project.rancher2text_3_0_1.rancher2text_3`.

### What to track in Git

Track: `talend.project`, `.project`, `.settings/project.settings`, `.settings/relationship.index` (optional; Studio rebuilds it but TAC/CI expect it in remote projects), every type folder (`process/`, `context/`, `metadata/`, `code/`, ...). Ignore: `.metadata/`, `.Java/`, `.JETEmitters/`, `poms/**/target/`, `*.class`, `*.jar` under `poms/`, Eclipse `.classpath`, `local.properties`, `.loadpath`, `*.launch`. A community `.gitignore` for Talend (evandycke/talend-tips-tricks) ignores exactly: `.metadata`, `.settings/`, `.loadpath`, `.Java`, `.JETEmitters`, `.classpath`, `*.class`, `*.jar`. Keep `.settings/` if you rely on project-level settings being shared. Suggested `.gitattributes`:

```
*.item        text eol=lf
*.properties  text eol=lf
*.screenshot  binary
*.jobscript   text eol=lf
*.bmp -text
```

## 2. Job item XML (.item)

File `process/<path>/<JobName>_<M>.<m>.item`. One root element, no `xmi:XMI` wrapper for jobs.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<talendfile:ProcessType xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:TalendMapper="http://www.talend.org/mapper"            <!-- only when a tMap exists -->
    xmlns:TalendXMLMap="http://www.talend.org/xmlmap"            <!-- only when a tXMLMap exists -->
    xmlns:talendfile="platform:/resource/org.talend.model/model/TalendFile.xsd"
    defaultContext="Default" jobType="Standard">
  <context .../>          1..n
  <parameters> ... </parameters>
  <node .../>             0..n
  <connection .../>       0..n
  <subjob> ... </subjob>  0..n
  <note .../>             0..n
</talendfile:ProcessType>
```

Root attributes (from `TalendFile.ecore` `ProcessType`): `defaultContext`, `jobType`
(`Standard` | `Big_Data_Batch` | `Big_Data_Streaming`; absent in <= 6.x items), `framework`
(`Spark` | `Spark_Streaming` | `MapReduce` | `Storm`, only Big Data), plus rarely used
`name`, `version`, `author`, `comment`, `purpose`, `status`, `description`,
`repositoryContextId`, `required`, `screenshot` (<= 5.x inline PNG base64), `screenshots`
(moved to the `.screenshot` file). Items saved by TAC/Git-managed Studios also carry
`xmi:id` on every element; local-project Studios usually omit them. Both are valid.

### context / contextParameter

```xml
<context confirmationNeeded="false" hide="false" name="Default">
  <contextParameter comment="" name="file" prompt="file?" promptNeeded="false"
      type="id_String" value="/tmp/x.csv" repositoryContextId="_abc123..."/>
</context>
```

- One `<context>` per environment (Default, Dev, Prod...). All contexts must declare the same parameter names.
- `repositoryContextId` = id of the context group item the variable came from; `built-in` (8.x) or absent for job-local variables. `internalId` exists in the model (8.x) for rename tracking.
- `type` values (Talend types, `id_` prefix): `id_String`, `id_Integer`, `id_Long`, `id_Short`, `id_Byte`, `id_Double`, `id_Float`, `id_BigDecimal`, `id_Boolean`, `id_Character`, `id_Date`, `id_Object`, `id_List`, `id_File`, `id_Directory`, `id_Password`, `id_Document`, `id_byte[]`, `id_Dynamic`. `id_Password` values are stored encrypted (section 4).
- `value` is stored raw (no Java quotes) for contexts. Component parameters that reference it use the expression `context.file`.

### parameters (job level)

All are `<elementParameter field="..." name="..." value="..." [show="false"] [contextMode="false"]/>`.
`show="false"` means hidden in the Job view (6.x+); 5.x items used `contextMode="false"` instead. Important names:

| Name | Field | Meaning |
|---|---|---|
| `MULTI_THREAD_EXECATION` (sic) | CHECK | Job > Extra > Multi thread execution |
| `PARALLELIZE_UNIT_SIZE` | TEXT | default `25000` |
| `IMPLICIT_TCONTEXTLOAD`, `FROM_FILE_FLAG_IMPLICIT_CONTEXT`, `FROM_DATABASE_FLAG_IMPLICIT_CONTEXT`, `IMPLICIT_TCONTEXTLOAD_FILE`, `FIELDSEPARATOR`, `*_IMPLICIT_CONTEXT` (URL, HOST, PORT, DBNAME, USER, PASS, DBTABLE, QUERY_CONDITION...), `LOAD_NEW_VARIABLE`, `NOT_LOAD_OLD_VARIABLE`, `PRINT_OPERATIONS`, `DISABLE_ERROR/WARNINGS/INFO` | mixed | Job > Extra > Implicit tContextLoad |
| `IMPLICITCONTEXT_USE_PROJECT_SETTINGS`, `STATANDLOG_USE_PROJECT_SETTINGS` | CHECK | `true` = inherit Project Settings; then the local values are ignored |
| `ON_STATCATCHER_FLAG`, `ON_LOGCATCHER_FLAG`, `ON_METERCATCHER_FLAG`, `ON_CONSOLE_FLAG`, `ON_FILES_FLAG`, `ON_DATABASE_FLAG`, `FILE_PATH`, `FILENAME_STATS/LOGS/METTER`, `DB_TYPE`, `DB_VERSION`, `URL`, `DRIVER_JAR`, `DRIVER_CLASS`, `HOST`, `PORT`, `DBNAME`, `USER`, `PASS`, `TABLE_STATS/LOGS/METER`, `CATCH_RUNTIME_ERRORS`, `CATCH_USER_ERRORS`, `CATCH_USER_WARNING`, `CATCH_REALTIME_STATS` | mixed | Job > Stats & Logs |
| `LOG4J_RUN_LEVEL` | CLOSED_LIST | 7.x+: `Info`, `Debug`, ... (Run view log4j level) |
| `JOB_RUN_VM_ARGUMENTS_OPTION`, `JOB_RUN_VM_ARGUMENTS` | CHECK/TEXT | Job > Extra > Use specific JVM arguments (unverified exact names) |
| `SCREEN_OFFSET_X/Y` | TEXT | canvas scroll offset: pure diff noise |
| `REPOSITORY_CONNECTION_ID`, `OOZIE_*` | TEXT | legacy Oozie scheduler settings, always empty |
| `OVERRIDE_ENCODING_FLAG`, `OVERRIDE_ENCODING_IN_EXTRA`, `OVERRIDE_ENCODING_IN_EXTRA:ENCODING_TYPE` | mixed | 8.x: override tContextLoad encoding |
| `HEADER_*`, `FOOTER_*`, `HEADERFOOTER_HEADERID/FOOTERID` | mixed | header/footer code (legacy) |
| `COMP_DEFAULT_FILE_DIR`, `AUTHOR`, `STATUS`, `NAME`, `VERSION`, `PURPOSE`, `DESCRIPTION`, `displaySubjobs` | mixed | <= 5.x only; moved to `.properties` later |
| `TESTCONTAINER_*`, `PROCESS_TYPE_*` | | appear in test-case items / tRunJob nodes, not at job level (unverified at job level) |

`<routinesParameter id="<routine property id>" name="TalendDate"/>` entries at the end of
`<parameters>` list the routines the job depends on (system routines are listed too).
The `id` must match a routine `.properties` `Property@id`; a dangling id gives an import warning only.

### node

```xml
<node componentName="tFileInputDelimited" componentVersion="0.102" offsetLabelX="0" offsetLabelY="0" posX="96" posY="96">
  <elementParameter field="TEXT" name="UNIQUE_NAME" value="tFileInputDelimited_1" show="false"/>
  <elementParameter field="TECHNICAL" name="PROPERTY:PROPERTY_TYPE" value="REPOSITORY"/>
  <elementParameter field="TECHNICAL" name="PROPERTY:REPOSITORY_PROPERTY_TYPE" value="_cuJ8QPB5EfCv4Ytt6y8EMw" show="false"/>
  <elementParameter field="TECHNICAL" name="SCHEMA:SCHEMA_TYPE" value="REPOSITORY" show="false"/>
  <elementParameter field="TECHNICAL" name="SCHEMA:REPOSITORY_SCHEMA_TYPE" value="_cuJ8QPB5EfCv4Ytt6y8EMw - metadata" show="false"/>
  <elementParameter field="FILE" name="FILENAME" value="&quot;D:/data/student.csv&quot;"/>
  <elementParameter field="TEXT" name="ROWSEPARATOR" value="&quot;\n&quot;"/>
  <elementParameter field="TEXT" name="FIELDSEPARATOR" value="&quot;,&quot;"/>
  <elementParameter field="TEXT" name="HEADER" value="1"/>
  <elementParameter field="CHECK" name="DIE_ON_ERROR" value="false"/>
  <elementParameter field="TABLE" name="TRIMSELECT">
    <elementValue elementRef="SCHEMA_COLUMN" value="Regno"/>
    <elementValue elementRef="TRIM" value="false"/>
    <elementValue elementRef="SCHEMA_COLUMN" value="Name"/>
    <elementValue elementRef="TRIM" value="false"/>
  </elementParameter>
  <elementParameter field="ENCODING_TYPE" name="ENCODING" value="&quot;ISO-8859-15&quot;"/>
  <elementParameter field="TECHNICAL" name="ENCODING:ENCODING_TYPE" value="ISO-8859-15"/>
  <elementParameter field="TEXT" name="CONNECTION_FORMAT" value="row"/>
  <metadata connector="FLOW" label="metadata" name="tFileInputDelimited_1">
    <column comment="" key="false" length="4" name="Regno" nullable="true" pattern="&quot;dd-MM-yyyy&quot;" precision="0" type="id_String" usefulColumn="true"/>
    <column comment="" key="false" length="10" name="Bdate" nullable="true" pattern="&quot;dd-MM-yyyy&quot;" precision="0" type="id_Date" usefulColumn="true"/>
  </metadata>
  <metadata connector="REJECT" label="metadata" name="REJECT">
    ... same columns ...
    <column defaultValue="" key="false" length="255" name="errorCode" nullable="true" precision="0" sourceType="" type="id_String" originalLength="-1" usefulColumn="true"/>
    <column defaultValue="" key="false" length="255" name="errorMessage" nullable="true" precision="0" sourceType="" type="id_String" originalLength="-1" usefulColumn="true"/>
  </metadata>
</node>
```

Node attributes (ecore `NodeType`): `componentName`, `componentVersion` (component's own
version, e.g. tMap `2.1`, tFileInputDelimited `0.102`, tLogRow `0.101`; bumps when
Studio migrates), `posX`, `posY`, `offsetLabelX`, `offsetLabelY`, `sizeX`, `sizeY`,
plus children `elementParameter`, `metadata`, `nodeData` (external data: tMap, tXMLMap,
tELTMap...), `binaryData`/`stringData` (legacy), `nodeContainer` (joblet containers).

Value quoting rule: anything typed in a Java-expression field is stored as the Java
expression, so a literal string carries its own double quotes, XML-escaped:
`value="&quot;,&quot;"` is the Java `","`. `value="context.sep"` is a context reference.
Numeric/boolean widgets store bare `1`, `true`. Empty expression = `value=""`.

`elementParameter@field` values (the widget type; from `EParameterFieldType`):

| field | Widget / storage |
|---|---|
| `TEXT` | one-line Java expression |
| `CHECK` | `true`/`false` |
| `RADIO` | one of a radio group, `true`/`false` each |
| `CLOSED_LIST` | combo; `value` = item code (`MYSQL_8`, `INSERT`, `Info`) |
| `OPENED_LIST` | editable combo |
| `TABLE` | repeated `<elementValue elementRef="<col>" value="..."/>` rows, one group of elementValues per row, in column order; `SCHEMA_COLUMN` rows are tied to schema columns |
| `MEMO`, `MEMO_SQL`, `MEMO_JAVA`, `MEMO_PERL`, `MEMO_IMPORT` | multi-line (SQL for QUERY, Java for tJava CODE) |
| `SCHEMA_TYPE` / `TECHNICAL` pair `SCHEMA:SCHEMA_TYPE` + `SCHEMA:REPOSITORY_SCHEMA_TYPE` | `BUILT_IN` or `REPOSITORY`; repository value = `<metadata item property id> - <table label>` |
| `PROPERTY_TYPE` pair `PROPERTY:PROPERTY_TYPE` + `PROPERTY:REPOSITORY_PROPERTY_TYPE` | `BUILT_IN`/`REPOSITORY`; value = property id of the metadata connection (`_cuJ8QPB5EfCv4Ytt6y8EMw`) |
| `QUERYSTORE_TYPE` pair `QUERYSTORE:QUERYSTORE_TYPE` + `QUERYSTORE:REPOSITORY_QUERYSTORE_TYPE` | saved SQL queries |
| `SCHEMA_REFERENCE` | tELT* / schema from another component |
| `PASSWORD` | encrypted value (section 4) |
| `FILE`, `DIRECTORY` | path expression (still Java-quoted) |
| `COLOR` | `r;g;b` e.g. `92;131;150` |
| `COMPONENT_LIST` | unique name of another component (`tDBConnection_1`, used by `CONNECTION`, `SPARK_CONFIGURATION`, `HTTPS_SETTING`) |
| `CONNECTION_LIST`, `PREV_COLUMN_LIST`, `COLUMN_LIST`, `LOOKUP_COLUMN_LIST` | names from the graph |
| `ENCODING_TYPE` (+ `TECHNICAL` `ENCODING:ENCODING_TYPE`) | encoding combo; the TECHNICAL twin holds the un-quoted code |
| `DBTYPE_LIST`, `MAPPING_TYPE`, `DBTABLE`, `SQLPATTERN_LIST`, `VERSION`, `MODULE_LIST`, `HADOOP_JARS_DIALOG`, `ICON_SELECTION`, `IMAGE`, `EXTERNAL`, `JAVA_COMMAND`, `LABEL`, `TECHNICAL` | misc; `TECHNICAL` = hidden helper, `LABEL` = read-only text (`FILENAMETEXT`) |
| `PROCESS_TYPE` (tRunJob) `PROCESS` + `TECHNICAL` `PROCESS:PROCESS_TYPE_PROCESS`, `PROCESS:PROCESS_TYPE_CONTEXT`, `PROCESS:PROCESS_TYPE_VERSION` | child job: value of `PROCESS` = job label; `_PROCESS` = child job property id; `_CONTEXT` = context name; `_VERSION` = `Latest` or `0.1` |
| `ROUTE_INPUT`, `ROUTE_COMPONENT_TYPE` | route-only widgets (unverified names) |

Common hidden node parameters: `UNIQUE_NAME`, `LABEL` (default `__UNIQUE_NAME__`), `HINT`,
`CONNECTION_FORMAT` (`row`), `ACTIVATE`, `START`, `STARTABLE`, `UPDATE_COMPONENTS`,
`TSTATCATCHER_STATS`, `HELP` (`org.talend.help.tLogRow`), `REPOSITORY_ALLOW_AUTO_SWITCH`,
`SCHEMA_OPT_NUM`, `IREPORT_PATH`, `TEMP_DIR`, `COMMENT`.

TCK (Component Kit) components (tAzureAdlsGen2*, tSnowflake* v2, tREST* v2...) store their
properties as flattened keys `configuration.accountName`, `configuration.__version`, plus
`TACOKIT_COMPONENT_ID` (base64 of family#component#...). Legacy "Daikon" components
(tSnowflakeOutput 7.x, Salesforce, Marketo) store one `PROPERTIES` JSON blob with `@type`
`org.talend.components...Properties` and `__version`. Both are opaque to hand-editing beyond
simple value swaps.

### metadata (schemas)

`<metadata connector="FLOW" name="tFileInputDelimited_1" label="metadata">` holds a schema
per connector. `name` = the component unique name for the main output, or the connector
name (`REJECT`, `UNIQUE`, `DUPLICATES`, `FILTER`, `MERGE`, `LOOKUP`), or for tMap/tXMLMap
the output table name (`<metadata connector="FLOW" label="out1" name="out1">`). `label` is
the repository table label (`metadata`) or the row name.

Column attributes (`ColumnType`): `name`, `type` (`id_*`), `nullable`, `key`, `length`,
`precision`, `pattern` (date pattern, Java-quoted `&quot;dd-MM-yyyy&quot;`), `comment`,
`defaultValue`, `sourceType` (DB type, e.g. `VARCHAR`), `originalDbColumnName`,
`originalLength`, `usefulColumn` (false = unchecked in tELT*/db output), `relatedEntity`,
`relationshipType`, `additionalField` map entries. Length/precision `-1`/`0` both mean unset.

Connector names seen in items: `FLOW` (main out and also lookups into tMap),
`MAIN`, `LOOKUP`, `REJECT`, `ITERATE`, `FILTER`, `UNIQUE`, `DUPLICATES`, `OUTPUT`,
`MERGE`, `TABLE`, `REJECTS`, `ERROR_REJECT` (tMap die-on-error reject), `COMPONENT_OK`,
`COMPONENT_ERROR`, `SUBJOB_OK`, `SUBJOB_ERROR`, `RUN_IF`, `ROWS_END`, `SYNCHRONIZE`,
`PARALLELIZE`, `ROUTE`, `ROUTE_WHEN`, `ROUTE_OTHER`, `ROUTE_TRY`, `ROUTE_CATCH`,
`ROUTE_FINALLY`, `ROUTE_ENDBLOCK`, `STARTS`.

### connection

```xml
<connection connectorName="FLOW" label="row1" lineStyle="0" metaname="tFileInputDelimited_1"
    offsetLabelX="0" offsetLabelY="0" source="tFileInputDelimited_1" target="tMap_1">
  <elementParameter field="CHECK" name="MONITOR_CONNECTION" value="false"/>
  <elementParameter field="TEXT" name="UNIQUE_NAME" value="row1" show="false"/>
</connection>
```

- `source`/`target` = node `UNIQUE_NAME`s. `label` = displayed name, `UNIQUE_NAME` = row variable (`row1`, `out1`, `iterate1`, `OnSubjobOk1`).
- `metaname` = which `<metadata>` of the source describes the flow: the source unique name for a normal FLOW, the output table name for tMap/tXMLMap outputs (`metaname="op2"`), the connector name for REJECT/UNIQUE/FILTER (`metaname="UNIQUE"`).
- `mergeOrder` (tUnite inputs), `outputId` (tMap outputs) are optional attributes.
- Connection-level parameters: `MONITOR_CONNECTION` (tFlowMeter), `TRACES_CONNECTION_FILTER`/`TRACES_CONNECTION_ENABLE` (Run view traces), `CONDITION` (RUN_IF Java boolean), `ENABLE_PARALLEL`, `NUMBER_PARALLEL`, `ROUTE_WHEN` expression `CONDITION`, `MERGE` order (unverified exact names for traces/parallel).

`lineStyle` = ordinal of `org.talend.core.model.process.EConnectionType` (confirmed from source):

| lineStyle | enum | connectorName / default label | Category |
|---|---|---|---|
| 0 | `FLOW_MAIN` | `FLOW` (`row`) | row; also used by `REJECT` (0, `REJECT`), `FILTER`, `UNIQUE`, `DUPLICATES`, `OUTPUT` |
| 1 | `ON_SUBJOB_OK` | `SUBJOB_OK` (`OnSubjobOk`) | trigger |
| 2 | `RUN_AFTER` | `AFTER` | legacy trigger (hidden) |
| 3 | `ON_COMPONENT_OK` | `COMPONENT_OK` (`OnComponentOk`) | trigger |
| 4 | `ON_SUBJOB_ERROR` | `SUBJOB_ERROR` | trigger |
| 5 | `ON_COMPONENT_ERROR` | `COMPONENT_ERROR` | trigger |
| 6 | `RUN_IF` | `RUN_IF` (`If`) | trigger, `CONDITION` param |
| 7 | `ITERATE` | `ITERATE` (`iterate`) | iterate |
| 8 | `FLOW_REF` | `LOOKUP` written as `connectorName="FLOW"` into tMap (`row`) | row (lookup) |
| 9 | `TABLE` | `TABLE` | tELT* table link |
| 10 | `FLOW_MERGE` | `MERGE` | tUnite inputs |
| 11 | `ON_ROWS_END` | `ROWS_END` | legacy |
| 12 | `SYNCHRONIZE` | `SYNCHRONIZE` | tParallelize |
| 13 | `PARALLELIZE` | `PARALLELIZE` | tParallelize |
| 14 | `ROUTE` | `ROUTE` (`route`) | Camel |
| 15 | `ROUTE_WHEN` | `ROUTE_WHEN` (`when`) | cMessageRouter |
| 16 | `ROUTE_OTHER` | `ROUTE_OTHER` (`otherwise`) | cMessageRouter |
| 17 | `ROUTE_TRY` | `ROUTE_TRY` | cTry |
| 18 | `ROUTE_CATCH` | `ROUTE_CATCH` | cTry |
| 19 | `ROUTE_FINALLY` | `ROUTE_FINALLY` | cTry |
| 20 | `ROUTE_ENDBLOCK` | `ROUTE_ENDBLOCK` | cTry/cMessageRouter end |
| 21 | `STARTS` | `STARTS` | joblet trigger input |
| 22 | `TABLE_REF` | `TABLE_REF` | tELT* lookup table |

The help.qlik.com Job script reference lists the same numbers for 0,1,3,4,5,6,7,8,9,10,12,13.

### subjob and note

```xml
<subjob>
  <elementParameter field="TEXT" name="UNIQUE_NAME" value="tFileInputDelimited_1" show="false"/>
  <elementParameter field="COLOR" name="SUBJOB_TITLE_COLOR" value="92;131;150" show="false"/>
  <elementParameter field="COLOR" name="SUBJOB_COLOR" value="207;226;236"/>
  <!-- optional: SUBJOB_TITLE, SUBJOB_DISPLAYED (CHECK), COLLAPSED (CHECK) -->
</subjob>
<note opaque="true" posX="100" posY="20" sizeHeight="60" sizeWidth="200" text="Loads the file">
  <elementParameter field="TEXT" name="UNIQUE_NAME" value="Note_1"/>
  <elementParameter field="COLOR" name="BACKGROUND_COLOR" value="255;255;203"/>   <!-- (unverified names) -->
</note>
```

A `<subjob>` exists only for subjobs whose title/colour/collapsed state was customised; the
`UNIQUE_NAME` is the start component of that subjob. Missing `<subjob>` = default rendering.

### tMap nodeData (MapperData)

Model `mapper.ecore` (nsPrefix `TalendMapper`, nsURI `http://www.talend.org/mapper`):

```xml
<nodeData xsi:type="TalendMapper:MapperData">
  <uiProperties shellMaximized="false"/>
  <varTables sizeState="INTERMEDIATE" name="Var" minimized="true">
    <mapperTableEntries name="age" expression="TalendDate.diffDate(TalendDate.getCurrentDate(), row1.Bdate, &quot;yyyy&quot;)" type="id_Integer" nullable="true"/>
  </varTables>
  <outputTables sizeState="INTERMEDIATE" name="op2" reject="false" rejectInnerJoin="false"
      expressionFilter="row1.Major.equals(&quot;ICT&quot;)" activateExpressionFilter="true">
    <mapperTableEntries name="course_name" expression="row3.Cname" type="id_String" nullable="true"/>
  </outputTables>
  <inputTables sizeState="INTERMEDIATE" name="row1" matchingMode="UNIQUE_MATCH" lookupMode="LOAD_ONCE">
    <mapperTableEntries name="Regno" type="id_String" nullable="true"/>
  </inputTables>
  <inputTables sizeState="INTERMEDIATE" name="row2" activateCondensedTool="true" matchingMode="UNIQUE_MATCH"
      lookupMode="LOAD_ONCE" innerJoin="true" persistent="false">
    <mapperTableEntries name="RegNo" expression="row1.Regno" type="id_String" nullable="true" operator="="/>
    <mapperTableEntries name="marks" type="id_Integer" nullable="true"/>
    <globalMapKeysValues name="rowsCount" expression="..." type="id_Integer"/>   <!-- "Reload at each row" keys -->
  </inputTables>
</nodeData>
```

| Element / attribute | Values |
|---|---|
| `inputTables@matchingMode` | `UNIQUE_MATCH` (default), `FIRST_MATCH`, `ALL_MATCHES`, `ALL_ROWS` (no join keys) |
| `inputTables@lookupMode` | `LOAD_ONCE` (default), `RELOAD` ("Reload at each row"), `CACHE_OR_RELOAD` ("Reload at each row (cache)") |
| `inputTables@innerJoin` | `true` = Inner Join; absent/false = Left Outer Join |
| `inputTables@persistent` | "Store temp data" (tMap `TEMPORARY_DATA_DIRECTORY`) |
| `inputTables@expressionFilter` + `activateExpressionFilter` | input filter (lookup only) |
| `mapperTableEntries` in an input table with `expression` + `operator` | join key: expression against the main flow, operator one of `=`, `<>`, `<`, `<=`, `>`, `>=` (Operator enum literals) |
| `outputTables@reject` | "Catch lookup inner join reject" is `rejectInnerJoin`; "Catch output reject" is `reject` |
| `outputTables@isErrorRejectTable` | the die-on-error `ErrorReject` table (adds `errorMessage`, `errorStackTrace` columns) |
| `outputTables@isJoinTableOf` | name of the output table this one is a "join" (All matches duplicate) of |
| `sizeState` | `MINIMIZED`, `INTERMEDIATE`, `MAXIMIZED` |
| `activateCondensedTool`, `activateColumnNameFilter`, `columnNameFilter`, `id` | UI state |

The tMap `<node>` itself keeps parameters `MAP` (field EXTERNAL, value ""), `LINK_STYLE`
(`AUTO`/`BEZIER_CURVE`/`LINE`), `TEMPORARY_DATA_DIRECTORY`, `ROWS_BUFFER_SIZE` (2000000),
`DIE_ON_ERROR`, `LKUP_PARALLELIZE`, `ENABLE_AUTO_CONVERT_TYPE`,
`CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL`, `PREVIEW` (IMAGE, name of a `.bmp` under the
project `images/`? folder, diff noise). The `<metadata>` children of the tMap node repeat
every output table schema (`connector="FLOW" name="<outTable>"`), and must agree with
`mapperTableEntries` names/types.

### tXMLMap nodeData (XmlMapData)

Namespace `xmlns:TalendXMLMap="http://www.talend.org/xmlmap"`, `xsi:type="TalendXMLMap:XmlMapData"`.

```xml
<nodeData xsi:type="TalendXMLMap:XmlMapData">
  <inputTrees name="row2" matchingMode="UNIQUE_MATCH" lookupMode="LOAD_ONCE">
    <nodes name="payload" expression="" type="id_Document" nullable="true"
        outgoingConnections="//@node.2/@nodeData/@connections.1" xpath="row2/payload">
      <children name="air:getAirportInformationByISOCountryCode" type="id_String" xpath="row2.payload:/air:getAirportInformationByISOCountryCode">
        <children name="air:CountryAbbrviation" type="id_String" loop="true"
            outgoingConnections="//@node.2/@nodeData/@connections.2"
            lookupOutgoingConnections="//@node.2/@nodeData/@connections.0"
            xpath="row2.payload:/air:getAirportInformationByISOCountryCode/air:CountryAbbrviation"/>
      </children>
    </nodes>
  </inputTrees>
  <outputTrees name="out1" allInOne="false" ...>
    <nodes name="root" type="id_Document" ...> <children ... expression="[row2.payload:/.../air:CountryAbbrviation]" .../> </nodes>
  </outputTrees>
  <varTables .../>
  <connections sourceNode="//@node.2/@nodeData/@inputTrees.0/@nodes.0/@children.0/@children.0" targetNode="..."/>
</nodeData>
```

Key points: tree nodes carry `xpath`, `loop="true"`, `group="true"`, `aggregate`,
`optional`, `nodeType` (`ELEMENT`/`ATTRIBUT`/`NAME_SPACE`), `filterOutGoingConnections`;
connections are EMF intra-document references (`//@node.N/@nodeData/@connections.K`),
where `N` is the 0-based index of the tXMLMap `<node>` in the file. Inserting or removing
any `<node>` before it breaks every such reference: never reorder nodes by hand in a job
that contains tXMLMap.

### Minimal hand-built Standard job item (tFileInputDelimited -> tMap -> tLogRow)

Hand-built from the schema and from Studio-produced items above; NOT round-tripped through
Studio import in this build. Only the hidden job-level parameters that Studio writes by
default are included; Studio re-adds any it misses on first save.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<talendfile:ProcessType xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:TalendMapper="http://www.talend.org/mapper"
    xmlns:talendfile="platform:/resource/org.talend.model/model/TalendFile.xsd"
    defaultContext="Default" jobType="Standard">
  <context confirmationNeeded="false" name="Default">
    <contextParameter comment="" name="file" prompt="file?" promptNeeded="false" type="id_String" value="/tmp/in.csv"/>
  </context>
  <parameters>
    <elementParameter field="CLOSED_LIST" name="LOG4J_RUN_LEVEL" value="Info" show="false"/>
    <elementParameter field="TEXT" name="SCREEN_OFFSET_X" value="0" show="false"/>
    <elementParameter field="TEXT" name="SCREEN_OFFSET_Y" value="0" show="false"/>
    <elementParameter field="CHECK" name="IMPLICITCONTEXT_USE_PROJECT_SETTINGS" value="true" show="false"/>
    <elementParameter field="CHECK" name="STATANDLOG_USE_PROJECT_SETTINGS" value="true" show="false"/>
    <elementParameter field="CHECK" name="MULTI_THREAD_EXECATION" value="false"/>
    <elementParameter field="TEXT" name="PARALLELIZE_UNIT_SIZE" value="25000" show="false"/>
    <elementParameter field="CHECK" name="IMPLICIT_TCONTEXTLOAD" value="false"/>
    <elementParameter field="CHECK" name="ON_STATCATCHER_FLAG" value="false"/>
    <elementParameter field="CHECK" name="ON_LOGCATCHER_FLAG" value="false"/>
    <elementParameter field="CHECK" name="ON_METERCATCHER_FLAG" value="false"/>
    <routinesParameter id="_5GzN0PBuEfCv4Ytt6y8EMw" name="TalendDate"/>
  </parameters>
  <node componentName="tFileInputDelimited" componentVersion="0.102" offsetLabelX="0" offsetLabelY="0" posX="96" posY="96">
    <elementParameter field="TEXT" name="UNIQUE_NAME" value="tFileInputDelimited_1" show="false"/>
    <elementParameter field="TECHNICAL" name="PROPERTY:PROPERTY_TYPE" value="BUILT_IN"/>
    <elementParameter field="TECHNICAL" name="PROPERTY:REPOSITORY_PROPERTY_TYPE" value="" show="false"/>
    <elementParameter field="TECHNICAL" name="SCHEMA:SCHEMA_TYPE" value="BUILT_IN" show="false"/>
    <elementParameter field="TECHNICAL" name="SCHEMA:REPOSITORY_SCHEMA_TYPE" value="" show="false"/>
    <elementParameter field="FILE" name="FILENAME" value="context.file"/>
    <elementParameter field="CHECK" name="CSV_OPTION" value="false"/>
    <elementParameter field="TEXT" name="ROWSEPARATOR" value="&quot;\n&quot;"/>
    <elementParameter field="TEXT" name="FIELDSEPARATOR" value="&quot;;&quot;"/>
    <elementParameter field="TEXT" name="HEADER" value="1"/>
    <elementParameter field="TEXT" name="FOOTER" value="0"/>
    <elementParameter field="TEXT" name="LIMIT" value=""/>
    <elementParameter field="CHECK" name="REMOVE_EMPTY_ROW" value="true"/>
    <elementParameter field="CHECK" name="UNCOMPRESS" value="false"/>
    <elementParameter field="CHECK" name="DIE_ON_ERROR" value="false"/>
    <elementParameter field="CHECK" name="ADVANCED_SEPARATOR" value="false"/>
    <elementParameter field="CHECK" name="TRIMALL" value="false"/>
    <elementParameter field="CHECK" name="CHECK_FIELDS_NUM" value="false"/>
    <elementParameter field="CHECK" name="CHECK_DATE" value="false"/>
    <elementParameter field="ENCODING_TYPE" name="ENCODING" value="&quot;UTF-8&quot;"/>
    <elementParameter field="TECHNICAL" name="ENCODING:ENCODING_TYPE" value="UTF-8"/>
    <elementParameter field="CHECK" name="SPLITRECORD" value="false"/>
    <elementParameter field="CHECK" name="ENABLE_DECODE" value="false"/>
    <elementParameter field="TEXT" name="CONNECTION_FORMAT" value="row"/>
    <metadata connector="FLOW" name="tFileInputDelimited_1">
      <column comment="" key="false" length="-1" name="id" nullable="true" pattern="" precision="-1" sourceType="" type="id_Integer" originalLength="-1" usefulColumn="true"/>
      <column comment="" key="false" length="-1" name="name" nullable="true" pattern="" precision="-1" sourceType="" type="id_String" originalLength="-1" usefulColumn="true"/>
      <column comment="" key="false" length="-1" name="birth" nullable="true" pattern="&quot;yyyy-MM-dd&quot;" precision="-1" sourceType="" type="id_Date" originalLength="-1" usefulColumn="true"/>
    </metadata>
    <metadata connector="REJECT" label="REJECT" name="REJECT">
      <column comment="" key="false" length="-1" name="id" nullable="true" pattern="" precision="-1" sourceType="" type="id_Integer" originalLength="-1" usefulColumn="true"/>
      <column comment="" key="false" length="-1" name="name" nullable="true" pattern="" precision="-1" sourceType="" type="id_String" originalLength="-1" usefulColumn="true"/>
      <column comment="" key="false" length="-1" name="birth" nullable="true" pattern="&quot;yyyy-MM-dd&quot;" precision="-1" sourceType="" type="id_Date" originalLength="-1" usefulColumn="true"/>
      <column defaultValue="" key="false" length="255" name="errorCode" nullable="true" precision="0" sourceType="" type="id_String" originalLength="-1" usefulColumn="true"/>
      <column defaultValue="" key="false" length="255" name="errorMessage" nullable="true" precision="0" sourceType="" type="id_String" originalLength="-1" usefulColumn="true"/>
    </metadata>
  </node>
  <node componentName="tMap" componentVersion="2.1" offsetLabelX="0" offsetLabelY="0" posX="320" posY="96">
    <elementParameter field="TEXT" name="UNIQUE_NAME" value="tMap_1" show="false"/>
    <elementParameter field="EXTERNAL" name="MAP" value=""/>
    <elementParameter field="CLOSED_LIST" name="LINK_STYLE" value="AUTO"/>
    <elementParameter field="DIRECTORY" name="TEMPORARY_DATA_DIRECTORY" value=""/>
    <elementParameter field="CHECK" name="DIE_ON_ERROR" value="true" show="false"/>
    <elementParameter field="CHECK" name="LKUP_PARALLELIZE" value="false" show="false"/>
    <elementParameter field="CHECK" name="ENABLE_AUTO_CONVERT_TYPE" value="false" show="false"/>
    <elementParameter field="TEXT" name="ROWS_BUFFER_SIZE" value="2000000"/>
    <elementParameter field="CHECK" name="CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL" value="true"/>
    <elementParameter field="TEXT" name="CONNECTION_FORMAT" value="row"/>
    <metadata connector="FLOW" label="out1" name="out1">
      <column comment="" key="false" length="-1" name="id" nullable="true" pattern="" precision="-1" sourceType="" type="id_Integer" originalLength="-1" usefulColumn="true"/>
      <column comment="" key="false" length="-1" name="upper_name" nullable="true" pattern="" precision="-1" sourceType="" type="id_String" originalLength="-1" usefulColumn="true"/>
      <column comment="" key="false" length="-1" name="age" nullable="true" pattern="" precision="-1" sourceType="" type="id_Integer" originalLength="-1" usefulColumn="true"/>
    </metadata>
    <nodeData xsi:type="TalendMapper:MapperData">
      <uiProperties shellMaximized="false"/>
      <varTables sizeState="INTERMEDIATE" name="Var" minimized="true">
        <mapperTableEntries name="age" expression="TalendDate.diffDate(TalendDate.getCurrentDate(), row1.birth, &quot;yyyy&quot;)" type="id_Integer" nullable="true"/>
      </varTables>
      <outputTables sizeState="INTERMEDIATE" name="out1" expressionFilter="row1.id &gt; 0" activateExpressionFilter="true">
        <mapperTableEntries name="id" expression="row1.id" type="id_Integer" nullable="true"/>
        <mapperTableEntries name="upper_name" expression="row1.name == null ? null : row1.name.toUpperCase()" type="id_String" nullable="true"/>
        <mapperTableEntries name="age" expression="Var.age" type="id_Integer" nullable="true"/>
      </outputTables>
      <inputTables sizeState="INTERMEDIATE" name="row1" matchingMode="ALL_ROWS" lookupMode="LOAD_ONCE">
        <mapperTableEntries name="id" type="id_Integer" nullable="true"/>
        <mapperTableEntries name="name" type="id_String" nullable="true"/>
        <mapperTableEntries name="birth" type="id_Date" nullable="true"/>
      </inputTables>
    </nodeData>
  </node>
  <node componentName="tLogRow" componentVersion="0.101" offsetLabelX="0" offsetLabelY="0" posX="544" posY="96">
    <elementParameter field="TEXT" name="UNIQUE_NAME" value="tLogRow_1" show="false"/>
    <elementParameter field="RADIO" name="BASIC_MODE" value="false"/>
    <elementParameter field="RADIO" name="TABLE_PRINT" value="true"/>
    <elementParameter field="RADIO" name="VERTICAL" value="false"/>
    <elementParameter field="TEXT" name="FIELDSEPARATOR" value="&quot;|&quot;" show="false"/>
    <elementParameter field="CHECK" name="PRINT_HEADER" value="false" show="false"/>
    <elementParameter field="CHECK" name="PRINT_CONTENT_WITH_LOG4J" value="true"/>
    <elementParameter field="TEXT" name="CONNECTION_FORMAT" value="row"/>
    <metadata connector="FLOW" label="out1" name="tLogRow_1">
      <column comment="" key="false" length="-1" name="id" nullable="true" pattern="" precision="-1" sourceType="" type="id_Integer" originalLength="-1" usefulColumn="true"/>
      <column comment="" key="false" length="-1" name="upper_name" nullable="true" pattern="" precision="-1" sourceType="" type="id_String" originalLength="-1" usefulColumn="true"/>
      <column comment="" key="false" length="-1" name="age" nullable="true" pattern="" precision="-1" sourceType="" type="id_Integer" originalLength="-1" usefulColumn="true"/>
    </metadata>
  </node>
  <connection connectorName="FLOW" label="row1" lineStyle="0" metaname="tFileInputDelimited_1" offsetLabelX="0" offsetLabelY="0" source="tFileInputDelimited_1" target="tMap_1">
    <elementParameter field="CHECK" name="MONITOR_CONNECTION" value="false"/>
    <elementParameter field="TEXT" name="UNIQUE_NAME" value="row1" show="false"/>
  </connection>
  <connection connectorName="FLOW" label="out1" lineStyle="0" metaname="out1" offsetLabelX="0" offsetLabelY="0" source="tMap_1" target="tLogRow_1">
    <elementParameter field="CHECK" name="MONITOR_CONNECTION" value="false"/>
    <elementParameter field="TEXT" name="UNIQUE_NAME" value="out1" show="false"/>
  </connection>
  <subjob>
    <elementParameter field="TEXT" name="UNIQUE_NAME" value="tFileInputDelimited_1" show="false"/>
    <elementParameter field="COLOR" name="SUBJOB_TITLE_COLOR" value="92;131;150" show="false"/>
    <elementParameter field="COLOR" name="SUBJOB_COLOR" value="207;226;236"/>
  </subjob>
</talendfile:ProcessType>
```

Pair it with a `.properties` (section 3) whose `Property@label="<JobName>"`,
`Property@version="0.1"` and `<process href="<JobName>_0.1.item#/"/>`, then import via
File > Import items (from a folder) and open: Studio will complain about anything it
dislikes in the Problems view, and will add missing default parameters on save.

## 3. Property files, contexts, routines, metadata, joblets

### `<Item>_<M>.<m>.properties`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:TalendProperties="http://www.talend.org/properties">
  <TalendProperties:Property xmi:id="_L3nIYe0TEeWFQopXQquZvw" id="_L3nIYO0TEeWFQopXQquZvw" label="Testjob"
      purpose="" description="" creationDate="2016-03-18T15:10:36.134+0100" modificationDate="2016-03-18T15:19:19.532+0100"
      version="0.1" statusCode="" item="_L3nIY-0TEeWFQopXQquZvw" displayName="Testjob" maxInformationLevel="WARN">
    <author href="../../talend.project#_3rCW0e0REeWFQopXQquZvw"/>
    <additionalProperties xmi:id="..." key="created_product_fullname" value="Talend Open Studio for Data Integration"/>
    <additionalProperties xmi:id="..." key="created_product_version" value="7.1.1.20181026_1147"/>
    <additionalProperties xmi:id="..." key="created_date" value="2014-01-15T12:18:25.991+1100"/>
    <additionalProperties xmi:id="..." key="modified_product_fullname" value="..."/>
    <additionalProperties xmi:id="..." key="modified_product_version" value="8.0.1.20250218_0945-patch"/>
    <additionalProperties xmi:id="..." key="modified_date" value="2025-05-23T16:30:00.597+0100"/>
    <additionalProperties xmi:id="..." key="import_product_fullname" value="..."/>   <!-- set on Import items -->
    <additionalProperties xmi:id="..." key="import_product_version" value="..."/>
    <additionalProperties xmi:id="..." key="import_date" value="..."/>
    <additionalProperties xmi:id="..." key="item_key" value="988dfacb0744...sha256"/>   <!-- 8.0 R2024+ content hash -->
    <informations xmi:id="..." level="WARN" text="The import java.io.File is never used"/>  <!-- compile problems -->
  </TalendProperties:Property>
  <TalendProperties:ItemState xmi:id="_L3nIYu0TEeWFQopXQquZvw" path="demo" locked="true" lockDate="2016-03-18T15:10:36.337+0100" deleted="false">
    <locker href="../../talend.project#_3rCW0e0REeWFQopXQquZvw"/>
  </TalendProperties:ItemState>
  <TalendProperties:ProcessItem xmi:id="_L3nIY-0TEeWFQopXQquZvw" property="_L3nIYe0TEeWFQopXQquZvw" state="_L3nIYu0TEeWFQopXQquZvw">
    <process href="Testjob_0.1.item#/"/>
  </TalendProperties:ProcessItem>
</xmi:XMI>
```

| Element / attr | Notes |
|---|---|
| `Property@id` | the repository object id, stable across versions of the same item; this is what `PROPERTY:REPOSITORY_PROPERTY_TYPE`, `routinesParameter@id`, `PROCESS:PROCESS_TYPE_PROCESS`, `repositoryContextId` and `jobInfo.properties jobId` point at |
| `Property@xmi:id` / `item` / `ItemState@xmi:id` | intra-file XMI ids; must match the `property=` / `state=` back-references |
| `Property@version` | `M.m`; must equal the version in both file names |
| `statusCode` | job status (Project Settings > Status) |
| `author href` | `../../talend.project#<User xmi:id>`; the number of `../` equals the folder depth below the project |
| `ItemState@path` | repository sub-folder (empty for root); `deleted="true"` = in Recycle bin; `locked`/`lockDate`/`locker` = TAC lock |
| `*Item` element | the typed item, with one `href` into the `.item` file: `#/` = root of a single-root file, `#/0`, `#/1` = N-th root element of an `xmi:XMI` wrapper, `#_<xmi:id>` = element by id |
| ids | classic EMF ids are `_` + 22 base64url chars (UUID-based, e.g. `_L3nIYe0TEeWFQopXQquZvw`); 8.0 R2024+ Studios write RFC UUIDs (`9931e17c-8ffc-4267-8375-ea1d9c19f372`) with `_item`/`_state` suffixes for the sibling elements. Both are accepted. |

Item element types (namespace `TalendProperties` unless noted) and their `href` child:

| Item type | Folder | href child | .item root |
|---|---|---|---|
| `ProcessItem` | process/, process_mr/, process_storm/ | `process` | `talendfile:ProcessType` |
| `JobletProcessItem` | joblets/ | `jobletProcess` (`#/0`) + `icon` (`#/1`) | `xmi:XMI` wrapper with `model:JobletProcess` (xmlns:model=`http://www.talend.com/joblet.ecore`) and an icon element |
| `ContextItem` (`defaultContext="Default"`) | context/ | one `context` per group (`#/0`, `#/1`...) | `xmi:XMI` with n `talendfile:ContextType` |
| `RoutineItem` (`builtIn="true"` for system) | code/routines/ | `content` (`#/`) | raw Java source (see below) |
| `BeanItem` | code/beans/ | `content` | raw Java |
| `DatabaseConnectionItem` (`typeName="PostgreSQL"`) | metadata/connections/ | `connection` (`#_<id>`) | `xmi:XMI` with `TalendMetadata:DatabaseConnection` |
| `DelimitedFileConnectionItem`, `PositionalFileConnectionItem`, `RegexpFileConnectionItem`, `XmlFileConnectionItem`, `ExcelFileConnectionItem`, `LdifFileConnectionItem`, `JSONFileConnectionItem`, `GenericSchemaConnectionItem`, `LDAPSchemaConnectionItem`, `WSDLSchemaConnectionItem`, `SalesforceSchemaConnectionItem`, `FTPConnectionItem`, `SAPConnectionItem`, `HadoopClusterConnectionItem`, `NoSQLConnectionItem`, `MDMConnectionItem` | metadata/* | `connection` | `TalendMetadata:<X>Connection` (names from memory except Database/DelimitedFile/GenericSchema) |
| `CamelProperties:CamelProcessItem` (xmlns:CamelProperties=`http://www.talend.org/CamelProperties`) | routes/ | `process` | `talendfile:ProcessType` with cXXX nodes; attr `springContent` = escaped Spring XML |
| `Services:ServiceItem` (xmlns:Services=`http://www.talend.org/Services`, `referenceResources`) | services/ | `connection` | `xmi:XMI` with service connection + sibling `.wsdl` |
| `TestContainerItem` | test cases of a job (stored next to/under the job; folder unverified) | `process` | ProcessType with tCreateTemporaryFile/tFileInput* test nodes |
| `SQLPatternItem`, `DocumentationItem`, `BusinessProcessItem`, `SnippetItem`, `HeaderFooterItem`, `LinkDocumentationItem`, `RulesItem`, `ValidationRulesConnectionItem` | respective folders | `content`/`link` | varies |

### `.screenshot`

`<Job>_<M>.<m>.screenshot` (6.x+), one element per screenshot key:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<talendfile:ScreenshotsMap xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI"
    xmlns:talendfile="platform:/resource/org.talend.model/model/TalendFile.xsd"
    key="process" value="iVBORw0KGgoAAAANSUhEUg...base64 PNG..."/>
```

Keys: `process` (job canvas), `tMap_1` etc. for mapper previews (unverified). Pure diff
noise; safe to delete (Studio regenerates on open). Treat as binary in Git.

### Context group `.item`

```xml
<xmi:XMI xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:talendfile="platform:/resource/org.talend.model/model/TalendFile.xsd">
  <talendfile:ContextType confirmationNeeded="false" name="Default">
    <contextParameter comment="" name="MySQL_DWH_Login" prompt="MySQL_DWH_Login?" promptNeeded="false" repositoryContextId="built-in" type="id_String" value="adnadm"/>
    <contextParameter comment="" name="MySQL_DWH_Password" prompt="MySQL_DWH_Password?" promptNeeded="false" repositoryContextId="built-in" type="id_Password" value="enc:system.encryption.key.v1:1ZZpx2OAA/3y5VVYBV8ewni+LgmF+o/AKKMaIiHf+ON+SAZyxLWQCCZQ"/>
  </talendfile:ContextType>
  <talendfile:ContextType confirmationNeeded="false" name="Deployment"> ... </talendfile:ContextType>
</xmi:XMI>
```

The `.properties` `ContextItem@defaultContext` names the default group; `<context href="X_0.1.item#/0"/>`
entries count the groups. Context groups exported from a metadata wizard ("Export as context")
name variables `<ConnName>_<Field>` (`DTW_TR_V2_Port`, `_Login`, `_Password`, `_Schema`, `_AdditionalParams`).

### Routines

`code/routines/<Name>_<M>.<m>.item` is the raw `.java` source (not XML), always
`package routines;` with the class name = item label. The Javadoc of each public static method
must carry the Talend tags so it appears in the expression builder:

```java
package routines;
public class MyRoutine {
    /**
     * helloExample: not return value, only print "hello" + message.
     *
     * {talendTypes} String
     * {Category} User Defined
     * {param} string("world") input: The string need to be printed.
     * {example} helloExample("world") # hello world !.
     */
    public static void helloExample(String message) { ... }
}
```

`{talendTypes}` must be one of `String, char | Character, long | Long, int | Integer,
boolean | Boolean, byte | Byte, Date, double | Double, float | Float, Object, short | Short`
(the comment template in the generated routine says so). Built-in routines live in
`code/routines/system/` with `RoutineItem@builtIn="true"`; do not edit them. User routine
dependencies on extra jars are stored as `<imports>` in the properties (7.x: `IMPORT` entries
with `MODULE`, `MVN` coordinates `mvn:org.talend.libraries/<jar>/6.0.0/jar`) (unverified exact element).

### Metadata connection items

Database connection (`metadata/connections/<Name>_<ver>.item`):

```xml
<xmi:XMI xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:TalendMetadata="http://www.talend.org/metadata/connection/2010"
    xmlns:orgomg.cwm.resource.relational="http:///orgomg/cwm/resource/relational.ecore">
  <TalendMetadata:DatabaseConnection xmi:id="_jTdKoH16EeOTGfN6m9kVCA" name="DestinationDb" id="_jTauYH16EeOTGfN6m9kVCA" label="DestinationDb"
      dataPackage="_OWIlwFYJEeurK_q1FZygFg" ContextMode="true" ContextId="_i5o8cH16EeOTGfN6m9kVCA" contextName="Default"
      DatabaseType="PostgreSQL" DriverClass="org.postgresql.Driver" URL="jdbc:postgresql://host:5432/harvest?ssl=true"
      dbVersionString="PRIOR_TO_V9" Port="context.Destination_Port" Username="context.Destination_Login"
      Password="context.Destination_Password" ServerName="context.Destination_Server" SID="context.Destination_Database"
      DbmsId="postgres_id" ProductId="POSTGRESQL" AdditionalParams="" StandardSQL="true" SQLMode="false" UiSchema="context.Destination_Schema">
    <taggedValue xmi:id="..." tag="Is Conn Need Reload" value="false"/>
    <taggedValue xmi:id="..." tag="DB IdentifierQuoteString" value="&quot;"/>
    <taggedValue xmi:id="..." tag="DB ProductName" value="PostgreSQL"/>
    <taggedValue xmi:id="..." tag="DB ProductVersion" value="9.6.10"/>
  </TalendMetadata:DatabaseConnection>
  <orgomg.cwm.resource.relational:Catalog xmi:id="_OWIlwFYJEeurK_q1FZygFg" name="harvest" dataManager="_jTdKoH16EeOTGfN6m9kVCA">
    <ownedElement xsi:type="orgomg.cwm.resource.relational:Schema" xmi:id="..." name="nrmn">
      <ownedElement xsi:type="TalendMetadata:TdTable" xmi:id="..." name="customer" id="_tbl..." label="customer" tableType="TABLE">
        <feature xsi:type="TalendMetadata:TdColumn" xmi:id="..." name="id" label="id" length="10" precision="0" talendType="id_Integer" sourceType="int4" nullable="false" key="true">
          <sqlDataType xmi:id="..." name="int4" javaDataType="4"/>
          <initialValue xmi:id="..." body=""/>
        </feature>
      </ownedElement>
    </ownedElement>
  </orgomg.cwm.resource.relational:Catalog>
</xmi:XMI>
```

- `ContextMode="true"` + `ContextId` = connection was exported to a context group; every field then holds `context.<var>`.
- `Password` is encrypted when not contextualised (section 4).
- `DbmsId` = mapping file id (`postgres_id`, `mysql_id`, `oracle_id`, `mssql_id`, `generic_id`... from `mapping_*.xml` in Studio); `ProductId` = `EDatabaseTypeName` code (`POSTGRESQL`, `MYSQL`, `ORACLEFORSID`, `MSSQL`, `SNOWFLAKE`, `JDBC`...). `dbVersionString` = `EDatabaseVersion4Drivers` code (`MYSQL_8`, `ORACLE_12`, `PRIOR_TO_V9`, `V9_X`...).
- Tables/columns are CWM objects (`TdTable`/`TdColumn`/`TdView`, `sqlDataType`, `talendType`). Table/column ids are what `SCHEMA:REPOSITORY_SCHEMA_TYPE` references (`<connection property id> - <table label>`).

Delimited file (`metadata/fileDelimited/`): `TalendMetadata:DelimitedFileConnection` with
`FilePath`, `Encoding`, `FieldSeparatorType="Comma"`, `FieldSeparatorValue="&quot;,&quot;"`,
`RowSeparatorType`, `RowSeparatorValue="&quot;\n&quot;"`, `UseHeader="true"`, `HeaderValue="1"`,
`UseFooter`, `FooterValue`, `UseLimit`, `LimitValue`, `FirstLineCaption="true"`, `Csv`
(CSV option), `EscapeChar`, `TextEnclosure`, `RemoveEmptyRow`, `SplitRecord`, `Server`; then
an `orgomg.cwm.resource.record:RecordFile` dataPackage with `ownedElement
xsi:type="TalendMetadata:MetadataTable" name="metadata"` and `feature
xsi:type="TalendMetadata:MetadataColumn" label= length= precision= talendType= pattern= nullable= key=`.

Generic schema (`metadata/genericSchema/`): `TalendMetadata:GenericSchemaConnection` +
`TalendMetadata:GenericPackage` with one `MetadataTable name="metadata"`.

Hadoop cluster (`metadata/hadoopcluster/`): `TalendMetadata:HadoopClusterConnection` with
`distribution`, `dfVersion`, `nameNodeURI`, `jobTrackerURI`, `enableKerberos`, `principal`,
`useKeytab`, `keytab`, `userName`, `group`, `useCustomConfs`, `parameters` map (unverified attrs).

### Joblet `.item`

```xml
<xmi:XMI xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:TalendProperties="http://www.talend.org/properties" xmlns:model="http://www.talend.com/joblet.ecore">
  <model:JobletProcess defaultContext="Default" jobType="Standard">
    <context .../> <parameters> ...same as job plus STARTABLE (CHECK), ICONSELECTION (ICON_SELECTION)... </parameters>
    <node componentName="tJobletInput" .../> <node componentName="tJobletOutput" .../> <node componentName="tJobletTriggerInput" .../> ...
  </model:JobletProcess>
  <TalendProperties:ByteArray xmi:id="..." innerContent="iVBOR...icon png..."/>   <!-- #/1 = icon (element name unverified) -->
</xmi:XMI>
```

Jobs that use a joblet contain a `<node componentName="<JobletName>">` whose
`componentVersion` is the joblet version and whose parameters are the joblet's context
variables; `nodeContainer` elements track the expanded joblet box.

## 4. Password encryption in items

| Era | Storage | Mechanism |
|---|---|---|
| <= 7.2 (and generated-code `routines.system.PasswordEncryptUtil`) | bare Base64, e.g. `value="0RMsyjmybrE="` | DES/ECB with the fixed key `"Talend-Key"` (`DESKeySpec`, `Cipher.getInstance("DES")`), UTF-8, Base64. Deterministic, trivially reversible, same for every install. `0RMsyjmybrE=` is the encryption of the empty string. |
| 7.3 / 8.0 Studio items, `.properties`, context files | `enc:system.encryption.key.v1:<base64 iv+ciphertext>` | AES-256-GCM (help.qlik.com: "AES GCM 256") with the key named `system.encryption.key.v1` from `<Studio>/configuration/studio.keys` (file created on first launch with `system.encryption.key.v1` and `routine.encryption.key.v1`). Everyone working on the same project (and TAC/JobServer/CommandLine building it) must share the same `studio.keys`. |
| Passwords baked into generated Java | `routines.system.PasswordEncryptUtil.decryptPassword("enc:routine.encryption.key.v1:...")` | the `routine.encryption.key.v1` default cannot be changed; it ships inside the runtime jars, so a built job decrypts its own passwords anywhere. |
| TAC / Talend Runtime | same `enc:` scheme with their own key files | Runtime: `-Dencryption.keys.file=<path>` via `EXTRA_JAVA_OPTS` (file example `keys.properties`), deployed artifacts use the last key in the file. TAC: `configuration.properties` `encryption.keys.file`? (unverified) |

Key rotation (8.0 docs): append `system.encryption.key.v2=<base64 32 bytes>` to
`studio.keys`, restart; new saves use the highest version, old values are still read with
v1; "Rotate encryption keys" exists in Project Settings (unverified label). The default v1
value is the same in every Studio download of a given version, so `enc:system.encryption.key.v1:`
values from a stock Studio are decryptable by any other stock Studio; treat them as obfuscated,
not secure. `-Dtalend.security.allowUnsafeEncryptionKey` is not a confirmed property (unverified).

Practical: never hand-edit an `enc:` value; set the field to `context.password` in the item
(no encryption applies to a context reference) and keep the real secret in the context file /
TMC parameter. In exported `contexts/<Ctx>.properties`, `id_Password` values are written as
`enc:routine.encryption.key.v1:...` by 7.3+/8.0 (older: DES Base64); the job decrypts them in
`ContextProperties.synchronizeContext()`/`PasswordEncryptUtil`.

## 5. Jobscript

Jobscript is Studio's textual job format (Repository > Code > Job Scripts). The same text is
shown read-only in the **Jobscript** tab under the job designer (next to Designer / Code).
Right-click a Job Script > **Export Job Script** writes `<Name>.jobscript`; right-click a job
> Generate Job Script (or drag a job onto Job Scripts) creates one from a job; right-click a Job
Script > Generate Job creates the job (menu labels unverified). The grammar is documented in
the "Talend Job Script Reference Guide" (7.2, 7.3, 8.0). Items are not Jobscript: Studio
stores `.item` XML; Jobscript is a derived view.

Confirmed shape (from an 8.0 export, `SCRIPT_VERSION=4.2`):

```
SCRIPT_VERSION=4.2,
JobType= Standard,
DEFAULT_CONTEXT: Default,
ContextType {
	NAME: Default
	addContextParameter {
		NAME: "file",
		TYPE: "id_String",
		VALUE: "\"/tmp/in.csv\"",
		COMMENT: "",
		PROMPT: "file?",
		REPOSITORYCONTEXTID: "\"\"",
		INTERNALID: "_3WurYEgYEe61saTaFxjVuw"
	}
}
addParameters {
	addElementParameters {
		LOG4J_RUN_LEVEL : "Info",
		SCREEN_OFFSET_X : "0",
		IMPLICITCONTEXT_USE_PROJECT_SETTINGS : "true",
		STATANDLOG_USE_PROJECT_SETTINGS : "true",
		MULTI_THREAD_EXECATION : "false",
		PARALLELIZE_UNIT_SIZE : "25000",
		IMPLICIT_TCONTEXTLOAD : "false",
		OVERRIDE_ENCODING_IN_EXTRA:ENCODING_TYPE : "ISO-8859-15",
		PASS_IMPLICIT_CONTEXT : "enc:system.encryption.key.v1:KpB8Q...",
		ON_STATCATCHER_FLAG : "false"
	}
}
addComponent {
	setComponentDefinition {
		TYPE: "tFileInputDelimited",
		NAME: "tFileInputDelimited_1",
		POSITION: 160, 192,
		SIZE: 32, 32,
		OFFSETLABEL: 0, 0
	}
	setSettings {
		FILENAME : "\"/tmp/in.csv\"",
		ROWSEPARATOR : "\"\\n\"",
		FIELDSEPARATOR : "\";\"",
		HEADER : "1",
		LABEL : "Read CSV",
		CONNECTION_FORMAT : "row"
	}
	addSchema {
		NAME: "tFileInputDelimited_1",
		CONNECTOR: "FLOW",
		LABEL: "metadata"
		addColumn {
			NAME: "id",
			TYPE: "id_Integer",
			NULLABLE: true,
			LENGTH: 0,
			COMMENT: "",
			PATTERN: "\"dd-MM-yyyy\"",
			PRECISION: 0,
			ORIGINALLEHGTH: -1
		}
	}
	addSchema { NAME: "REJECT", CONNECTOR: "REJECT", LABEL: "metadata" addColumn { ... } }
}
addComponent {
	setComponentDefinition { TYPE: "tMap", NAME: "tMap_1", POSITION: 352, 192, SIZE: 32, 32, OFFSETLABEL: 0, 0 }
	setSettings { LINK_STYLE : "AUTO", ROWS_BUFFER_SIZE : "2000000", DIE_ON_ERROR : "true", CONNECTION_FORMAT : "row" }
	addSchema { NAME: "out1", CONNECTOR: "FLOW" addColumn { NAME: "id", TYPE: "id_Integer", NULLABLE: true } }
	addMapperData {
		addInputTable { NAME: "row1", SIZESTATE: "INTERMEDIATE", MATCHINGMODE: "ALL_ROWS", LOOKUPMODE: "LOAD_ONCE"
			addEntry { NAME: "id", TYPE: "id_Integer", NULLABLE: true } }
		addVarTable { NAME: "Var", SIZESTATE: "INTERMEDIATE" }
		addOutputTable { NAME: "out1", SIZESTATE: "INTERMEDIATE", REJECT: false, REJECTINNERJOIN: false
			addEntry { NAME: "id", EXPRESSION: "row1.id", TYPE: "id_Integer", NULLABLE: true } }
	}
}
addConnection {
	TYPE: "FLOW",
	NAME: "row1",
	LINESTYLE: 0,
	METANAME: "tFileInputDelimited_1",
	SOURCE: "tFileInputDelimited_1",
	TARGET: "tMap_1",
	OFFSETLABEL: 0, 0,
	MONITOR_CONNECTION : "false"
}
addConnection {
	TYPE: "SUBJOB_OK",
	NAME: "OnSubjobOk",
	LINESTYLE: 1,
	METANAME: "tFileInputDelimited_1",
	SOURCE: "tFileInputDelimited_1",
	TARGET: "tLogRow_2",
	OFFSETLABEL: 0, 0,
}
addSubjob {
	NAME: "tFileInputDelimited_1"
	SUBJOB_TITLE_COLOR : "92;131;150",
	SUBJOB_COLOR : "207;226;236"
}
```

Rules and quirks:
- Keys are the same `elementParameter@name`s as the XML; values are strings with Java quoting escaped once more (`"\"/tmp/in.csv\""`). `POSITION`, `SIZE`, `OFFSETLABEL` take two bare ints.
- Definition keys use `KEY: value` (colon, no space before); settings use `KEY : "value"` (spaced colon). Studio's exporter emits stray commas (`,,`) for empty hidden parameters; the parser tolerates them.
- `addSchema` `CONNECTOR` values: `FLOW`, `LOOKUP`, `MERGE`, `REJECT`, `FILTER`, `UNIQUE`, `DUPLICATES`, `OUTPUT`... The exporter writes an `addSchema` for every connector the component declares, even empty ones.
- Column keys: `NAME`, `TYPE`, `NULLABLE`, `KEY`, `LENGTH`, `PRECISION`, `COMMENT`, `PATTERN`, `DEFAULTVALUE`, `ORIGINALLEHGTH` (misspelling is the real key), `SOURCETYPE`.
- `addMapperData { addInputTable{} addVarTable{} addOutputTable{} }` is documented in the reference guide ("Mapper settings" / "tMap Job script properties"); the `addEntry`/attribute spelling above follows the XML attribute names and is (unverified) in detail. No `setMapperData` exists.
- `addConnection@TYPE` is the connector name, `LINESTYLE` the EConnectionType ordinal (table in section 2). The documented list: 0 row (FLOW/FILTER/REJECT), 1 SUBJOB_OK, 3 COMPONENT_OK, 4 SUBJOB_ERROR, 5 COMPONENT_ERROR, 6 RUN_IF, 7 ITERATE, 8 LOOKUP, 9 TABLE, 10 MERGE, 12 SYNCHRONIZE, 13 PARALLELIZE.
- `addNote { ... }` exists for notes (unverified keys). Routes and Big Data jobs can also be exported (`JobType= Big_Data_Batch, FRAMEWORK: Spark` (unverified)).
- Version caveats: Jobscript exists since 5.x (SCRIPT_VERSION 1.x); 7.x/8.x exports carry `SCRIPT_VERSION=4.x`, `INTERNALID`, `REPOSITORYCONTEXTID` and `enc:` passwords. Older scripts import into newer Studios; the reverse is not guaranteed. Build Job does not produce a `.jobscript`; only the explicit export does.

## 6. Generated Java

One class per job (plus one per joblet usage inlined, one per child job built separately).
Confirmed from a generated class (6.1) and unchanged in shape through 8.0:

```java
package local_project.rancher2text_3_0_1;             // <project_lower>.<job_lower>_<M>_<m>

import routines.Numeric; import routines.TalendDate; ...  // every routine listed in routinesParameter
import routines.system.*; import routines.system.api.*;

@SuppressWarnings("unused")
public class rancher2text_3 implements TalendJob {    // TalendJob = routines.system.api.TalendJob

    public class ContextProperties extends java.util.Properties {   // one typed field per context param
        public String file;                                          // id_String -> String, id_Integer -> Integer, id_Date -> java.util.Date, id_Password -> java.lang.String
        public String getFile() { return this.file; }
        public void synchronizeContext() { if (file != null) this.setProperty("file", file.toString()); ... }
    }
    private ContextProperties context = new ContextProperties();
    public ContextProperties getContext() { return this.context; }
    private final java.util.Map<String, Object> globalMap = java.util.Collections.synchronizedMap(new java.util.HashMap<String, Object>());
    private final java.util.Map<String, Long> start_Hash, end_Hash;          // component timings
    private final java.util.Map<String, Boolean> ok_Hash;                    // component finished flags
    public final java.util.List<String[]> globalBuffer;                      // tBufferOutput rows
    public Integer errorCode = null;  private String currentComponent = "";
    private String status = "";                                              // "end" / "failure"
    private RunStat runStat = new RunStat();  private ResumeUtil resumeUtil = null;
    public String resuming_logs_dir_path, resuming_checkpoint_path, parent_part_launcher;
    public boolean watch = false; public Integer portStats = null; public int portTraces = 4334; public String clientHost;
    public String contextStr = "Default"; public boolean isDefaultContext = true;
    public String pid = "0", rootPid = null, fatherPid = null, fatherNode = null; public boolean isChildJob = false;
    public String log4jLevel = "";
    private final java.util.Properties defaultProps = new java.util.Properties();  private final java.util.Properties context_param = new java.util.Properties();

    private class TalendException extends Exception {                        // wraps any component exception
        private TalendException(Exception e, String errorComponent, final java.util.Map<String, Object> globalMap) {...}
        public void printStackTrace() {
            if (!(e instanceof TalendException || e instanceof TDieException)) {
                globalMap.put(currentComponent + "_ERROR_MESSAGE", exception_msg);   // => ((String)globalMap.get("tDBOutput_1_ERROR_MESSAGE"))
                System.err.println(...stack...);
            }
            if (!(e instanceof TalendException)) { try { tLogCatcher? / processing_error_handling } ... }
        }
    }

    // ---- one row struct per connection ----
    public static class row1Struct implements routines.system.IPersistableRow<row1Struct> {
        public Integer id; public Integer getId() {...}
        public String name;  ...
        public void readData(ObjectInputStream dis) {...}  public void writeData(ObjectOutputStream dos) {...}
        public String toString() {...}  public int compareTo(row1Struct other) {...}  // + hashCode/equals when keys exist
    }

    // ---- one *Process method per subjob, named after its start component ----
    public void tFileInputDelimited_1Process(final java.util.Map<String, Object> globalMap) throws TalendException {
        globalMap.put("tFileInputDelimited_1_SUBPROCESS_STATE", 0);
        final boolean execStat = this.execStat;
        String iterateId = ""; String currentComponent = ""; java.util.Map<String, Object> resourceMap = new java.util.HashMap<>();
        try {
            // -- begin of every component in the subjob, in flow order --
            ok_Hash.put("tLogRow_1", false); start_Hash.put("tLogRow_1", System.currentTimeMillis());
            currentComponent = "tLogRow_1";  int tos_count_tLogRow_1 = 0;
            ...
            ok_Hash.put("tFileInputDelimited_1", false); ...
            // -- main loop: generated by the start component --
            while (...read row...) {
                row1 = new row1Struct(); ... tos_count_tFileInputDelimited_1++;
                /* tMap_1 main */ ... out1 = new out1Struct(); ...
                /* tLogRow_1 main */ ... tos_count_tLogRow_1++;
            }
            // -- end of every component --
            globalMap.put("tFileInputDelimited_1_NB_LINE", nb_line_tFileInputDelimited_1);
            ok_Hash.put("tFileInputDelimited_1", true); end_Hash.put("tFileInputDelimited_1", System.currentTimeMillis());
            // OnSubjobOk / OnComponentOk triggers are method calls here:
            tLogRow_2Process(globalMap);
        } catch (java.lang.Exception e) {
            TalendException te = new TalendException(e, currentComponent, globalMap);
            throw te;
        } catch (java.lang.Error error) { runStat.stopThreadStat(); throw error; }
        finally { try { /* finally of each component: close readers/connections */ } catch (...) {...} 
            resourceMap = null; }
        globalMap.put("tFileInputDelimited_1_SUBPROCESS_STATE", 1);
    }

    public static void main(String[] args) { final rancher2text_3 cls = new rancher2text_3(); int exitCode = cls.runJobInTOS(args); System.exit(exitCode); }
    public String[][] runJob(String[] args) { int exitCode = runJobInTOS(args); return new String[][] { { Integer.toString(exitCode) } }; }  // used by tRunJob / TalendJob API; returns tBufferOutput rows when present
    public boolean hastBufferOutputComponent() {...}
    public int runJobInTOS(String[] args) {
        // parse args: "--context_param" is a 2-token arg, everything else one token -> evalParam()
        // load contexts from classpath: "<project_lower>/<job_lower>_<M>_<m>/contexts/" + contextStr + ".properties"
        // then override with --context_param values, then typed assignment: context.file = (String) context.getProperty("file") ... (dates parsed with ParserUtils)
        // set up log4j level, stats (RunStat on --stat_port), resume (ResumeUtil), then:
        // this.globalResumeTicket = true; tFileInputDelimited_1Process(globalMap); ... one call per start component, in order
        // end: runStat.stopThreadStat(); if (status.equals("failure")) errorCode = 1; return errorCode == null ? 0 : errorCode
    }
    private void evalParam(String arg) {  // confirmed flags
        --resuming_logs_dir_path=  --resuming_checkpoint_path=  --parent_part_launcher=  --watch  --stat_port=  --trace_port=
        --client_host=  --context=  --father_pid=  --root_pid=  --father_node=  --pid=  --context_param key=value  --log4jLevel=
    }
}
```

Reading a stack trace: the frame `at local_project.myjob_0_1.MyJob.tMap_1Process(MyJob.java:2345)`
names the **subjob** (its start component) and the line inside the generated source, not the
failing component. The failing component is the `currentComponent` at the time of the throw,
printed by `TalendException.printStackTrace()` as `Exception in component tDBOutput_1 (MyJob)`
just above the trace (7.x+ with log4j: logged at ERROR by logger `<project>.<job>_<ver>.<Job>`,
component logger names are `<Job>.<component>`? (unverified)). To find the line: open the job,
Code tab, Ctrl+L on the line number, or `poms/jobs/process/<job>_<M>_<m>/src/main/java/.../<Job>.java`
after a build. tRunJob children appear as separate classes; `--father_pid`/`--root_pid`/`--father_node`
link them in stats. Since 7.x the generated code also carries `talendJobLog`
(`org.apache.logging.log4j.Logger`) and `log` fields when log4j is enabled, and
`tos_count_<comp>` counters feed `<comp>_NB_LINE`.

Other generated artifacts per job: `routines/system/*.java` (RunStat, ResumeUtil,
ParserUtils, PasswordEncryptUtil, TDieException, TalendJob/TalendESBJob interfaces),
`contexts/<Ctx>.properties` as resources, and for joblets the joblet code is inlined.

## 7. Build outputs

Layout of the zip itself is in deployment-runtime.md; the file formats inside:

### `jobInfo.properties` (zip root; required by TAC Job Conductor "pre-generated job" import)

```
#just for tac
statistics=false
job=rancher2text_3
jobVersion=0.1
date=2015-12-10 102204977
contextName=dev
jobId=_WhMvMJj-EeWDJK38eZDknQ
projectId=0
applyContextToChildren=false
project=LOCAL_PROJECT
branch=
cmdLineVersion=6.1.0.20151029_1337
```

Later versions add `jobType=Standard`, `jobDefaultContext`, `addStatisticsCode`,
`addTracsCode`? (unverified keys), `cmdLineVersion` = Studio/CommandLine build string.
Missing `jobInfo.properties` => TAC "Can not find the job information properties file in uploaded file".

### `<Job>_run.sh` / `.bat`

6.x launcher (confirmed):
```sh
#!/bin/sh
cd `dirname $0`
ROOT_PATH=`pwd`
java -Xms256M -Xmx1024M -cp .:$ROOT_PATH:$ROOT_PATH/../lib/routines.jar:$ROOT_PATH/../lib/log4j-1.2.16.jar:...:$ROOT_PATH/rancher2text_3_0_1.jar: local_project.rancher2text_3_0_1.rancher2text_3 --context=dev "$@"
```
7.x/8.x: same shape with `-Dtalend.component.manager.m2.repository=$ROOT_PATH/../lib` (TCK components),
`-Dfile.encoding=UTF-8`, optional `-Dlog4j2.configurationFile`? (unverified), the JVM arguments from
Job > Extra, and `-cp .:$ROOT_PATH/../lib/*.jar...` or `$ROOT_PATH/../lib/classpath.jar` when
Window > Preferences > Talend > Import/Export > "Add classpath jar in exported jobs" is on
(avoids the Windows command-line length limit). Context scripts: `--context=<Name>` is baked in,
one launcher pair per selected context ("Context scripts" option in Build Job).

### `contexts/<Name>.properties`

Inside `<job>_<ver>.jar` under `<project_lower>/<job_lower>_<M>_<m>/contexts/`, and (Build Job
with "Context scripts") also unpacked next to the launcher. Plain `java.util.Properties`:

```
#Fri Oct 17 10:00:00 UTC 2026
file=/tmp/in.csv
port=5432
password=enc\:routine.encryption.key.v1\:QmFzZTY0...
```

Properties escaping applies (`\:`, `\=`, `\\`, unicode `\uXXXX`); Dates use the
pattern of the context param (`yyyy-MM-dd HH:mm:ss`); booleans `true`/`false`. The job loads
`--context=<Name>` from the classpath resource first, then applies `--context_param`.

### `log4j2.xml` (7.3+/8.0; 6.x used `log4j.xml` with log4j 1.x)

Build Job embeds the Project Settings > Log4j template into the jar root. Default (approximate, unverified verbatim):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Configuration>
  <Appenders>
    <Console name="stdout" target="SYSTEM_OUT">
      <PatternLayout pattern="%d{yyyy-MM-dd HH:mm:ss.SSS} %-5p %c{1} - %m%n"/>
    </Console>
  </Appenders>
  <Loggers>
    <Root level="INFO">     <!-- replaced at build by "Custom log4j level" / overridden at run by --log4jLevel= -->
      <AppenderRef ref="stdout"/>
    </Root>
  </Loggers>
</Configuration>
```

Component logs use `log.info(...)` on logger `<Job>` / `<component>`; `talendJobLog` appender
name `talendJobLogAppender` and `talendLogs_LOGS` global exist in generated code with "Log4j
job logs" enabled (unverified names). Override at runtime with `-Dlog4j2.configurationFile=file:/path/log4j2.xml`.

### `pom.xml` (7.x/8.x Maven build, also what CI Builder consumes)

Studio generates per job `poms/jobs/process/<job>_<M>_<m>/pom.xml`:

```xml
<project>
  <parent>
    <groupId>org.example.local_project</groupId>     <!-- default groupId = org.example.<project_lower>; override in Project Settings > Build > Maven -->
    <artifactId>jobs</artifactId>  <version>8.0.1</version>
    <relativePath>../../pom.xml</relativePath>
  </parent>
  <artifactId>myjob</artifactId>          <!-- job name (lower-case? case preserved - unverified) -->
  <version>0.1.0</version>                <!-- job version + ".0"; SNAPSHOT when "Use snapshot" -->
  <packaging>jar</packaging>
  <name>MyJob</name>
  <properties>
    <talend.job.name>MyJob</talend.job.name> <talend.job.version>0.1</talend.job.version>
    <talend.job.class>local_project.myjob_0_1.MyJob</talend.job.class>
    <talend.job.context>Default</talend.job.context> <talend.job.type>Standard</talend.job.type>
    <talend.job.finalName>MyJob_0.1</talend.job.finalName> ...                                   (unverified property names)
  </properties>
  <dependencies>
    <dependency><groupId>org.example.local_project</groupId><artifactId>routines</artifactId><version>8.0.1</version></dependency>
    <dependency><groupId>org.talend.libraries</groupId><artifactId>talend-codegen-utils</artifactId><version>0.31.0</version></dependency>
    <dependency><groupId>org.talend.libraries</groupId><artifactId>mysql-connector-java-8.0.18</artifactId><version>6.0.0</version></dependency>  <!-- third-party jars Studio does not know get GAV org.talend.libraries:<jar basename>:6.0.0 -->
    ...
  </dependencies>
  <build>
    <plugins>
      <plugin><artifactId>maven-assembly-plugin</artifactId>
        <configuration><descriptors><descriptor>${project.basedir}/assembly.xml</descriptor></descriptors></configuration></plugin>
      <plugin><groupId>org.talend.ci</groupId><artifactId>talend-job-maven-plugin</artifactId>? (unverified) </plugin>
    </plugins>
  </build>
  <profiles> <profile><id>packaging_and_assembly</id>...</profile> <profile><id>docker</id>...</profile> <profile><id>cloud-publisher</id>...</profile> <profile><id>nexus_pull</id>...</profile> (names unverified) </profiles>
</project>
```

What is firm: default groupId prefix `org.example.`; version = `<M>.<m>.0`; third-party
libraries are served from Talend's library repository with groupId `org.talend.libraries`
(`https://talend-update.talend.com/nexus/content/repositories/libraries/`, needs the Talend
user settings `maven_user_settings.xml` in `<Studio>/configuration/`); the local repo is
`<Studio>/configuration/.m2/repository`; `assembly.xml` next to the pom defines the zip
(`<job>_<ver>.zip` with `lib/`, `<job>/`, `jobInfo.properties`). Project Settings > Build >
Maven lets you edit templates "Project pom", "Project settings", "Job pom", "Job assembly",
"Routines pom", "Beans pom", "Docker" (file names under `<PROJECT>/poms/templates/`? unverified);
`maven.repository=global` in `configuration/config.ini` switches Studio to the user `~/.m2`.
CI Builder (`org.talend.ci:builder-maven-plugin` 8.0.x) runs `mvn -s settings.xml org.talend.ci:builder-maven-plugin:8.0.x:generate` then `mvn package` on this tree (see deployment-runtime.md).

### OSGi bundle (Build Job "OSGi Bundle For ESB", routes, data services)

`META-INF/MANIFEST.MF` headers written by `JobJavaScriptOSGIForESBManager`: `Bundle-Name`,
`Bundle-SymbolicName` (= `<Job>` or `<project>.<job>`), `Bundle-Version` (`0.1.0`),
`Bundle-ManifestVersion: 2`, `Bundle-ClassPath` (`.,lib/xxx.jar,...` for embedded jars),
`Import-Package` (`routines.system.api`, `javax.sql`, `org.osgi.service.blueprint`...),
`Export-Package` (the job package), `Require-Bundle` (for Studio-known bundles, e.g.
`org.talend.libraries.*`), `Export-Service: routines.system.api.TalendJob;name=<Job>;type=job`,
plus `Talend-*` custom headers? (unverified). `OSGI-INF/blueprint/job.xml` from the confirmed template:

```xml
<blueprint xmlns="http://www.osgi.org/xmlns/blueprint/v1.0.0">
  <bean id="job" class="local_project.myjob_0_1.MyJob" destroy-method="destroy">
    <property name="dataSourceReferences"><ref component-id="dataSourceReferenceList"/></property>   <!-- only when the job uses JNDI/OSGi datasources -->
  </bean>
  <service ref="job">
    <interfaces>
      <value>routines.system.api.TalendJob</value>
      <value>routines.system.api.TalendESBJob</value>          <!-- ESB jobs (tESBProviderRequest/tRESTRequest) -->
      <value>routines.system.api.TalendESBJobFactory</value>   <!-- multithreaded ESB jobs -->
    </interfaces>
    <service-properties>
      <entry key="name" value="MyJob"/> <entry key="version" value="0.1"/> <entry key="type" value="job"/>
      <entry key="multithreading" value="true"/>
    </service-properties>
  </service>
  <reference-list id="dataSourceReferenceList" member-type="service-reference" interface="javax.sql.DataSource"/>
</blueprint>
```

REST data services get a `jaxrs:server` blueprint (`job-rest-template.xml`) with
`ExceptionMapper4TalendJobRestService`, `JSONProvider`, optional `JAASAuthenticationFilter`
(BASIC), SAML/`org.talend.esb.job.service` placeholders, Service Locator (`locatorFeature`)
and SAM (`eventFeature`) references. Routes: `META-INF/spring/*.xml` or blueprint with the
`RouteBuilder` bean plus the `springContent` from the item. Folders are the constants
`OSGI-INF/blueprint`, `META-INF/spring`, `TALEND-INF`, `MAVEN-INF`. Build Route "Karaf
feature" produces a `.kar` (zip with `repository/<maven layout>` and `features.xml`).

### Spring Boot microservice (Build Job/Route "Microservice (Spring Boot)")

Executable jar `<Job>_<ver>.jar` with `BOOT-INF/`, `application.properties` keys (unverified
exact set): `server.port=8065`, `spring.main.banner-mode=off`, `camel.springboot.name`,
`camel.springboot.main-run-controller=true`, `management.endpoints.web.exposure.include`,
`logging.level.*`, `talend.job.context`? ; override with `--server.port=` or
`-Dspring.config.location=`. Routes also accept `--context_param` style? no: use
`--spring.config.additional-location` / env vars.

### Docker image

Build Job "Docker image" / CI `-Pdocker` uses a `Dockerfile` from the Maven template: base
image `openjdk`/`eclipse-temurin` (configurable `talend.docker.baseImage`? unverified), copies the
job zip contents to `/talend/<job>/`, `ENTRYPOINT ["/talend/<job>/<job>_run.sh"]`, so
`docker run img --context=Prod --context_param k=v` works.

### Talend Cloud publish payload

Publishing to Talend Cloud uploads the same job zip plus metadata (artifact name = job name,
version = `M.m.p` with `.0` appended, type `Job`/`Route`/`DataService`, project, description);
the artifact appears under Management > Artifacts. Parameters exposed to TMC = the job's context
variables of the default context. Details of the JSON: apis-sdks.md.

### `.car` (Component Kit ARchive)

A `.car` is a zip/jar built by `org.talend.sdk.component.tools.CarBundler`:

```
META-INF/MANIFEST.MF                       Main-Class: org.talend.sdk.component.tools.exec.CarMain
TALEND-INF/metadata.properties             version=<car version>, date=..., component_coordinates=<groupId>:<artifactId>:<version>, type=connector (unverified key 'type')
MAVEN-INF/repository/<group/path>/<artifact>/<ver>/<artifact>-<ver>.jar   the component jar + every runtime dependency, Maven layout
org/talend/sdk/component/tools/exec/CarMain*.class
```

Usage: `java -jar my-component.car studio-deploy --location <StudioDir>` (copies jars into
`<Studio>/configuration/.m2/repository`, appends the coordinates to
`component.java.coordinates` in `configuration/config.ini`), `maven-deploy --location ~/.m2/repository`,
`deploy-to-nexus --url <nexus> --repo <repo> [--user --pass --threads --dir]`. Component jars
carry `TALEND-INF/dependencies.txt` (output of `mvn dependency:list`, used by the runtime to
resolve the classloader) generated by the `talend-component-maven-plugin` goal
`dependencies`. Config.ini key for a remote component server repo: `talend.component.server.maven.repository`.

### Studio configuration files

`<Studio>/Talend-Studio-<os>.ini` (Eclipse launcher ini; names like `Talend-Studio-linux-gtk-x86_64.ini`, `Talend-Studio-win-x86_64.ini`):

```
-vm
/path/to/jdk-11/bin          (optional; must precede -vmargs)
-vmargs
-Xms512m
-Xmx3072m
-XX:MaxMetaspaceSize=512m
-Dfile.encoding=UTF-8
-Dosgi.requiredJavaVersion=11          (8.0; 7.3 = 1.8)
-Dtalend.disable.internet=true         (offline mode, unverified)
-Dtalend.studio.p2.update=...          (update site; unverified)
-Dencryption.keys.file=/path/studio.keys  (8.0 custom key file, unverified for Studio)
```

`configuration/config.ini` (OSGi props: `osgi.instance.area` workspace, `maven.repository=global|local`,
`component.java.coordinates`, `talend.component.server.maven.repository`, `talend.studio.p2.update`...),
`configuration/maven_user_settings.xml` (Talend Nexus mirrors), `configuration/.m2/repository`
(local Maven repo), `configuration/studio.keys` (encryption keys), `plugins/` + `features/`
(update-site layout; patches land as `plugins/*.jar` and `patches/`).

## 8. Context and properties files at runtime

| Source | Format | Notes |
|---|---|---|
| `--context=<Name>` | selects `contexts/<Name>.properties` from the jar | unknown name: prints `Could not find the context <Name>` and continues with defaults |
| `--context_param name=value` | two CLI tokens, repeatable; value is `String` then typed by the job; escapes `\\ \n \' \r \f \b \t` are unescaped for the top-level job only | spaces need shell quoting: `--context_param "file=/tmp/a b.csv"`; dates must match the param pattern |
| Implicit tContextLoad / tContextLoad file | one `key=value` per line (or `key<sep>value` with "Field separator", e.g. `;`), `#` comments ignored, blank lines skipped, no escaping, values are raw strings | keys not in the job: "Print operations"/warnings per `LOAD_NEW_VARIABLE`/`NOT_LOAD_OLD_VARIABLE` (`Ignore`/`Warning`/`Error`); passwords may be `enc:` encrypted or clear |
| Implicit tContextLoad from DB | table with `key`,`value` columns + query condition | typed via the same path |
| TAC Job Conductor | "Context parameters" grid per task; stored in TAC DB; passed as `--context_param` | overrides exported context |
| TMC task | JSON `parameters: {"key": "value"}` (all strings) in the task config / API `PUT /orchestration/executables/tasks/{id}` | per-task; connection/resource params similar |
| `ContextProperties` in Java | `context.<name>` typed field + `context.getProperty("name")` string | `context.synchronizeContext()` copies fields back into the Properties before passing to tRunJob |
| `jobInfo.properties` | see section 7 | only read by TAC import |
| log4j2 | `--log4jLevel=<DEBUG, INFO, WARN or ERROR>` sets `log4jLevel` | pattern in `log4j2.xml` |

## 9. Route, Service, Big Data and other item kinds

### Routes (`routes/<Route>_<ver>.item`)

Same `talendfile:ProcessType` root (observed `jobType="Standard"` on a 7.1 route; no
`framework`), nodes are Camel components `cMessagingEndpoint`, `cREST`, `cSetBody`,
`cProcessor`, `cTalendJob`, `cMessageRouter`, `cTry`, `cOnException`, `cConfig`, `cBean`...
Connections use `connectorName="ROUTE" lineStyle="14"` (`route1`, `route2`), `ROUTE_WHEN` 15
with a `CONDITION` elementParameter (language `simple`/`xpath`/`header`...), `ROUTE_OTHER` 16,
`ROUTE_TRY`/`CATCH`/`FINALLY` 17-19, `ROUTE_ENDBLOCK` 20. The `.properties` item is
`CamelProperties:CamelProcessItem` with `springContent` (an escaped Spring `<beans>` XML with
`camel` namespace; shown in the Studio "Spring" tab) and `additionalProperties` keys
`ROUTE_RESOURCES_PROP` (`<resource item id>|Latest`) and `Bundle-ClassPath` (embedded jars).
Generated Java: `package <project_lower>.<route_lower>_<M>_<m>; public class <Route> extends
org.apache.camel.builder.RouteBuilder { public void configure() { from("...").routeId("cMessagingEndpoint_1")...; } }`
plus a `CamelContext`/Spring launcher `main` (standalone build) or blueprint (OSGi). `cTalendJob`
embeds the job class or references it by OSGi service name/version.

### Services (`services/<Service>_<ver>.item|.wsdl|.properties`)

`Services:ServiceItem` (`referenceResources` -> the `.wsdl` reference). The `.item` holds
`ServiceConnection` with `ServicePort`/`ServiceOperation` entries binding operations to
provider jobs (job property id + version); the `.wsdl` is the contract file. Consumers in jobs
use `metadata/wsdl/` (`WSDLSchemaConnectionItem`).

### Big Data jobs

| Folder | `jobType` | `framework` | Notes |
|---|---|---|---|
| `process_mr/` | `Big_Data_Batch` | `Spark` (older `MapReduce`) | Spark Batch; job-level params `DISTRIBUTION` (`AMAZON_EMR`, `CLOUDERA`, `DATABRICKS`, `UNIVERSAL`...), `SPARK_VERSION` (`EMR_62_x`...), `SPARK_MODE` (`LOCAL`, `YARN_CLIENT`, `YARN_CLUSTER`, `STANDALONE`, `KUBERNETES`...), `SPARK_API_VERSION` (`SPARK_240`, `SPARK_3_x`), `SPARK_HOST`, `SPARK_HOME`, `SPARK_DRIVER_MEM/CORES`, `SPARK_EXECUTOR_MEM/CORES/INSTANCES`, `SPARK_YARN_*`, `SPARK_SERIALIZER`, `SPARK_BROADCAST_FACTORY`, `HADOOP_CONF_SPECIFIC_JAR`, `HADOOP_HOME_DIR`, `HADOOP_LOGIN`, `SPARK_STATS_POLLING_RATE`; the `tSparkConfiguration_1` node is referenced by every component's `SPARK_CONFIGURATION` param |
| `process_storm/` | `Big_Data_Streaming` | `Spark_Streaming` (older `Storm`) | Spark Streaming / Structured Streaming; components reference `STORAGE_CONFIGURATION`=`tSparkConfiguration_1`; Kafka props tables `KAFKA_CONSUMER_PROPERTIES` |

Spark job connections are still `FLOW`/`lineStyle 0`; generated code extends Talend's Spark
job base and builds the DAG in `run(SparkSession)`; details in big-data-spark.md.

### Other
- Data Mapper (TDM): structures/maps are Eclipse resources in the project (TDM project props file `com.oaklandsw.base.projectProps` per `FileConstants`), stored under `metadata/` as Hierarchical Mapper items with `.map`/`.structure`? content (unverified file extensions); they are referenced by `tHMap` by path.
- Test cases: `TestContainerItem` whose `.item` is a ProcessType of the test job (tCreateTemporaryFile, tFileInputDelimited test data, tAssert) with `TESTCONTAINER_*` parameters linking to the tested job id; stored in the job's folder (exact sub-folder unverified).
- Pipeline Designer pipelines: JSON exported via TMC API (`/pipelines/{id}`), not Studio items. Data Preparation recipes: JSON via Data Preparation API. API Designer: OAS 2/3 or RAML exported from the API Designer app; API Tester projects: JSON. See data-quality-governance.md / esb-routes-services.md.

## 10. Reading, writing and diffing items programmatically

Parsing:
- Use a namespace-aware parser; the root prefix `talendfile` maps to the fake URI
  `platform:/resource/org.talend.model/model/TalendFile.xsd` (an Eclipse workspace URI; do not try to fetch it). Other URIs: `http://www.omg.org/XMI`, `http://www.talend.org/properties`, `http://www.talend.org/mapper`, `http://www.talend.org/xmlmap`, `http://www.talend.org/metadata/connection/2010`, `http:///orgomg/cwm/resource/relational.ecore`, `http://www.talend.com/joblet.ecore`, `http://www.talend.org/CamelProperties`, `http://www.talend.org/Services`.
- Attribute order written by EMF is stable (model order), so a formatter that preserves attribute order diffs cleanly; `xmllint --format` reorders nothing but may change whitespace. Keep 2-space indent, `&quot;` for quotes inside attributes, `&lt;`/`&gt;`/`&amp;`/`&#xD;&#xA;` for newlines in `MEMO_*` values.
- Fast lookups: `//node[elementParameter[@name='UNIQUE_NAME']/@value='tMap_1']`, `//connection[@target='tMap_1' and @lineStyle='8']` (lookups), `//elementParameter[@field='PASSWORD' and not(starts-with(@value,'enc:')) and @value!='']` (clear-text password audit), `//contextParameter[@type='id_Password']`.
- Python: `ET.register_namespace` for every prefix before writing or ElementTree renames them to `ns0`, which Studio still reads but which pollutes diffs. `lxml` preserves prefixes.

Common diff noise to filter in reviews: `posX`/`posY`/`offsetLabel*`, `SCREEN_OFFSET_X/Y`,
`componentVersion` bumps, `UPDATE_COMPONENTS`, `PREVIEW` bmp names, `sizeState`/`minimized`/
`shellMaximized`/`activateCondensedTool` in mapper data, `.screenshot` files, `modificationDate`
/ `modified_*` / `import_*` / `item_key` in `.properties`, `migrationTask` and
`componentsSettings` in `talend.project`, `informations` (compile warnings) in `.properties`,
`relationship.index`, `xmi:id` churn when an item is re-imported. Useful: a `.gitattributes`
driver that runs `xmllint --format` before diff, or a pre-diff script that strips those attributes.

Merge strategy: never 3-way merge `.item` files with a text tool when both sides touched the
same `<node>`; take one side and redo the other change in Studio. Mark `*.screenshot binary`
and consider `*.item -diff` for generated-heavy items (tXMLMap with EMF fragment paths). A
committed `relationship.index` conflicts constantly; either exclude it or let Studio regenerate
(Project Settings > "Reload relationships"? unverified). Lock contention is a TAC/Git feature,
not a file-level one; `ItemState@locked` in local projects can be hand-cleared.

Ids and references:
- Repository id (`Property@id`) is the join key. `PROPERTY:REPOSITORY_PROPERTY_TYPE` = that id; `SCHEMA:REPOSITORY_SCHEMA_TYPE` = `<id> - <table label>`; `PROCESS:PROCESS_TYPE_PROCESS` = child job id; `routinesParameter@id`; `repositoryContextId`; `ROUTE_RESOURCES_PROP` = `<id>|Latest`.
- When copying an item between projects by hand, the referenced metadata/context/routine ids must exist in the target project or the component falls back to Built-In with its last stored values (Studio warns "repository item not found"). Export/Import items in Studio rewrites nothing; ids are global UUIDs so collisions are not an issue, but duplicated label+folder is.
- Generating new ids: EMF ids are 22 chars of base64url derived from a type-1 UUID with `_` prefix; any unique `_[A-Za-z0-9_-]{22}` string is accepted, as are RFC UUID strings.

Schema propagation hazards when editing by hand:
- A `<metadata>` column list on an output component must equal the `<metadata>` of the input connection's source (`metaname`) unless the component declares schema conversion; otherwise Studio shows the yellow "schema mismatch" triangle and generated code fails to compile (`row1.newcol cannot be resolved`).
- tMap: input `inputTables/mapperTableEntries` must mirror the incoming `<metadata>` of each connected source; output `outputTables/mapperTableEntries` must mirror the tMap node's own `<metadata name="<out>">`; the downstream component's `<metadata>` must match too. Keep `type` identical in all three places.
- Renaming a `UNIQUE_NAME` requires updating every `connection@source/@target/@metaname`, `<subjob> UNIQUE_NAME`, expressions `row1.x` are unaffected but `globalMap.get("tX_1_NB_LINE")` strings are not.
- Changing a `contextParameter@name` requires the same change in every `<context>` group and in all `context.<name>` expressions; the generated `ContextProperties` field is the Java identifier, so names must be valid Java identifiers (Studio enforces; hand edits do not).
- `componentVersion` must be one the installed Studio knows; a too-new version triggers migration refusal, a too-old one triggers migration tasks on open (harmless, but rewrites the item).

Versioning rules:
- File names `<Label>_<M>.<m>.item|.properties|.screenshot` must agree with `Property@label` and `Property@version`; a mismatch makes the item invisible or imports as a different version. Label is case-sensitive and `[A-Za-z0-9_]` (Studio rejects spaces/hyphens).
- All versions of an item sit in the same folder (`Job_0.1.item`, `Job_0.2.item`, `Job_1.0.item`); "Latest" references resolve to the highest `M.m` numerically (0.10 > 0.9).
- `.properties` `Property@id` is shared by all versions; `xmi:id`s are per file.

Validation: import into a scratch project (File > Import items > root directory), open the
job, check Problems view and the Code tab compiles (the Designer shows red/yellow markers);
or run the CommandLine `importItems`/`generateJob`? (apis-sdks.md) in CI. Studio rewrites the
item on first save, so diff the re-saved file against yours to learn what you got wrong.

## Gotchas

| Symptom | Cause | Fix |
|---|---|---|
| Hand-written item imports but Studio shows an empty canvas | `.properties` `href` wrong (`#/0` on a single-root file, or `#/` on an `xmi:XMI` wrapper), or file name version != `Property@version` | Jobs: `<process href="Name_0.1.item#/"/>`; contexts/joblets/metadata use `#/0`,`#/1` or `#_id`; align versions |
| `Could not find the context Prod` at run, job continues with defaults | `--context=Prod` but only `Default.properties` was built (Build Job "Context scripts" = selected context only) | rebuild with all contexts, or pass `--context_param` |
| Stack trace points to `tMap_1Process(Job.java:1234)` but tMap is fine | method name = subjob start component, line = generated source | read `Exception in component tX_1` line above, or open Code tab at that line |
| Passwords `enc:system.encryption.key.v1:...` fail to decrypt on another machine ("Can not decrypt" / `javax.crypto.AEADBadTagException`) | different `studio.keys` (rotated or custom key) | copy `configuration/studio.keys` to every Studio/TAC/CommandLine; use `-Dencryption.keys.file` on Runtime |
| Same job, every commit changes `posX`, `SCREEN_OFFSET_X`, `.screenshot`, `modified_date` | Studio writes UI state and timestamps on save | `.gitattributes` binary for `.screenshot`, review with a filter script, do not fight it |
| `routinesParameter` id warning "routine not found" after moving a job to another project | `routinesParameter@id` points at the source project's routine property id | import the routine too, or delete the stale `routinesParameter` (Studio re-adds system ones) |
| Component shows Built-In although it was Repository | `PROPERTY:REPOSITORY_PROPERTY_TYPE` id not present in this project | import the metadata item (same id) or re-select in Studio; re-saving writes new values |
| Schema mismatch triangle after editing columns in the item | downstream `<metadata>` / tMap `mapperTableEntries` not updated in all places | edit input metadata, mapper entries and output metadata together; `type` must be identical |
| tXMLMap connections vanish after reordering `<node>`s | EMF fragment refs `//@node.N/@nodeData/@connections.K` are positional | never reorder nodes in jobs containing tXMLMap/tELTMap; append new nodes at the end |
| `.item` opens in 8.0 but is silently rewritten (hundreds of lines) | migration tasks (component version bumps, new hidden params) | commit the rewritten version once per Studio upgrade on a dedicated branch |
| TAC import: "Can not find the job information properties file" | `jobInfo.properties` not at zip root (built without "Items" or re-zipped with a parent folder) | Build Job with Items checked; zip contents, not the folder |
| Windows launcher `The input line is too long` | `-cp` with 200 jars exceeds cmd length | Preferences > Talend > Import/Export > "Add classpath jar in exported jobs" |
| `--context_param file=/tmp/a b.csv` loses ` b.csv` | shell splits on space; the launcher passes `"$@"` | quote: `--context_param "file=/tmp/a b.csv"`; in `.bat` use `%*` and quotes |
| Date context param set via `--context_param` is null | string does not match the param's date pattern (default `yyyy-MM-dd HH:mm:ss`) | pass the exact pattern or use `id_String` + `TalendDate.parseDate` |
| `tContextLoad` warns `Variable xyz not in job` / `not loaded` | file key not declared in job contexts | declare it or set `LOAD_NEW_VARIABLE=Ignore` |
| Routine edit compiles in Studio but exported job still old | job jar bundles `routines.jar` built at export time; CI Builder cached `routines` artifact | rebuild job; in CI `mvn -U` / clean the `org.example.<project>:routines` artifact |
| `java.lang.NoClassDefFoundError` for a driver only in built job | jar is in Studio `configuration/.m2` but `org.talend.libraries:<jar>:6.0.0` missing from CI repo | deploy the jar to Nexus `talend-custom-libs-release` with that GAV, or ship it in `lib/` |
| OSGi bundle refuses to start: `Unresolved requirement: Import-Package routines.system.api` | Talend ESB runtime job feature (`tesb-job-api`/`talend-job-controller`) not installed in Karaf | `feature:install tesb-job-api` (see esb-routes-services.md) |
| Jobscript import fails on `,,` or `ORIGINALLEHGTH` | assumed clean grammar | Studio tolerates both; keep the misspelled key and stray commas as exported |
| `.properties` shows `deleted="true"` but the item is in Git | item is in the Recycle bin, not deleted from disk | restore in Studio or set `deleted="false"` and remove from `recycle_bin.index` |
| Two developers both saved: `.item` merge produced duplicate `<node>` with same `UNIQUE_NAME` | text merge of XML | take one side, redo the other in Studio; never auto-merge items |
| Generated class name clash `myjob` vs `MyJob` on Linux CI | job labels differing only by case map to the same lower-case package | Talend forbids case-only duplicates per project; rename |

## Sources

https://help.qlik.com/talend/en-US/job-script-reference-guide/8.0/defining-connections-between-components-in-job-script
https://help.qlik.com/talend/en-US/job-script-reference-guide/7.3/defining-connections-between-components-in-job-script
https://help.qlik.com/talend/en-US/job-script-reference-guide/7.3/defining-connections-linking-components
https://help.qlik.com/talend/en-US/job-script-reference-guide/8.0/adding-component-in-job-script
https://help.qlik.com/talend/en-US/job-script-reference-guide/8.0/defining-input-components
https://help.qlik.com/talend/en-US/job-script-reference-guide/8.0/defining-input-component
https://help.qlik.com/talend/en-US/job-script-reference-guide/7.2/defining-contexts-and-variables-in-job-script
https://help.qlik.com/talend/en-US/job-script-reference-guide/7.3/mapper-settings
https://help.qlik.com/talend/en-US/job-script-reference-guide/8.0/tmap-job-script-properties
https://help.qlik.com/talend/en-US/job-script-reference-guide/7.3/defining-processing-component
https://help.qlik.com/talend/en-US/job-script-reference-guide/8.0/how-to-export-job-script
https://help.qlik.com/talend/en-US/talend-glossary/Cloud/job-script
https://help.qlik.com/talend/en-US/studio-user-guide/8.0/building-jobs
https://help.qlik.com/talend/en-US/studio-user-guide/8.0/exporting-job
https://help.qlik.com/talend/en-US/studio-user-guide/8.0/changing-context-parameters-in-jobs-and-routes
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-09/creating-spark-job
https://help.qlik.com/talend/en-US/data-matching/8.0/converting-the-standard-job-to-a-spark-batch-job-procedure
https://help.qlik.com/talend/en-US/installation-guide-linux/8.0/rotating-encryption-keys-in-talend-studio
https://help.qlik.com/talend/en-US/esb-container-administration-guide/8.0/encrypting-passwords-for-data-services-and-routes
https://help.qlik.com/talend/en-US/administration-center-user-guide/7.3/adding-execution-task-to-pre-generated-job
https://help.qlik.com/talend/en-US/administration-center-user-guide/7.3/modifying-context-parameters-for-specific-tasks
https://help.qlik.com/talend/en-US/component-code-generate-model/8.0/component-cogen-model
https://help.qlik.com/talend/en-US/call-job-from-external-app/8.0/pass-new-values-to-context-variables
https://help.qlik.com/talend/en-US/software-dev-lifecycle-best-practices-guide/8.0/designing-jobs-routes-or-data-services
https://help.qlik.com/talend/en-US/object-naming-conventions/8.0/projects-folders
https://community.qlik.com/t5/Talend-Studio/Export-jobscript-file-from-a-Job-Design/m-p/2373341
https://community.qlik.com/t5/Talend-Studio/Password-type-encryption-algorithm/m-p/2373381
https://community.qlik.com/t5/Talend-Studio/resolved-Problem-importing-job-into-Job-Conductor/m-p/2265621
https://community.qlik.com/t5/Talend-Studio/Database-SQL-Result-Set-to-Context-Variable/td-p/2231764
https://jira.talendforge.org/browse/TCOMP-229
https://www.ibm.com/docs/en/DSXDOC/wsj/lineage/lineage-talend.html
https://docs.atlan.com/apps/connectors/etl-tools/talend/how-tos/set-up-talend.md
https://raw.githubusercontent.com/toscollection/tcommon-studio-se/master/main/plugins/org.talend.core.runtime/src/main/java/org/talend/core/model/process/EConnectionType.java
https://raw.githubusercontent.com/toscollection/tcommon-studio-se/master/main/plugins/org.talend.model/model/TalendFile.ecore
https://raw.githubusercontent.com/toscollection/tcommon-studio-se/master/main/plugins/org.talend.core.repository/src/main/java/org/talend/core/repository/constants/FileConstants.java
https://raw.githubusercontent.com/toscollection/tcommon-studio-se/master/main/plugins/org.talend.core.runtime/src/main/java/org/talend/core/model/repository/ERepositoryObjectType.java
https://raw.githubusercontent.com/toscollection/tdi-studio-se/master/main/plugins/org.talend.designer.mapper/model/mapper.ecore
https://raw.githubusercontent.com/toscollection/tdi-studio-se/master/main/plugins/org.talend.repository/resources/job-template.xml
https://raw.githubusercontent.com/toscollection/tdi-studio-se/master/main/plugins/org.talend.repository/resources/job-rest-template.xml
https://raw.githubusercontent.com/toscollection/tdi-studio-se/master/main/plugins/org.talend.repository/src/main/java/org/talend/repository/ui/wizards/exportjob/scriptsmanager/esb/JobJavaScriptOSGIForESBManager.java
https://raw.githubusercontent.com/Talend/component-runtime/master/component-tools/src/main/java/org/talend/sdk/component/tools/CarBundler.java
https://raw.githubusercontent.com/Talend/component-runtime/master/component-tools/src/main/java/org/talend/sdk/component/tools/exec/CarMain.java
https://github.com/oVirt/ovirt-dwh/blob/master/etl_export/src/main/java/ovirt_engine_dwh/historyetl_4_5/HistoryETL.java
https://github.com/eea/eea.rancher.parity/blob/master/jobInfo.properties
https://github.com/eea/eea.rancher.parity/blob/master/rancher2text_3/rancher2text_3_run.sh
https://github.com/eea/eea.rancher.parity/blob/master/rancher2text_3/src/main/java/routines/system/PasswordEncryptUtil.java
https://github.com/aodn/harvesters/blob/master/workspace/NRMN/talend.project
https://github.com/aodn/harvesters/blob/master/workspace/NRMN/metadata/connections/DestinationDb_0.1.item
https://github.com/aodn/harvesters/blob/master/workspace/AUV/context/source_0.1.item
https://github.com/michelbaud/siusProject/blob/master/SIUS2/process/demo/Testjob_0.1.item
https://github.com/enigmatronix13/Data-Mining-Lab/blob/master/Lab02/lab2q2_0.1.item
https://github.com/oumaimmadebbich/bi-payment-tracker-talend-qlicksense/blob/master/FINANCE_PFE/talend.project
https://github.com/PacktPublishing/Talend-Open-Studio-Cookbook/blob/master/code/routines/XMLUtils_0.1.item
https://github.com/PacktPublishing/Talend-Open-Studio-Cookbook/blob/master/fileDelimited/chapter07/order_0.1.item
https://github.com/PacktPublishing/Talend-Open-Studio-Cookbook/blob/master/chapter2/sc_cook_0040_genericCustomer_0.1.item
https://github.com/smartbiz/talend/blob/master/DEMO_ESB/process/RESTAPI/REST_Demo_0.1.item
https://github.com/jsminet/talend-esb-webservice-tuning/blob/master/routes/FromRestDBSpringtoLog_0.1.properties
https://github.com/tlnd-frguo/frguo/blob/master/CITEST/joblets/JobError_0.1.properties
https://github.com/jliu-talendbj/jliu-talendbj/blob/master/JLIU_TALENDBJ/process_mr/testbatch_0.1.item
https://github.com/adityakonda/TALEND-with-Kafka-Spark/blob/master/process_storm/kafkaip_stream_0.1.item
https://github.com/Abhinav281996/API_to_Kafka_Spark
https://github.com/evandycke/talend-tips-tricks/blob/master/scripts/talend_gitignore.gitignore
https://github.com/liferay/liferay-portal/blob/master/modules/integrations/talend/README.md
