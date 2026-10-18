#!/usr/bin/env python3
"""Offline consistency check for the talend-etl skill (CI gate).

Verifies that:
- every ``references/*.md`` file is linked from SKILL.md and vice versa;
- every relative markdown link in SKILL.md and references/ resolves to a file;
- every reference file carries the Verification block, a Contents section,
  a Gotchas table and a Sources section;
- every script named in SKILL.md exists and every scripts/*.py is mentioned;
- files are ASCII-only (the style rule) and SKILL.md stays under 500 lines;
- the plugin manifest and marketplace entry agree on the skill path.

Exit code 1 on any failure; prints a summary either way.
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
PLUGIN = os.path.dirname(os.path.dirname(SKILL))
REPO = os.path.dirname(os.path.dirname(PLUGIN))
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s#]+)(?:#[^)]*)?\)")
REQUIRED_SECTIONS = ["> Verification:", "## Contents", "## Gotchas", "## Sources"]


def main() -> int:
    errors, warnings = [], []
    skill_md = os.path.join(SKILL, "SKILL.md")
    text = open(skill_md, encoding="utf-8").read()
    lines = text.count("\n") + 1
    if lines > 500:
        errors.append(f"SKILL.md has {lines} lines (> 500); move detail into references/")

    refs_dir = os.path.join(SKILL, "references")
    refs = sorted(f for f in os.listdir(refs_dir) if f.endswith(".md"))
    for r in refs:
        if f"references/{r}" not in text and r not in text:
            errors.append(f"references/{r} is not linked from SKILL.md")

    scripts = sorted(f for f in os.listdir(HERE) if f.endswith(".py") and not f.startswith("_"))
    for s in scripts:
        if s not in text:
            errors.append(f"scripts/{s} is not mentioned in SKILL.md")
    for m in re.finditer(r"scripts/([\w.-]+\.py)", text):
        if not os.path.exists(os.path.join(HERE, m.group(1))):
            errors.append(f"SKILL.md names scripts/{m.group(1)} which does not exist")

    def check_links(path: str, body: str):
        base = os.path.dirname(path)
        for m in LINK_RE.finditer(body):
            target = m.group(1)
            if re.match(r"^[a-z]+://", target) or target.startswith("mailto:"):
                continue
            if not os.path.exists(os.path.normpath(os.path.join(base, target))):
                errors.append(f"{os.path.relpath(path, SKILL)}: broken link -> {target}")

    def check_ascii(path: str, body: str):
        bad = [(i + 1, ch) for i, line in enumerate(body.splitlines()) for ch in line if ord(ch) > 127]
        if bad:
            ln, ch = bad[0]
            warnings.append(f"{os.path.relpath(path, SKILL)}: {len(bad)} non-ASCII chars (first at line {ln}: U+{ord(ch):04X})")

    check_links(skill_md, text)
    check_ascii(skill_md, text)
    total_ref_lines = 0
    for r in refs:
        p = os.path.join(refs_dir, r)
        body = open(p, encoding="utf-8").read()
        total_ref_lines += body.count("\n") + 1
        for sec in REQUIRED_SECTIONS:
            if sec not in body:
                errors.append(f"references/{r}: missing '{sec}'")
        if "## Gotchas" in body:
            got = body.split("## Gotchas", 1)[1].split("\n## ", 1)[0]
            rows = [l for l in got.splitlines() if l.startswith("|") and not set(l) <= set("|-: ")]
            if len(rows) < 4:
                warnings.append(f"references/{r}: Gotchas table has only {max(0, len(rows) - 1)} rows")
        check_links(p, body)
        check_ascii(p, body)

    # manifests
    try:
        plugin = json.load(open(os.path.join(PLUGIN, ".claude-plugin", "plugin.json")))
        mp = json.load(open(os.path.join(REPO, ".claude-plugin", "marketplace.json")))
        entry = next((pl for pl in mp["plugins"] if pl["name"] == plugin["name"]), None)
        if entry is None:
            errors.append("marketplace.json has no entry for plugin " + plugin["name"])
        elif not os.path.exists(os.path.join(REPO, entry["source"], "skills", "talend-etl", "SKILL.md")):
            errors.append(f"marketplace source {entry['source']} does not contain skills/talend-etl/SKILL.md")
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        errors.append(f"manifest check failed: {exc}")

    fm = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not fm or "name:" not in fm.group(1) or "description:" not in fm.group(1):
        errors.append("SKILL.md frontmatter must declare name and description")

    print(f"talend-etl check_docs: SKILL.md {lines} lines, {len(refs)} references ({total_ref_lines} lines), {len(scripts)} scripts")
    for w in warnings:
        print("WARN  " + w)
    for e in errors:
        print("ERROR " + e)
    print("FAIL" if errors else "OK")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
