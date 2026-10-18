---
description: Inspect a Talend job .item file or an exported job zip and explain it
---

Read `${CLAUDE_PLUGIN_ROOT}/skills/talend-etl/SKILL.md` first.

The user wants a Talend artifact explained or reviewed. Decide which helper applies:

- A `.item` file (job, joblet, route): run
  `python3 "${CLAUDE_PLUGIN_ROOT}/skills/talend-etl/scripts/inspect_job_item.py" <file> --review`
- An exported job zip or extracted build folder: run
  `python3 "${CLAUDE_PLUGIN_ROOT}/skills/talend-etl/scripts/inspect_job_export.py" <path>`

Then explain the output in plain language using the "How to explain a Talend job"
template in `references/patterns-gotchas.md`: inputs, outputs, transformations,
contexts and secrets, dependencies, how it runs, and the review findings with a
recommended fix for each WARN/ERROR. Pull component semantics from
`references/components-core.md` / `tmap-expressions.md` / `orchestration-logging.md`
when a setting needs explaining. If the user only wants a diagram, use `--format dot`.
