#!/usr/bin/env python3
"""Inspect a Talend "Build Job" standalone export (zip or extracted folder).

Finds the launcher scripts, the main class and JVM settings they use, the
context parameter files, ``jobInfo.properties``, the library jars (and which
JDBC drivers / notable libs are present), bundled items/sources and the log4j
configuration, then prints a ready-to-adapt run command.

Usage::

    inspect_job_export.py LOAD_CUSTOMERS_0.1.zip
    inspect_job_export.py ./LOAD_CUSTOMERS            # already extracted
    inspect_job_export.py build.zip --format json
    inspect_job_export.py build.zip --list            # every entry

Standard library only. The zip is read in place (nothing is extracted). Tested
against a synthetic export produced from the fixture layout documented in
references/deployment-runtime.md; real exports vary slightly by release.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import zipfile

DRIVER_HINTS = [
    ("postgresql", "PostgreSQL JDBC"), ("mysql-connector", "MySQL JDBC"), ("mariadb", "MariaDB JDBC"),
    ("ojdbc", "Oracle JDBC"), ("mssql-jdbc", "Microsoft SQL Server JDBC"), ("jtds", "jTDS (SQL Server/Sybase)"),
    ("snowflake-jdbc", "Snowflake JDBC"), ("redshift", "Amazon Redshift JDBC"), ("db2jcc", "IBM DB2 JDBC"),
    ("terajdbc", "Teradata JDBC"), ("vertica", "Vertica JDBC"), ("hive-jdbc", "Hive JDBC"),
    ("sqlite-jdbc", "SQLite JDBC"), ("h2-", "H2"), ("hsqldb", "HSQLDB"), ("ngdbc", "SAP HANA JDBC"),
    ("exasol", "Exasol JDBC"), ("iijdbc", "Actian Ingres/Vector JDBC"), ("bigquery", "Google BigQuery"),
    ("aws-java-sdk", "AWS SDK"), ("azure-storage", "Azure Storage"), ("google-cloud", "Google Cloud"),
    ("kafka-clients", "Kafka client"), ("mongo", "MongoDB driver"), ("cassandra", "Cassandra driver"),
    ("force-wsc", "Salesforce WSC"), ("sapjco", "SAP JCo"), ("log4j-core", "log4j2 core"),
    ("log4j-1.2", "log4j 1.x"), ("talend_file_enhanced", "Talend file routines"), ("dom4j", "dom4j"),
    ("routines", "Talend routines jar"), ("jackson", "Jackson"), ("httpclient", "Apache HttpClient"),
    ("cxf", "Apache CXF"), ("camel", "Apache Camel"), ("spark-core", "Spark core"), ("hadoop-common", "Hadoop common"),
]

JAVA_RE = re.compile(r"java(?:\.exe)?\s+(.*)$", re.I)
MAIN_RE = re.compile(r"\s([a-z][\w]*(?:\.[\w]+)+\.[A-Z]\w*)\s+(--context=\S+)?", re.U)
XMX_RE = re.compile(r"(-Xm[sx]\S+|-XX:\S+|-D[\w.]+=\S*)")


class Entries:
    """Uniform access to a zip or a directory."""

    def __init__(self, path: str):
        self.path = path
        self.is_zip = zipfile.is_zipfile(path)
        if self.is_zip:
            self.zf = zipfile.ZipFile(path)
            self.names = [i.filename for i in self.zf.infolist() if not i.is_dir()]
            self.sizes = {i.filename: i.file_size for i in self.zf.infolist()}
        elif os.path.isdir(path):
            self.names, self.sizes = [], {}
            for root, _dirs, files in os.walk(path):
                for f in files:
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, path).replace(os.sep, "/")
                    self.names.append(rel)
                    self.sizes[rel] = os.path.getsize(full)
        else:
            raise ValueError(f"{path} is neither a zip file nor a directory")
        self.names.sort()

    def read(self, name: str, limit: int = 2_000_000) -> str:
        if self.is_zip:
            data = self.zf.read(name)[:limit]
        else:
            with open(os.path.join(self.path, name), "rb") as fh:
                data = fh.read(limit)
        return data.decode("utf-8", "replace")


def parse_properties(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        s = line.strip()
        if not s or s[0] in "#!":
            continue
        if "=" in s:
            k, v = s.split("=", 1)
        elif ":" in s:
            k, v = s.split(":", 1)
        else:
            k, v = s, ""
        out[k.strip()] = v.strip()
    return out


def analyse(path: str) -> dict:
    e = Entries(path)
    res: dict = {
        "source": path, "kind": "zip" if e.is_zip else "directory", "entries": len(e.names),
        "launchers": [], "jobInfo": None, "contexts": {}, "libs": [], "drivers": [], "job_jars": [],
        "items": [], "sources": [], "log4j": [], "other_config": [], "warnings": [],
    }
    for n in e.names:
        low = n.lower()
        base = n.rsplit("/", 1)[-1]
        if re.search(r"_run\.(sh|bat|ps1)$", low) or re.search(r"/run\.(sh|bat)$", low):
            res["launchers"].append(_parse_launcher(n, e.read(n)))
        elif base == "jobInfo.properties":
            res["jobInfo"] = {"path": n, **parse_properties(e.read(n))}
        elif "/contexts/" in n and low.endswith(".properties"):
            res["contexts"][n] = parse_properties(e.read(n))
        elif low.endswith(".jar"):
            if "/lib/" in n or n.startswith("lib/"):
                res["libs"].append(n)
                for hint, label in DRIVER_HINTS:
                    if hint in base.lower():
                        res["drivers"].append(f"{label} ({base})")
                        break
            else:
                res["job_jars"].append(n)
        elif low.endswith((".item", ".properties", ".screenshot")) and "/items/" in low:
            res["items"].append(n)
        elif "/src/" in low and low.endswith(".java"):
            res["sources"].append(n)
        elif re.search(r"log4j2?\.(xml|properties)$", low):
            res["log4j"].append(n)
        elif low.endswith((".properties", ".xml", ".cfg", ".yaml", ".yml", ".json")):
            res["other_config"].append(n)

    # job folder naming heuristics
    tops = sorted({n.split("/", 1)[0] for n in e.names if "/" in n})
    res["top_level_dirs"] = tops
    if not res["launchers"]:
        res["warnings"].append("no *_run.sh/.bat launcher found - not a standalone Job build? (OSGi bundle, microservice jar or items export)")
    if not res["libs"]:
        res["warnings"].append("no lib/*.jar found - exported with 'Extract the zip file' off, or libs are referenced externally")
    if res["jobInfo"] is None:
        res["warnings"].append("no jobInfo.properties (older export or non-Job artifact)")
    if not res["contexts"]:
        res["warnings"].append("no contexts/*.properties - 'Context scripts' was not selected at build; parameters must come from --context_param")
    return res


def _parse_launcher(name: str, text: str) -> dict:
    info = {"path": name, "shell": "bat" if name.lower().endswith(".bat") else "ps1" if name.lower().endswith(".ps1") else "sh",
            "java_line": None, "main_class": None, "default_context": None, "jvm_args": [], "classpath_style": None,
            "cd_to": None}
    for line in text.splitlines():
        s = line.strip()
        m = re.search(r"^cd\s+(.+)$", s)
        if m and not info["cd_to"]:
            info["cd_to"] = m.group(1).strip('"')
        if re.search(r"\bjava(?:\.exe)?\b", s) and ("-cp" in s or "-classpath" in s or ".jar" in s):
            info["java_line"] = s
            mc = re.search(r"\s((?:[a-z_][\w]*\.)+[A-Z]\w*)(?:\s|$)", s)
            if mc:
                info["main_class"] = mc.group(1)
            dc = re.search(r"--context=(\S+)", s)
            if dc:
                info["default_context"] = dc.group(1).strip('"\'')
            info["jvm_args"] = XMX_RE.findall(s)
            if "lib/*" in s or "lib\\*" in s:
                info["classpath_style"] = "wildcard lib/*"
            elif "$ROOT_PATH" in s or "%ROOT_PATH%" in s:
                info["classpath_style"] = "explicit jar list via ROOT_PATH"
            else:
                info["classpath_style"] = "explicit"
    return info


def render(res: dict) -> str:
    L = [f"# Talend job export: {res['source']} ({res['kind']}, {res['entries']} entries)"]
    ji = res["jobInfo"]
    if ji:
        L.append("\n## jobInfo.properties")
        for k in ("project", "projectName", "job", "jobName", "jobVersion", "contextName", "jobType", "applicationType",
                  "date", "commandLineVersion", "productVersion", "gitCommitId", "jobDefaultContext"):
            if k in ji:
                L.append(f"- {k} = `{ji[k]}`")
        extra = {k: v for k, v in ji.items() if k not in ("path",) and k not in (
            "project", "projectName", "job", "jobName", "jobVersion", "contextName", "jobType", "applicationType",
            "date", "commandLineVersion", "productVersion", "gitCommitId", "jobDefaultContext")}
        for k, v in extra.items():
            L.append(f"- {k} = `{v}`")
    L.append("\n## Launchers")
    if not res["launchers"]:
        L.append("(none)")
    for l in res["launchers"]:
        L.append(f"- `{l['path']}` ({l['shell']}): main class `{l['main_class'] or '?'}`, default context "
                 f"`{l['default_context'] or '?'}`, JVM args `{' '.join(l['jvm_args']) or '-'}`, classpath {l['classpath_style'] or '?'}")
    L.append("\n## Contexts")
    if not res["contexts"]:
        L.append("(no contexts/*.properties bundled)")
    for path, kv in res["contexts"].items():
        L.append(f"- `{path}`: " + ", ".join(
            f"{k}={'<enc>' if v.startswith('enc:') else v}" for k, v in kv.items()))
    L.append(f"\n## Libraries ({len(res['libs'])} jars)")
    if res["drivers"]:
        L.append("Notable: " + "; ".join(sorted(set(res["drivers"]))))
    if res["job_jars"]:
        L.append("Job/routines jars outside lib/: " + ", ".join(res["job_jars"]))
    if res["items"]:
        L.append(f"\n## Bundled items ({len(res['items'])}): " + ", ".join(res["items"][:12]) + (" ..." if len(res["items"]) > 12 else ""))
    if res["sources"]:
        L.append(f"\n## Bundled sources ({len(res['sources'])} .java)")
    if res["log4j"]:
        L.append("\n## Logging config: " + ", ".join(res["log4j"]))
    if res["other_config"]:
        L.append("\n## Other config files: " + ", ".join(res["other_config"][:15]))
    L.append("\n## How to run")
    l = next((x for x in res["launchers"] if x["shell"] == "sh"), None) or (res["launchers"][0] if res["launchers"] else None)
    if l:
        ctx = l["default_context"] or "Default"
        first_ctx = next(iter(res["contexts"].values()), {})
        sample = " ".join(f"--context_param {k}=<value>" for k in list(first_ctx)[:3]) or "--context_param KEY=VALUE"
        L.append("```sh")
        L.append(f"unzip -q {os.path.basename(res['source'])} -d build && cd build/{res['top_level_dirs'][0] if res['top_level_dirs'] else '<job>'}")
        L.append(f"chmod +x {os.path.basename(l['path'])}")
        L.append(f"./{os.path.basename(l['path'])} --context={ctx} {sample}")
        L.append("echo \"exit code: $?\"   # 0 = OK, 1 = uncaught error, tDie code otherwise")
        L.append("```")
        L.append("Override memory by editing the -Xmx in the launcher or exporting JAVA_TOOL_OPTIONS; "
                 "add -Dlog4j.configurationFile=... to point at your own log4j2.xml.")
    else:
        L.append("No launcher: for an OSGi bundle deploy to Talend Runtime (`bundle:install`), for a microservice run `java -jar <name>.jar`.")
    if res["warnings"]:
        L.append("\n## Warnings")
        for w in res["warnings"]:
            L.append(f"- {w}")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("path", help="exported job zip or extracted directory")
    ap.add_argument("--format", choices=("markdown", "json"), default="markdown")
    ap.add_argument("--list", action="store_true", help="list every entry")
    a = ap.parse_args(argv)
    try:
        res = analyse(a.path)
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if a.list:
        for n in Entries(a.path).names:
            print(n)
        return 0
    sys.stdout.write(json.dumps(res, indent=2) + "\n" if a.format == "json" else render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
