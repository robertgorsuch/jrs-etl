---
description: Operate Talend Cloud Management Console (list/run tasks, poll executions) via the TMC API
---

Read `${CLAUDE_PLUGIN_ROOT}/skills/talend-etl/SKILL.md` and the TMC section of
`${CLAUDE_PLUGIN_ROOT}/skills/talend-etl/references/apis-sdks.md`.

Use `python3 "${CLAUDE_PLUGIN_ROOT}/skills/talend-etl/scripts/tmc_api.py"` for the
user's request. The token must come from the `TALEND_CLOUD_TOKEN` environment
variable (never paste it into the conversation or a file); the region from
`--region` or `TALEND_CLOUD_REGION`. Always do a `--dry-run` first and show the
request when the operation is a write (run, terminate, raw POST/PUT/DELETE), and
ask before executing writes against an environment whose name contains "prod".
Interpret execution statuses with the table in apis-sdks.md and, on failure, pull
`executions logs` and map the error with `references/patterns-gotchas.md`.
