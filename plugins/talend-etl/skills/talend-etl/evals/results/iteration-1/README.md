# talend-etl evals - iteration 1 (2026-10-18)

Three realistic prompts (see `../../evals.json`), each run once with the skill
and once without it (same model, fresh agents). Answers are in
`<eval>/<config>/answer.md`, grades in `grading.json`, timing in `timing.json`;
`benchmark.md` has the aggregate and `review.html` is the standalone reviewer
page (open it in a browser: Outputs tab to read each answer, Benchmark tab for
the numbers).

## Result

| | With skill | Without skill |
|---|---|---|
| Assertion pass rate | 100% (19/19) | 100% (19/19) |
| False factual claims found by the grader | 1 (TMC status string, now fixed in the reference) | 5 |
| Mean time | 342 s | 265 s |
| Mean tokens | 146k | 77k |

The original assertions did not discriminate: both configurations satisfied all
of them. The difference showed up in factual correctness, which the grader
recorded as claims:

- Without the skill: claimed the tMap lookup is loaded once per job although it
  sits inside an Iterate loop (eval 1); treated batch mode as effective for
  `Insert or update` (eval 1); used TAC "Simple trigger" vocabulary for a TMC
  schedule and combined PostgreSQL auto-commit ON with cursor streaming (eval 2);
  named exported context files `<job>_<ctx>.properties` (eval 3).
- With the skill: one error, inherited from `references/apis-sdks.md`, which
  said TMC task executions end in `EXECUTION_SUCCESSFUL`. A follow-up search
  of the Processing and Execution History Search API docs shows task executions
  use `EXECUTION_SUCCESS` and plan executions lower-case `execution_successful`.
  The reference, SKILL.md and `scripts/tmc_api.py` were corrected after this run.

## Changes made from this iteration

- `evals.json`: three discriminating assertions added per eval (lookup inside
  Iterate, batch vs Insert-or-update, implicit context load; TMC trigger
  vocabulary, auto-commit vs cursor, status strings; context file path, Outline
  view for globalMap types, wrong-context -> NPE link).
- `references/tmap-expressions.md` and `references/components-core.md`: gotcha
  rows for the two facts the baseline got wrong.
- `references/apis-sdks.md`, `SKILL.md`, `scripts/tmc_api.py`: status-string fix.

Next iteration should re-run the same prompts against the updated skill and
grade with the new assertions; the expectation is a measurable pass-rate delta.
