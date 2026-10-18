#!/usr/bin/env python3
"""Minimal Talend Cloud Management Console (TMC) public API client.

Covers the day-to-day operator calls: list environments / workspaces /
engines, find and inspect tasks and plans, run a task or plan with parameters,
poll an execution, read task run-config and schedules, and a generic ``raw``
escape hatch for any other path. Authentication is a Personal Access Token or
service-account token in ``TALEND_CLOUD_TOKEN`` (or ``--token``).

Usage::

    export TALEND_CLOUD_TOKEN=...            # PAT from TMC > Profile preferences
    tmc_api.py --region us environments
    tmc_api.py --region eu workspaces --environment-id <envId>
    tmc_api.py --region us tasks list --environment-id <envId> [--name "LOAD_*"]
    tmc_api.py tasks get <taskId>
    tmc_api.py tasks run-config <taskId>
    tmc_api.py tasks history <taskId>            # recent executions of a task
    tmc_api.py tasks run <taskId> --param DB_HOST=prod --param BATCH_SIZE=5000 [--wait]
    tmc_api.py executions get <executionId>
    tmc_api.py executions wait <executionId> --poll 10 --timeout 3600
    tmc_api.py plans list --environment-id <envId>
    tmc_api.py plans run <planId> [--wait]
    tmc_api.py engines
    tmc_api.py raw GET /orchestration/executables/tasks?environmentId=...
    tmc_api.py raw POST /processing/executions --body '{"executable":"<taskId>"}'
    ... --dry-run     # print the request instead of sending it

Regions: ``us`` -> api.us.cloud.talend.com, ``eu`` -> api.eu.cloud.talend.com,
``ap`` -> api.ap.cloud.talend.com, ``us-west`` -> api.us-west.cloud.talend.com,
``au`` -> api.au.cloud.talend.com; or pass ``--base-url`` for anything else
(for example a Qlik Talend Cloud tenant endpoint). Paths default to the current
API families (``/orchestration/...``, ``/processing/...``); ``--legacy v2.6``
rewrites them to the numbered ``/tmc/v2.6/...`` form for older tenants.

Paths are doc-derived (references/apis-sdks.md); this build was not run
against a live tenant. Standard library only.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REGIONS = {
    "us": "https://api.us.cloud.talend.com",
    "eu": "https://api.eu.cloud.talend.com",
    "ap": "https://api.ap.cloud.talend.com",
    "us-west": "https://api.us-west.cloud.talend.com",
    "au": "https://api.au.cloud.talend.com",
}
SUCCESS = {"EXECUTION_SUCCESSFUL", "EXECUTION_SUCCESS", "SUCCESSFUL", "SUCCESS"}
TERMINAL = SUCCESS | {"EXECUTION_FAILED", "EXECUTION_REJECTED", "TERMINATED", "EXECUTION_TERMINATED",
                      "CANCELLED", "ABORTED", "DEPLOY_FAILED", "FAILED"}


class TmcError(Exception):
    pass


FAMILIES = ("orchestration", "processing", "monitoring", "account", "security")


class Client:
    def __init__(self, base_url: str, token: str | None, legacy: str | None = None,
                 dry_run: bool = False, timeout: float = 60.0):
        self.base = base_url.rstrip("/")
        self.legacy = legacy  # e.g. "v2.6" -> /tmc/v2.6/<path without family prefix>
        self.token = token
        self.dry_run = dry_run
        self.timeout = timeout

    def _path(self, path: str) -> str:
        path = path if path.startswith("/") else "/" + path
        if self.legacy and not path.startswith("/tmc/"):
            parts = path.split("/", 2)
            if len(parts) == 3 and parts[1] in FAMILIES:
                path = "/" + parts[2]
            path = f"/tmc/{self.legacy}" + path
        return path

    def request(self, method: str, path: str, params: dict | None = None, body=None):
        url = self.base + self._path(path)
        if params:
            q = {k: v for k, v in params.items() if v not in (None, "")}
            if q:
                url += ("&" if "?" in url else "?") + urllib.parse.urlencode(q)
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self.dry_run:
            shown = dict(headers)
            if "Authorization" in shown:
                shown["Authorization"] = "Bearer ***"
            print(json.dumps({"method": method, "url": url, "headers": shown, "body": body}, indent=2))
            return None
        if not self.token:
            raise TmcError("no token: set TALEND_CLOUD_TOKEN or pass --token")
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # nosec - operator URL
                raw = resp.read().decode("utf-8", "replace")
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            raise TmcError(f"HTTP {exc.code} {method} {url}: {detail[:800]}") from exc
        except urllib.error.URLError as exc:
            raise TmcError(f"{method} {url}: {exc.reason}") from exc

    # --- convenience -------------------------------------------------------
    def list_all(self, path: str, params: dict | None = None, limit: int = 100):
        """Follow offset/limit pagination where the API returns {items,total} or a bare list."""
        params = dict(params or {})
        params.setdefault("limit", limit)
        offset = 0
        items = []
        while True:
            params["offset"] = offset
            page = self.request("GET", path, params)
            if page is None:
                return []
            if isinstance(page, list):
                items.extend(page)
                if len(page) < limit:
                    break
            else:
                chunk = page.get("items", [])
                items.extend(chunk)
                total = page.get("total")
                if not chunk or (total is not None and len(items) >= total) or len(chunk) < limit:
                    break
            offset += limit
        return items

    def wait(self, execution_id: str, poll: float = 10.0, timeout: float = 3600.0):
        start = time.time()
        last = None
        while True:
            ex = self.request("GET", f"/processing/executions/{execution_id}")
            if ex is None:
                return None
            status = (ex.get("status") or ex.get("executionStatus") or "").upper()
            if status != last:
                print(f"[{time.strftime('%H:%M:%S')}] {execution_id}: {status}", file=sys.stderr)
                last = status
            if status in TERMINAL:
                return ex
            if time.time() - start > timeout:
                raise TmcError(f"timed out after {timeout}s; last status {status}")
            time.sleep(poll)


def parse_params(pairs: list) -> dict:
    out = {}
    for kv in pairs:
        if "=" not in kv:
            raise TmcError(f"--param expects KEY=VALUE, got {kv!r}")
        k, v = kv.split("=", 1)
        out[k] = v  # TMC task parameters are strings
    return out


def out(obj):
    if obj is not None:
        print(json.dumps(obj, indent=2))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--region", choices=sorted(REGIONS), default=os.environ.get("TALEND_CLOUD_REGION", "us"))
    ap.add_argument("--base-url", help="override the regional base URL")
    ap.add_argument("--legacy", metavar="vX.Y", help="use the numbered legacy prefix, e.g. v2.6 -> /tmc/v2.6/...")
    ap.add_argument("--token", default=os.environ.get("TALEND_CLOUD_TOKEN"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--timeout", type=float, default=60.0)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("environments")
    p = sub.add_parser("workspaces"); p.add_argument("--environment-id")
    sub.add_parser("engines")

    t = sub.add_parser("tasks").add_subparsers(dest="sub", required=True)
    tl = t.add_parser("list"); tl.add_argument("--environment-id"); tl.add_argument("--workspace-id"); tl.add_argument("--name", help="glob on task name")
    tg = t.add_parser("get"); tg.add_argument("task_id")
    trc = t.add_parser("run-config"); trc.add_argument("task_id")
    tr = t.add_parser("run"); tr.add_argument("task_id"); tr.add_argument("--param", action="append", default=[]); tr.add_argument("--wait", action="store_true"); tr.add_argument("--poll", type=float, default=10.0); tr.add_argument("--wait-timeout", type=float, default=3600.0)
    ts = t.add_parser("schedule"); ts.add_argument("task_id")
    th = t.add_parser("history"); th.add_argument("task_id"); th.add_argument("--limit", type=int, default=20)

    e = sub.add_parser("executions").add_subparsers(dest="sub", required=True)
    eg = e.add_parser("get"); eg.add_argument("execution_id")
    ew = e.add_parser("wait"); ew.add_argument("execution_id"); ew.add_argument("--poll", type=float, default=10.0); ew.add_argument("--timeout", dest="wait_timeout", type=float, default=3600.0)
    el = e.add_parser("logs"); el.add_argument("execution_id")
    et = e.add_parser("terminate"); et.add_argument("execution_id")

    pl = sub.add_parser("plans").add_subparsers(dest="sub", required=True)
    pll = pl.add_parser("list"); pll.add_argument("--environment-id"); pll.add_argument("--workspace-id")
    plg = pl.add_parser("get"); plg.add_argument("plan_id")
    plr = pl.add_parser("run"); plr.add_argument("plan_id"); plr.add_argument("--wait", action="store_true"); plr.add_argument("--poll", type=float, default=15.0); plr.add_argument("--wait-timeout", type=float, default=7200.0)

    r = sub.add_parser("raw"); r.add_argument("method"); r.add_argument("path"); r.add_argument("--body", help="JSON body")

    a = ap.parse_args(argv)
    base = a.base_url or REGIONS[a.region]
    c = Client(base, a.token, a.legacy, a.dry_run, a.timeout)
    try:
        if a.cmd == "environments":
            out(c.request("GET", "/orchestration/environments"))
        elif a.cmd == "workspaces":
            out(c.request("GET", "/orchestration/workspaces", {"environmentId": a.environment_id}))
        elif a.cmd == "engines":
            out({"remoteEngines": c.request("GET", "/processing/runtimes/remote-engines"),
                 "remoteEngineClusters": c.request("GET", "/processing/runtimes/remote-engine-clusters")})
        elif a.cmd == "tasks":
            if a.sub == "list":
                items = c.list_all("/orchestration/executables/tasks", {"environmentId": a.environment_id, "workspaceId": a.workspace_id})
                if a.name:
                    items = [i for i in items if fnmatch.fnmatch(i.get("name", ""), a.name)]
                out([{k: i.get(k) for k in ("executable", "id", "name", "workspaceId", "environmentId", "artifact", "version")}
                     for i in items] if not a.dry_run else None)
            elif a.sub == "get":
                out(c.request("GET", f"/orchestration/executables/tasks/{a.task_id}"))
            elif a.sub == "run-config":
                out(c.request("GET", f"/orchestration/executables/tasks/{a.task_id}/run-config"))
            elif a.sub == "schedule":
                out(c.request("GET", f"/orchestration/executables/tasks/{a.task_id}/schedule"))
            elif a.sub == "history":
                out(c.request("GET", f"/processing/executables/tasks/{a.task_id}/executions", {"limit": a.limit}))
            elif a.sub == "run":
                body = {"executable": a.task_id}
                params = parse_params(a.param)
                if params:
                    body["parameters"] = params
                res = c.request("POST", "/processing/executions", body=body)
                out(res)
                if a.wait and res:
                    final = c.wait(res.get("executionId") or res.get("id"), a.poll, a.wait_timeout)
                    out(final)
                    return 0 if ((final or {}).get("status") or (final or {}).get("executionStatus") or "").upper() in SUCCESS else 1
        elif a.cmd == "executions":
            if a.sub == "get":
                out(c.request("GET", f"/processing/executions/{a.execution_id}"))
            elif a.sub == "wait":
                final = c.wait(a.execution_id, a.poll, a.wait_timeout)
                out(final)
                return 0 if ((final or {}).get("status") or (final or {}).get("executionStatus") or "").upper() in SUCCESS else 1
            elif a.sub == "logs":
                out(c.request("GET", f"/processing/executions/{a.execution_id}/logs"))
            elif a.sub == "terminate":
                out(c.request("POST", f"/processing/executions/{a.execution_id}/stop"))
        elif a.cmd == "plans":
            if a.sub == "list":
                out(c.list_all("/orchestration/executables/plans", {"environmentId": a.environment_id, "workspaceId": a.workspace_id}))
            elif a.sub == "get":
                out(c.request("GET", f"/orchestration/executables/plans/{a.plan_id}"))
            elif a.sub == "run":
                res = c.request("POST", "/processing/executions/plans", body={"executable": a.plan_id})
                out(res)
                if a.wait and res:
                    exec_id = res.get("executionId") or res.get("id")
                    start = time.time()
                    while True:
                        st = c.request("GET", f"/processing/executions/plans/{exec_id}")
                        status = ((st or {}).get("status") or (st or {}).get("executionStatus") or "").upper()
                        print(f"[{time.strftime('%H:%M:%S')}] plan {exec_id}: {status}", file=sys.stderr)
                        if status in TERMINAL:
                            out(st)
                            return 0 if status in SUCCESS else 1
                        if time.time() - start > a.wait_timeout:
                            raise TmcError("plan wait timed out")
                        time.sleep(a.poll)
        elif a.cmd == "raw":
            body = json.loads(a.body) if a.body else None
            out(c.request(a.method.upper(), a.path, body=body))
    except TmcError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
