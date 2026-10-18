# Security Policy

## Reporting a vulnerability

Please report vulnerabilities privately via GitHub's **private vulnerability
reporting**: [Security → Report a vulnerability](https://github.com/robertgorsuch/AI-JasperReports-Generator/security/advisories/new).
Do not open a public issue for security reports. You should receive a response
within a few business days.

## Supported versions

Only the latest release of the `jasper-deploy` plugin (and current `main`) is
supported with fixes.

## Scope and deployment notes

This is a demo/reference project. Two areas deserve care in any deployment:

- **`webapp/jasper-wizard`** executes user-supplied SQL with the configured
  data source's privileges and publishes to JasperReports Server using stored
  admin credentials. It is designed as an **internal, trusted-user tool**:
  keep it behind the JRS login and a network boundary, and never expose it to
  untrusted users or the public internet.
- **Credentials** are never stored in this repository. The skill resolves
  them from script parameters, `JRS_URL`/`JRS_USER`/`JRS_PASS` environment
  variables, or a gitignored `jrs.config.json` (a `passwordCommand` hook is
  available for secret managers). CI runs a gitleaks scan over full history
  on every push and pull request.

## Hardening references

The skill ships doc-derived references for securing JasperReports Server
itself (keystore, CSRF, SSL, domain whitelist, lockout policies):
`plugins/jasper-deploy/skills/jasper-deploy/references/server-hardening.md`.
