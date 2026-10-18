# jrs-etl

[![CI](https://github.com/robertgorsuch/jrs-etl/actions/workflows/ci.yml/badge.svg)](https://github.com/robertgorsuch/jrs-etl/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/robertgorsuch/jrs-etl)](LICENSE)

> A Claude Code plugin marketplace holding **talend-etl**: a complete Talend /
> Qlik Talend data-integration knowledge base for Claude, with offline helpers
> to inspect job files and exports and to drive TAC and Talend Cloud.

The skill is a lean `SKILL.md` index over 13 deep reference files (about
10,500 lines) covering Talend Studio, the connector library at parameter level,
tMap and expression semantics, Big Data / Spark jobs, ESB Routes and Services,
build and deployment options (standalone, TAC/JobServer, Talend Cloud TMC and
Remote Engine, Talend Runtime, Docker, CI Builder), the TMC / MetaServlet /
CommandLine / Component Kit APIs, `.item` / `.properties` / Jobscript / export
formats, Data Quality / Stewardship / MDM, the product and version history, and
a design-pattern and troubleshooting playbook.

## Install

In Claude Code:

```
/plugin marketplace add robertgorsuch/jrs-etl
/plugin install talend-etl@jrs-etl
```

Then ask anything Talend, or use the slash commands:

| Command | What it does |
|---|---|
| `/talend-etl:inspect <file>` | Explain a job `.item` or a Build Job zip in plain language |
| `/talend-etl:review <file>` | Design-review a job against the skill's scorecard |
| `/talend-etl:tmc ...` | Operate Talend Management Console through the TMC API (dry-run first) |

## Layout

| Path | Contents |
|---|---|
| `.claude-plugin/marketplace.json` | Marketplace manifest (one plugin: `talend-etl`) |
| `plugins/talend-etl/.claude-plugin/plugin.json` | Plugin manifest |
| `plugins/talend-etl/commands/` | The three slash commands |
| `plugins/talend-etl/skills/talend-etl/SKILL.md` | The skill index Claude loads first |
| `plugins/talend-etl/skills/talend-etl/references/` | 13 reference files; each ends with a Gotchas table and a Sources list |
| `plugins/talend-etl/skills/talend-etl/scripts/` | `inspect_job_item.py`, `inspect_job_export.py`, `metaservlet.py`, `tmc_api.py`, `check_docs.py` (Python 3 stdlib only) |
| `plugins/talend-etl/skills/talend-etl/fixtures/` | A Studio-8-shaped sample job (`LOAD_CUSTOMERS_0.1.item` + `.properties`) |
| `plugins/talend-etl/skills/talend-etl/tests/` | Unit tests for the scripts (`python -m unittest`) |
| `plugins/talend-etl/skills/talend-etl/evals/` | Eval prompts, trigger eval set, and results of two eval iterations and a description-optimization run |
| `plugins/talend-etl/CHANGELOG.md` | Plugin changelog |

## Verification status

Every reference is doc-derived (help.qlik.com / help.talend.com search
evidence, Talend GitHub, Maven Central, Talend policy PDFs) combined with model
knowledge. Nothing has been exercised against a live Studio, TAC or TMC yet.
Facts that could not be confirmed against documentation are marked
`(unverified)` inside the references. When an exact label matters, confirm it
in the Studio Component view or the TMC Swagger UI for your release.

The helper scripts are tested offline against the bundled fixture and a
synthetic export; they parse what Studio writes but have not yet been run on a
customer export. Open an issue with a redacted `.item` if one trips them.

## Evals

`skills/talend-etl/evals/results/` holds two iterations of a with-skill versus
without-skill comparison (three realistic prompts, independently graded) and a
description-optimization run. Iteration 2: skill 28/28 assertions versus
baseline 26/28, with fewer false factual claims. See each folder's README.

## Development

```sh
cd plugins/talend-etl/skills/talend-etl
python3 scripts/check_docs.py              # links, required sections, ASCII, manifests
python3 -m unittest -v tests/test_scripts.py
```

CI runs both on Ubuntu and Windows plus a gitleaks secret scan.

## Related

The sibling repository
[AI-JasperReports-Generator](https://github.com/robertgorsuch/AI-JasperReports-Generator)
holds the `jasper-deploy` skill for JasperReports Server.

## License

Apache-2.0. See [LICENSE](LICENSE).
