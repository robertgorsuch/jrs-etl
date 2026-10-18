# ORDERS_LOAD: why it works in Studio but dies on the Linux server

## The short version

The three symptoms are almost certainly one root cause plus two latent bugs it exposes:

1. **Wrong context values on the server.** `./ORDERS_LOAD_run.sh --context_param DB_HOST=prod-db` does *not* select your Prod context. The exported run script hard-codes `--context=Default` (or whichever context was selected in the Build Job dialog), so the job starts with the **Default/Dev** values for every variable and then overrides exactly one of them, `DB_HOST`. Everything else (port, schema, user, password, file paths, batch sizes, flags...) is still Dev. Fix: pass `--context=Prod` (or bake it into the script / rebuild with the Prod context selected).
2. **`NullPointerException` in `tMap_2`.** A tMap expression dereferences or unboxes something that is null on the server but never null in Studio: a nullable input/lookup column, an unmatched left-outer-join lookup row, or a context variable that is empty in the context the server is actually using (see 1). Fix: make the expressions null-safe and fix the schema Nullable flags.
3. **`ClassCastException: Long cannot be cast to Integer` in `tJava_1`.** Hand-written code does an unchecked cast like `(Integer) globalMap.get(...)` or `(Integer) row.someCol` and, on the server, the object is a `java.lang.Long`. The difference comes from the environment (prod DB/driver returns `BIGINT`/`COUNT(*)` as Long, or a context variable typed differently), or from a stale/different build. Fix: never cast blindly; go through `Number`.

Details, diagnosis steps, and fixes for each follow.

---

## 1. Context values are wrong on the server

### What is happening

Open the script ops are running. A Talend-exported launcher looks like this:

```sh
#!/bin/sh
cd `dirname $0`
ROOT_PATH=`pwd`
java -Xms256M -Xmx1024M -cp .:$ROOT_PATH:$ROOT_PATH/../lib/routines.jar:$ROOT_PATH/../lib/<drivers>.jar:$ROOT_PATH/orders_load_0_1.jar \
     <project>.orders_load_0_1.ORDERS_LOAD --context=Default "$@"
```

Key facts about how the generated job parses that command line:

- `--context=<name>` selects which context *group* of values to load. The values for every context are compiled into the job jar as `<project>/orders_load_0_1/contexts/<ContextName>.properties` at build time. If you do not pass `--context=...`, whatever is hard-coded in the script wins (`Default` unless you changed the "Context scripts" dropdown in the Build Job dialog).
- `--context_param NAME=value` overrides **one** variable, *after* the context file has been loaded. It is not a way of choosing a context.
- In Studio you never notice this because the Run tab has its own context selector and you presumably had Prod (or had Dev values that happened to work with your dev DB).

So on the server the job runs with Dev values for everything except `DB_HOST`. That alone explains "the context values seem wrong", and it can easily cascade into the other two errors (dev credentials against a prod host, dev file paths that do not exist on the server, numeric context vars that are empty in Default, etc.).

Other gotchas that bite here:

- **Context name is case-sensitive** and must match exactly the name in Studio (`Prod` vs `PROD` vs `production`). If the name is not found, the job prints a warning and falls back to the default values. It does *not* fail.
- **Unknown `--context_param` names are silently ignored.** A typo (`DB_host`) produces no error; the variable just keeps its baked-in value.
- Syntax is `--context_param NAME=value` (space between `--context_param` and `NAME`, no spaces around `=`). Each variable needs its own `--context_param`. Quote values containing spaces or shell metacharacters: `--context_param "FILE_DIR=/data/in bound"`.
- **Implicit context load** (Job > Extra > "Implicit tContextLoad", or an explicit `tContextLoad`) runs *after* the command-line parsing and **overrides** whatever you passed. If the job is configured to read contexts from a file or table, the path/connection it uses may itself be a Dev value or not exist on the server. Check the job's Extra tab and any tContextLoad components.
- **Context values are frozen at build time.** Editing the context group in the repository after exporting changes nothing on the server until you rebuild and redeploy the zip.
- **Password-type variables**: the values in the properties files are stored encrypted; passing them via `--context_param DB_PASS=secret` in plain text is fine, and is the usual way to keep prod secrets out of the build.

### Fix

Pick one:

- **Pass the context explicitly** (later `--context=` arguments win over the one in the script):
  ```sh
  ./ORDERS_LOAD_run.sh --context=Prod --context_param DB_HOST=prod-db
  ```
- **Edit the script** so ops cannot forget: change `--context=Default` to `--context=Prod` in `ORDERS_LOAD_run.sh`.
- **Rebuild correctly**: in Studio, right-click the job > Build Job, tick "Context scripts" and choose `Prod` in the context dropdown, then redeploy the zip. Also tick "Apply context to children" if you have tRunJob child jobs, otherwise children keep running with their own default context.

### Verify

Add a `tJava` at the start of the job (or in tPreJob) with:

```java
System.out.println("Running with context: " + contextStr);
System.out.println(context);          // context extends Properties; prints every variable
```

Run it once on the server. If a value is wrong you will see it immediately. Remove it or guard it with a `DEBUG` context var afterwards (passwords print too).

---

## 2. `NullPointerException` in `tMap_2`

### What is happening

tMap expressions compile to plain Java. The NPE comes from one of these patterns, and prod data / prod contexts hit the null where dev data did not:

| Pattern in tMap | Why it throws |
|---|---|
| `row1.customer_name.trim()`, `.toUpperCase()`, `.equals("X")`, `.length()` | the String is null for some rows |
| `row1.qty * row1.unit_price`, `row1.qty > 0`, `row1.qty + 1` | `qty` is `Integer`/`Long`/`BigDecimal` and null; the arithmetic unboxes it |
| output column typed `int`/`long`/`double` (Nullable unchecked) fed from a nullable source | assigning `null` to a primitive unboxes and throws |
| `lookup.region.toUpperCase()` with a **Left Outer Join** lookup | no match in the lookup, so every lookup column is null for that row |
| `context.DEFAULT_WAREHOUSE.trim()`, `context.BATCH_SIZE * 2` | the variable is empty in the context actually loaded on the server (see section 1); an empty Integer/Long/Date context value becomes `null` |
| `TalendDate.formatDate("yyyy-MM-dd", row1.order_date)` | `order_date` is null |

In Studio you ran against a dev database where every order had a customer, every lookup matched and every column was populated. On the server the join does not match, columns are null, or the context var is empty.

### Find the exact expression

- Look at the full stack trace in the server log, not just the first line. It contains a frame like `at myproject.orders_load_0_1.ORDERS_LOAD.tDBInput_1Process(ORDERS_LOAD.java:2873)`. Open the generated code (Studio > job > Code tab, or the `src` folder in the zip if "Include Java sources" was ticked) at that line; it is the tMap expression that failed.
- Alternatively, in Studio switch the Run tab to the Prod context (or point Dev at a copy of prod data) and use Debug Run / Traces on tMap_2.

### Fix

- Make expressions null-safe:
  ```java
  row1.customer_name == null ? "" : row1.customer_name.trim()
  Relational.ISNULL(row1.qty) ? 0 : row1.qty * row1.unit_price
  StringHandling.LEN(row1.code) > 0            // null-safe routine
  ```
  Use the built-in routines (`Relational.ISNULL`, `StringHandling.*`, `TalendDate.*`) where possible; they mostly tolerate nulls.
- Fix schemas: tick **Nullable** on every input and output column that can legitimately be null (which turns `int` into `Integer`, etc.), or supply a default in the expression. Note that tDBInput with Nullable unchecked throws a different error ("Null value in non-Nullable column"), so the NPE inside tMap points at an expression or a primitive output column, not the reader.
- For lookups with Left Outer Join, guard every lookup column, or switch to Inner Join and route the unmatched rows to a reject flow ("Catch lookup inner join reject").
- For context variables, either give them values in every context (Default included) or guard them, and pass the right context (section 1).
- Optionally untick **Die on error** on tMap_2 and connect an error-reject output so a bad row is logged rather than killing the load. Do this in addition to, not instead of, fixing the expression.

---

## 3. `ClassCastException: java.lang.Long cannot be cast to java.lang.Integer` in `tJava_1`

### What is happening

Somewhere in tJava_1 there is an unchecked cast, typically one of:

```java
Integer n = (Integer) globalMap.get("tDBInput_2_NB_LINE");        // or some other *_NB_LINE / *_COUNT
Integer total = (Integer) globalMap.get("orderCount");           // set earlier by tSetGlobalVar / tJavaRow
int id = (Integer) row2.order_id;                                 // row field via globalMap or Object column
```

The Java compiler lets an `Object -> Integer` cast through; the check happens at runtime. In Studio the object really was an `Integer`; on the server it is a `Long`. Studio-vs-server differences that produce exactly this:

- **Different database or JDBC driver.** `COUNT(*)`, `SUM(...)`, `BIGINT`/`BIGSERIAL`/`NUMBER(19)` columns come back as `Long` (PostgreSQL, MySQL Connector/J, SQL Server) while a dev DB (H2, SQLite, a different driver version, a column that is `INT` in dev and `BIGINT` in prod) returns `Integer`. This matters whenever the value reaches Java as `Object`: `tSetGlobalVar`, `tJavaRow` into `globalMap`, an `Object`-typed schema column, `tParseRecordSet`, or `rs.getObject()` in custom code. (Columns typed `Integer` in a tDBInput schema are read with `getInt()` and are safe.)
- **A context variable typed `Long`** (or `Object`) in the context group while the code assumes `Integer` -- for example a `BATCH_SIZE` that someone changed to Long in the repository and the job was rebuilt, but the `tJava` code was not updated.
- **Stale or differently built artifact.** The zip on the server was built from a different job revision, or by a different Studio/CommandLine/CI version than the one you are testing in, so component return variables or schema types differ. Compare the job version/build timestamp in the jar `MANIFEST.MF` with Studio and rebuild from the same source.
- (Less likely but worth checking) a different Java version on the server. Talend 7.x jobs target Java 8/11, Talend 8 targets 11/17. Match the Studio JRE; mismatches cause other classes of error, not usually this one, but it is cheap to rule out with `java -version`.

### Fix

Make the code type-tolerant instead of guessing the wrapper class:

```java
Object o = globalMap.get("tDBInput_2_NB_LINE");
int count = (o == null) ? 0 : ((Number) o).intValue();     // works for Integer, Long, BigDecimal, BigInteger

// or, if the value can be text (e.g. came from a context or a String column):
long total = Long.parseLong(String.valueOf(globalMap.get("orderCount")).trim());
```

Also:

- Declare the column type explicitly in the schema that feeds the value (make it `Long` if it is a `BIGINT`/aggregate) rather than leaving it `Object`.
- If a context variable is involved, align its type in the context group with the code, or read it via `((Number) context.BATCH_SIZE).intValue()` style access only when its type is Object; for a typed var just use `context.BATCH_SIZE` directly and let the compiler enforce the type.
- Rebuild and redeploy the zip after the change; a jar on the server never changes until you do.

---

## Recommended order of operations

1. Fix the launch: `./ORDERS_LOAD_run.sh --context=Prod --context_param DB_HOST=prod-db` (or bake `--context=Prod` into the script / rebuild with the Prod context). Print `context` once to confirm every variable.
2. Re-run. Some or all of the NPE/ClassCast errors may disappear because the job is now using prod connection details, file paths and non-empty context values.
3. For whatever remains, pull the full stack trace, map the line number to the generated code, and apply the null-safe tMap expressions and `Number`-based casts above.
4. Rebuild from the exact job version you tested in Studio, with "Context scripts" set to Prod and "Apply context to children" ticked, and redeploy. Keep prod secrets out of the build by passing them with `--context_param`.
5. Make sure the server's Java major version matches the Studio that built the job, and that the JDBC driver jars in `lib/` are the ones you tested with.
