# Deployment and runtime: build artifacts, launchers, JobServer, TAC, Talend Cloud (TMC), Docker/K8s, CI Builder

> Verification: doc-derived (help.qlik.com / help.talend.com search snippets, Talend GitHub, Maven Central) plus model knowledge. Not exercised against a live Studio/TAC/TMC in this build. Items marked (unverified) are from memory only and should be checked in Studio before relying on exact labels.

Scope: everything that happens to a Job/Route after Studio: building, packaging, launching, scheduling, promoting. HTTP/API contracts (TMC public API, TAC MetaServlet, Studio CommandLine) are owned by apis-sdks.md; file-format internals (.item, generated Java, pom.xml, log4j2.xml, context files) by artifact-formats.md; the Build dialog UI itself by studio.md. Version context: Studio/TAC/JobServer 7.3 and 8.0 (monthly R-releases), Talend Cloud "Cloud" docs (continuously released).

## Contents
- [1. Build artifacts](#1-build-artifacts)
  - [1.1 Standalone Job zip layout](#11-standalone-job-zip-layout)
  - [1.2 Launcher scripts](#12-launcher-scripts)
  - [1.3 jobInfo.properties](#13-jobinfoproperties)
  - [1.4 Build dialog options](#14-build-dialog-options)
  - [1.5 Other build types (OSGi, Microservice, Docker, Cloud, Nexus)](#15-other-build-types)
- [2. Running standalone](#2-running-standalone)
  - [2.1 Job arguments](#21-job-arguments)
  - [2.2 JVM arguments](#22-jvm-arguments)
  - [2.3 Exit codes, stdout/stderr, logging](#23-exit-codes-stdoutstderr-logging)
  - [2.4 Java version compatibility](#24-java-version-compatibility)
  - [2.5 Scheduling with cron / Task Scheduler, concurrency](#25-scheduling-with-cron--task-scheduler-concurrency)
- [3. Talend JobServer](#3-talend-jobserver)
- [4. Talend Administration Center (TAC)](#4-talend-administration-center-tac)
  - [4.1 Installation and configuration.properties](#41-installation-and-configurationproperties)
  - [4.2 Configuration page modules](#42-configuration-page-modules)
  - [4.3 Users, roles, projects](#43-users-roles-projects)
  - [4.4 Servers and virtual servers](#44-servers-and-virtual-servers)
  - [4.5 Job Conductor tasks](#45-job-conductor-tasks)
  - [4.6 Triggers](#46-triggers)
  - [4.7 Execution Plans](#47-execution-plans)
  - [4.8 Other conductors, monitoring, backup, HA, roadmap](#48-other-conductors-monitoring-backup-ha-roadmap)
- [5. Talend Cloud / Talend Management Console (TMC)](#5-talend-cloud--talend-management-console-tmc)
  - [5.1 Tenants, regions, workspaces, environments](#51-tenants-regions-workspaces-environments)
  - [5.2 Artifacts, tasks, plans, run profiles](#52-artifacts-tasks-plans-run-profiles)
  - [5.3 Engines: Cloud Engine, Remote Engine, Clusters, Gen2](#53-engines)
  - [5.4 Promotion, connections, resources](#54-promotion-connections-resources)
  - [5.5 Users, security, licensing, Qlik transition](#55-users-security-licensing-qlik-transition)
- [6. CI/CD with Talend CI Builder](#6-cicd-with-talend-ci-builder)
- [7. Docker and Kubernetes](#7-docker-and-kubernetes)
- [8. Environment promotion and configuration management](#8-environment-promotion-and-configuration-management)
- [Gotchas](#gotchas)
- [Sources](#sources)

## 1. Build artifacts

Studio: right-click Job in Repository > `Build Job` (7.x/8.0; older "Export Job"). `Build Type` drop-down (subscription editions): `Standalone Job`, `OSGi Bundle For ESB`, `Microservice` (Spring Boot), `Docker Image`, plus `Publish to Cloud` (Cloud-connected Studio, separate menu entry) and `Publish` to the artifact repository (TAC-connected Studio). Routes get `Build Route` with OSGi / Microservice / Docker variants (esb-routes-services.md). Big Data Spark Jobs build as Standalone Job too; the launcher runs the driver which submits to the cluster itself (no spark-submit wrapper is generated) - see big-data-spark.md.

### 1.1 Standalone Job zip layout

File name: `<JobName>_<major>.<minor>.zip` (for example `LoadCustomers_0.1.zip`). Layout as produced by Studio 7.3 / 8.0 with defaults (`Shell launcher: All`, `Context scripts` checked, `Items`/`Source files` unchecked):

```
LoadCustomers_0.1.zip
|-- jobInfo.properties                       # build metadata (section 1.3)
|-- lib/                                     # ALL jars shared by job + child jobs
|   |-- routines.jar                         # compiled project routines (+ beans in ESB builds)
|   |-- dom4j-*.jar, log4j-api-*.jar, log4j-core-*.jar, slf4j-*.jar
|   |-- talend_file_enhanced_*.jar, talendcsv-*.jar, ...   # Talend runtime helpers
|   |-- <jdbc drivers>.jar, <component libs>.jar
|   `-- classpath.jar                        # only when "Add classpath jar" preference is on (manifest-only jar)
`-- LoadCustomers/                           # one folder per Job (child jobs get sibling folders)
    |-- LoadCustomers_run.sh
    |-- LoadCustomers_run.bat
    |-- LoadCustomers_run.ps1                # PowerShell launcher, present in recent 8.0 R-releases (unverified exact release)
    |-- loadcustomers_0_1.jar                # the Job classes: <job_lowercase>_<ver with _>.jar
    |-- myproject/                           # <project_lowercase>/
    |   `-- loadcustomers_0_1/
    |       `-- contexts/
    |           |-- Default.properties       # one file per context when "Context scripts" is checked
    |           `-- PROD.properties
    |-- items/                               # only with "Items": <project>/process/LoadCustomers_0.1.item/.properties/.screenshot
    `-- src/                                 # only with "Source files": generated Java sources
```

Notes:
- Child Jobs (tRunJob) referenced by the parent are built into the same zip: their jar lands in the parent's folder (`childjob_0_1.jar`) and their contexts under `myproject/childjob_0_1/contexts/`. `Apply to children` in the dialog propagates the chosen context to them.
- Each context file is also packaged inside the job jar at the same path (`myproject/loadcustomers_0_1/contexts/Default.properties`), so the jar alone can start with its baked-in context. The extracted copy in the folder takes precedence because the folder precedes the jar on the classpath (`-cp .:$ROOT_PATH:...`), which is why editing `Default.properties` after extraction works.
- `log4j2.xml` (7.3+, log4j 1.x `log4j.xml` in 7.0-7.2) is packaged inside the job jar root; to override it externally, place a copy next to the launcher (classpath `.` and `$ROOT_PATH` come first) or pass `-Dlog4j2.configurationFile=file:/path/log4j2.xml`. Details of the file in artifact-formats.md.
- Project name is upper-cased in Studio (`MYPROJECT`) but lower-cased in package/folder names (`myproject`). Job class is `myproject.loadcustomers_0_1.LoadCustomers`.
- The `lib/` folder in 8.0 may also contain `<project>-routines`-style names when the project uses "Routine jars"/custom routine dependencies (unverified naming); the standard compiled routines jar is still referred to as `routines.jar` in the launcher.
- Spark/Big Data builds add a `lib/` set of hadoop/spark client jars and the launcher gains `-Dhadoop.home.dir` style properties; Big Data Jobs are compiled at Java 8 compliance even on Java 17 Studio (help.qlik.com "compatible java environments").

### 1.2 Launcher scripts

`<Job>_run.sh` (Studio 7.3/8.0, abbreviated jar list):

```sh
#!/bin/sh
cd `dirname $0`
ROOT_PATH=`pwd`
java -Dtalend.component.manager.m2.repository=$ROOT_PATH/../lib -Xms256M -Xmx1024M \
  -cp .:$ROOT_PATH:$ROOT_PATH/../lib/routines.jar:$ROOT_PATH/../lib/log4j-api-2.17.1.jar:$ROOT_PATH/../lib/dom4j-2.1.3.jar:...:$ROOT_PATH/loadcustomers_0_1.jar \
  myproject.loadcustomers_0_1.LoadCustomers --context=Default "$@"
```

`<Job>_run.bat`:

```bat
%~d0
cd %~dp0
java -Dtalend.component.manager.m2.repository="%cd%/../lib" -Xms256M -Xmx1024M -cp .;%cd%;%cd%\..\lib\routines.jar;...;%cd%\loadcustomers_0_1.jar myproject.loadcustomers_0_1.LoadCustomers  --context=Default %*
```

| Element | Meaning | Where it comes from |
|---|---|---|
| `-Xms256M -Xmx1024M` | default heap | Job view > `Run` > `Advanced settings` > `Use specific JVM arguments`; project default in `Window > Preferences > Talend > Run/Debug` |
| `-Dtalend.component.manager.m2.repository=../lib` | tells Component Kit (TCK) components where their jars live | always emitted since 7.1 when any TCK component is used; harmless otherwise |
| `-cp .:$ROOT_PATH:...` | folder first, then libs, then job jar | makes an extracted `contexts/*.properties` or `log4j2.xml` override the packaged copy |
| `--context=Default` | context selected in the Build dialog | can be overridden by appending `--context=PROD` (last wins) |
| `"$@"` / `%*` | forwards extra args (`--context_param ...`) | edit the script to hard-code params if the scheduler cannot pass args |
| `-Dfile.encoding`, `-Duser.timezone` | not emitted by default | add via JVM arguments in Studio before building, or edit launcher |

Windows "command line too long" (>8191 chars in cmd.exe) is a classic failure for Jobs with many jars: enable `Window > Preferences > Talend > Import/Export > Add classpath jar in exported jobs` (label approximate, unverified) so the launcher references one `classpath.jar` whose `META-INF/MANIFEST.MF` `Class-Path:` lists everything; or hand-edit the launcher to `-cp ".;%cd%;%cd%\..\lib\*;%cd%\loadcustomers_0_1.jar"` (Java 6+ wildcard expansion). help.qlik.com "building jobs" documents the classpath length problem.

### 1.3 jobInfo.properties

Written at the zip root (and in the Nexus artifact / Cloud artifact). Java properties format, `#Generated by Talend Studio` header. Keys observed in 7.3/8.0 builds:

| Key | Example | Notes |
|---|---|---|
| `job` | `LoadCustomers` | Job name |
| `jobVersion` | `0.1` | job version, not build number |
| `projectName` | `MYPROJECT` | technical (upper-case) project name |
| `contextName` | `Default` | context chosen in Build dialog; TAC/TMC read it as the default |
| `jobDefaultContext` | `Default` | Job's own default context (unverified key name) |
| `jobType` | `Standalone` | also `Microservice`, `OSGi` style values for other build types (unverified values) |
| `applicationType` | `DI` / `BD` | DI vs Big Data (unverified) |
| `date` | `2024-05-02T10\:15\:33+02\:00` | build timestamp |
| `commandlineVersion` | `8.0.1.20240115_1200` | Studio/CommandLine build id used to generate code |
| `addStatisticsCode` | `false` | whether stats/trace code (tStatCatcher, Studio stats port) was generated |
| `jobId` | `_kq4X8...` | Job UUID from the .properties item |
| `gitCommitId` / `branch` | sha / `main` | present when project is Git-managed (8.0; unverified key names) |

Use it in deployment scripts to assert version/context before launching (`grep '^jobVersion=' jobInfo.properties`). TMC uses it to display artifact version and default context; TAC Artifact tasks read it to map the Nexus artifact to a Job.

### 1.4 Build dialog options

| Option | Effect |
|---|---|
| `To archive file` | output path of the zip |
| `Select the Job version` | which repository version (`0.1`, `Latest`) to build |
| `Build Type` | `Standalone Job` / `OSGi Bundle For ESB` / `Microservice` / `Docker Image` |
| `Extract the zip file` | also unzips into the target directory (help.qlik.com "building jobs") |
| `Shell launcher` | `All` (.bat + .sh), `Unix` (.sh), `Windows` (.bat) |
| `Context scripts` + context list | export one or all context `.properties`; pick the context used in `--context=` |
| `Apply to children` | use the same context for tRunJob children |
| `Items` | include `.item/.properties` sources (re-importable in Studio only) |
| `Source files` | include generated Java under `src/` |
| `Java version` / compiler compliance | 8.0 R2023+: choose Java 8/11/17 (later 17/21) bytecode compliance; also at project level (`Project Settings > Build > Java version`, title per help.qlik.com "Setting up the Java version to build artifacts in Talend Studio"; exact label unverified) |
| `Export as Zip` / `Add classpath jar` | preference-level toggles (see 1.2) |
| `Log4j level` | emitted as `--log4jLevel` default when log4j is enabled in Project Settings |

### 1.5 Other build types

| Build type | Output | Run with | Notes |
|---|---|---|---|
| `OSGi Bundle For ESB` | `<Job>_<ver>.jar` with `META-INF/MANIFEST.MF` (`Bundle-SymbolicName: <Job>`, `Bundle-Version`), `OSGI-INF/blueprint/job.xml` (Routes: `route.xml`) | drop in Talend Runtime (Karaf) `deploy/` or `bundle:install`, or deploy via TAC ESB Conductor / TMC | Data Services and Routes only build this way or as Microservice/Docker. See esb-routes-services.md |
| `Microservice` | Spring Boot fat jar `<Job>_<ver>.jar` | `java -jar <Job>_<ver>.jar --server.port=8065 --spring.config.location=...` | Routes/Data Services; exposes actuator; context via `--context_param` still works for Jobs (unverified for Routes) |
| `Docker Image` | image `<registry>/<project_lower>/<job_lower>:<tag>` built with Jib (7.x) / JKube+Jib (8.0) | `docker run image --context=PROD --context_param k=v` | Dialog: `Docker Host` (`Local` or remote `tcp://host:2375`), `Image name` (no underscores allowed), `Image tag` (job version default; `latest` is ALWAYS also built), `Push image to registry` + `Registry/Username/Password`. Jib builds to a registry without a local daemon; building to a local daemon needs Docker Engine >= 20.10.21 (help.qlik.com "publishing job as docker image"). Base image 8.0: `eclipse-temurin:11` (`-Dtalend.docker.jdk`); 7.x used an OpenJDK 8 JRE image (unverified tag) |
| `Publish to Cloud` | artifact (zip + jobInfo.properties) uploaded to TMC workspace | create Task in TMC | Cloud-connected Studio only; version increments per publish; screenshot optional |
| `Publish` (artifact repository) | Maven artifact in Nexus 2/3 or Artifactory | TAC `Artifact task`, or CI | Dialog `Publish Job`: `Export type` (Standalone/OSGi/Microservice/Docker), `Group ID` default `org.example.<project_lower>`, `Artifact ID` = job name, `Publish version` `0.1-SNAPSHOT` -> `snapshots` repo, `0.1` -> `releases` repo; repository URL/credentials come from TAC `Configuration > Artifact repository` |

## 2. Running standalone

### 2.1 Job arguments

Arguments are parsed by the generated `main()`; unknown args are ignored silently. Order independent; later `--context` wins.

| Argument | Purpose | Status |
|---|---|---|
| `--context=<name>` | select context group (case-sensitive, must exist or job falls back to default context and may warn) | confirmed |
| `--context_param <name>=<value>` | override one context variable; repeatable; the whole pair is ONE argv element so quote it when the value has spaces: `--context_param "path=/data/in dir"`; `=` inside the value is kept (split on first `=` only) | confirmed (help.qlik.com, Saagie guide) |
| `--context_param <name>=enc:system.encryption.key.v1:<base64>` | encrypted value for `Password` typed context vars (7.3+/8.0); decrypted with the key from `-Dencryption.keys.file` or the default key baked in the job | partially (unverified exact prefix for all releases) |
| `--context_type=<name>` (unverified) | legacy alias of context | unverified |
| `--stat_port=<n>` | port on which the Job pushes runtime statistics (Studio "Statistics", TAC/TMC "Real time statistics"); `-1` or absent disables | confirmed in generated code |
| `--trace_port=<n>` | row-level trace port (Studio `Traces Debug`) | confirmed in generated code |
| `--client_host=<host>` | host receiving stats/trace (Studio/JobServer) | confirmed in generated code |
| `--father_pid=<id>`, `--root_pid=<id>`, `--pid=<id>` | process ids used by tRunJob and JobServer to correlate parent/child logs (`pid` is a random Talend id, not OS pid) | confirmed in generated code |
| `--log4jLevel=<TRACE|DEBUG|INFO|WARN|ERROR|FATAL|OFF>` | root logger level when `Project Settings > Log4j` is enabled; overrides log4j2.xml level | confirmed |
| `--watch` | print total elapsed time at job end ("Job ... ended at ... [exit code=0]") | confirmed |
| `--resuming_logs_dir_path=<dir>`, `--resuming_checkpoint_path=<file>` | Error recovery (recovery checkpoints) when run by JobServer/TAC "Resume" | confirmed in generated code; manual use unverified |
| `--parent_part_launcher=<...>` | internal, parent-job launcher info for Error recovery | unverified |
| `--context_file=<path>` | load a context properties file (unverified; prefer tContextLoad / Implicit Context Load) | unverified |

Passwords: `--context_param pwd=secret` appears in `ps -ef` and scheduler logs. Alternatives: `Implicit Context Load` from a file with restricted permissions, tContextLoad reading from a vault, environment variable read via `System.getenv()` in a tJava/tSetGlobalVar, or encrypted `enc:` values. Windows batch: `%*` forwards args; quote pairs with double quotes; escape `%` as `%%`, `^` for special chars, and never use `!` with delayed expansion on.

### 2.2 JVM arguments

Set at design time (`Run > Advanced settings > Use specific JVM arguments`, or project default) so they are emitted in the launchers and inherited by TAC/TMC defaults; or edit the launcher / TAC task `JVM parameters` / TMC `Run profile`.

| Argument | Use |
|---|---|
| `-Xms`/`-Xmx` | heap; defaults 256M/1024M. tMap lookups, tSortRow, tAggregateRow, tHash* are in-memory: size to data or switch to `Store temp data` options (patterns-gotchas.md) |
| `-XX:+UseG1GC` (11/17 default), `-XX:MaxMetaspaceSize=256m` | many generated classes with big Jobs; metaspace rarely needs tuning |
| `-Dfile.encoding=UTF-8` | JVM default charset; Java 18+ defaults to UTF-8 anyway, Java 8/11/17 use OS locale. Component `Encoding` fields override per component |
| `-Duser.timezone=UTC` | make `TalendDate`/`java.util.Date` parsing/formatting deterministic across servers; CRON triggers in TAC/TMC have their own time zone setting |
| `-Djava.security.krb5.conf=/etc/krb5.conf`, `-Djava.security.auth.login.config=jaas.conf`, `-Djavax.security.auth.useSubjectCredsOnly=false` | Kerberos (Hadoop, Kafka, MSSQL integrated auth) |
| `-Dlog4j2.configurationFile=file:/path/log4j2.xml` | external logging config (7.3+); 7.0-7.2: `-Dlog4j.configuration=file:...` |
| `-Dtalend.component.manager.m2.repository=<dir>` | TCK component jar lookup; already in launcher |
| `-Dencryption.keys.file=/secure/studio.keys` | key file (`system.encryption.key.v1=...`) to decrypt `enc:` values built with a custom key (8.0; unverified property name across releases) |
| `-Djavax.net.ssl.trustStore=... -Djavax.net.ssl.trustStorePassword=...` | custom CA for HTTPS/JDBC TLS |
| `-Dhttp.proxyHost/-Dhttps.proxyHost/-Dhttp.nonProxyHosts` | outbound proxy for tREST/tHttpRequest/cloud components |
| `--add-opens java.base/java.lang=ALL-UNNAMED` etc. | Java 17 modules; Studio 8.0 R2024+ emits the needed `--add-opens` into launchers for Big Data Jobs (help.qlik.com) |

### 2.3 Exit codes, stdout/stderr, logging

| Exit code | When |
|---|---|
| `0` | normal end (also when an error was caught by tLogCatcher/OnComponentError and the flow continued) |
| `1` | uncaught exception in a component (console shows `Exception in component tXxx_1 (Job)` then `Job LoadCustomers ended at ... [exit code=1]`) |
| `4` | tDie with default `Exit code`; tDie `Code` field sets any int (help.qlik.com "conventions for return codes"; community reports default 4) |
| child code | tRunJob with `Die on child error` checked: parent dies (exit 1 by default) when the child returns non-zero; the child's code is in `((Integer)globalMap.get("tRunJob_1_CHILD_RETURN_CODE"))`. tRunJob `Use an independent process to run subjob` spawns a new JVM and still propagates the code |
| `130`/`143` | SIGINT/SIGTERM from the OS or JobServer `Kill` |

Conventions (help.qlik.com "Best Practice: Conventions for Return Codes"): use tDie/tWarn with agreed codes; messages in `DIE_MESSAGES`/`WARN_MESSAGES` globals; a tLogCatcher that catches a tDie does NOT by itself produce a non-zero exit, end with tDie again or `System.exit(code)` in a final tJava.

Console: the Job writes stdout for tLogRow/System.out and stderr for stack traces and `[statistics]` lines (`--watch`). With Project Settings > Log4j enabled, log4j2 root goes to CONSOLE appender by default; add a RollingFile appender in `log4j2.xml` and reference it (artifact-formats.md has the file). TAC/JobServer capture both streams into per-execution log files; TMC captures them into task run logs (truncated for very large outputs; TMC logs are kept 30 days by default (unverified)).

### 2.4 Java version compatibility

| Studio | Studio runs on | Job bytecode (compliance) | Runtime for built jobs | Notes |
|---|---|---|---|---|
| 7.3.1 | Java 8 (11 supported for Studio since 7.3.1 patches) | Java 8 | Java 8 or 11 | JobServer 7.3: Java 8/11 |
| 8.0 (R2021-10 .. R2024) | Java 11 | Java 11 default; option for 8 (compat) and 17 (added ~R2023, unverified month) | Java 11 or 17 | DI Jobs built at 17 need JobServer/Remote Engine on 17 |
| 8.0 R2025-xx | Java 17 recommended; option to stay on Java 8/11 + Camel 3 supported only until 2025-08-31 (Qlik community post) | 11 or 17 | 11/17/21 | Remote Engine moved to Java 17 bundles |
| 8.0 R2026-06+ | Java 17 required for DI Jobs, Routes, Data Services | Java 17 or 21 compliance; Big Data Jobs stay Java 8 compliance with `--add-opens` | Java 17 or 21 | help.qlik.com "compatible java environments" |

Symptom of a mismatch: `java.lang.UnsupportedClassVersionError: ... has been compiled by a more recent version of the Java Runtime (class file version 55.0 / 61.0), this version ... only recognizes class file versions up to 52.0` (52 = Java 8, 55 = 11, 61 = 17, 65 = 21). Fix: run with a newer JRE (set `JAVA_HOME` and `PATH`, launcher uses whatever `java` resolves) or rebuild with lower compliance.

### 2.5 Scheduling with cron / Task Scheduler, concurrency

```cron
# /etc/cron.d/talend-loadcustomers  (set env explicitly; cron has a minimal PATH and no JAVA_HOME)
JAVA_HOME=/usr/lib/jvm/temurin-17
PATH=/usr/lib/jvm/temurin-17/bin:/usr/bin:/bin
15 2 * * * talend flock -n /var/lock/loadcustomers.lock /opt/talend/jobs/LoadCustomers/LoadCustomers_run.sh --context=PROD --context_param "run_date=$(date +\%F)" >> /var/log/talend/loadcustomers.log 2>&1
```
- `%` must be escaped as `\%` in crontab lines.
- `flock -n` prevents overlapping runs; the launcher itself does nothing to stop two copies of the same Job running (tHash/tBuffer are in-process so they do not clash, but file outputs, tFileList-based moves, temp dirs of tSortRow `Store temp data`, and tUniqRow disk cache will).
- Windows Task Scheduler: Program `cmd.exe`, Arguments `/c "C:\talend\jobs\LoadCustomers\LoadCustomers_run.bat --context=PROD --context_param ""path=D:\in dir"" >> C:\logs\lc.log 2>&1"`, `Start in` = the job folder (the .bat does `cd %~dp0` anyway). Run under a service account with a password (not "Run only when user is logged on") and give it write access to the job folder (TCK components write caches under `lib`).
- Relative paths in the Job resolve against the launcher's folder (`cd` in script), not the scheduler's cwd.
- Running the exported Job from your own Java code (`new LoadCustomers().runJobInTOS(args)` / `runJob(args)`) is covered in apis-sdks.md.

## 3. Talend JobServer

Standalone execution agent used by TAC (and embedded inside Remote Engine for TMC, and inside Talend Runtime/Karaf for ESB). Delivered as `Talend-JobServer-V<ver>.zip` (subscription download) and deprecated RPM (`/opt/talend/jobserver`).

```
Talend-JobServer-V8.0.1/
|-- start_rs.sh / stop_rs.sh / start_rs.bat / stop_rs.bat
|-- conf/
|   |-- TalendJobServer.properties
|   `-- log4j2.xml (jobserver logging; 7.x: log4j.xml)
|-- lib/  (org.talend.remote.jobserver.*.jar ...)
|-- jobs?/, agent/ (layout varies per release)
`-- TalendJobServersFiles/                   # created on first deploy
    |-- repository/<task_label_or_job>_<ver>/   # unzipped job folders delivered by TAC (zip is extracted here)
    |-- jobexecutions/logs/<job>_<ver>_<yyyyMMdd_HHmmss>_<execId>.log  (+ .err / .out variants)
    `-- jobexecutions/archive? , pid files    (unverified names)
```

`conf/TalendJobServer.properties` keys (full prefixes matter):

| Key | Default | Notes |
|---|---|---|
| `org.talend.remote.jobserver.server.TalendJobServer.COMMAND_SERVER_PORT` | `8000` | TAC sends run/kill/deploy commands here (community: changed in this file) |
| `org.talend.remote.jobserver.server.TalendJobServer.FILE_SERVER_PORT` | `8001` | TAC transfers job zips here (port confirmed in firewall allowlist; key name unverified) |
| `org.talend.remote.jobserver.server.TalendJobServer.MONITORING_PORT` | `8888` | JMX monitoring port used by TAC Servers page (CPU/RAM/disk) |
| `org.talend.remote.jobserver.server.TalendJobServer.ENABLE_MONITORING_PORT` | `true` | disable if not registered in TAC |
| `org.talend.remote.jobserver.server.TalendJobServer.PROCESS_MESSAGE_PORT` | `8555` | internal stats/trace relay port (unverified) |
| `org.talend.remote.jobserver.commons.config.JobServerConfiguration.ADMIN_USER` / `ADMIN_PASSWORD` | empty | when set, TAC server registration must use `Username/Password` (unverified key path) |
| `org.talend.remote.jobserver.commons.config.JobServerConfiguration.ROOT_PATH` / `UNARCHIVE_ZIP_FOLDER` | `./TalendJobServersFiles` | where jobs are unzipped (unverified exact key) |
| `org.talend.remote.jobserver.commons.config.JobServerConfiguration.EXECUTION_LOGS_DIRECTORY` | `./TalendJobServersFiles/jobexecutions/logs` | (unverified key) |
| `org.talend.remote.jobserver.commons.config.JobServerConfiguration.MAX_OLD_EXECUTIONS_LOGS` | `5` | per-job retention of log files (unverified) |
| `org.talend.remote.jobserver.server.use.ssl` / keystore keys | `false` | TLS between TAC and JobServer; same flag mirrored in TAC server registration `Use SSL` (unverified) |
| `org.talend.remote.jobserver.commons.config.JobServerConfiguration.JOB_KILL_TIMEOUT`? | | (unverified) |

Operations:
- Start: `./start_rs.sh` (foreground; background with `nohup ... &`), Windows `start_rs.bat`. JobServer JVM options are inside the start script (`-Xmx` for the server, not for jobs; jobs are separate JVMs launched with the task's `JVM parameters`).
- Stop: `./stop_rs.sh -w <seconds>` waits for running jobs (exit 2 if still running at timeout), `-f` forces (help.qlik.com "shutting down your jobserver gracefully").
- Windows service: no official service installer in recent zips; use NSSM / `sc create` wrapping `start_rs.bat` (community thread), or the 7.x `service/` wrapper scripts where present (unverified).
- Java: the server uses `JAVA_HOME`/`PATH` java; jobs use the same unless TAC task sets a different one via `JVM parameters` (no per-task java binary; the JobServer `start_rs.sh` java is used for jobs too).
- Ports/firewall: TAC -> JobServer 8000, 8001, 8888 inbound; Studio `Target Exec` remote run uses 8000/8001 and the Studio-side stats port back to Studio (`--client_host`). JobServer -> TAC no inbound requirement except AMC/logging DBs the job writes to.
- Studio remote run: `Run > Target Exec` lists JobServers registered in TAC for the project (`Servers` page with `Enabled for Studio? ` / "Use for Studio" (unverified label)); `Window > Preferences > Talend > Run/Debug > Remote` can also define ad hoc servers by host/ports in non-TAC Studio (unverified in 8.0).
- Not used by Talend Cloud: TMC uses Remote Engines (which embed the JobServer code; RE has its own `TalendJobServersFiles/`).

## 4. Talend Administration Center (TAC)

### 4.1 Installation and configuration.properties

- Web app `org.talend.administrator.war` (installer or manual), deployed into Tomcat 9 (TAC 7.3/8.0): `<install>/apache-tomcat/webapps/org.talend.administrator/`. URL `http://<host>:8080/org.talend.administrator`. Default login after DB init: `admin@company.com` / `admin` (change it).
- Admin DB: embedded H2 (`WEB-INF/database/talend_administrator`, file or `jdbc:h2:tcp://host:port/...` with `org.h2.tools.Server -tcp -tcpAllowOthers` for shared access) for evaluation; MySQL/MariaDB, PostgreSQL, Oracle, MS SQL Server for production. First-start wizard `Database configuration` writes `database.url`, `database.driver`, `database.username`, `database.password`.
- `WEB-INF/classes/configuration.properties` (help.qlik.com "updating parameters after configuration is finalized"):

| Key | Purpose |
|---|---|
| `configuration.admin.enable`, `configuration.securityadmin.enable`, `configuration.dbadmin.enable` | set `true` to reopen the Configuration / Security / DB config pages; TAC flips them to `false` after finalization; missing lines = finalized |
| `database.url` / `database.driver` / `database.username` / `database.password` | admin DB |
| `scheduler.conf.executionPlanThreadPoolSize` (7.3) / Quartz thread count in `quartz.properties` (8.0, default 20) | parallel plan tasks (25 default in 7.3) |
| `random.jobserver.selector=true` | random instead of best-rated JobServer in virtual servers |
| `virtual.server.load.balancing.synchronized=false` | many short parallel tasks; loses balancing guarantee |
| `scheduler.conf.jobLogsFolder`-style keys | some Job Conductor paths can be overridden here (unverified) |

8.0 also lets you edit the `configuration` table in the admin DB directly (help.qlik.com). Non-GUI install via `configuration.properties` prefilled plus `install.skipLicenseValidation`-style keys (help.qlik.com "configuring TAC in non GUI mode"; exact keys unverified).

### 4.2 Configuration page modules

| Module | Key fields |
|---|---|
| `Database` | admin DB (see above) |
| `License` | upload `.license` file (TAC 7.x/8.0 use token-based licenses: the license carries a number of Studio user tokens; TAC validates online or by offline validation token); `Online/Offline` validation and `Update` for renewals |
| `Job Conductor` | `Generated jobs folder` (where CommandLine output zips land), `Tasks logs folder`, `Timeout on unknown state (s)`, `Max number of parallel executions? ` (unverified) |
| `CommandLine` (7.x; 8.0 still for Normal tasks) | `Primary/Secondary CommandLine` host, `port` (default `8002`), `path`, `Use remote` |
| `Logging` | `Technical server` (Logstash host/port), Kibana URL, Elasticsearch; "Talend LogServer" bundle = ELK (ports: Elasticsearch 9200, Kibana 5601, Logstash 8057 for TAC/jobs (unverified)) |
| `Monitoring` | AMC database connection used by the `Monitoring > Activity Monitoring Console` page; `Audit` DB for Project Audit |
| `Artifact repository` | `Nexus 2` / `Nexus 3` / `Artifactory`; URL, user, password; repos `snapshots`, `releases`, and `talend-custom-libs-release/-snapshot` for custom jars shared with Studio |
| `Software update` | Talend update/patch repository (`Talend Update Site` URL or local Nexus `talend-update`), used by Studio to fetch monthly patches via TAC |
| `Svn` / `Git` | project SCM: Git providers (GitHub, GitLab, Bitbucket, Azure DevOps, generic Git over HTTPS/SSH); `Project authentication` (TAC credentials or per-user Studio credentials); branch/tag management in `Projects > Branches` |
| `Service Registry`, `Service Locator`, `Service Activity Monitoring` | ESB infrastructure endpoints (esb-routes-services.md) |
| `SSO` | SAML 2.0 IdP (Okta, ADFS, Azure AD...) metadata; `Kerberos` SSO (7.x); `LDAP` for user import/sync (bind DN, base DN, user filter, periodic sync) |
| `Dashboard`, `Drools`, `Talend Data Preparation`, `Data Stewardship`, `Data Catalog` | URLs of other servers so TAC can link/launch them |
| `Notification` | SMTP for `Notifications` (task failure/success emails per task or project) |

### 4.3 Users, roles, projects

- Users: `Login` (email), password or SSO/LDAP, `Type` = product family the user can use in Studio (`Data Integration/ESB`, `Data Management` (DQ/MDM), `Business Modeler`, etc.) and `Role(s)`: `Administrator`, `Operation manager` (Job Conductor/Servers), `Designer` (Studio), `Viewer`, `Auditor`, `Security administrator` (8.0; unverified). Roles gate menu visibility; project access is separate.
- `Projects`: `Add` (local or `Reference project` flag), `Storage` Git/SVN with repository URL and branch; `Project authorizations`: per user `Read`/`Read Write` on project and on branches (`Git branches` view lets you lock a branch for release). `Reference projects` share routines/metadata/jobs read-only into other projects.
- Studio login: `Manage connections` > `Connection` with `Remote` repository (`Talend Administration Center` URL `http://host:8080/org.talend.administrator`), user/password or SSO; Studio fetches the project list and token license from TAC. Project `Branch` selection at login (`main`/`master`, release branches, tags are read-only).
- `Locks`: TAC lists item locks held by Studio users; Admin can release.

### 4.4 Servers and virtual servers

`Servers` page: `Add` JobServer with `Label`, `Host`, `Command port 8000`, `File transfer port 8001`, `Monitoring port 8888`, `Username/Password` (if ADMIN_USER set), `Use SSL`, `Active`, `Use for Studio? ` (remote run target; label unverified), `Time zone`. Status shows up/down and CPU/RAM/disk from JMX.

`Virtual servers` (`Configuring virtual servers`, TAC 7.3/8.0): a named group of physical JobServers. At run time TAC picks the best rated server (rating 0-100 from `monitoring_client.properties` indicators: free disk, CPU, RAM bounds and weights); a Job already deployed on one server prefers that server; `random.jobserver.selector=true` for random; `virtual.server.load.balancing.synchronized=false` relaxes locking for many short tasks. The engine is historically called `Grid Conductor`. There is no documented "least used" rule.

### 4.5 Job Conductor tasks

Task kinds: `Normal task` (Job generated from the project by CommandLine, then deployed to JobServer), `Artifact task` (pre-built artifact pulled from Nexus/Artifactory: group/artifact/version; `Latest` resolves newest), `Big Data Streaming task` and `ESB` items live in their own conductors.

Task fields (Add/Edit panel; labels per TAC 7.3/8.0, minor variations):

| Field | Notes |
|---|---|
| `Label`, `Description`, `Active` | |
| `Project`, `Branch`, `Job`, `Version` | pick repository Job; `Version` = specific or `Latest` (uses the highest Job version at generation time) |
| `Context` | context group to run; `Apply context to children` propagates |
| `Regenerate Job on change` | re-run CommandLine generation automatically when the Job's source changed since last generation (works with `Latest`) |
| `Execution server` / `Virtual server` | physical JobServer or virtual group |
| `On unavailable JobServer` | `Wait`, `Recover`/`Reset task` style options (exact labels unverified) |
| `JVM parameters` | appended to the job JVM (`-Xmx4096m -Dfile.encoding=UTF-8`) |
| `Log4j level` | passed as `--log4jLevel` |
| `Statistics` | `Enable Statistics`/`Enable Trace` (real-time stats view) |
| `Timeout (s)` | kill after timeout (`Kill the Job when timeout is reached`, unverified label) |
| `Pause triggers on error` | stop the schedule after a failure until manually resumed |
| `Context parameters` tab | per-task override table (name/value, passwords masked); applied as `--context_param`; `Reset to default` restores values from the generated job (help.qlik.com "modifying context parameters for specific tasks") |
| `Notifications` | emails on `Error`/`Success`/`Timeout` |

Lifecycle and statuses (7.2/7.3: `Ready to generate` -> `Ready to deploy` -> `Ready to install`(ESB) -> `Ready to run`; running shows `Requesting run` -> `Running` -> back to `Ready to run`; `Incomplete configuration` when fields are missing; 8.0 lists `Ready to deploy / Ready to install / Ready to run / Incomplete configuration`). Toolbar actions: `Generate` (CommandLine builds the zip into `Generated jobs folder`), `Deploy` (zip pushed to the JobServer over port 8001 and unzipped under `TalendJobServersFiles/repository`), `Run` (immediate), `Kill`, `Pause triggers`/`Resume triggers`, `Recover`/`Resume` (restart a failed Job from its last recovery checkpoint when the Job has checkpoints defined on OnSubjobOk links and `Error recovery` is enabled), `Reset task`, `Duplicate`, `Logs` (per execution: stdout/stderr files from the JobServer, `Download`), `Error Recovery Management` page for checkpoint restarts (7.x).

`Execution history` (Monitoring) keeps start/end, trigger name, status, exit code, JobServer; `Task execution monitoring` shows real-time rows when statistics are enabled.

### 4.6 Triggers

| Trigger | Fields |
|---|---|
| `Simple trigger` | `Label`, `Start date/time`, `End date/time`, `Number of repetitions` (`Repeat count`, -1 = unlimited), `Time interval (s)`, `Time zone` (execution server's, web app's, or chosen zone with autocomplete) (help.qlik.com "how to add simple trigger onto task") |
| `CRON trigger` | Quartz expression built via a UI (`Minutes`, `Hours`, `Days of month`, `Months`, `Days of week`, `Years`) or typed; `Time zone`; example `0 15 2 ? * MON-FRI *` (Quartz has seconds field and `?`) |
| `File trigger` | `Folder path` (on the JobServer), `File mask` (regex/glob), `Polling interval`, `Timeout`; fires when a matching file appears/changes; `Delete file after run`? (unverified) |
| Multiple triggers | allowed per task; "first one checked runs first"; plan-level triggers exist too |

Time zone pitfalls: TAC web app zone vs JobServer zone vs DB; DST shifts cause a skipped or duplicated 02:xx run; choose an explicit zone (`UTC`) on each trigger.

### 4.7 Execution Plans

`Job Conductor > Execution Plan`: tree of tasks. Root node, then child nodes attached with `OnOk` (parent succeeded), `OnError` (parent failed), `After` (regardless). `Use parallel execution` on a parent lets N children run simultaneously (choose count 1..N or `MAX`); a task flagged parallel cannot have its own OnOk/OnError/After children (help.qlik.com 7.2/8.0 "planning execution of data integration jobs"). Plan statuses: `Ready to deploy / Ready to run / Deployed / Killed / Incomplete configuration`; result `Error` = parent failed and no child ran, `Warning` = parent failed but its OnError child succeeded. Plans have their own triggers and `Run`, `Kill`, `Pause`, `Resume` (resume restarts from the failed node). Parallelism cap 20 (quartz.properties, 8.0) / 25 (`scheduler.conf.executionPlanThreadPoolSize`, 7.3). Chaining plans: no native plan->plan dependency; use a final task that triggers another plan via MetaServlet `runTask`/`runExecutionPlan` (apis-sdks.md) or merge trees.

### 4.8 Other conductors, monitoring, backup, HA, roadmap

- `ESB Conductor`: deploy OSGi features/Data Services/Routes to Talend Runtime containers (`Ready to install`), `ESB Publisher` to Nexus; `Big Data Streaming Conductor` for Spark Streaming Jobs (7.x). See esb-routes-services.md / big-data-spark.md.
- `Monitoring`: `Execution history`, `Logging` (Kibana dashboards from Talend LogServer), `Activity Monitoring Console` (AMC tables `tlogcatcher`, `tstatcatcher`, `tflowmetercatcher`), `Realtime statistics`, `Data Stewardship`/`Data Preparation` links.
- `Audit` (Talend Project Audit): generates PDF reports of project quality metrics into the Audit DB (7.x; dropped in later 8.0? (unverified)).
- Backup: back up the admin DB (dump) plus `configuration.properties`, the license, and Git repositories; MetaServlet has no full backup command; `Settings > Backup/Restore` page exists for the H2/DB export in some versions (unverified). Rebuilding TAC = restore DB + same war version; tasks/servers/users live in the DB.
- HA: active/passive Tomcat nodes sharing one admin DB; only one scheduler instance active (Quartz clustering not supported, so the standby must not start triggers; use a load balancer health check and manual failover). JobServers can be clustered freely via virtual servers.
- Deprecations: TAC 8.0 removed the SVN+CommandLine-centric flows in favour of Git and Nexus artifact tasks (CommandLine is still needed for Normal task generation); Qlik positions Talend Cloud / Qlik Talend Cloud (TMC + Remote Engines) as the strategic deployment platform. As of the 2026 docs TAC 8.0 still receives monthly R-release patches; no hard EOL date surfaced in the material consulted (unverified).

TAC CLI/API: `metaServlet` (base64 JSON over HTTP, e.g. `runTask`, `getTaskStatus`, `associatePreGeneratedJob`) in apis-sdks.md.

## 5. Talend Cloud / Talend Management Console (TMC)

### 5.1 Tenants, regions, workspaces, environments

- Account = tenant (one per subscription), with apps: `Management Console`, `Data Inventory`, `Data Preparation`, `Data Stewardship`, `Pipeline Designer`, `API Designer`, `API Tester`, `Studio` download, `Data Catalog` (hosted separately). Non-DI apps in data-quality-governance.md / esb-routes-services.md.
- Regions and base URLs (region code in hostnames; API base `https://api.<region>.cloud.talend.com`, portal `https://<app>.<region>.cloud.talend.com`, TMC `https://tmc.<region>.cloud.talend.com`):

| Region | Code | Notes |
|---|---|---|
| AWS US East | `us` | `api.us.cloud.talend.com` |
| AWS EU (Frankfurt) | `eu` | |
| AWS APAC (Tokyo) | `ap` | |
| AWS US West (Oregon) | `us-west` | |
| Azure Australia | `au` | (unverified) |
| Azure US / other Azure | `at` | (unverified) |

- `Environments` (Management > Environments): `default` plus custom (`DEV`, `TEST`, `PROD`); each environment has `Workspaces`: `Personal` (one per user, auto-created) and shared workspaces (created by admins, with user/group permissions). Artifacts and tasks belong to a workspace; engines are assigned to environments; promotion copies between environments (5.4).
- Studio publishes to a workspace in a chosen environment (`Publish to Cloud` dialog: environment, workspace, `Publish screenshot`, version bump `Major/Minor`).

### 5.2 Artifacts, tasks, plans, run profiles

Artifact types: `Job` (DI/Big Data standalone), `Route`, `Data Service`, `Pipeline` (Pipeline Designer), `Preparation`, plus `Connections`, `Resources`, `Datasets`. Artifact page shows versions; a task pins a version or `Latest`? (TMC tasks store a specific artifact version and offer `Use latest version` toggle (unverified label)).

Task (`Management > Tasks and plans > Add task` or from artifact `Create task`):

| Section | Fields |
|---|---|
| `Artifact` | artifact + version, workspace, environment |
| `Parameters` | context parameters discovered from the artifact; set values, mark sensitive, or bind to `Connections`/`Resources`; `Advanced parameters` = raw JVM args (unverified) |
| `Processing` | `Engine`: `Cloud Engine`, `Cloud Engine for Design` (pipelines only), `Remote Engine`, `Remote Engine Cluster`; `Run profile` (Remote Engine only: JVM memory/args preset defined in `Management > Run profiles`, e.g. `-Xms1G -Xmx4G`); `Log level` (`Info/Warn/Error/Debug/Trace/Off`); `Timeout` (minutes); `Allow parallel run of this task` (Remote Engine: default up to 3 concurrent task runs per engine (help.qlik.com); turning it off takes effect after the current run) |
| `Schedule` | triggers: `Once`, `Daily`, `Weekly`, `Monthly`, `CRON` (Quartz-like 6-7 fields with time zone), `Webhook`; max 15 non-webhook triggers per task, spacing >= 5 minutes; a webhook excludes other triggers (copy the task to have both); each trigger has its own `Timeout` overriding the task's; `Pause` a schedule without deleting |
| `Webhook` | TMC generates an HTTPS endpoint under `https://api.<region>.cloud.talend.com/...` with a per-webhook token, optionally HMAC signature header; POST JSON body is exposed to the Job as the `resource_webhook_payload` style context/global (unverified names); at most 1 webhook per task |

Queueing: a task whose engine is busy waits in chronological order; a given task can be queued/pending/running at most 50 times per 60 minutes; engines heartbeat every 60 s. Run statuses: `Pending`, `Deploying`, `Running`, `Successful`, `Execution failed`, `Deploy failed`, `Terminated`/`Killed`, `Timeout`. Task run page: logs (download), context parameter snapshot, duration, engine. `Run now`, `Terminate`, `Pause`, `Resume`.

Plans (`Add plan`): steps containing one or more tasks; a step runs tasks in parallel; next step connected `On success`, `On failure` or `On any` (`Run always`); `Plan parameters` push a value into all tasks that share a context parameter name; plan-level triggers (same kinds), `Allow parallel run` (if not allowed, leave >= 1 minute between consecutive runs per docs), `Pause/Resume`, `Rerun from failed step`. Plans execute on the engines of their tasks.

### 5.3 Engines

| Engine | What | Limits / notes |
|---|---|---|
| `Cloud Engine` | Talend-hosted shared executor per environment (one or two per environment depending on subscription, unverified) | Cannot reach on-prem networks or local files; working dir ephemeral; limited concurrency (a few parallel tasks per engine, unverified number); outbound internet only; use for cloud-to-cloud Jobs |
| `Cloud Engine for Design` | runs Pipeline Designer previews/pipelines | Pipeline Designer only |
| `Remote Engine` (Gen1, Karaf-based) | customer-installed agent (`Talend-RemoteEngine-V2.x.y.zip`, Windows installer, Linux zip; Java 11 then 17 bundled/required per version) | Runs Jobs, and since RE 2.9+/2.11+ also Routes and Data Services as microservices (unverified version). Outbound HTTPS 443 only to `*.cloud.talend.com`; no inbound ports. Default 3 parallel tasks |
| `Remote Engine Cluster` | logical group of Remote Engines in one environment | load balancing + failover for tasks assigned to the cluster; all engines need identical local resources |
| `Remote Engine Gen2` | Docker/compose-based engine for Pipeline Designer pipelines (`remote-engine-gen2-*.zip`, AWS AMI / Azure Marketplace images) | `docker compose up -d`; pairing with pre-authorized key in `.env`/config; needs Docker CE + Compose, 8+ GB RAM (unverified) |

Remote Engine (Gen1) install and pairing:

```
Talend-RemoteEngine-V2.13.x/
|-- bin/trun (console), bin/start, bin/stop (Linux); trun.bat/start.bat/stop.bat (Windows)
|-- etc/preauthorized.key.cfg      # remote.engine.pre.authorized.key=<key>  remote.engine.name=<name>  remote.engine.description=
|-- etc/org.talend.remote.engine.cfg? / system.properties / org.ops4j.pax.url.mvn.cfg (proxy, repos)   (exact names unverified)
|-- etc/org.talend.ipaas.rt.jobserver.client.cfg   # job execution settings (parallel count, job JVM defaults)  (unverified key names)
|-- data/log/  (karaf.log, remote-engine logs)
`-- TalendJobServersFiles/  (deployed jobs + jobexecutions/logs, like JobServer)
```
1. TMC `Management > Engines > Add > Remote Engine` -> `Pre-authorized key` (visible on the engine detail page) or via API `POST /tmc/v2.6/runtimes/remote-engines` (`preAuthorizedKey` in response) - apis-sdks.md.
2. With the engine stopped, set the key and name in `etc/preauthorized.key.cfg`; start `bin/trun` (foreground) or `bin/start`; engine status becomes `Paired` and TMC shows version and availability. Alternative: web pairing page `https://localhost:8043/configuration` while running.
3. Re-pair: stop engine, clear stored engine id, delete `data/cache`/`data/tmp` and re-enter a new key (help.qlik.com "pairing a remote engine repairing recovery").
4. Proxy: configure HTTP proxy in `etc/system.properties` (`http.proxyHost/Port`, `https.proxy*`) and Maven `org.ops4j.pax.url.mvn.cfg` for artifact downloads (unverified file names).
5. Updates: TMC offers one-click `Update` of a paired engine to the latest patch version (RE 2.10+), or install a new zip and re-pair; engines older than the supported window show `Not supported`/`Update required` (unverified labels). Java 8 support ended for Remote Engine around v2.12 (2023); current engines bundle/require Java 17 (unverified).
6. Windows service: `bin/service.bat install` style wrapper (`Talend Remote Engine` service) (unverified); Linux: systemd unit calling `bin/start`/`bin/stop`.
7. Engine `Run profile`: JVM args for jobs launched by this engine (`-Xmx`, `-Dfile.encoding`); default heap for RE-launched jobs is the job launcher default (1024M) unless a run profile is set.

Firewall: outbound 443 to `https://api.<region>.cloud.talend.com`, `https://tmc.<region>...`, `*.cloud.talend.com` and the artifact store (S3-backed) hosts; plus access to your data sources. Engine `Availability`: `Available/Unavailable` based on heartbeat; tasks assigned to an unavailable engine sit `Pending` until it returns or time out.

### 5.4 Promotion, connections, resources

- `Management > Environments > Promotions` (promotion pipelines): define `Source environment -> Target environment`; execute a promotion of the whole environment or a scope (workspace, artifact, task, plan, connection, resource). Target items are matched by name and workspace; `Overwrite` vs keep target task parameters/engine is selectable per promotion (recent TMC offers `Keep existing target values` style option, unverified label). Promotion history shows success/failure per item. Engines are NOT promoted; a promoted task needs an engine assignment in the target.
- `Connections` (Management > Connections): typed connection objects (JDBC, S3, Salesforce...) with per-environment values; Studio metadata built with Cloud connections lets context parameters be bound to a TMC connection at task creation (`Use connection`). Values are stored encrypted in TMC and injected at run time.
- `Resources`: file resources (certificates, small reference files) uploaded to TMC and bound to a task parameter; downloaded to the engine at run time (size limited; Cloud Engine cannot read arbitrary local paths, so resources are the only file input there).

### 5.5 Users, security, licensing, Qlik transition

- `Users`, `Roles` (predefined: `Environment Administrator`, `Operator`, `Integration Developer`, `Security Administrator`, `Data Steward`, etc. and custom roles built from permissions), `Groups`; workspace-level permissions (`Author`, `Execute`, `View`, `Manage`).
- Auth: Talend IAM (`iam.<region>.cloud.talend.com`), `SSO` via SAML 2.0 IdP, `SCIM` provisioning (Okta/Azure AD), `Service accounts` (client credentials for automation, scoped by role) and `Personal Access Tokens` (PAT, per user, used by Studio CI `-Dcloud.token`, by API calls `Authorization: Bearer <PAT>`). API details in apis-sdks.md.
- `Audit logs` (Management Console > Audit): user/task/engine actions, exportable.
- Subscriptions: `Talend Cloud Data Integration`, `Big Data`, `API Services Platform`, `Data Management Platform`, `Data Fabric`; `Studio` seats and engine counts are license dimensions; Cloud Engine run hours may be metered (unverified).
- Qlik transition (2023-2026): Talend Cloud rebranded `Qlik Talend Cloud`; TMC and Remote Engines continue; Qlik Cloud gained `Qlik Talend Data Integration` (cloud-native pipelines) and the ability to surface Talend Studio artifacts/Remote Engines inside a Qlik Cloud tenant; Talend accounts can be linked to Qlik Cloud tenants for identity. Treat any specific migration dates/feature parity as (unverified); the help.qlik.com "Cloud" doc set remains the authority.

## 6. CI/CD with Talend CI Builder

Maven plugin `org.talend.ci:builder-maven-plugin` (CI Builder license required). Studio 7.1+ no longer needs a CommandLine install: the plugin fetches a P2 update site containing CommandLine + libraries at build time (`-Dupdatesite.path`, 7.2 used `-Dproduct.path` to a local Studio/CommandLine).

Prerequisites: Maven 3.6+ (3.8/3.9 for 8.0), JDK 11 (8.0) or 17 (8.0 R2024+/R2025+), license file (`-Dlicense.path`, may be a URL with `-Dlicense.remote.user/-Dlicense.remote.password`), P2 update site (Talend's hosted `https://update.talend.com/Studio/8/updates/<R-release>/` behind license credentials, or a local mirror/Nexus `talend-update` raw repo), Git checkout of the Studio project(s) (`<root>/<PROJECT>/process/...`), and `~/.m2/settings.xml` with a `<server>` entry for the Talend artifact repository the plugin downloads from (`https://talend-update.talend.com/nexus/content/repositories/...`; id/credentials from the license, unverified id) and your Nexus.

```sh
# 1. generate poms for every project under the checkout (mandatory first step; version must match Studio R-release line)
mvn org.talend.ci:builder-maven-plugin:8.0.X:generateAllPoms \
    -Dlicense.path=/opt/talend/license -Dupdatesite.path=https://update.talend.com/Studio/8/updates/R2025-06 \
    -Dgeneration.type=local   # (7.x: -Dproduct.path=/opt/Talend-CommandLine)

# 2. build + deploy to Nexus (-fae: fail at end, continue other modules)
mvn -fae deploy -Dlicense.path=... -Dupdatesite.path=... -Dgeneration.type=local \
    -DaltDeploymentRepository=releases::default::https://nexus:8081/repository/releases/ \
    -DskipTests

# 3. publish to Talend Cloud instead of Nexus
mvn -fae deploy -Dlicense.path=... -Dupdatesite.path=... -Dgeneration.type=local \
    -Dservice.url=https://api.us.cloud.talend.com/v1.1 -Dcloud.token=<PAT or service account token> \
    -Dcloud.publisher.environment=DEV -Dcloud.publisher.workspace=Shared -Dcloud.publisher.screenshot=true

# 4. docker images
mvn -fae deploy -Pdocker -Dtalend.docker.name=cicd4talend -Djkube.docker.push.registry=registry.example.com \
    -Djkube.docker.username=... -Djkube.docker.password=... -Dtalend.docker.jdk=eclipse-temurin:17 ...
```

| Option | Notes |
|---|---|
| `-Dlicense.path`, `-Dlicense.remote.user/password` | confirmed (help.qlik.com "cibuilder maven build options") |
| `-Dupdatesite.path` / `-Dtalend.studio.p2.update` / `-Dtalend.studio.p2.base` | P2 site; version must be >= project version or build fails `The Talend Commandline version X is older than project version` (community) |
| `-Dgeneration.type=local` | generate code in the build agent (vs remote CommandLine) |
| `-Dproduct.path` | 7.x local Studio/CommandLine |
| `-Dservice.url`, `-Dcloud.token`, `-Dcloud.publisher.environment/workspace/screenshot` | Cloud publisher (token param name from doc memory; `-Dcloud.token` not confirmed by snippet) |
| `-DaltDeploymentRepository=<id>::default::<url>` | Nexus target (snapshots vs releases depends on `-SNAPSHOT` in Job version pom) |
| `-Pdocker`, `-Dtalend.docker.name`, `-Djkube.docker.push.registry/username/password` (8.0) / `-Ddocker.push.registry` (7.2), `-Dtalend.docker.jdk` | Docker profile; properties overridable in the project parent pom |
| `-Ptest` / `mvn test` | runs Job test cases (Studio `Test Cases`) through Surefire; `-DskipTests` to skip; `-Dtalend.ci.test.*` flags (unverified) |
| `-pl <module path> -am` | build one Job module (`<PROJECT>/poms/jobs/process/<job>_<ver>`) with its dependencies (routines) |
| `-Dstudio.log.level=DEBUG`? , `-Dtalend.ci.workspace`? | diagnostics (unverified) |

Generated layout after `generateAllPoms`: `<root>/pom.xml` (aggregator), `<PROJECT>/poms/pom.xml` (project parent with profiles `docker`, `nexus`, `cloud-publisher`), `<PROJECT>/poms/code/routines/pom.xml`, `<PROJECT>/poms/jobs/process/<job>_<ver>/pom.xml` (one module per Job version; artifactId `<job>`, groupId `org.example.<project_lower>`, version `<ver>` or `<ver>-SNAPSHOT`), `<PROJECT>/poms/jobs/routes/...`, `.../services/...`. pom internals in artifact-formats.md. Regenerate poms whenever Jobs are added/renamed or after Studio upgrade (help.qlik.com "regenerate pom files").

Version alignment: plugin version `8.0.X` tracks the Studio monthly release (e.g. the plugin released with R2025-06 must build projects last saved by Studio R2025-06 or older; the P2 site must be the same or newer). 7.3 used `7.3.1`. The 7.3-to-8.0 project migration in CI needs a Studio migration first (community thread on pom upgrade errors).

Pipeline sketches (agent needs Maven, JDK, Git, license, network to update site):

```yaml
# GitHub Actions
- uses: actions/checkout@v4
- uses: actions/setup-java@v4
  with: { distribution: temurin, java-version: '17' }
- run: mvn -B org.talend.ci:builder-maven-plugin:${TALEND_CI_VERSION}:generateAllPoms -Dlicense.path=$LICENSE -Dupdatesite.path=$P2 -Dgeneration.type=local
- run: mvn -B -fae deploy -Dlicense.path=$LICENSE -Dupdatesite.path=$P2 -Dgeneration.type=local -Dservice.url=$TMC_API -Dcloud.token=${{ secrets.TMC_TOKEN }} -Dcloud.publisher.environment=DEV -Dcloud.publisher.workspace=CI -DskipTests
```
Jenkins/Azure DevOps/GitLab: same two `mvn` steps; cache `~/.m2` (the P2 install is extracted under the build workspace, 1-2 GB, cache it too). Publishing to TMC creates/updates artifacts only; create or update tasks and run them with the TMC API (apis-sdks.md) as a later stage (`POST /tmc/v2.6/executions`). The old `Talend Cloud Publisher` CLI (pre-7.1) is superseded by the Maven cloud publisher profile.

Branching: trunk/`main` + release branches in Git, one Studio project per repo; TAC `Regenerate Job on change` and `Version=Latest` pull from the task's configured branch; TMC gets versions from CI publishing, tasks pinned to artifact versions per environment. Tag the Git commit with the artifact version; `gitCommitId` in jobInfo.properties links back.

## 7. Docker and Kubernetes

Minimal Dockerfile around a built zip (when not using Studio/CI Docker build):

```dockerfile
FROM eclipse-temurin:17-jre
WORKDIR /opt/talend
COPY LoadCustomers_0.1.zip .
RUN apt-get update && apt-get install -y unzip && unzip LoadCustomers_0.1.zip && rm LoadCustomers_0.1.zip \
    && chmod +x LoadCustomers/LoadCustomers_run.sh
ENV TZ=UTC JAVA_TOOL_OPTIONS="-Dfile.encoding=UTF-8"
COPY log4j2-console.xml LoadCustomers/log4j2.xml       # console-only appender, overrides packaged copy
COPY entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
```
```sh
#!/bin/sh
# entrypoint.sh: map env vars to context params; extra args pass through
set -e
exec /opt/talend/LoadCustomers/LoadCustomers_run.sh --context="${TALEND_CONTEXT:-Default}" \
  --context_param "db_host=${DB_HOST}" --context_param "db_password=${DB_PASSWORD}" "$@"
```
Studio/CI-built images (Jib/JKube) contain the extracted job under `/talend` style path with the launcher as ENTRYPOINT, so `docker run image --context=PROD --context_param k=v` works directly; the image tag `latest` is always produced in addition to the custom tag (help.qlik.com). Image names must not contain underscores; Job names with `_` need `-Dtalend.docker.name`.

Kubernetes CronJob:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata: { name: loadcustomers }
spec:
  schedule: "15 2 * * *"
  timeZone: "Europe/Paris"           # k8s 1.27+
  concurrencyPolicy: Forbid          # no overlapping runs
  successfulJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 0                # Talend jobs are rarely idempotent; do not auto-retry blindly
      template:
        spec:
          restartPolicy: Never
          containers:
          - name: job
            image: registry.example.com/myproject/loadcustomers:0.1
            args: ["--context=PROD", "--context_param", "run_date=2024-05-02"]
            env:
            - { name: DB_HOST, value: db.prod.svc }
            - name: DB_PASSWORD
              valueFrom: { secretKeyRef: { name: talend-db, key: password } }
            - { name: JAVA_TOOL_OPTIONS, value: "-Xmx2g -Dfile.encoding=UTF-8 -Duser.timezone=UTC" }
            resources: { requests: { memory: 2.5Gi, cpu: "1" }, limits: { memory: 3Gi } }
            volumeMounts: [{ name: data, mountPath: /data }]
          volumes: [{ name: data, persistentVolumeClaim: { claimName: talend-data } }]
```
- Memory limit must exceed `-Xmx` + metaspace + off-heap (~512 MB) or the container is OOM-killed with exit 137 and no Java stack trace.
- Logs: force console appenders only; let the platform (Fluent Bit, CloudWatch) collect. Exit code of the launcher = Job exit code, so Kubernetes `Failed` status reflects tDie/exceptions.
- Remote Engine in containers: Talend ships Remote Engine Gen2 as compose images and (recent) a Remote Engine Gen1 container distribution/Helm chart (unverified availability); community images wrap the zip in a Dockerfile with the pre-authorized key injected via env/secret and `TalendJobServersFiles` + `data` on persistent volumes. Talend Runtime (Karaf) also runs in Docker for ESB (esb-routes-services.md).

## 8. Environment promotion and configuration management

| Mechanism | Where values live | Pros / cons |
|---|---|---|
| Context groups per environment (`DEV`/`TEST`/`PROD`) + `--context=` | inside the artifact | simple; secrets baked into the artifact; every change = rebuild |
| `--context_param` / TAC task `Context parameters` / TMC task `Parameters` | scheduler config | artifact immutable across environments; TAC/TMC store masked passwords; visible in process args when run manually |
| Implicit Context Load (Project Settings > Job Settings, or Job `Extra` tab) from file/DB with a `Default` context holding only the path/DSN | file or table per server | one artifact everywhere; needs the file deployed and secured; failure mode: missing file -> defaults silently used (`Print operations` helps) |
| tContextLoad from file/DB/vault component (tFileInputDelimited key=value) | same | explicit, visible in the Job design (patterns-gotchas.md) |
| TMC `Connections`/`Resources` bound to context params | TMC, per environment | promotion-friendly, encrypted; Studio Cloud connections required for seamless binding |
| Environment variables via `System.getenv()` in tJava/tSetGlobalVar or entrypoint mapping | container/OS | 12-factor friendly; needs a small code hook |
| Encrypted context values `enc:system.encryption.key.v1:...` | properties files / args | Studio 7.3+/8.0 `Password` type; key must match (`-Dencryption.keys.file`), otherwise garbage or decryption error |

Rules of thumb:
- Keep `jobInfo.properties` `contextName` equal to the context you intend as default; TAC/TMC preselect it, and a zip built with `--context=Default` baked in will run Default when the scheduler forgets to pass one.
- Version bump policy: increment the Job version (`m`/`M` in Studio) for each release; TAC `Version=Latest` + `Regenerate on change` for DEV only, pinned versions in PROD; TMC artifacts auto-increment on publish, tasks pin versions, promotion carries the pinned version.
- Rollback: TAC Artifact task -> change `Version` to the previous Nexus release and `Deploy`; TMC -> edit task, choose previous artifact version (`Restore`), or re-run the previous promotion; standalone -> keep previous extracted folder (`LoadCustomers_0.1` vs `_0.2`) and switch the scheduler path.
- TLS/keystores: ship CA bundles as TMC Resources or mounted secrets and reference by context param; never hard-code `javax.net.ssl.trustStore` paths that differ per host.
- Time zones: pin `-Duser.timezone` and trigger time zones explicitly; document both.

## Gotchas

| Symptom | Cause | Fix |
|---|---|---|
| `.bat` fails with `The input line is too long` / `The command line is too long` | cmd.exe 8191-char limit exceeded by the explicit jar list in `-cp` | enable `Add classpath jar` in Studio export preferences (manifest-only `classpath.jar`), or edit launcher to `-cp ".;%cd%;%cd%\..\lib\*;%cd%\<job>.jar"` |
| `--context_param` value truncated or wrong param set | pair passed as two argv elements (`--context_param k = v`) or value contains spaces/`;` unquoted | pass exactly `--context_param "k=v with spaces"`; `=` inside the value is fine (split on first `=`) |
| `UnsupportedClassVersionError ... class file version 55.0/61.0` | Job built with Java 11/17 compliance run on an older JRE | install matching JDK, set `JAVA_HOME`/`PATH` for the scheduler/JobServer, or rebuild with lower `Java version` |
| JobServer fails to start: `Address already in use: 8000` / TAC server shows down | another JobServer/Talend Runtime (whose embedded JobServer also uses 8000/8001) on the host | change `COMMAND_SERVER_PORT`/`FILE_SERVER_PORT`/`MONITORING_PORT` in `conf/TalendJobServer.properties` and in TAC `Servers` |
| TAC task stuck `Ready to deploy`/`Generation failed`/`Incomplete configuration` | CommandLine unreachable (port 8002), wrong `Generated jobs folder` permissions, Job version deleted, branch mismatch | check `Configuration > CommandLine`, CommandLine logs, regenerate; for Artifact tasks verify Nexus coordinates |
| TAC Artifact task `Cannot resolve artifact` | wrong repo (snapshot vs release), groupId not `org.example.<project_lower>`, Nexus credentials, Nexus 3 vs 2 setting | fix `Configuration > Artifact repository`, republish with correct `Publish version` |
| TMC Remote Engine `Not paired`/`Unavailable`; tasks stay `Pending` | key already consumed, engine clock skew, proxy blocks `*.cloud.talend.com`, engine process down, unsupported old version | re-pair with fresh key (stop, clear id/cache), fix proxy/443, sync NTP, update engine |
| Cloud Engine task `FileNotFoundException` for local path | Cloud Engine has no access to customer filesystems/networks | use Remote Engine, or TMC `Resources`/cloud storage components |
| Scheduled run fires at wrong hour or twice/skipped around DST | trigger time zone defaults to server/web app zone; DST transitions | set explicit zone (`UTC`) on TAC/TMC triggers and `-Duser.timezone` |
| Duplicate concurrent runs corrupt files | `Allow parallel run` on in TMC, overlapping cron without `flock`, K8s `concurrencyPolicy: Allow` | disable parallel run (after current run ends), `flock -n`, `concurrencyPolicy: Forbid` |
| log4j2.xml edits ignored | file edited in `lib`/wrong folder; packaged copy inside job jar wins when folder copy absent; `--log4jLevel` overrides level | put `log4j2.xml` in the job folder (classpath `.`), or `-Dlog4j2.configurationFile=file:...`; remove `--log4jLevel` |
| Docker image runs but `ClassNotFoundException: com.mysql.cj.jdbc.Driver` | driver jar excluded (Studio `Modules` not installed when building, or custom lib not in Nexus `talend-custom-libs`) | install module in Studio before build, or add jar to `lib/` and classpath; in CI ensure `talend-custom-libs-release` reachable |
| CI: `The Talend Commandline version X is older than project version` | P2 update site older than Studio that saved the project | point `-Dupdatesite.path`/`-Dtalend.studio.p2.update` at the matching or newer R-release; align plugin version |
| CI: `Could not resolve dependencies ... org.talend.libraries` / build hangs on download | no network to Talend update Nexus, missing `settings.xml` server credentials, Maven offline (`-o`) | configure proxy/mirror Nexus with Talend repos, correct server id/credentials, run online once to warm `~/.m2` |
| Accented characters garbled in files/DB when run from cron but fine in Studio | JVM default charset from OS locale (`POSIX` in cron) | `-Dfile.encoding=UTF-8` (or set component `Encoding`), `LANG=en_US.UTF-8` in cron env |
| `java.lang.OutOfMemoryError: Java heap space` in production only | launcher default `-Xmx1024M`; larger PROD volumes in tMap lookups/tSortRow | raise `-Xmx` via Studio JVM args before build, TAC `JVM parameters`, TMC `Run profile`; use `Store temp data`/`Reload at each row` |
| Remote Engine refuses to start / `UnsupportedClassVersionError` in karaf.log | engine version requires Java 11/17 but `JAVA_HOME` points to 8 | install required JDK, set `JAVA_HOME` in `bin/setenv` (unverified file) / service wrapper |
| Job runs with DEV values in PROD | `jobInfo.properties`/launcher `--context=Default` baked in; scheduler did not pass `--context`; TAC/TMC task context not changed after promotion | always pass `--context` explicitly; review task `Context`/`Parameters` after promotion |
| After TMC promotion, PROD task parameters/engine reverted to source values | promotion executed with overwrite of task configuration | re-promote with keep-target option, or restrict promotion scope to artifacts and reconfigure tasks; check promotion history |
| `enc:` password decrypts to garbage / `Decryption failed` on another server | encryption key differs between the Studio that built the artifact and the runtime | ship the same `encryption.keys.file`, or use TAC/TMC masked parameters instead of baked-in encrypted values |
| Parent Job exits 0 although child failed | tRunJob `Die on child error` unchecked and no check of `tRunJob_1_CHILD_RETURN_CODE` | check the option or add `OnComponentError`/tDie after tRunJob |
| Exit code 0 after tDie caught by tLogCatcher | tLogCatcher consumes the die event and flow continues | end with tDie again or `System.exit(code)` in a final tJava |
| Container killed exit 137 without Java error | cgroup memory limit below `-Xmx` + off-heap | set limits >= Xmx + 512M-1G; use `-XX:MaxRAMPercentage` instead of fixed `-Xmx` |
| TAC Execution Plan child never runs | parent flagged `Use parallel execution` (cannot have OnOk/OnError children) or plan thread pool exhausted | restructure tree; raise `executionPlanThreadPoolSize`/Quartz threads |

## Sources

https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-05/building-jobs
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2025-04/publishing-job-as-docker-image
https://help.qlik.com/talend/en-US/studio-user-guide/7.2/customizing-docker-images-build-settings
https://help.qlik.com/talend/en-US/installation-guide-linux/Cloud/compatible-java-environments
https://help.qlik.com/talend/en-US/installation-guide-windows/Cloud/compatible-java-environments
https://community.qlik.com/t5/Support-Updates/Talend-8-Java-amp-Camel-upgrade-coming-early-2025/ba-p/2492539
https://help.qlik.com/talend/en-US/conventions-for-return-codes/8.0/return-codes
https://help.qlik.com/talend/en-US/conventions-for-return-codes/8.0
https://community.qlik.com/t5/Talend-Studio/TOS-Exit-Codes/m-p/2358353/highlight/true
https://community.qlik.com/t5/Talend-Studio/How-to-force-return-code-at-the-end-of-the-job/m-p/2324369/highlight/true
https://community.qlik.com/t5/Talend-Studio/How-to-set-the-context-for-sub-jobs-through-command-line/m-p/2212530/highlight/true
https://help.qlik.com/talend/en-US/talend-glossary/Cloud/context-parameter
https://help.qlik.com/talend/en-US/administration-center-user-guide/7.3/modifying-context-parameters-for-specific-tasks
https://creativedata.atlassian.net/wiki/x/NQAvAw
https://dev.classmethod.jp/articles/talend-change-context-parameters/
https://help.qlik.com/talend/en-US/installation-guide-linux/8.0/configuring-jmx-monitoring-port-for-jobserver
https://help.qlik.com/talend/en-US/installation-guide-linux/7.3/proxy-and-firewall-allowlist-information
https://community.qlik.com/t5/Installing-and-Upgrading/INVALID-commandPort-or-FileTransferPort-is-misconfigured/m-p/2353141
https://community.qlik.com/t5/Talend-Studio/Configure-Job-Server-as-a-Windows-Service/td-p/2296961
https://help.qlik.com/talend/en-US/installation-guide-linux/8.0/directory-layout-of-talend-jobserver-rpm
https://help.qlik.com/talend/en-US/installation-guide-linux/8.0/shutting-down-your-jobserver-gracefully
https://help.qlik.com/talend/en-US/installation-guide-linux/7.3/cheatsheet-start-and-stop-commands-for-talend-server-modules
https://help.qlik.com/talend/en-US/patch-notes/8.0/tps-5389
https://community.qlik.com/t5/Talend-Studio/Jobserver-issue-setup/m-p/2289505/highlight/true
https://help.qlik.com/talend/en-US/installation-guide-linux/8.0/installing-your-talend-jobserver
https://help.qlik.com/talend/en-US/installation-guide-linux/7.3/config-server-load-balancing
https://help.qlik.com/talend/en-US/administration-center-user-guide/8.0/updating-parameters-after-configuration-is-finalized
https://help.qlik.com/talend/en-US/administration-center-user-guide/8.0/configuring-talend-administration-center-in-non-gui-mode
https://help.qlik.com/talend/en-US/installation-guide-linux/8.0/setting-up-h2-database-for-access-from-other-machines
https://help.qlik.com/talend/en-US/installation-guide-mac/7.3/configuring-h2-database-url
https://help.qlik.com/talend/en-US/administration-center-user-guide/8.0/accessing-execution-task-list
https://help.qlik.com/talend/en-US/administration-center-user-guide/7.3/accessing-execution-task-list
https://help.qlik.com/talend/en-US/administration-center-user-guide/7.3/generating-scripts
https://help.qlik.com/talend/en-US/administration-center-user-guide/8.0/running-jobs
https://help.qlik.com/talend/en-US/studio-getting-started-guide-data-integration/7.3/running-job-in-talend-administration-center
https://help.qlik.com/talend/en-US/administration-center-user-guide/8.0/accessing-execution-plan-page
https://help.qlik.com/talend/en-US/administration-center-user-guide/7.3/creating-running-or-resuming-execution-plan
https://help.qlik.com/talend/en-US/administration-center-user-guide/7.2/group-tasks-under-plan-based-on-onok-onerror-or-after-conditions
https://help.qlik.com/talend/en-US/administration-center-user-guide/8.0/planning-execution-of-data-integration-jobs
https://community.qlik.com/t5/Talend-Studio/Dependent-Execution-plan-trigger/td-p/2251390
https://help.qlik.com/talend/en-US/administration-center-user-guide/8.0/configuring-virtual-servers
https://help.qlik.com/talend/en-US/administration-center-user-guide/8.0/prerequisites-to-configuring-execution-servers
https://community.qlik.com/t5/Talend-Studio/Strategy-for-load-balancing/m-p/2363114/highlight/true
https://help.qlik.com/talend/en-US/administration-center-user-guide/8.0/how-to-add-simple-trigger-onto-task
https://help.qlik.com/talend/en-US/administration-center-user-guide/7.3/adding-triggers
https://help.qlik.com/talend/en-US/administration-center-user-guide/7.3/scheduling-task
https://help.qlik.com/talend/en-US/software-dev-lifecycle-best-practices-guide/8.0/cibuilder-maven-build-options
https://help.qlik.com/talend/en-US/software-dev-lifecycle-best-practices-guide/7.3/ci-mvn-options
https://help.qlik.com/talend/en-US/software-dev-lifecycle-best-practices-guide/8.0/regenerate-pom-files
https://help.qlik.com/talend/en-US/software-dev-lifecycle-best-practices-guide/8.0/deploying-project-artifacts
https://help.qlik.com/talend/en-US/software-dev-lifecycle-best-practices-guide/8.0/other-talend-maven-build-options
https://help.qlik.com/talend/en-US/software-dev-lifecycle-best-practices-guide/7.3/deploying-to-docker
https://help.qlik.com/talend/en-US/software-dev-lifecycle-best-practices-guide/7.2/talend-custom-maven-build-options
https://community.qlik.com/t5/Deployment/Issue-in-upgrade-talend-version-7-3-1-to-Talend-8-0-1-with-pom/m-p/2426788/highlight/true
https://help.qlik.com/talend/en-US/remote-engine-user-guide-linux/Cloud/pairing-a-remote-engine
https://help.qlik.com/talend/en-US/remote-engine-user-guide-linux/Cloud/pairing-remote-engines-with-configuration-file
https://help.qlik.com/talend/en-US/remote-engine-user-guide-linux/Cloud/creating-and-pairing-remote-engine-programmatically
https://help.qlik.com/talend/en-US/remote-engine-user-guide-windows/Cloud/pairing-a-remote-engine-repairing-recovery
https://help.qlik.com/talend/en-US/remote-engine-configuration-files-reference/Cloud
https://help.qlik.com/talend/en-US/remote-engine-user-guide-linux/Cloud/executing-job-tasks-on-remote-engine-or-cluster
https://help.qlik.com/talend/en-US/management-console-user-guide/Cloud/scheduling-job-tasks
https://help.qlik.com/talend/en-US/management-console-user-guide/Cloud/scheduling-plans
https://help.qlik.com/talend/en-US/archive-release-notes/8.0/r2022-07-talend-cloud-management-console
