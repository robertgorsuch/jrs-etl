#!/usr/bin/env python3
"""Inspect a Talend Studio job/joblet/route ``.item`` file without Studio.

Reads the XMI (``talendfile:ProcessType``) that Studio stores for a Job and
prints a human-readable summary: contexts, job-level settings, components with
their meaningful settings and schemas, connections (rows / lookups / triggers),
tMap internals (lookup and match modes, join keys, Var table, output filters),
subjobs, notes and a design-review checklist.

Usage::

    inspect_job_item.py JOB_0.1.item                 # markdown summary
    inspect_job_item.py JOB_0.1.item --format json   # machine readable
    inspect_job_item.py JOB_0.1.item --format dot    # graphviz digraph
    inspect_job_item.py JOB_0.1.item --review        # add the review checklist
    inspect_job_item.py JOB_0.1.item --all-params    # every elementParameter

Standard library only (xml.etree). Tested on a hand-built Studio-8-shaped
fixture (../fixtures/LOAD_CUSTOMERS_0.1.item); the XML vocabulary follows
references/artifact-formats.md. Unknown elements are ignored, never fatal.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict

XMI = "{http://www.omg.org/XMI}"
XSI = "{http://www.w3.org/2001/XMLSchema-instance}"

# connectorName -> human kind. lineStyle is a fallback only (ordinal of the
# Studio EConnectionType enum; values differ between releases, so the
# connectorName is authoritative when present).
CONNECTOR_KIND = {
    "FLOW": "row",
    "MAIN": "row",
    "LOOKUP": "lookup",
    "REJECT": "reject",
    "REJECTS": "reject",
    "OUTPUT": "row",
    "FILTER": "row",
    "UNIQUE": "row",
    "UNIQUES": "row",
    "DUPLICATES": "row",
    "MERGE": "row",
    "ITERATE": "iterate",
    "RUN_IF": "trigger",
    "COMPONENT_OK": "trigger",
    "COMPONENT_ERROR": "trigger",
    "SUBJOB_OK": "trigger",
    "SUBJOB_ERROR": "trigger",
    "SYNCHRONIZE": "trigger",
    "PARALLELIZE": "trigger",
    "RUN_AFTER": "trigger",
    "STARTS": "trigger",
    "ROUTE": "route",
    "ROUTE_WHEN": "route",
    "ROUTE_OTHER": "route",
    "ROUTE_TRY": "route",
    "ROUTE_CATCH": "route",
    "ROUTE_FINALLY": "route",
    "ROUTE_ENDBLOCK": "route",
}
TRIGGER_LABEL = {
    "RUN_IF": "RunIf",
    "RUN_AFTER": "RunAfter",
    "COMPONENT_OK": "OnComponentOk",
    "COMPONENT_ERROR": "OnComponentError",
    "SUBJOB_OK": "OnSubjobOk",
    "SUBJOB_ERROR": "OnSubjobError",
    "SYNCHRONIZE": "Synchronize",
    "PARALLELIZE": "Parallelize",
}
# lineStyle = ordinal of org.talend.core.model.process.EConnectionType (confirmed from
# Talend source; see references/artifact-formats.md). Lookups into tMap are written
# connectorName="FLOW" with lineStyle 8, so lineStyle is what distinguishes them.
LOOKUP_LINESTYLE = "8"
LINESTYLE_KIND = {
    "0": "row", "1": "trigger", "2": "trigger", "3": "trigger", "4": "trigger", "5": "trigger",
    "6": "trigger", "7": "iterate", "8": "lookup", "9": "row", "10": "row", "11": "row",
    "12": "trigger", "13": "trigger", "14": "route", "15": "route", "16": "route", "17": "route",
    "18": "route", "19": "route", "20": "route", "21": "trigger", "22": "row",
}
LINESTYLE_NAME = {
    "1": "SUBJOB_OK", "2": "RUN_AFTER", "3": "COMPONENT_OK", "4": "SUBJOB_ERROR", "5": "COMPONENT_ERROR",
    "6": "RUN_IF", "7": "ITERATE", "8": "LOOKUP", "9": "TABLE", "10": "MERGE", "12": "SYNCHRONIZE",
    "13": "PARALLELIZE", "14": "ROUTE", "15": "ROUTE_WHEN", "16": "ROUTE_OTHER", "17": "ROUTE_TRY",
    "18": "ROUTE_CATCH", "19": "ROUTE_FINALLY", "20": "ROUTE_ENDBLOCK",
}

# Parameters that are UI noise; hidden unless --all-params.
NOISE_PARAMS = {
    "UNIQUE_NAME", "LABEL", "HINT", "CONNECTION_FORMAT", "ACTIVATE",
    "START", "STARTABLE", "SUBTREE_START", "END_OF_FLOW", "DUMMY",
    "REPOSITORY_ALLOW_AUTO_SWITCH", "UPDATE_COMPONENTS", "IREPORT_PATH",
    "SCHEMA", "SCHEMA_TYPE", "PROPERTY", "PROPERTY_TYPE", "QUERYSTORE",
    "QUERYSTORE_TYPE", "REPOSITORY_QUERYSTORE_TYPE", "REPOSITORY_SCHEMA_TYPE",
    "REPOSITORY_PROPERTY_TYPE", "LOG4J_ACTIVATE", "TSTATCATCHER_STATS",
    "DB_COMMIT_EVERY", "VALIDATION_RULE_TYPE", "VALIDATION_RULE_TYPE:VALIDATION_RULE_TYPE",
    "COMPONENT_ENCODING", "DESTINATION", "INFORMATION", "NOT_SYNCHRONIZED_SCHEMA",
    "PARALLELIZE", "PARALLELIZE_NUMBER", "PARALLELIZE_KEEP_EMPTY",
}
NOISE_FIELDS = {"TECHNICAL", "ICON_SELECTION"}

# For the summary table: parameters worth surfacing per component family.
KEY_PARAMS = [
    "DB_TYPE", "DB_VERSION", "HOST", "PORT", "DBNAME", "SCHEMA_DB", "TABLE",
    "TABLE_ACTION", "DATA_ACTION", "QUERY", "USE_EXISTING_CONNECTION",
    "CONNECTION", "DIE_ON_ERROR", "USE_BATCH_SIZE", "BATCH_SIZE", "COMMIT_EVERY",
    "FILENAME", "DIRECTORY", "FILEMASK", "FIELDSEPARATOR", "ROWSEPARATOR",
    "HEADER", "CSV_OPTION", "ENCODING", "PROCESS", "PROCESS:PROCESS_TYPE_PROCESS",
    "PROCESS:PROCESS_TYPE_CONTEXT", "PROCESS:PROCESS_TYPE_VERSION",
    "TRANSMIT_WHOLE_CONTEXT", "USE_INDEPENDENT_PROCESS", "DIE_ON_CHILD_ERROR",
    "MESSAGE", "CODE", "EXIT_JVM", "CONDITION", "BASIC_MODE", "URL", "METHOD",
    "ENDPOINT", "TOPIC", "BUCKET", "KEY", "SQLQUERY", "LOOKUP_MODE",
]

REDACT_FIELDS = {"PASSWORD"}


class ItemError(Exception):
    pass


# --------------------------------------------------------------------------- parse

def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _params(elem) -> "OrderedDict[str, dict]":
    """Collect direct elementParameter children (and TABLE rows) of elem."""
    out: "OrderedDict[str, dict]" = OrderedDict()
    for p in elem.findall("elementParameter"):
        name = p.get("name", "")
        field = p.get("field", "")
        entry = {"field": field, "value": p.get("value")}
        if field == "TABLE":
            rows = []
            cur: "OrderedDict[str, str]" = OrderedDict()
            first_ref = None
            for ev in p.findall("elementValue"):
                ref = ev.get("elementRef", "")
                if first_ref is None:
                    first_ref = ref
                elif ref == first_ref and cur:
                    rows.append(cur)
                    cur = OrderedDict()
                cur[ref] = ev.get("value")
            if cur:
                rows.append(cur)
            entry["rows"] = rows
        children = p.findall("elementParameter")
        if children:
            entry["children"] = {c.get("name"): c.get("value") for c in children}
        out[name] = entry
    return out


def _columns(meta) -> list:
    cols = []
    for c in meta.findall("column"):
        cols.append({
            "name": c.get("name"),
            "type": (c.get("type") or "").replace("id_", ""),
            "key": c.get("key") == "true",
            "nullable": c.get("nullable") != "false",
            "length": c.get("length"),
            "precision": c.get("precision"),
            "pattern": c.get("pattern") or "",
            "default": c.get("defaultValue") or "",
            "comment": c.get("comment") or "",
        })
    return cols


def _mapper(nodedata) -> dict:
    def entries(t):
        return [{k: v for k, v in e.attrib.items()} for e in t.findall("mapperTableEntries")]
    m = {"inputs": [], "vars": [], "outputs": []}
    for t in nodedata.findall("inputTables"):
        m["inputs"].append({
            "name": t.get("name"),
            "lookupMode": t.get("lookupMode"),
            "matchingMode": t.get("matchingMode"),
            "innerJoin": t.get("innerJoin") == "true",
            "expressionFilter": t.get("expressionFilter") if t.get("activateExpressionFilter") == "true" else None,
            "joinKeys": [e for e in entries(t) if e.get("expression")],
            "columns": [e.get("name") for e in entries(t)],
        })
    for t in nodedata.findall("varTables"):
        m["vars"].extend(entries(t))
    for t in nodedata.findall("outputTables"):
        m["outputs"].append({
            "name": t.get("name"),
            "reject": t.get("reject") == "true",
            "rejectInnerJoin": t.get("rejectInnerJoin") == "true",
            "expressionFilter": t.get("expressionFilter") if t.get("activateExpressionFilter") == "true" else None,
            "columns": entries(t),
        })
    return m


def parse_item(path: str) -> dict:
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        raise ItemError(f"not well-formed XML: {exc}") from exc
    root = tree.getroot()
    if _local(root.tag) != "ProcessType":
        raise ItemError(f"root element is {_local(root.tag)}, expected talendfile:ProcessType "
                        "(is this a job .item? contexts/metadata/routines use other roots)")

    job: dict = {
        "file": os.path.basename(path),
        "jobType": root.get("jobType") or "Standard",
        "framework": root.get("framework"),
        "defaultContext": root.get("defaultContext"),
        "contexts": [],
        "parameters": {},
        "routines": [],
        "components": [],
        "connections": [],
        "subjobs": [],
        "notes": [],
    }

    for ctx in root.findall("context"):
        job["contexts"].append({
            "name": ctx.get("name"),
            "params": [{
                "name": p.get("name"), "type": (p.get("type") or "").replace("id_", ""),
                "value": p.get("value"), "prompt": p.get("promptNeeded") == "true",
                "repositoryContextId": p.get("repositoryContextId"), "comment": p.get("comment") or "",
            } for p in ctx.findall("contextParameter")],
        })

    params_elem = root.find("parameters")
    if params_elem is not None:
        job["parameters"] = {k: v["value"] for k, v in _params(params_elem).items()}
        job["routines"] = [r.get("name") for r in params_elem.findall("routinesParameter")]

    for n in root.findall("node"):
        p = _params(n)
        comp = {
            "name": p.get("UNIQUE_NAME", {}).get("value") or "?",
            "type": n.get("componentName"),
            "version": n.get("componentVersion"),
            "label": p.get("LABEL", {}).get("value"),
            "active": p.get("ACTIVATE", {}).get("value", "true") != "false",
            "pos": (n.get("posX"), n.get("posY")),
            "params": p,
            "schemas": [],
            "mapper": None,
        }
        if comp["label"] in (None, "", "__UNIQUE_NAME__"):
            comp["label"] = comp["name"]
        for meta in n.findall("metadata"):
            comp["schemas"].append({
                "connector": meta.get("connector"), "name": meta.get("name"),
                "label": meta.get("label"), "columns": _columns(meta),
            })
        nd = n.find("nodeData")
        if nd is not None and "MapperData" in (nd.get(XSI + "type") or ""):
            comp["mapper"] = _mapper(nd)
        job["components"].append(comp)

    for c in root.findall("connection"):
        p = _params(c)
        connector = c.get("connectorName") or ""
        style = c.get("lineStyle") or ""
        if connector in CONNECTOR_KIND:
            kind = CONNECTOR_KIND[connector]
        else:
            kind = LINESTYLE_KIND.get(style, "row")
            connector = connector or LINESTYLE_NAME.get(style, "")
        if connector in ("FLOW", "MAIN") and style == LOOKUP_LINESTYLE:
            kind = "lookup"
        job["connections"].append({
            "name": p.get("UNIQUE_NAME", {}).get("value") or c.get("label"),
            "label": c.get("label"),
            "connector": connector,
            "kind": kind,
            "lineStyle": c.get("lineStyle"),
            "source": c.get("source"),
            "target": c.get("target"),
            "metaname": c.get("metaname"),
            "condition": p.get("CONDITION", {}).get("value"),
            "parallel": p.get("ENABLE_PARALLEL", {}).get("value") == "true",
            "parallelN": p.get("NUMBER_PARALLEL", {}).get("value"),
        })

    for s in root.findall("subjob"):
        p = _params(s)
        job["subjobs"].append({
            "start": p.get("UNIQUE_NAME", {}).get("value"),
            "title": p.get("SUBJOB_TITLE", {}).get("value") or "",
        })
    for note in root.findall("note"):
        job["notes"].append(note.get("text") or "")

    props = _sibling_properties(path)
    if props:
        job["properties"] = props
    return job


def _sibling_properties(item_path: str) -> dict | None:
    base = item_path[:-5] if item_path.endswith(".item") else item_path
    pp = base + ".properties"
    if not os.path.exists(pp):
        return None
    try:
        root = ET.parse(pp).getroot()
    except ET.ParseError:
        return None
    out = {}
    for el in root.iter():
        if _local(el.tag) == "Property":
            for k in ("label", "version", "purpose", "description", "statusCode",
                      "creationDate", "modificationDate", "id"):
                if el.get(k):
                    out[k] = el.get(k)
        if _local(el.tag) == "ItemState" and el.get("path") is not None:
            out["folder"] = el.get("path")
    return out


# --------------------------------------------------------------------------- analysis

def unresolved_context_refs(job: dict) -> list:
    declared = set()
    for ctx in job["contexts"]:
        declared.update(p["name"] for p in ctx["params"])
    used = set()
    pat = re.compile(r"\bcontext\.([A-Za-z_][A-Za-z0-9_]*)")
    for comp in job["components"]:
        for p in comp["params"].values():
            for v in _param_values(p):
                used.update(pat.findall(v))
        if comp["mapper"]:
            for t in comp["mapper"]["inputs"]:
                for e in t["joinKeys"]:
                    used.update(pat.findall(e.get("expression") or ""))
                used.update(pat.findall(t.get("expressionFilter") or ""))
            for t in comp["mapper"]["outputs"]:
                for e in t["columns"]:
                    used.update(pat.findall(e.get("expression") or ""))
                used.update(pat.findall(t.get("expressionFilter") or ""))
            for e in comp["mapper"]["vars"]:
                used.update(pat.findall(e.get("expression") or ""))
    for v in job["parameters"].values():
        used.update(pat.findall(v or ""))
    return sorted(used - declared)


def _param_values(p: dict):
    if p.get("value"):
        yield p["value"]
    for row in p.get("rows", []):
        for v in row.values():
            if v:
                yield v
    for v in (p.get("children") or {}).values():
        if v:
            yield v


def review(job: dict) -> list:
    """Return (severity, message) findings. Heuristic, not a linter."""
    f = []
    by_name = {c["name"]: c for c in job["components"]}
    types = [c["type"] for c in job["components"] if c["active"]]

    def pv(comp, key, default=None):
        return comp["params"].get(key, {}).get("value", default)

    # context / secrets
    missing = unresolved_context_refs(job)
    if missing:
        f.append(("ERROR", f"context variables used but not declared in any context: {', '.join(missing)}"))
    for ctx in job["contexts"]:
        for p in ctx["params"]:
            if p["type"] == "Password" and p["value"] and not p["value"].startswith("enc:"):
                f.append(("WARN", f"context {ctx['name']}.{p['name']} is a Password stored in clear text"))
    for comp in job["components"]:
        for k, p in comp["params"].items():
            if p["field"] == "PASSWORD" and p.get("value") and "context." not in p["value"] and "globalMap" not in p["value"]:
                f.append(("WARN", f"{comp['name']}: password parameter {k} is not a context variable"))
            for v in _param_values(p):
                if re.search(r'^"(?:[A-Za-z]:\\\\|/)[^"]+"$', v) and k not in ("ROWSEPARATOR", "FIELDSEPARATOR"):
                    f.append(("WARN", f"{comp['name']}.{k}: hard-coded absolute path {v} (prefer a context variable)"))
                if re.search(r'"(?:jdbc:|https?://)[^"]+"', v):
                    f.append(("INFO", f"{comp['name']}.{k}: hard-coded URL {v}"))

    # execution safety
    if job["parameters"].get("MULTI_THREAD_EXECATION") == "true":
        f.append(("INFO", "Multi thread execution is ON: subjobs without trigger links run concurrently; globalMap handoffs between them are unsafe"))
    for c in job["connections"]:
        if c["kind"] == "iterate" and c["parallel"]:
            f.append(("INFO", f"iterate link {c['name']} runs {c['parallelN']} parallel executions: check routines/sequences/shared connections for thread safety"))

    # DB hygiene
    conns = [c for c in job["components"] if c["type"].endswith("Connection") and c["active"]]
    closes = {pv(c, "CONNECTION") for c in job["components"] if c["type"].endswith("Close") and c["active"]}
    commits = {pv(c, "CONNECTION") for c in job["components"] if c["type"].endswith("Commit") and c["active"]}
    for c in conns:
        if c["type"].startswith("tDB") or re.match(r"t[A-Z][A-Za-z]+Connection$", c["type"]):
            if c["name"] not in closes and pv(c, "AUTO_COMMIT", "false") != "true":
                if c["name"] not in commits:
                    f.append(("WARN", f"{c['name']}: connection has neither a tDBCommit nor a tDBClose using it (auto-commit off)"))
                else:
                    f.append(("INFO", f"{c['name']}: no tDBClose for this connection (use tPostjob -> tDBClose)"))
    for c in job["components"]:
        if not c["active"]:
            continue
        if c["type"] in ("tDBOutput",) or re.match(r"t[A-Z][A-Za-z]+Output$", c["type"]):
            if pv(c, "DIE_ON_ERROR", "true") == "false" and not any(x["source"] == c["name"] and x["kind"] == "reject" for x in job["connections"]):
                f.append(("WARN", f"{c['name']}: Die on error is off but no reject link captures failed rows"))
            if pv(c, "DATA_ACTION") in ("INSERT_OR_UPDATE", "UPDATE_OR_INSERT"):
                f.append(("INFO", f"{c['name']}: {pv(c, 'DATA_ACTION')} issues 2 statements per row; consider staging + MERGE/tDBRow for volume"))
            if pv(c, "USE_BATCH_SIZE") == "true" and any(x["source"] == c["name"] and x["kind"] == "reject" for x in job["connections"]):
                f.append(("WARN", f"{c['name']}: batch mode plus a reject link - Studio disables batching when rejects are caught"))
        if c["type"] in ("tDBInput",) or re.match(r"t[A-Z][A-Za-z]+Input$", c["type"]):
            q = pv(c, "QUERY") or ""
            if re.search(r"\bselect\s+\*", q, re.I):
                f.append(("INFO", f"{c['name']}: SELECT * - schema drift will break the job silently"))
        if c["type"] == "tLogRow":
            f.append(("INFO", f"{c['name']}: tLogRow in the flow (fine for dev; remove or deactivate for production volume)"))
        if c["type"] == "tDie" and pv(c, "EXIT_JVM") == "true":
            f.append(("WARN", f"{c['name']}: Exit JVM immediately skips tPostjob cleanup"))
        if c["type"] == "tRunJob":
            if pv(c, "DIE_ON_CHILD_ERROR", "true") == "false":
                f.append(("WARN", f"{c['name']}: Die on child error is off - check CHILD_RETURN_CODE yourself"))
            if pv(c, "TRANSMIT_WHOLE_CONTEXT") == "false":
                f.append(("INFO", f"{c['name']}: context not transmitted to child; relies on explicit Context Param table"))
        if c["mapper"]:
            for t in c["mapper"]["inputs"]:
                if t["lookupMode"] == "RELOAD":
                    f.append(("WARN", f"{c['name']}: lookup {t['name']} uses Reload at each row - verify the lookup query is parameterised via globalMap or expect N queries"))
                if t["matchingMode"] == "ALL_MATCHES":
                    f.append(("INFO", f"{c['name']}: lookup {t['name']} is All matches - row multiplication is intended?"))
                if t["lookupMode"] in (None, "LOAD_ONCE") and not t["joinKeys"] and t["name"] not in {
                        x["name"] for x in c["mapper"]["inputs"][:1]}:
                    f.append(("WARN", f"{c['name']}: lookup {t['name']} has no join key (cartesian/first-row behaviour)"))
            if not any(o["reject"] or o["rejectInnerJoin"] for o in c["mapper"]["outputs"]) and any(
                    t["innerJoin"] for t in c["mapper"]["inputs"]):
                f.append(("INFO", f"{c['name']}: inner join without an inner-join-reject output silently drops unmatched rows"))
    # orchestration
    if "tPrejob" not in types and conns:
        f.append(("INFO", "connections are opened outside a tPrejob"))
    if "tPostjob" not in types and conns:
        f.append(("INFO", "no tPostjob: closes/cleanup will not run after an error"))
    if "tLogCatcher" not in types and "tDie" not in types and job["parameters"].get("ON_LOGCATCHER_FLAG") != "true":
        f.append(("INFO", "no tLogCatcher / Stats&Logs logging: errors only reach stdout"))
    if not job["contexts"] or all(not c["params"] for c in job["contexts"]):
        f.append(("INFO", "job has no context parameters: environment portability relies on hard-coded values"))
    starts = {c["source"] for c in job["connections"]}
    targets = {c["target"] for c in job["connections"]}
    for c in job["components"]:
        if c["active"] and c["name"] not in starts and c["name"] not in targets and c["type"] not in ("tPrejob", "tPostjob"):
            f.append(("INFO", f"{c['name']} is not connected to anything"))
    inactive = [c["name"] for c in job["components"] if not c["active"]]
    if inactive:
        f.append(("INFO", f"deactivated components: {', '.join(inactive)}"))
    return f


# --------------------------------------------------------------------------- render

def _redact(key: str, p: dict) -> str:
    v = p.get("value")
    if p.get("field") in REDACT_FIELDS and v and "context." not in v:
        return "<redacted>"
    return v if v is not None else ""


def _fmt_rows(p: dict) -> str:
    rows = p.get("rows") or []
    return "; ".join(", ".join(f"{k}={v}" for k, v in r.items()) for r in rows)


def render_markdown(job: dict, all_params: bool, do_review: bool) -> str:
    L = []
    props = job.get("properties") or {}
    title = props.get("label") or job["file"]
    L.append(f"# Talend job: {title}")
    meta = [f"type `{job['jobType']}`"]
    if job.get("framework"):
        meta.append(f"framework `{job['framework']}`")
    if props.get("version"):
        meta.append(f"version {props['version']}")
    if props.get("statusCode"):
        meta.append(f"status {props['statusCode']}")
    if props.get("folder"):
        meta.append(f"folder `{props['folder']}`")
    meta.append(f"default context `{job['defaultContext']}`")
    L.append("- " + " | ".join(meta))
    if props.get("purpose") or props.get("description"):
        L.append(f"- purpose: {props.get('purpose','')}  {props.get('description','')}".rstrip())
    L.append(f"- {len(job['components'])} components, {len(job['connections'])} connections, "
             f"{len(job['subjobs'])} subjobs, routines: {', '.join(job['routines']) or '-'}")

    # job settings worth knowing
    jp = job["parameters"]
    interesting = {
        "MULTI_THREAD_EXECATION": "Multi thread execution",
        "IMPLICIT_TCONTEXTLOAD": "Implicit tContextLoad",
        "IMPLICIT_TCONTEXTLOAD_FILE": "Implicit context file",
        "IMPLICIT_TCONTEXTLOAD_TABLE": "Implicit context table",
        "ON_STATCATCHER_FLAG": "Stats&Logs: statistics",
        "ON_LOGCATCHER_FLAG": "Stats&Logs: logs",
        "ON_METERCATCHER_FLAG": "Stats&Logs: volumetrics",
        "LOG4J_ACTIVATE": "log4j active",
        "JOB_RUN_VM_ARGUMENTS": "JVM arguments",
        "PARALLELIZE_UNIT_SIZE": "Parallelize unit size",
    }
    rows = [(lbl, jp[k]) for k, lbl in interesting.items() if jp.get(k) not in (None, "", "false")]
    if rows:
        L.append("\n## Job settings")
        L.append("| Setting | Value |\n|---|---|")
        for lbl, v in rows:
            L.append(f"| {lbl} | `{v}` |")

    L.append("\n## Contexts")
    if not job["contexts"]:
        L.append("(none)")
    else:
        names = [c["name"] for c in job["contexts"]]
        allp = OrderedDict()
        for c in job["contexts"]:
            for p in c["params"]:
                allp.setdefault(p["name"], {"type": p["type"], "vals": {}})["vals"][c["name"]] = p["value"]
        L.append("| Parameter | Type | " + " | ".join(names) + " |")
        L.append("|---|---|" + "---|" * len(names))
        for name, info in allp.items():
            vals = []
            for n in names:
                v = info["vals"].get(n, "")
                if info["type"] == "Password" and v:
                    v = "enc:..." if v.startswith("enc:") else "<clear text>"
                vals.append(f"`{v}`" if v else "")
            L.append(f"| {name} | {info['type']} | " + " | ".join(vals) + " |")

    L.append("\n## Components")
    L.append("| Component | Type | Label | Active | Key settings |\n|---|---|---|---|---|")
    for c in job["components"]:
        shown = []
        keys = list(c["params"].keys()) if all_params else [k for k in KEY_PARAMS if k in c["params"]]
        for k in keys:
            p = c["params"][k]
            if not all_params and (k in NOISE_PARAMS or p["field"] in NOISE_FIELDS):
                continue
            v = _fmt_rows(p) if p.get("rows") else _redact(k, p)
            if v in ("", None, "false") and not all_params:
                continue
            if len(v) > 90:
                v = v[:87] + "..."
            shown.append(f"{k}={v}")
        L.append(f"| {c['name']} | {c['type']} | {c['label']} | {'yes' if c['active'] else 'NO'} | "
                 + "<br>".join(x.replace("|", "\\|") for x in shown) + " |")

    L.append("\n## Connections")
    L.append("| Link | Kind | From | To | Detail |\n|---|---|---|---|---|")
    for c in job["connections"]:
        detail = TRIGGER_LABEL.get(c["connector"], c["connector"])
        if c["condition"]:
            detail += f" `{c['condition']}`"
        if c["parallel"]:
            detail += f" parallel x{c['parallelN']}"
        L.append(f"| {c['name']} | {c['kind']} | {c['source']} | {c['target']} | {detail} |")

    maps = [c for c in job["components"] if c["mapper"]]
    if maps:
        L.append("\n## tMap details")
        for c in maps:
            m = c["mapper"]
            L.append(f"\n### {c['name']} ({c['label']})")
            for t in m["inputs"]:
                mode = []
                if t["lookupMode"]:
                    mode.append(t["lookupMode"])
                if t["matchingMode"]:
                    mode.append(t["matchingMode"])
                mode.append("inner join" if t["innerJoin"] else "left outer join" if t["joinKeys"] else "main" if t is m["inputs"][0] else "")
                keys = ", ".join(f"{e['name']} {e.get('operator','==')} {e['expression']}" for e in t["joinKeys"])
                L.append(f"- input `{t['name']}`: {' / '.join(x for x in mode if x)}"
                         + (f"; keys: {keys}" if keys else "")
                         + (f"; filter: `{t['expressionFilter']}`" if t["expressionFilter"] else ""))
            if m["vars"]:
                L.append("- Var table:")
                for e in m["vars"]:
                    L.append(f"  - `{e.get('name')}` ({(e.get('type') or '').replace('id_','')}) = `{e.get('expression')}`")
            for t in m["outputs"]:
                flags = []
                if t["reject"]:
                    flags.append("catch output reject")
                if t["rejectInnerJoin"]:
                    flags.append("catch lookup inner join reject")
                if t["expressionFilter"]:
                    flags.append(f"filter `{t['expressionFilter']}`")
                L.append(f"- output `{t['name']}`" + (f" ({'; '.join(flags)})" if flags else "") + ":")
                for e in t["columns"]:
                    L.append(f"  - {e.get('name')} = `{e.get('expression')}`")

    L.append("\n## Schemas")
    for c in job["components"]:
        for s in c["schemas"]:
            cols = ", ".join(
                f"{col['name']}:{col['type']}" + ("*" if col['key'] else "") + ("" if col['nullable'] else "!")
                + (f"[{col['pattern']}]" if col['pattern'] else "")
                for col in s["columns"])
            L.append(f"- {c['name']} `{s['connector']}:{s['name']}` ({len(s['columns'])} cols): {cols}")
    L.append("(`*` = key, `!` = not nullable, `[pattern]` = date pattern)")

    if job["subjobs"]:
        L.append("\n## Subjobs")
        for s in job["subjobs"]:
            L.append(f"- starts at `{s['start']}`" + (f": {s['title']}" if s["title"] else ""))
    if job["notes"]:
        L.append("\n## Notes")
        for n in job["notes"]:
            L.append(f"- {n}")

    if do_review:
        L.append("\n## Review findings")
        found = review(job)
        if not found:
            L.append("- nothing flagged")
        for sev, msg in found:
            L.append(f"- **{sev}** {msg}")
    return "\n".join(L) + "\n"


def render_dot(job: dict) -> str:
    L = ["digraph talend {", "  rankdir=LR;", "  node [shape=box, fontname=Helvetica];"]
    for c in job["components"]:
        style = "" if c["active"] else ", style=dashed, color=gray"
        lbl = c["name"] if c["label"] == c["name"] else f"{c['label']}\\n({c['name']})"
        L.append(f'  "{c["name"]}" [label="{lbl}\\n{c["type"]}"{style}];')
    for c in job["connections"]:
        attrs = {"row": "", "lookup": ", style=dashed", "reject": ", color=red",
                 "iterate": ", color=blue, style=bold", "trigger": ", color=darkgreen, style=dotted",
                 "route": ""}[c["kind"]]
        lbl = c["name"] if c["kind"] in ("row", "lookup", "reject") else TRIGGER_LABEL.get(c["connector"], c["connector"])
        if c["condition"]:
            lbl += f": {c['condition']}"
        lbl = lbl.replace('"', '\\"')
        L.append(f'  "{c["source"]}" -> "{c["target"]}" [label="{lbl}"{attrs}];')
    L.append("}")
    return "\n".join(L) + "\n"


def to_json(job: dict, do_review: bool) -> str:
    findings = review(job) if do_review else None
    out = json.loads(json.dumps(job, default=str))  # deep copy, JSON-safe
    for c in out["components"]:
        c["params"] = {k: (_fmt_rows(p) if p.get("rows") else _redact(k, p)) for k, p in c["params"].items()}
    if findings is not None:
        out["review"] = [{"severity": s, "message": m} for s, m in findings]
    return json.dumps(out, indent=2) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("item", help="path to a Talend job .item file")
    ap.add_argument("--format", choices=("markdown", "json", "dot"), default="markdown")
    ap.add_argument("--review", action="store_true", help="append heuristic design-review findings")
    ap.add_argument("--all-params", action="store_true", help="show every elementParameter, not just key ones")
    a = ap.parse_args(argv)
    try:
        job = parse_item(a.item)
    except (ItemError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if a.format == "json":
        sys.stdout.write(to_json(job, a.review))
    elif a.format == "dot":
        sys.stdout.write(render_dot(job))
    else:
        sys.stdout.write(render_markdown(job, a.all_params, a.review))
    return 0


if __name__ == "__main__":
    sys.exit(main())
