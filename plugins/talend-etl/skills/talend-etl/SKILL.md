---
name: talend-etl
description: >-
  Talend / Qlik Talend ETL specialist. Use when someone is building,
  debugging, explaining, reviewing, deploying or inheriting a job made of
  Talend components, even if "Talend" is never said - most users omit it. Any
  one of these signals means Talend: tXxx component names (tMap, tDBOutput,
  tDBSCD, tRESTClient, tDie, tPrejob/tPostjob), OnSubjobOk / OnComponentOk /
  Run if, context variables, globalMap, Joblets, routines, a "Standard job" or
  "Big Data batch / Spark job" in Studio, Open Studio or Big Data Platform
  7.x/8, *_0.1.item + .properties folders, Build Job zips, TAC, JobServer,
  TMC. Prefer this over generic debug, design, Spark or SQL skills, which lack
  Talend component semantics. Typical asks: SCD2/upsert/lookup designs, REST
  pagination loops into a DB, trigger and tDie/tPostjob behaviour, tMap join
  NullPointerExceptions, Spark job failures on EMR/Databricks, decoding an
  inherited job, scheduling, versions, licensing. Skip for dbt, Airflow,
  Camel, spark-submit or plain SQL with no Talend.
---

# Talend / Qlik Talend data integration

This skill is a knowledge base, not an automation harness: a lean index here,
deep detail in `references/`. **Read the reference that owns the topic before
answering anything non-trivial** - exact component settings, CLI flags, API
paths and version facts live there, not in this file.

> Verification status: every reference is **doc-derived** (help.qlik.com /
> help.talend.com search evidence, Talend GitHub and Maven Central) combined
> with model knowledge. Nothing has been exercised against a live Studio, TAC or
> TMC in this build. Facts marked `(unverified)` inside a reference are memory
> only. When exact labels matter, tell the user to confirm in the Studio
> Component view or the TMC Swagger UI for their release.

## Orientation (read first when the context is unclear)
1. **Which Talend?** Identify product + version before advising: Studio release
   (7.3.1 vs 8.0.1 R20xx-xx), Open Studio vs subscription, on-prem (TAC +
   JobServer / Talend Runtime) vs Talend Cloud (TMC + Remote Engine) vs Qlik
   Talend Cloud. `references/versions-licensing.md` has the timeline, EOL dates,
   Java/OS support and the Open Studio (TOS) sunset. Ask for `Help > About` or
   `jobInfo.properties` if the user does not know.
2. **Which job type?** Standard (Java, DI) vs Big Data Batch / Streaming (Spark)
   vs Route (Camel) vs Service (SOAP/REST). Component names overlap but
   semantics differ (`tMap` lookups, `tLogRow`, file components). Standard is
   the default assumption.
3. **Where does it run?** Studio run, standalone zip launcher, TAC Job
   Conductor on a JobServer, TMC task on a Cloud/Remote Engine, Talend Runtime
   (Karaf) for Routes/Services, Docker/Kubernetes, Spark cluster. Deployment
   semantics (context override, logging, return codes) live in
   `references/deployment-runtime.md`.

## Capability map (topic -> reference)
| Need | Read |
|---|---|
| Studio IDE: perspectives, repository tree, metadata wizards, Designer/Component/Run views, Job and Project settings, Preferences, Build Job dialog, test cases, debugging, Feature Manager, Git/remote projects, generated code location | `references/studio.md` |
| Database / File / Processing components with their Basic and Advanced settings, globalMap return variables, tDB* unified components, bulk loaders, SCD/CDC/ELT, schema data types, Dynamic schema | `references/components-core.md` |
| tMap join/lookup/match modes, Var table, filters, rejects; tXMLMap; tELTMap; expression language; context/globalMap access; system routines (TalendDate, StringHandling, Numeric, Relational, ...); user routines; type conversions; tJava/tJavaRow/tJavaFlex | `references/tmap-expressions.md` |
| Cloud (AWS/Azure/Google/Snowflake/Databricks), SaaS (Salesforce, NetSuite, Marketo, Workday, ServiceNow, SAP...), NoSQL, messaging (Kafka/JMS/MQ), Internet (FTP/REST/SOAP/mail), LDAP, Data Mapper, TCK vs javajet connectors, authentication patterns, license availability, deprecated connectors | `references/connectors-catalog.md` |
| Execution model (subjobs, triggers, iterate, Run if, tPrejob/tPostjob, return codes), Orchestration / Logs & Errors / Misc / System / Custom Code components, Stats & Logs and AMC, implicit context load, recovery checkpoints, parallelization | `references/orchestration-logging.md` |
| Spark batch/streaming jobs, Spark Configuration tab, Hadoop cluster metadata, distributions and Spark Universal, Hive/HBase/Kafka/Kinesis/HDFS components, Databricks/EMR/Dataproc/Synapse/Kubernetes, tSqlRow/tPartition/tCacheOut, ML components | `references/big-data-spark.md` |
| ESB: Camel Routes (c* components), SOAP Data Services (tESB*), REST services (tRESTRequest/Response/Client), Talend Runtime (Karaf), Service Locator / SAM / STS / IAM, microservices, API Designer / Tester / Portal | `references/esb-routes-services.md` |
| Build artifacts and zip layout, launcher flags (`--context`, `--context_param`, stat/trace ports), JVM/log4j2, JobServer, TAC (Job Conductor, execution plans, triggers, servers, Nexus), Talend Cloud TMC (workspaces, tasks, plans, engines, promotion, Connections/Resources), Docker/Kubernetes, CI Builder (Maven), environment promotion | `references/deployment-runtime.md` |
| TMC public API (`/tmc/v2.6`), TAC MetaServlet, Studio CommandLine, Talend Component Kit SDK, legacy javajet custom components, running exported jobs from Java (`runJob`, `runJobInTOS`), MDM/Data Stewardship/Data Prep/Data Catalog/API Tester APIs | `references/apis-sdks.md` |
| Syntax of `.item` / `.properties` / `.screenshot` XML, workspace and project layout, Jobscript, generated Java (reading stack traces), export zip, pom/assembly, OSGi bundle, Spring Boot microservice, context `.properties`, `.car`, Route/Service/Spark item variants, hand-editing and Git merge rules | `references/artifact-formats.md` |
| Data Quality profiling and DQ components (standardization, matching, survivorship, masking, validation), Data Stewardship, Data Preparation, Data Catalog / Inventory / Trust Score, MDM (data models, containers, triggers, processes, tMDM* components) | `references/data-quality-governance.md` |
| Product and version history, editions and license availability, Java/OS/Eclipse matrix, EOL dates, 5.x -> 6.x -> 7.x -> 8.0 migration deltas, monthly R-release changes, Qlik acquisition and Qlik Talend Cloud, documentation map | `references/versions-licensing.md` |
| Design patterns (incremental/CDC/SCD/upsert/bulk/ELT/lookups/file ingestion/API pagination/error handling/restartability/parallelism), performance tuning, troubleshooting index by error text, design-review scorecard, "explain this job" template | `references/patterns-gotchas.md` |

## Helper scripts (`scripts/`, Python 3 standard library only)
| Want to... | Run |
|---|---|
| Explain or review a job without Studio: contexts, components and key settings, links (row/lookup/reject/iterate/trigger), tMap internals, schemas, subjobs, heuristic review findings | `python3 scripts/inspect_job_item.py JOB_0.1.item --review` (`--format json\|dot`, `--all-params`) |
| Understand a Build Job export: launchers, main class, JVM args, default context, bundled contexts, jobInfo, drivers in `lib/`, run command | `python3 scripts/inspect_job_export.py JOB_0.1.zip` (zip or extracted dir; `--format json`, `--list`) |
| Call TAC's MetaServlet correctly (base64 + URL encoding) or decode a captured call | `python3 scripts/metaservlet.py --tac-url http://tac:8080/org.talend.administrator --user u --password-env TAC_PASS runTask --param taskId=12 --param mode=synchronous [--call]` |
| List/run/poll TMC tasks, plans and executions; task history, run-config, schedule; engines; any other path via `raw` | `TALEND_CLOUD_TOKEN=... python3 scripts/tmc_api.py --region eu tasks list --environment-id <id>`; `tasks run <id> --param K=V --wait`; `--dry-run` prints the request. Uses the current `/orchestration` and `/processing` families; `--legacy v2.6` rewrites to `/tmc/v2.6/...` |
| CI gate: links, required sections, ASCII, manifest agreement | `python3 scripts/check_docs.py` |

The inspectors are tested on `fixtures/LOAD_CUSTOMERS_0.1.item` (a Studio-8
shaped job: tPrejob/tDBConnection, tFileList iterate, tFileInputDelimited with
reject, tMap with inner-join lookup and Var table, tDBOutput upsert, commit,
tPostjob/tDBClose, tDie on error) and on a synthetic export. They parse what
Studio writes but have not been run on a customer export yet; if a real file
trips them, the XML vocabulary is documented in `references/artifact-formats.md`.
Unit tests: `python3 -m unittest -v tests/test_scripts.py`.

## Working conventions
- **Exact names.** Use Talend casing and labels exactly (`tFileInputDelimited`,
  `OnSubjobOk`, `Reload at each row`, `--context_param`). If a label is
  uncertain, say which reference row it comes from and whether it is marked
  `(unverified)`.
- **Expressions are Java.** Anything typed into a Talend field is a Java
  expression: string literals need double quotes (`"UTF-8"`, not `UTF-8`),
  context access is `context.NAME`, globalMap access is
  `((Type)globalMap.get("tComponent_1_KEY"))`. Primitive vs object nullability
  is the number one source of runtime NPEs - see `tmap-expressions.md`.
- **Separate design from deployment.** When a user describes a problem, work
  out whether it is a design issue (job logic), a packaging issue (build/export,
  libs, Java version) or an operations issue (TAC/TMC task, engine, context
  override). The troubleshooting index in `patterns-gotchas.md` is keyed by the
  error text and tells you which.
- **Never hard-code secrets or hosts** in advice: steer to context groups per
  environment, `Password` context type, TAC/TMC parameter override, keystore.
- **Spark and ESB differ.** Before answering about `tMap`, file components,
  `tLogRow` or logging in a Big Data or Route job, check the job type and read
  `big-data-spark.md` / `esb-routes-services.md` - behaviour differs from
  Standard jobs.
- **Version-qualify.** Say which Studio release or product line a statement
  applies to when the references show it changed (log4j 1 -> 2, Java 8 -> 11 ->
  17, SVN removal, Open Studio sunset, TAC vs TMC).

## Fast answers (one-liners you can give without opening a reference)
- Job returns 0 on success, 1 on an uncaught exception, the `tDie` code
  (default 4) when `tDie` fires; TAC/TMC treat non-zero as failed.
- `--context=PROD --context_param DB_HOST=db1` selects a context then overrides
  single parameters; all CLI values arrive as strings and are parsed to the
  declared type.
- `OnSubjobOk` fires when the whole subjob finishes; `OnComponentOk` fires when
  that one component's end code runs. Use `OnSubjobOk` to sequence subjobs.
- A lookup flow into `tMap` is a Main-flow component connected with a second
  `row` link; the dashed link means lookup. `Unique match` returns the last
  match, `First match` the first, `All matches` multiplies rows.
- `tHashOutput`/`tHashInput` share memory only inside one job execution; pass
  data to a child job via context, files, a DB, or `tBufferOutput` back to the
  parent.
- Talend Open Studio (TOS) is discontinued (downloads retired 31 January 2024);
  the last open-source Studio was 8.0.1 (January 2022). Subscription Studio 8
  continues with monthly R-releases (R2026-09 at the time of writing); Java 17
  has been mandatory since R2024-05 and Java 21 since R2026-06.
- In a job `.item`, a link's `lineStyle` is the `EConnectionType` ordinal:
  0 row/reject, 1 OnSubjobOk, 3 OnComponentOk, 4 OnSubjobError,
  5 OnComponentError, 6 RunIf, 7 Iterate, 8 lookup into tMap.
- TMC task executions (`GET /processing/executions/{id}`) end in `EXECUTION_SUCCESS`
  or `EXECUTION_FAILED`; plan executions use lower-case `execution_successful`.
  Compare case-insensitively and accept both spellings.

## Repository and conventions for this plugin
- `references/` are the source of truth; `SKILL.md` stays an index (< 500 lines).
- Every reference ends with a `Gotchas` table and a `Sources` list of the
  help.qlik.com / help.talend.com pages that back it.
- `scripts/check_docs.py` runs in CI and fails on broken links or missing
  sections; run it after editing any reference.
- Slash commands: `/talend-etl:inspect`, `/talend-etl:review`, `/talend-etl:tmc`
  (in `../../commands/`).
