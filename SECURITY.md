# Security

Use **Security → Report a vulnerability** on this repository (GitHub private
vulnerability reporting). Do not open a public issue for a security problem.

You will get an acknowledgement within 5 working days. Fixes ship as a patch
release with a `CHANGELOG.md` entry under *Security*.

Only the latest minor release line receives security fixes.

The range this source deploys is deliberately vulnerable: weak and reused
passwords, Kerberoastable accounts, an upload-to-webshell target and the rest
of the FGNW scenario are the product, not defects, and they live inside a
contained Ludus range. A report is about the automation — the roles, the
plays, the templates, the gate — not about the lab's intended weaknesses.

## What is in place

- Secret scanning (`gitleaks`) on every commit locally and on every pull request;
  the only allowlisted matches are the lab's synthetic AD passwords and a
  published Microsoft KMS client key (`.gitleaks.toml`, `.gitleaksignore`).
- Dependency updates with a 7-day cooldown (Dependabot) and SHA-pinned actions.
- Vendored third-party payloads carry their sha256 in the owning role's
  `meta/upstream.yml`; `scripts/check-upstream.py` fails the gate on drift.
