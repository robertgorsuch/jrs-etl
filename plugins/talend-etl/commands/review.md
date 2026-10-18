---
description: Design-review a Talend job (.item) against the talend-etl scorecard
---

Read `${CLAUDE_PLUGIN_ROOT}/skills/talend-etl/SKILL.md`, then
`${CLAUDE_PLUGIN_ROOT}/skills/talend-etl/references/patterns-gotchas.md`
(sections "Design review scorecard" and "Troubleshooting index").

Run `python3 "${CLAUDE_PLUGIN_ROOT}/skills/talend-etl/scripts/inspect_job_item.py" <file> --review --all-params`
on the job the user points at (ask for the path if none was given; look for `*.item`
under `process/` in the current directory first).

Produce a review with these sections: Summary (what the job does), Blocking issues,
Risks, Performance, Portability (contexts, secrets, paths), Operability (logging,
error handling, restartability), Suggested changes (ordered, each with the exact
component/setting to change). Cite the reference file that backs each non-obvious
recommendation. Do not invent settings that the component does not have; when
unsure, say so and point to the Studio Component view.
