# Description optimization run (2026-10-18)

`scripts/run_loop.py` from skill-creator, 20 trigger queries
(`../../trigger_eval.json`, 10 should-trigger / 10 near-miss negatives),
60/40 train/test split, 3 `claude -p` runs per query, model claude-fable-5-1,
5 improvement iterations. Artefacts: `report.html` (per-iteration table),
`results.json` (every description and per-query trigger counts), `loop.log`.

| Iteration | Train correct / 36 | Test correct / 24 | Precision |
|---|---|---|---|
| 1 (original) | 22 | 15 | 100% |
| 2 | 22 | 16 | 100% |
| 3 | 22 | 14 | 100% |
| 4 (applied) | 23 | 16 | 100% |
| 5 | 23 | 15 | 100% |

Iteration 4 was applied to the SKILL.md frontmatter (best held-out score,
ties broken by train score). The original description is preserved in
`results.json` under `original_description`.

Reading the numbers: precision stayed at 100% for every candidate, so none of
the near-miss negatives (dbt, plain Camel, JasperReports, Qlik Sense,
Informatica, plain JDBC, Kubernetes spark-submit, Snowflake MERGE) ever pulled
the skill in. Recall moved only from 22% to 28% across very different
wordings, and even unmistakable Talend prompts (tMap NullPointerException,
Build Job zip, TAC to TMC migration) triggered in at most one run of three.
That pattern means the wording is not the limiting factor: in headless
`claude -p` runs the model mostly answers Talend questions from its own
knowledge without consulting a skill. Interactive sessions and the slash
commands (`/talend-etl:inspect`, `/talend-etl:review`, `/talend-etl:tmc`)
are the reliable entry points; re-run the loop after harness changes to see
whether recall improves.
