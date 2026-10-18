# ORDERS_LOAD: why it works in Studio and dies on the Linux server

Short version: the three symptoms are almost certainly one root cause plus two latent design bugs that the wrong context exposes.

1. **Context values are wrong** because ops never select a context. `ORDERS_LOAD_run.sh` has `--context=Default` baked into it; `--context_param DB_HOST=prod-db` only patches one variable on top of the *Default* (DEV) context. Every other variable (DB_NAME, DB_PORT, DB_USER, DB_PASS, file paths...) is still the Default value.
2. **`tMap_2` NullPointerException** is a nullability bug in the job (a non-`Nullable` schema column, i.e. a Java primitive, receives `null`). It never fires in Studio because the DEV lookup data is complete; on the server the job connects to `prod-db` with DEV database/user/paths, so the lookup returns nothing (or PROD data simply contains nulls that DEV does not), and the first Left Outer Join miss unboxes `null` into an `int`.
3. **`ClassCastException: Long cannot be cast to Integer` in `tJava_1`** is a hard cast on a `globalMap` value whose real runtime type is `Long`. It is "sometimes" because the code path/data differ per run; the fix is a type-agnostic cast.

Fix the launch command first, then the two code bugs so the job fails loudly in Studio instead of in production.

---

## 1. Context values wrong on the server (operations issue)

### What is happening

The generated launcher looks like this (Studio 7.3 / 8.0):

```sh
#!/bin/sh
cd `dirname $0`
ROOT_PATH=`pwd`
java -Xms256M -Xmx1024M -cp .:$ROOT_PATH:$ROOT_PATH/../lib/routines.jar:...:$ROOT_PATH/orders_load_0_1.jar \
  <project>.orders_load_0_1.ORDERS_LOAD --context=Default "$@"
```

- `--context=Default` is the context chosen in the **Build Job** dialog at export time (also recorded as `contextName=` in `jobInfo.properties` at the zip root).
- `"$@"` appends whatever ops type. `--context_param DB_HOST=prod-db` overrides exactly one variable; all CLI values arrive as Strings and are parsed to the declared type.
- No `--context=PROD` was passed, so the job runs with `contexts/Default.properties` plus one patched host. That is why it "connects" to prod-db but with DEV database name / credentials / paths, and why values look wrong when printed.

Two more differences from Studio to be aware of:

- In Studio you run with whatever context is selected in the **Run view > Context** drop-down and with the values as they currently are in the Studio context group. The zip contains the values **as of the build**: a context edited after the export is not in the zip until you rebuild.
- If the project uses **Implicit Context Load** (Project Settings > Job Settings, or Job > Extra tab) from a file or DB, the file path / DSN must exist on the Linux host. If it does not, the job silently keeps the compiled-in defaults (only a warning, and `Disable warnings` may hide even that). Implicit load runs after CLI parsing; recent versions keep `--context_param` values for the keys you passed, so your `DB_HOST` survives but everything else comes from the file (or from nothing).

### How to fix

1. Pass the context explicitly. `--context` is case-sensitive and must match the context group name exactly; a later `--context` wins over the baked-in one:

   ```sh
   ./ORDERS_LOAD_run.sh --context=PROD --context_param DB_HOST=prod-db
   ```

   Each `--context_param` is one `name=value` argv element; quote it when the value has spaces (`--context_param "IN_DIR=/data/in dir"`). Values with `=` are fine (split on first `=` only).

2. Verify what the job actually received. Run once with the context printed (tContextDump to tLogRow, or a tJava with `System.out.println(context.toString())`, or `Print operations` on the implicit load), and check `contextStr` in the log. Do not leave password printing on in PROD.

3. Check the artifact: `jobInfo.properties` (`job`, `jobVersion`, `contextName`, `commandlineVersion`) and the bundled contexts under `<project>/orders_load_0_1/contexts/*.properties`. The helper in this skill does it without unzipping by hand:

   ```sh
   python3 plugins/talend-etl/skills/talend-etl/scripts/inspect_job_export.py ORDERS_LOAD_0.1.zip
   ```

   It lists the launcher, main class, JVM args, baked default context, which contexts are bundled, and the drivers in `lib/`. If `PROD` is not bundled, rebuild with **Build Job > Context scripts** including PROD (or all contexts), and choose the context you want as default.

4. Longer term, pick one promotion mechanism and stick to it:
   - Context group per environment (`DEV`/`TEST`/`PROD`) + `--context=` (simple, but secrets are inside the artifact, every change needs a rebuild).
   - `--context_param` for everything from the scheduler/TAC/TMC task (artifact is immutable, but passwords show in `ps -ef` and scheduler logs when run by hand; use TAC/TMC masked parameters or `enc:` values).
   - Implicit Context Load from a per-server file with restricted permissions; `Default` then holds only the config path.
   - Keep `Default` = safe DEV values so a forgotten `--context` cannot hit PROD, and keep `jobInfo.properties` `contextName` equal to the context you intend as default. Never hard-code hosts or credentials in components.

## 2. `Exception in component tMap_2 (ORDERS_LOAD) java.lang.NullPointerException` (design issue)

### What is happening

In generated Talend Java, a schema column of type Integer/Long/Double/Boolean/... with `Nullable` **unchecked** is a primitive (`int`, `long`...). The three classic ways to NPE inside a tMap:

- A **Left Outer Join lookup miss**: lookup columns are `null` for that row; mapping `lkp.region_id` into a non-nullable output column (or using it in an expression) unboxes `null` -> NPE.
- An **optional source column** that is null in the data but non-nullable in the schema.
- A **method call on a null String**: `row1.customer_code.trim()`, `row1.status.equals("A")`, `row1.x.toUpperCase()`.

Why Studio hides it: in DEV every order finds its customer/product in the lookup and the sample data has no nulls. On the server, with the wrong context, the lookup query runs against `prod-db` with DEV database/user (empty or different reference tables) or against real PROD volumes that contain nulls; the first miss kills the job. tMap is simply where the null is first dereferenced; the real culprit may be the input or lookup component upstream.

### How to fix

1. Find the exact expression. The stack trace line number refers to the generated `ORDERS_LOAD.java`. In Studio open the **Code** view, `Ctrl+L` to that line; the comment block above it names the component and the expression. (Build the same job version as the zip; the sources are not shipped in the zip.)
2. Make every lookup column you read and every optional source column **`Nullable`** in the schema editor (Integer instead of int). Do the same on the tMap output columns and on `Var` rows (a Var with `Nullable` unchecked is primitive too).
3. Guard expressions:

   ```java
   row2.region_id == null ? null : row2.region_id          // lookup miss (row2 == null is NOT a usable test)
   row1.customer_code == null ? null : row1.customer_code.trim()
   Relational.ISNULL(row1.status) ? "N" : row1.status
   "A".equals(row1.status)                                  // literal on the left is null-safe
   ```

   If a lookup match is mandatory, switch the join to **Inner Join** and send non-matching main rows to an **Inner Join Reject** output instead of letting them through with nulls.
4. Fail soft instead of dying: with Property Settings > `Die on error` unchecked on tMap_2, add an `ErrorReject` output; rows whose expressions throw go there with `errorMessage` / `errorStackTrace` instead of killing the Job. Also consider `tSchemaComplianceCheck` after the inputs. Note that `Die on error` on input/output components does not catch NPEs or ClassCastExceptions in tMap/tJava; those are uncaught Java exceptions.
5. Re-test in Studio with a context that reproduces the miss (clone the context group to a `DEBUG` context with read-only PROD-like reference data, or empty the lookup table in DEV). Never run `--context=PROD` from a workstation.

## 3. `java.lang.ClassCastException: java.lang.Long cannot be cast to java.lang.Integer` in `tJava_1` (design issue)

### What is happening

`globalMap` is `Map<String, Object>`; every read is a hard cast, e.g. `((Integer)globalMap.get("tDBOutput_1_NB_LINE"))`. Somewhere in tJava_1 the code casts to `Integer` a value that is actually a `Long`. Typical sources:

- A value put by another component whose type is `Long` (counts/ids from a DB `BIGINT`/`COUNT(*)`, `tDBLastInsertId`'s `last_insert_id`, a `tAggregateRow` sum declared Long, a `tFlowToIterate` / `tSetGlobalVar` entry from a Long column).
- A value stored in an `Object` or `Dynamic` column: the JDBC driver's `getObject()` decides the Java type at runtime, so a `BIGINT` on prod-db comes back as `Long` while the DEV table (or a different driver version in the zip's `lib/`) returned `Integer`. This is the most common reason the same code behaves differently per environment.
- The zip was built from a different job version than the one open in Studio (compare `jobVersion` in `jobInfo.properties` with the Studio job), so the server runs older code in which that variable had another type.
- It is "sometimes" because tJava_1 is only reached when tMap_2 does not blow up first, or because the branch that puts the value (RunIf / OnSubjobOk) only runs for some inputs; when the key is missing you get an NPE at unboxing instead.

### How to fix

1. Check the real type in Studio's **Outline** view (hover the variable; dragging it inserts the right cast) and in the component that does the `globalMap.put`.
2. Replace the hard cast with a type-agnostic, null-safe read:

   ```java
   Object o = globalMap.get("tDBOutput_1_NB_LINE");
   long n = (o == null) ? 0L : ((Number) o).longValue();        // works for Integer, Long, BigDecimal...
   // or
   long n = Long.parseLong(String.valueOf(globalMap.get("x")));  // throws on null/"null", so guard first
   ```

   If the consumer really needs `int`, use `((Number) o).intValue()` and make sure the value fits.
3. Declare the producing column as `Long` (`Nullable`) when the DB type is `BIGINT`/`NUMBER(19)`; use Long for row counts and ids > 2^31.
4. Rebuild the zip from the job version you actually tested, and bump the Job version (`m`/`M`) per release so `jobInfo.properties` tells you what is deployed.

## 4. Diff checklist: Studio vs server

Differences between a Studio run and a deployed run are environmental. Walk this list on the server:

| Check | Command / where | Why |
|---|---|---|
| Context in effect | add `--context=PROD`; print `contextStr` / `context.toString()` | root cause above |
| Baked default context, bundled contexts, job version | `jobInfo.properties`, `<project>/orders_load_0_1/contexts/`, `inspect_job_export.py` | stale build or missing PROD context |
| Java | `java -version` vs Studio's `Project Settings > Build > Java version` | a mismatch gives `UnsupportedClassVersionError`, not an NPE, but rule it out |
| Working directory and relative paths | the launcher does `cd` to its own folder; use `context.IN_DIR + "/file.csv"` | `FileNotFoundException` style failures |
| `lib/` drivers | `ls lib/` vs Studio `Modules` | different JDBC driver -> different `getObject` types |
| Implicit Context Load file / DB | exists and readable on the host? `Print operations` | silent fallback to defaults |
| Encoding / timezone | `LANG`, `-Dfile.encoding`, `-Duser.timezone` in cron env | data differences |
| Heap | `-Xmx1024M` default in launcher | PROD volumes in tMap lookups |

Reproduce by running the built launcher on your own machine with exactly the ops command before changing the job; once it fails locally the Code view line numbers match.

## 5. Recommended run command and design changes

Operations (cron / Control-M / wrapper script):

```sh
/opt/talend/jobs/ORDERS_LOAD/ORDERS_LOAD_run.sh --context=PROD \
  --context_param DB_HOST=prod-db \
  --context_param "DB_PASS=${DB_PASS}"        # or implicit context load / TAC-TMC masked param
echo "exit=$?"                               # 0 ok, 1 uncaught exception, tDie code (default 4)
```

Design (in Studio, then rebuild and redeploy a new version):

- `Nullable` on every lookup column and optional source column feeding `tMap_2`; null guards in expressions; Inner Join + reject where a match is mandatory; `ErrorReject` output on tMap_2.
- `((Number) globalMap.get(...)).longValue()` with a null guard in `tJava_1`; producer column typed `Long`.
- `Default` context = DEV-safe values; `PROD` context group complete; `contextName` in `jobInfo.properties` set deliberately at build; one documented override mechanism.
- Run `python3 plugins/talend-etl/skills/talend-etl/scripts/inspect_job_item.py ORDERS_LOAD_0.1.item --review` on the job's `.item` to get the nullability and context findings listed automatically before the next build.

Version note: the above holds for Standard (DI) jobs built with Studio 7.3 or 8.0 standalone zips; TAC Job Conductor and TMC tasks pass the same `--context` / `--context_param` through their task settings. If this is a Big Data (Spark) job, tMap null and globalMap semantics differ; check `Help > About` and tell me the Studio release if anything here does not match what you see.
