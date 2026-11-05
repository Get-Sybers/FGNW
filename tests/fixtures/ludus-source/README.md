# LudusPlusPlus

A [Ludus](https://ludus.cloud) **source**: a versioned bundle of Packer templates, blueprints and Ansible content
that a Ludus server installs with one command, plus continuous integration that holds every artifact to the
conventions the Ludus server itself relies on (the build-time variables it injects, the Proxmox builder settings it
expects, the credentials it deploys with, and the manifest formats it parses).

```bash
# Register the source and pick what to install (or pass --all)
ludus source add https://github.com/Get-Sybers/LudusPlusPlus

# Build the template this source ships, apply the example blueprint, deploy
ludus templates build -n ludusplusplus-debian-13-x64-server-template
ludus blueprint apply <sourceID>/example
ludus range deploy
```

`<sourceID>` is shown by `ludus source list` (derived as `<userID>-Get-Sybers-LudusPlusPlus` unless you pass
`--id`). Full reference: [Ludus sources](https://docs.ludus.cloud/docs/using-ludus/sources).

## What this source ships

| Artifact | Name | Notes |
| --- | --- | --- |
| Packer template | `ludusplusplus-debian-13-x64-server-template` | Debian 13 (Trixie) minimal server, `debian:debian`, built from the Ludus Packer starter. See [`templates/`](templates/README.md). |
| Blueprint | `example` | One VM from the template above; proves the source installs and deploys end to end. See [`blueprints/`](blueprints/README.md). |
| Ansible roles / collections | none yet | Vendor them under [`ansible/`](ansible/README.md), as directories or git submodules. |

## Layout

```
source.yml                   repo-level metadata read by `ludus source list`
templates/<name>/            one self-contained Packer template per directory
blueprints/<id>/             blueprint.yml + range-config.yml + requirements.yml + README.md
ansible/roles/<name>/        Ansible roles (standard layout, meta/main.yml required)
ansible/collections/<dir>/   Ansible collections (galaxy.yml required)
docs/                        notes on templates: the Ludus templates reference, default passwords, macOS on Proxmox
ludus-reference/             facts copied from upstream Ludus that the CI rules enforce (see below)
scripts/                     the linter, the Packer smoke test, the Ludus-pinned tool installer, the reference updater
tests/                       self-tests for the linter
.github/workflows/           ci.yml (every push / PR) and ludus-reference-drift.yml (weekly)
```

## Continuous integration

Every push and pull request runs [`ci.yml`](.github/workflows/ci.yml):

| Job | What it proves |
| --- | --- |
| **source-structure** | `scripts/ludus_source_lint.py` walks the repository the way `ludus source add` does and checks `source.yml`, every blueprint, template, role and collection against the Ludus rules (table below). Findings are GitHub annotations. The linter's own tests run afterwards. |
| **packer** | Installs Packer and the Packer plugins at the exact versions the Ludus server installs (`badsectorlabs/proxmox`, not `hashicorp/proxmox`, plus `hashicorp/ansible`) and runs `packer fmt -check` and `packer validate` from each template directory with the same `-var` set, `PKR_VAR_*` variables and `PROXMOX_*` environment that `ludus templates build` uses. Unknown builder attributes, undeclared `-var`s, variables without defaults and missing files fail here exactly as they would on a Ludus server. |
| **ansible-and-yaml** | `yamllint` over the repository and `ansible-lint` (production profile) over the roles, collections and template-build playbooks. |
| **shell-and-workflows** | `shellcheck` over the scripts and `actionlint` over the workflows. |

[`ludus-reference-drift.yml`](.github/workflows/ludus-reference-drift.yml) runs weekly: it re-derives
`ludus-reference/` from upstream Ludus `main` and opens an issue when the variables, plugin versions,
credentials, builtin template names or the range-config schema changed, so these rules follow what Ludus
actually does instead of a list written once.

### Rules the linter enforces

Run `python scripts/ludus_source_lint.py --list-rules` for the catalogue. In short:

- **Source (S)** – at least one artifact; a valid `source.yml` (`manifest_version: 1`, string fields, authors list);
  git submodules populated and inside `blueprints/`, `templates/`, `ansible/roles/`, `ansible/collections/`.
- **Templates (T)** – exactly one `*.pkr.hcl` per directory; the Ludus variable block declared with the documented
  types and **no defaults**; every other variable has a default; `vm_name` resolves (as Ludus resolves it) to a
  DNS-valid name ending in `-template` that is unique and does not collide with a builtin or Bad Sector Labs name;
  a literal `variable "os"` so Ludus can classify the OS; `proxmox_url`, `node`, `insecure_skip_tls_verify`,
  `pool`, disk storage pool and format, network bridge, ISO/EFI/TPM storage pools and API credentials bound to the
  Ludus variables rather than hard-coded; no `vm_id`, `template_name` or `skip_convert_to_template`; ansible
  provisioners set `ANSIBLE_HOME=${var.ansible_home}` and `skip_version_check = true`; every referenced file exists
  inside the template directory; Windows templates ship `Autounattend.xml` and use WinRM over HTTPS; baked-in
  credentials match the Ludus `group_vars` for the guest OS; a static `description` (and optional icon) for the
  catalog. Performance recommendations from the Ludus docs are reported as information.
- **Blueprints (B)** – `blueprint.yml` satisfies the Ludus manifest parser (id matches the directory, semver
  version, relative config path); `range-config.yml` validates against the Ludus JSON schema and the offline
  checks the server runs on apply (name charset, unique names/hostnames/IPs, NetBIOS uniqueness); every referenced
  role is declared in `requirements.yml` or vendored; every referenced template is known; `{{ range_id }}` in VM
  names, no `router:` block, no hard-coded `10.x` addresses.
- **Roles (R) / collections (C)** – `tasks/main.yml` and `meta/main.yml` with a `galaxy_info.description`;
  `galaxy.yml` with `namespace`, `name`, `version` and a description.

Severities can be tuned per rule in [`.ludus-lint.yml`](.ludus-lint.yml), which also allow-lists template names from
other sources that blueprints here may reference.

### The reference data

[`ludus-reference/`](ludus-reference/README.md) holds the upstream facts the checks are built on, each with its
provenance: the `packer build` invocation from `ludus-api/api_template_management.go`, the Packer and plugin
versions from `ludus-server/dependency_updates.go`, the per-OS credentials from
`range-management/group_vars`, the builtin and Bad Sector Labs template names, and a verbatim copy of
`range-config.jsonschema`. `make update-reference` regenerates it; `make check-reference` reports drift.

## Working locally

```bash
make deps              # Python tooling (python-hcl2, PyYAML, jsonschema, yamllint, ansible-lint, pytest)
make packer-tools      # Packer + plugins at the Ludus-pinned versions, into .tools/ (git-ignored)
make lint              # every linter: source rules, yamllint, ansible-lint, shellcheck, actionlint
make packer-validate   # packer fmt -check + packer validate, invoked as the Ludus server does
make test              # the linter's self-tests
make ci                # all of the above
```

`shellcheck` and `actionlint` are expected on `PATH` (`make lint-actions` falls back to the pinned
`rhysd/actionlint` container when the binary is missing).

### Adding a template

1. Copy `templates/ludusplusplus-debian-13/` (or a
   [Bad Sector Labs template](https://github.com/badsectorlabs/ludus-source-bsl/tree/main/templates) for another OS)
   into `templates/<name>/`.
2. Change `vm_name` (keep the `-template` suffix and the `ludusplusplus-` prefix), the ISO, the install answer file
   and `description`; keep the Ludus variable block untouched.
3. Run `make lint-source packer-validate`, then build it on a Ludus server with
   `ludus templates add -d templates/<name> && ludus templates build -n <name>-template`.

### Adding a blueprint

1. Create `blueprints/<id>/` with `blueprint.yml`, `range-config.yml`, `requirements.yml` and a `README.md`
   (the [example](blueprints/example/) is a template for all four).
2. Declare every role the config references in `requirements.yml`, or vendor it under `ansible/roles/`.
3. Run `make lint-source`, then deploy it end to end before opening a pull request.

## Documentation in this repository

- [`docs/templates/ludus-packer.md`](docs/templates/ludus-packer.md) – the Ludus templates reference (copy of the upstream page).
- [`docs/templates/ludus-template-passwords.md`](docs/templates/ludus-template-passwords.md) – default credentials Ludus uses.
- [`docs/templates/ludus-template-building.md`](docs/templates/ludus-template-building.md) – links to the template starters.
- [`docs/templates/installing-MacOSVentura-ProxMox.md`](docs/templates/installing-MacOSVentura-ProxMox.md) – building a macOS template by hand on Proxmox.

## Upstream references

- [Ludus sources](https://docs.ludus.cloud/docs/using-ludus/sources) and [templates](https://docs.ludus.cloud/docs/using-ludus/templates) documentation
- [ludus-source-template](https://github.com/badsectorlabs/ludus-source-template) – the official starting point for a source
- [ludus-source-bsl](https://github.com/badsectorlabs/ludus-source-bsl) – the Bad Sector Labs source Ludus registers automatically
- [ludus_packer_template](https://github.com/badsectorlabs/ludus_packer_template) – the Packer starter this source's template is based on

## License

No license file has been chosen for this repository yet; `source.yml` leaves `license` unset until one is added.
The vendored starter template content is MIT-licensed by Bad Sector Labs.
