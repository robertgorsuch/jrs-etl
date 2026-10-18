# ORDERS_LOAD: why it works in Studio but dies on the Linux server

Three separate symptoms, but they share one root cause family: an exported Talend job does **not** run in the same environment Studio runs it in. Different context, different working directory, different JVM/OS/charset, different (prod) data and often a different JDBC driver/DB. Below is what each symptom almost always means and how to fix it. Start with the context problem — it very likely explains at least part of the `NullPointerException` too.

---

## 0. What is different when ops run `ORDERS_LOAD_run.sh`

| In Studio | Exported zip on the server |
|---|---|
| Context = whatever is selected in the **Run** tab, with values you may have edited in that tab | Context = the one baked into the `.sh` by the export dialog (`--context=Default` unless you changed it), read from `ORDERS_LOAD/contexts/ORDERS_LOAD_<ctx>.properties` |
| Working directory = Studio install / workspace; Windows paths work | `.sh` does `cd` into the job folder; relative paths resolve from there; Windows paths (`C:\…`) and case-insensitive filenames stop working |
| Studio's bundled JDK, Windows charset (cp1252), Windows timezone/locale | Server JRE (possibly a different major version), UTF-8/POSIX locale, server TZ |
| Dev/test data, dev DB and the driver Studio has in its module cache | Prod data (with NULLs, BIGINTs, wider ranges), prod DB engine/version, the driver jar that ended up in `lib/` |
| Clean classpath | Whatever is in `lib/` — if ops unzip a new build **over** an old folder, old and new jars sit side by side |

Keep that table in mind; every fix below is one of those rows.

---

## 1. Context values are "wrong" on the server

### What is happening

`./ORDERS_LOAD_run.sh --context_param DB_HOST=prod-db` does exactly one thing: it overrides the single variable `DB_HOST`. **Every other context variable keeps the value from the context that is hard-wired in the script.** Open `ORDERS_LOAD_run.sh`; the last line looks like:

```sh
java -Xms256M -Xmx1024M -cp $ROOT_PATH/../lib/...:$ROOT_PATH/orders_load_0_1.jar \
     orders_load.ORDERS_LOAD --context=Default "$@"
```

`--context=Default` was chosen in the export dialog ("Context scripts" drop-down). So ops are running the **Default** (dev) context — dev `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, file paths, etc. — with only the host replaced. That is "the context values seem wrong".

Other things that make `--context_param` appear to do nothing:

1. **Name must match exactly** (case-sensitive, same spelling as in the job's Context tab). An unknown name is silently ignored; the job does not complain.
2. **Syntax**: `--context_param NAME=value` — a space between the flag and the pair, one flag per variable, quote values containing spaces/special characters: `--context_param "ORDER_DIR=/data/orders in/"`.
3. **The variable must exist in the *parent* job's context.** Variables that only live in a child job are not reachable from the command line unless the `tRunJob` has *Transmit whole context* checked (or you map them explicitly).
4. **Typed variables**: `Integer`/`Date`/`Boolean` context vars are parsed from the string. A value that does not parse (e.g. a date in the wrong pattern) ends up `null` — and that becomes an NPE later (see §2).
5. **An implicit/explicit `tContextLoad` runs *after* the command line and overwrites it.** If Project Settings → Job Settings → *Implicit Context Load* (or a `tContextLoad` in a pre-job) reads a properties file or a DB table, those values win over `--context_param`. On the server that file usually either does not exist at the dev path (so nothing is loaded and the Default values stay) or is a stale copy. Check `Print operations` / `Die on error` on that component — by default it fails silently.
6. **Empty value in the exported context**: if a variable has no value in the selected context (you only filled it in the Run tab in Studio), the properties file contains `DB_PORT=` → the typed parse returns `null`.

### Fix

Pick one of these (first is the cleanest):

- **Run the right context and only override what truly varies:**
  ```sh
  ./ORDERS_LOAD_run.sh --context=Prod --context_param DB_HOST=prod-db
  ```
  A second `--context=` on the command line overrides the one in the script (arguments are processed in order). The file `ORDERS_LOAD/contexts/ORDERS_LOAD_Prod.properties` must exist in the zip, which it does as long as the Prod context existed in the job when it was exported.
- **Or re-export with `Prod` selected** in the export dialog so the script itself says `--context=Prod`.
- **Or externalise the whole thing**: keep a server-side `ORDERS_LOAD_Prod.properties` (or a context table) and load it with `tContextLoad` in a pre-job with *Die on error* on, so a missing file is a loud failure, not a silent fall-back to dev values. Passwords in Talend 7.x/8.x `.properties` must be in the encrypted form Studio writes; put them there via Studio or pass them with `--context_param`.
- **Prove what the job sees**: temporarily add a `tContextDump` → `tLogRow` (or `tJava` with `System.out.println(context);`) as the very first subjob and run it once on the server. Every remaining issue below is much easier when you know the real context values.

Also make sure every variable the Prod run needs actually has a value in the **Prod** context in Studio (Contexts tab, not the Run tab) before exporting; values typed only into the Run tab are not exported.

---

## 2. `Exception in component tMap_2 (ORDERS_LOAD) java.lang.NullPointerException`

### What is happening

A tMap is generated Java. An NPE inside it means an **expression dereferenced a null**, and the only reason it is null on the server but not in Studio is that the inputs differ: prod data, prod lookups, or (very often) a context variable that is `null` because of §1.

Find the exact line first — do not guess. The stack trace continues with something like `at orders_load.ORDERS_LOAD.tDBInput_1Process(ORDERS_LOAD.java:4812)`. Open that line in `ORDERS_LOAD_0.1/ORDERS_LOAD/src/main/java/orders_load/ORDERS_LOAD.java` inside the zip (or Studio's *Code* tab, same code). It will be one of these patterns:

| Generated code at the failing line | Cause | Fix |
|---|---|---|
| `row1.CUSTOMER_NAME.trim()`, `.toUpperCase()`, `.substring(...)`, `.equals(...)`, `.getTime()` on an **input column** | Prod rows have NULL in that column; dev data did not | Null-guard the expression: `row1.CUSTOMER_NAME == null ? null : row1.CUSTOMER_NAME.trim()`, or `Relational.ISNULL(row1.X) ? ... : ...`. Prefer null-tolerant routines (`StringHandling.TRIM` etc.) only after checking they accept null. |
| `lookup.PRICE.doubleValue()` / `lookup.X.method()` where `lookup` is a tMap lookup flow | Left-outer join with no match → all lookup columns are `null`; prod has orders whose customer/product is missing in the lookup | Guard with `lookup.ID == null ? default : ...`, or switch the join to *Inner Join* and route non-matching rows to an *Inner join reject* output so they are reported instead of crashing. Check *Unique match / All matches* and that the lookup key types match (String vs Integer never match → everything null). |
| `int qty = row1.QTY;` / `row1.QTY.intValue()` / passing `row1.QTY` into a column of **primitive** type (`int`, `long`, `double`, `boolean`) | Schema column is primitive (Nullable unchecked). Unboxing a null Integer is an NPE. | In the schema set the type to the object type (`Integer`, `Long`, `Double`, `Boolean`) and tick **Nullable**; the DB input will then read NULL as `null` instead of failing. |
| `context.ORDER_DIR + "/..."` works, but `context.BATCH_SIZE.intValue()`, `context.CUTOFF_DATE.getTime()`, `context.REGION.equals(...)` | The context variable is `null` on the server: not in the selected context, misspelled in `--context_param`, empty in the properties file, overwritten by a failed implicit load — see §1 | Fix §1; additionally fail fast: a `tJava` in the pre-job that throws if any required context value is null. |
| `TalendDate.parseDate("yyyy-MM-dd", row1.ORDER_DATE)` or `Integer.parseInt(row1.X)` | Null (or differently formatted) string in prod | Guard for null; be aware default locale/timezone differ on Linux — pass an explicit pattern/locale. |
| `((String) globalMap.get("...")).something()` or `globalMap.get("tFileList_1_CURRENT_FILEPATH")` | The producing component did not run / produced nothing on the server (file path not found, earlier subjob skipped because of context) | Fix the path/context; check the `OnSubjobOk` vs `OnComponentOk` ordering. |

Two environmental tMap gotchas that are not expression bugs:

- **Store temp data** (tMap property for large lookups) with a *Temp data directory path* like `C:\Temp` → on Linux this fails when the lookup is written. Use a context variable with a Linux path (`/tmp/orders_load`) and make sure it exists.
- A tMap that reads a **routine** which itself depends on a Windows path, system property or charset.

### Make it fail usefully

- Turn on **Die on error** on the DB inputs and add `tLogCatcher` → `tLogRow`/`tDie` so the real exception and the offending row are logged, instead of `Exception in component tMap_2` with the job continuing or exiting with code 1 and nothing else.
- Put a `tLogRow` (or `tFilterRow` catching null keys to a reject file) just before `tMap_2` on the server run to see the row that kills it.

---

## 3. `java.lang.ClassCastException: java.lang.Long cannot be cast to java.lang.Integer` in `tJava_1`

### What is happening

Your `tJava_1` code contains, explicitly or implicitly, an `(Integer)` cast of something that is **typed `Object` at compile time** and turns out to be a `Long` at runtime. The classic shapes:

```java
Integer n = (Integer) globalMap.get("row2.ORDER_ID");          // set by tFlowToIterate / tSetGlobalVar
int count = (Integer) globalMap.get("tDBInput_2_NB_LINE");     // fine - NB_LINE is Integer
Integer lastId = (Integer) globalMap.get("tMysqlLastInsertId_1_LAST_INSERT_ID");  // this one IS Long
```

It works in Studio because against the dev database the value really is an `Integer`; on the server it is a `Long`. Why the type changes between environments:

1. **Different DB engine / column type / driver behaviour.** Any column read through `getObject()` (a schema column of type `Object`, a `Dynamic` schema, `tParseRecordSet`, `tDBRow` with "Propagate QUERY's recordset") gets the type the driver chooses: MySQL `BIGINT`, `INT UNSIGNED`, and the result of `COUNT(*)`/`SUM()`/`LAST_INSERT_ID()` are `Long`; PostgreSQL `bigint`/`count(*)` is `Long`; Oracle `NUMBER` is `BigDecimal`; H2/dev MySQL may hand back `Integer` for the same query. Prod tables are routinely `BIGINT` where the dev table was `INT`. Also, a newer/different `mysql-connector-java` jar in `lib/` can change the mapping (Connector/J 5.1 vs 8.x differ for unsigned ints).
2. **A value handed through `globalMap`** by `tFlowToIterate`, `tSetGlobalVar` or a `tJavaRow` whose *schema* column is `Long` (or was changed to `Long` to stop overflow in prod) while `tJava_1` still casts to `Integer`. Studio compiles `tJava` code only against what the code literally says; `globalMap` is `Map<String,Object>` so the mistake only shows at runtime with real data.
3. **Parent/child context type mismatch.** `tRunJob` mapping a `Long` parent context variable into an `Integer` child context variable (or the repository context group being `Integer` while the job's local copy is `Long`). Re-sync the job's context from the repository and make the types identical.
4. **Component globals that are `Long`**, not `Integer`: `tMysqlLastInsertId`/`tDBLastInsertId` output, `tFileProperties` `size`, `tStatCatcher`/`tFlowMeterCatcher` durations and counts, `tAggregateRow` `count` when the output column is `Long`. The `*_NB_LINE`, `*_NB_LINE_INSERTED/UPDATED/DELETED`, `tFileRowCount_COUNT`, `tLoop_CURRENT_VALUE` globals are `Integer`.

### Fix

Make the code type-agnostic instead of guessing the box type:

```java
Object o = globalMap.get("row2.ORDER_ID");
long orderId = o == null ? 0L : ((Number) o).longValue();   // works for Integer, Long, BigDecimal
```

and/or align the types end to end:

- Set the schema column to `Long` (or `BigDecimal` for Oracle NUMBER) in the DB input, in `tFlowToIterate`/`tSetGlobalVar`, and in `tJava_1`; or `CAST(... AS SIGNED INTEGER)` / `::int` in the SQL if the value genuinely fits in 32 bits.
- Replace `Object`/`Dynamic` schema columns on the path to `tJava_1` with explicit types; then Talend generates `rs.getLong(...)`/`rs.getInt(...)` and the driver's `getObject()` mapping no longer matters.
- Check which driver jar is actually in `<export>/lib/` on the server and that it is the one Studio used (Studio: *Modules* view). Deploy into an **empty** directory every time — unzipping over the previous release leaves two versions of the same jar on the classpath and whichever loads first wins.

---

## 4. Server-side checklist to hand to ops

1. **Clean deploy**: `rm -rf /opt/talend/ORDERS_LOAD && unzip ORDERS_LOAD_0.1.zip -d /opt/talend/ORDERS_LOAD`. Never unzip over an old build.
2. **JVM**: `java -version` on the server must be a version your Talend release compiled for (Talend 7.3 → Java 8/11; Talend 8 → Java 11/17). Mismatches give `UnsupportedClassVersionError`, not these errors, but confirm anyway.
3. **Run with the correct context**:
   ```sh
   cd /opt/talend/ORDERS_LOAD/ORDERS_LOAD_0.1/ORDERS_LOAD
   ./ORDERS_LOAD_run.sh --context=Prod --context_param DB_HOST=prod-db
   ```
   Verify `contexts/ORDERS_LOAD_Prod.properties` exists and contains every variable with a Prod value.
4. **Pin the runtime environment in the script** (edit the `java` line or set `JAVA_OPTS`): `-Dfile.encoding=UTF-8 -Duser.timezone=Europe/Paris -Duser.language=en -Duser.country=US` (whatever matches Studio) so date parsing and file encoding behave as they did in Studio; raise `-Xmx` if prod volumes are bigger.
5. **No Windows paths, no relative paths**: every file/temp path in a context variable, Linux-style, directories created with correct permissions for the ops user; filenames are case-sensitive.
6. **Capture the real error**: run once with a `tContextDump`→`tLogRow` at the start and `tLogCatcher`→`tLogRow` at the end, keep stdout/stderr in a log file, and read the `ORDERS_LOAD.java:<line>` from the stack trace against the code in `src/` of the same zip.

## 5. Summary

- **Wrong context values**: the script runs `--context=Default` and `--context_param` only overrides `DB_HOST`; everything else is still dev. Run `--context=Prod` (or re-export with Prod selected), make sure Prod values exist in the Contexts tab, and watch for an implicit `tContextLoad` or a typo/case mismatch that silently discards the override.
- **NPE in tMap_2**: an expression touches a null — a prod column/lookup that is NULL where dev data wasn't, a primitive (non-Nullable) schema type, or a context variable that is `null` because of the context problem. Locate the line in the generated `ORDERS_LOAD.java`, null-guard it, switch primitives to object types with Nullable ticked, and use inner-join rejects for missing lookups.
- **ClassCastException Long→Integer in tJava_1**: the value you cast with `(Integer)` is a `Long` on prod because the prod DB/driver returns `BIGINT`/`count(*)`/`LAST_INSERT_ID` as `Long` (or a `Long` global/context variable feeds it). Use `((Number) o).longValue()` or align the schema/context/variable types to `Long` end to end, and make sure only one JDBC driver version sits in `lib/`.
