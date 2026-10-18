#!/usr/bin/env python3
"""Build (and optionally call) a Talend Administration Center MetaServlet request.

TAC's MetaServlet takes ONE query-string argument: the base64 encoding of a
JSON object such as ``{"actionName":"runTask","authUser":"...","authPass":"...",
"taskId":12,"mode":"synchronous"}``. This helper does the encoding exactly
(no line wrapping, URL-safe percent-encoding of ``+`` ``/`` ``=``) so that a
shell one-liner cannot get it subtly wrong, and decodes the JSON answer.

Usage::

    metaservlet.py --tac-url http://tac:8080/org.talend.administrator \
        --user admin@company.com --password-env TAC_PASS \
        runTask --param taskId=12 --param mode=synchronous

    metaservlet.py --tac-url ... --user ... --password-env TAC_PASS help
    metaservlet.py --json '{"actionName":"listTasks","authUser":"a","authPass":"b"}' --tac-url ...
    ... --call            # actually send the GET and print the decoded response
    ... --decode <base64> # decode a MetaServlet argument back to JSON

Parameter typing: ``--param key=value`` keeps strings; ``--param taskId=12``
becomes the integer 12; ``true``/``false`` become booleans; a value starting
with ``{`` or ``[`` is parsed as JSON (e.g. ``--param 'context={"k":"v"}'``).
See references/apis-sdks.md for the command catalogue and return codes.
Standard library only. The URL builder is unit-tested; the ``--call`` path is
not exercised against a live TAC in this build.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.parse
import urllib.request


def typed(value: str):
    v = value.strip()
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    if v[:1] in "{[":
        return json.loads(v)
    try:
        return int(v)
    except ValueError:
        pass
    try:
        f = float(v)
        if "." in v:
            return f
    except ValueError:
        pass
    return value


def build_payload(action: str, user: str | None, password: str | None, params: dict) -> dict:
    payload = {"actionName": action}
    if user is not None:
        payload["authUser"] = user
    if password is not None:
        payload["authPass"] = password
    payload.update(params)
    return payload


def encode(payload: dict) -> str:
    """base64 of compact JSON, then percent-encoded for a query string."""
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    b64 = base64.b64encode(raw).decode("ascii")
    return urllib.parse.quote(b64, safe="")


def decode(arg: str) -> dict:
    s = urllib.parse.unquote(arg)
    s += "=" * (-len(s) % 4)
    return json.loads(base64.b64decode(s).decode("utf-8"))


def build_url(tac_url: str, payload: dict) -> str:
    base = tac_url.rstrip("/")
    if not base.endswith("/metaServlet"):
        base += "/metaServlet"
    return base + "?" + encode(payload)


def call(url: str, timeout: float = 60.0) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec - operator supplied URL
        body = resp.read().decode("utf-8", "replace")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"raw": body}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("action", nargs="?", help="MetaServlet actionName, e.g. runTask, listTasks, help")
    ap.add_argument("--tac-url", help="TAC base URL, e.g. http://host:8080/org.talend.administrator")
    ap.add_argument("--user", help="authUser (TAC login, usually an email)")
    ap.add_argument("--password", help="authPass (prefer --password-env)")
    ap.add_argument("--password-env", default="TAC_PASS", help="env var holding authPass (default TAC_PASS)")
    ap.add_argument("--param", action="append", default=[], metavar="KEY=VALUE", help="extra JSON field (typed)")
    ap.add_argument("--json", help="raw JSON payload instead of action/--param")
    ap.add_argument("--decode", metavar="B64", help="decode a MetaServlet argument and exit")
    ap.add_argument("--call", action="store_true", help="send the request and print the decoded response")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--show-payload", action="store_true", help="print the JSON payload (password masked)")
    a = ap.parse_args(argv)

    if a.decode:
        print(json.dumps(decode(a.decode), indent=2))
        return 0

    if a.json:
        payload = json.loads(a.json)
    else:
        if not a.action:
            ap.error("an action (or --json / --decode) is required")
        params = {}
        for kv in a.param:
            if "=" not in kv:
                ap.error(f"--param expects KEY=VALUE, got {kv!r}")
            k, v = kv.split("=", 1)
            params[k] = typed(v)
        password = a.password if a.password is not None else os.environ.get(a.password_env)
        payload = build_payload(a.action, a.user, password, params)

    if a.show_payload:
        masked = dict(payload)
        if "authPass" in masked:
            masked["authPass"] = "***"
        print(json.dumps(masked, indent=2), file=sys.stderr)

    if not a.tac_url:
        print(encode(payload))
        return 0
    url = build_url(a.tac_url, payload)
    if not a.call:
        print(url)
        return 0
    try:
        result = call(url, a.timeout)
    except Exception as exc:  # noqa: BLE001 - surface any transport error plainly
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    rc = result.get("returnCode") if isinstance(result, dict) else None
    return 0 if rc in (0, None) else 1


if __name__ == "__main__":
    sys.exit(main())
