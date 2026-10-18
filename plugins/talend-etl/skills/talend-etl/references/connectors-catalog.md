# Connectors catalog: Cloud, SaaS, business apps, NoSQL, messaging, Internet, technical

> Verification: doc-derived (help.qlik.com / help.talend.com search snippets, Talend GitHub, Maven Central) plus model knowledge. Not exercised against a live Studio/TAC/TMC in this build. Items marked (unverified) are from memory only and should be checked in Studio before relying on exact labels.

Scope: every Studio Standard-Job component family that is NOT core DB/File/Processing
(components-core.md), NOT Spark-only (big-data-spark.md) and NOT ESB c*/tESB*/tREST*
service components (esb-routes-services.md). Palette family names below are the Studio
8.0 ones; 7.x names in brackets where they differ. Component labels are the exact
Basic/Advanced settings labels where a snippet confirmed them.

## Contents

- [How to use this file](#how-to-use-this-file)
- [TCK vs javajet connectors in Studio 8](#tck-vs-javajet-connectors-in-studio-8)
- [Authentication patterns](#authentication-patterns)
- [Proxy handling](#proxy-handling)
- [Cloud: Amazon](#cloud-amazon)
- [Cloud: Microsoft Azure](#cloud-microsoft-azure)
- [Cloud: Google](#cloud-google)
- [Snowflake](#snowflake)
- [Databricks and Delta Lake](#databricks-and-delta-lake)
- [Salesforce](#salesforce)
- [SaaS business apps](#saas-business-apps)
- [Microsoft Dynamics and legacy ERP/CRM](#microsoft-dynamics-and-legacy-erpcrm)
- [SAP](#sap)
- [NoSQL](#nosql)
- [Messaging](#messaging)
- [Internet](#internet)
- [XML, JSON, LDAP, Mail](#xml-json-ldap-mail)
- [Business Intelligence](#business-intelligence)
- [Talend Cloud and Data Fabric integration components](#talend-cloud-and-data-fabric-integration-components)
- [Data Mapper (tHMap)](#data-mapper-thmap)
- [Technical and misc connectors](#technical-and-misc-connectors)
- [Pipeline Designer connectors](#pipeline-designer-connectors)
- [Component availability by license](#component-availability-by-license)
- [Deprecated and removed connectors](#deprecated-and-removed-connectors)
- [Gotchas](#gotchas)
- [Sources](#sources)

## How to use this file

- Tables are `| Component | Purpose | Key settings / auth | Notes (license, version, TCK vs javajet) |`.
- "Connection/Close" pattern: every family with a `t<X>Connection` component exposes
  `Use an existing connection` + `Component List` on the other components; a matching
  `t<X>Close` (or `t<X>Commit`/`t<X>Rollback` for transactional stores) runs OnSubjobOk.
  Not repeated per row.
- "Die on error" (Basic settings) exists on nearly every component; clearing it routes the
  error to the component's `ERROR_MESSAGE` global and lets the subjob continue. Not repeated.
- Doc URL pattern (8.0): `https://help.qlik.com/talend/en-US/components/8.0/<family-slug>/<componentname-lowercase>`.
  7.3: `.../components/7.3/<family>/<component>-standard-properties`. Spark variants:
  `.../<component>-properties-for-apache-spark-batch|streaming`.
- Globals naming: `((Integer)globalMap.get("tS3Put_1_NB_LINE"))`, `..._ERROR_MESSAGE`,
  `..._CURRENT_STATUS` are the near-universal ones; family-specific ones are listed per table.

## TCK vs javajet connectors in Studio 8

Two component technologies coexist on the Studio 8.0 palette:

| Aspect | Legacy javajet components | Talend Component Kit (TCK) components |
| --- | --- | --- |
| Source | `*.javajet` templates in `plugins/org.talend.designer.components.localprovider/components/<tName>` | Java annotations (`@Processor`, `@Emitter`, `@DataStore`, `@DataSet`, `@Option`) packaged as a `.car` (component archive) per connector family |
| Delivery | Shipped in the Studio build; patched only by a Studio monthly update (R20YY-MM) | Shipped in the build AND re-deliverable independently via Feature Manager / "Talend Cloud" update site; some (tMarketoCampaign, tDataprepRun, tHMapInput, many newer SaaS) are not in the default install and show as "must be installed with the Feature Manager" |
| Metadata model | Flat property list; Repository > Metadata wizards are per-family hand-written | Two-level: a **datastore** (connection: endpoint + credentials) and a **dataset** (object/table/query/module on that connection). Repository > Metadata shows the connection node with datasets under it; both can be dragged on the canvas |
| Settings UI | Basic / Advanced settings, labels fixed in the javajet | Basic / Advanced derived from `@Option` layout; often an extra Repository-only "Dataset" entry; "Guess schema" is driven by the connector's discovery service |
| Dependencies | `IMPORT` entries in the component XML; Studio prompts "Install missing modules" for jars not on Maven Central / Talend update site (sapjco3, ojdbc, WebSphere MQ client, etc.) | Dependencies bundled in the `.car`, resolved into the Studio local m2 (`configuration/.m2/repository`); still show in Modules view and can require "Install missing modules" when the car was installed offline |
| Examples (8.0) | tFileInput*, tMysql*, tMap, tS3*, tRedshift*, tMongoDB*, tKafka*, tFTP*, tSendMail, tRESTClient, tSAP*, tLDAP*, tMom* | Salesforce (8.0 Salesforce family is TCK-based (unverified) ), Snowflake, Azure ADLS Gen2, Azure Storage (newer), Google (BigQuery TCK variants in Cloud), NetSuite (tNetSuite*), Marketo (REST), Workday, Couchbase, MarkLogic, Splunk (tSplunkEventCollector), Zendesk, Box, ServiceNow, Jira, tHTTPClient, tHMap I/O for Spark, tDataprepRun, tDataset* |
| Job generation | Component code inlined into the Job's generated Java | Job calls the `component-runtime` manager (`org.talend.sdk.component:component-runtime-manager`) which loads the car's classloader at runtime; stack traces show `org.talend.sdk.component.runtime.*` |
| Custom components | Build with Talend Component Designer / javajet, drop in `components/` user folder, or `Preferences > Talend > Components > User component folder` | Build with Component Kit starter (starter-toolkit.talend.io), `mvn talend-component:car`, then `java -jar <x>.car studio-deploy --location <studio>` or install via Feature Manager; see apis-sdks.md |

Operational points:

- Feature Manager: `Help > Feature Manager` (or top-bar button) after logging into a project.
  A feature is installed Studio-wide but **activated per project**; local projects activate it
  only in the current project, new projects get all installed features active. Default download
  source is the Talend official site; the repository URL is configurable (offline/air-gapped
  mirrors). Feature Manager is also where "Data Mapper for Spark", Bonita, Marketo campaign,
  Data Preparation, DQ extras etc. live.
- Studio monthly updates (`8.0.1-R2023-02`-style) carry both javajet patches and TCK car
  updates; many connector options are gated on an update ("available only if you have installed
  the 8.0.1-R2023-03 Talend Studio Monthly update or a later one"). Always state the R-version
  when a label is missing in a customer's Studio.
- "Install missing modules" / Modules view (`Window > Show View > Talend > Modules`): red
  entries are jars Studio cannot download automatically (license-restricted: sapjco3,
  IBM `com.ibm.mq.allclient`, Oracle, Teradata, DB2 in some versions, Neo4j 3.x bundles,
  Vertica). Install manually (browse the jar) or via `Install` button when a Talend-hosted URL
  exists. Build server / CI must have the same jars in its Nexus/Artifactory `talend-custom-libs`
  repository (see deployment-runtime.md).
- A TCK connector's version is pinned inside the Job item (`<elementParameter name="COMPONENT_VERSION">`-like
  field in the `.item`; see artifact-formats.md); opening a Job built with a newer car in an
  older Studio fails to load those components and shows them as unknown/red.
- Pure-password vs Java mode: newer TCK/javajet secret fields (8.0.1-R2022-05+) offer a
  "pure password" mode where the field holds a literal, and a Java mode where it is an
  expression (`context.secret`). Mixing them is a common cause of `Unknown variable` compile errors.

## Authentication patterns

| Pattern | Where it appears | Studio fields / mechanics | Notes |
| --- | --- | --- | --- |
| Basic (user/password) | Nearly all | `Username`, `Password` (password field encrypted in the item as `enc:` or via `context`) | Prefer `context` values loaded from TAC/TMC or `tContextLoad`; never commit literals |
| OAuth2 client credentials | tHTTPClient, tRESTClient (via `Use Authentication > OAuth2` (unverified)), Dynamics 365 (ONLINE), Azure AD service principal, Zendesk/ServiceNow (TCK: Basic or token), Marketo REST (client id/secret -> `identity/oauth/token`) | `Client ID`, `Client Secret`, `Token endpoint`/`Authority`, `Scope` | Marketo tokens live 1h; connector refreshes automatically. Dynamics uses `https://<org>.crm.dynamics.com/.default` scope |
| OAuth2 authorization code / ROPC | tMicrosoftCrm* (Authentication Code flow then ROPC, 8.0 late-2022 update), tGoogleDrive* Installed Application | Browser-based first consent; refresh token stored | Studio will open a browser once per credential set; headless build servers cannot do the first consent, do it in Studio first |
| JWT bearer (Salesforce) | tSalesforceConnection `Connection type`/`Login Type` = `OAuth` with `OAuth2 flow type` = `JWT Flow` (unverified exact labels) | `Issuer` (connected app client id), `Subject` (username), `Audience` (`https://login.salesforce.com` or `test.`), `Key Store`, `Key Store Password`, `Certificate Alias`, `Expiration time (seconds)`, `Token File` | Connected app needs "Use digital signatures" + pre-authorized profile/permission set; sandbox audience must be `test.salesforce.com` |
| Key pair (Snowflake) | tSnowflake* `Authentication Type = Key Pair` | `Private Key` (PEM path or content), `Private Key Passphrase`, `Key Alias` (unverified) | Public key registered with `ALTER USER ... SET RSA_PUBLIC_KEY`; PKCS8; unencrypted key needs blank passphrase |
| Service account JSON (Google) | tBigQuery*, tGS*, tGoogleDrive* `OAuth Method = Service Account`, tPubSub*, tDataproc* | `Service account key` / `Service account credentials file` = path to JSON file on the **job runtime** machine | Alternatively `GOOGLE_APPLICATION_CREDENTIALS` env var for ADC where the connector supports "Application Default Credentials" (BigQuery TCK, unverified) |
| AWS static keys | tS3*, tRedshift* bulk (S3 staging), tDynamoDB*, tSQS*, tKinesis*, tAmazonEMR* | `Access Key`, `Secret Key`; `Credential Provider = Static Credentials` | Signature V4 is implicit in SDK v1.11+/v2; specify `Region` explicitly for non-us-east-1 buckets |
| AWS IAM role / instance profile | tS3Connection `Credential Provider = Inherit credentials from AWS role` (7.3 R-update+, 8.0) | Reads EC2/EMR instance metadata; falls back from a named `Profile` to the role if the profile is missing | Only works when the Job runs on the EC2/EMR/ECS host; fails in Studio on a laptop |
| AWS STS assume role | tS3Connection `Assume Role` checkbox: `Role ARN`, `Role session name`, `Session duration`, `STS endpoint` (e.g. `sts.amazonaws.com`), optional `External Id`, `Serial number`/`Token code` for MFA (unverified subset) | Regional STS endpoint needed in VPC-endpoint setups | |
| AWS Web Identity Token / Profile | tS3Connection `Credential Provider = Web Identity Token` / `Profile` (`Profile name`, `~/.aws/credentials`) | EKS IRSA uses web identity | |
| Azure account key | tAzureStorage* `Authentication type = Basic`: `Account Name`, `Account Key`; tAzureAdlsGen2* `Authentication method = Shared key` | | |
| Azure SAS | tAzureStorage* `Use Azure Shared Access Signature` + `Azure Shared Access Signature` URL `https://<storagename>.<service>.core.windows.net/<sastoken>`; tAzureAdlsGen2* `Shared Access Signature`; Snowflake Azure stage `SAS Token` | SAS has an expiry and service/resource scope; blob vs file vs queue vs table SAS differ | |
| Azure AD service principal | tAzureStorage* `Authentication type = Azure Active Directory`: `Tenant ID`, `Client ID`, `Client Secret`; tAzureAdlsGen2* `Azure Active Directory`; tAzureSynapse*/tCosmosDB* (unverified) | Table storage does NOT support AAD (7.3 note) | |
| Azure managed identity | tAzureStorageConnection `Authentication type = Managed identities` (8.0.1-R2023-03+) | Only on Azure VMs/AKS/Remote Engine in Azure | |
| Databricks PAT | tDBFSConnection/tDBFSPut/tDBFSGet `Endpoint` (`https://adb-<id>.<n>.azuredatabricks.net`) + `Token`; tDeltaLake* JDBC URL `jdbc:databricks://...;PWD=<token>` | Token field click `[...]` | |
| NetSuite token-based auth (TBA) | tNetSuiteConnection `Login type = Token-based`: `Consumer key`, `Consumer secret`, `Token ID`, `Token secret`, `Account`, `Role` | Basic login is deprecated by NetSuite; TBA requires an Integration record and Access Token in NetSuite | |
| Kerberos keytab | tKafka* (`Use Kerberos authentication`, `JAAS configuration path`, `Kafka brokers principal name`, `Set kinit command path`, `Set Kerberos configuration path` (standard variant, unverified)), HBase/HDFS/Hive (big-data-spark.md), tMongoDB (`Authentication mechanism = KERBEROS` (unverified)), tSAP (SNC via JCo props) | JVM flag `-Djava.security.auth.login.config=jaas.conf`; `-Djava.security.krb5.conf=krb5.conf` | |
| SASL/PLAIN, SCRAM, SSL for Kafka | tKafkaConnection/Input/Output `Use SSL/TLS` + tSetKeystore, `Security protocol` (`SASL_PLAINTEXT`, `SASL_SSL`), `SASL mechanism` (PLAIN/SCRAM-SHA-256/512), JAAS via `Kafka properties` table | Confluent Cloud = SASL_SSL + PLAIN with API key/secret | |
| TLS keystore/truststore | tSetKeystore (`Set TrustStore`, `TrustStore type JKS/PKCS12`, `TrustStore file`, `TrustStore password`, `Need Client authentication`, `KeyStore type/file/password`); FTPS keystore on tFTPConnection; `Use SSL` on tMongoDB*, tCassandra*, tElasticSearch*, tNeo4j* | tSetKeystore sets JVM-wide `javax.net.ssl.*` system properties for the rest of the Job; not supported in ESB routes | |
| API key / token header | tZendeskInput/Output (`API token`), tServiceNow* (Basic or OAuth), tJIRAInput/Output (`Basic` user + API token), tSplunkEventCollector (`Token` for HEC), tBox* (OAuth JWT or developer token (unverified)), Dropbox (`Access Token`) | | |
| SSH key | tSCP*, tSSH, tFTPConnection SFTP `Authentication method = Public key` (`Private key`, `Key Passphrase`) or `Public key and password` | OpenSSH `ed25519` keys fail on old JSch (<0.1.55); convert to RSA PEM or update Studio | |

## Proxy handling

| Layer | How | Scope | Notes |
| --- | --- | --- | --- |
| Studio itself (update sites, Feature Manager, license, Talend Cloud login) | `Window > Preferences > General > Network Connections` (`Active Provider = Manual`, HTTP/HTTPS host:port, bypass list) or `-Dhttp.proxyHost=... -Dhttp.proxyPort=... -Dhttps.proxyHost=... -Dhttps.proxyPort=... -Dhttp.nonProxyHosts=...` in `Talend-Studio-*.ini` after `-vmargs` | Studio JVM only, not the Jobs it runs | Feature Manager failing with "Unable to read repository" = proxy or blocked `update.talend.com`/`talend-update.talend.com` |
| Job at design time and runtime | `tSetProxy` (family Internet > Proxy): `Proxy type` HTTP / HTTPS / SOCKS / FTP, `Proxy host`, `Proxy port`, `Proxy user`, `Proxy password`; option `Set a JVM proxy` (unverified label) | Sets `http.proxyHost` etc. JVM-wide for the rest of the Job run; place on a tPreJob or as first subjob | Not for ESB routes/data services (affects whole Talend Runtime). Does NOT apply to SFTP (JSch) - tFTPConnection docs: "SFTP Support does not work with an HTTPS proxy, use tSetProxy"; with HTTP proxy select `FTPS Support` + `Passive` mode |
| Per-component proxy | `Use or save proxy` / `Use proxy` + `Host`, `Port`, `User`, `Password` on tSalesforce*, tRESTClient, tHTTPClient, tSOAP, tFileFetch, tSendMail (unverified), tGoogleDrive*, tBox*, tMarketo*, tDropbox* (varies) | Component only | tSalesforce* `Use or save the connection session`/`Use Proxy` lives in Advanced settings |
| JVM args on launchers / TAC / TMC engines | Job `Run > Advanced settings > Use specific JVM arguments` (saved in the item and exported launcher), TAC task JVM parameters, Remote Engine `engine.sh`/`etc/org.talend.ipaas.rt.jobserver.client.cfg` or `JAVA_OPTS` | Whole process | `-Dhttp.nonProxyHosts="localhost\|*.internal"` uses pipe separators |
| Couchbase | Couchbase SDK does not support proxies; tCouchbase* ignore tSetProxy | | |
| Authenticated proxies + Java 8u111+ | Basic auth to HTTPS proxies is disabled by default: add `-Djdk.http.auth.tunneling.disabledSchemes=` | | |

## Cloud: Amazon

Palette: `Cloud > Amazon > S3 | Redshift | DynamoDB | EMR | Aurora | MySQL | Oracle | Kinesis | SQS`.
Redshift/Aurora/AmazonMysql/AmazonOracle are JDBC families that follow the standard
DB pattern (Connection/Input/Output/Row/Commit/Rollback/Close, see components-core.md for
the shared Input/Output/Row parameters); only the Amazon-specific bits are listed here.

| Component | Purpose | Key settings / auth | Notes (license, version, TCK vs javajet) |
| --- | --- | --- | --- |
| tS3Connection | Open a reusable S3 client | `Access Key`/`Secret Key`; `Credential Provider` (Static Credentials / Inherit credentials from AWS role / Web Identity Token / Profile); `Assume Role` (+ `Role ARN`, `Role session name`, `STS endpoint` e.g. `sts.amazonaws.com`); `Region`; Advanced: `Config client` table (`connectionTimeout`, `socketTimeout`, `maxConnections`, `protocol`, `signerOverride`, `proxyHost`...), `Use path-style access`, `Encrypt` (unverified), `Endpoint`/`Specify AWS S3 endpoint` for S3-compatible stores (MinIO) | javajet; Open Studio. Inherit-from-role requires the Job to run on the EC2/EMR host |
| tS3Put | Upload a local file (or stream) to a bucket/key | `Bucket`, `Key`, `File`; `Server-Side Encryption` (SSE-S3 / SSE-KMS `KMS key id`); `Enable Accelerate Mode`; `Upload from stream` (unverified); `Use ... connection` | Returns `KEY`, `BUCKET` globals (unverified) |
| tS3Get | Download object to local file | `Bucket`, `Key`, `File`; `Server-Side Encryption`; `Use a specific version` | |
| tS3List | List objects as rows | `List all buckets objects` or `Bucket`/`Key prefix` table; `Use path-style access` | Schema: `bucket`, `key`, `size`, `lastModified`, `storageClass`, `owner` (unverified); iterate via `Iterate` link with `((String)globalMap.get("tS3List_1_CURRENT_KEY"))`, `..._CURRENT_BUCKET` |
| tS3Delete | Delete object(s) | `Bucket`, `Key`(s) table | |
| tS3Copy | Server-side copy between buckets/keys | `Bucket`, `Key`, `Destination bucket`, `Destination key`, `Server-Side Encryption` | Objects >5 GB need multipart copy (handled by TransferManager in newer versions) |
| tS3BucketCreate / tS3BucketDelete / tS3BucketExist / tS3BucketList | Bucket admin | `Bucket`, `Region`/location constraint | tS3BucketExist sets `..._EXIST` boolean global (unverified) |
| tS3Close | Close connection | `Component List` | |
| tRedshiftConnection | JDBC connection | `Host`, `Port` 5439, `Database`, `Schema`, `Username`, `Password`; `Additional JDBC Parameters` (`ssl=true&sslfactory=...`); `Use SSO`/`Use IAM credentials`-style JDBC auth via `Driver version` (unverified) | javajet; Redshift JDBC 4.2 driver (`com.amazon.redshift.jdbc42.Driver`) downloaded by Studio |
| tRedshiftInput / tRedshiftOutput / tRedshiftRow / tRedshiftCommit / tRedshiftRollback / tRedshiftClose | Standard DB pattern | tRedshiftOutput: `Action on table` (Default / Drop and create / Create if not exists / Clear / Truncate), `Action on data` (Insert / Update / Insert or update / Update or insert / Delete), `Distribution style`/`Dist key`/`Sort key` on table create (unverified) | Row-by-row INSERT is slow on Redshift; use bulk for >10k rows |
| tRedshiftOutputBulk | Write delimited file and upload to S3 (no load) | `Data file path at local`, `Append local file`, S3: `Access Key`/`Secret Key`/`Bucket`/`Key`/`Region`; `Compress the data file` (gzip), `Encrypt`, field/row separators, `Text enclosure`, `Encoding` | javajet |
| tRedshiftBulkExec | Run `COPY` from S3 / EMR / DynamoDB / remote hosts (SSH manifest) | `Data source type` (S3 / EMR / DynamoDB / Remote host); `Table`, `Action on table`; `Key`/`Bucket`; `Date format`, `Time format`, `Delimiter`, `Null as`, `Ignore header`, `Compressed by` (GZIP/LZOP/BZIP2), `Encrypted`, `Fixed width`, `JSON`/`Avro` format options, `STATUPDATE`, `COMPUPDATE`, `MAXERROR` (unverified subset) | COPY needs the Redshift cluster IAM role or the key pair to read the bucket; cross-region needs `REGION` |
| tRedshiftOutputBulkExec | Generates delimited/CSV file, uploads to S3, loads with COPY in one component | Union of the two above; `Delete local file after load` (unverified) | Standard "bulk" idiom for Redshift loads |
| tRedshiftUnload | `UNLOAD (select) TO 's3://...'` | `Query`, S3 `Bucket`/`Key prefix`, `Access Key`/`Secret Key` or `IAM role`, `Parallel`, `Delimiter`, `Compressed by`, `Escape`, `Add quotes`, `Encrypted`, `Allow overwrite`, `Manifest` (unverified subset) | Output is N files `key000`, `key001`... unless `Parallel` off |
| tAmazonAuroraConnection / Input / Output / Row / Commit / Rollback / Close | Aurora MySQL via MySQL driver | `DB Version` (MySQL 5 / Aurora), `Additional JDBC Parameters` `noDatetimeStringSync=true` default | Aurora Postgres: use tPostgresqlInput family or tAmazonAuroraOutput "Postgres" variant (unverified) |
| tAmazonMysqlConnection / Input / Output / Row / Commit / Rollback / Close | RDS MySQL (same engine as tMysql* with Amazon endpoint) | Standard MySQL params | Functionally identical to tMysql*; kept for metadata clarity |
| tAmazonOracleConnection / Input / Output / Row / Commit / Rollback / Close | RDS Oracle | `Connection type` SID / Service Name; `Oracle version` | Needs ojdbc jar (Install missing modules) |
| tDynamoDBConnection / tDynamoDBInput / tDynamoDBOutput / tDynamoDBClose | Key-value NoSQL | `Access Key`/`Secret Key` or `Inherit credentials from AWS role`, `Region`, `Endpoint` (DynamoDB Local); tDynamoDBInput: `Table Name`, `Use advanced key condition expression` + `Key condition expression`, `Filter expression`, `Value mapping` table (`:placeholder` -> column); `Action on table`; tDynamoDBOutput: `Action on data` Insert / Update / Delete (unverified), `Partition Key`/`Sort Key` columns, `Read capacity`/`Write capacity` when creating | javajet; also Spark Batch variants (big-data-spark.md). Scan vs Query: without key condition it scans the whole table |
| tAmazonEMRManage | Create / terminate EMR clusters from a Job | `Action` (Create / Terminate), `Cluster name`, `Release label` (`emr-6.x`), `Applications`, `Instance type/count`, `EC2 key pair`, `Log URI`, `Service role`/`Job flow role`, `Visible to all users`, `Wait for cluster to be ready` (unverified subset) | Big Data license; pairs with `tAmazonEMRListInstances`/`tAmazonEMRResize` in older versions (unverified) |
| tKinesisInput / tKinesisOutput / tKinesisInputAvro | Kinesis Data Streams | `Stream name`, `Region`/`Endpoint`, `Access Key`/`Secret Key`; Input: `Shard iterator type` (TRIM_HORIZON / LATEST / AT_SEQUENCE_NUMBER) | **Spark Streaming only** in Studio (big-data-spark.md); no Standard Kinesis component. For Standard jobs use tHTTPClient against the REST API or a Route cAWS-KINESIS |
| tSQSConnection / tSQSInput / tSQSOutput / tSQSMessageDelete / tSQSMessageChangeVisibility / tSQSQueueCreate / tSQSQueueDelete / tSQSQueueList / tSQSQueueAttributes / tSQSQueuePurge / tSQSClose | Simple Queue Service | `Queue URL` or `Queue name`; `Access Key`/`Secret Key` or role; Input: `Max number of messages` (1-10), `Visibility timeout`, `Wait time seconds` (long polling), `Delete the message after receive`; Output: `Message body` column, `Delay seconds`, `Message group id`/`Deduplication id` (FIFO) | Standard family (7.1+). Message is a String; JSON must be parsed with tExtractJSONFields |

## Cloud: Microsoft Azure

Palette: `Cloud > Microsoft > Azure Storage Blob | Azure Storage Queue | Azure Storage Table | Azure Data Lake Storage Gen2 | Azure Synapse | Cosmos DB | Event Hubs`.

| Component | Purpose | Key settings / auth | Notes (license, version, TCK vs javajet) |
| --- | --- | --- | --- |
| tAzureStorageConnection | Shared connection for Blob/Queue/Table components | `Account Name`; `Authentication type` Basic (`Account Key`) / Azure Active Directory (`Tenant ID`, `Client ID`, `Client Secret`) / Managed identities (8.0.1-R2023-03+); `Use Azure Shared Access Signature` + `Azure Shared Access Signature` (`https://<storagename>.<service>.core.windows.net/<sastoken>`); `Protocol` HTTPS/HTTP; `Endpoint suffix` (`core.windows.net`, `core.chinacloudapi.cn`, `core.usgovcloudapi.net`) | javajet (azure-storage SDK); Open Studio. Table storage does not support AAD |
| tAzureStorageContainerCreate / ContainerDelete / ContainerExist / ContainerList | Blob container admin | `Container name`, `Access control` (Private / Public container / Public blob) | ContainerExist sets `..._CONTAINER_EXIST` (unverified) |
| tAzureStoragePut | Upload local file(s) to blob | `Container name`, `Local folder`, `Azure Storage Folder`, `Use file list`/`Files` table with masks, `Keep existing file name`; `Blob type` Block / Append / Page (unverified) | Large files are chunked automatically |
| tAzureStorageGet | Download blobs | `Container`, `Local folder`, `Files` table (`Blob prefix`, `Include sub-directories`), `Keep remote folder structure`, `Die on error` | |
| tAzureStorageList | List blobs as rows / iterate | `Container`, `Blobs` table (prefix + include subdirs); globals `..._CURRENT_BLOB` | Iterate link to tAzureStorageGet per blob |
| tAzureStorageDelete | Delete blobs matching prefixes | `Container`, `Blobs` table | |
| tAzureStorageInputTable / tAzureStorageOutputTable | Azure Table storage rows | `Table name`; Input: `Use filter expression` (OData `PartitionKey eq 'x'`), `Name mappings`; Output: `Action on data` Insert / Insert or replace / Insert or merge / Merge / Replace / Delete, `Partition Key`/`Row Key` column mapping, `Process in batch` (100 max per batch, same partition) | No AAD auth (7.3 doc note) |
| tAzureStorageQueueCreate / QueueDelete / QueueList / QueueInput / QueueOutput / QueueInputLoop / QueuePurge | Azure Storage Queues | `Queue name`; QueueInput: `Number of messages` (<=32), `Peek`/`Delete the message`, `Visibility timeout`; QueueInputLoop: `Loop waiting time`; QueueOutput: `Time to live`, `Initial visibility delay` | Message body is String (base64 handled by SDK) |
| tAzureAdlsGen2Connection | ADLS Gen2 (DFS endpoint) | `Account Name`, `Endpoint suffix` (`dfs.core.windows.net`); `Authentication method` Shared key (`Shared key` field; pure-password or Java mode, 8.0.1-R2022-05+) / Shared Access Signature (`SAS token`) / Azure Active Directory (`Tenant ID`, `Client ID`, `Client Secret`; R2020-06+ on 7.3) ; 8.0 Output docs also describe Microsoft Fabric OneLake endpoints | TCK (Azure ADLS Gen2 connector `azure-dls-gen2`); subscription (unverified) |
| tAzureAdlsGen2Input / tAzureAdlsGen2Output | Read/write files in a filesystem path with schema | `Filesystem`, `Blob path`; `Format` CSV / Avro / JSON / Parquet (8.0) ; CSV: `Field delimiter`, `Record separator`, `Header`, `Encoding`, `Text enclosure`, `Escape`; Output: `Blob name template`, `Overwrite` | TCK; also Spark via tAzureFSConfiguration (big-data-spark.md) |
| tAzureAdlsGen2Get / tAzureAdlsGen2Put / tAzureAdlsGen2List / tAzureAdlsGen2Delete | File transfer and listing against ADLS Gen2 paths | `Filesystem`, `Blob path`, `Local folder`, `Recursive`, `Files` table; Delete has `Recursive` | TCK |
| tAzureSynapseConnection / Input / Output / Row / Commit / Rollback / Close / BulkExec / OutputBulk / OutputBulkExec | Synapse SQL pool (dedicated/serverless) via mssql JDBC | `Host` (`<ws>.sql.azuresynapse.net`), `Port` 1433, `Database`, `Authentication` SQL password / Azure AD password / Service principal (unverified subset); BulkExec: `COPY INTO` from ADLS/Blob (`Azure Storage` account, container, `Authentication` SAS/Storage key/Managed identity), `File format` CSV/Parquet | Formerly `tAzureSqlDWH*` (Azure SQL Data Warehouse) in 7.x; renamed Synapse in 7.3/8.0; old names remain as deprecated aliases (unverified). Subscription |
| tCosmosDBConnection / tCosmosDBInput / tCosmosDBOutput / tCosmosDBRow / tCosmosDBBulkLoad / tCosmosDBSQLAPIInput / tCosmosDBSQLAPIOutput / tCosmosDBClose | Cosmos DB | MongoDB API components mirror tMongoDB* (`Action on data`, `Mapping` with `Parent node path`); `Host` `<acct>.documents.azure.com`, `Port` 10255, `Use SSL`, `Database`, `Username`=account, `Password`=key; SQL API components: `Endpoint`, `Primary key`, `Database`, `Collection`, Input `Query` (SQL), Output `Action on data` Create / Upsert / Delete (unverified) | javajet; Mongo-API variants need Cosmos account created with MongoDB API |
| tAzureEventHubsInput / tAzureEventHubsOutput | Event Hubs (Kafka-compatible) | `Namespace`, `Event hub name`, `SAS key name`/`SAS key` or connection string; Input: `Consumer group` (`$Default`), `Receiver position` (start/end/offset/enqueued time), `Checkpoint store` (blob) (unverified) | 8.0 family, TCK-based (unverified). Alternative: tKafka* with `SASL_SSL`/`PLAIN` + connection string `$ConnectionString` against `<ns>.servicebus.windows.net:9093` |
| tAzureFSConfiguration | Spark-only filesystem config for ADLS/Blob | see big-data-spark.md | Spark |
| tMicrosoftOneLake* (unverified) | Fabric OneLake | per 8.0 ADLS Gen2 Output doc, OneLake is reached via ADLS Gen2 components with `onelake.dfs.fabric.microsoft.com` endpoint | |

## Cloud: Google

Palette: `Cloud > Google > BigQuery | Google Storage | Google Drive | Pub/Sub | Dataproc | Bigtable`.

| Component | Purpose | Key settings / auth | Notes (license, version, TCK vs javajet) |
| --- | --- | --- | --- |
| tBigQueryConnection | Shared BigQuery client | `Project ID`; `Authentication mode`/`Credential type` Service account (default in 8.0; `Service account key` JSON file via `[...]`) / OAuth 2.0 Access Token / Application Default Credentials (8.0, unverified) ; `Use Google Cloud Storage` staging settings for bulk | javajet (google-api-services-bigquery) with a TCK rewrite in later 8.0 R-updates (unverified) |
| tBigQueryInput | Run a query and stream rows | `Query` (Standard SQL; `Use legacy SQL` checkbox), `Result size` (Small = synchronous `jobs.query`, Large = `allowLargeResults` to a temp/destination table (unverified)), `Dataset location` / `Location` (EU/US/region - must match dataset) | Query cost = bytes scanned; timestamps come back as String/Long epoch depending on version |
| tBigQueryOutput | Write rows via GCS + load job (not streaming inserts) | `Dataset`, `Table`, `Action on data` Truncate / Append / Empty (unverified labels), `Bucket`, `File` (`gs://my_bucket/my_file.csv`, must be directly under bucket root), `Bulk file already exists in Google storage`, `Create directory if not exists`, `Table operation` Create if not exist / Drop and create / Truncate (unverified) | Writes a local CSV then uploads; needs Storage Object Admin on the bucket + BigQuery Data Editor + Job User |
| tBigQueryBulkExec | Load an existing GCS file into a table | `Bucket`, `File`, `Dataset`, `Table`, `Action on data`, `Field delimiter`, `Header rows to skip`, `Encoding`, `Allow quoted newlines`, `Source format` CSV/JSON/Avro/Parquet (unverified) | |
| tBigQueryOutputBulk | Write the local/GCS file only | Delimited file options | Pair with tBigQueryBulkExec |
| tBigQuerySQLRow | Execute DDL/DML without a flow (CREATE/MERGE/DELETE) | `Query`, `Dataset location`, `Propagate QUERY's recordset` (unverified) | Use for MERGE-based upserts; BigQuery has no row-level UPDATE from tBigQueryOutput |
| tBigQueryClose | Close | | |
| tGSConnection | Google Cloud Storage client | `Access Key`/`Secret Key` (HMAC interoperability keys, legacy javajet) or `Service account` JSON (8.0) | javajet; HMAC keys are per-user/per-service-account under Cloud Storage > Settings > Interoperability |
| tGSPut / tGSGet / tGSList / tGSDelete / tGSCopy | Object transfer and listing | `Bucket`, `Key`/`Object key`, `Local file`/`Local folder`, `Files` masks; List: `Bucket`, `Key prefix`, globals `..._CURRENT_KEY`/`..._CURRENT_BUCKET` | |
| tGSBucketCreate / tGSBucketDelete / tGSBucketExist / tGSBucketList | Bucket admin | `Bucket`, `Location`, `Storage class` (unverified) | |
| tGSClose | Close | | |
| tGoogleDriveConnection | Drive client | `OAuth Method`: Installed Application (Id & Secret) (`Client ID`, `Client Secret`, `Application Name`, `Data store path` for refresh token), Installed Application (JSON) (`Client secret JSON`), Service Account (`Service account JSON`); `Use Proxy`, `Use SSL` (unverified) | javajet; first run of Installed Application opens a browser consent at design time |
| tGoogleDriveCreate / tGoogleDrivePut / tGoogleDriveGet / tGoogleDriveCopy / tGoogleDriveDelete / tGoogleDriveList | Folder create, upload, download, copy, delete, list | `File name`/`Folder`/`Parent folder` by name or `Use folder ID`/`Access method` (By Name / By Id); Put: `Local file`, `Overwrite`, `Replace if existing`, `Upload mode` (Upload file / Expose as output stream / Read from input stream (unverified)); Get: `Export format` for Google Docs/Sheets (CSV/PDF/XLSX...); List: `Folder`, `Include subfolders`, `List mode` Files / Directories / Both; `Include trashed` (unverified) | Service accounts see only files shared with their email or in Shared Drives (`Include shared drives` option on newer versions, unverified) |
| tPubSubInput / tPubSubOutput / tPubSubInputAvro | Pub/Sub | `Project`, `Topic`, `Subscription` (Input), `Service account` JSON; Output `Message body`/`Attributes`; Input `Subscription type` Create if not exists (unverified) | **Spark Streaming only** in Studio (big-data-spark.md). Standard jobs: tHTTPClient to `pubsub.googleapis.com/v1/...:publish` or Route cGoogle... (none) |
| tGoogleDataprocManage | Create/delete Dataproc clusters | `Action`, `Project`, `Cluster name`, `Region`/`Zone`, `Image version`, `Master/Worker machine type`, `Number of workers`, `Service account` JSON | Big Data license; pairs with Spark Job `Dataproc` distribution (big-data-spark.md) |
| tBigtableInput / tBigtableOutput | Cloud Bigtable | `Project ID`, `Instance ID`, `Table`, `Service account`, Output `Column family` mappings | 8.0 (TCK, unverified); Spark variants exist |
| tGoogleAnalyticsInput (deprecated) | GA Core Reporting API v3 | `View ID`, `Dimensions`/`Metrics`, service account | Deprecated/removed with GA Universal Analytics EOL (2023); no GA4 component - use tHTTPClient against Data API v1 |

## Snowflake

Palette `Cloud > Snowflake`. TCK-based since 7.1 (connector id `snowflake`); Open Studio includes
the basic set (unverified), bulk/stage components are subscription. All components share the
connection block below or `Use an existing connection` from tSnowflakeConnection.

Connection block: `Account` (locator or `org-account`), `Snowflake Region` (legacy; prefer full
account identifier), `User Id`, `Authentication Type` Basic (`Password`) / Key Pair (`Private Key`,
`Private Key Passphrase`) / OAuth 2.0 (`Token` or client id/secret + `OAuth token endpoint`, 8.0
R-update) ; `Warehouse`, `Schema`, `Database`, `Role`; Advanced: `Login Timeout` (minutes),
`Tracing`, `Allow Snowflake to convert columns and tables to uppercase`, `Additional JDBC
Parameters` (`application=TALEND&...`), `Use custom region`/`Custom Region` (unverified).

| Component | Purpose | Key settings / auth | Notes (license, version, TCK vs javajet) |
| --- | --- | --- | --- |
| tSnowflakeConnection | Shared JDBC session | Connection block above; `Use custom Snowflake region` | TCK |
| tSnowflakeInput | Read from table or query | `Table Name` + `Condition` (WHERE clause) or `Manual Query`/`Query`; `Guess schema` via `Snowflake table` dropdown; Advanced: `Convert columns and table to uppercase`, `Fetch size` (unverified) | Timestamps mapped to `java.util.Date`; `TIMESTAMP_TZ` loses zone unless read as String |
| tSnowflakeOutput | Row-level Insert/Update/Upsert/Delete; internally the Snowflake loader stages the rows as files, runs COPY INTO a temporary table and then INSERT/MERGE into the target (not per-row JDBC statements) | `Table`, `Table Action` None / Drop and create / Create / Create if not exists / Drop if exists and create / Clear / Truncate (unverified labels); `Output Action` Insert / Update / Upsert / Delete; `Upsert Key Column`; Advanced: `Use Schema Date Pattern`, `Date Pattern`, `Convert empty strings to null`, `Use custom DB type` (unverified) | Plain JDBC batches (no stage); for >100k rows use tSnowflakeOutputBulkExec |
| tSnowflakeRow | Execute arbitrary SQL (`CALL proc()`, `MERGE`, `COPY INTO`) | `Query`, `Propagate QUERY's recordset`, `Die on error`, `Commit every` (unverified) | Session parameters like `ALTER SESSION SET TIMEZONE` via tSnowflakeRow on same connection |
| tSnowflakeOutputBulk | Write rows to a stage file (no COPY) | `Storage` Internal (`Stage Folder`) / S3 (`Region`, `Access Key`, `Secret Key`, `Bucket`, `Folder`) / Azure (`Protocol`, `Account Name`, `Container`, `Folder`, `SAS Token`); file options `Field Separator`, `Compress` (gzip), `Encoding`, `Use Custom Stage Path`/`Stage Name` (`@~`, `@%table`, `@mystage`) | TCK; S3 keys here are the stage keys, not the connection |
| tSnowflakeBulkExec | `COPY INTO` from existing staged files | Same `Storage` block; `Table`, `Table Action`, `Load Action` (unverified), `Copy Command Options` (`ON_ERROR=CONTINUE`, `PURGE=TRUE`, `FORCE`, `MATCH_BY_COLUMN_NAME`), `Delete Storage Files On Success`, `File Format` CSV/JSON/AVRO/PARQUET (unverified) | Monitor `COPY_HISTORY`/`LOAD_HISTORY` for rejects |
| tSnowflakeOutputBulkExec | Stage + COPY in one | Union of the two above | Standard Snowflake load idiom; Internal stage = no cloud credentials needed |
| tSnowflakeCommit / tSnowflakeRollback / tSnowflakeClose | Transaction + close | `Close Connection` on Commit | Autocommit is ON by default on the JDBC driver unless `Auto Commit` unchecked on tSnowflakeConnection (unverified) |
| tSnowflakeInputTable (unverified) | Older TCK dataset-style input using Repository dataset | | Appears in some 7.x builds; superseded by tSnowflakeInput |
| Snowflake metadata wizard | `Repository > Metadata > Snowflake` stores connection (datastore) and lets you `Retrieve Schema` of tables/views (dataset) | | TCK datastore/dataset model |

## Databricks and Delta Lake

Palette `Cloud > Databricks` (DBFS) and `Databases > Delta Lake` (JDBC). Spark-on-Databricks
cluster execution is in big-data-spark.md.

| Component | Purpose | Key settings / auth | Notes (license, version, TCK vs javajet) |
| --- | --- | --- | --- |
| tDBFSConnection | REST client to DBFS | `Endpoint` (`https://adb-<id>.<n>.azuredatabricks.net` or AWS workspace URL), `Token` (Personal Access Token via `[...]`) | javajet; subscription (Big Data) |
| tDBFSPut / tDBFSGet / tDBFSDelete | Upload/download/delete files on `dbfs:/` | `DBFS directory`, `Local directory`, `Files` masks, `Overwrite`; Get: `Keep remote structure` (unverified) | Uses DBFS REST API `/api/2.0/dbfs/*` (1 MB blocks); not suitable for TB loads - use cloud storage + mount |
| tDeltaLakeConnection / tDeltaLakeInput / tDeltaLakeOutput / tDeltaLakeRow / tDeltaLakeClose | SQL against Databricks SQL warehouse / cluster via Databricks JDBC | `JDBC URL` must start with `jdbc:databricks://` from 8.0.1-R2023-05 (older `jdbc:spark://` jobs need manual edit); `httpPath=/sql/1.0/warehouses/<id>`; `AuthMech=3;UID=token;PWD=<PAT>`; add `EnableArrow=0` to avoid Log4j2 conflict errors; Output: `Action on data` Insert / Update / Delete / Merge (unverified), `Table action` | javajet, DB family. Delta Lake Spark components (`tDeltaLakeInput/Output` in Spark Batch) are different: big-data-spark.md |
| Databricks Unity Catalog | 3-level names `catalog.schema.table` in `Table` field; `ConnCatalog`/`ConnSchema` JDBC params | | 8.0 R2023+ (unverified) |

## Salesforce

Palette `Business > Salesforce`. Studio 7.x/8.0 family is TCK-based (connector `salesforce`,
Partner WSDL + Bulk API); the 6.x javajet set had the same names. Components share a connection
block or `Use an existing connection` to tSalesforceConnection.

Connection block: `Connection type`/`Login Type` Basic (`User Id`, `Password`, `Security Key`
= security token appended to password) / OAuth (`OAuth2 flow type` JWT Flow or Implicit Flow:
`Client Id`, `Client Secret`, `Callback Host`/`Callback Port` (implicit), `Token File`; JWT:
`Issuer`, `Subject`, `Audience`, `Key Store`, `Key Store Password`, `Certificate Alias`,
`Expiration time`); `Salesforce URL` (`https://login.salesforce.com/services/Soap/u/<version>`,
`test.salesforce.com` for sandboxes); `API version` (e.g. `57.0`; the URL and the field must
agree); Advanced: `Timeout (milliseconds)`, `Use Proxy`/`Use or save proxy` (`Host`, `Port`,
`User`, `Password`), `Use HTTP Chunked`, `Client Id` (connected app name shown in Salesforce
login history), `Retry` settings (unverified labels), `Use SOAP compression`.

| Component | Purpose | Key settings / auth | Notes (license, version, TCK vs javajet) |
| --- | --- | --- | --- |
| tSalesforceConnection | Shared session (one login) | Block above; `Bulk Connection` checkbox (unverified) when the session will be used by Bulk components | Open Studio includes Salesforce. A session configured for Bulk must be paired with Bulk query mode; Query mode works only with non-bulk connections (community answer) |
| tSalesforceInput | SOQL read | `Module Name` (sObject; `Use custom module` for custom objects `Foo__c`), `Query Mode` Query / Bulk / BulkV2; `Query condition` (WHERE) or `Manual Query` (full SOQL, `Guess query`/`Guess schema`), `Include deleted records` (queryAll), `Column Name Delimiter` for relationship fields (`Account.Name` -> `Account_Name`), `Normalize Delimiter` for child relationship subqueries; Advanced: `Safety Switch` (unchecked allows >10k rows in-memory for relationships), `Batch Size` (QueryOptions 200-2000), `Use Soap Compression`, `Convert date to local`/`Use Date Pattern` (unverified) | Bulk: async CSV job (`Job Id` global), PK chunking NOT supported by the component; BulkV2 7.3 R-update+, needs API 41+; community error "Number of records should be less than or equal to 10001" when a Bulk batch result exceeds the CSV parser limit |
| tSalesforceOutput | Row-level DML via SOAP | `Module Name`, `Output Action` Insert / Update / Upsert / Delete; `Upsert Key Column` (External ID field); Advanced: `Extend Insert` (batch up to `Commit Level` rows per call, default 200), `Retrieve Insert Id` / `Retrieve Salesforce ID` (adds `salesforce_id` to output; only available when Extend Insert is OFF), `Ignore Null`, `Use Soap Compression`, `Reject`/`Main` output flows with `errorCode`/`errorFields`/`errorMessage` columns (unverified exact names), `Log File` | Hard-delete not available (SOAP delete -> recycle bin). Extend Insert off = 1 API call per row (slow; community: 9 min vs seconds) but per-row rejects |
| tSalesforceOutputBulk | Write a local CSV in Bulk API format | `Bulk File Path`, `Append`, `Ignore Null`, `Relationship mapping for upsert` table (polymorphic lookup `Account:External_Id__c`) | Pair with tSalesforceBulkExec |
| tSalesforceBulkExec | Submit CSV via Bulk API | `Module Name`, `Action` Insert / Update / Upsert / Delete / Hard delete (unverified), `Upsert Key Column`, `Bulk File Path`, `Bytes To Commit`/`Rows To Commit` per batch (max 10 MB / 10,000 rows), `Concurrency Mode` Parallel / Serial, `Wait Time Check Batch State`, `Bulk API V2`, `Use Content Type` CSV/JSON (unverified), outputs Main (successes with `salesforce_id`, `salesforce_created`) and Reject (`error`) | Bulk API limits: 15,000 batches / 24h (classic), 150 MB per V2 job |
| tSalesforceOutputBulkExec | OutputBulk + BulkExec | Union | Standard high-volume load idiom |
| tSalesforceGetServerTimestamp | Returns server time | Output schema `ServerTimestamp` (Date) | Use to stamp incremental loads consistently (UTC) |
| tSalesforceGetDeleted | `getDeleted(module, start, end)` | `Module Name`, `Start Date`, `End Date` (ISO `yyyy-MM-dd'T'HH:mm:ss'Z'` or Date), schema `Id`, `deletedDate` | Window max 30 days back and <= 30 days wide (Salesforce API limit) |
| tSalesforceGetUpdated | `getUpdated(module, start, end)` | Same; returns `Id` list then join with tSalesforceInput | Same window limits; minute granularity |
| tSalesforceEinsteinBulkExec / tSalesforceEinsteinOutputBulk / tSalesforceEinsteinOutputBulkExec | Push datasets to Einstein Analytics (CRM Analytics / Wave) via External Data API | `Dataset Name`, `Operation` Overwrite / Append / Upsert / Delete, `Edgemart Container` (app), `Metadata JSON` (auto-generated from schema), `Notification` settings | Subscription; Wave/Einstein naming retained |
| tSalesforceWaveBulkExec (old name) | Same as Einstein | | 6.x alias |
| Salesforce metadata wizard | `Repository > Metadata > Salesforce`: connection + `Retrieve Salesforce Modules` (datasets) | | TCK datastore/dataset |

## SaaS business apps

Palette `Business > Marketo | NetSuite | Workday | ServiceNow | Zendesk | Box | Dropbox | JIRA | Splunk`.
Most are TCK connectors delivered in 7.1+ and updated through Feature Manager / R-updates.

| Component | Purpose | Key settings / auth | Notes (license, version, TCK vs javajet) |
| --- | --- | --- | --- |
| tMarketoConnection | Marketo REST/SOAP session | `API Mode` REST (default) / SOAP (legacy, removed 8.0, unverified); `Endpoint address` (`https://<munchkin>.mktorest.com/rest`), `Client Access ID`, `Secret key` (Admin > LaunchPoint > View Details; endpoint under Admin > Web Services); Advanced: `Timeout`, `Max reconnection attempts`, `Attempt interval time` | TCK-ish (javajet with REST client) (unverified). `Repository > Metadata > Marketo` wizard exists (8.0 R2024-05 doc "Centralizing Marketo metadata") |
| tMarketoInput | Read leads, activities, lead changes, custom objects, companies, opportunities | `Operation` getLead / getMultipleLeads / getLeadActivity / getLeadChanges / getCustomObjects / describeCustomObject / listCustomObjects / getCompanies / getOpportunities (REST); `Lead Key Type` (email, id, cookie, ...), `Lead Key Values`, `List Param` (STATIC_LIST_NAME/ID), `Include Types` (activity type ids), `Since Date Time`/`Paging token`, `Batch Size` (<=300 REST), `Fields` mapping | REST quota 50,000 calls/day and 100 calls / 20 s per instance; `Max reconnection attempts` handles 606 rate-limit codes |
| tMarketoOutput | Sync leads / custom objects | `Operation` syncLead / syncMultipleLeads / syncCustomObjects / deleteCustomObjects / syncCompanies / deleteCompanies / syncOpportunities...; `Operation type`/`Action` createOnly / updateOnly / createOrUpdate / createDuplicate; `Lookup field` (`email`, `id`, `Munchkin cookie`), `De-dupe by`; `Batch Size` (<=300) | Main + Reject outputs with `Status`/`ERROR_MSG` |
| tMarketoListOperation | addToList / removeFromList / isMemberOfList | `List Param` STATIC_LIST_NAME / STATIC_LIST_ID, `List Param Value`, `Lead Key Type`, `Multiple Operation` | |
| tMarketoBulkExec | Bulk import leads/custom objects from a local CSV (REST bulk import API) | `Bulk Import To` Leads / CustomObjects, `Bulk File Path`, `Lookup Field`, `List Id`, `Partition Name`, `Log Download Path` (failures/warnings CSV), `Poll wait time`, `Timeout` | 8.0; async job with status polling; 10 MB per file, 10 concurrent jobs (Marketo limits) |
| tMarketoCampaign | Trigger/schedule smart campaigns, get campaigns | `Campaign action` getCampaigns / getCampaignById / scheduleCampaign / triggerCampaign (unverified), `Campaign Id`, `Lead Ids`, `Tokens` table, `Clone to program` | Not installed by default; install via Feature Manager |
| tNetSuiteConnection | NetSuite SOAP (SuiteTalk) session | `Version` NetSuite Deprecated (2019 component) / Netsuite SOAP (2019/2021/2025 component); `Endpoint` (`https://<acct>.suitetalk.api.netsuite.com/services/NetSuitePort_2025_1`), `Login type` Basic (`Email`, `Password`, `Role`, `Account`, `Application ID`) / Token-based (`Consumer key`, `Consumer secret`, `Token ID`, `Token secret`); `Account`, `Role` | Component named `tNetSuiteV2019Connection/Input/Output` until 8.0.1-R2023-02, then folded back into `tNetSuiteConnection/Input/Output` with the `Version` switch; original `tNetsuiteInput`/`tNetsuiteOutput` (lowercase s, API 2014.2/2016.2) are `(deprecated)` pages in 8.0 |
| tNetSuiteInput | Search a record type | `Record Type` (standard and custom records, fetched from the account), `Search Condition` table (`Field`, `Operator`, `Value`, join sub-record fields), `Body fields only` (skip sublists for speed), `Use custom fields`/`Custom fields` (resolved from `customFieldList`), `Page size` (<=1000), `Saved search` support via `Search Condition` on `savedSearchId` (unverified) | SuiteTalk concurrency governance: default 1 concurrent request per account unless SuiteCloud Plus; 429/`WS_REQUEST_BLOCKED` on parallel subjobs |
| tNetSuiteOutput | add / update / upsert / delete records | `Action` Add / Update / Upsert / Delete, `Record Type`, `Use Native Upsert` (external id), `Batch size` (<=100 per `addList`), custom fields mapping, Reject flow with `errorCode`/`errorMessage` | |
| tWorkdayInput | Read from Workday | `Authentication mode` OAuth 2.0 client credentials (`Tenant alias`, `Client ID`, `Client Secret`, `Authentication endpoint`) / SOAP - Login (`User`, `Password`); `Mode` Workday Query Language (WQL: `Query`), Report As A Service (`Report Owner`, `Report Name`, extra `Parameters`), Workday web services (8.0: `Service`, `Operation`, request XML); `Service endpoint` (`https://<host>/ccx/`) | TCK (`workday`), 7.3+. RaaS only takes effect with SOAP - Login auth mode (8.0 doc). RaaS URL `https://<host>/ccx/service/customreport2/<tenant>/<owner>/<Report_Name>` |
| tServiceNowInput / tServiceNowOutput | Table API | `Instance URL` (`https://<inst>.service-now.com`), `Authentication` Basic / OAuth 2.0 (`Client ID`, `Client Secret`, user+password ROPC); Input: `Table` (`incident`, `sys_user`, `cmdb_ci`), `Query` (encoded query `active=true^priority=1`), `Fields`, `Max records`/`Limit`, `Exclude reference link`, `Display value` (unverified); Output: `Action` Insert / Update / Delete, `Sys ID` column | TCK (`servicenow`), 7.0+ |
| tZendeskInput / tZendeskOutput | Zendesk Support API | `Server URL` (`https://<sub>.zendesk.com`), `Authentication` Basic / API Token (`Username/token` style) / OAuth token; Input: `Selection` Tickets / Users / Organizations / Requests..., `Query` (Search API syntax), `Resolve references`; Output: Create / Update / Delete on same objects | TCK (`zendesk`), 7.0+ |
| tBoxConnection / tBoxGet / tBoxPut / tBoxDelete / tBoxList / tBoxCopy | Box content | `Authentication` OAuth 2.0 with JWT (`Client ID`, `Client Secret`, `Enterprise ID`, `Public key ID`, `Private key`, `Passphrase`) via Box app config JSON, or `Developer token` (unverified); `Folder`/`File` by path or ID, `Overwrite`, `Local file` | TCK (`box`), 7.x; Box app must be authorized by the enterprise admin |
| tDropboxConnection / tDropboxGet / tDropboxPut / tDropboxDelete / tDropboxList | Dropbox v2 API | `Access Token` (long-lived or refresh via `App key`/`App secret`, unverified); `Path`, `Local file`, `Upload mode` (Upload entire file / Chunked, `Chunk size`), `Overwrite`/`Rename on conflict` | javajet (dropbox-core-sdk); Open Studio |
| tJIRAInput / tJIRAOutput | Jira Cloud/Server REST | `Host URL`, `Authentication` Basic (`User`, `Password`/API token) / PAT (unverified); Input: `Resource` Issue / Project, `JQL`/`Issue id`, `Batch size`; Output: `Action` Create / Update / Delete, `Resource`, JSON body column | TCK (`jira`), 7.0+ |
| tSplunkEventCollector | Send events to Splunk HTTP Event Collector | `Server URL` (`https://<host>:8088`), `Token` (HEC token), `Extended Event Metadata` (`index`, `source`, `sourcetype`, `host`, `time` columns), `Batch size`, `Disable SSL verification` (unverified) | TCK (`splunk`), 7.0+. Output-only; no Splunk search input component |

## Microsoft Dynamics and legacy ERP/CRM

| Component | Purpose | Key settings / auth | Notes (license, version, TCK vs javajet) |
| --- | --- | --- | --- |
| tMicrosoftCrmInput | Query Dynamics CRM / 365 entities | `Authentication Type` ON_PREMISE / ONLINE; `CRM Version` 2011 / 2015 / 2016 / 2018 (Dynamics 365) (unverified subset); ON_PREMISE: `Mode` NTLM / OAUTH 2.0, `Service root URL`/`Security Service URL` (ADFS/STS), `Domain`, `Username`, `Password`, `Max connection retries`; ONLINE: `Registered application type` Native App / Web App with delegated permissions, `Application ID`/`Client ID`, `Client Secret`, `OAuth authorization endpoint`, `Username`/`Password` (ROPC) with Authentication Code flow used first to obtain the token (8.0 late-2022 R-update); `Entity` (`account`, `contact`, custom `new_foo`), `Query` (FetchXML or `Filter` conditions via `Conditions` table, `Logical operator`), `Order by`; Advanced: `Reuse Http Client`, `Lookup mapping` (`Lookup type`, `Reference entity`) | javajet (odata-client for 2016+); Open Studio? subscription (unverified). AADSTS7000218 = client secret missing for a Web App registration |
| tMicrosoftCrmOutput | Create / Update / Delete entities | Same auth; `Action` Insert / Update / Delete; `Entity`; `Lookup mapping` table: `Input Column`, `Lookup Type` (entity logical name) for `EntityReference` columns; `Ignore Null`; Reject flow with `errorMessage` | Web API (2016+) uses `@odata.bind` for lookups |
| tMSAXInput / tMSAXOutput (Dynamics AX) | Dynamics AX 2012 via AIF .NET Business Connector | `Server`, `Company`, `Language`, `Table`, `Connection via .NET` | Deprecated/removed in 8.0 (Windows-only Business Connector); use OData/tHTTPClient against D365 F&O |
| tSugarCRMInput / tSugarCRMOutput | SugarCRM (SOAP v2/v4 API) | `Server URL` (`.../soap.php`), `Username`, `Password`, `Module` (Accounts, Contacts...), Output `Action` Insert / Update (via `id`) | Legacy javajet, Open Studio; SOAP API removed in Sugar 7+ -> use tHTTPClient against REST v11 |
| tVtigerCRMInput / tVtigerCRMOutput | vtiger CRM 5.x webservice | `Endpoint`, `Username`, `Access key`, `Module` | Legacy, unmaintained; Open Studio |
| tOpenbravoERPInput / tOpenbravoERPOutput | Openbravo ERP REST (XML) | `Endpoint`, `User`, `Password`, `Entity`/`Table` | Deprecated 7.x, removed 8.0 (unverified) |
| tCentricCRMInput / tCentricCRMOutput | Centric CRM (ConcourseSuite) | | Removed years ago (5.x era); only in very old exports |
| tSalesforceWave* | see Salesforce | | |
| tMicrosoftMQInput / tMicrosoftMQOutput | MSMQ via COM/.NET bridge | `Queue path` `.\private$\name` | Windows only; deprecated/removed in 8.0 (unverified) |
| SharePoint / Exchange | No native Studio components | Use tHTTPClient against Microsoft Graph (`/sites/{id}/drives`, `/users/{id}/messages`) with OAuth2 client credentials, or Route cMSGraph (none) | Pipeline Designer and Qlik Cloud have SharePoint/OneDrive connectors; Studio does not |

## SAP

Palette `Business > SAP`. Subscription-only (Data Integration / Data Fabric; Open Studio has no
SAP). All need `sapjco3.jar` + native `libsapjco3.so`/`sapjco3.dll` (SAP JCo 3.x, downloaded from
SAP Support Portal with S-user; Studio prompts "requires sapjco.jar" -> Install missing modules,
and the native lib must be on `java.library.path` / `PATH` / `LD_LIBRARY_PATH` of Studio,
JobServer and Remote Engine). IDoc components additionally need `sapidoc3.jar`. Table/BW streaming
needs the **Talend SAP RFC Server** (separate installer, `$TSAPS_HOME`; connections under
`$TSAPS_HOME/conf/named-connections` (doc snippet spelled "named-connectiond")), used as a
streaming proxy so large extractions avoid FTP/SFTP staging; its ABAP side needs the Talend
transport (`Z_TALEND_*` function modules) imported into the SAP system.

| Component | Purpose | Key settings / auth | Notes (license, version, TCK vs javajet) |
| --- | --- | --- | --- |
| tSAPConnection | JCo client connection | `Connection type` Application server (`Host`, `System number`, `Client`, `User`, `Password`, `Language`) / Message server (load balancing: `Message host`, `R3 name`, `Group`) ; `SAP Properties` table (any `jco.client.*` prop: `jco.client.snc_mode=1`, `jco.client.snc_partnername`, `jco.client.saprouter`, `jco.client.peak_limit`) ; `Use SAP router` | javajet; repository wizard `Metadata > SAP Connections` retrieves BAPIs, tables, IDoc types, BW objects |
| tSAPBapi | Call a BAPI/RFC with import/export/table/changing parameters, or document-type (XML) input | `Function Name` (e.g. `BAPI_CUSTOMER_GETLIST`, `BAPI_TRANSACTION_COMMIT`), `Input mapping` (parameter -> column or `Document` XML), `Output mapping` (output tables -> schemas, one output flow per table), `Use Document type parameter`, `Commit after each BAPI call`/`BAPI_TRANSACTION_COMMIT` (unverified) | Metadata wizard generates the schema per table parameter; `tSAPCommit` not needed when using BAPI_TRANSACTION_COMMIT |
| tSAPTableInput | Read a table/view with a filter | `Table name` (`MARA`, `KNA1`, `/BI0/PMATERIAL`), `Where clause`/`Filter condition` (ABAP OpenSQL syntax, 72-char line split handled), `Fields` (schema = selected columns), `Batch size`/`Rows per package`, `Use RFC Server`/`Streaming via Talend SAP RFC Server` (`RFC server host/port`, `Program ID`), `Row skips`/`Row count` (unverified subset) | Classic `RFC_READ_TABLE` limited to 512 bytes/row; Talend's `Z_TALEND_READ_TABLE` (via transport) removes the limit |
| tSAPIDocInput (deprecated) / tSAPIDocOutput / tSAPIDocReceiver | IDoc send/receive | Output: `IDoc type` (`DEBMAS07`), `Message type`, `Document` XML input flow (built with tXMLMap / tWriteXMLField from the wizard-generated IDoc schema), `Receiver port`/`Partner profile`; Receiver: registers as RFC server (`Program ID`, `Gateway host/service`, `Repository destination`), `Wait time`, outputs IDoc XML | tSAPIDocInput marked deprecated in 7.2; tSAPIDocReceiver is a listener component (runs until timeout/stop) |
| tSAPCommit / tSAPRollback | BAPI transaction control on a shared tSAPConnection | `Component List`, `Close Connection` | |
| tSAPDSOInput / tSAPDSOOutput | BW DataStore Object (classic DSO) read/write | `DSO name`, `Active table`/`Changelog`, filter | BW 7.x; RFC Server optional for streaming |
| tSAPADSOInput | BW/4HANA Advanced DSO read | `ADSO name`, `Table type` Active / Inbound (unverified), filter | Requires Talend transport + RFC server (unverified) |
| tSAPInfoObjectInput / tSAPInfoObjectOutput | BW InfoObject master data (attributes/texts/hierarchies) | `InfoObject`, `Data type` Attributes / Texts / Hierarchy | |
| tSAPInfoCubeInput | BW InfoCube (MDX via BAPI_MDPROVIDER / OpenHub style) | `InfoCube`, `MDX`/characteristics and key figures selection | Prefer ODP or ADSO on BW/4 |
| tSAPODPInput | Operational Data Provisioning (extractors, CDS views, BW objects) with delta | `Subscriber name`, `Context` (SAPI / ABAP_CDS / BW / HANA), `ODP name`, `Extraction mode` Full / Delta init / Delta, `Package size`, `Fields`, `Filter` | 7.3+; delta queue state kept per subscriber in SAP (ODQMON) |
| tSAPDataSourceReceiver / tSAPDataSourceOutput | Receive data pushed from a BW DataSource (3rd-party BW source system) / write to BW | `DataSource`, `Source system` (Talend registered as 3rd-party system via `RSA1`), RFC server `Program ID`; Output: `Target InfoProvider`, `Request handling` | Talend acts as the BW source system; requires BW admin setup |
| tSAPBWInput | Generic BW read (OpenHub destination table or MDX) | `Query`/`OpenHub destination` | Older component; DSO/ADSO/InfoCube/ODP are the focused successors |
| tSAPHanaConnection / Input / Output / Row / Commit / Rollback / Close / BulkExec / OutputBulk / OutputBulkExec / tSAPHanaUnload | SAP HANA as a JDBC database | `Host`, `Port` 3xx15, `Database`/`Schema`, `ngdbc.jar` driver; BulkExec = `IMPORT FROM CSV FILE` on server-side path (unverified) | DB family in `Databases > SAP HANA`; see components-core.md for shared params |

## NoSQL

Palette `Databases > NoSQL` (8.0) / `Big Data > NoSQL` (7.x). Most families: javajet with a
`DB Version` dropdown that selects the driver jar set; many also have Spark variants (big-data-spark.md).
HBase/Hive/HCatalog are in big-data-spark.md.

| Component | Purpose | Key settings / auth | Notes (license, version, TCK vs javajet) |
| --- | --- | --- | --- |
| tMongoDBConnection | Shared Mongo client | `DB Version` (3.x / 4.x driver; 8.0 adds 4.4+/5/6 via `mongo-java-driver` 4.x), `Use replica set address` + `Replica set` table (host/port rows; `Set read preference` Primary / Secondary / Nearest...), `Server`/`Port` 27017, `Database`, `Use SSL` (truststore via tSetKeystore), `Required authentication` + `Authentication mechanism` NEGOTIATE / PLAIN_SASL (LDAP) / SCRAM-SHA-1 / SCRAM-SHA-256 / KERBEROS / X.509 (unverified subset) + `Authentication database`, `Username`, `Password`; `Use connection string` (`mongodb+srv://...`) in newer 8.0 R-updates (unverified) | javajet; Open Studio. Atlas needs `mongodb+srv` (DNS seedlist) -> use connection string option or list all replica hosts with `Use SSL` |
| tMongoDBInput | Query a collection | `Collection`, `Query` (JSON `{ "status": "A", "qty": { "$gt": 25 } }`), `Mapping` table (`Column`, `Parent node path` for nested docs), `Sort by` table, `Limit`, `No query timeout`, `Aggregation pipeline`/`Use aggregation framework` (JSON stages, 7.x+), `Set read preference`, `Allow disk use` | Non-schema fields are dropped; use a single `Document`/`String` column + tExtractJSONFields for schemaless reads |
| tMongoDBOutput | Write documents | `Collection`, `Drop collection if exists`, `Action on data` Insert / Set / Upsert / Upsert with set / Update / Delete / Bulk write (unverified last), `Mapping` table (`Column`, `Parent node path`, `Remove null field` (unverified)), `Append to parent` (Set adds field to the parent node in Mapping), `Insertable`/`Updatable` columns (Upsert with set; R2020-08+), `Query`/`Keys` columns (which schema columns form the match filter; 7.2 used `Data node`/`Query node` on a JSON tree), `Bulk write` + `Bulk write size`, `Ordered`, `Write concern` (unverified) | `_id` as ObjectId: map a String column named `_id`; Upsert needs the key column in both Query and Mapping |
| tMongoDBRow | Run `db.runCommand` / JavaScript-ish command JSON | `Function`/`Command` JSON, `Execute command` or `Use a function` (unverified) | For `createIndex`, `renameCollection`, `aggregate` with `$out` |
| tMongoDBBulkLoad | Wrapper around `mongoimport` binary | `Mongoimport path`, `Data file`, `File type` JSON / CSV / TSV, `Action on data` Insert / Upsert, `Upsert fields`, `Drop`, `Headerline`, `Ignore blanks`, `Fields` | Needs mongo tools installed on the Job host |
| tMongoDBGridFSGet / tMongoDBGridFSPut / tMongoDBGridFSDelete / tMongoDBGridFSList / tMongoDBGridFSProperties | GridFS file store | `Bucket` (`fs`), `Query` (JSON on `filename`/metadata), `Local folder`, `Files` masks, `Metadata` table on Put | |
| tMongoDBClose | Close | | |
| tCassandraConnection / tCassandraInput / tCassandraOutput / tCassandraRow / tCassandraOutputBulk / tCassandraBulkExec / tCassandraOutputBulkExec / tCassandraClose | Cassandra CQL3 | `DB Version` (Cassandra 2.0 deprecated (Thrift `API type` CQL/Thrift) / 2.2 / 3.x / 4.x via `datastax java-driver`), `Host`, `Port` 9042, `Keyspace`, `Username`/`Password`, `Use SSL`, `Datacenter`/`Load balancing policy`; Input: `Query` (CQL, `Use query`), `Column family`/`Table`, `Consistency level`; Output: `Action on keyspace` / `Action on column family`, `Action on data` Insert / Update / Delete, `Replication` (`SimpleStrategy`/`NetworkTopologyStrategy`, `Replication factor`), `Use TTL`/`TTL column`, `Insert if not exists`, `Batch size`/`Use unlogged batch`, `Consistency level`; Bulk: `SSTable` generation + `sstableloader` path | javajet; Open Studio. DataStax Astra needs secure-connect bundle -> not supported; use tJDBC with Astra JDBC or REST |
| tNeo4jConnection / tNeo4jInput / tNeo4jOutput / tNeo4jRow / tNeo4jBatchOutput / tNeo4jBatchOutputRelationship / tNeo4jBatchSchema / tNeo4jImportTool / tNeo4jOutputRelationship / tNeo4jClose | Neo4j graph | `DB Version` Neo4j 2.x (embedded `Database path` or REST `Server URL`) / 3.x (Bolt `bolt://host:7687`, `Username`/`Password`) / 4.x+ (8.0 R-updates, `neo4j://` routing, unverified); Input: `Query` (Cypher `MATCH (n:Person) RETURN n.name`), `Mapping` of return columns; Output: `Node label`/`Index`, `Mapping`, `Create relationship` (`Relationship type`, `Direction`, start/end key columns), `Batch size`, `Commit every`; Row: Cypher DDL/DML (`CREATE INDEX`); BatchOutput: unsafe fast CSV import for new DBs | javajet; does not support 3.2.x (doc note); never mix 2.x and 3.x components in one Job (class conflict). Neo4j 5 Aura: use tJDBC with Neo4j JDBC driver or tHTTPClient (unverified) |
| tElasticSearchInput / tElasticSearchOutput / tElasticSearchConfiguration / tElasticSearchLookupInput | Elasticsearch index read/write | `Nodes` (`host:port` list), `Transport` HTTP (9200) / Node (9300, removed in ES 8) (unverified), `Index`, `Type` (removed ES 7+, `_doc`), `Use authentication` (`Username`/`Password`, API key via headers (unverified)), `Use SSL`; Input: `Query` (JSON query DSL), `Scroll size`/`Page size`; Output: `Action` Index / Upsert / Delete, `Id column`, `Batch size`/`Bulk size`, `Refresh` | Standard variants exist (7.x+, javajet, `elasticsearch-rest-client`) but most docs are Spark Batch/Streaming (big-data-spark.md). OpenSearch works over HTTP with Basic auth for ES 7-compatible versions |
| tCouchbaseConnection / tCouchbaseInput / tCouchbaseOutput / tCouchbaseClose (and Spark variants) | Couchbase Server bucket/collection | `Bootstrap nodes` (`couchbase://host1,host2`), `Bucket`, `Scope`/`Collection` (7.x server), `Username`/`Password` (RBAC), `Connection timeout`; Input: `Use N1QL query` + `Query` (`SELECT META().id, * FROM bucket WHERE ...`), or `Document type` JSON / String / Binary; Output: upserts documents built from flat input (`Id field`, `Generate document id`, `Content format` JSON / String / Binary, `Partial update` (sub-document), `Use N1QL query` for arbitrary DML), `Query parameters` mapping | TCK (`couchbase`), 7.1+; Couchbase SDK does not support proxies so tSetProxy is ignored |
| tCouchDBInput / tCouchDBOutput / tCouchDBConnection / tCouchDBClose | Apache CouchDB (HTTP) | `Server`, `Port` 5984, `Database`, `Username`/`Password`; Input: `Use view`/`Design document`/`View name` or `Document id`, `Mapping`; Output: `Action` Insert / Update / Delete, `Bulk documents` | Legacy javajet (ektorp); low maintenance; Open Studio |
| tMarkLogicConnection / tMarkLogicInput / tMarkLogicOutput / tMarkLogicBulkLoad / tMarkLogicClose | MarkLogic document database | `Host`, `Port` (REST app server 8000+), `Database`, `Username`/`Password`, `Authentication` Digest / Basic (unverified); Input: `Criteria`/`Query` (string query or structured), `Page size`, `Document type` XML / JSON / Text / Binary -> `docContent` column; Output: `Action` Upsert / Patch / Delete, `Doc id` column, `Collections`; BulkLoad: wraps MLCP (`MLCP path`, `Input file path`, `Input type`, `Output URI prefix`, extra `-options`) | TCK (`marklogic`), 7.1+; "available in Talend products with Big Data and in Talend Data Fabric" |
| tRedisConnection / tRedisInput / tRedisOutput / tRedisClose / tRedisKeyList (unverified) | Redis key-value | `Host`, `Port` 6379, `Password`, `Database index`, `Use cluster`/`Sentinel` (unverified); Input: `Key pattern`, `Data type` String / Hash / List / Set / ZSet; Output: `Action` Set / HSet / RPush / SAdd / ZAdd / Delete, `TTL` | Standard components exist in 7.x subscription palette (`Big Data > NoSQL > Redis`, javajet, Jedis) (unverified); also Spark Streaming variants |
| tDynamoDB* | see Cloud: Amazon | | |
| tCosmosDB* | see Cloud: Microsoft Azure | | |
| Amazon DocumentDB | Use tMongoDB* with `Use replica set` + `Use SSL` (RDS CA bundle in truststore) + SCRAM-SHA-1 | | No dedicated family |
| tRiakInput / tRiakOutput / tRiakConnection (deprecated) | Riak KV | `Node`, `Bucket`, `Key` | Deprecated 6.x, removed 7.x/8.0 (unverified) |
| ArangoDB, Aerospike, ScyllaDB | No native components | tJDBC (ArangoDB JDBC), tCassandra* for Scylla (CQL-compatible), tHTTPClient | |
| tHBase*, tHive*, tHCatalog*, tHDFS*, tSqoop*, tImpala* | Hadoop ecosystem | big-data-spark.md | |

## Messaging

Palette `Internet > Kafka | JMS | MOM | MQTT | RabbitMQ` (8.0; 7.x had `Big Data > Kafka`).
Standard components are listed; Spark Streaming counterparts carry the same names and are
documented in big-data-spark.md.

| Component | Purpose | Key settings / auth | Notes (license, version, TCK vs javajet) |
| --- | --- | --- | --- |
| tKafkaConnection | Shared broker config | `Version` (Kafka client 0.9/0.10/1.x/2.x/3.x per Studio release), `Broker list` (`host1:9092,host2:9092`), `Use SSL/TLS` (+ tSetKeystore), `Use Kerberos authentication` (`JAAS configuration path`, `Kafka brokers principal name`, `Kerberos configuration path`, `Set kinit command path`), `Kafka properties` table (`security.protocol=SASL_SSL`, `sasl.mechanism=PLAIN`, `sasl.jaas.config=...`, `ssl.endpoint.identification.algorithm=`) | javajet; Open Studio has Kafka Standard components (unverified); Spark versions need Big Data |
| tKafkaInput | Consume messages (String or byte[]) | `Topic name`, `Consumer group id` (created at runtime if absent), `Reset offsets on consumer group` (discard committed offsets), `New consumer group starts from` beginning / latest (only used when the group has no committed offset), `Auto-commit offsets` + `Interval` or manual commit via tKafkaCommit, `Stop after a maximum number of messages`/`Stop after receiving a maximum number of messages`, `Stop after a maximum total duration (ms)`, `Stop after a maximum time without receiving a message (ms)`, `Max poll records`, `Output type` String / byte[] (`Serializer`), `Consumer properties` table (`max.partition.fetch.bytes`, `isolation.level=read_committed`); Advanced: `Load the offset with the message` (adds `offset`/`partition`/`key`/`timestamp` columns, unverified) | Runs forever unless a `Stop after...` option is set; use with `Iterate`-less flow into tMap/tExtractJSONFields. Job-script key `AUTO_OFFSET_RESET_NEW` = EARLIEST/LATEST |
| tKafkaOutput | Produce | `Topic name`, `Compress the data` (gzip/snappy/lz4/zstd), `Serializer` String/byte[], `Key` column (`Set a key column` / `Use key`), `Producer properties` table (`acks=all`, `enable.idempotence=true`, `linger.ms`, `batch.size`, `max.request.size`) | Message = one input row's single column (String/byte[]); build JSON upstream with tWriteJSONField |
| tKafkaCommit | Commit consumer offsets of a tKafkaInput on the same connection | `Component List` (the tKafkaInput) | Place after the processing subjob to get at-least-once semantics |
| tKafkaCreateTopic | Admin create topic | `Topic`, `Partitions`, `Replication factor`, `Action on topic` Create / Create if not exists, `Topic properties` (`retention.ms`) | 7.x+ |
| tKafkaInputAvro | Consume Avro with schema | `Avro schema`/Schema Registry URL (`schema.registry.url` in properties) | Spark Streaming only (big-data-spark.md); in Standard Jobs consume byte[] with tKafkaInput and decode with a routine/tJavaRow using the Avro or Confluent deserializer (tLibraryLoad) |
| tJMSInput / tJMSOutput | Generic JMS 1.1 via JNDI | `Context Provider` (`org.apache.activemq.jndi.ActiveMQInitialContextFactory`, `com.sun.jndi.fscontext.RefFSContextFactory` for IBM MQ bindings, `org.jboss.naming.remote.client.InitialContextFactory`, `org.apache.qpid.jms.jndi.JmsInitialContextFactory` for AMQP 1.0), `Server URL` (`tcp://host:61616`, `file:/path/.bindings`), `Connection Factory JNDI Name` (`ConnectionFactory`), `Use Specified User Identity` (`User`, `Password`), `Message Type` Queue / Topic, `To`/`From` (destination name; ActiveMQ `dynamicQueues/foo` style via JNDI props), `Message Selector` (SQL92), `Timeout`, `Maximum Messages`, `Processing Mode` Raw message / Message content (unverified), `Properties` table (JNDI env), `Durable subscription`/`Client ID` (Topic), Output: `Delivery mode` Persistent / Non persistent, `Priority`, `Time to live`, `Message properties` table, `Reply to` (unverified); Advanced: `Transacted`/`Acknowledgement mode` AUTO / CLIENT / DUPS_OK | javajet; Open Studio. The JMS provider client jars (activemq-all, com.ibm.mq.allclient + jms.jar, artemis-jms-client) must be added via `Modules`/tLibraryLoad; mismatched versions = `ClassNotFoundException`/`NoSuchMethodError` at runtime |
| tMomConnection / tMomInput / tMomOutput / tMomCommit / tMomRollback / tMomClose / tMomMessageIdList (unverified) | Vendor-specific MOM shortcuts | `MQ Server` ActiveMQ / JBoss Messaging / WebSphere MQ; `Host`, `Port` (61616 / 1414), `Username`/`Password`; WebSphere MQ only: `QueueManager`, `Channel` (default `DC.SVRCONN`), `MessageQueue`, `Set Transacted`, `Target client` MQ / JMS (unverified), `CCSID`; ActiveMQ: `Failover` (`failover:(tcp://a,tcp://b)`), `Static Discovery`, `Transport options` table; Input: `Message Type` Queue/Topic, `To`/`From`, `Timeout`, `Maximum messages`, `Message body type` String / byte[] (`Use byte[]`), `Get message id`/`Get message headers`; Output: `Message` column, `Delivery mode` | javajet; IBM MQ needs `com.ibm.mq.allclient.jar` (not downloadable by Studio; license). 8.0 docs also list newer `tMessagingInput`/`tMessagingOutput` (JMS family) that delegate to "Configure JMS producers / WebSphere MQ connector" pages (unverified details) |
| tMessagingInput / tMessagingOutput | 8.0 unified messaging (JMS/WMQ) components | `Connection` type, `Destination`, `Message format`; see 8.0 `mom`/`jms` family pages | 8.0 R-update additions (unverified scope) |
| tRabbitMQInput / tRabbitMQOutput / tRabbitMQConnection / tRabbitMQClose (unverified names) | AMQP 0-9-1 | `Host`, `Port` 5672, `Virtual host`, `Username`/`Password`, `Use SSL`; Input: `Queue`, `Auto ack`/`Prefetch`, `Stop after N messages`; Output: `Exchange`, `Routing key`, `Durable`, `Message properties` | Standard RabbitMQ components exist only in newer 8.0 R-updates / Routes (`cMQ`/`cRabbitMQ`) (unverified); classic workaround is tJMSInput with Qpid JMS AMQP 1.0 client or Route cAMQP |
| tMQTTInput / tMQTTOutput | MQTT 3.1.1 (Eclipse Paho) | `Broker URL` (`tcp://host:1883`, `ssl://...`), `Topic`, `QoS` 0/1/2, `Client ID`, `Username`/`Password`, `Clean session`, `Retained` (Output) | Spark Streaming components in Studio; Standard MQTT via Route `cMQTT` (esb-routes-services.md). No Standard tMQTT* (unverified) |
| tPubSubInput / tPubSubOutput, tKinesisInput / tKinesisOutput | Google Pub/Sub, AWS Kinesis | Spark Streaming only (see Cloud sections) | |
| tAzureEventHubsInput / tAzureEventHubsOutput | Event Hubs | see Cloud: Microsoft Azure | |
| tSQS* | AWS SQS Standard components | see Cloud: Amazon | |
| IBM MQ | tMomInput/Output `MQ Server = WebSphere MQ` (native MQ classes) or tJMSInput/Output with `.bindings` JNDI file (`com.sun.jndi.fscontext.RefFSContextFactory`) created by `JMSAdmin`; Route `cMQConnectionFactory` + `cJMS`/`cWMQ` | | |
| cKafka, cJMS, cMQTT, cAMQP, cMQConnectionFactory | Route (Camel) messaging components | esb-routes-services.md | cKafka `Auto Offset Reset` EARLIEST / LATEST / NONE |

## Internet

Palette `Internet > FTP | SCP | HTTP | REST | SOAP | Mail | Socket | Proxy | SSH`.

| Component | Purpose | Key settings / auth | Notes (license, version, TCK vs javajet) |
| --- | --- | --- | --- |
| tFTPConnection | FTP / FTPS / SFTP session | `Host`, `Port` (21 / 990 implicit FTPS / 22 SFTP), `Username`, `Password`; `SFTP Support` + `Authentication method` Password / Public key (`Private key`, `Key Passphrase`) / Public key and password; `FTPS Support` + `Keystore File`/`Keystore Password` (server private key or client cert), `Security mode` Implicit / Explicit, `Protection level` (unverified), TLS version (Java 17: session resumption between control and data connection only with `TLSv1.2` + specific JVM props per 8.0 doc); `Connection Mode` Passive / Active; `Encoding` (`ISO-8859-1` default for FTP control channel); Advanced: `Use Socks Proxy` (`Proxy host/port/user/password`), `Ignore failure at quit`, `Connection timeout`, `Data channel timeout`/`Keep alive` (unverified) | javajet (commons-net + JSch); Open Studio. SFTP + HTTPS proxy is unsupported: use tSetProxy; with an HTTP proxy choose `FTPS Support` + `Passive`. `Use Perl5 Regex Expression as Filemask` option on list/get components |
| tFTPPut / tFTPGet | Upload/download by masks | `Local directory`, `Remote directory`, `Files` table (`Filemask`, `New name`), `Transfer mode` ASCII / Binary, `Overwrite file` Never / Always / Size differs / ... (unverified), `Append`, `Create directory if not exists` (Put), Get: `Delete remote files after transfer` (unverified), `Ignore failure at quit` | Globals `..._NB_FILE`, `..._CURRENT_FILE`, `..._CURRENT_STATUS`, `..._TRANSFERRED_FILES` list (unverified) |
| tFTPFileList | Iterate remote files/dirs | `Remote directory`, `Files` masks, `Include subdirectories`, `Order by` Name / Size / Modified date (unverified), `List type` Files / Directories / Both; globals `..._CURRENT_FILE`, `..._CURRENT_FILEPATH`, `..._CURRENT_FILEDIRECTORY`, `..._NB_FILE` | Iterate link to tFTPGet / tFTPDelete |
| tFTPFileExist | Check a remote file | `Remote directory`, `File name`; global `..._EXISTS` (boolean) | |
| tFTPFileProperties | Size, mtime, permissions of a remote file | Output schema `abs_path`, `dirname`, `basename`, `mode_string`, `size`, `mtime`, `mtime_string` (unverified subset) | |
| tFTPDelete / tFTPRename / tFTPTruncate | Remove / rename / empty remote files | `Files` table; Rename has `Filemask`/`New name`; Truncate writes zero-length | |
| tFTPClose | Close session | | |
| tSCPConnection / tSCPGet / tSCPPut / tSCPDelete / tSCPFileExists / tSCPFileList / tSCPRename / tSCPTruncate / tSCPClose | SCP over SSH (JSch) | `Host`, `Port` 22, `Username`, `Authentication method` Password / Public key (`Private key`, `Passphrase`), `Files` masks, `Local/Remote directory`, `Overwrite` | Open Studio. Strict host key checking off by default (unverified); ed25519 keys need newer JSch (8.0) |
| tSSH | Run remote commands over SSH | `Host`, `Port`, `User`, `Authentication method` Password / Public key / Keyboard interactive (unverified), `Commands` table (one row per command), `Timeout`, `Pseudo terminal`, `Standard output`/`Error output` columns, `Die on error`/`Exit code` global `..._EXIT_CODE` | `System` family in 7.x (orchestration-logging.md covers tSystem); listed here as a connector |
| tFileFetch | HTTP(S) GET/POST download to file or stream | `Protocol` http / https / ftp (unverified), `URI`, `Method` GET / POST, `Destination directory`, `Target file name`, `Headers` table, `Use cache` (ETag/If-Modified-Since-based reuse of local copy), `Upload file` (multipart POST with `File name`/`Field name`), `Read cookie`/`Save cookie` files, `Use authentication` (Basic), `Use proxy`, `Post parameters` table, `Timeout`, `Expose stream` (flow via `tFileFetch_1_INPUT_STREAM` to a tFileInput* `Use existing stream`), `Die on 4xx/5xx` via `Check response code` (unverified), `Disable SSL certificate validation` (unverified) | javajet; Open Studio. For APIs with JSON bodies use tHTTPClient/tRESTClient instead |
| tHttpRequest | Simple HTTP GET/POST returning body as String row | `URI`, `Method` GET / POST, `Post parameters`, `Write response content to file` / `Response file`, `Need authentication` (Basic), `Headers` table (7.x+), `Use proxy`, `Follow redirects`, `Timeout`, `Response encoding`, global `..._RESPONSE_CODE` (unverified) | javajet, Open Studio; superseded by tHTTPClient |
| tHTTPClient | 8.0 TCK HTTP client (recommended over tRESTClient per 8.0 doc) | `Base URL` + `Path`/`Resource`, `Method` GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS, `Authentication` None / Basic / Digest / Bearer / OAuth 2.0 client credentials (`Token endpoint`, `Client ID`, `Client Secret`, `Scopes`) / NTLM / API key (header or query) (unverified subset), `Query parameters`, `Headers`, `Body` type Raw (text/JSON/XML) / Form data / Multipart (`File` parts), `Timeout`, `Max redirects`, `Accept redirections`, `Bypass server certificate validation`; Response: `Output body format` Raw text / JSON / XML / Bytes, `Output key/value pairs`, `Pagination` (Offset/limit or Page or Cursor/Next link with JSONPath `Next page path`), `Die on error` on HTTP >= 400, response `headers` and `status` columns (unverified names), `Response payload as a file`/`Download file` | TCK (`http`); 8.0.1-R2022+; Open Studio? subscription (unverified). Pipeline Designer "HTTP Client" connector is the same TCK code |
| tRESTClient | CXF-based REST client (ESB REST family but usable in DI Jobs) | `URL`, `Relative Path`, `HTTP Method` GET / POST / PUT / PATCH / DELETE, `Content Type` XML / JSON / FORM / TEXT / ANY, `Accept Type` XML / JSON / ANY (ANY -> response as String), `Query parameters` (name/value), `Headers` (name/value), input `body` column (String or Document) when POST/PUT, `Use Authentication` None / Basic HTTP / OAuth2 Bearer (`Token`) / HTTP Digest / Kerberos (SPNEGO) / SAML (unverified subset), `Use Service Registry`/`Use Service Locator`/`Use Authorization` (Talend ESB infrastructure), `Use SSL`/`Trust server certificate` via tSetKeystore; Advanced: `Convert Response To DOM Document` (Document type `body` instead of String), `Log messages`, `Connection timeout`/`Receive timeout` (ms), `Disable chunking`, `Use proxy`, `Drop JSON request root` (unverified), `Enable JSON-to-XML conversion`; Outputs `Response` (`statusCode`, `body`, `string`/`headers` via `Response` schema) and `Error` flows (unverified names) | javajet (Apache CXF JAX-RS client); Open Studio includes it. Prefer tHTTPClient in 8.0 for OAuth and pagination; keep tRESTClient when ESB registry/SAML needed |
| tREST (deprecated) | Minimal REST call (HttpClient 3) | `URL`, `HTTP Method`, `HTTP Headers` table, `HTTP Body` (POST/PUT) | Deprecated since 6.x; output `Body` String only; replaced by tRESTClient/tHTTPClient |
| tSOAP | Call a SOAP 1.1/1.2 endpoint with a raw envelope | `ESB`/`Use NTLM`/`Use Authentication` (Basic, `Domain` for NTLM), `Endpoint`, `SOAP Action`, `SOAP version` 1.1/1.2, `Message` (envelope String from upstream, typically tXMLMap or tFixedFlowInput), `Use proxy`, `Trust server with SSL`/`Use SSL` (tSetKeystore), Output `Body` as String or `Output in Document` (XML Document type) , `Header` column, `Die on error` on SOAP faults | javajet; Open Studio. Pair with tXMLMap to parse the response Document |
| tWebService | WSDL-driven SOAP client with a mapping editor (`Component > Advanced > Edit`/`...` opens the Web Service editor) | `WSDL` URL/file, `Service`/`Port`/`Operation` (fetched by `Refresh`), input/output mapping in the editor (drag columns to request parts), `Use authentication`, `Use http proxy`, `Trust server with SSL`, `Timeout` | javajet (Axis2/CXF code generated at design time into the Job); Open Studio. Complex schemas (choice/any) often fail - fall back to tSOAP + tXMLMap |
| tWebServiceInput (deprecated) | Older WSDL client, flat result | `WSDL`, `Method`, `Parameters` table, `Advanced Use` (Java code) | Deprecated 5.x+, still shipped; replace with tWebService or tSOAP |
| tXMLRPCInput (deprecated, unverified) | XML-RPC call | `Server URL`, `Method`, `Parameters` | Legacy |
| tSocketInput / tSocketOutput | Raw TCP socket row exchange between Jobs/processes | `Host`, `Port`, `Timeout`, `Row separator`/`Field separator`, `Escape char`/`Text enclosure`, `Encoding`, Input `Timeout` then stop (unverified) | Open Studio; tSocketOutput sends a delimited stream; used for simple inter-process piping |
| tSetProxy | JVM-level proxy for the rest of the Job | see Proxy handling | Open Studio |
| tSendMail / tPOP / tFileInputMail | Mail | see XML, JSON, LDAP, Mail | |

## XML, JSON, LDAP, Mail

| Component | Purpose | Key settings / auth | Notes (license, version, TCK vs javajet) |
| --- | --- | --- | --- |
| tXSLT | Apply an XSLT stylesheet to a file | `XML file`, `XSL file`, `Output file`, `Parameters` table (name/value passed to `<xsl:param>`) | javajet; Open Studio; XSLT 1.0 via JDK Xalan unless Saxon added with tLibraryLoad + `javax.xml.transform.TransformerFactory` system prop |
| tDTDValidator / tXSDValidator | Validate XML file against DTD / XSD | `DTD file`/`XSD file`, `XML file` (`Mode` File / Flow for tXSDValidator: validate a `Document` column), `If XML is valid`/`If XML is invalid` output messages, `Print to console`; valid/invalid routed by `If XML is valid` / `If XML is invalid` triggers; no row flows (unverified) | Open Studio |
| tExtractXMLField | Parse XML held in a String/Document column into columns via XPath | `XML field` (input column), `Loop XPath query`, `Mapping` table (`Column`, `XPath query`, `Get Nodes`), `Limit`, `Ignore DTD file`, `Ignore the namespaces` / `Namespace` table, `Generation mode` Dom4j / SAX (unverified), `Encoding` | Open Studio; see tmap-expressions.md for tXMLMap as the alternative |
| tWriteXMLField | Build an XML String/Document column from flow using a tree editor | `Output Column` (String or Document), `Configure XML Tree` (loop element, group by, attributes), `Remove root`? / `Create empty element if needed`, `Encoding`, `Advanced separator`, `Trim data`, `Compact format` | Open Studio |
| tAdvancedFileOutputXML | Write a multi-level XML file via tree mapping | `File Name`, `Configure XML Tree` (loop element, `Group by`, `Set As Attribute`, `Set As Loop Element`), `Append the source xml file`, `Create directory if not exists`, `Split output in several files` (`Rows in each output file`), `Encoding`, `Compact format`, `Generation mode` Slow and memory-consuming (DOM) / Fast with low memory (SAX) (unverified labels), `Advanced separator` | Open Studio; for DTD/XSD-driven output use the schema import (`Import from XSD`) in the tree editor |
| tFileOutputXML, tFileInputXML | Simple XML file I/O | components-core.md | |
| tXMLMap | Hierarchical mapping | tmap-expressions.md | |
| tExtractJSONFields / tWriteJSONField / tFileInputJSON / tFileOutputJSON | JSON | `Read By` JsonPath / XPath / JsonPath without loop, `Loop Jsonpath query`, `Mapping` (`Json query`); tWriteJSONField same tree editor as XML with `Remove root node` | components-core.md owns these; listed as pointers |
| tLDAPConnection | Bind to a directory | `Host`, `Port` 389 / 636, `Base DN` ("path to user's authorized tree leaf"), `Protocol` LDAP / LDAPS / TLS (StartTLS), `Authentication` Simple (`User` = bind DN, `Password`) / Anonymous, `Advanced CA` (truststore via tSetKeystore or `Use certificate`/`Keystore path` (unverified)), `Referrals` Ignore / Follow, `Alias dereferencing` Always / Never / Searching / Finding | javajet (JNDI); Open Studio |
| tLDAPInput | Search with filter | `Filter` (RFC 4515, e.g. `(&(objectClass=person)(uid=jdoe))`), `Multi-valued field separator` (`,`), `Alias dereferencing`, `Referrals handling`, `Limit`/`Time limit`, `Paging` (`Page size`, AD 1000-entry cap), schema column `DN` returns the entry DN, `Fetch attributes` list from the schema columns, `Binary attributes` (`objectGUID`, `objectSid`; `Use binary field`?) (unverified) | Attribute names in schema must match LDAP attribute names (`sAMAccountName`, `memberOf`); multi-valued attributes join with the separator |
| tLDAPOutput | Add / Update / Delete entries | `Insert`/`Update`/`Delete`/`Insert or update` via `Mode`, `Multi-valued field separator`, `Use attribute options` / `Attribute options` table (operation per attribute: Add / Replace / Remove), `DN` column required for the entry (Base DN = highest reachable leaf when full DN comes from tMap) | Password attribute `unicodePwd` on AD needs LDAPS + UTF-16LE quoted value |
| tLDAPAttributesInput | List attributes of entries matching a filter | `Filter`, output `Attribute`/`Value`/`DN` rows (schema fixed) | Schema discovery for unknown directories |
| tLDAPRenameEntry | Rename / move DN | `Filter` or `DN` input column, `New DN`/`Rename to`, global `GetResultName` for retrieving the base DN automatically (doc mention) | |
| tLDAPClose | Close | | |
| tSendMail | SMTP send with attachments | `To`/`From`/`Cc`/`Bcc`, `Subject`, `Message` (text or HTML with `MIME subtype` plain/html, `Encoding`), `Attachments` table (file paths; `Die if the attachment file doesn't exist` checkbox default on), `Headers` table (custom MIME headers), `SMTP host`/`Port` (25 / 587 STARTTLS / 465 SSL), `SSL support` (implicit SSL; for 587 use `STARTTLS support` (7.3+, unverified label)), `Need authentication` (`Username`, `Password`), `Importance`, `Die on error`; Advanced: `Debug mode` (JavaMail debug), `Set smtp socket timeout` (unverified) | javajet (JavaMail); Open Studio. Gmail: port 465 + `SSL support` + app password (community). Office 365: 587 + STARTTLS; Basic auth disabled by Microsoft -> use OAuth2 via tHTTPClient (Graph `sendMail`) or an SMTP relay |
| tPOP | Download messages (POP3/IMAP) to files | `Protocol` POP3 / IMAP, `Server`, `Port` (110/995, 143/993), `Username`/`Password`, `Use SSL`, `Folder` (IMAP, `INBOX`), `Output directory`, `Filename pattern` (`Mail` + timestamp), `Retrieve all emails` / `Retrieve newer than` / `Retrieve latest N`, `Delete emails from the server`, `Filter` by `Subject`/`From`/`To`/`Date` (`Filter Type`, `Filter Value`) (unverified subset) | Open Studio. Writes `.eml`-like files; parse with tFileInputMail |
| tFileInputMail | Parse an email file's headers/parts into columns | `File Name`, `Mail Parts` table (`Column`, `Mail part` e.g. `From`, `To`, `Subject`, `Body`, `Date`, custom header), `Attachment export directory`, `Extract attachments` | Pair: tPOP (Iterate on files) -> tFileInputMail |

## Business Intelligence

Palette `Business Intelligence` (7.x: `Business Intelligence > Jasper | Palo | SPSS`). Mostly legacy.

| Component | Purpose | Key settings / auth | Notes (license, version, TCK vs javajet) |
| --- | --- | --- | --- |
| tJasperOutput | Fill a JasperReports `.jrxml`/`.jasper` with the input flow as datasource and export | `Jasper file` (`.jrxml` compiled at run or `.jasper`), `Output file`, `Report format` PDF / HTML / XLS / RTF / CSV / XML / TXT (unverified set), `Parameters` table (report params), `Encoding`, `iReport path`/`Edit with iReport` button (opens iReport/Jaspersoft Studio if configured in Preferences) | javajet; Open Studio; bundles JasperReports library (version pinned per Studio, old 6.x in 8.0 (unverified)). For JasperReports Server interaction use the jasper-deploy skill / REST via tHTTPClient |
| tJasperOutputExec | tJasperOutput without input flow (report has its own SQL datasource) | `Jasper file`, `Output file`, `Report format`, `Database connection` (reuse a `t<DB>Connection`) (unverified), `Parameters` | Standalone trigger component |
| tBIRTOutput (unverified) | Eclipse BIRT report run | | Not in 7.x/8.0 palettes; ignore |
| tPaloConnection / tPaloInput / tPaloOutput / tPaloOutputMulti / tPaloCube / tPaloCubeList / tPaloDimension / tPaloDimensionList / tPaloDatabase / tPaloDatabaseList / tPaloRule / tPaloRuleList / tPaloCheckElements / tPaloClose | Jedox Palo OLAP cubes/dimensions | `Host`, `Port` 7777, `Username`/`Password`; `Database`, `Cube`, `Dimension`, `Element` mapping, `Splash mode` for consolidated cells | Deprecated 7.x, removed from 8.0 palette (unverified); use Jedox REST via tHTTPClient |
| tSPSSInput / tSPSSOutput / tSPSSProperties / tSPSSStructure | Read/write IBM SPSS `.sav` files | `File name`, `Properties` (variable labels), `Structure` | Deprecated 7.x (requires SPSS I/O module), removed 8.0 (unverified); use Python/pyreadstat via tSystem or convert to CSV |
| tSalesforceEinstein* | CRM Analytics | see Salesforce | |
| tTableauOutput / tMicroStrategy* / tPowerBI* | Not present | Export CSV/Hyper via tFileOutput* or tHTTPClient to Tableau REST/Power BI push datasets | No native BI vendor components beyond Jasper/Palo/SPSS |
| tGoogleAnalyticsInput (deprecated) | GA Universal Analytics v3 | see Cloud: Google | |

## Talend Cloud and Data Fabric integration components

| Component | Purpose | Key settings / auth | Notes (license, version, TCK vs javajet) |
| --- | --- | --- | --- |
| tDataprepRun | Apply a Talend Data Preparation recipe (preparation) to the flow | `URL` (Data Prep server or Talend Cloud region URL `https://tdp.<region>.cloud.talend.com`), `Username`/`Password` or `Personal access token` (Cloud), `Preparation` (`Fetch preparations`/ path or ID), `Version` (Current state / specific version), `Deployment` Cloud (runs on the same engine as the Job) / On-Premises (runs on the Data Prep server), `Dynamic schema`? (unverified), `Action on error` Fail / Skip (unverified) | TCK-ish; not shipped by default -> Feature Manager (`Data Preparation` feature). See data-quality-governance.md for preparations themselves |
| tDatasetInput | Read a Data Preparation / Data Inventory dataset by ID | `URL`, credentials/PAT, `Dataset ID` (from the dataset URL in Talend Cloud), `Fetch datasets` | Not shipped by default; Feature Manager |
| tDatasetOutput | Publish the flow as a new/updated dataset in Talend Cloud Data Preparation / Inventory | `Dataset name`, `Action` Create / Update (`Dataset ID`), `Limit` rows (unverified) | Same feature package |
| tDataStewardshipTaskInput / tDataStewardshipTaskOutput / tDataStewardshipTaskDelete | Read / create / delete Data Stewardship campaign tasks | `URL` (`https://tds.<region>.cloud.talend.com/data-stewardship` or on-prem), `Username`/`Password` or PAT, `Campaign` (`Fetch` button loads campaigns and their schema), `Task type` Resolution / Merging / Arbitration / Grouping; Input: `Task state` filter (New / Ready to resolve / Resolved...), `Assignee`, `Query` (Lucene), `Batch size`; Output: `Priority`, `Assignee`, `Tags`, `Source` columns, for Merging tasks `Golden record`/`Source records` mapping via `Mapping` of `TDS_*` columns | TCK-ish; subscription (Data Fabric / DQ); details in data-quality-governance.md |
| tMDM* (tMDMConnection, tMDMInput, tMDMOutput, tMDMDelete, tMDMRouteRecord, tMDMTriggerInput/Output, tMDMBulkLoad, tMDMViewSearch, tMDMSP, tMDMCommit/Rollback/Close, tMDMReceive, tMDMRestInput) | Talend MDM server | `URL` (`http://host:8180/talendmdm/services/soap`), `Username`/`Password`, `Data Model`, `Data Container`, `Entity`, `XPath`/`Query`, `Operation` Update / Insert / Partial update | Subscription (MDM Platform, EOL path); data-quality-governance.md |
| tDQRules*, tMatchGroup, tRecordMatching, tStandardize*, tAddressRow* | Data Quality | data-quality-governance.md | |
| tESB*, tRESTRequest/Response, tRouteInput/Output, c* | ESB / Routes | esb-routes-services.md | |
| API Tester / API Designer | Cloud apps, no components | esb-routes-services.md | |

## Data Mapper (tHMap)

Talend Data Mapper (TDM, "Hierarchical Mapper") is a subscription feature (Data Fabric / DI
Platform) installed via Feature Manager (`Data Mapper`, plus `Data Mapper for Spark` for the Spark
I/O components). Structures (`Repository > Metadata > Hierarchical Mapper > Structures`) model
COBOL copybooks, EDI (X12, EDIFACT, HL7, SWIFT MT/MX), flat/positional, XML/XSD, JSON, Avro;
Maps transform one structure into another with TDM functions (`Loop`, `Filter`, `Concat`,
`LookUp`, `AgConcat`, `IOFunction`...). The map editor opens from the component (`...` next to
`Map Path`/`Select an existing map` or `Generate hierarchical mapper structure based on the schema`).

| Component | Purpose | Key settings / auth | Notes (license, version, TCK vs javajet) |
| --- | --- | --- | --- |
| tHMap | Execute a TDM map inside a Standard Job flow (one or many inputs/outputs) | `Map Path` (`Select an existing map`) or `Generate hierarchical mapper structure based on the schema` for the connected flows, `Input/Output representation` (XML / JSON / CSV / Flat / Avro...), `Open Map Editor`, `Exception threshold`/`Error handling`, `Use Document type` input columns, `Rows`/`Record` mode (unverified) | Multiple inputs require TDM I/O functions in the map; in-memory per record |
| tHMapFile | Run a map over a whole file (streaming) in a Standard Job | `Map Path`, `Input file`/`Output file`, `Input/Output representation`, `Streaming` / `Record boundary` (unverified) | Standard; good for large EDI/COBOL files |
| tHMapRecord | Run a map over records in a Spark Streaming/Batch flow (record by record) | `Map Path`, record representation | Spark (big-data-spark.md) |
| tHMapInput | Spark Batch/Streaming input: read a file through a TDM structure as the start of the flow | `Storage` (HDFS/S3/ADLS configuration component), `Input file`, `Structure`/`Map`, `Open Map Editor` | "not shipped with Talend Studio by default" -> Feature Manager `Data Mapper > Talend Data Mapper for Spark` |
| tHMapOutput | Spark Batch/Streaming output through a structure | `Output file`, `Representation`, `Map Path` | Spark |
| tHConvertFile | Convert a file between representations using one structure (e.g. COBOL -> XML) without a map | `Structure`, `Input representation`, `Output representation`, files, `Streaming` | Standard, subscription |
| Structures import | `Import > COBOL copybook`, `XSD`, `EDI standard library` (X12/EDIFACT bundled), `Sample document` (CSV/JSON inference) | | Keep structures in the shared repository project for reuse |

## Technical and misc connectors

| Component | Purpose | Key settings / auth | Notes (license, version, TCK vs javajet) |
| --- | --- | --- | --- |
| tLibraryLoad | Add a jar to the Job classpath at design/compile time | `Library` (pick from Studio module list or `Browse` local jar; stored in `Modules` and in `pom.xml` as `talend-custom-libs` dep), `Import` statements (`import com.foo.*;`) for tJava*, Advanced `Lib Paths` (runtime path) | Custom Code family; Open Studio. Jar is copied into the exported Job `lib/`; CI builds must have it in Nexus `talend-custom-libs-release` |
| tSetKeystore | Set JVM truststore/keystore | `Set TrustStore` (`TrustStore type` JKS/PKCS12, `TrustStore file`, `TrustStore password`), `Need Client authentication` (`KeyStore type/file/password`), `Check server identity` (unverified), `Set KeyStore only`/`Both` (8.0 options; some gated on R-updates) | Sets `javax.net.ssl.trustStore*` system properties for the whole JVM for the rest of the run; not supported in ESB. Put first via OnSubjobOk; alternatively import the CA into the JRE `cacerts` of Studio/JobServer/Remote Engine |
| tSetProxy | see Proxy handling | | |
| tSystem | Run OS command | orchestration-logging.md | |
| tSSH | see Internet | | |
| tRunJob | Call a child Job | orchestration-logging.md | |
| tChronometerStart / tChronometerStop | Timing | orchestration-logging.md | |
| tServerAlive | TCP ping host:port | `Host`, `Port`, `Timeout`, `Iterate` ok/ko flows | orchestration-logging.md |
| tMsgBox / tSleep / tWaitForFile / tWaitForSqlData / tWaitForSocket | Orchestration | orchestration-logging.md | |
| tSCPTruncate / tFTPTruncate | Empty remote files (used for lock files) | | |
| tJavaRow / tJava / tJavaFlex | Escape hatch for any REST/SDK call with tLibraryLoad | components-core.md / tmap-expressions.md | |

## Pipeline Designer connectors

Talend Cloud Pipeline Designer (and its successor flows in Qlik Talend Cloud) uses the TCK
connector catalog directly, not Studio components: a **connection** (datastore) + a **dataset**
created in Talend Cloud Data Inventory, run by a Cloud Engine for Design or a Remote Engine Gen2.
Names differ from Studio (`Amazon S3`, `Azure Data Lake Storage Gen2`, `Google BigQuery`,
`Snowflake`, `Salesforce`, `Marketo`, `NetSuite`, `Workday`, `Zendesk`, `Box`, `HTTP Client`,
`REST`, `Kafka`, `Pub/Sub`, `Kinesis`, `Azure Event Hubs`, `MongoDB`, `Couchbase`, `Elasticsearch`,
`JDBC`, `Database` dialects, `Test connection`, `Local connection`). Capabilities differ: e.g.
Pipeline Designer S3 reads Parquet/Avro natively and streams, Studio tS3* only moves files; Pipeline
Kafka needs no "stop after" condition because pipelines run as streams. A Studio Job cannot embed a
pipeline; integrate via Talend Cloud API (apis-sdks.md) or shared datasets (tDatasetInput). See
deployment-runtime.md for Remote Engine Gen2 and data-quality-governance.md for Data Inventory.

## Component availability by license

Edition column reflects 7.x/8.0 Studio palettes; Open Studio for Data Integration (free, discontinued
for new downloads in Jan 2024 and unsupported) vs subscription Data Integration / Big Data /
Data Fabric. "Cloud-only" = exists as a Pipeline Designer/Qlik Talend Cloud connector, not in Studio.

| Family | Open Studio (DI) | Subscription DI / Platform | Big Data / Data Fabric | Notes |
| --- | --- | --- | --- | --- |
| Amazon S3, Redshift, Aurora, RDS MySQL/Oracle, DynamoDB (Standard), SQS | yes | yes | yes | EMR manage, Kinesis, Spark DynamoDB: Big Data only |
| Azure Storage Blob/Queue/Table, Cosmos DB (Mongo API) | yes | yes | yes | ADLS Gen2, Synapse, Event Hubs: subscription (unverified for ADLS) |
| Google BigQuery, Cloud Storage, Drive | yes | yes | yes | Pub/Sub, Dataproc, Bigtable: Big Data |
| Snowflake | basic Connection/Input/Output/Row/Close (unverified) | yes incl. bulk | yes | |
| Databricks DBFS / Delta Lake JDBC | no | Delta Lake JDBC yes (unverified) | yes | Spark-on-Databricks: Big Data |
| Salesforce | yes (Connection/Input/Output/Bulk, GetDeleted/Updated/Timestamp) | yes | yes | Einstein/Wave: subscription |
| Marketo, NetSuite, Workday, ServiceNow, Zendesk, Box, Jira, Splunk | no (Marketo/NetSuite were in OS 6.x (unverified)) | yes | yes | Mostly TCK, Feature Manager updates |
| Microsoft Dynamics CRM/365 | yes (7.x OS palette) (unverified) | yes | yes | |
| SugarCRM, vtiger, Openbravo, Centric (legacy) | yes | yes | yes | deprecated |
| SAP (all) | no | yes (DI Platform / Data Fabric; SAP add-on licensing historically) | yes | RFC Server + JCo from SAP |
| MongoDB, Cassandra, Neo4j, CouchDB, Redis (Standard) | yes | yes | yes | Couchbase, MarkLogic, Elasticsearch Standard: subscription / Big Data (MarkLogic doc: "products with Big Data and Data Fabric") |
| HBase, Hive, HDFS, HCatalog, Sqoop, Impala, Spark, MapReduce | no | no | yes | big-data-spark.md |
| Kafka (Standard), JMS, MOM, MQTT (Route) | Kafka Standard yes (unverified), JMS/MOM yes | yes | yes | Kafka Spark Streaming: Big Data |
| FTP/SFTP/FTPS, SCP, SSH, HTTP, tRESTClient, tSOAP, tWebService, Mail, Socket, LDAP, XML, Proxy, Keystore | yes | yes | yes | tHTTPClient (TCK, 8.0) subscription (unverified) |
| Jasper, Palo, SPSS | yes (7.x) | yes (7.x) | yes (7.x) | removed/deprecated 8.0 (Palo, SPSS) |
| tDataprepRun, tDataset*, tDataStewardship*, tMDM*, DQ components | no | Data Prep/Stewardship: Cloud or Data Fabric; MDM: MDM Platform | Data Fabric | data-quality-governance.md |
| tHMap / Data Mapper | no | DI Platform / Data Fabric (feature "Data Mapper") | yes | |
| ESB c* Routes, tESB*, tREST* services | no (Open Studio for ESB separate, discontinued) | ESB / Data Services Platform | Data Fabric | esb-routes-services.md |
| Pipeline Designer connectors (SharePoint? no), Qlik Talend Cloud SaaS connectors (Hubspot, Shopify, Stripe, Google Sheets, Microsoft Dynamics 365 CRM, Workday Reports...) | n/a | n/a | n/a | Cloud-only; not Studio components |

## Deprecated and removed connectors

Studio shows deprecated components under a `(deprecated)` suffix in the palette only when
`Window > Preferences > Talend > Palette Settings > Show deprecated components` (unverified
label) is enabled; existing Jobs keep working. Removed = not on the 8.0 palette and the Job
import marks them unknown. Release notes: "Data Integration deprecated and removed items" and
"R20YY-MM Studio deprecated and removed items" pages on help.qlik.com.

| Connector / family | Status | Replacement |
| --- | --- | --- |
| tREST | deprecated (6.x), still shipped 8.0 | tRESTClient, tHTTPClient (8.0 recommended) |
| tWebServiceInput | deprecated | tWebService, tSOAP + tXMLMap |
| tHttpRequest | superseded (not formally deprecated, unverified) | tHTTPClient |
| tFileFetch | kept | tHTTPClient `Download file` for API cases |
| tNetsuiteConnection/Input/Output (lower-case s, API 2014.2/2016.2) | deprecated 7.1, pages titled `(deprecated)` in 8.0 | tNetSuiteConnection/Input/Output (`Version = Netsuite SOAP`, 2019/2021/2025) |
| tNetSuiteV2019* | renamed | folded into tNetSuite* from 8.0.1-R2023-02 |
| tMarketo* SOAP mode | removed | REST mode |
| tSAPIDocInput | deprecated (7.2 doc) | tSAPIDocReceiver (listener) / tSAPIDocOutput |
| tSAPBWInput, tSAPInfoCubeInput (classic) | legacy | tSAPODPInput, tSAPADSOInput |
| tAzureSqlDWH* | renamed | tAzureSynapse* |
| tGoogleAnalyticsInput (UA v3) | deprecated/removed with UA EOL 2023 | tHTTPClient against GA4 Data API |
| tPalo* (Jedox) | deprecated 7.x, removed 8.0 (unverified) | tHTTPClient (Jedox REST) |
| tSPSS* | deprecated 7.x, removed 8.0 (unverified) | CSV export / tSystem + Python |
| tAlfresco* (tAlfrescoOutput) | removed 7.x | CMIS via tHTTPClient / Route cCMIS (removed too) |
| tOpenbravoERP*, tCentricCRM*, tMSAX*, tMicrosoftMQ* | deprecated / removed 8.0 (unverified) | tHTTPClient / OData |
| tRiak* | removed | none |
| tCassandra* `DB Version = 2.0` (Thrift `API type`) | deprecated | CQL3 versions |
| tNeo4j* 2.x embedded | legacy | Bolt 3.x/4.x |
| tMongoDB* `DB Version` 2.x/3.0 drivers | removed in 8.0 R-updates (unverified) | 4.x driver versions |
| Pig family (tPigLoad, tPigMap, tPigStoreResult...) | removed 8.0 | Spark Batch Jobs (big-data-spark.md) |
| MapReduce Jobs and `tMahout*`, `tGenKey`/`tMatchGroup`/`tStandardizeRow` MapReduce variants | removed 8.0 | Spark Batch |
| tBlockedFuzzyJoin, tFuzzyJoin | removed R2024-05 | tRecordMatching |
| tClassify, tClassifySVM, tPredictCluster | removed 8.0 | tPredict |
| tMatchIndex, tMatchIndexPredict | removed R2025-07 | tMatchGroup / tRecordMatching |
| tNLPPreprocessing, tNLPModel, tNLPPredict, tCompareColumns (Spark) | removed 8.0 | none |
| Bonita BPM integration (project-level) | removed 8.0; tBonitaDeploy / tBonitaInstantiateProcess components unaffected (Feature Manager) | |
| Talend ESB Open Studio, Open Studio for DI/BD | discontinued Jan 2024 | subscription Studio 8 / Qlik Talend Cloud |
| tHDFS*/tHive* "Custom" unsupported distributions (CDH 5, HDP 2.x, MapR) | removed per big data release notes | CDP, EMR 6, Dataproc, Databricks |
| tRESTClient `Use Service Registry`/`Use Authorization` (ESB infra) | deprecated with ESB Registry EOL (unverified) | plain auth |

## Gotchas

| Symptom | Cause | Fix |
| --- | --- | --- |
| tSalesforce* fails with `INVALID_SESSION_ID: Session expired or invalid` mid-Job | Session reused across a long Job after Salesforce session timeout, or `Use or save the connection session` reused a stale token file; also happens when the API version in `Salesforce URL` and `API version` disagree | Open the connection per subjob (tSalesforceConnection + tSalesforceClose), raise the org session timeout, delete the saved session file, align URL `/services/Soap/u/<ver>` with `API version` |
| tSalesforceInput Bulk/BulkV2 returns `Bad Request` or `Number of records should be less than or equal to 10001` while `Query` works | Connection not configured for bulk, Bulk unsupported for relationship subqueries / compound fields, or CSV result batch exceeds parser limit | Use `Query` mode for relationship queries, or BulkV2 with a flat SOQL; pair a bulk-enabled connection with Bulk mode; split by date ranges (no PK chunking support) |
| Salesforce `REQUEST_LIMIT_EXCEEDED` / `TotalRequests Limit exceeded` | Per-row SOAP calls (Extend Insert off) or many small batches hit the 24h API call quota | Enable `Extend Insert` (200 rows per call), use Bulk API for >50k rows, check `Company Information > API Requests` |
| Salesforce datetime fields shift by hours | Salesforce returns UTC ISO datetimes; Studio converts to the JVM timezone (`Convert date to local`/`Use Date Pattern` settings) and tSalesforceOutput sends local time without zone | Run Jobs with `-Duser.timezone=UTC`, or keep datetimes as String with pattern `yyyy-MM-dd'T'HH:mm:ss.SSS'Z'` |
| tSalesforceOutput never exposes `Retrieve Insert Id` / no `salesforce_id` column | Option is only available when `Extend Insert` is unchecked (8.0 doc wording "Extended Output" in older versions) | Uncheck `Extend Insert` (accept per-row calls) or use tSalesforceBulkExec whose Main output already has `salesforce_id` |
| tSnowflakeOutputBulkExec: `Access Denied (Status Code: 403)` or `Failure using stage area` on S3 storage | Stage keys lack `s3:PutObject`/`GetObject`/`ListBucket` on the bucket+prefix, or bucket region differs from the `Region` field; KMS-encrypted bucket without `kms:Decrypt` | Grant the policy, set `Region` to the bucket's region, or switch `Storage = Internal` (no cloud credentials, Snowflake-managed stage) |
| Snowflake load silently loads 0 rows / `COPY` reports `LOAD_SKIPPED` | File already loaded once (COPY dedup by file name/MD5 within 64 days) when `Delete Storage Files On Success` is off or `Stage Folder` reused | Add `FORCE=TRUE` in `Copy Command Options` or purge/unique-name staged files |
| Snowflake key-pair auth: `JWT token is invalid` / `Private key provided is invalid or not supported` | Key not PKCS8 (`BEGIN RSA PRIVATE KEY` instead of `BEGIN PRIVATE KEY`), encrypted key with empty passphrase, or public key not set on the user, or account identifier mismatch (locator vs `org-account`) | `openssl pkcs8 -topk8 -inform PEM -nocrypt`, `ALTER USER x SET RSA_PUBLIC_KEY='MII...'`, use full account identifier, sync server clocks |
| tS3Put/tS3Get `The authorization header is malformed; the region 'us-east-1' is wrong; expecting 'eu-west-1'` or `SignatureDoesNotMatch` | `Region` left default; S3-compatible endpoint needs path-style; clock skew > 15 min | Set `Region` to the bucket region; for MinIO/Ceph enable `Use path-style access` and custom `Endpoint`; NTP sync the host |
| tS3Connection `Inherit credentials from AWS role` works on EC2 but fails in Studio (`Unable to load credentials from service endpoint`) | Instance metadata exists only on AWS compute | Use `Profile`/static keys locally via `context`, role in production; or `Assume Role` with a regional STS endpoint from inside the VPC |
| tRedshiftBulkExec: `S3ServiceException: Access Denied` or `The specified S3 prefix does not exist` though tRedshiftOutputBulk uploaded fine | COPY runs with the cluster's credentials (IAM role / keys passed in COPY), not the component's upload keys; cross-region bucket without `REGION` | Attach an IAM role to the cluster and reference it, or pass the same keys; set `Region` on the bulk component; check `stl_load_errors` for row-level errors |
| tAzureStorage* `AuthenticationFailed: Server failed to authenticate the request... Signature not valid in the specified time frame` | SAS token expired or start time in the future (clock skew), or SAS scoped to a different service (blob vs file) / `sr=` resource type | Regenerate SAS with `st` a few minutes in the past, matching service (`ss=b`), permissions `rwdlac`; or switch to Azure AD/managed identity |
| tAzureAdlsGen2* `AuthorizationPermissionMismatch` with a valid service principal | SP has only RBAC Reader or no ACLs on the filesystem path (ADLS Gen2 needs `Storage Blob Data Contributor` or POSIX ACLs on each folder level) | Assign `Storage Blob Data Contributor` on the account/container or set ACLs (`--x` on parents, `rwx` on target) |
| tBigQueryInput `Not found: Dataset project:dataset was not found in location US` | `Location`/`Dataset location` not set to the dataset's region (EU, europe-west2...) | Set the location field to match; BigQuery jobs are region-scoped |
| tBigQueryOutput `Access Denied: ... storage.objects.create` or `Not found: URI gs://bucket/dir/file.csv` | Service account lacks Storage Object Admin on the staging bucket; file path placed in a subfolder while the component expects it directly under the bucket root (7.2 doc) | Grant bucket IAM, write to `gs://bucket/file.csv`, also grant `bigquery.jobs.create` + `bigquery.dataEditor` on the dataset |
| Google components: `invalid_grant` / `unauthorized_client` for a service account on Drive / GA | Domain-wide delegation not configured or wrong OAuth scopes; Drive files not shared with the service account email | Share the folder with the SA email or enable domain-wide delegation with the exact scopes; use Shared Drives |
| Google API `403 Quota exceeded for quota metric 'Queries' and limit 'Queries per day'` | Project-level API quota (Drive 1,000 requests/100 s/user, BigQuery 1,500 table ops/day) hit by row-by-row components | Batch via bulk components, add `tSleep`, request quota increase, avoid per-row `tGoogleDriveList` |
| tKafkaInput re-reads all messages or skips messages after a Job restart | Offsets auto-committed before processing (at-most-once) or never committed (`Auto-commit` off without tKafkaCommit); `Reset offsets on consumer group` left checked from testing | Use `Auto-commit offsets` off + tKafkaCommit after the subjob (at-least-once), make processing idempotent, uncheck reset in production; new groups honour `New consumer group starts from` only when no committed offset exists |
| tKafkaInput Job never ends | Consumer loops forever by design | Set `Stop after a maximum number of messages` / `maximum total duration` / `time without receiving a message`, or run as a long-lived service on a Remote Engine |
| Kafka SASL_SSL: `Failed to construct kafka consumer... Could not find a 'KafkaClient' entry in the JAAS configuration` | JAAS file not passed to the JVM or `sasl.jaas.config` missing from the properties table | Add `sasl.jaas.config=org.apache.kafka.common.security.plain.PlainLoginModule required username="k" password="s";` in `Consumer/Producer properties` (quotes escaped in Java mode) or `-Djava.security.auth.login.config` |
| tJMSInput `javax.naming.NoInitialContextException` / `ClassNotFoundException: org.apache.activemq.jndi.ActiveMQInitialContextFactory` | Provider client jar missing from the Job classpath (Studio only downloads some ActiveMQ versions) or version mismatch with the broker | Add the exact client jar (activemq-client x.y, `com.ibm.mq.allclient` + `javax.jms-api`, artemis-jms-client) with tLibraryLoad / Modules; make sure the build server Nexus has it |
| tMomInput against IBM MQ: `MQJE001: Completion Code '2', Reason '2035'` (NOT_AUTHORIZED) or `2059` (QMGR_NOT_AVAILABLE) | Channel auth (CHLAUTH) blocking the OS user, wrong `Channel` (default `DC.SVRCONN`), wrong port/queue manager | Set the MCAUSER/CHLAUTH rule, correct `QueueManager`/`Channel`/`Port` 1414, confirm `MQSERVER` connectivity with `amqsputc` |
| tFTPGet/tFTPFileList hang or `Connection timed out` after login | Active mode behind NAT/firewall; data channel blocked; FTPS data-channel session resumption on Java 17 | Set `Connection Mode = Passive`; for FTPS on Java 17 force `TLSv1.2` + the JVM props from the 8.0 tFTPConnection doc; open the passive port range on the server |
| tFTPGet downloads files with mangled accents in names / `File not found` for non-ASCII names | FTP control-channel `Encoding` default ISO-8859-1 vs server UTF-8 | Set `Encoding = UTF-8` on tFTPConnection; for SFTP set `-Dfile.encoding` / `Use Perl5 Regex` masks carefully |
| SFTP `Auth fail` with a key that works in OpenSSH | OpenSSH new-format or ed25519 key unsupported by the bundled JSch, or passphrase-protected key with `Password` method | Convert `ssh-keygen -p -m PEM -f id_rsa`, use RSA 2048/4096, choose `Public key` method with `Key Passphrase`; upgrade Studio (newer JSch fork in 8.0 R-updates) |
| tRESTClient `body` output is a String when the Job expects a Document (tXMLMap input error `Document expected`) or vice versa | `Accept Type = ANY` always yields String; Document only when `Convert Response To DOM Document` (Advanced) is checked and the response is XML; JSON is converted to XML only with the JSON-to-XML option | Set `Accept Type` to XML/JSON, tick `Convert Response To DOM Document` for tXMLMap, otherwise parse `string` with tExtractJSONFields |
| tRESTClient / tHTTPClient `401` right after a long run though the first calls worked | OAuth2 access token expired (typically 1h); tRESTClient Bearer token is static | Use tHTTPClient OAuth 2.0 client credentials (auto-refresh) or refresh in a tJavaRow / tRESTClient token call stored in `globalMap` and re-fetched every N minutes |
| tHTTPClient `Die on error` stops the Job on 404 that is expected (lookup miss) | Default dies on >= 400 | Uncheck `Die on error` and branch on the `status`/`responseCode` column |
| SAP components: `java.lang.ExceptionInInitializerError: JCo initialization failed with java.lang.UnsatisfiedLinkError: no sapjco3 in java.library.path` | Only `sapjco3.jar` installed; native `libsapjco3.so`/`sapjco3.dll` missing or wrong arch/glibc, or the jar was renamed (JCo refuses renamed jars) | Put the native lib next to the jar on `java.library.path` (Studio: `-Djava.library.path=` in `.ini`; JobServer/Remote Engine: `LD_LIBRARY_PATH`/`PATH`), keep the file name `sapjco3.jar`, use JCo 3.1.x matching the JDK |
| tSAPTableInput truncates rows / `DATA_BUFFER_EXCEEDED` | Classic `RFC_READ_TABLE` 512-byte row limit when the Talend ABAP transport / RFC Server is not used | Install the Talend SAP transport and use the RFC Server streaming mode, or select fewer fields |
| tMicrosoftCrm* ONLINE `AADSTS7000218: The request body must contain the following parameter: 'client_assertion' or 'client_secret'` | App registered as Web App (confidential) but `Registered application type = Native App` (no secret) or secret empty | Choose `Web App with delegated permissions` + `Client Secret`, or set the app as public client in Azure AD; grant `Dynamics CRM user_impersonation` and admin consent |
| tMarketo* `606 Max rate limit '100' exceeded with in '20' secs` / `607 Daily quota reached` | REST limits per instance; parallel subjobs or tiny batches | Set `Batch Size` 300, serialize Marketo subjobs, enable `Max reconnection attempts` + `Attempt interval time`, use tMarketoBulkExec for loads |
| tNetSuite* `WS_REQUEST_BLOCKED: Only one request may be made against a session at a time` / `EXCEEDED_CONCURRENCY_LIMIT` | SuiteTalk concurrency governance (1 per account by default; SuiteCloud Plus adds 10 per license) hit by parallel tRunJob/tParallelize | Serialize NetSuite subjobs, share one tNetSuiteConnection, buy SuiteCloud Plus, lower `Page size` churn |
| tNetSuiteInput custom fields come back null / not in schema | `Use custom fields` not enabled or schema guessed before custom fields were added; `Body fields only` hides sublists | Tick the custom-field option, re-`Guess schema`, uncheck `Body fields only` when sublists are needed |
| tMongoDBOutput Upsert creates duplicates instead of updating | Key column not flagged in `Query`/keys and not present in `Mapping`, or `_id` typed as String while stored as ObjectId | Mark the key column, keep `_id` consistent (String column named `_id` converts to ObjectId only when valid 24-hex), use `Upsert with set` with `Updatable` columns |
| tMongoDBConnection to Atlas: `Timed out after 30000 ms while waiting to connect` / `MongoSocketReadException` | `mongodb+srv` seedlist unsupported in old driver versions; TLS required; IP not allow-listed | Choose a 4.x driver `DB Version`, `Use SSL`, list replica hosts explicitly or use the connection-string option; allow-list the engine IP |
| tNeo4jOutput `NoSuchMethodError` / `ClassCastException` in a Job that also has tNeo4jInput | Mixed `DB Version` 2.x and 3.x in the same Job (doc warning), or 3.2.x server (unsupported) | Use one driver version per Job; split into child Jobs if needed |
| tCassandraOutput `InvalidQueryException: Batch too large` / timeouts | Logged batch with many partitions exceeding `batch_size_fail_threshold_in_kb` | Lower `Batch size`, use `unlogged batch`, insert without batch for cross-partition data |
| tElasticSearchOutput `mapper_parsing_exception` / `Rejecting mapping update ... as the final mapping would have more than 1 type` | `Type` set on ES 7+/8 which dropped mapping types; dates sent as Strings not matching the index format | Leave type `_doc` / blank, set explicit mappings or send ISO-8601 Strings |
| tCouchbase* ignore tSetProxy and fail from a proxied network | Couchbase SDK has no proxy support (doc note) | Open direct network access (8091-8096, 11210, 18091+ with TLS) or run on an engine inside the VPC |
| tLDAPInput returns only 1000 entries from Active Directory | AD `MaxPageSize` 1000 without paging | Enable paging (`Page size` <= 1000) on tLDAPInput (7.x+) or filter/segment by OU |
| tLDAPOutput to AD `LDAP: error code 53 - 0000001F: SvcErr: DSID-031A12D2, problem 5003 (WILL_NOT_PERFORM)` on password set | `unicodePwd` requires LDAPS and a UTF-16LE quoted value | Use `Protocol = LDAPS` with trusted cert (tSetKeystore) and set the value via tJavaRow as `"\"" + pwd + "\""` encoded UTF-16LE (byte[] attribute) |
| tSendMail `javax.mail.AuthenticationFailedException` / `535 5.7.3 Authentication unsuccessful` on Office 365, or `Could not convert socket to TLS` on port 587 | Basic SMTP auth disabled by Microsoft; `SSL support` (implicit TLS) used on the STARTTLS port 587 | Use 465 + `SSL support` where offered, or 587 with STARTTLS option; for M365 use Graph `sendMail` via tHTTPClient with OAuth2 or an authenticated relay/SMTP AUTH-enabled mailbox with an app password |
| tSendMail silently sends without attachment | `Die if the attachment file doesn't exist` unchecked | Re-check it, or test with tFileExist upstream |
| Proxy configured in Studio Preferences but Job still cannot reach the Internet | Studio's Eclipse proxy applies to Studio only, not to the Job JVM | Add tSetProxy at Job start or JVM args `-Dhttps.proxyHost/-Dhttps.proxyPort/-Dhttp.nonProxyHosts` in Run > Advanced settings / TAC task / engine `JAVA_OPTS`; for authenticated HTTPS proxies add `-Djdk.http.auth.tunneling.disabledSchemes=` |
| tSetKeystore has no effect for one component (`PKIX path building failed`) | Component uses its own HTTP stack/truststore (e.g. Snowflake JDBC `-Djavax.net.ssl.trustStore` must be set before driver load; Couchbase/Mongo drivers use their own `Use SSL` + truststore params) | Put tSetKeystore in the very first subjob (tPrejob), or import the CA into the JRE `cacerts` of every runtime (Studio JRE, JobServer, Remote Engine) |
| TCK connector shows as red/unknown component after importing a Job or after Studio update | Job built with a newer connector version (car) than installed; feature not activated for this project; missing R-update | `Help > Feature Manager` install/activate the feature in this project, apply the same monthly update as the source Studio, check `Modules` for missing jars |
| "Install missing modules" dialog keeps returning at every Job open | Jars Studio cannot download (sapjco3, IBM MQ, Oracle ojdbc in some builds, Teradata, Neo4j 3.x bundles) | Install manually once via the dialog's browse button; for CI put them in Nexus `talend-custom-libs-release`/`talend-custom-libs-snapshot`; set `Window > Preferences > Talend > Performance > Check the modules` (unverified) |
| Pure-password field shows `Unknown variable` or literal `context.pwd` sent to the server | Field in "pure password" mode holds a literal, Java mode expects an expression | Toggle the field mode (8.0.1-R2022-05+ eye/mode icon) to match; keep secrets in `context` with Java mode |
| tDeltaLakeInput `Log4j2 conflict` / `java.lang.NoSuchMethodError` from Arrow | Databricks JDBC bundles Arrow + log4j shading clashes with Studio log4j2 | Append `;EnableArrow=0` to the JDBC URL (8.0 doc) |
| tDeltaLake* `No suitable driver found for jdbc:spark://` after 8.0.1-R2023-05 | Driver switched to `com.databricks.client.jdbc.Driver`, URL scheme must be `jdbc:databricks://` | Edit the JDBC URL in every Job/context (doc note: existing Jobs need manual update) |
| tAzureSynapseBulkExec `COPY INTO` fails `Not able to validate external location` | Synapse workspace managed identity lacks `Storage Blob Data Contributor` on the staging account, or firewall blocks Azure services | Grant the role to the workspace MSI, allow trusted Microsoft services, or use SAS auth in the COPY credential |
| tHMap `Exception threshold reached` / map runs but output structure empty | Representation mismatch (CSV structure with wrong delimiter/encoding) or loop not mapped (`Loop` function missing on the output repeating element) | Open the map, run with sample data (`Test Run`), add `Loop` on the output element, check `Input representation` properties |

## Sources

https://help.qlik.com/talend/en-US/components/8.0/salesforce/tsalesforceinput
https://help.qlik.com/talend/en-US/components/8.0/salesforce/tsalesforceoutputbulk
https://help.qlik.com/talend/r/en-US/7.3/components/salesforce/tsalesforceoutput
https://help.qlik.com/talend/en-US/components/7.3/salesforce/tsalesforceoutputbulk-standard-properties
https://community.qlik.com/t5/Talend-Studio/bulk-and-bulkv2-options-not-working-in-tSalesforceInput/m-p/2336169/highlight/true
https://community.qlik.com/t5/Talend-Studio/resolved-tSalesforceInput-PK-or-Autonumber-chunking/td-p/2325100
https://community.qlik.com/t5/Talend-Studio/Bulk-Query-mode-not-working-in-tSalesforce-Input/m-p/2320930/highlight/true
https://community.qlik.com/t5/Talend-Studio/Can-not-retrieve-Salesforce-ID-while-using-tSalesforceOutput/td-p/2321578
https://community.qlik.com/t5/Talend-Studio/Problem-with-tsalesforceoutput-main-reject-flow-when-Commit/m-p/2368857/highlight/true
https://help.qlik.com/talend/en-US/components/8.0/snowflake/tsnowflakeoutputbulk
https://help.qlik.com/talend/en-US/components/8.0/snowflake/tsnowflakeoutputbulkexec
https://help.qlik.com/talend/en-US/components/8.0/snowflake/tsnowflakebulkexec
https://help.qlik.com/talend/en-US/components/7.3/snowflake/tsnowflakeoutputbulk-standard-properties
https://help.qlik.com/talend/en-US/components/7.2/snowflake/tsnowflakeoutputbulkexec-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/amazon-s3/ts3connection
https://help.qlik.com/talend/en-US/components/7.3/amazon-s3/ts3connection-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/amazon-s3/ts3get-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/amazon-s3/ts3put-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/amazon-s3/ts3copy-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/amazon-s3/ts3list
https://help.qlik.com/talend/en-US/components/8.0/amazon-redshift/tredshiftoutputbulk
https://help.qlik.com/talend/en-US/components/8.0/amazon-redshift/tredshiftoutputbulkexec
https://help.qlik.com/talend/en-US/components/8.0/amazon-redshift/tredshiftbulkexec
https://help.qlik.com/talend/en-US/components/7.3/amazon-redshift/amazon-redshift-component
https://help.qlik.com/talend/en-US/components/8.0/google-bigquery/tbigqueryoutput-standard-properties
https://help.qlik.com/talend/en-US/components/7.2/google-bigquery/tbigqueryoutput-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/google-bigquery/tbigquerybulkexec
https://help.qlik.com/talend/en-US/components/7.2/google-bigquery/tbigqueryinput-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/google-bigquery/tbigquerysqlrow
https://help.qlik.com/talend/en-US/components/8.0/google-bigtable/tbigtableoutput
https://help.qlik.com/talend/en-US/components/8.0/azure-storage-blob/tazurestorageconnection
https://help.qlik.com/talend/en-US/components/8.0/azure-storage-queue/tazurestorageconnection
https://help.qlik.com/talend/en-US/components/8.0/azure-storage-table/tazurestorageconnection
https://help.qlik.com/talend/en-US/components/7.3/azure-storage-blob/tazurestorageconnection-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/azure-storage-table/tazurestorageinputtable-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/azure-storage-blob/tazurestoragecontainerlist
https://help.qlik.com/talend/en-US/components/8.0/azure-data-lake-storage-gen2/tazureadlsgen2connection
https://help.qlik.com/talend/en-US/components/8.0/azure-data-lake-storage-gen2/tazureadlsgen2input
https://help.qlik.com/talend/en-US/components/7.3/azure-data-lake-storage-gen2/tazureadlsgen2output-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/azure-data-lake-storage-gen2/tazureadlsgen2put
https://help.qlik.com/talend/en-US/components/8.0/azure-data-lake-storage-gen2/tazureadlsgen2delete
https://help.qlik.com/talend/en-US/components/8.0/mongodb/tmongodboutput-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/mongodb/tmongodboutput-standard-properties
https://help.qlik.com/talend/en-US/components/7.2/mongodb/tmongodboutput-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/mongodb/tmongodbinput-tmongodboutput-tlogrow-upserting-data-to-mongodb-standard-component-bigdata
https://help.qlik.com/talend/en-US/components/7.2/cosmosdb/tcosmosdboutput-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/kafka/tkafkainput-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/kafka/tkafkainput-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/mediation-kafka/ckafka
https://help.qlik.com/talend/en-US/components/7.3/kafka/tkafkainputavro-properties-for-apache-spark-streaming
https://help.qlik.com/talend/en-US/job-script-reference-guide/8.0/component-specific-settings-for-tkafkainput
https://help.qlik.com/talend/en-US/components/8.0/esb-rest/trestclient
https://help.qlik.com/talend/en-US/components/7.3/esb-rest/trestclient-standard-properties
https://help.qlik.com/talend/en-US/components/7.2/esb-rest/trestclient-txmlmap-tlogrow-tlogrow-configuring-service-call-standard-component
https://help.qlik.com/talend/en-US/components/8.0/http/thttpclient
https://help.qlik.com/talend/en-US/components/7.3/rest/trest-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/ftp/tftpconnection
https://help.qlik.com/talend/en-US/components/7.3/ftp/tftpconnection-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/ftp/tftpfileproperties
https://help.qlik.com/talend/en-US/components/8.0/ftp/tftpput
https://help.qlik.com/talend/en-US/components/8.0/ftp/tftpget
https://help.qlik.com/talend/en-US/components/8.0/ftp/tftpdelete
https://help.qlik.com/talend/en-US/components/7.3/ftp/tftptruncate-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/sap/sap-component
https://help.qlik.com/talend/en-US/components/8.0/sap/tsaptableinput
https://help.qlik.com/talend/en-US/components/7.3/sap/sap-component
https://help.qlik.com/talend/en-US/components/7.3/sap/tsaptableinput-standard-properties
https://help.qlik.com/talend/en-US/components/7.2/sap/sap-component
https://help.qlik.com/talend/en-US/release-notes/8.0/r2025-07-studio-deprecated-and-removed-items
https://help.qlik.com/talend/en-US/release-notes/8.0/data-integration-deprecated-and-removed-items
https://help.qlik.com/talend/en-US/release-notes/8.0/data-quality-deprecated-and-removed-items
https://help.qlik.com/talend/en-US/release-notes/8.0/r2024-05-deprecated-and-removed-features-data-quality
https://help.qlik.com/talend/en-US/release-notes/8.0/r2023-01-deprecated-and-removed-features-data-quality
https://help.qlik.com/talend/r/en-US/8.0/studio-user-guide/install-features-to-talend-studio
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2025-10/install-features-to-talend-studio
https://jira.talendforge.org/browse/TCOMP-2443
https://help.qlik.com/talend/en-US/components/8.0/netsuite/tnetsuitev2019input
https://help.qlik.com/talend/en-US/components/8.0/netsuite/tnetsuitev2019connection
https://help.qlik.com/talend/en-US/components/7.3/netsuite/tnetsuitev2019input-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/netsuite/tnetsuiteinput-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/netsuite/tnetsuiteinput-deprecated
https://help.qlik.com/talend/en-US/connectors-guide/Cloud/connector-netsuite
https://help.qlik.com/talend/en-US/components/7.3/marketo/marketo
https://help.qlik.com/talend/en-US/components/7.2/marketo/marketo-component
https://help.qlik.com/talend/en-US/components/7.3/marketo/tmarketoinput-tmarketoconnection-tlogrow-connecting-to-marketo-using-rest-api-before
https://help.qlik.com/talend/en-US/components/8.0/marketo/tmarketocampaign
https://help.qlik.com/talend/ja-JP/studio-user-guide/8.0-R2024-05/centralizing-marketo-metadata
https://help.qlik.com/talend/en-US/components/8.0/workday/tworkdayinput
https://help.qlik.com/talend/en-US/components/7.3/workday/tworkdayinput-standard-properties
https://help.qlik.com/en-US/cloud-services/Subsystems/Hub/Content/Sense_Hub/DataIntegration/WebApplications/Connecting-Workday-Reports.htm
https://help.qlik.com/talend/r/en-US/8.0/components/microsoft-crm/tmicrosoftcrmoutput
https://help.qlik.com/talend/en-US/microsoft-crm/8.0/tmicrosoftcrminput
https://help.qlik.com/talend/en-US/components/7.3/microsoft-crm/tmicrosoftcrmoutput-standard-properties
https://help.qlik.com/talend/en-US/components/7.2/microsoft-crm/tmicrosoftcrminput-standard-properties
https://community.qlik.com/t5/Talend-Studio/What-is-Security-Service-URL-in-tMicrosoftcrmOutput-component/m-p/2281336/highlight/true
https://community.qlik.com/t5/Design-and-Development/Connecting-to-Dynamics-365/m-p/2377798/highlight/true
https://help.qlik.com/en-US/cloud-services/Subsystems/Hub/Content/Sense_Hub/DataIntegration/WebApplications/Connecting-MicrosoftDynamics365-v2.htm
https://help.qlik.com/talend/en-US/components/8.0/mail/tsendmail
https://help.qlik.com/talend/en-US/components/7.3/mail/tsendmail-standard-properties
https://community.qlik.com/t5/Talend-Studio/resolved-Error-on-tSendMail/td-p/2363758
https://community.qlik.com/t5/Talend-Studio/tSendMail-component-issue/td-p/2349552
https://help.qlik.com/talend/en-US/components/8.0/mom/tmomoutput
https://help.qlik.com/talend/en-US/components/8.0/mom/tmominput
https://help.qlik.com/talend/en-US/components/8.0/mom/tmomconnection
https://help.qlik.com/talend/en-US/components/7.3/mom/tmominput-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/mom/tmessagingoutput
https://help.qlik.com/talend/en-US/components/8.0/mom/tmessaginginput
https://help.qlik.com/talend/en-US/components/8.0/mediation-jms/cmqconnectionfactory
https://help.qlik.com/talend/en-US/components/8.0/mediation-wmq/cmqconnectionfactory
https://help.qlik.com/talend/en-US/components/8.0/dbfs/tdbfsput
https://help.qlik.com/talend/en-US/components/8.0/dbfs/tdbfsconnection
https://help.qlik.com/talend/en-US/components/7.3/databricks/tdbfsput-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/databricks/tdbfsget-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/delta-lake/tdeltalakeinput-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/data-mapping/thmap
https://help.qlik.com/talend/en-US/components/8.0/data-mapping/thmapinput
https://help.qlik.com/talend/en-US/components/7.2/data-mapping/thmap-tfileinputdelimited-tfileoutputxml-tfileoutputxml-defining-properties-of-thmap-standard-component-enterprise-select
https://help.qlik.com/talend/en-US/components/8.0/data-preparation/tdatapreprun
https://help.qlik.com/talend/en-US/components/8.0/data-preparation/tdatasetinput
https://help.qlik.com/talend/en-US/components/8.0/data-preparation/tdatasetoutput
https://help.qlik.com/talend/en-US/components/8.0/data-preparation/data-preparation-component
https://help.qlik.com/talend/en-US/data-preparation-user-guide/Cloud/talend-cloud-data-preparation-architecture-beta
https://help.qlik.com/talend/en-US/components/8.0/proxy/tsetproxy
https://help.qlik.com/talend/en-US/components/7.3/proxy/tsetproxy-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/keystore/tsetkeystore-standard-properties
https://help.qlik.com/talend/en-US/components/7.2/keystore/tsetkeystore-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/library-import/tlibraryload-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/ldap/tldapinput
https://help.qlik.com/talend/en-US/components/8.0/ldap/tldapoutput
https://help.qlik.com/talend/en-US/components/8.0/ldap/tldapattributesinput
https://help.qlik.com/talend/en-US/components/8.0/ldap/tldaprenameentry
https://help.qlik.com/talend/en-US/components/7.3/ldap/tldapinput-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/ldap/tldapinput-tldapoutput-tmap-tlogrow-configuring-components-standard-component-in
https://help.qlik.com/talend/en-US/components/8.0/couchbase/tcouchbaseoutput
https://help.qlik.com/talend/en-US/components/8.0/cassandra/tcassandraoutput-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/cassandra/tcassandraoutput-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/neo4j/tneo4joutput-standard-properties
https://help.qlik.com/talend/en-US/components/7.2/marklogic/tmarklogicoutput-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/google-drive/tgoogledriveconnection
https://help.qlik.com/talend/en-US/components/8.0/google-drive/tgoogledriveget
https://help.qlik.com/talend/en-US/components/8.0/google-drive/tgoogledriveput
https://help.qlik.com/talend/en-US/components/7.2/google-drive/tgoogledriveconnection-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/google-drive/tgoogledriveput-standard-properties
