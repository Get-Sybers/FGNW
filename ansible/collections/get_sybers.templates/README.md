# get_sybers.templates

Shared Packer template-baking content for the Get-Sybers Ludus sources. It exists
to remove the per-template duplication that used to live under `templates/`: the
same role, module, and build playbooks were copied verbatim into every template
directory. They now live here once and are consumed by each template's `.pkr.hcl`
build through the native Ansible mechanism — `requirements.yml` +
`ansible-galaxy collection install`, referenced by FQCN.

> Design rule (ansible-standards §2): **the role acts, the playbook decides.** The
> roles below carry the actions; each template keeps only a thin build entry point
> (its `.pkr.hcl`, and for Windows a two-line `import_playbook` wrapper) that
> selects which of them run.

## Contents

| Kind | Reference | Was |
| --- | --- | --- |
| role | `get_sybers.templates.macos_template` | `templates/macos-*/roles/macos_template/` (×5, identical) |
| module | `get_sybers.templates.proxmox_iso_download` | `.../macos_template/library/proxmox_iso_download.py` (×5) |
| role | `get_sybers.templates.windows_ngen` | `templates/win*/ansible/ngen.yml` (×3, identical) |
| role | `get_sybers.templates.metasploitable_provision` | `templates/metasploitable-*/ansible/provision.yml` (×2, identical) |
| playbook | `playbooks/build.yml` | `templates/macos-*/build.yml` (×5) + `macos_template_vars.yml` (×5) |
| playbook | `playbooks/ngen.yml` | thin play around `windows_ngen` |
| playbook | `playbooks/provision.yml` | thin play around `metasploitable_provision` |

The three roles and the module are referenced by FQCN; the playbooks are invoked
by their collection-qualified name (the collection name followed by the playbook
stem). Each consuming template's build definition holds the exact command.

## How templates consume it

Each consuming template ships a `requirements.yml` pinning this collection and
installs it at build time, then refers to its content by FQCN:

- **macOS** (`templates/macos-*`): the `.pkr.hcl` `shell-local` provisioner runs
  `ansible-galaxy collection install -r requirements.yml` then invokes the
  collection's `build.yml` play. The build env-bridge lives in
  `playbooks/vars/macos_template_vars.yml`.
- **Windows** (`templates/win*`): the Packer `ansible` provisioner sets
  `galaxy_file = requirements.yml` and runs the two-line `ansible/ngen.yml`,
  which `import_playbook`s the collection's `ngen.yml` play.
- **Metasploitable** (`templates/metasploitable-*`): `scripts/import.sh` installs
  the collection and invokes the collection's `provision.yml` play.

## Requirements

- `ansible-core >= 2.15` (`meta/runtime.yml`).
- `community.windows` (for `windows_ngen`), declared in `galaxy.yml` and pinned in
  the consuming template's `requirements.yml`.

## Testing

`extensions/molecule/` holds the native molecule scenarios (docker driver,
Debian substrate), run with `molecule test --all`. Roles whose real target is a
live Proxmox node / a Windows guest / a legacy Linux image are exercised by
negative scenarios (clean failure on bad input) here and against real
infrastructure in CI, matching the `get_sybers.range` and `get_sybers.cluster`
pattern.
