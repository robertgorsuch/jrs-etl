"""Offline unit tests for the talend-etl helper scripts (plain unittest, no network)."""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPTS = os.path.join(SKILL, "scripts")
FIXTURES = os.path.join(SKILL, "fixtures")
ITEM = os.path.join(FIXTURES, "LOAD_CUSTOMERS_0.1.item")
sys.path.insert(0, SCRIPTS)

import inspect_job_item as iji  # noqa: E402
import inspect_job_export as ije  # noqa: E402
import metaservlet as ms  # noqa: E402
import tmc_api  # noqa: E402


def run(script, *args):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args],
                          capture_output=True, text=True, timeout=60)


class InspectJobItem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.job = iji.parse_item(ITEM)

    def test_basic_counts(self):
        j = self.job
        self.assertEqual(j["jobType"], "Standard")
        self.assertEqual(j["defaultContext"], "Default")
        self.assertEqual(len(j["components"]), 13)
        self.assertEqual(len(j["connections"]), 10)
        self.assertEqual([c["name"] for c in j["contexts"]], ["Default", "PROD"])
        self.assertEqual(j["routines"], ["TalendDate", "StringHandling", "CustomerUtils"])
        self.assertEqual(j["properties"]["label"], "LOAD_CUSTOMERS")
        self.assertEqual(j["properties"]["folder"], "dwh/dimensions")

    def test_connection_kinds(self):
        kinds = {c["name"]: c["kind"] for c in self.job["connections"]}
        self.assertEqual(kinds["row1"], "row")
        self.assertEqual(kinds["lkp"], "lookup")       # lineStyle 1 => FLOW_REF
        self.assertEqual(kinds["rejects"], "reject")
        self.assertEqual(kinds["iterate1"], "iterate")
        self.assertEqual(kinds["OnSubjobOk1"], "trigger")

    def test_linestyle_fallback_when_connector_missing(self):
        import copy
        import xml.etree.ElementTree as ET
        src = open(ITEM, encoding="utf-8").read()
        # strip connectorName so the ordinal alone must classify the links
        stripped = src.replace('connectorName="FLOW" label="lkp"', 'label="lkp"') \
                      .replace('connectorName="SUBJOB_OK" label="OnSubjobOk"', 'label="OnSubjobOk"') \
                      .replace('connectorName="ITERATE" label="Iterate"', 'label="Iterate"')
        with tempfile.NamedTemporaryFile("w", suffix=".item", delete=False, encoding="utf-8") as fh:
            fh.write(stripped)
        try:
            kinds = {c["name"]: (c["kind"], c["connector"]) for c in iji.parse_item(fh.name)["connections"]}
        finally:
            os.unlink(fh.name)
        self.assertEqual(kinds["lkp"], ("lookup", "LOOKUP"))
        self.assertEqual(kinds["OnSubjobOk1"], ("trigger", "SUBJOB_OK"))
        self.assertEqual(kinds["iterate1"], ("iterate", "ITERATE"))

    def test_tmap_internals(self):
        tmap = next(c for c in self.job["components"] if c["type"] == "tMap")
        m = tmap["mapper"]
        self.assertEqual(m["inputs"][1]["lookupMode"], "LOAD_ONCE")
        self.assertEqual(m["inputs"][1]["matchingMode"], "UNIQUE_MATCH")
        self.assertTrue(m["inputs"][1]["innerJoin"])
        self.assertEqual(m["inputs"][1]["joinKeys"][0]["expression"], "StringHandling.UPCASE(row1.country_code)")
        self.assertEqual([v["name"] for v in m["vars"]], ["clean_name", "clean_email"])
        self.assertTrue(m["outputs"][1]["rejectInnerJoin"])
        self.assertIn("contains", m["outputs"][0]["expressionFilter"])

    def test_schema_columns(self):
        fid = next(c for c in self.job["components"] if c["name"] == "tFileInputDelimited_1")
        flow = next(s for s in fid["schemas"] if s["connector"] == "FLOW")
        self.assertEqual([c["name"] for c in flow["columns"]][:2], ["customer_id", "full_name"])
        self.assertTrue(flow["columns"][0]["key"])
        self.assertFalse(flow["columns"][0]["nullable"])
        self.assertEqual(flow["columns"][4]["pattern"], '"yyyy-MM-dd"')
        rej = next(s for s in fid["schemas"] if s["connector"] == "REJECT")
        self.assertEqual([c["name"] for c in rej["columns"]][-2:], ["errorCode", "errorMessage"])

    def test_table_parameter_rows(self):
        out = next(c for c in self.job["components"] if c["name"] == "tDBOutput_1")
        rows = out["params"]["FIELD_OPTIONS"]["rows"]
        self.assertEqual(rows[0]["SCHEMA_COLUMN"], "customer_id")
        self.assertEqual(rows[0]["UPDATE_KEY"], "true")

    def test_review_findings(self):
        msgs = [m for _s, m in iji.review(self.job)]
        self.assertTrue(any("Die on error is off but no reject link" in m for m in msgs))
        self.assertTrue(any("INSERT_OR_UPDATE" in m for m in msgs))
        self.assertTrue(any("deactivated components: tLogRow_2" in m for m in msgs))
        self.assertFalse(any("not declared" in m for m in msgs))  # all context refs declared

    def test_unresolved_context_detected(self):
        import copy
        j = copy.deepcopy(self.job)
        j["components"][2]["params"]["DIRECTORY"]["value"] = "context.MISSING_DIR"
        self.assertEqual(iji.unresolved_context_refs(j), ["MISSING_DIR"])

    def test_renderers(self):
        md = iji.render_markdown(self.job, all_params=False, do_review=True)
        self.assertIn("# Talend job: LOAD_CUSTOMERS", md)
        self.assertIn("| lkp | lookup | tDBInput_1 | tMap_1 |", md)
        self.assertIn("## Review findings", md)
        self.assertEqual(md.count("CODE=4"), 1)
        dot = iji.render_dot(self.job)
        self.assertIn('"tMap_1" -> "tDBOutput_1"', dot)
        js = json.loads(iji.to_json(self.job, True))
        self.assertEqual(len(js["review"]), 4)
        self.assertEqual(js["components"][1]["params"]["PASS"], "context.DB_PASS")

    def test_password_redaction(self):
        p = {"field": "PASSWORD", "value": '"hunter2"'}
        self.assertEqual(iji._redact("PASS", p), "<redacted>")

    def test_cli_rejects_non_job(self):
        with tempfile.NamedTemporaryFile("w", suffix=".item", delete=False) as fh:
            fh.write('<?xml version="1.0"?><talendfile:ContextType xmlns:talendfile="x" name="Default"/>')
        try:
            r = run("inspect_job_item.py", fh.name)
            self.assertEqual(r.returncode, 2)
            self.assertIn("expected talendfile:ProcessType", r.stderr)
        finally:
            os.unlink(fh.name)

    def test_cli_markdown(self):
        r = run("inspect_job_item.py", ITEM, "--review")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("## tMap details", r.stdout)


class MetaServlet(unittest.TestCase):
    def test_typed(self):
        self.assertEqual(ms.typed("12"), 12)
        self.assertIs(ms.typed("true"), True)
        self.assertEqual(ms.typed('{"a":1}'), {"a": 1})
        self.assertEqual(ms.typed("Default"), "Default")
        self.assertEqual(ms.typed("1.5"), 1.5)

    def test_roundtrip(self):
        payload = ms.build_payload("runTask", "admin@x.com", "p+/=w", {"taskId": 12, "mode": "synchronous"})
        enc = ms.encode(payload)
        self.assertNotIn("+", enc)
        self.assertNotIn("/", enc)
        self.assertEqual(ms.decode(enc), payload)

    def test_url(self):
        url = ms.build_url("http://tac:8080/org.talend.administrator/", {"actionName": "help"})
        self.assertTrue(url.startswith("http://tac:8080/org.talend.administrator/metaServlet?"))
        self.assertEqual(ms.decode(url.split("?", 1)[1]), {"actionName": "help"})

    def test_cli(self):
        r = run("metaservlet.py", "--user", "a", "--password", "b", "listTasks", "--param", "x=1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(ms.decode(r.stdout.strip()), {"actionName": "listTasks", "authUser": "a", "authPass": "b", "x": 1})


class InspectJobExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.zip = os.path.join(cls.tmp, "LOAD_CUSTOMERS_0.1.zip")
        with zipfile.ZipFile(cls.zip, "w") as z:
            z.writestr("LOAD_CUSTOMERS/LOAD_CUSTOMERS_run.sh",
                       "#!/bin/sh\ncd `dirname $0`\nROOT_PATH=`pwd`\n"
                       "java -Dtalend.component.manager.m2.repository=$ROOT_PATH/../lib -Xms256M -Xmx1024M "
                       "-Dfile.encoding=UTF-8 -cp .:$ROOT_PATH:$ROOT_PATH/../lib/routines.jar:$ROOT_PATH/../lib/postgresql-42.6.0.jar:"
                       "$ROOT_PATH/load_customers_0_1.jar dwh.load_customers_0_1.LOAD_CUSTOMERS --context=Default \"$@\"\n")
            z.writestr("LOAD_CUSTOMERS/LOAD_CUSTOMERS_run.bat",
                       "%~d0\r\ncd %~dp0\r\njava -Xms256M -Xmx1024M -cp .;..\\lib\\routines.jar;load_customers_0_1.jar "
                       "dwh.load_customers_0_1.LOAD_CUSTOMERS --context=Default %*\r\n")
            z.writestr("LOAD_CUSTOMERS/load_customers_0_1.jar", b"PK\x05\x06" + b"\0" * 18)
            z.writestr("LOAD_CUSTOMERS/contexts/Default.properties", "INPUT_DIR=/data/in\nDB_PASS=enc:system.encryption.key.v1:abc\n")
            z.writestr("LOAD_CUSTOMERS/contexts/PROD.properties", "INPUT_DIR=/mnt/landing\n")
            z.writestr("jobInfo.properties", "job=LOAD_CUSTOMERS\njobVersion=0.1\nproject=DWH\ncontextName=Default\n"
                                             "applicationType=STANDALONE\njobType=Standard\ncommandLineVersion=8.0.1\n")
            z.writestr("lib/routines.jar", b"PK")
            z.writestr("lib/postgresql-42.6.0.jar", b"PK")
            z.writestr("lib/log4j-core-2.17.1.jar", b"PK")
            z.writestr("LOAD_CUSTOMERS/log4j2.xml", "<Configuration/>")
            z.writestr("LOAD_CUSTOMERS/items/DWH/process/LOAD_CUSTOMERS_0.1.item", "<x/>")

    def test_analyse_zip(self):
        res = ije.analyse(self.zip)
        self.assertEqual(res["kind"], "zip")
        self.assertEqual(res["jobInfo"]["job"], "LOAD_CUSTOMERS")
        sh = next(l for l in res["launchers"] if l["shell"] == "sh")
        self.assertEqual(sh["main_class"], "dwh.load_customers_0_1.LOAD_CUSTOMERS")
        self.assertEqual(sh["default_context"], "Default")
        self.assertIn("-Xmx1024M", sh["jvm_args"])
        self.assertEqual(len(res["libs"]), 3)
        self.assertTrue(any("PostgreSQL JDBC" in d for d in res["drivers"]))
        self.assertEqual(res["contexts"]["LOAD_CUSTOMERS/contexts/Default.properties"]["INPUT_DIR"], "/data/in")
        self.assertEqual(res["log4j"], ["LOAD_CUSTOMERS/log4j2.xml"])
        self.assertEqual(len(res["items"]), 1)
        self.assertEqual(res["warnings"], [])

    def test_render_and_cli(self):
        md = ije.render(ije.analyse(self.zip))
        self.assertIn("## How to run", md)
        self.assertIn("--context=Default", md)
        self.assertIn("DB_PASS=<enc>", md)
        r = run("inspect_job_export.py", self.zip, "--format", "json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["jobInfo"]["jobVersion"], "0.1")

    def test_directory_and_warnings(self):
        d = os.path.join(self.tmp, "osgi")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "bundle.jar"), "wb") as fh:
            fh.write(b"PK")
        res = ije.analyse(d)
        self.assertEqual(res["kind"], "directory")
        self.assertTrue(any("no *_run.sh" in w for w in res["warnings"]))

    def test_bad_path(self):
        r = run("inspect_job_export.py", os.path.join(self.tmp, "nope.zip"))
        self.assertEqual(r.returncode, 2)


class TmcApi(unittest.TestCase):
    def test_dry_run_builds_request(self):
        c = tmc_api.Client("https://api.eu.cloud.talend.com", "tok", dry_run=True)
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            c.request("POST", "/processing/executions", body={"executable": "abc", "parameters": {"k": "v"}})
        finally:
            sys.stdout = old
        req = json.loads(buf.getvalue())
        self.assertEqual(req["url"], "https://api.eu.cloud.talend.com/processing/executions")
        self.assertEqual(req["headers"]["Authorization"], "Bearer ***")
        self.assertEqual(req["body"]["parameters"], {"k": "v"})

    def test_query_params_skip_empty(self):
        c = tmc_api.Client("https://x", "t", dry_run=True)
        buf = io.StringIO(); old = sys.stdout; sys.stdout = buf
        try:
            c.request("GET", "/orchestration/executables/tasks", {"environmentId": "e1", "workspaceId": None})
        finally:
            sys.stdout = old
        self.assertEqual(json.loads(buf.getvalue())["url"], "https://x/orchestration/executables/tasks?environmentId=e1")

    def test_legacy_prefix_rewrite(self):
        c = tmc_api.Client("https://x", "t", legacy="v2.6", dry_run=True)
        self.assertEqual(c._path("/orchestration/executables/tasks/T1"), "/tmc/v2.6/executables/tasks/T1")
        self.assertEqual(c._path("/processing/executions"), "/tmc/v2.6/executions")
        self.assertEqual(c._path("/tmc/v2.6/environments"), "/tmc/v2.6/environments")
        self.assertEqual(tmc_api.Client("https://x", "t")._path("processing/executions"), "/processing/executions")

    def test_cli_dry_run_and_param_parsing(self):
        r = run("tmc_api.py", "--dry-run", "--token", "t", "--region", "ap", "tasks", "run", "T1", "--param", "A=1", "--param", "B=x=y")
        self.assertEqual(r.returncode, 0, r.stderr)
        req = json.loads(r.stdout)
        self.assertEqual(req["url"], "https://api.ap.cloud.talend.com/processing/executions")
        self.assertEqual(req["body"], {"executable": "T1", "parameters": {"A": "1", "B": "x=y"}})

    def test_missing_token(self):
        r = run("tmc_api.py", "--token", "", "environments")
        self.assertEqual(r.returncode, 2)
        self.assertIn("no token", r.stderr)


if __name__ == "__main__":
    unittest.main()
