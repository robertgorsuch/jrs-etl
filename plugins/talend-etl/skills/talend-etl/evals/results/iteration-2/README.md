# talend-etl evals - iteration 2 (2026-10-18)

Same three prompts as iteration 1, re-run after the fixes from iteration 1
(TMC status strings, lookup-in-Iterate and batch-vs-upsert gotchas) and graded
against the strengthened assertion set (10 / 9 / 9 assertions). Layout as in
iteration 1; `review.html` includes iteration-1 outputs as the "previous"
column.

## Result

| | With skill | Without skill |
|---|---|---|
| Assertion pass rate | 100% (28/28) | 93% (26/28) |
| False factual claims (grader) | 1 | 2 |
| Mean time | 304 s | 240 s |
| Mean tokens | 138k | 75k |

Discriminating assertions this time:

- eval 2: PostgreSQL `Use cursor` needs Auto Commit off. The baseline enabled
  cursor streaming with auto-commit on; the skill run stated the dependency.
- eval 3: checking the Outline / Component view for the real type behind a
  globalMap value. The baseline never pointed at it.

False claims: the skill run described tSnowflakeOutput Upsert as per-batch JDBC
statements (the component stages files, COPYs into a temp table and MERGEs);
the baseline runs claimed `StringHandling.LEN/TRIM/UPCASE` are null-safe (they
throw on null) and combined auto-commit on with cursor streaming.

## Changes made from this iteration

- `references/connectors-catalog.md`: tSnowflakeOutput row now describes the
  stage + COPY + MERGE mechanism.
- `references/orchestration-logging.md`: context-file naming corrected to
  `<project>/<job>_<ver>/contexts/<ContextName>.properties` (it contradicted
  deployment-runtime.md).

## Still weak (candidates for iteration 3)

- eval 1 no longer discriminates: both configurations know the lookup,
  batch and implicit-context facts. Candidate positive checks the grader saw
  in only one answer: the PostgreSQL aborted-transaction trap (Die on error
  off + auto-commit off turns the final commit into a rollback), the silent
  drop on the `out_ok` email filter, the misleading `Load failed: null` tDie
  message.
- eval 2 #9 (status strings) passes vacuously unless the answer volunteers a
  constant; eval 3 #6 is a trivial negative. Add an assertion penalising
  wrong null-safety claims about built-in routines.
