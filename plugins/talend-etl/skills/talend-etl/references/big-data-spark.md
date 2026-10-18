# Talend Big Data: Spark Batch / Streaming, Hadoop ecosystem, cloud Spark platforms

> Verification: doc-derived (help.qlik.com / help.talend.com search snippets, Talend GitHub, Maven Central) plus model knowledge. Not exercised against a live Studio/TAC/TMC in this build. Items marked (unverified) are from memory only and should be checked in Studio before relying on exact labels.

Scope: Talend Open Studio for Big Data (TOSBD, free, discontinued after 8.0 like the
other Open Studios), Talend Big Data Platform / Real-Time Big Data Platform, Talend
Data Fabric, and the Big Data features of Studio 8.0 monthly R-releases (Spark
Universal). Standard-job plumbing (contexts, triggers, build) is in studio.md,
deployment-runtime.md and orchestration-logging.md; this file covers only what is
specific to Hadoop/Spark jobs and components.

## Contents
- [1. Job types and frameworks](#1-job-types-and-frameworks)
- [2. Hadoop Cluster metadata and distributions](#2-hadoop-cluster-metadata-and-distributions)
- [3. Spark Configuration tab (Run view)](#3-spark-configuration-tab-run-view)
- [4. Spark Universal per-mode parameters](#4-spark-universal-per-mode-parameters)
- [5. Storage configuration components](#5-storage-configuration-components)
- [6. Spark Batch component catalog](#6-spark-batch-component-catalog)
- [7. Spark Streaming components](#7-spark-streaming-components)
- [8. Standard-job Hadoop components (HDFS, Hive, Impala, HBase, Sqoop)](#8-standard-job-hadoop-components-hdfs-hive-impala-hbase-sqoop)
- [9. Execution model: driver placement, jars, logs](#9-execution-model-driver-placement-jars-logs)
- [10. Hive, HDFS HA, Kerberos, security specifics](#10-hive-hdfs-ha-kerberos-security-specifics)
- [11. Data formats, schema and types in Spark jobs](#11-data-formats-schema-and-types-in-spark-jobs)
- [12. Development and deployment workflow](#12-development-and-deployment-workflow)
- [13. Version matrix (Spark / Scala / platforms per release)](#13-version-matrix-spark--scala--platforms-per-release)
- [Gotchas](#gotchas)
- [Sources](#sources)

## 1. Job types and frameworks

Repository > Job Designs has three folders in Big Data editions:

| Job type | Framework (dropdown at creation) | Generated runtime | Status |
|---|---|---|---|
| Standard | n/a | Plain Java, row-by-row in one JVM; Hadoop touched only through client components (tHDFS*, tHive*, tSqoop*, tHBase*) | Always available |
| Big Data Batch | MapReduce (5.x-7.x) or Spark | MapReduce: Hadoop MR driver + mappers/reducers. Spark: one Java `main` that builds a `SparkSession`/`JavaSparkContext` and chains RDD/Dataset transformations | MapReduce deprecated 7.3, removed 8.0 (only Spark remains, so the Framework prompt disappears) |
| Big Data Streaming | Storm (6.x-7.x) or Spark Streaming | Spark Streaming: DStream micro-batches sized by "Batch size" | Storm deprecated 7.3 GA, removed 8.0 |

Related removals in 8.0 (Big Data "deprecated and removed items" release note): Pig
components (tPigLoad, tPigMap, tPigStoreResult, tPigFilterRow, tPigAggregate,
tPigSort, tPigJoin, tPigDistinct, tPigCode, tPigCross, tPigCoGroup,
tPigFilterColumns, tPigReplicate), Oozie scheduler view and tOozie* metadata,
tFlumeInput/tFlumeOutput, Storm/MapReduce frameworks, HCatalog components
(unverified for exact release). MapR-DB components (tMapRDBInput/Output/
Connection/Close/Configuration/Lookup) are deprecated with the MapR distribution.
Elasticsearch 2.3.x/5.6.x/6.4.x Spark component support removed through the
8.0 R2023 releases.

Creating / converting:
- Right-click Job Designs > Big Data Batch > "Create Big Data Batch Job" (7.x
  shows Framework: MapReduce | Spark). Same for Big Data Streaming.
- Convert an existing Standard Job: right-click the Job > "Edit Big Data Batch
  properties" (opens the properties dialog where the target framework is chosen;
  label varies, (unverified) in 8.0) or right-click > "Duplicate" and change
  "Job Type" to Big Data Batch / Big Data Streaming and "Framework" to Spark. The
  converter keeps components that exist in the target palette and drops the
  rest; connections, contexts and schemas are preserved. Orchestration
  components (tRunJob, tPrejob/tPostjob, OnSubjobOk) survive; row-level Standard
  components without a Spark twin (tDBInput generic, tFileList, tSystem, tSendMail)
  do not.
- The reverse (Spark -> Standard) is also offered in the Duplicate dialog but
  Spark-only components (tSqlRow, tPartition, tCacheIn/Out, configuration
  components) are dropped.
- Best practice: keep a Standard "orchestrator" job that calls Spark jobs via
  tRunJob (tRunJob is available inside Standard jobs and can launch a Big Data
  Batch job; a Spark job cannot embed another Spark job's RDDs).

Palette differences: a Spark job's palette only shows families/components with a
Spark Batch (or Spark Streaming) implementation. Each component's help has
separate pages "tX properties for Apache Spark Batch" / "... for Apache Spark
Streaming" / "... Standard"; properties differ per page (e.g. tFileOutputDelimited
Spark has "Merge result to single file"; Standard does not).

Design-time differences versus Standard:
- No row-level "Traces Debug"; the Run view shows driver logs and Spark job
  progress. Row counts on links appear when "Statistics" is enabled only where the
  framework supports it (unverified).
- Component "Advanced settings" lose "tStatCatcher Statistics" in many Spark
  components.
- `globalMap` is driver-local: tJava (Spark) runs on the driver, tJavaRow (Spark)
  runs inside executors and cannot publish to globalMap for later subjobs.
- Lookup "Reload at each row" in tMap is not available; see tMap row in section 6.
- OnComponentOk/OnSubjobOk still exist to sequence Spark subjobs; each subjob is a
  separate set of Spark actions run against the same SparkContext.

## 2. Hadoop Cluster metadata and distributions

Repository > Metadata > Hadoop Cluster > "Create Hadoop Cluster". Wizard step 1:
Distribution + Version; step 2 "Import option":

| Import option | Behaviour |
|---|---|
| Enter manually Hadoop services | Type every URI yourself |
| Retrieve configuration from Ambari or Cloudera | Give Cloudera Manager / Ambari URL + credentials, pick the cluster, services are auto-filled |
| Import configuration from local files | Point to a folder with `core-site.xml`, `hdfs-site.xml`, `yarn-site.xml`, `mapred-site.xml` (plus `hive-site.xml`, `hbase-site.xml`); Studio parses them and builds a "Hadoop configuration JAR" that it embeds in jobs |

Connection fields (classic, non-Universal distributions):

| Field | Typical value | Notes |
|---|---|---|
| Distribution / Version | Cloudera CDH 6.3, Hortonworks HDP 3.1, Amazon EMR 6.2, MapR 6.1, Microsoft HDInsight 4.0, Google Dataproc 1.4, Databricks 7.3, Cloudera CDP 7.1, Universal | Drives which jars and which Spark/Hadoop client versions are loaded; "Custom" lets you tick a base distribution and supply jars (6.x/7.x) |
| Use Yarn | checked | Unchecked = MR1/JobTracker (CDH4 era); unused for Spark Universal |
| Namenode URI | `hdfs://nn1:8020` or `hdfs://<nameservice>` for HA; `maprfs:///` for MapR; `wasb(s)://`, `abfss://`, `s3a://` for cloud storage | Default FS for all HDFS components that reuse the metadata |
| Resource Manager | `rm1:8032` | YARN RM address; for RM HA add the `yarn.resourcemanager.ha.*` Hadoop properties |
| Set resourcemanager scheduler address | `rm1:8030` | `yarn.resourcemanager.scheduler.address` |
| Set jobhistory address | `jhs:10020` | `mapreduce.jobhistory.address` |
| Set staging directory | `/user` or `/tmp/hadoop-yarn/staging` | `yarn.app.mapreduce.am.staging-dir`; job jars are uploaded under it |
| Use datanode hostname | checked when the client resolves datanodes by hostname (cloud / NAT / Docker) | `dfs.client.use.datanode.hostname=true` |
| Authentication: Use Kerberos authentication | Namenode principal `nn/_HOST@REALM`, Resource manager principal `rm/_HOST@REALM`, Job history principal `jhs/_HOST@REALM` | `_HOST` is substituted by Hadoop at connect time |
| Use a keytab to authenticate | Principal `svc_talend@REALM`, Keytab `/etc/security/keytabs/talend.keytab` | Without keytab Studio relies on a ticket cache from `kinit` (Linux) or the Windows LSA (MIT krb5 needed) |
| User name | OS-like Hadoop user (when no Kerberos) | Sets `HADOOP_USER_NAME`; used for HDFS permissions |
| Hadoop properties | key/value table | Any `*-site.xml` property (see section 10) |
| Spark properties (Spark-aware metadata) | key/value | Forwarded to `SparkConf` (unverified label placement) |
| Check Services | button | Tests Namenode/RM/JobHistory reachability |

Child metadata under a Hadoop cluster: HDFS, Hive (JDBC URL, HiveServer2 port
10000, Kerberos SPN), HBase (Zookeeper quorum + client port 2181, znode
`/hbase`), HCatalog and Oozie (7.x only), MapRDB (deprecated). Dragging a child
metadata onto the canvas creates the matching Standard component with
"Property Type: Repository".

### Spark Universal (Studio 8.0+)
- Distribution "Universal" in both Hadoop Cluster metadata and the Spark
  Configuration tab. You pick only a Spark version (3.0.x ... 3.5.x; 4.x for
  Databricks in R2026 releases) and a runtime mode; the cluster-specific Hadoop
  client config comes from a "Hadoop configuration JAR" (built by the metadata
  wizard from `*-site.xml`, or referenced by path) or from the platform API
  (Databricks, Dataproc, Synapse, CDE).
- Only Scala 2.12 is supported with Spark Universal (help text).
- Modules (Spark jars per version) are downloaded on demand through the Studio
  "Install external modules" / Feature Manager dialog from the Talend update
  repository; offline installs need the Spark Universal module zips staged in a
  local Nexus/Artifactory (see studio.md for module install).
- Qlik now recommends Spark Universal over built-in distributions for CDP
  7.1.9+, CDP Public Cloud 7.2, EMR 6.x/7.x, Dataproc 2.x, Databricks and
  Synapse; built-in distributions stop at Spark 2.4.

### Dynamic distributions (7.2 - 8.0, deprecated in 8.0 R2025/R2026 pages)
- Project Settings > General > "Dynamic distribution settings" > Add: choose
  Cloudera (CDH 6.x, CDP 7.1.x up to 7.1.8) or Hortonworks (HDP 3.x); Studio
  fetches the component/jar configuration from the vendor Maven repository through
  Talend's dynamic distribution proxy (a Nexus proxy with a shared read-only client
  account documented in help) and generates a distribution entry selectable in
  Hadoop Cluster metadata and the Spark Configuration tab.
- Project Settings > General > "Artifact Proxy Setting" > "Override default setup"
  lets you point to your own Nexus proxy (recommended: caches jars for all Studio
  instances) with its own credentials; "Check Connection" validates.
- Cloudera moved CDH/CDP artifacts behind paywall authentication (2021); the proxy
  (yours or Talend's) must carry Cloudera repository credentials or the retrieval
  stalls at "retrieving configuration files". Qlik now says: use built-in CDP 7.x
  distributions, or Spark Universal for CDP 7.1.9+/7.2.
- Import/export of dynamic distributions: Project Settings dialog has
  Import/Export buttons writing a zip of the generated configuration (unverified
  exact labels).

### Distribution support timeline (approximate, check versions-licensing.md for release dates)

| Studio | Built-in distributions (Spark) | Spark versions |
|---|---|---|
| 5.6 | CDH 4/5.x, HDP 2.x, MapR 3.x/4.x, Pivotal HD, EMR 3.x (Spark via tSparkConnection/tSparkLoad components in Standard jobs) | 1.x |
| 6.0 - 6.2 | CDH 5.4-5.7, HDP 2.2-2.4, MapR 4.1/5.x, EMR 4.x, Custom | 1.3 - 1.6 |
| 6.3 - 6.5 | + CDH 5.8-5.13, HDP 2.5/2.6, MapR 5.2, EMR 5.x, Google Dataproc 1.x, Microsoft HDInsight 3.x, Cloudera Altus, Qubole | 1.6, 2.0, 2.1, 2.2 |
| 7.0 - 7.1 | + CDH 5.14-5.16, HDP 2.6.x, MapR 6.0, EMR 5.11-5.15, Databricks (runtime 3.5/4.x), HDInsight 3.6 | 2.1 - 2.3 |
| 7.2 - 7.3 | + CDH 6.1-6.3, HDP 3.1, MapR 6.1, EMR 5.20-5.29, Databricks 5.5 LTS, Dataproc 1.4, Dynamic distributions (CDH 6.x, HDP 3.x, CDP 7.1 in 7.3 R2020+), EMR 6.x via dynamic (late 7.3) | 2.2 - 2.4 |
| 8.0 (Jan 2022) + R-releases | Built-in: CDP 7.1.x, EMR 5.29/6.2, Databricks 7.3, Dataproc 1.4/2.0, HDInsight 4.0 (all Spark 2.4 or 3.0); Spark Universal: Local, Standalone, Yarn cluster, Kubernetes, Databricks (AWS/Azure/GCP; Serverless added 2025/2026), Dataproc 2.0/2.1, Synapse Spark pools, Cloudera Data Engineering (CDE), Spark-submit scripts | Universal 3.0.x, 3.1.x, 3.2.x, 3.3.x, 3.4.x, 3.5.x; 4.x (Databricks only, R2026) |

Scala: Spark 1.x/2.x jobs compile against Scala 2.10/2.11 jars (Talend code is
Java; Scala version matters only for matching cluster libs), Spark Universal 3.x
is 2.12 only. Java: Spark 2.4 jobs need Java 8 at runtime; Spark 3.3+ runs on
Java 11/17 (Studio 8 R2024+ runs on Java 17 and adds `--add-opens` JVM args to
generated launch scripts).

## 3. Spark Configuration tab (Run view)

Run view > "Spark Configuration" tab (there is no tSparkConfiguration component
since 6.0; the 5.x tSparkConnection/tSparkLoad/tSparkStore Standard components
were replaced by the job-level tab). Settings are per Job; "Property Type:
Repository" lets you bind them to a Hadoop Cluster metadata entry so changes
propagate.

| Setting | Values / meaning | Notes |
|---|---|---|
| Property Type | Built-In / Repository | Repository binds to Metadata > Hadoop Cluster |
| Use local mode | checkbox | Spark `local[*]` inside the Studio/JobServer JVM; no cluster needed; still needs a Hadoop client (winutils on Windows) |
| Distribution / Version | as in section 2, or Universal + Spark version | Universal replaces Distribution with "Spark mode" choices |
| Spark mode (classic) | Local, Standalone, Yarn client, Yarn cluster | Yarn client: driver in Studio JVM, needs "Define the driver hostname or IP address" when the Studio host has several NICs/VPN. Yarn cluster: driver on an AM container; "Wait for the Job to complete" keeps Studio polling |
| Spark mode (Universal) | Local, Standalone, Yarn cluster, Kubernetes, Databricks, Dataproc, Synapse, CDE, Spark-submit scripts | Yarn client is not offered in Universal |
| Spark host / Spark home (Standalone) | `spark://master:7077`, path of the Spark install on the Studio host | Standalone requires cluster Spark version == job Spark version |
| Resource Manager, scheduler address, jobhistory, staging directory, Use datanode hostname | as in metadata | Yarn modes only |
| Hadoop configuration JAR / Use custom Hadoop confs (Universal Yarn, K8s) | jar generated by metadata wizard | Carries `*-site.xml`; without it the job cannot locate RM/Namenode (unverified exact label) |
| Use Kerberos authentication | Namenode/RM/JobHistory principals; "Use a keytab to authenticate" Principal + Keytab | Keytab path is read on the driver host; for Yarn cluster it is shipped with the job |
| User name | Hadoop user | Non-Kerberos clusters |
| Spark "scratch" directory | default `/tmp` | Local directory on the driver host where Talend stages the job jar, lib jars and temp files before uploading (`spark.local.dir` for local mode) |
| Set Tuning properties | opens the tuning block below | Required (not optional) for Universal Standalone: otherwise "400 - Bad request" |
| Set Web UI port | checkbox + port (default 4040) | `spark.ui.port` for the driver UI |
| Spark serializer | Java / Kryo (`org.apache.spark.serializer.KryoSerializer`) | Kryo is faster; Talend row classes are registered automatically (unverified) |
| Activate checkpointing + Checkpoint directory | HDFS/S3 path | Mandatory for stateful Spark Streaming (tWindow, updateStateByKey patterns); optional lineage truncation for Batch |
| Batch size (ms) (Streaming) | e.g. 2000 | Micro-batch interval; see section 7 |
| Define a streaming timeout (ms) (Streaming) | e.g. 3600000 | Stops the StreamingContext after N ms; otherwise runs until killed |
| Advanced properties | key/value table | Raw `spark.*` and `spark.hadoop.*` keys; last-wins over computed defaults |
| Use local timezone for date | checkbox (Advanced) | Writes/reads Date values in the driver JVM timezone instead of UTC; affects Parquet/Hive timestamp shift (section 11) |
| Enable Spark event logging / Spark event log directory (unverified) | HDFS path | Needed for Spark History Server to show finished jobs |
| Use the Spark cluster's logging configuration (unverified) | checkbox | Else Talend ships its own log4j config |

### Set Tuning properties block

| Field | Spark property | Notes |
|---|---|---|
| Driver memory | `spark.driver.memory` | e.g. `4g`; in Yarn client mode it is the Studio/JobServer JVM so `-Xmx` of the launcher also matters |
| Driver cores | `spark.driver.cores` | Yarn cluster / Standalone |
| Executor memory | `spark.executor.memory` | per executor |
| Set executor memory overhead | `spark.yarn.executor.memoryOverhead` (2.x) / `spark.executor.memoryOverhead` (2.3+) | Raise when YARN kills containers for exceeding physical memory |
| Executor cores | `spark.executor.cores` | Help starting point: 2 cores per executor, executors = total cluster cores / 2, memory = cluster memory / executors |
| Yarn resource allocation | Auto / Fixed / Dynamic | Fixed: "Number of executors" (`spark.executor.instances`). Dynamic: `spark.dynamicAllocation.enabled=true` with "Initial executors", "Min executors", "Max executors" (`spark.dynamicAllocation.initialExecutors/minExecutors/maxExecutors`); requires the YARN external shuffle service |
| Set application master tuning | `spark.yarn.am.memory`, `spark.yarn.am.cores` | Yarn client only (AM is separate from driver) |
| Broadcast factory | Torrent / HTTP (1.x) | Removed in Spark 2 |
| Customize Spark serializer | see above | |
| Set backpressure (Streaming) | `spark.streaming.backpressure.enabled` | Plus initial rate |

Properties available vary by distribution; the help notes "the actual properties
available in the Spark configuration tab could vary depending on the distribution
you are using".

## 4. Spark Universal per-mode parameters

| Mode | Key fields (Spark Configuration tab) | Driver placement / notes |
|---|---|---|
| Local | Spark version; "Set Tuning properties" optional; "Spark scratch directory" | Driver and executors in the Studio/JobServer/Remote Engine JVM. File paths are local unless a storage configuration component is present. Use for unit tests and CI |
| Standalone | Spark host `spark://host:7077`, Spark home, Define the driver hostname or IP address, Set Tuning properties (mandatory), Set Web UI port | Driver in Studio JVM (client deploy mode); cluster must run the same Spark/Scala version; Standalone Spark Universal supported on Spark 3.x |
| Yarn cluster | Hadoop configuration JAR (from metadata or path), Resource Manager + scheduler, Namenode, Kerberos principal/keytab, Spark scratch directory, "Wait for the Job to complete", Set Tuning properties | Driver runs in a YARN ApplicationMaster; Studio submits and polls via YARN REST/RPC. Supported for Spark 3.x (R2026-09 page: 3.x except 3.4.x). Distributions listed: Amazon EMR 6.x/7.x, Cloudera CDP 7.1.x/7.2; "the list is not exhaustive" |
| Kubernetes | Kubernetes master `k8s://https://host:6443`, Namespace, Docker image (Talend provides a base Spark image recipe; `spark.kubernetes.container.image`), Service account, Image pull policy/secret, Driver/executor pod templates (unverified), storage configuration component mandatory (tS3Configuration / tAzureFSConfiguration / tGSConfiguration) for staging jars and data | Driver runs as a pod on the cluster ("cluster" deploy mode); Studio collects status through the Kubernetes API. Supported on Spark 3.x |
| Databricks | Cloud provider (AWS / Azure / GCP), Endpoint (`https://<workspace>.cloud.databricks.com` or `https://adb-xxx.azuredatabricks.net`), Cluster ID (`spark.databricks.clusterUsageTags.clusterId`, Spark UI > Environment) or "Use pool" + Pool ID, Token (PAT), DBFS dependencies folder (must end with `/`, e.g. `/jars/`), Cluster type: Job clusters / All-purpose clusters, Run mode: "Create and run now" (creates a Databricks Job then runs) / "Runs submit" (one-time run, no Job object), Autoscale + Node type / Driver node type / Workers, Databricks runtime version, "Do not restart the cluster when submitting" (unverified label), Poll interval when retrieving Job status | Driver is the Databricks cluster driver; Studio uploads the job jar + Talend libs to DBFS dependencies folder and calls the Jobs API 2.x. Without a storage configuration component data paths are DBFS (`dbfs:/`). Databricks Serverless listed separately in R2026 (restricted component set, e.g. tCacheOut unsupported) |
| Dataproc | Project ID, Cluster ID, Region, Google Storage staging bucket (must pre-exist; the directory is created), Credentials: Service account (JSON key path) / OAuth2 Access Token, "Use Dataproc Serverless" (unverified) | Jobs API submits a Spark job; driver on the cluster master. Compatible with Dataproc 2.0.x and 2.1 (help). 7.3 built-in Dataproc was Yarn client only |
| Synapse (Azure Synapse Analytics Spark pools) | Endpoint (workspace "Development endpoint"), Authentication method: Secret Key / Azure Active Directory (service principal: tenant, client id, secret), Username (secret key only), Apache Spark pools name, ADLS Gen2 Hostname + Container (from workspace Overview) for staging, Poll interval (default 3000 ms), Maximum number of consecutive statuses missing (default 10) | Yarn cluster only (pool-managed). AAD application needs "Storage Blob Data Contributor" on the ADLS Gen2 account. Only Spark pools are supported, not dedicated SQL pools |
| CDE (Cloudera Data Engineering) | Virtual cluster Jobs API endpoint (`https://<vc>.cde-xxx.cloudera.site/dex/api/v1`), Workload user + password or CDP access key/private key, Resource name for uploaded jars, Poll interval (unverified labels) | Studio creates a CDE resource, uploads jars, creates/runs a Spark job through the CDE API; driver inside the CDE virtual cluster (K8s) |
| Spark-submit scripts | Path to `spark-submit` / Spark home on the Studio or engine host, extra arguments, master URL; Talend writes a script and calls it | Lets any cluster that ships a working `spark-submit` run Talend jars (e.g. vendor-specific wrappers); driver placement follows the `--deploy-mode` you pass (unverified) |

Classic (non-Universal) 7.x extras: Databricks fields had "Use transient cluster";
EMR required "Set staging directory" plus `fs.s3a.*` keys; HDInsight mode needed
"Livy configuration" (Livy endpoint on the HDInsight head node, port 443, with
"Deployment Blob" Azure Storage account/container/key and "Poll interval") because
the cluster was reached through Livy rather than YARN RPC.

## 5. Storage configuration components

Spark file components do not carry their own connection; they take it from a
configuration component dropped anywhere in the same Job (no link needed). Basic
settings of every Spark file/DB component: "Define a storage configuration
component" checkbox + "Storage configuration" dropdown listing the tXConfiguration
components in the Job. Unchecked = local file system of the driver/executors
(fine in Local mode; wrong on a cluster). The help: "The configuration component
to be used must be present in the same Job".

| Component | Backs | Key settings |
|---|---|---|
| tHDFSConfiguration | HDFS / `maprfs` / any `hdfs://` default FS | Distribution/Version or Repository metadata, Namenode URI, User name, Kerberos, Use datanode hostname, Hadoop properties table, "Setup HDFS encryption configurations" (KMS URL) (unverified) |
| tS3Configuration | `s3a://` (also EMR's `s3://`) | Access Key / Secret Key or "Inherit credentials from AWS role" / "Assume role" (Role ARN, session name, external id, STS endpoint), Bucket, Region, "Use EMRFS" (EMR only), "Use S3 bucket endpoint", "Encrypt using SSE-S3 / SSE-KMS / SSE-C", Temp folder |
| tAzureFSConfiguration | Azure Blob (`wasbs://`), ADLS Gen1 (`adl://`), ADLS Gen2 (`abfss://`) | Azure FileSystem: Azure Blob Storage / Azure Datalake Storage (Gen1) / Azure Datalake Storage Gen2; Blob account + Access key or SAS token or Azure Active Directory (Tenant ID, Client ID, Client secret / certificate); Container; "Use shared access signature" |
| tGSConfiguration | `gs://` | Project identifier, Google credentials: Service account JSON path or "Use P12 file" (legacy) or OAuth; Bucket; "Use Dataproc default credentials" when on Dataproc |
| (none) | DBFS | On Databricks, with no configuration component, paths resolve against DBFS (`/mnt/...`, `dbfs:/`) |
| tHiveConfiguration | Hive metastore for tHiveInput/tHiveOutput | Distribution, Hive thrift metastore Host/Port (9083), "Execution engine" (Tez for HDP), Kerberos Hive principal `hive/_HOST@REALM`, Hive properties, "Use SSL" |
| tHiveWarehouseConfiguration | Hive Warehouse Connector (HWC) for HDP 3 / CDP 7 managed (ACID) tables | HiveServer2 Interactive (LLAP) JDBC URL, Metastore URI, Zookeeper quorum, Kerberos principal; used by tHiveWarehouseInput/tHiveWarehouseOutput (unverified labels) |
| tHBaseConfiguration | HBase for tHBaseInput/Output (Spark) | Zookeeper quorum, Zookeeper client port, Set zookeeper znode parent, Kerberos (HBase master/regionserver principals), HBase properties |
| tKuduConfiguration | Apache Kudu (CDH/CDP) | Server connection: Kudu master host/port list |
| tCassandraConfiguration | Cassandra via spark-cassandra-connector | Host, Port (9042), Username/Password, Cassandra version, "Configuration" table (`spark.cassandra.*`) |
| tMongoDBConfiguration | MongoDB Spark connector | Server, Port, Database, Use replica set addresses, Auth (SCRAM/Kerberos/X509), SSL |
| tElasticSearchConfiguration | elasticsearch-hadoop | Nodes `host:9200`, Transport addresses, Cluster name, "Use SSL/TLS", User/Password, ES version |
| tJDBCConfiguration | Any JDBC source for tJDBCInput/Output (Spark) | JDBC URL, Driver JAR (Maven coordinates / path), Driver class, User/Password |
| tRedshiftConfiguration | Redshift via spark-redshift + S3 temp | Host, Port 5439, Database, Schema, credentials, S3 temp path (tS3Configuration), "Use an IAM role", Driver version |
| tSnowflakeConfiguration | Snowflake Spark connector | Account, Region, User/Password or Key pair, Warehouse, Database, Schema, "Connection properties" |
| tDynamoDBConfiguration | DynamoDB (emr-dynamodb-hadoop) | Access key/Secret key or inherit, Region, Endpoint |
| tCosmosDBConfiguration | Azure Cosmos DB (SQL API / MongoDB API) via Spark connector | URI, Key, Database, "Preferred regions" |
| tDeltaLakeConfiguration (unverified name) | Delta Lake tables on Databricks/ADLS/S3 | Storage settings; tDeltaLakeInput/tDeltaLakeOutput read/write delta format with "Time travel" (version / timestamp) and "Merge" modes |
| tBigQueryConfiguration | BigQuery via spark-bigquery connector | Project, Service account JSON, Temp GCS bucket |
| tSetKeystore | TLS truststore/keystore for Spark components (Kafka SSL, ES https, JDBC SSL) | TrustStore type (JKS/PKCS12), path, password; KeyStore equivalents; "Check server identity" |
| tLibraryLoad | Extra jar on driver + executors | Library path / Maven coordinate; Spark version adds jars to `spark.jars` |

Rule: one configuration component per storage system per Job; if two exist the
component dropdown lets you choose. For Yarn cluster / Kubernetes / Databricks
the configuration component is also used to stage Talend's own jars when the
Spark scratch dir cannot be reached from the driver.

## 6. Spark Batch component catalog

Family labels in the Spark palette: Big Data > (HDFS, Hive, HBase, Kudu, ...),
File (Delimited, Positional, Regex, JSON, XML, Avro, Parquet, ORC), Processing,
Machine Learning, Natural Language Processing (tNLPPreprocessing, tNLPModel,
tNLPPredict), Data Quality, Databases (NoSQL, Cloud), Logs & Errors, Misc,
Technical, Orchestration (tRunJob/tPrejob/tPostjob), Internet (tS3*, tPubSub*).

### File input / output (Spark Batch)

| Component | Purpose | Key settings | Notes |
|---|---|---|---|
| tFileInputDelimited | Read CSV/TSV from storage config FS | Folder/File, Row separator, Field separator, Header, "Use multiple-lines quoted text" (unverified), Schema, Advanced: "Set minimum partitions", Encoding, Trim | Path can be a directory (all files) or glob; compressed files (gz, bz2, snappy) are decompressed by codec extension |
| tFileInputPositional | Fixed-width | Pattern `"10,8,*"` | |
| tFileInputRegex | Regex-split lines | Regex with groups | |
| tFileInputFullRow | One column `line` per line | | Pair with tExtractDelimitedFields / tExtractRegexFields |
| tFileInputJSON | JSON (one object per line "JsonPath"/"Xpath" loop) | Read by: JsonPath / XPath, Loop Jsonpath query, Mapping table | Spark reads multi-line JSON poorly; prefer JSON Lines |
| tFileInputXML | XML via loop XPath | Loop XPath query, Mapping, "Element to process" | Large XML must be splittable (one record per line) or runs as a single partition |
| tAvroInput / tAvroOutput | Avro (Spark jobs use tAvroInput/tAvroOutput, not tFileInputAvro/tFileOutputAvro) | Folder, Schema (auto-inferred from Avro schema), Output: Compression (None/Snappy/Deflate), Action: Create/Overwrite | Spark-avro version bound to Spark version |
| tFileInputParquet / tFileOutputParquet | Parquet | Folder/File; Output: Action (Create/Overwrite), Compression (Uncompressed/Snappy/Gzip), "Merge result to single file"? (Parquet uses coalesce via tPartition instead) (unverified), Advanced "Use Timestamp format for Date type" | Schema can be retrieved from the file by the "Retrieve Schema" button on metadata; Dynamic column supported for complex Parquet structures in 8.0 (with tSqlRow) |
| tFileInputORC / tFileOutputORC | ORC | same shape as Parquet | Hive-friendly; available from 7.x |
| tFileOutputDelimited / Positional / JSON / XML | Write text | Folder, Action: Create / Overwrite (no Append), "Merge result to single file" + "Merge file path" + "Remove source dir" (concatenates part-files on the driver via FileUtil.copyMerge), Compress (gzip/bz2/snappy/lz4), Include header, Encoding | Output is a directory of `part-xxxxx` files; "Merge result to single file" is single-threaded and pulls everything through the driver; "Create" fails if the folder exists |
| tFileOutputJSON | One JSON doc per row or whole | "Generate as JSON Lines"? (unverified) | |
| tFileStream* | Streaming-only, see section 7 | | |

### Hive, HBase, Kudu, NoSQL, cloud DB (Spark Batch)

| Component | Purpose | Key settings | Notes |
|---|---|---|---|
| tHiveInput | Read Hive table or query as Dataset | Hive storage configuration (tHiveConfiguration), Input source: Hive table / Hive query, Hive database, Table name, Hive query | Uses HiveContext/`SparkSession.enableHiveSupport`; on HDP3/CDP managed ACID tables needs HWC instead |
| tHiveOutput | Write Dataset to Hive | Output source: Hive table (unverified: also "ORC file"), Database, Table name, Table format: Text / ORC / Parquet / Avro / RCFile (unverified list), Save mode: Create / Append / Overwrite, "Enable Hive partitions" + Partition keys, Advanced: "Use Timestamp format for Date type", "Sort columns alphabetically" | Creates the table when missing; partition columns must be last in schema |
| tHiveWarehouseInput / tHiveWarehouseOutput | HWC read/write (HDP 3.x, CDP 7.x) | tHiveWarehouseConfiguration, Table/Query, Save mode | Only path to Hive 3 managed/transactional tables from Spark; requires LLAP (HiveServer2 Interactive) or CDP HWC "JDBC_CLUSTER"/"spark" read modes (unverified) |
| tHBaseInput / tHBaseOutput | Scan/Put HBase | tHBaseConfiguration, Table name, Mapping table (Column, Column family, Qualifier), Row key column, Filters (Spark input), "Is by filter" | Row key is a mandatory mapping; Spark HBase connector version tied to distribution |
| tKuduInput / tKuduOutput | Kudu scan/upsert | tKuduConfiguration, Table name, Action: Insert/Update/Upsert/Delete, Create table: Hash/Range partitions, Replicas | CDH/CDP only |
| tCassandraInput / tCassandraOutput | Cassandra | Keyspace, Column family, Query (CQL), Action: Insert/Update/Delete, Consistency level | |
| tMongoDBInput / tMongoDBOutput | MongoDB | Collection, Query, Mapping (nested docs via "Parent node path"), Action: Insert/Upsert/Update | |
| tElasticSearchInput / tElasticSearchOutput | ES index read/write | Index/Type, Query, "Use JSON output"/"Document ID column" | |
| tJDBCInput / tJDBCOutput | Any JDBC via Spark JDBC datasource | tJDBCConfiguration, Table/Query, "Partition column / Lower bound / Upper bound / Number of partitions" (parallel read), Action: Insert/Update/Upsert/Delete, Batch size | Without partition settings the read is one partition (single executor) |
| tRedshiftInput / tRedshiftOutput / tRedshiftLookupInput | Redshift via UNLOAD/COPY through S3 | tRedshiftConfiguration, Table/Query, Save mode | Needs tS3Configuration temp dir and IAM role |
| tSnowflakeInput / tSnowflakeOutput | Snowflake Spark connector | Table/Query, Action, "Use merge" | |
| tDeltaLakeInput / tDeltaLakeOutput | Delta format (Databricks, or OSS Delta jars) | Folder/Table, Time travel: "Version as of" / "Timestamp as of", Output Action: Create/Append/Overwrite/Merge(upsert keys) | 7.3 R2020+/8.0 |
| tBigQueryInput / tBigQueryOutput (Spark) | BigQuery via connector | Table/Query, Temp bucket, Write disposition | Dataproc-centric |
| tDynamoDBInput / tDynamoDBOutput, tCosmosDBInput / tCosmosDBOutput, tMarkLogicInput/Output, tNeo4jInput/Output (7.x) | Cloud NoSQL | per connector | Several deprecated in 8.0 R2023+ (Neo4j, MarkLogic Spark) (unverified) |
| tSqoopImport etc. | Not Spark; Standard only | | see section 8 |

### Processing (Spark Batch)

| Component | Purpose | Key settings | Spark-specific notes |
|---|---|---|---|
| tMap | Join/transform | Same editor as Standard (see tmap-expressions.md) | Lookup "Model" fixed to "Load once"; "Reload at each row" and "Store temp data" unavailable. Joins become Spark joins; Advanced setting "Use replicated join" broadcasts the lookup to executors (keep lookups small, under driver memory). Inner join + "Catch lookup inner join reject" supported. Expressions run in executors: routines must be serializable/static; no `globalMap.put` visible elsewhere |
| tAggregateRow | Group by + functions | Group by, Operations (count, sum, min, max, avg, first, last, list, count distinct, std dev) | Shuffle; "list" collects into a delimited string on one executor per key |
| tSortRow | Sort | Criteria (asc/desc, num/alpha/date) | Global sort = range partition shuffle; expensive at scale |
| tFilterRow / tFilterColumns | Filter rows (conditions or "Use advanced mode" Java) / project columns | | Narrow transformations |
| tUniqRow | Distinct on key columns | Key attribute checkboxes, "Only once each duplicated key" | Shuffle; duplicates link available |
| tJoin | Inner/left join by key | Include lookup columns, Inner join reject | Alternative to tMap for simple joins |
| tNormalize / tDenormalize | Split/concatenate list columns | Item separator, Delimiter | flatMap / groupBy |
| tReplicate | Duplicate a flow to N outputs | | No Spark `cache` by itself; pair with tCacheOut when branches re-read |
| tUnite | Union flows with identical schema | | `union` (no dedupe) |
| tSqlRow | Spark SQL / HiveQL over input links | SQL context: Spark SQL (SQLContext) / Hive (HiveContext; no metastore access, use tHiveInput for that), SQL Query, "Register table" implicit: each input link `rowN` is a temp view named after the link label (`select a.id, b.name from row1 a join row2 b on a.id=b.id`), Advanced: "Register UDF jars" + "Temporary UDF functions" (alias -> class) | Output schema must match the SELECT list (set via Edit schema or "Sync columns"). Spark version decides SQL dialect (ANSI mode defaults, `legacy.timeParserPolicy`) |
| tPartition | Repartition | Number of partitions, Partition key columns, "Use custom partitioner" (class implementing `org.apache.spark.Partitioner`), "Sort within partitions" / "Use ... hash" (unverified) | Controls parallelism and output file count; coalesce to 1 before tFileOutput* to get one file without the driver-side merge |
| tCacheOut / tCacheIn | Persist an RDD/Dataset and reuse in another subjob | tCacheOut: Storage level (MEMORY_ONLY, MEMORY_ONLY_SER, MEMORY_AND_DISK, MEMORY_AND_DISK_SER, DISK_ONLY, OFF_HEAP, plus `_2` replicated variants mapped to Spark StorageLevel); tCacheIn: "Output cache" = the tCacheOut to read | tCacheOut is an end component; the follow-up subjob (OnSubjobOk) starts with tCacheIn. Beta in 8.0 pages; unsupported on Databricks Serverless |
| tSample | Random sample | Fraction / Sample size, Seed, With replacement | |
| tTop / tTopBy | First N rows globally / per key after sorting | Number of lines, Criteria / Key | Collects top N per partition then merges on driver |
| tExtractDelimitedFields / tExtractPositionalFields / tExtractRegexFields / tExtractJSONFields / tExtractXMLField (unverified name) / tExtractAvroFields | Parse a string/byte column into columns | Field to split, separator/regex/JsonPath/XPath, Loop query | Core of streaming payload parsing |
| tWriteDelimitedFields / tWritePositionalFields / tWriteJSONField / tWriteXMLField (unverified) / tWriteAvroFields | Serialize a row into one string/byte column | Output column (`serializedValue`/`messageContent`), Separator, Configure JSON tree | Used before tKafkaOutput/tFileOutput of payloads |
| tConvertType | Cast columns | Auto cast, "Die on error" | Spark version only casts compatible types |
| tReplace | String replace | | |
| tSplitRow | One row -> N rows | | |
| tJavaRow | Per-row Java in executors | Code (uses `input_row`/`output_row`), Schema | Runs in a `map`; no `globalMap` writes persist; use `tJavaRow`'s "Import" for libs; avoid non-serializable fields |
| tJava | Driver-side Java | Code, "Import" | Executes once on the driver when its subjob runs; can read `globalMap` and the `SparkSession` through generated variables (name unstable, (unverified)) |
| tRowGenerator / tFixedFlowInput | Synthetic rows | Number of rows, values | Parallelism: one partition unless "Number of partitions" set (tRowGenerator Spark has it, (unverified)) |
| tLogRow | Print rows to driver console | Mode: Basic / Table / Vertical, Print header | Runs `collect()` to the driver: OOM on big flows; use tSample/tTop first. "Table" mode buffers everything |
| tCollectAndCheck | Assert rows against expected values in Test Cases | Separator, Expected result lines, "Keep order" | Only in test case instances of Spark jobs |
| tWarn / tDie | Driver-side logging / abort | | tDie stops the SparkContext with exit code |
| tRunJob / tPrejob / tPostjob | Orchestration inside Spark jobs | | tRunJob inside a Spark job runs a child Standard or Spark job as a separate JVM/application |

### Machine Learning (Spark MLlib) and DQ

| Component | Role | Key settings |
|---|---|---|
| tModelEncoder | Feature engineering | Transformation table: Input/Output column, Transformation (Tokenizer, RegexTokenizer, StopWordsRemover, HashingTF, Word2Vec, CountVectorizer, StringIndexer, OneHotEncoder, VectorAssembler, Normalizer, StandardScaler, MinMaxScaler, PCA, Binarizer, Bucketizer, QuantileDiscretizer, ChiSqSelector, DCT, IDF, NGram, PolynomialExpansion, VectorIndexer, SQLTransformer), Parameters (`key=value;...`) |
| tLogisticRegressionModel, tDecisionTreeModel, tRandomForestModel, tGradientBoostedTreeModel, tNaiveBayesModel, tSVMModel, tLinearRegressionModel, tKMeansModel, tALSModel | Train and save model | Vector to process (features column), Label column, Model location: "Save the model on file system" + HDFS folder (needs storage config), algorithm hyperparameters (Max iterations, Regularization, Number of clusters, Max depth/bins, Rank/Lambda...) |
| tPredict | Apply classification/regression/clustering model | Model type, Model computed in the current Job (link from model component) / Model on filesystem (folder), Features column; output adds `label`/`prediction` column |
| tClassify / tClassifySVM | Older classification appliers (tPredict superseded) | |
| tRecommend | Apply ALS model | Model, User/Product columns |
| tKMeansStrModel | Streaming k-means (Spark Streaming) | |
| tNLPPreprocessing / tNLPModel / tNLPPredict | NLP (CoreNLP/OpenNLP) | Tokenization, NER model training |
| tMatchModel / tMatchPairing / tMatchPredict / tRuleSurvivorship / tMatchIndex (DQ) | ML-assisted matching, survivorship, Elasticsearch-indexed matching | See data-quality-governance.md |
| tDataMasking / tDataUnmasking / tDataShuffling / tDataEncrypt / tDataDecrypt / tPatternMasking / tPatternUnmasking (Spark) | DQ privacy functions distributed | Same function table as Standard; FF1 format-preserving with "Password" or cryptographic key file |

MLlib components depend on Spark MLlib of the selected Spark version; several
were marked deprecated in 8.0 R2023-R2024 release notes (check "deprecated and
removed features big data" pages for the exact release, (unverified)).

## 7. Spark Streaming components

Big Data Streaming jobs reuse most Spark Batch processing components (tMap,
tAggregateRow per micro-batch, tSqlRow, tFilterRow, tJavaRow, tExtract*,
tWrite*, tCacheOut) and add sources/sinks that produce DStreams. Lookups in tMap
are loaded once at start (static) or, for streaming lookups, re-read per batch
(unverified behaviour per component).

| Component | Purpose | Key settings | Notes |
|---|---|---|---|
| tKafkaInput (Spark Streaming) | Kafka direct stream | Broker list `host:9092,...`, Topic name, Group ID (Kafka 0.10+), Starting offset: From beginning / From latest, "Set number of records per second to read from each Kafka partition" (`spark.streaming.kafka.maxRatePerPartition`), Kafka version (0.8 / 0.9 / 0.10 / 1.x-2.x), Consumer properties (security.protocol, sasl.*, ssl.* via tSetKeystore), "Use SSL/TLS", "Use Kerberos" (jaas config) | Output schema is a single read-only `payload` column (byte[] by default, String when "Output type" set, (unverified)); parse with tExtractDelimitedFields/tExtractJSONFields/tJavaRow. With checkpointing on, offsets resume from the checkpoint and "Starting offset" is ignored |
| tKafkaInputAvro (7.x) | Kafka + Avro deserialization | Same + Avro schema | Replaced by tKafkaInput + tExtractAvroFields / Schema Registry components in later releases (unverified) |
| tKafkaOutput (Spark Streaming) | Produce | Broker list, Topic name, Compress (gzip/snappy/lz4), Producer properties, input column `serializedValue` from tWriteDelimitedFields/tWriteJSONField | One producer per partition per batch |
| tKinesisInput / tKinesisInputAvro / tKinesisOutput | AWS Kinesis via KCL/KPL | Access key / Secret key or inherit, Stream name, Endpoint URL `https://kinesis.<region>.amazonaws.com`, Region, Initial position: LATEST / TRIM_HORIZON, Checkpoint interval, Storage level; Output: Partition key column | KCL keeps lease table in DynamoDB named after the app |
| tPubSubInput / tPubSubOutput | Google Pub/Sub | Project, Topic, Subscription (input), Credentials, "Create subscription if it does not exist" | 7.x Dataproc era |
| tMQTTInput / tMQTTOutput | MQTT broker (IoT) | Broker URL `tcp://host:1883`, Topic, QoS, Client id | |
| tJMSInput / tJMSOutput (Spark Streaming) (unverified availability) | JMS via custom receiver | Context provider, Connection factory | |
| tFileStreamInputDelimited / Positional / Regex / FullRow / JSON / XML / Parquet, tAvroStreamInput | File-system watcher sources: each batch picks up files newly created in the folder | Folder (on storage config FS), "Include subfolders"?, same parsing options as batch | Files must be moved atomically into the folder (Spark fileStream semantics); existing files at start are ignored unless configured |
| tWindow | Windowed DStream | Window duration (ms), "Define the slide duration" + Slide duration (ms) | Both must be multiples of Batch size; requires "Activate checkpointing"; place after the source, before aggregations |
| tSocketTextInput? | not provided | | Use tKafkaInput |
| Streaming sinks: tFileOutputDelimited/JSON/Parquet/Avro, tHDFSOutput? (Streaming jobs use tFileOutput* with "Rolling" / prefix per batch), tHiveOutput, tHBaseOutput, tElasticSearchOutput, tMongoDBOutput, tCassandraOutput, tJDBCOutput, tRedshiftOutput, tKafkaOutput, tKinesisOutput, tPubSubOutput, tMQTTOutput, tLogRow | Each micro-batch writes its own `part-` files in a timestamped subfolder (tFileOutput*: "Folder" + batch suffix) | Small files problem: compact downstream |

Spark Configuration (Streaming) extras: "Batch size (ms)" (micro-batch interval,
default about 2000), "Define a streaming timeout (ms)" (stops the job cleanly
after N ms; used to make streaming jobs terminate in TAC/TMC schedules), "Activate
checkpointing" + "Checkpoint directory" (HDFS/S3/ADLS path; stores DStream
metadata and Kafka offsets; must be a stable path across restarts and must be
deleted when the job graph or Spark version changes), "Set backpressure" and
"Spark serializer". Stop semantics: the driver registers a shutdown hook that
calls `StreamingContext.stop(stopGracefully=true)` when killed with SIGTERM
(TAC "Kill" / `yarn application -kill` is not graceful) (unverified).

Running streaming jobs: TAC has a dedicated "Big Data Streaming Conductor"
page (separate from Job Conductor) that keeps the task "Running" and offers
Stop; TMC runs Big Data Streaming artifacts as tasks on a Remote Engine (Cloud
Engines cannot run Big Data jobs) and relies on the streaming timeout or manual
stop. Streaming jobs cannot be scheduled with a tight cron because each run is
a new Spark application competing for the checkpoint directory.

## 8. Standard-job Hadoop components (HDFS, Hive, Impala, HBase, Sqoop)

These run inside the Standard JVM and talk to the cluster as a client; they
appear under Big Data > HDFS / Hive / Impala / HBase / Sqoop in Standard jobs.

| Component | Purpose | Key settings | Notes |
|---|---|---|---|
| tHDFSConnection | Shared connection | Distribution/Version, Namenode URI, User name, Kerberos, "Use datanode hostname", Hadoop properties; "Use Knox" (Knox gateway URL, user, password, WebHDFS path) on HDP in 7.3+ (unverified) | Reused with "Use an existing connection" |
| tHDFSInput / tHDFSOutput | Read/write delimited text on HDFS row by row | File name, Type: Text / Sequence File, Row/Field separator, Header, Action: Create / Overwrite / Append, Compression (gzip/bz2) | Single-threaded; for volume use Spark jobs |
| tHDFSOutputRaw | Write a whole String/byte[] column to a file | | For XML/JSON blobs |
| tHDFSPut / tHDFSGet | Local -> HDFS / HDFS -> local file transfer | Local dir, HDFS dir, Files mask table (Filemask / New name), Overwrite file: always / never / size | Returns `globalMap.get("tHDFSPut_1_NB_FILE")` |
| tHDFSList | Iterate HDFS files | Directory, FileList type (Files / Directories / Both), Files mask, "Include subdirectories", Order by | Iterate link exposes `((String)globalMap.get("tHDFSList_1_CURRENT_FILEPATH"))` |
| tHDFSExist / tHDFSDelete / tHDFSRename / tHDFSCopy / tHDFSProperties / tHDFSCompare / tHDFSRowCount | File ops | | `tHDFSExist_1_EXISTS`, `tHDFSRowCount_1_COUNT` globals |
| tHiveConnection | HiveServer2 JDBC | Connection mode: Standalone (JDBC) / Embedded (in-process, deprecated), Hive server: Hive 1 / Hive 2, Host, Port 10000 (HTTP transport 10001 with `transportMode=http;httpPath=cliservice`), Database, Username/Password, "Use Kerberos authentication" (Hive principal `hive/_HOST@REALM`, Namenode/RM principals for Embedded), "Use a keytab", "Use SSL" (truststore), "Set Resource Manager" etc. (Embedded), Hive properties, Hadoop properties, "Execution engine" (MapReduce / Tez / Spark) in 6.x/7.x | Zookeeper service discovery: `jdbc:hive2://zk1:2181,zk2:2181/;serviceDiscoveryMode=zooKeeper;zooKeeperNamespace=hiveserver2` via "Use ZooKeeper" / JDBC URL override (unverified) |
| tHiveRow | Execute HiveQL (DDL/DML) | Query, "Propagate QUERY's recordset" | Sequencing DDL (ALTER TABLE ADD PARTITION) |
| tHiveInput | SELECT into a flow | Query, Schema | Fetches through JDBC: driver-side, slow for volume |
| tHiveCreateTable | DDL helper | Table, Action on table (Create / Create if not exists / Drop and create), Format: TEXTFILE / SEQUENCEFILE / RCFILE / ORC / PARQUET / AVRO / INPUTFORMAT-OUTPUTFORMAT / STORED BY, Partition columns, Row format, "Set the location of the table" (external) | |
| tHiveLoad | `LOAD DATA [LOCAL] INPATH` / `INSERT ... SELECT` | Load action: LOAD / INSERT, Target type: Table / Directory, Partitions, Overwrite, "Local" | |
| tHiveClose | Close JDBC | | |
| tImpalaConnection / tImpalaInput / tImpalaOutput / tImpalaRow / tImpalaCreateTable / tImpalaLoad / tImpalaClose | Impala over JDBC (port 21050) | Distribution CDH/CDP, Host, Port, Database, Kerberos principal `impala/_HOST@REALM`, "Use SSL" | tImpalaRow `INVALIDATE METADATA`/`REFRESH table` after writing files with Spark |
| tHBaseConnection / tHBaseInput / tHBaseOutput / tHBaseClose (Standard) | HBase client | Zookeeper quorum/port, Table, Mapping (column family/qualifier), Row key, Filters table (Standard tHBaseInput: Filter type / column / family / operation / value), "Set table namespace mappings" | Also tHBaseLookupInput in Spark Streaming |
| tSqoopImport | RDBMS -> HDFS/Hive/HBase via Sqoop | Mode: Use Commandline (needs `sqoop` on PATH of the JVM host) / Use Java API, Hadoop properties, JDBC connection (URL/driver jar/user/password or `--password-file`), Table name / "Use query" + "Split by", Target dir, File format: textfile / sequencefile / avrodatafile / parquetfile, "Specify Number of Mappers", Delete target directory, "Direct" (vendor fast path), Hive import ("Import to Hive", Hive table, overwrite), HBase import, Compress + codec, Incremental (append / lastmodified, check column, last value), "Additional arguments" table (`--map-column-java`, `--null-string`, `--fetch-size`) | Java API mode runs Sqoop in-process: driver jar must be in Studio libs and the Hadoop client config must be loadable; Commandline mode just shells out, so logs are Sqoop's. Sqoop removed from CDP 7.x Public Cloud; Sqoop 1 retired upstream 2021 |
| tSqoopExport | HDFS -> RDBMS | Export dir, Table, Update key / Update mode (updateonly / allowinsert), Staging table, Input delimiters, Number of mappers | |
| tSqoopImportAllTables | Whole schema import | Exclude tables, Warehouse dir | |
| tSqoopMerge | Merge incremental datasets | New data dir, Old data dir, Merge key, Target dir, Jar + class name from codegen | |
| tHCatalogInput/Output/Load/Operation (removed 8.0) | HCatalog | | Use Hive components |
| tOozieScheduler (removed 8.0) | Oozie workflow submission from Studio Oozie view | | Use TAC/TMC scheduling |
| tPig* (removed 8.0) | Pig Latin generation | | Convert to Spark jobs |

HDFS component "Distribution" dropdown also offers "Custom" (6.x/7.x) where you
import a zip of client jars; in 8.0 use Universal/Hadoop configuration JAR or the
generic `hadoop-client` of the closest distribution.

## 9. Execution model: driver placement, jars, logs

Generated code: a Spark job compiles to one Java class (`<project>.<job>_<version>.<JobName>`)
whose `main`/`runJobInTOS` builds `SparkConf` from the Spark Configuration tab
(`spark.master`, `spark.app.name = <JobName>_<timestamp>`, tuning keys, Advanced
properties), creates a `SparkSession`/`JavaSparkContext`, then executes each
subjob as a chain of transformations ending in an action (`saveAsTextFile`,
`write().parquet()`, `foreachPartition` for DB outputs, `collect` for tLogRow).
Standard orchestration glue (tPrejob/tPostjob, OnSubjobOk, tRunJob, context
loading, `--context_param`) is identical to Standard jobs (deployment-runtime.md).

Where the driver runs:

| Mode | Driver | What Studio/engine uploads | Where Talend libs go |
|---|---|---|---|
| Local | Studio / JobServer / Remote Engine JVM | nothing | job classpath (`lib/`) |
| Standalone, Yarn client (classic) | Studio/engine JVM | job jar + routines + `lib/*.jar` to the Spark scratch directory, then to executors via `spark.jars` / HDFS staging (`/user/<user>/.sparkStaging/<appId>/`) | staging dir |
| Yarn cluster | ApplicationMaster container on the cluster | job jar + dependencies to HDFS staging dir ("Set staging directory"); keytab shipped as `spark.yarn.keytab` | `__spark_libs__` / staging |
| Kubernetes | driver pod | jars to the storage configuration bucket (`spark.kubernetes.file.upload.path`) | image + uploaded jars |
| Databricks | cluster driver node | jars to "DBFS dependencies folder"; the job is created/run through Jobs API with `spark_jar_task` main class = generated job class | DBFS |
| Dataproc / Synapse / CDE | cluster master / pool driver / CDE pod | jars to GS staging bucket / ADLS Gen2 container / CDE resource | respective storage |
| Spark-submit scripts | per `--deploy-mode` | Talend writes `spark-submit --class <job class> --jars <libs> <job jar> --context_param ...` | local Spark home |

Dependencies: Studio bundles Spark client jars per distribution/Universal version
under `<studio>/configuration/.m2` and the job build's `lib/` (hundreds of MB).
Exclusions: cluster-provided jars (`spark-core`, `hadoop-*`) are flagged
"provided" so they are not uploaded; Talend's own `talend-bigdata-*.jar`,
routines jar and third-party connector jars are uploaded each run (set a stable
scratch/staging dir to reuse them; Studio compares checksums and skips unchanged
jars (unverified)).

Logs and monitoring:
- Run view console shows driver log4j output (level from Run > Advanced settings
  > log4jLevel) and, in Yarn cluster, the polled YARN application state.
- `yarn logs -applicationId application_<id>` aggregates driver + executor logs
  after the app finishes (needs `yarn.log-aggregation-enable=true`).
- Spark Web UI on the driver (`http://<driver>:4040`, "Set Web UI port"), Spark
  History Server when event logging is enabled; Databricks: Spark UI tab of the
  cluster; Dataproc: Cluster > Web interfaces; Synapse: Monitor > Apache Spark
  applications.
- `spark.app.name` is the Talend job name, so `yarn application -list | grep
  <JobName>` finds the running app; tDie/exit code is propagated from the driver
  to the launcher (`<job>_run.sh` exit status) only in client modes; in Yarn
  cluster mode Studio maps FINAL_STATUS FAILED to a non-zero exit (unverified).

## 10. Hive, HDFS HA, Kerberos, security specifics

### Hive
- Hive versions follow the distribution: CDH 5 = Hive 1.1, CDH 6 = Hive 2.1, HDP
  2.6 = Hive 1.2/2.1 (LLAP), HDP 3 / CDP 7 = Hive 3.1 (ACID by default for
  managed tables, Tez only, LLAP via HiveServer2 Interactive).
- Spark (tHiveInput/tHiveOutput) talks to the metastore directly and reads
  table files; it cannot read Hive 3 transactional (ACID) managed tables. Fixes:
  create tables as EXTERNAL (`TBLPROPERTIES('transactional'='false')`), or use
  tHiveWarehouseConfiguration + tHiveWarehouseInput/Output (HWC), which routes
  reads through LLAP/JDBC and writes through the HWC API.
- tHiveConnection (Standard) "Execution engine": Tez on HDP/CDP (`hive.execution.engine=tez`
  is the default there; MapReduce removed in Hive 3), Spark for Hive-on-Spark on
  CDH 5.7+/6 (`hive.execution.engine=spark`). Set per session via Hive properties
  table or `SET` in tHiveRow.
- Partitioned writes: tHiveOutput "Enable Hive partitions" + partition keys
  (dynamic partitioning: `hive.exec.dynamic.partition.mode=nonstrict` set by
  Talend; cap `hive.exec.max.dynamic.partitions`). tFileOutputParquet to a
  partitioned path + tHiveRow `MSCK REPAIR TABLE` / `ALTER TABLE ADD PARTITION`
  is the alternative.
- Formats: ORC is the Hive-native columnar format (ACID requires ORC); Parquet is
  interoperable with Spark/Impala; Avro for schema evolution. Impala needs
  `INVALIDATE METADATA` after external writes.
- Database/catalog: tHiveInput "Hive database" + table; Spark SQL in tSqlRow
  (Hive context) only sees temp views unless `enableHiveSupport` with the right
  `hive-site.xml` in the Hadoop configuration JAR; "Table not found" usually means
  default database or missing metastore URI (`hive.metastore.uris=thrift://ms:9083`).

### HDFS / YARN high availability (Hadoop properties table)
```
dfs.nameservices=prodns
dfs.ha.namenodes.prodns=nn1,nn2
dfs.namenode.rpc-address.prodns.nn1=nn1.example.com:8020
dfs.namenode.rpc-address.prodns.nn2=nn2.example.com:8020
dfs.client.failover.proxy.provider.prodns=org.apache.hadoop.hdfs.server.namenode.ha.ConfiguredFailoverProxyProvider
yarn.resourcemanager.ha.enabled=true
yarn.resourcemanager.ha.rm-ids=rm1,rm2
yarn.resourcemanager.hostname.rm1=rm1.example.com
yarn.resourcemanager.hostname.rm2=rm2.example.com
yarn.resourcemanager.cluster-id=yarn-prod
```
Namenode URI then is `hdfs://prodns` (no port). Importing `*-site.xml` into the
Hadoop Cluster metadata fills these automatically; manual entry must add them to
every component or to the metadata's Hadoop properties.

### Kerberos
- Client side needs `krb5.conf` (Studio: `-Djava.security.krb5.conf=C:\krb5.ini`
  in `Talend-Studio-*.ini`; JobServer/Remote Engine: same JVM arg or
  `/etc/krb5.conf`), realm/KDC reachable, clock skew < 5 min.
- Hadoop properties implied: `hadoop.security.authentication=kerberos`,
  `hadoop.security.authorization=true`, `dfs.namenode.kerberos.principal`,
  `yarn.resourcemanager.principal`, `hive.server2.authentication=KERBEROS`,
  `hbase.security.authentication=kerberos` (plus master/regionserver principals).
- Keytab vs ticket cache: "Use a keytab to authenticate" is the only workable
  option for TAC/TMC/JobServer runs (no interactive kinit). Multiple Kerberos
  clusters in one JVM collide on `UserGroupInformation` static state: run them in
  separate tRunJob "Use an independent process" children.
- Hive JDBC with Kerberos: URL `jdbc:hive2://hs2:10000/default;principal=hive/_HOST@REALM`
  (Talend builds it from the Hive principal field). Over Knox:
  `jdbc:hive2://knox:8443/;ssl=true;transportMode=http;httpPath=gateway/default/hive`
  with user/password (LDAP), no Kerberos on the client.
- AES-256 tickets on Java 8 < u161 require the unlimited JCE policy jars;
  Studio 8 on Java 11/17 does not.
- Debug: `-Dsun.security.krb5.debug=true -Dsun.security.spnego.debug=true` in the
  .ini / JVM parameters of the task.

### Authorization, encryption, gateways
- Sentry (CDH) / Ranger (HDP, CDP): permission errors surface as
  `AccessControlException` (HDFS) or `HiveAccessControlException` (Hive); the
  Talend principal needs the Hive database privileges and the HDFS path ACLs for
  the Spark scratch/staging dir and the table locations.
- HDFS encryption zones (KMS): the client needs `hadoop.security.key.provider.path=kms://https@kms:9494/kms`
  (usually in `core-site.xml`) and decrypt EEK privileges; tHDFSConfiguration has a
  KMS field in 7.x ("Setup HDFS encryption configurations", (unverified)).
- Knox: WebHDFS/Hive/HBase REST through the gateway; HDFS components in 7.3+ have
  a Knox option (unverified); Spark jobs cannot run through Knox (they need RPC to
  RM/Namenode), so Knox is a Standard-job feature.
- TLS: HiveServer2/Impala "Use SSL" with truststore; Kafka/ES via tSetKeystore;
  Hadoop RPC encryption via `hadoop.rpc.protection=privacy`,
  `dfs.encrypt.data.transfer=true` in Hadoop properties.

## 11. Data formats, schema and types in Spark jobs

| Topic | Behaviour |
|---|---|
| Talend schema -> Spark types | String->StringType, Integer->IntegerType, Long->LongType, Double->DoubleType, Float->FloatType, Boolean->BooleanType, Short->ShortType, Byte->ByteType, BigDecimal->DecimalType(precision, scale from schema Length/Precision), Date->TimestampType (Talend `Date` is `java.util.Date` with time; written to Parquet as INT96/TIMESTAMP_MICROS, to Hive as `timestamp`), byte[]->BinaryType, Character->StringType(1), Object->not supported in Spark (serialization), Document->not available in Spark jobs (no tXMLMap/Document type; use tFileInputXML + tExtractXMLField mappings) |
| Date vs DATE | There is no date-only type; writing to a Hive `date` column needs the "Use Timestamp format for Date type" switch off / explicit cast in tSqlRow (`cast(col as date)`); reading Hive `date` yields midnight timestamps |
| Timezone | Spark stores timestamps as UTC instants; Talend formats with the driver/executor JVM zone. "Use local timezone for date" (Spark Configuration Advanced) makes Talend interpret `Date` in the JVM default zone instead of UTC. Mismatched executor TZ (cluster UTC, Studio local) shifts Parquet/Hive timestamps by the offset; fix by setting `spark.sql.session.timeZone=UTC` and `-Duser.timezone=UTC` on driver (`spark.driver.extraJavaOptions`) and executors (`spark.executor.extraJavaOptions`) |
| Spark 3 date parsing | `spark.sql.legacy.timeParserPolicy=LEGACY` restores Spark 2 `SimpleDateFormat` behaviour for patterns in tSqlRow / tConvertType; Spark 3 also rejects INT96 rebase ambiguity: `spark.sql.parquet.int96RebaseModeInWrite=LEGACY` / `datetimeRebaseModeInRead` for pre-1582 dates |
| Decimal | DecimalType requires Length/Precision in the Talend schema; unset gives (10,0) and truncates; Parquet decimal is written as FIXED_LEN_BYTE_ARRAY |
| Nullability | Spark Dataset columns are nullable by default; Talend "Nullable" unchecked only matters for primitives in tMap expressions (NPE/unboxing) |
| Avro | tAvroInput infers the schema from the files' embedded schema (Retrieve schema in metadata); Avro logical types (timestamp-millis, decimal) map to Talend Date/BigDecimal from 7.x; union with null = nullable |
| Parquet | Column names must match the Talend schema exactly (case sensitive by default, `spark.sql.caseSensitive`); nested structs/arrays appear as String (JSON) unless Dynamic + tSqlRow (8.0) flatten them; "Merge schema" on read via `spark.sql.parquet.mergeSchema=true` |
| ORC | Same as Parquet; Hive 3 ACID ORC files carry `operation`/`originalTransaction` columns Spark cannot read |
| Dynamic schema | Standard-only in 6.x/7.x; 8.0 adds Dynamic in Spark Batch for Parquet/Delimited input/output and tSqlRow (retrieving unknown columns, not creating tables) (partially unverified). Use "Edit schema" > type Dynamic as last column |
| Compression | Read: by extension/codec automatically. Write: tFileOutput* "Compress" (gzip not splittable; bz2/lz4/snappy via `spark.io.compression.codec`, Parquet default snappy) |
| Partition count | Input: HDFS block count (`spark.default.parallelism`, `mapreduce.input.fileinputformat.split.minsize`); shuffle: `spark.sql.shuffle.partitions` (200 default, set in Advanced properties); output files = partitions unless tPartition/coalesce |

## 12. Development and deployment workflow

1. Prototype in Local mode ("Use local mode" or Universal Local) against sample
   files on the local FS (no storage configuration component) or against the
   cluster FS via tHDFSConfiguration/tS3Configuration (Local Spark still reaches
   HDFS/S3 with the client jars). Windows needs `HADOOP_HOME` with
   `bin\winutils.exe` matching the Hadoop client version
   (`-Dhadoop.home.dir=C:\hadoop` in the Studio .ini) or every Local run fails
   with `NativeIO$Windows.access0` / "Could not locate executable winutils.exe".
2. Test Cases (Test Case view on a Spark job) wrap the job with tFixedFlowInput /
   tCollectAndCheck and run in Local mode under Maven (`mvn test` from CI Builder
   needs the Spark Universal modules present in the build agent's `.m2`).
3. Switch Spark Configuration to Repository metadata of the target cluster;
   run from Studio in Yarn client (classic) or Yarn cluster/Databricks/etc.
   (Universal) to validate against real data volume; tune with "Set Tuning
   properties" and `spark.sql.shuffle.partitions`.
4. Build: right-click Job > Build Job > Build type "Standalone Job" (zip with
   `lib/` incl. Spark client jars, `<job>_run.sh/.bat`, contexts, `jobInfo.properties`),
   or "Docker image" (8.0; Spark client jars in the image, Local/K8s/Databricks
   modes work from containers), or publish to Nexus/Artifact repository for TAC
   Job Conductor, or Publish to Cloud for TMC. CI Builder (`mvn
   org.talend.ci:builder-maven-plugin:<version>:generateAllPoms`) builds Spark
   jobs the same way as Standard ones (deployment-runtime.md) but the build
   agent must have the Big Data modules installed (`-Dtalend.studio.p2.update`
   / `-Dgenerate.bigdata`? see apis-sdks.md/deployment-runtime.md).
5. Deploy:
   - TAC: Job Conductor task (Spark Batch) or Big Data Streaming Conductor
     task (Streaming) on a JobServer that has network access to RM/Namenode (or
     to the Databricks/Dataproc/Synapse APIs), `krb5.conf` and keytabs, and for
     Yarn client enough RAM for the driver. JobServer host must resolve cluster
     hostnames (datanodes!) or set "Use datanode hostname".
   - TMC: promote the artifact, create a task; Big Data jobs run only on Remote
     Engines (not Cloud Engines) and the Remote Engine host plays the role of the
     driver/submitter (same prerequisites as JobServer). Remote Engine Gen2 is for
     Pipeline Designer, not Studio Spark jobs.
   - Context parameters (`--context_param spark_master=...`) can switch Spark
     Configuration fields exposed as context variables (Resource Manager, Namenode
     URI, Databricks cluster id, keytab path) between environments.
6. Operate: Spark UI/History Server, `yarn logs`, Databricks run pages; set
   "Define a streaming timeout" for streaming tasks that must end for a
   redeploy; checkpoint directory per environment and per job version.

CLI flags unique to Spark jobs: none in the launcher (`<job>_run.sh` only has
`--context`, `--context_param`, `--stat_port`, `--trace_port` like Standard);
all Spark settings are compiled in or driven by context variables. Studio
CommandLine (`executeJob`, `buildJob`) handles Spark jobs transparently.

## 13. Version matrix (Spark / Scala / platforms per release)

| Platform version | Spark | Talend selection |
|---|---|---|
| CDH 5.x (Spark 1.6 or CDS 2.x parcel) | 1.6 / 2.1-2.4 | built-in CDH 5.x (6.x-7.x) |
| CDH 6.1-6.3 | 2.4 | built-in CDH 6.x (7.2+), dynamic distribution |
| CDP 7.1.x Private Cloud Base | 2.4 (CDS 3.x parcel: 3.1/3.2) | built-in CDP 7.1 (8.0), Spark Universal 2.4.x / 3.1.x; CDP 7.1.9+ Universal only |
| CDP 7.2 Public Cloud, CDE | 3.x | Spark Universal Yarn cluster (CDP) or CDE mode |
| HDP 2.6 | 2.3 | built-in HDP 2.6 |
| HDP 3.1 | 2.3.2 (+ HWC) | built-in HDP 3.1 (7.2/7.3) |
| EMR 5.x | 2.4 | built-in EMR 5.29 (7.3/8.0) |
| EMR 6.3-6.5 (Hadoop 3.2.1) | 3.1 | Spark Universal 3.1.x |
| EMR 6.6-6.7 | 3.2 | Spark Universal 3.2.x |
| EMR 6.8-6.10 | 3.3 | Spark Universal 3.3.x |
| EMR 7.x (Hadoop 3.4.0) | 3.5 | Spark Universal 3.5.x |
| Dataproc 1.4 | 2.4 | built-in Dataproc 1.4 (7.x/8.0) |
| Dataproc 2.0 / 2.1 | 3.1 / 3.3 | Spark Universal Dataproc mode |
| Databricks 5.5 LTS | 2.4.3 | built-in Databricks 5.5 (7.3) |
| Databricks 7.3 LTS | 3.0.1 | built-in / Universal 3.0.x |
| Databricks 9.1 LTS | 3.1.2 | Universal 3.1.x |
| Databricks 10.4 LTS | 3.2.1 | Universal 3.2.x |
| Databricks 11.3 / 12.2 LTS | 3.3.0 / 3.3.2 | Universal 3.3.x |
| Databricks 13.3 LTS | 3.4.1 | Universal 3.4.x |
| Databricks 14.3 / 15.4 LTS | 3.5.0 | Universal 3.5.x |
| Databricks 17.x | 4.0 | Universal 4.x (R2026 pages list Databricks on Spark 4.x) |
| Azure Synapse Spark pools | 3.1 / 3.2 / 3.3 / 3.4 | Universal Synapse mode |
| HDInsight 3.6 / 4.0 | 2.3 / 2.4 | built-in HDInsight (Livy) (7.x/8.0) |
| Kubernetes (any) | 3.x | Universal Kubernetes mode |
| Spark Standalone | 3.x | Universal Standalone (cluster version must match) |

Scala: 2.11 for all Spark 2.x targets; 2.12 for Spark Universal 3.x; Spark 4.x is
Scala 2.13 (Databricks-only path). Java: Spark 2.4 -> Java 8; Spark 3.x -> Java
8/11 (3.3+ also 17). Studio 8 R2024-xx moved to Java 17 for Studio itself.

## Gotchas

| Symptom | Cause | Fix |
|---|---|---|
| `java.lang.NoSuchMethodError: com.google.common.base.Preconditions.checkArgument` or `Stopwatch` during Spark job start | Guava version clash between Talend/Hadoop client jars (11.x) and a connector needing Guava 20+ (Cassandra, ES, Google clients) | Shade/relocate the connector jar, use the connector version matching the distribution's Guava, or add `spark.driver.userClassPathFirst=true` / `spark.executor.userClassPathFirst=true` in Advanced properties (test carefully) |
| `java.lang.NoSuchMethodError ... com.fasterxml.jackson.databind.ObjectMapper` / `Scala module 2.x.x requires Jackson Databind version >= 2.x` | Jackson versions in job `lib/` differ from cluster Spark's | Align the Spark version in Spark Configuration with the cluster; remove extra Jackson jars pulled by tLibraryLoad; on Databricks pick the runtime matching the Universal version |
| `GSS initiate failed` / `No valid credentials provided (Mechanism level: Failed to find any Kerberos tgt)` | No ticket: keytab path wrong on the executing host, `krb5.conf` missing, wrong principal realm, clock skew, or AES-256 without JCE on old Java 8 | Use "Use a keytab to authenticate" with absolute path on the engine host; set `-Djava.security.krb5.conf`; `klist -kt` the keytab; sync NTP; verify with `-Dsun.security.krb5.debug=true` |
| `Server has invalid Kerberos principal: hdfs/host@REALM` | Principal field uses the Studio's resolved hostname or missing `_HOST` | Set Namenode principal exactly to `nn/_HOST@REALM` (or the `hdfs/_HOST` form the cluster uses) and let Hadoop substitute `_HOST`; ensure reverse DNS works |
| Timestamps in Parquet/Hive shifted by N hours after a Spark job | Driver/executors in different JVM zones; Talend `Date` interpreted as local time while Spark stores UTC; "Use local timezone for date" toggled inconsistently between writer and reader jobs | Set `spark.sql.session.timeZone=UTC` and `-Duser.timezone=UTC` via `spark.driver.extraJavaOptions`/`spark.executor.extraJavaOptions`; use the same "Use local timezone for date" setting for all jobs touching the table |
| Driver `java.lang.OutOfMemoryError: Java heap space` / `GC overhead limit exceeded` | tLogRow, tSample-less tTop on huge flows, "Merge result to single file", or tMap "Use replicated join" with a large lookup all `collect()` to the driver | Remove tLogRow in production, raise "Driver memory", coalesce with tPartition instead of merge, use a normal (shuffle) join for big lookups |
| Thousands of tiny `part-` files in HDFS/S3, slow Hive/Impala | Output partition count = input partitions or `spark.sql.shuffle.partitions` (200) per write; streaming writes per micro-batch | Add tPartition (Number of partitions) before the output, set `spark.sql.shuffle.partitions` lower, compact streaming output with a batch job, or write to Delta/Hive with periodic compaction |
| `No FileSystem for scheme: s3a` / `abfss` / `gs` | Missing `hadoop-aws`/`aws-java-sdk`, `hadoop-azure`, `gcs-connector` jars for the chosen Spark/Hadoop version, or no storage configuration component so the FS impl class is not registered | Drop tS3Configuration / tAzureFSConfiguration / tGSConfiguration in the Job; make sure the Spark Universal modules for that version are installed; add `spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem` only as a last resort |
| Databricks run fails with `java.lang.NoClassDefFoundError: scala/...` or Jobs API `INVALID_PARAMETER_VALUE` | Databricks runtime Spark version differs from the Spark Universal version selected (e.g. Universal 3.3.x against runtime 13.3 = Spark 3.4) or Scala 2.11 jars (7.x) against a Scala 2.12 runtime | Match runtime <-> Universal version using the table in section 13; redeploy jars (clear the DBFS dependencies folder) |
| Dynamic distribution wizard hangs at "retrieving configuration files" or 401 from `archive.cloudera.com` | Cloudera repositories require paywall credentials since 2021; Talend's default proxy cannot serve them | Configure your own Nexus proxy with Cloudera credentials in Project Settings > General > Artifact Proxy Setting ("Override default setup"), or stop using dynamic distributions: built-in CDP 7.x or Spark Universal |
| `Table or view not found` on a Hive managed table in CDP/HDP 3, or empty result / `Could not read footer` on ACID ORC | Hive 3 managed tables are transactional; plain Spark cannot read them | Use tHiveWarehouseConfiguration + tHiveWarehouseInput/Output (HWC), or create the table EXTERNAL / `transactional=false` |
| tMap job with a lookup runs fine locally but executors die with OOM on the cluster | "Use replicated join" broadcasting a multi-GB lookup to every executor | Untick replicated join (Spark does a shuffle join), raise "Executor memory"/overhead, or pre-filter the lookup |
| YARN kills containers: `Container killed by YARN for exceeding memory limits. X GB of Y GB physical memory used` or `virtual memory used` | Off-heap + overhead exceed `spark.executor.memory + memoryOverhead`; `yarn.nodemanager.vmem-check-enabled=true` on old Hadoop | Increase "Set executor memory overhead" (10 percent min 384 MB default), lower executor cores, or ask admins for `yarn.nodemanager.vmem-check-enabled=false` / raise `yarn.nodemanager.vmem-pmem-ratio` |
| Spark Universal mode dropdown missing entries, or run fails `ClassNotFoundException: org.apache.spark.SparkConf` in Studio 8 | Spark Universal modules for the chosen version not installed (Feature Manager / Install external modules), or offline Studio without the module zips | Help > Install Additional Packages / Feature Manager > install "Spark Universal 3.x"; for offline, mirror the update repository in Nexus and set it in Preferences > Talend > Update settings |
| Local mode on Windows: `Failed to locate the winutils binary in the hadoop binary path` / `UnsatisfiedLinkError: NativeIO$Windows.access0` | Hadoop client needs `winutils.exe` and `hadoop.dll` even for local FS | Install Hadoop bin matching the client version, set `HADOOP_HOME` or `-Dhadoop.home.dir` in `Talend-Studio-win-x86_64.ini`, add `%HADOOP_HOME%\bin` to PATH, restart Studio |
| tHiveInput `Table not found: mytable` though it exists in Hue | Query against `default` database, wrong metastore (hive-site.xml missing from the Hadoop configuration JAR), or Spark catalog in-memory instead of Hive | Set "Hive database", include `hive-site.xml` with `hive.metastore.uris` when importing the metadata, ensure tHiveConfiguration points to the thrift metastore |
| Streaming job restarts with `Checkpoint directory is not compatible` / `ClassNotFoundException` / old settings keep applying | Checkpoint directory reused after changing the job graph, Spark version or batch size: Spark restores the serialized DStream graph from the checkpoint | Use a new checkpoint directory per job version (context variable with version suffix), delete the old one deliberately |
| After deleting the checkpoint dir, Kafka consumer re-reads the topic from the beginning or skips to latest | Offsets live only in the checkpoint; "Starting offset" (From beginning / From latest) applies again on a fresh start | Choose the desired Starting offset before the restart; for exactly-once resumption keep the checkpoint or store offsets externally (Kafka group commit, tJavaRow to a DB) |
| `Permission denied: user=talend, access=WRITE, inode="/tmp/hadoop-yarn/staging"` or `/user/talend/.sparkStaging` | Staging dir not writable by the Kerberos principal/user, or "Set staging directory" points to a path the user does not own | Set staging directory to `/user/<user>` or ask admins to chmod; ensure HDFS home dir exists for the principal |
| Yarn client job hangs at "Submitting application" or executors cannot reach the driver (`Failed to connect to <ip>:<port>`) | Driver (Studio/engine) hostname resolves to an unreachable IP (VPN, multiple NICs, Docker) | Set "Define the driver hostname or IP address" to the reachable address, open the ephemeral driver ports or fix `spark.driver.port`/`spark.blockManager.port` in Advanced properties; prefer Yarn cluster |
| Datanode reads time out from Studio though Namenode works (`BlockMissingException` / `could not obtain block`) | Client receives datanode internal IPs (cloud, Docker, NAT) | Tick "Use datanode hostname" (`dfs.client.use.datanode.hostname=true`) and make hostnames resolvable (hosts file or DNS) |
| `java.io.IOException: Mkdirs failed to create /tmp/...` or job writes temp files to the Studio disk | Spark "scratch" directory default `/tmp` on Windows or not writable on the engine host | Set Spark scratch directory to a writable local path with free space (tens of GB for big jobs) |
| `Create` action on tFileOutput* fails with `FileAlreadyExistsException` | Spark refuses to write into an existing directory in Create mode | Use Action "Overwrite" or delete the folder with tHDFSDelete (Standard parent job) first; remember the output is a directory, not a file |
| Spark 3 job fails parsing dates: `SparkUpgradeException: You may get a different result due to the upgrading of Spark 3.0` | New Proleptic Gregorian calendar / DateTimeFormatter in Spark 3 | Add `spark.sql.legacy.timeParserPolicy=LEGACY` and `spark.sql.parquet.int96RebaseModeInRead=LEGACY` (or CORRECTED) in Advanced properties |
| tJDBCInput Spark reads a 100M-row table on one executor | No partitioning configured, so Spark JDBC does a single `SELECT` | Fill Partition column / Lower bound / Upper bound / Number of partitions, or push down a filtered query per run |
| TMC task for a Big Data job stays "Deploy failed" or no engine is eligible | Big Data jobs cannot run on Cloud Engines; the Remote Engine lacks the Hadoop config / network path / Java version | Assign a Remote Engine (or engine cluster) with cluster connectivity, `krb5.conf`, keytab and the required Java; check engine logs for the submit error |
| Sqoop "Use Java API" fails `Could not load db driver class` but Commandline mode works | JDBC driver jar not in the job's lib; Java API mode runs in the Talend JVM | Add the driver via tLibraryLoad / component "Driver JAR" field, or use Commandline mode with `--driver` and the jar in `$SQOOP_HOME/lib` |
| Dataproc/Synapse/CDE submit fails with 403 | Service account / AAD app / workload user lacks roles (Dataproc Editor + Storage Object Admin; Storage Blob Data Contributor; CDE user role) | Grant the roles on project/storage; for Synapse also link the app to ADLS Gen2 and the Spark pool |

## Sources

https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-11/defining-connection-details-spark-configuration
https://help.qlik.com/talend/en-US/studio-user-guide/8.0/defining-connection-details-spark-configuration
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-08/defining-connection-details-spark-configuration
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-04-and-earlier/running-job-via-spark-universal
https://help.qlik.com/talend/en-US/release-notes/8.0/r2023-03-studio-new-features-big-data
https://help.qlik.com/talend/ja-JP/studio-user-guide/8.0-R2026-09/spark
https://help.qlik.com/talend/fr-FR/studio-user-guide/8.0-R2026-04/spark-universal-support-for-hadoop-distributions-in-talend-studio
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2025-01/supported-cloud-big-data-platform-distribution-versions-for-talend-jobs
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-07/supported-cloud-big-data-platform-distribution-versions-for-talend-jobs
https://help.qlik.com/talend/en-US/studio-user-guide/8.0/supported-cloud-big-data-platform-distribution-versions-for-talend-jobs
https://help.qlik.com/talend/en-US/studio-user-guide/8.0/dynamic-distribution
https://help.qlik.com/talend/en-US/studio-user-guide/7.3/dynamic-distribution
https://help.qlik.com/talend/en-US/studio-user-guide/7.2/adding-latest-big-data-platform-dynamically
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-07/dynamic-support-for-hadoop-distributions-in-talend-studio
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-09/dynamic-support-for-hadoop-distributions-in-talend-studio
https://help.qlik.com/talend/en-US/release-notes/8.0/big-data-deprecated-and-removed-items
https://help.qlik.com/talend/en-US/release-notes/7.3/big-data-deprecated-and-removed-items
https://help.qlik.com/talend/en-US/release-notes/8.0/r2023-10-deprecated-and-removed-features-big-data
https://help.qlik.com/talend/en-US/release-notes/8.0/r2023-05-deprecated-and-removed-features-big-data
https://help.qlik.com/talend/en-US/release-notes/8.0/r2024-06-deprecated-and-removed-features-big-data
https://help.qlik.com/talend/en-US/components/8.0/processing/tsqlrow-properties-for-apache-spark-batch
https://help.qlik.com/talend/en-US/components/8.0/processing/tsqlrow-properties-for-apache-spark-streaming
https://help.qlik.com/talend/en-US/components/7.3/processing/tsqlrow-properties-for-apache-spark-batch
https://help.qlik.com/talend/en-US/components/8.0/processing/tcacheout-properties-for-apache-spark-batch
https://help.qlik.com/talend/en-US/components/8.0/processing/tcacheout-properties-for-apache-spark-streaming
https://help.qlik.com/talend/en-US/components/7.3/processing/tcacheout-properties-for-apache-spark-batch
https://help.qlik.com/talend/r/en-US/8.0/spark-batch/tuning-spark-for-apache-spark-batch-jobs-spark-batch-component
https://help.qlik.com/talend/r/en-US/7.3/spark-streaming/tuning-spark-for-apache-spark-streaming-jobs-spark-stream-component
https://help.qlik.com/talend/fr-FR/components/7.3/spark-batch/tuning-spark-for-apache-spark-batch-jobs-spark-batch-component
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-08/defining-standalone-connection-parameters-with-spark-universal
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2025-10/defining-standalone-connection-parameters-with-spark-universal
https://help.qlik.com/talend/en-US/components/8.0/hdfs/thdfsconfiguration-properties-for-apache-spark-streaming
https://help.qlik.com/talend/en-US/components/7.3/hdfs/thdfsconfiguration-properties-for-apache-spark-streaming
https://help.qlik.com/talend/en-US/components/7.2/hdfs/thdfsconfiguration-properties-for-apache-spark-batch
https://help.qlik.com/talend/en-US/components/7.3/parquet/tfileinputparquet-properties-for-apache-spark-batch
https://help.qlik.com/talend/en-US/components/8.0/positional/tfileinputpositional-properties-for-apache-spark-batch
https://help.qlik.com/talend/en-US/components/7.3/positional/tfilestreaminputpositional-properties-for-apache-spark-streaming
https://help.qlik.com/talend/en-US/components/8.0/avro/tavrostreaminput
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-12/defining-databricks-connection-parameters-with-spark-universal
https://help.qlik.com/talend/en-US/studio-user-guide/8.0/defining-databricks-connection-parameters-with-spark-universal
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2025-01/defining-databricks-connection-parameters-with-spark-universal
https://help.qlik.com/talend/en-US/components/7.3/spark-batch/defining-dataproc-connection-parameters-spark-batch-component-enter
https://help.qlik.com/talend/en-US/studio-user-guide/8.0/defining-dataproc-connection-parameters-with-spark-universal
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-05/defining-dataproc-connection-parameters-with-spark-universal
https://help.qlik.com/talend/en-US/studio-user-guide/8.0/defining-the-azure-synapse-analytics-connection-parameters-with-spark-universal
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-08/defining-the-azure-synapse-analytics-connection-parameters-with-spark-universal
https://help.qlik.com/talend/en-US/components/8.0/spark-batch/defining-the-azure-synapse-analytics-connection-parameters
https://spark.apache.org/docs/latest/rdd-programming-guide.html#rdd-persistence
