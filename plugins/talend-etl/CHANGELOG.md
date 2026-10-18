# Changelog - talend-etl plugin

## 0.1.0 (2026-10-18) -- initial knowledge base

First release. A reference-library skill (lean `SKILL.md` index over deep
`references/*.md`) covering Talend / Qlik Talend end to end, plus four
stdlib-only Python helpers and three slash commands.

### References (doc-derived + model knowledge; not verified on a live install)
- `studio.md` - Talend Studio IDE, repository, job design concepts, metadata
  wizards, build/export, Feature Manager, project settings.
- `components-core.md` - Database / File / Processing families at parameter level.
- `tmap-expressions.md` - tMap, tXMLMap, tELTMap, expression language, system
  routines, globalMap/context semantics, data types.
- `connectors-catalog.md` - cloud, SaaS, business apps, NoSQL, messaging,
  internet and technical connectors; TCK vs javajet; auth patterns.
- `orchestration-logging.md` - execution model, triggers, Orchestration /
  Logs & Errors / Misc / System / Custom Code components, Stats & Logs, AMC.
- `big-data-spark.md` - Spark batch/streaming jobs, Hadoop ecosystem,
  Databricks/EMR/Dataproc/Synapse/Kubernetes, Spark Universal.
- `esb-routes-services.md` - Camel routes (c* components), SOAP/REST data
  services, Talend Runtime/Karaf, microservices, API Designer/Tester.
- `deployment-runtime.md` - build artifacts and launchers, CLI args, JobServer,
  TAC, Talend Cloud TMC/engines, Docker/Kubernetes, CI Builder, promotion.
- `apis-sdks.md` - TMC public API, TAC MetaServlet, Studio CommandLine,
  Component Kit SDK, legacy javajet components, run-from-Java, other REST APIs.
- `artifact-formats.md` - .item/.properties XML, workspace layout, Jobscript,
  generated Java, export zip, pom/assembly, OSGi/Spring Boot, context files.
- `data-quality-governance.md` - DQ profiling and components, Data Stewardship,
  Data Preparation, Data Catalog/Inventory, MDM.
- `versions-licensing.md` - product/edition/version history 5.x-8.0 R-releases,
  Java/OS support, EOL, Qlik era, migration deltas.
- `patterns-gotchas.md` - design patterns, performance tuning, troubleshooting
  index, review scorecard.

### Scripts (`skills/talend-etl/scripts/`, Python 3 stdlib, unit-tested offline)
- `inspect_job_item.py` - summarise a job `.item` (contexts, components, links,
  tMap internals, schemas) as markdown/JSON/dot, with `--review` heuristics.
- `inspect_job_export.py` - inspect a Build Job zip/folder: launchers, main
  class, JVM args, contexts, jobInfo, drivers; prints a run command.
- `metaservlet.py` - encode/decode/call TAC MetaServlet requests.
- `tmc_api.py` - Talend Cloud Management Console API client (tasks, plans,
  executions, engines, raw), `--dry-run` by design for writes.
- `check_docs.py` - CI consistency gate (links, required sections, ASCII,
  manifest agreement).

### Commands
- `/talend-etl:inspect`, `/talend-etl:review`, `/talend-etl:tmc`.

### Evals
- `skills/talend-etl/evals/evals.json`: three prompts (explain/review a job
  item, design an incremental PostgreSQL -> Snowflake load with TMC deployment,
  troubleshoot an exported job) with assertions.
- `evals/results/iteration-1/`: with-skill vs without-skill answers, grading,
  benchmark and a standalone `review.html`. Pass rates tied at 100%; the skill
  run made 1 factual error (fixed) against 5 for the baseline. See its README.
- `evals/results/iteration-2/`: re-run against the strengthened assertions
  after the iteration-1 fixes: skill 28/28 vs baseline 26/28, 1 vs 2 false
  claims. Two reference inconsistencies found by the grader were corrected.
- `evals/trigger_eval.json` + `evals/results/description-opt/`: 20-query
  trigger set and a 5-iteration description optimization run; the best
  held-out description (precision 100%, recall 33% test) is now the SKILL.md
  description. See that folder's README for why recall stays low in
  headless runs.
