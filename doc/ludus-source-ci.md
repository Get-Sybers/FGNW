# The Ludus-source CI gate

FGNW is a [Ludus](https://docs.ludus.cloud/) source, so beyond the house gate
(the [CI workflow](standards/03-ansible-ci-workflow.md) and [linting, conformance
and the merge gate](standards/04-Linting-and-Conformance.md)) it runs a second
gate that holds the Packer templates and the blueprint to the conventions the
Ludus server itself relies on. Two GitHub Actions workflows and a handful of
scripts make it up, and every fact the rules enforce is vendored under
`ludus-reference/` so the checks run offline against a recorded revision of
upstream Ludus.

## Required checks

`.github/rulesets/main.json` requires two status checks before `main` accepts a
merge:

- `all_green` — the house gate (`ci.yml`: the `lint` prek job and the `conform`
  job described in the standards docs above).
- `ludus-source-green` — this gate (`ludus-source.yml`).

## `ludus-source.yml`

Runs on every pull request and push to `main`, and on demand
(`workflow_dispatch`). Its jobs:

| Job | Runs | Proves |
| --- | --- | --- |
| `source-lint` | `python3 scripts/ludus_source_lint.py --root . --format github`, then `python3 -m pytest -q tests` | every template, blueprint and range-config matches the Ludus conventions, and the linter's own rules still pass their self-tests |
| `packer-smoke` | `scripts/install_ludus_packer.sh` then `scripts/packer_smoke.sh --inspect` | every template `packer fmt`-checks and `packer validate`s with the plugin set and variable set the Ludus server uses |
| `reference-check` | `scripts/update_ludus_reference.py --check` pinned to the commits `ludus-reference/versions.json` records as its `provenance` | the committed `ludus-reference/` was not hand-edited away from its recorded upstream source |
| `ludus-source-green` | aggregates the three above | the single required status check for this workflow |

The yamllint, ansible-lint, shellcheck, shfmt and actionlint that a standalone
Ludus source might also run here are already part of the house gate (prek and
`conform`), so this workflow does not repeat them.

## The source linter

`scripts/ludus_source_lint.py` (locally `make lint-source`; its self-tests are
`make test-source`) checks:

- **Templates** (`templates/<name>/*.pkr.hcl`) — one Packer file per directory,
  valid HCL2, a `vm_name` that resolves to a literal ending in `-template`, the
  Ludus build-time variables declared exactly as Ludus passes them, the Proxmox
  builder attributes bound to those variables rather than hard-coded, the
  `proxmox-iso` (or `proxmox-clone`) builder, a literal `os`, the ansible
  provisioner conventions, and that every file the template references exists.
- **Blueprints and range-configs** (`blueprints/<name>/`) — the range-config
  validated against the Ludus JSON schema, `vm_name` validity and uniqueness,
  and that every template a range-config names is shipped by this source, is a
  Ludus builtin, or comes from the Bad Sector Labs source.

Every Ludus-specific fact the rules use — the injected build-time variables, the
Proxmox builder bindings, the default credentials, the builtin and Bad Sector
Labs template names, and the range-config schema — is read from
`ludus-reference/`, never hard-coded. Per-rule severity overrides and extra
known template names live in `.ludus-lint.yml`.

### macOS templates

A template built from a `null` source whose `vm_name` contains `macos` is a
macOS template: macOS cannot use the `proxmox-iso` builder (it has no
answer-file installer and boots through OpenCore), and Ludus classifies it by
that name substring. The linter skips the Proxmox-builder rules for such a
template and checks the rest.

## The Packer smoke test

`scripts/install_ludus_packer.sh` installs Packer and the two plugins at the
versions the Ludus server pins — `ludus-reference/versions.json` records
`badsectorlabs/proxmox` and `hashicorp/ansible` — and `scripts/packer_smoke.sh`
runs, from each template directory and with the same `-var` set and `PROXMOX_*`
environment the Ludus server's build passes:

```text
packer fmt -check -diff <template>.pkr.hcl
packer validate [-evaluate-datasources] -var <ludus vars...> <template>.pkr.hcl
```

A template that validates here validates on a Ludus server: unknown builder
attributes, undeclared `-var`s, unset variables and missing files all fail
natively. Locally, `make packer-tools` then `make packer-validate`.

## Keeping the reference data current

`ludus-reference/` is derived from upstream Ludus and the Bad Sector Labs source
at a recorded commit (each file carries its `provenance`). Two checks keep it
honest, and they watch different things:

- On every pull request, the `reference-check` job re-derives it from the exact
  commits the `provenance` records and fails on any mismatch — so a hand-edit or
  a stale file is caught, while upstream Ludus advancing does not turn unrelated
  PRs red.
- `ludus-reference-drift.yml` re-derives it from upstream `main` every Monday
  (`scripts/update_ludus_reference.py`) and opens a tracking issue when a fact
  the rules depend on has changed, so the gate never silently falls behind the
  Ludus server.

Regenerate it by hand with `make update-reference`; compare against upstream
`main` with `make check-reference`.

## Make targets

| Target | Does |
| --- | --- |
| `make lint-source` | the source, template and blueprint linter |
| `make test-source` | the linter's self-tests |
| `make packer-tools` | install Packer and the Ludus plugin set into `.tools/` |
| `make packer-validate` | `packer fmt -check` and `packer validate` on every template |
| `make check-reference` | fail if upstream Ludus drifted from `ludus-reference/` |
| `make update-reference` | regenerate `ludus-reference/` from upstream Ludus |
