# Orchestration, logging and execution semantics (Standard Jobs)

> Verification: doc-derived (help.qlik.com / help.talend.com search snippets, Talend GitHub, Maven Central) plus model knowledge. Not exercised against a live Studio/TAC/TMC in this build. Items marked (unverified) are from memory only and should be checked in Studio before relying on exact labels.

Scope: how a Standard (DI) Job executes, trigger/iterate link semantics, and the
Orchestration, Logs & Errors, Misc, System, Technical, Custom Code, Context and
Buffer component families, parameter-level. tMap/expressions/globalMap typing:
`tmap-expressions.md`. Build artifacts, launcher scripts, CLI flags, TAC/TMC:
`deployment-runtime.md`. Generated Java layout and log4j2.xml location:
`artifact-formats.md`. Spark/Big Data parallelism: `big-data-spark.md`.

## Contents

- [Execution model](#execution-model)
- [Trigger and iterate links](#trigger-and-iterate-links)
- [Return codes, errors and exceptions](#return-codes-errors-and-exceptions)
- [tPrejob / tPostjob guarantees](#tprejob--tpostjob-guarantees)
- [Orchestration family](#orchestration-family)
- [tRunJob in depth](#trunjob-in-depth)
- [Iteration components](#iteration-components)
- [Wait components](#wait-components)
- [Flow shaping and buffers](#flow-shaping-and-buffers)
- [tHashOutput / tHashInput](#thashoutput--thashinput)
- [Misc family](#misc-family)
- [Context components and Implicit Context Load](#context-components-and-implicit-context-load)
- [Custom Code family](#custom-code-family)
- [System and Technical families](#system-and-technical-families)
- [Logs & Errors family](#logs--errors-family)
- [Stats & Logs, AMC, log4j](#stats--logs-amc-log4j)
- [Resume and recovery checkpoints](#resume-and-recovery-checkpoints)
- [Parallelization](#parallelization)
- [Patterns](#patterns)
- [Gotchas](#gotchas)
- [Sources](#sources)

## Execution model

### Job = one Java class

| Fact | Detail |
| --- | --- |
| Class | One class per Job, `<project>.<jobname>_<major>_<minor>.<JobName>` implementing `TalendJob` (`routines.system.api.TalendJob`). Entry points: `main(String[])` -> `runJobInTOS(String[])` (returns int exit code); `runJob(String[])` returns `String[][]` (used by run-from-Java / tRunJob). |
| Context | Inner class `ContextProperties extends java.util.Properties` with one typed public field per context variable (`context.db_port` is `Integer`, not String). Values arrive as strings (`.properties`, `--context_param`, tContextLoad) and are parsed with `ParserUtils`. |
| globalMap | `java.util.Map<String,Object> globalMap = new java.util.HashMap<>()` per job instance. Every `tComponent_1_SOMETHING` lives here. With Job > Extra > Multi thread execution it is wrapped `Collections.synchronizedMap` (doc: "access to the globalMap object is synchronized"). Child jobs via tRunJob get their own globalMap. |
| Subjob | A coloured block in the designer = one generated method `tStartComponent_1Process(final Map<String,Object> globalMap) throws TalendException`. The start component is the one with no incoming Main/Lookup row; every subjob has exactly one. |
| Component code sections | Each component contributes three generated sections: begin (open resources, declare counters, start loops), main (per-row body), end (close, `globalMap.put("tX_1_NB_LINE", ...)`). Templates are `*_begin.javajet`, `*_main.javajet`, `*_end.javajet`. |
| Main row flow | Not pull-based. The input component's begin section opens a `while (reader.next())`-style loop; the main sections of every downstream component in the same subjob are nested inside the loop body in flow order; end sections run after the loop in flow order. A row object (`row1Struct row1`) is a single reused instance - do not keep references across rows. |
| Order inside a subjob | begin(input) -> begin(downstream components, flow order) -> loop { main(input) -> main(tMap) -> main(output) } -> end(input) -> end(tMap) -> end(output). `NB_LINE` style globals are therefore only valid after the subjob ends (OnSubjobOk), not inside the same subjob. |
| Order between subjobs | Trigger links decide. Subjobs with no incoming trigger are started one after another from `runJobInTOS` in an order chosen by the code generator (roughly creation order; not guaranteed and not the canvas position). Never rely on it: connect with OnSubjobOk or use Multi thread execution. |
| Per-subjob status | Each unlinked start is wrapped in `try { tX_1Process(globalMap); } catch (TalendException e) { globalMap.put("tX_1_SUBPROCESS_STATE", -1); e.printStackTrace(); }`. An error in one independent subjob does not stop other independent subjobs; it does set `status = "failure"` so the exit code is 1. |
| Job-level maps | `start_Hash`, `end_Hash` (component timings), `ok_Hash` (component success flags used by OnComponentOk/Run if), `execStat`/`runStat` (Studio Traces and Statistics ports `--stat_port`, `--trace_port`), `resumeUtil` (checkpoints), `errorCode`, `status`. |
| Command-line args parsed by the generated job | `--context=Name`, `--context_param key=value` (repeatable), `--father_pid=`, `--root_pid=`, `--pid=`, `--stat_port=`, `--trace_port=`, `--client_host=`, `--log4jLevel=`, `--resuming_logs_dir_path=`, `--resuming_checkpoint_path=`, `--parent_part_launcher=`. Details and launcher scripts: `deployment-runtime.md`. |

### Component kinds vs allowed links

| Kind | Examples | Incoming | Outgoing |
| --- | --- | --- | --- |
| Start / input | tFileInputDelimited, tDBInput, tFixedFlowInput, tRowGenerator, tFileList, tLoop, tForeach, tInfiniteLoop, tWaitFor*, tPrejob, tPostjob, tLogCatcher, tStatCatcher, tFlowMeterCatcher, tHashInput, tBufferInput, tJava, tJavaFlex | trigger only (OnSubjobOk, OnComponentOk, Run if, Iterate for inputs) | Main row (inputs) or Iterate (iterators) |
| Processing | tMap, tJavaRow, tFilterRow, tLogRow, tFlowMeter, tReplicate, tUnite, tSetGlobalVar, tFlowToIterate, tIterateToFlow | Main row | Main row / Iterate (tFlowToIterate only) / triggers |
| Output / end | tFileOutput*, tDBOutput, tBufferOutput, tHashOutput, tDie, tWarn, tSendMail | Main row or trigger (tDie/tWarn/tSendMail also accept triggers) | triggers only |
| Standalone action | tRunJob, tSystem, tSSH, tSleep, tMsgBox, tChronometerStart/Stop, tLibraryLoad, tSetKeystore, tSetProxy, tContextDump (output), tCreateTable | trigger or Iterate | trigger, Iterate (tRunJob also Main out) |

A component that "requires a start" (red error "component has no start") is a
processing component wired with nothing upstream on a Main row: give it an
input, or if it is meant to run once per iteration, wire the iterator with
Iterate to an input component (tFileInputDelimited), not directly to tMap.

## Trigger and iterate links

Right-click a component > Trigger > ... (or drag from the component's right
edge then pick). Triggers carry no data; they define order.

| Link | Fires when | Generated as | Use |
| --- | --- | --- | --- |
| OnSubjobOk | The whole subjob containing the source component ended without error (all end sections ran, all iterations done). Only legal from the start component of a subjob. | Call to the target `..Process()` placed after the source subjob's `end_Hash.put` inside the source method, guarded by no exception having been thrown. | Default sequencing link. Use it for anything that depends on `NB_LINE`, tHashOutput contents, closed files, committed connections. |
| OnSubjobError | The source subjob threw (Die on error exception, tDie, uncaught exception). | Call placed in the `catch (TalendException)` of the source subjob method. | Error branch: tSendMail, tDie, cleanup, logging to DB. Job exit code remains 1 unless you reset `errorCode` yourself (do not). |
| OnComponentOk | The source component's end section finished without error, immediately, before the rest of the subjob continues. Legal from any component. Chained OnComponentOk subjobs run "within the execution cycle of the previous subJob" (doc). | Call placed right after the component's end code, guarded by `ok_Hash`. | Notifications; starting a step as soon as one component is done. Dangerous on mid-flow components (see Gotchas). |
| OnComponentError | The source component raised an error. | Call in the component-level catch. | Per-component error handling. |
| Run if | Java boolean expression typed in the link's Component view > Basic settings > Condition, evaluated ONCE at the point where OnComponentOk/OnSubjobOk would fire (after the source component or subjob, depending on where you drew it from). | `if (<condition>) { tTarget_1Process(globalMap); }` | Branching: `((Integer)globalMap.get("tFileList_1_NB_FILE")) > 0`, `context.env.equals("prod")`, `"true".equals(globalMap.get("flag"))`. No `else`: draw a second Run if with the negated condition. |
| Iterate | Once per iteration produced by the source (tFileList, tLoop, tForeach, tFlowToIterate, tInfiniteLoop, tWaitFor*). The target subjob executes completely (begin/main/end) per iteration. | Target `..Process()` called inside the iterator's loop body. | Looping. Carrier is globalMap: `tFileList_1_CURRENT_FILEPATH`, `tLoop_1_CURRENT_VALUE`, `row1.col` from tFlowToIterate. Basic settings of the link: Enable parallel execution + Number of parallel executions. |
| Parallelize / Synchronize | Only from/to tParallelize (subscription). | Threads. | See Parallelization. |
| Main / Lookup / Reject / Filter / Output etc. | Row links (data). Not triggers. | Nested loop body. | `components-core.md`, `tmap-expressions.md`. |

Rules of thumb:
- Multiple triggers from one component are numbered; the label shows e.g.
  `OnSubjobOk (order:1)`, `(order:2)` and they fire in that order. Changing the
  order is done from the link's context menu / the source component's view
  (exact menu label unverified); deleting and recreating links also renumbers.
- A trigger drawn from a non-start component to a subjob is OnComponentOk
  semantics even if you later move things; check the label.
- Run if condition uses the globalMap state at the moment the trigger fires.
  If you draw it from a component whose `NB_LINE` is only set in its end
  section, draw from the subjob start with OnSubjobOk timing or test
  `ok_Hash`-independent values.
- Iterate target must be a start-capable component (input, tRunJob, tJava,
  tSystem, tFixedFlowInput...). Connecting Iterate into tMap is invalid.
- OnSubjobOk cannot be drawn from a component in the middle of a flow (Studio
  only offers OnComponentOk there).

## Return codes, errors and exceptions

| Situation | Exit code / effect |
| --- | --- |
| Normal end | `runJobInTOS` returns 0 (`status` != "failure", `errorCode` null). |
| Uncaught exception in a component with Die on error checked | Wrapped in `TalendException`, caught at subjob level, `status = "failure"`, `globalMap.put("tX_1_ERROR_MESSAGE", e.getMessage())`, stack trace on stderr as `Exception in component tX_1 (JobName)`. tLogCatcher (Catch Java Exception) receives it. Remaining components of that subjob are skipped; OnSubjobError branch runs; other independent subjobs still run; tPostjob runs. Exit code 1. |
| Die on error unchecked (components that offer it) | Exception swallowed per row/operation; `tX_1_ERROR_MESSAGE` set; rows go to the Reject link where one exists; job continues; exit code 0. tLogCatcher does NOT see it (nothing was thrown). |
| tDie | `errorCode = <Error code>` (default 4), `status = "failure"`, message to stderr and to tLogCatcher (Catch tDie). Job stops the current subjob chain; tPostjob still runs. Exit code = Error code. |
| tDie + Exit the JVM immediately | `System.exit(code)` right away: no tPostjob, no Stats & Logs flush beyond what already happened, no parent return in same-JVM tRunJob (parent dies too). |
| tDie Error code > 255 on Linux | Shell sees `code mod 256` (doc warns > 255 cannot be used). Keep codes 1..255. |
| Exception inside tRunJob child (same JVM), Die on child error checked | Child returns non-zero; parent tRunJob throws (`Child job running failed`), parent `errorCode` takes the child return code (approximately; verify), parent exit code non-zero. |
| Same but Die on child error unchecked | Parent continues, exit code 0 unless something else fails. Read `tRunJob_1_CHILD_RETURN_CODE`. |
| Independent process child | Parent reads the OS exit value of the `java` subprocess into `CHILD_RETURN_CODE`; `CHILD_EXCEPTION_STACKTRACE` not available (different JVM); child's stdout/stderr are piped to the parent console. |
| Final return | `errorCode != null ? errorCode : ("failure".equals(status) ? 1 : 0)`. The `.sh`/`.bat` launcher propagates it as the process exit code. |

Global error variables: `tX_1_ERROR_MESSAGE` (String, after a failure of tX_1
with Die on error unchecked, or after the catch when checked), `tDie_1_DIE_MESSAGES`,
`tDie_1_DIE_CODE`, `tDie_1_DIE_PRIORITY`, `tWarn_1_WARN_MESSAGES`, `tWarn_1_WARN_CODE`,
`tWarn_1_WARN_PRIORITY`, `tRunJob_1_CHILD_RETURN_CODE` (Integer),
`tRunJob_1_CHILD_EXCEPTION_STACKTRACE` (String), `tSystem_1_EXIT_VALUE`.

## tPrejob / tPostjob guarantees

```
tPrejob_1  --OnComponentOk-->  tDBConnection_1   (open shared resources, load context)
<main subjobs, linked by OnSubjobOk / Run if>
tPostjob_1 --OnComponentOk-->  tDBClose_1 / tDBCommit_1 / tFileDelete / tSendMail
```

| Rule | Detail |
| --- | --- |
| Ordering | tPrejob subjob is called first in `runJobInTOS`, before every other start component, regardless of canvas position. tPostjob is called last, after every main subjob method has returned (normally or via exception). |
| Error in tPrejob | The tPrejob chain stops; main subjobs STILL run (doc forum: "the other flow is still executed"). To abort the whole job from tPrejob you need tDie with Exit the JVM immediately, or put the main work behind an OnSubjobOk from a tPrejob-driven component instead of leaving it unlinked. |
| Error in main subjob | tPostjob runs anyway (exception is caught at subjob level). This is the place for connection close, temp-file cleanup, final audit row. |
| tDie | tPostjob runs after a normal tDie. It does not run after tDie with Exit the JVM immediately, after `System.exit()` in tJava, after OutOfMemoryError that kills the JVM, or after a TAC/TMC "kill". |
| Multiple tPrejob/tPostjob | Allowed (each is its own subjob); their relative order is generator-defined. Use one of each and chain with OnComponentOk. |
| Links from tPrejob/tPostjob | Only OnComponentOk/OnComponentError (they are single components, not flows). Do not draw OnSubjobOk from tPrejob to the main flow; the main flow should start on its own. |
| Child jobs | A child's tPostjob runs inside the child; it does not propagate errors to the parent (forum complaint). Parent decides via CHILD_RETURN_CODE. |
| Stats & Logs | Job-level "begin" stat is written before tPrejob; "end" after tPostjob. |

## Orchestration family

| Component | Purpose | Key settings | Notes |
| --- | --- | --- | --- |
| tPrejob | Marks the subjob that runs first | none | Connect with OnComponentOk. |
| tPostjob | Marks the subjob that runs last | none | Runs after failures too (see above). |
| tRunJob | Call another Job (child) | Use dynamic job; Context job; Job; Version (Latest or fixed); Context (child context group); Use an independent process to run subjob; Die on child error; Transmit whole context; Context Param table; Copy Child Job Schema; Adv: Print Parameters, Propagate the child result to the output schema, JVM Setting (Use specific JVM arguments), tStatCatcher Statistics | See dedicated section. |
| tLoop | Counted or while loop | Loop Type: For (From, To, Step, Values are increasing) / While (Declaration, Condition, Iteration) | Start component, Iterate out only. `tLoop_1_CURRENT_VALUE` (Integer, For only), `tLoop_1_CURRENT_ITERATION` (Integer). While example: Declaration `int i = 0`, Condition `i < 10`, Iteration `i++`. |
| tForeach | Iterate over a literal list | Values table (one Value expression per row) | `tForeach_1_CURRENT_VALUE` (String). Values are Java String expressions (`"a"`, `context.tbl`). `CURRENT_ITERATION` (unverified). |
| tInfiniteLoop | Poll forever | Wait at each iteration (in milliseconds) | `tInfiniteLoop_1_CURRENT_ITERATION`. Stop only by killing the job or tDie; pair with Run if + tDie on a stop condition. |
| tSleep | Pause | Pause (in seconds) | Accepts trigger or Iterate in; trigger out. |
| tWaitForFile | Poll a directory for created/deleted/updated files | Time (in seconds) between iterations; Max. iterations (empty = infinite); Directory; File mask; Trigger action when a file is: created / deleted / updated / combinations; Then: continue loop / exit loop; Include present file; Case sensitive (unverified) | Iterate out, one iteration per detected file event. `tWaitForFile_1_PRESENT_FILE` (full path+name), `FILENAME`, `FILE_DIRECTORY`, `CURRENT_ITERATION` (names other than PRESENT_FILE/CURRENT_ITERATION unverified). Detection is by directory listing diff each tick: a file still being written is "created" on first sight (see Gotchas). |
| tWaitForSqlData | Poll a table until a row-count condition holds | Component list / connection (Use an existing connection); Wait at each iteration (in seconds); Max. iterations; Table to scan; Where clause; Trigger action when rowcount is: equal to / greater than / lower than ...; Value; Then: continue loop / exit loop | Iterate out. Row count exposed as a global (name approximately `tWaitForSqlData_1_ROW_COUNT`, unverified). |
| tWaitForSocket | Block until a TCP client connects | Port; Max. iterations / timeout (labels unverified) | Iterate out; rarely used. |
| tParallelize | Run several subjobs concurrently and synchronize | Wait for: end of first subjob / end of all subjobs; Sleep Duration (ms in 8.0 docs, s in 7.3 docs); Die when one of parallelize subjobs fails | Subscription only. Links: Trigger > Parallelize (to each branch), Trigger > Synchronize (to the waiting subjob). Branches must be independent; globalMap writes from branches race. |
| tReplicate | Fan one Main flow out to N Main flows | schema only | Each output gets a copy of the row struct. Downstream subjob branches run inside the same loop body (same subjob). |
| tUnite | Concatenate several Main flows with identical schema | schema | Input flows are processed sequentially (flow 1 fully, then flow 2 ...), not interleaved. `tUnite_1_NB_LINE`. All inputs belong to the same subjob. |
| tFlowToIterate | Turn each row into one iteration | Use the default (key, value) in global variables (default: keys `row1.col1`, `row1.col2`...); or customize table Key / Value (pick a column) | Iterate out. `tFlowToIterate_1_CURRENT_ITERATION`. Read in target: `((String)globalMap.get("row1.filename"))`, `((Integer)globalMap.get("row1.id"))` - the cast must match the column class. |
| tIterateToFlow | Turn iterations into rows | Mapping table: Column (schema column) / Value (expression, Ctrl+Space for globals) | Iterate in, Main out. Downstream components begin once before the first iteration and end once after the last, so a single output file collects all iterations. |
| tFileList | Iterate over files in a directory (File family but orchestration in practice) | Directory; FileList Type: Files / Directories / Both; Include subdirectories; Case Sensitive: Yes/No; Generate Error if no file found; Use Glob Expressions as Filemask (checked = `*.csv`, unchecked = Java regex `.*\.csv`); Files table (Filemask); Order by: By default / By file name / By file size / By modified date; Order action: ASC / DESC; Adv: Use Exclude Filemask, Format file path to slash(/) style | `tFileList_1_CURRENT_FILE`, `CURRENT_FILEPATH`, `CURRENT_FILEDIRECTORY`, `CURRENT_FILEEXTENSION`, `NB_FILE` (Integer, after the loop). |
| tCollector / tPartitioner / tDepartitioner / tRecollector | Manual data-flow parallelization | Number of Child Threads; Buffer Size; Use a key hash for partitions + Key Columns (tPartitioner); Merge sort partitions (tDepartitioner); Starting Collector (tRecollector) | Subscription. Prefer right-click > Set parallelization, which inserts them implicitly. See Parallelization. |

## tRunJob in depth

### Basic settings

| Setting | Meaning |
| --- | --- |
| Use dynamic job | Child job name computed at runtime from Context job (expression, e.g. `context.child_job`). Selecting it hides Context and Use an independent process (dynamic jobs always run as independent processes) and hides Propagate the child result. Every candidate child must be ticked in the Job list so it is built into the export. |
| Job | Child job picked from the repository (`...` button). Version: Latest (resolves at build/generation time to the newest version in the workspace) or a fixed `n.m`. |
| Context | Which context group of the child to run (child's own groups). Overridden per variable by Transmit whole context / Context Param. |
| Use an independent process to run subjob | Spawns `java -cp ... <ChildClass> --context=... --context_param ...` with the JVM Setting arguments. Separate heap (fixes OOM in big children), separate globalMap, separate static state (Numeric.sequence, shared DB connections, tHash caches NOT shared). Not compatible with JobServer job cache (doc). Context values travel as command-line strings (visible in `ps`). |
| Die on child error | Checked: a non-zero child return code throws in the parent (parent subjob fails, OnSubjobError fires, exit code non-zero). Unchecked: parent continues; test `CHILD_RETURN_CODE` with Run if. |
| Transmit whole context | Pass all parent context variables to the child by name (child variables that do not exist in the parent keep the child's defaults for the selected Context). |
| Context Param | Table Parameters (dropdown of child variables) / Values (expression). Applied after Transmit whole context, so it wins. Values are stringified then parsed by the child's typed context. |
| Copy Child Job Schema | Pulls the child's tBufferOutput schema into tRunJob's output schema. |

### Advanced settings

| Setting | Meaning |
| --- | --- |
| Print Parameters | Prints the context values passed to the child on the console (passwords included - avoid in prod). |
| Propagate the child result to the output schema | Rows the child wrote with tBufferOutput are emitted on tRunJob's Main output in the parent. Only effective when tRunJob is itself fed by an input row (e.g. tFixedFlowInput -> tRunJob -> tLogRow) and not with dynamic job / independent process. |
| JVM Setting / Use specific JVM arguments | Table of arguments (`-Xmx4096m`, `-Dfile.encoding=UTF-8`) for the independent process only. |
| tStatCatcher Statistics | Emit begin/end stats for this component. |

### Passing data parent <-> child

| Channel | Direction | Same JVM | Independent process | Notes |
| --- | --- | --- | --- | --- |
| Context Param / Transmit whole context | parent -> child | yes | yes (as `--context_param`) | Strings; typed on arrival. |
| tBufferOutput in child + tRunJob output schema | child -> parent | yes | no | Needs an input row into tRunJob. |
| `CHILD_RETURN_CODE` | child -> parent | yes | yes | Integer; tDie code or 0/1. |
| `CHILD_EXCEPTION_STACKTRACE` | child -> parent | yes | no | Only for thrown exceptions, not tDie messages. |
| globalMap | neither | no (separate maps) | no | Use a static routine holder or context instead. |
| tHashOutput / tHashInput | neither | no | no | Hash caches are per job instance. |
| Shared DB connection | parent -> child | yes: tDBConnection Adv > Use or register a shared DB Connection, same Shared DB Connection Name in child's tDBConnection | no | Static registry in `SharedDBConnection`; commit/close once in the parent. |
| Static routine field | both | yes | no | `public static` in a Routine; thread-unsafe. |
| File / DB table | both | yes | yes | The only portable channel across processes. |

### Lineage and logging

Parent launches the child with `--father_pid=<parent pid> --root_pid=<root>`
so tStatCatcher/tLogCatcher rows carry `pid`, `father_pid`, `root_pid`; AMC
groups them under the root job. A tLogCatcher in the parent sees a child's
exception only when it propagates (same JVM, Die on child error). Put
tLogCatcher in the child too, or rely on project-level Stats & Logs which is
generated into every job.

## Iteration components

Iterate carrier contract: the iterator puts its values into globalMap just
before calling the target subjob method; the target reads them with a cast.

```
tFileList_1 --Iterate--> tFileInputDelimited_1 --Main--> tMap_1 --Main--> tDBOutput_1
   File name/Stream: ((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))

tLoop_1 (For 1..5 step 1) --Iterate--> tRunJob_1
   Context Param: batch_no = ((Integer)globalMap.get("tLoop_1_CURRENT_VALUE"))

tDBInput_1 --Main--> tFlowToIterate_1 --Iterate--> tDBInput_2 (query uses ((String)globalMap.get("row1.schema_name")))
```

- Everything inside the iterated subjob runs completely per iteration
  (connection open/close included unless you use an existing connection).
- `NB_LINE` of the iterated input is overwritten each iteration; accumulate
  with tSetGlobalVar or a tJava `globalMap.put("total", total + nb)`.
- After the loop, `tFileList_1_NB_FILE` is available on the OnSubjobOk from
  tFileList.
- tFlowToIterate with Iterate target followed by tIterateToFlow re-materialises
  a flow (classic trick to call a per-row web service / child job and continue
  with a Main flow).

## Wait components

| Component | Loop exit | Typical wiring |
| --- | --- | --- |
| tWaitForFile | Then: exit loop, or Max. iterations reached, or tDie | `tWaitForFile_1 --Iterate--> tFileInputDelimited (File name = ((String)globalMap.get("tWaitForFile_1_PRESENT_FILE")))`. To avoid half-written files: wait for a `.done` marker or compare size over two ticks with tFileProperties + Run if. |
| tWaitForSqlData | Then: exit loop / Max. iterations | `tWaitForSqlData_1 --Iterate--> tDBInput` |
| tWaitForSocket | connection arrives | `--Iterate-->` processing |
| tInfiniteLoop + tSleep | never (tDie or kill) | daemon-style polling in TAC/TMC with `Wait at each iteration` |

## Flow shaping and buffers

| Component | Family | Settings | Semantics |
| --- | --- | --- | --- |
| tBufferOutput | Buffer (Technical in old palettes) | schema | Appends each row to an in-memory list owned by the job instance. Consumers: tBufferInput in the same job (later subjob), tRunJob in the parent (Propagate the child result), `runJob()` return value from Java, and the legacy "Export Job as Webservice" (Axis) where the buffer is the SOAP response. No size limit except heap. |
| tBufferInput | Buffer | schema (set manually, matching tBufferOutput) | Start component; replays the buffered rows. Use after an OnSubjobOk from the subjob that filled the buffer. |
| tReplicate | Orchestration | schema | N identical Main outputs in the same subjob. |
| tUnite | Orchestration | schema | Sequential union, same subjob. |
| tSetGlobalVar | Misc | Variables table: Key (String expr) / Value (Object expr) | `globalMap.put(key, value)` per incoming row (Main in) or once (trigger/Iterate in). Also passes the row through if an output exists. Read back with the right cast. |

## tHashOutput / tHashInput

| Component | Settings | Notes |
| --- | --- | --- |
| tHashOutput | Schema; Link with a tHashOutput (then Component list = the primary tHashOutput; Append becomes hidden but always on); Keys management: Keep all / Keep first (Keep last unverified); Append (default on: keeps data across iterations in the same subjob; off: clears the cache before each load); Data write model (unverified) | Writes rows to an in-JVM cache keyed by the component. Linked tHashOutputs share one cache readable from any of them. |
| tHashInput | Component list (which tHashOutput); schema; Clear cache after reading | Start component; emits the cached rows. Must run AFTER the filling subjob has finished (OnSubjobOk), otherwise it reads nothing or a partial list. Cache survives across subjobs within one job run; not across tRunJob boundaries or JVMs. |

Palette: Technical family; in 6.x/7.x the two components are hidden by default
and must be enabled in Project Settings > Designer > Palette Settings (or
File > Edit Project properties). In 8.0 they are visible (unverified).
Memory: rows are stored as objects on the heap; size `-Xmx` accordingly. For
lookups inside one subjob prefer tMap lookup with "Load once" (tmap-expressions.md).

## Misc family

| Component | Purpose | Key settings | Globals / notes |
| --- | --- | --- | --- |
| tFixedFlowInput | Emit constant rows | Schema; Number of rows (default 1); Mode: Use Single Table (one value per column) / Use Inline Table (grid, one row per line) / Use Inline Content (delimited file) with Row Separator and Field Separator; Values | `tFixedFlowInput_1_NB_LINE`. Number of rows multiplies the table (Inline Table with 3 rows and Number of rows 2 = 6 rows). Use it to turn a trigger into a Main flow (one-row driver). |
| tRowGenerator | Generate test data | Editor: per-column Function (TalendDataGenerator.getFirstName(), Numeric.sequence("s1",1,1), TalendDate.getCurrentDate(), TalendDate.addDate(...), random values, `...` custom expression); Number of Rows for RowGenerator; Preview | `tRowGenerator_1_NB_LINE`. Functions come from system routines (tmap-expressions.md). |
| tSetGlobalVar | Put values into globalMap | Variables: Key / Value | see above. |
| tMemorizeRows | Keep the last N rows in arrays | Row count to memorize; Columns to memorize | Access `((Integer[])globalMap.get("tMemorizeRows_1_id"))[0]` (current), `[1]` (previous) ... per memorized column; arrays typed by column class. Used for running comparisons without tMap lookups. |
| tMsgBox | Modal dialog (Studio runs only) | Title; Buttons: OK / OK Cancel / Yes No / Yes No Cancel / Retry Cancel / Abort Retry Ignore; Icon: Error/Info/Question/Warning; Message | `tMsgBox_1_RESULT` (int button code). Blocks headless servers forever: never leave in a TAC/TMC job. |
| tServerAlive | Ping host:port list | Server list (Host, Port); Timeout | Main out with host/port/alive/message style columns (exact schema unverified). |
| tChronometerStart | Start a timer | none | Pair with tChronometerStop. |
| tChronometerStop | Print elapsed time | Since options: Since the beginning / Since a tChronometerStart (pick component); Caption; Display duration in console; Display in human readable format (label unverified); Adv: Print header? (unverified) | Output on stdout; also consider tStatCatcher `duration` for component timing. |
| tContextDump | Dump context as key/value rows | Hide Password | Main out schema `key`, `value`. Feed tLogRow or tFileOutputDelimited for debugging. |
| tCreateTable | DDL from schema (Database family) | DB type, table name, Action: Create table / Create table if not exists / Drop and create / Drop if exists and create | `components-core.md`. |
| tSendMail | SMTP mail (Internet family) | To/From/Subject/Message, attachments, SMTP host, TLS/SSL, auth | `connectors-catalog.md`. Standard OnSubjobError target. |

## Context components and Implicit Context Load

### tContextLoad (Context family)

| Setting | Meaning |
| --- | --- |
| Input | Any Main flow with exactly two columns: key (parameter name), value (string). Typical sources: tFileInputDelimited (`key;value` or `key=value` file with Field Separator `=`), tDBInput `select key, value from params where env = 'prod'`, tFixedFlowInput. |
| Print operations | Log each `key = value` assignment to the Run console (passwords shown). Can be bound to a context variable in 7.x. |
| Disable warnings | Suppress "variable X is not in the context" (key in source but not declared) and "context variable Y not set" (declared but absent from source). |
| Disable errors | Suppress error messages. |
| Die on error | Default on; off = skip the bad row and continue. |
| Semantics | Assigns `context.<key>` by name and re-parses to the declared type. Unknown keys are ignored (warning only). Runs as a normal component: whatever it loads overrides `--context_param` and implicit load values set earlier. |
| Globals | `tContextLoad_1_NB_LINE`, plus counts/lists of keys found/not found (`KEY_IN_FILE`, `KEY_NOT_IN_FILE`, `KEY_NOT_INCONTEXT` approximately; unverified). |

### Implicit Context Load (Job view > Extra tab)

| Setting | Meaning |
| --- | --- |
| Implicit tContextLoad | Enable. Equivalent of a tContextLoad executed at job start, before tPrejob, without any component on the canvas. |
| From File | File path (expression; may itself use context, e.g. `context.config_dir + "/" + context.env + ".properties"`), Field Separator. |
| From Database | Property Type Built-in/Repository, DB type, Host, Port, Database, Schema, Username, Password, Table Name, Query Condition (SQL `WHERE` fragment, e.g. `env = 'prod'`; empty = all rows). Table needs two columns key/value (column names fixed by the generator: `key`, `value`; unverified). |
| Print operations / Disable warnings / Disable errors | Same as the component. |
| Use Project Settings | Pulls the defaults from Project Settings > Job Settings > Implicit Context Load, so every job in the project loads the same way. |
| Remote Engine / JobServer | The file path must exist on the execution host, not the Studio machine (doc note for Remote Engine). |

### Precedence of context values (highest first)

1. Explicit tContextLoad component inside the job (runs when its subjob runs).
2. Implicit Context Load values (applied at job start after CLI parsing) -
   BUT recent versions skip keys that were supplied with `--context_param`,
   so the command line wins for those keys (unverified for your exact version;
   read the generated code block "tContextLoad" in the Code view to confirm).
3. `--context_param key=value` command-line overrides (TAC Job Conductor /
   TMC task "Context parameters" fields end up here). All values are strings and
   are parsed to the declared type; a non-numeric string for an Integer variable
   fails at start-up.
4. tRunJob Context Param / Transmit whole context (child jobs only).
5. Values of the selected context group (`--context=Prod`), compiled into
   `<project>/<job>_<ver>/contexts/<ContextName>.properties` inside the job jar (no job-name prefix;
   see deployment-runtime.md).
6. The Default context group when `--context` is absent.

Context variables declared with `[Prompt]` prompt interactively only in Studio.

## Custom Code family

| Component | Position | Settings | Notes |
| --- | --- | --- | --- |
| tJava | Standalone: start of a subjob, trigger target, or Iterate target. Runs once per activation. | Code; Adv: Import (`import java.util.*;`) | No row input/output. Use for `globalMap.put`, `System.out.println`, `context.x = ...`, `Thread.sleep`, calling routines. `return`/`System.exit` inside break the generated method; prefer tDie. |
| tJavaRow | Inside a Main flow; code runs once per row. | Schema (in/out), Code, Generate code button (writes `output_row.col = input_row.col;` for every column), Adv: Import | Variables `input_row`, `output_row`. Declarations inside Code are per row; keep state in globalMap or a tJavaFlex. `tJavaRow_1_NB_LINE`. |
| tJavaFlex | Anywhere: as input (start), transformer, or output. | Start code (runs once, before first row - declare variables, open loops `for (...) {`), Main code (per row - `row2.col = row1.col;`), End code (after last row - close loops `}`, aggregate, `globalMap.put`), Data Auto Propagate (copy input columns to output automatically), Adv: Import | The three sections map 1:1 to begin/main/end. Output link name (`row2`) is referenced literally in Main code; renaming the link breaks the code. |
| tGroovy / tGroovyFile | Standalone | Script / Script file, Variables table | Deprecated (hidden in 7.x/8.0 palette; unverified whether still shipped). Use tJava + routines. |
| tLibraryLoad | Start or trigger target, typically first subjob | Library (choose module / Install external jar); Adv: Dynamic Libs > Lib Paths (`"/opt/libs/x.jar"`), Import (Java import lines for tJava* code) | One jar per component. Jars selected here are added to the build classpath. For routines depending on jars use the routine's "Edit Routine Libraries" instead (studio.md). |
| Routines | Code > Routines | `public static` methods | Called as `MyRoutines.foo(x)` in any expression; shared JVM-wide, so static mutable fields are not thread-safe under parallel iterate. |

## System and Technical families

| Component | Family | Settings | Globals / notes |
| --- | --- | --- | --- |
| tSystem | System | Use Single Command / Use Array Command (`{"sh","-c","..."}` avoids shell quoting issues); Command; Standard Output: to console / to global variable / both (labels approximately); Error Output: same; Schema (optional output row with stdout/stderr); Adv: Environment variables table, Change directory / Use home directory | `tSystem_1_EXIT_VALUE` (Integer), `tSystem_1_OUTPUT`, `tSystem_1_ERROROUTPUT`. Non-zero exit does NOT fail the job by itself: add Run if `((Integer)globalMap.get("tSystem_1_EXIT_VALUE")) != 0 -> tDie`. Runs on the execution host (JobServer/engine), not the Studio machine. |
| tSSH | System | Host, Port (22), User, Authentication method: Password / Public key (Private key, Key passphrase); Commands table; Standard output / Error output to console/global variable; Pseudo terminal (unverified) | `tSSH_1_OUTPUT`, `tSSH_1_ERROR`, `tSSH_1_EXIT_CODE` (names approximately). Output row schema with stdout/stderr/exit columns available. |
| tSetEnv | System | Parameters table (Name / Value); mode append/overwrite (unverified) | Sets environment variables for the running JVM process so later tSystem children inherit them (unverified details). |
| tSetKeystore | Keystore (Technical) | TrustStore type: PKCS 12 / JKS; TrustStore file; TrustStore password; Need Client authentication -> KeyStore type / KeyStore file / KeyStore password; 8.0.1-R2023-06+: Set TrustStore / Set KeyStore / Both; Check server identity (Spark pages) | Sets `javax.net.ssl.trustStore*` / `keyStore*` JVM system properties for the whole JVM: run it in tPrejob or first subjob via OnSubjobOk before any HTTPS/LDAPS/JDBC-SSL component. Affects child jobs in the same JVM. |
| tSetProxy | Proxy (Technical) | Proxy type: Http Proxy / Https Proxy / Socks Proxy / FTP Proxy; Host; Port; User/Password (Https only per doc) | Sets `http.proxyHost` etc. system properties JVM-wide. Not for ESB routes (affects the whole Runtime). |
| tAssert | Logs & Errors (test) | Description; Expression (boolean) | Emits an assertion result (Ok / Failed) caught by tAssertCatcher; used by Studio Test Cases. |
| tAssertCatcher | Logs & Errors | Catch Java Exception; Catch tDie; Catch tAssert | Start component; schema approximately moment, pid, project, job, language, origin, status, substatus, errorMessage, exceptionMessage (unverified columns). |
| tWarn | Logs & Errors | Warn message; Code (default 42 approximately); Priority: Trace(1)/Debug(2)/Info(3)/Warning(4)/Error(5)/Fatal(6) | Non-blocking; sends an event to tLogCatcher (Catch tWarn) and Stats & Logs "Catch user warnings". `tWarn_1_WARN_MESSAGES`, `WARN_CODE`, `WARN_PRIORITY`. |
| tDie | Logs & Errors | Die message; Error code (default 4); Priority (default 5); Adv: Exit the JVM immediately; tStatCatcher Statistics | Cannot be a start component. `DIE_MESSAGES`, `DIE_CODE`, `DIE_PRIORITY`. See return codes. |

## Logs & Errors family

### Catcher components

| Component | Fires | Settings | Schema (read-only) |
| --- | --- | --- | --- |
| tLogCatcher | Each caught event: Java exception thrown by a component with Die on error (type `Java Exception`, priority 6/Fatal approximately), tDie (type `tDie`), tWarn (type `tWarn`). Its subjob runs once per event, synchronously in the raising thread. | Catch Java Exception; Catch tDie; Catch tWarn | moment (Date), pid, root_pid, father_pid, project, job, context, priority (Integer), type (String), origin (component unique name), message, code (Integer) |
| tStatCatcher | Job begin/end and, for components with Adv > tStatCatcher Statistics checked, component begin/end. | none beyond schema (project-level: Use statistics, Catch components statistics) | moment, pid, father_pid, root_pid, system_pid (Long), project, job, job_repository_id, job_version, context, origin, message_type (`begin`/`end`), message (`success`/`failure`), duration (Long, ms) |
| tFlowMeterCatcher | Each tFlowMeter report (end of the metered flow). | none | moment, pid, father_pid, root_pid, system_pid, project, job, job_repository_id, job_version, context, origin, label, count, reference, thresholds |
| tFlowMeter | Placed inline in a Main flow to count rows | Mode: Absolute (count) / Relative (ratio to Reference connection); Reference connection; Thresholds (relative only) | Passthrough; results go to tFlowMeterCatcher / Stats & Logs volumetrics. |

Catcher rules:
- A catcher is the start of its own subjob; nothing can trigger INTO it.
  Its downstream (tLogRow, tDBOutput, tFileOutputDelimited append, tSendMail
  via OnSubjobOk from the catcher subjob) runs per event; use Use an existing
  connection + append mode outputs, and commit in tPostjob.
- A tDie placed after tLogCatcher (tLogCatcher -> tLogRow; OnSubjobOk -> tDie)
  turns any caught warning into a job failure. tLogCatcher exposes no
  `_PRIORITY` global: filter with tFilterRow on `priority >= 5` before the
  output, or have a tJavaRow set a flag in globalMap and test it with Run if.
- tLogCatcher does not see exceptions swallowed by Die on error unchecked, nor
  reject rows. It does see child-job exceptions only when they propagate.
- One tLogCatcher per job is the norm; project Stats & Logs "Use logs" adds an
  invisible one anyway.

### tLogRow

| Setting | Meaning |
| --- | --- |
| Mode | Basic (one line per row, values separated by Field Separator, default `|`), Table (print values in cells of a table; buffered, printed at end of flow - memory heavy on big flows), Vertical (each row is a key/value list) |
| Field Separator | Basic mode only. |
| Print header | Basic mode: print column names first. |
| Print component unique name in front of each output row | Basic mode: prefix `tLogRow_1` to tell several loggers apart. |
| Print schema column name in front of each value | Basic mode: `id=1|name=x`. |
| Use fixed length | Basic mode: pad values to a fixed width. |
| Adv: Print content with log4j | Route the output through the log4j logger (INFO) instead of `System.out`, so it obeys the log4j level and appenders. |
| Adv: tStatCatcher Statistics | as everywhere. |

tLogRow is a passthrough: `tFileInputDelimited --> tLogRow --> tDBOutput` is
valid. It is the main console noise source in production: disable with the
component's Deactivate (right-click) or route via log4j and set WARN.

## Stats & Logs, AMC, log4j

### Stats & Logs (Project Settings > Job Settings > Stats & Logs; per job: Job view > Stats & Logs tab, Use Project Settings button)

| Setting | Effect |
| --- | --- |
| Use statistics (tStatCatcher) | Generates a hidden tStatCatcher: job start/end rows with duration and success/failure. |
| Catch components statistics | Also per-component begin/end rows (equivalent to ticking tStatCatcher Statistics on every component). |
| Use logs (tLogCatcher) | Hidden tLogCatcher; sub-options Catch runtime errors (Java exceptions), Catch user errors (tDie), Catch user warnings (tWarn). |
| Use volumetrics (tFlowMeterCatcher) | Hidden tFlowMeterCatcher; needs tFlowMeter components in flows. Catch realtime statistics (unverified label) streams row counts. |
| On Console | Print the three row types to stdout. |
| On Files | Directory + Stats file name / Log file name / Meter file name (delimited files, appended; defaults like `stats_file.txt`, `logs_file.txt`, `meter_file.txt` unverified). |
| On Databases | Property Type (Built-in / Repository connection), DB type, Host, Port, Database, Schema, Username, Password, and three table names (Stats table / Logs table / Meter table; default names unverified - commonly `statcatcher`, `logcatcher`, `flowmetercatcher`). Tables must pre-exist with the catcher schemas, or be created by running a job once with tCreateTable using the catcher schema (AMC guide: "create three files or database tables respectively using the schema of the tLogCatcher, tStatCatcher, tFlowMeterCatcher components"). |
| Context-driven | All fields accept context variables, so one build can log to different DBs per environment. |

### Activity Monitoring Console (AMC)

- Reads the three catcher tables/files. Views: Job tree / History / Detailed
  history / Logs / Meter log / Error report / Threshold charts.
- Available as a Studio perspective (Window > Perspective > Talend Activity
  Monitoring Console) and embedded in TAC (Monitoring > Activity Monitoring
  Console; datasource configured in TAC Monitoring settings with the three
  table names). Standalone AMC web app existed in older releases (unverified
  for 8.0). Talend Cloud/TMC has no AMC; TMC keeps its own run history.
- Supported DBs listed for the AMC DB in the 8.0 install guide: MySQL,
  MariaDB, Oracle, Sybase and others (PostgreSQL/MSSQL not listed in the
  snippet seen; verify).
- Lineage: `root_pid` = outermost job run, `father_pid` = calling job,
  `pid` = this job; AMC nests child jobs by these.

### log4j

| Item | Detail |
| --- | --- |
| Project Settings > Log4j | Activate log4j in components (checkbox) + editable log4j2 XML template that is generated into each build. Off = components print with `System.out/err` only. |
| Run view > Advanced settings | `log4jLevel` checkbox + level dropdown (TRACE, DEBUG, INFO, WARN, ERROR, FATAL, OFF) for Studio runs. |
| Built job | Accepts `--log4jLevel=DEBUG` (parsed in `runJobInTOS`, applied via `Configurator.setLevel`). TAC Job Conductor task has a Log4j level field (unverified); TMC task configuration has a Log level setting. |
| Config file | 8.0: log4j2 (`log4j2.xml` shipped in the export; override with `-Dlog4j2.configurationFile=file:/path/log4j2.xml` or `-Dlog4j.configurationFile=`). 7.3.1 before R2021-12 and earlier: log4j 1.x (`log4j.xml`, `-Dlog4j.configuration=file:...`). 7.3.1 switched to log4j2 in the R2021-12/R2022-01 monthly updates after CVE-2021-44228; 8.0.1 is log4j2 only. Exact file placement: `artifact-formats.md`. |
| Component logging | With log4j active, components log at DEBUG (parameters), INFO (start/stop, row counts), WARN, ERROR (`tDBOutput_1 - ...`). tLogRow Print content with log4j and tJava `log.info(...)` (the generated class exposes `log`, a `org.apache.logging.log4j.Logger` approximately) join the same stream. |
| Studio console | Run view output also receives log4j output; TAC/JobServer keeps it in the task's execution log; Remote Engine forwards to TMC Run details. |

## Resume and recovery checkpoints

| Item | Detail |
| --- | --- |
| Feature | "Recovery Checkpoints" (Error recovery). Studio: select an OnSubjobOk or OnSubjobError trigger > Component view > Error recovery tab > Recovery Checkpoint checkbox, Label, Failure instructions. Editable only in a remote (TAC-connected) project; save the job for it to take effect. |
| Runtime support | Generated code creates `resumeUtil = new ResumeUtil(resuming_logs_dir_path, isChildJob, rootPid)` and writes JOB_STARTED / CHECKPOINT_REACHED / SYSTEM_LOG / JOB_ENDED style entries (`resumeUtil.addLog(...)`) into a log in `--resuming_logs_dir_path`. Each checkpointed subjob method is guarded by `resumeEntryMethodName` / `globalResumeTicket` so that on a relaunch with `--resuming_checkpoint_path=<checkpoint id>` the subjobs before the checkpoint are skipped and execution enters at the checkpoint. |
| TAC | Job Conductor > select task > Recover last execution button (or Monitoring > Error Recovery Management); shows only the last execution; older ones via Task execution monitoring. TAC supplies the two `--resuming_*` arguments. |
| Limits | Only subjob-level granularity (trigger links), no row-level restart; state in globalMap/tHash is NOT restored (the skipped subjobs did not run), so checkpointed subjobs must be self-contained or reload what they need. Not available in TMC (unverified). |
| DIY restartability | Persist progress (file name, batch id) to a control table; on start read it and drive with Run if. Pattern in `patterns-gotchas.md`. |

## Parallelization

| Mechanism | Where | Granularity | globalMap behaviour | Notes |
| --- | --- | --- | --- | --- |
| Multi thread execution | Job view > Extra | Independent subjobs (no trigger between them) run concurrently, one thread each; also Parallelize Buffer Unit Size field | Access synchronized (doc), still logically racy: a value put by one subjob is not guaranteed visible in time for another subjob that is not trigger-linked | Keep thread count <= CPU count. Subjobs linked by OnSubjobOk stay sequential. tPrejob still first, tPostjob still last. |
| Iterate link > Enable parallel execution | Iterate link Basic settings; Number of parallel executions (int or context) | Iterations of one Iterate link | Doc warns globalMap.put/get after a parallel Iterate behave unreliably; generated code passes a per-thread copy of globalMap into each iteration (unverified), so reads of the iterator's own variables inside the branch usually work, while anything written for use after the loop is lost or raced | Routines with static state (Numeric.sequence) and non-thread-safe components fail. Safest: put the per-iteration work in a child job via tRunJob (own globalMap). |
| tParallelize | Component | Named subjob branches | Shared map, unsynchronized unless Multi thread also on | Wait for end of first / end of all; Die when one fails. |
| Set parallelization (automatic data-flow parallelization) | Right-click the start component of a subjob > Set parallelization; then click a Row link > Parallelization tab | Rows of a single subjob split across threads | Each thread is a copy of the downstream components; component globals (NB_LINE) become per-partition | Options per link: Partitioning (Number of Child Threads, Buffer Size, Use a key hash for partitions + Key Columns), Collecting, Departitioning (Merge sort partitions), Recollecting. Implemented with tPartitioner/tCollector/tDepartitioner/tRecollector. Subscription (Platform / Big Data) only. Key hash keeps same-key rows in one thread (needed for aggregates/SCD). Round-robin otherwise. |
| tRunJob independent process | Component | Child JVM | Separate | Parallel independent processes = N JVMs; mind total RAM. |
| Spark | Separate framework | RDD/Dataset partitions | n/a | `big-data-spark.md`. |

Thread-safety checklist for anything parallel: no `Numeric.sequence` (use DB
sequences), no shared static fields, one DB connection per thread (do not
share a tDBConnection across parallel iterations - most JDBC drivers are
connection-unsafe), unique temp file names per iteration (use
`Thread.currentThread().getId()` or the iteration value), tHashOutput Append
races.

## Patterns

ASCII: `-->` Main row, `==>` Iterate, `--OK-->` OnSubjobOk, `--CO-->` OnComponentOk,
`--ERR-->` OnSubjobError, `--IF[..]-->` Run if.

### Children in sequence with one shared DB connection

```
tPrejob_1 --CO--> tDBConnection_1   (Adv: Use or register a shared DB Connection, name "shared_dwh")
                                     --CO--> tRunJob_load_dim  (child: tDBConnection w/ same shared name, Use existing conn)
                                     --OK--> tRunJob_load_fact
                                     --OK--> tDBCommit_1 (Close connection off)
tPostjob_1 --CO--> tDBClose_1
tRunJob_* : Die on child error = on, Transmit whole context = on, same JVM (independent process OFF)
```

### Loop over files

```
tFileList_1 (Directory context.in_dir, Filemask "*.csv", glob on, Order by file name)
  ==> tFileInputDelimited_1 (File name: ((String)globalMap.get("tFileList_1_CURRENT_FILEPATH")))
        --> tMap_1 --> tDBOutput_1 (Use existing connection)
      --OK--> tFileCopy_1 (move to archive: ((String)globalMap.get("tFileList_1_CURRENT_FILEPATH")) -> context.archive_dir, Remove source)
tFileList_1 --OK--> tJava_1 (System.out.println("files: " + globalMap.get("tFileList_1_NB_FILE")))
```

### Retry loop

```
tLoop_1 (While: Declaration int attempt = 0; Condition attempt < 3 && !"ok".equals(globalMap.get("state")); Iteration attempt++)
  ==> tRunJob_1 (Die on child error OFF)
      --IF[((Integer)globalMap.get("tRunJob_1_CHILD_RETURN_CODE")) == 0]--> tSetGlobalVar_ok (state = "ok")
      --IF[((Integer)globalMap.get("tRunJob_1_CHILD_RETURN_CODE")) != 0]--> tSleep_1 (30)
tLoop_1 --OK--> tJava_check --IF[!"ok".equals(globalMap.get("state"))]--> tDie_1 (Error code 3, "gave up after 3 attempts")
```
Initialise `state` in a tJava before tLoop (`globalMap.put("state","init")`).

### Conditional branches

```
tFileInputDelimited_1 --> tFilterRow_1 --> tDBOutput_1
tFileInputDelimited_1 --IF[((Integer)globalMap.get("tFileInputDelimited_1_NB_LINE")) > 0]--> tRunJob_process
tFileInputDelimited_1 --IF[((Integer)globalMap.get("tFileInputDelimited_1_NB_LINE")) == 0]--> tWarn_1 ("empty file")
```
Both Run if links drawn from the subjob start component so they fire after
the subjob ends (NB_LINE set). Use `Integer` cast; wrap with
`globalMap.get(...) != null &&` when the component may not have run.

### Global error handler

```
tLogCatcher_1 (Catch Java Exception, tDie, tWarn) --> tMap_err (add context.env, hostname) --> tDBOutput_errors (append, Use existing connection)
                                                  --> tJavaRow_1 (globalMap.put("last_err", input_row.origin + ": " + input_row.message); output_row = input_row)
                                                  --> tLogRow_err (Vertical)
tLogCatcher_1 --OK--> tSendMail_err (Subject: "Job " + jobName + " failed"; Message: (String)globalMap.get("last_err"))
```
`jobName` is a field of the generated class and usable in expressions. The
catcher subjob (and its OnSubjobOk mail) runs once per caught event; put a
tFilterRow on `type.equals("Java Exception") || type.equals("tDie")` ahead of
the outputs to skip tWarn noise.
Failure-only mail without a catcher: main subjob `--ERR--> tSendMail_fail --CO--> tDie_1`.

### Audit stats to DB

```
Project Settings > Stats & Logs: Use statistics + Catch components statistics, On Databases (context.amc_*), tables stats/logs/meter
-- or explicit --
tStatCatcher_1 --> tMap (add run_id = context.run_id) --> tDBOutput_stats (append)
```

### Child returns rows to parent

```
child:  tDBInput --> tBufferOutput_1
parent: tFixedFlowInput_1 (1 row) --> tRunJob_1 (Copy Child Job Schema; Adv: Propagate the child result to the output schema) --> tLogRow / tMap
```

### Shared lookup via hash within one job

```
subjob A: tDBInput_ref --> tHashOutput_1 (Keep all, Append off)
subjob A --OK--> subjob B: tFileInputDelimited --> tMap_1 (lookup = tHashInput_1 [Component list tHashOutput_1]) --> tDBOutput
subjob B --OK--> subjob C: tFileInputDelimited_2 --> tMap_2 (lookup = tHashInput_2 [tHashOutput_1]) --> ...
```
Never let B start on OnComponentOk from tDBInput_ref: the hash is still filling.

### Dynamic child

```
tDBInput_jobs (select job_name from schedule) --> tFlowToIterate_1
  ==> tRunJob_dyn (Use dynamic job; Context job: ((String)globalMap.get("row1.job_name")); Die on child error OFF; JVM Setting -Xmx1g)
      --IF[((Integer)globalMap.get("tRunJob_dyn_CHILD_RETURN_CODE")) != 0]--> tWarn_1
```
Tick every possible child in the Job list so it is built.

### Wait for a file then process

```
tWaitForFile_1 (Directory context.drop, File mask "*.done", created, Then: exit loop, Max. iterations 720, 10 s)
  ==> tFileInputDelimited_1 (File name: ((String)globalMap.get("tWaitForFile_1_PRESENT_FILE")).replace(".done",".csv")) --> ...
tWaitForFile_1 --OK--> tJava_timeout --IF[globalMap.get("tWaitForFile_1_PRESENT_FILE") == null]--> tDie_1 ("no file in 2h", code 2)
```

### Derived values with tSetGlobalVar

```
tFixedFlowInput_1 (1 row) --> tSetGlobalVar_1
   run_id   = TalendDate.getDate("yyyyMMddHHmmss")
   out_file = context.out_dir + "/export_" + globalMap.get("run_id") + ".csv"   (second key may not see first in same row: compute in tJava instead)
```
Use tJava for dependent values:
`globalMap.put("run_id", TalendDate.getDate("yyyyMMddHHmmss")); globalMap.put("out_file", context.out_dir + "/export_" + globalMap.get("run_id") + ".csv");`

### Counting rows without tMap

```
tFileInputDelimited_1 --> tFlowMeter_1 (Absolute) --> tDBOutput_1
  after subjob: ((Integer)globalMap.get("tFileInputDelimited_1_NB_LINE")), ((Integer)globalMap.get("tDBOutput_1_NB_LINE_INSERTED")), _NB_LINE_UPDATED, _NB_LINE_REJECTED
```

### Timing with tChronometer

```
tChronometerStart_1 --CO--> tDBInput --> ... --> tDBOutput
                     --OK--> tChronometerStop_1 (Since a tChronometerStart: tChronometerStart_1, Caption "load_fact")
```
Or Run view > Advanced settings > Exec time / Statistics in Studio; tStatCatcher `duration` in prod.

## Gotchas

| Symptom | Cause | Fix |
| --- | --- | --- |
| Downstream subjob reads an empty/partial file or table even though it is linked to the writer | Trigger is OnComponentOk drawn from a mid-flow component (e.g. tFileInputDelimited or tMap): it fires when that component's end code runs, before the output component has flushed | Draw OnSubjobOk from the subjob's start component. |
| tPostjob (connection close, cleanup mail) never runs on failure | tDie with Exit the JVM immediately, `System.exit` in tJava, JVM OOM kill, or TAC kill | Uncheck Exit the JVM immediately; let tDie set the exit code; do cleanup in tPostjob. |
| tHashInput returns 0 rows | Its subjob started on OnComponentOk / unlinked / Multi thread while tHashOutput was still loading; or Append off and an iterate re-cleared it; or reading across a tRunJob boundary | Link with OnSubjobOk from the filling subjob; keep both in the same job and JVM. |
| Parent job exits 0 although the child failed | tRunJob Die on child error unchecked, or the child failure happened inside the child's tPostjob, or Die on error unchecked on the failing child component | Check Die on child error, or Run if on `CHILD_RETURN_CODE != 0 -> tDie`. |
| `java.lang.ClassCastException: java.lang.Long cannot be cast to java.lang.Integer` (or the reverse) on a globalMap read | NB_LINE-style globals differ in type between components; some are Integer, some Long, tFileList NB_FILE is Integer, tSystem EXIT_VALUE Integer | Cast via `((Number)globalMap.get("...")).intValue()` or `String.valueOf(...)`; check the component's Outline view for the declared type. |
| Duplicate sequence numbers, missing rows, random NPEs under parallel Iterate | Numeric.sequence / static routine state / tFlowToIterate globals / shared DB connection are not thread-safe | Move per-iteration work into a child job (tRunJob), use DB sequences, one connection per iteration, or disable parallel. |
| tFileList finds nothing although files exist | Filemask typed as regex with Use Glob Expressions as Filemask checked (`.*\.csv` vs `*.csv`), Case Sensitive mismatch, or Directory ends up with doubled/missing slash | Match mask syntax to the checkbox; use Format file path to slash(/) style; print `tFileList_1_CURRENT_FILEPATH`. |
| Context value from a config file is ignored, no error | tContextLoad / implicit load key does not match a declared context variable name (case, prefix); unknown keys only warn and warnings may be disabled | Declare the variable; keep Disable warnings off in dev; check Print operations output. |
| `NumberFormatException` / job dies at start-up with `--context_param` | All CLI values are strings parsed to the declared type; empty string into Integer/Date; wrong Date pattern | Supply a parseable value; keep numeric contexts as String if they may be blank; dates must match the context's pattern. |
| tLogCatcher logs nothing for a DB error | The failing component has Die on error unchecked, so the exception is swallowed into `ERROR_MESSAGE`/Reject and nothing is thrown | Check Die on error, or route the Reject flow to your error table and raise tDie yourself. |
| Run if branch taken wrongly / NullPointerException in the condition | Condition evaluated at trigger time with globals not yet set (component skipped, iteration not run) or reading a stale value from a previous iteration | Null-guard (`globalMap.get(x) != null && ...`), reset globals at loop start with tJava, draw the trigger from the right source. |
| Values put in globalMap by one subjob are null in another after enabling Multi thread execution | The subjobs now run concurrently; no trigger means no ordering | Link dependent subjobs with OnSubjobOk (they stay sequential) and parallelize only truly independent ones. |
| "Component tMap_1 has no start" / Iterate link refused | Iterate drawn into a processing component, or a Main-only component used as the first in a subjob | Target an input component (tFileInputDelimited, tDBInput, tFixedFlowInput, tRunJob, tJava) with Iterate; use tFixedFlowInput as a one-row driver when you need a Main flow after a trigger. |
| tWaitForFile fires but the reader gets a truncated file or `file in use` lock | Detection happens at first directory listing while the producer is still writing | Have the producer write to a temp name and rename, or drop a `.done` marker and wait for that; or check size stability with tFileProperties over two iterations. |
| Independent-process tRunJob returns 0 while the child printed a stack trace | Child's own Die on error settings swallowed it, or child tDie was in a branch that did not set `errorCode` (e.g. tDie reached via OnComponentError inside tPostjob) | Fix the child so failures reach exit code (tDie in main path); read `CHILD_RETURN_CODE`; grep child stderr in the parent log. |
| log4j level set in Run view has no effect on the server | Run view Advanced settings apply to Studio runs only; TAC/TMC/JobServer runs use the task's log level or the exported log4j2.xml | Pass `--log4jLevel=` as a task JVM/program argument, set the level in TAC task / TMC task config, or edit the exported log4j2.xml / `-Dlog4j2.configurationFile`. |
| tMsgBox job hangs forever on the JobServer | Modal dialog waiting for a click on a headless host | Remove tMsgBox or guard with Run if `context.interactive`. |
| Child job in same JVM runs out of memory / changes parent's static state | Shared heap and statics (SharedDBConnection, Numeric.sequence) | Use an independent process with JVM Setting `-Xmx`, or size the parent heap. |
| tDie Error code 300 shows as 44 in the shell | Exit codes are modulo 256 on Linux | Use 1..255. |
| OnSubjobOk after tLogCatcher subjob triggers for every warning | Catcher subjob runs per event; its OnSubjobOk fires per event | Filter in the catcher flow (tFilterRow on priority/type) and keep the post-action idempotent, or set a flag in globalMap and act in tPostjob. |
| tRunJob child cannot see the parent's `tDBConnection_1` in Use an existing connection | Connections live in the parent's globalMap; the child's component list only shows its own | Use or register a shared DB Connection (Adv settings on tDBConnection in both jobs, same name), same JVM only. |
| Stats & Logs rows never appear in the AMC tables | Table names in Project Settings differ from those configured in TAC AMC datasource; tables missing columns (schema drift between versions, e.g. `system_pid`, `job_repository_id`); connection context values not set on the server | Create tables from the catcher schemas of your Studio version; align names; verify via On Console first. |
| Job exits 1 with no stack trace | A subjob threw, `status = failure`, but stderr went to log4j appenders or the exception was a tDie with empty message | Enable Use logs (tLogCatcher) On Console; check `tDie` messages; run with `--log4jLevel=DEBUG`. |

## Sources

https://help.qlik.com/talend/en-US/components/8.0/orchestration/trunjob-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/orchestration/trunjob-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/orchestration/trunjob-mapreduce-properties-deprecated
https://help.qlik.com/talend/en-US/components/8.0/orchestration/trunjob-tfixedflowinput-tbufferoutput-tlogrow-setting-up-parent-job-standard-component-create
https://help.qlik.com/talend/en-US/job-script-reference-guide/8.0/notes-about-schema-for-trunjob
https://help.qlik.com/talend/en-US/components/8.0/buffer/tbufferoutput-trunjob-tfileinputdelimited-tlogrow-buffering-data-standard-component-this
https://help.qlik.com/talend/en-US/components/7.3/buffer/tbufferoutput-tfileinputdelimited-tfixedflowinput-tjavarow-creating-parent-job-to-get-value-from-child-job-create
https://community.qlik.com/t5/Talend-Studio/resolved-get-the-exit-code-returned-by-a-subjob-in-a-Run-If/m-p/2266861
https://community.qlik.com/t5/Talend-Studio/resolved-How-to-get-the-error-message-from-the-child-job/m-p/2318608
https://community.qlik.com/t5/Talend-Studio/How-to-rerun-the-failed-child-job/td-p/2226163
https://help.qlik.com/talend/en-US/components/8.0/logs-and-errors/tdie
https://help.qlik.com/talend/en-US/components/8.0/logs-and-errors/tdie-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/logs-and-errors/twarn
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-08/using-tdie-twarn-and-tlogcatcher-for-error-handling
https://help.qlik.com/talend/en-US/components/8.0/logs-and-errors/tlogcatcher
https://help.qlik.com/talend/en-US/components/7.3/logs-and-errors/tlogcatcher-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/logs-and-errors/tstatcatcher
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-06/studio-stats-and-logs
https://help.qlik.com/talend/en-US/studio-user-guide/7.3/studio-stats-and-logs
https://help.qlik.com/talend/en-US/components/8.0/logs-and-errors/tflowmetercatcher
https://help.qlik.com/talend/en-US/components/7.3/logs-and-errors/tflowmetercatcher-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/logs-and-errors/tflowmeter-tflowmetercatcher-tmysqlinput-catching-flow-metrics-from-job-standard-component-the
https://help.qlik.com/talend/en-US/activity-monitoring-console-user-guide/8.0/customizing-meter-log-view
https://help.qlik.com/talend/en-US/activity-monitoring-console-user-guide/7.3/creating-files-or-database-tables
https://help.qlik.com/talend/en-US/activity-monitoring-console-user-guide/8.0/configuring-datasources-for-monitoring-console
https://help.qlik.com/talend/en-US/installation-guide-mac/8.0/talend-activity-monitoring-console-log-database
https://community.qlik.com/t5/Official-Support-Articles/How-to-create-AMC-tables-for-any-Talend-version-to-any-database/ta-p/2151033
https://help.qlik.com/talend/en-US/components/7.3/orchestration/twaitforfile-standard-properties
https://help.qlik.com/talend/en-US/components/7.2/orchestration/twaitforfile-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/orchestration/twaitforfile
https://community.qlik.com/t5/Talend-Studio/tWaitforFile-triggers-too-soon/m-p/2198170/highlight/true
https://help.qlik.com/talend/en-US/components/7.2/orchestration/tloop-standard-properties
https://help.qlik.com/talend/en-US/components/7.2/orchestration/tloop-properties-for-apache-spark-batch
https://help.qlik.com/talend/en-US/components/8.0/orchestration/tparallelize
https://help.qlik.com/talend/en-US/components/8.0/orchestration/tparallelize-tmsgbox-parallelizing-synchronizing-subjobs-execution-standard-component-enterprise-the
https://help.qlik.com/talend/en-US/studio-user-guide/7.3/context-settings
https://help.qlik.com/talend/en-US/studio-user-guide/8.0/context-settings
https://help.qlik.com/talend/en-US/data-integration-job-examples/8.0/configuring-implicit-context-load-feature
https://help.qlik.com/talend/en-US/components/8.0/context/tcontextload
https://help.qlik.com/talend/en-US/components/7.3/context/tcontextload-standard-properties
https://help.qlik.com/talend/r/en-US/8.0/components/context/tcontextdump
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-09/handling-errors
https://help.qlik.com/talend/en-US/administration-center-user-guide/8.0/accessing-error-recovery-management-page
https://help.qlik.com/talend/en-US/administration-center-user-guide/8.0/recovering-last-execution-of-task
https://help.qlik.com/talend/en-US/administration-center-user-guide/7.2/what-are-recovery-checkpoints
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-11/recovering-job-execution-in-case-of-failure
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-01/setting-checkpoints-on-trigger-connections
https://community.qlik.com/t5/Talend-Studio/Restartability-recovery-checkpoints-and-restart-the-job-from-the/td-p/2238974
https://help.qlik.com/talend/en-US/studio-user-guide/8.0/enabling-parallelization-of-data-flows
https://help.qlik.com/talend/en-US/components/7.2/orchestration/tdepartitioner
https://help.qlik.com/talend/en-US/studio-user-guide/7.3/launching-parallel-iterations-to-read-data
https://community.qlik.com/t5/Talend-Studio/Global-Map-and-Parallelization-and-Iteration/m-p/2377458/highlight/true
https://community.qlik.com/t5/Design-and-Development/List-of-components-routines-etc-failing-on-parallel-executions/td-p/2244771
https://community.qlik.com/t5/Talend-Studio/Multithread-iterate-and-tFlowIterate/m-p/2236199/highlight/true
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-04-and-earlier/executing-multiple-subjobs-in-parallel
https://help.qlik.com/talend/en-US/components/8.0/technical/thashoutput-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/technical/thashoutput-thashinput-tfixedflowinput-tlogrow-configuring-components-standard-component
https://help.qlik.com/talend/en-US/components/7.3/tfixedflowinput/tfixedflowinput-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/logs-and-errors/tlogrow-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/orchestration/tflowtoiterate
https://help.qlik.com/talend/en-US/components/8.0/orchestration/titeratetoflow
https://help.qlik.com/talend/en-US/components/7.3/orchestration/tflowtoiterate-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/orchestration/titeratetoflow-standard-properties
https://community.qlik.com/t5/Talend-Studio/Job-behavior-when-prejob-fails/m-p/2265637/highlight/true
https://community.qlik.com/t5/Talend-Studio/tPostJob-execution-when-error-in-active-job/td-p/2309099
https://community.qlik.com/t5/Talend-Studio/How-to-exit-job-from-tPreJob/td-p/2200430
https://community.qlik.com/t5/Design-and-Development/Parent-job-is-not-failing-even-after-Child-job-failure/td-p/2225622
https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2026-09/trigger-connections-for-job
https://help.qlik.com/talend/en-US/studio-user-guide/7.3/trigger-connections-for-job
https://help.qlik.com/talend/en-US/components/8.0/java-custom-code/tjavaflex
https://help.qlik.com/talend/en-US/components/7.3/java-custom-code/tjavaflex-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/java-custom-code/tjavaflex-tlogrow-configuring-tjavaflex-component-standard-component
https://help.qlik.com/talend/en-US/components/8.0/keystore/tsetkeystore-standard-properties
https://help.qlik.com/talend/en-US/components/7.3/keystore/tsetkeystore-standard-properties
https://help.qlik.com/talend/en-US/components/8.0/proxy/tsetproxy
https://help.qlik.com/talend/en-US/components/8.0/library-import/tlibraryload-standard-properties
https://help.qlik.com/talend/en-US/job-script-reference-guide/8.0/tlibraryload-example
https://community.qlik.com/t5/Talend-Studio/tLoadLibrary/m-p/2352107/highlight/true
https://www.oreilly.com/library/view/talend-open-studio/9781782167266/ch11s06.html
