# Packer templates

Each `templates/<name>/` directory is one self-contained Ludus Packer template — the same shape as the
[Bad Sector Labs source templates](https://github.com/badsectorlabs/ludus-source-bsl/tree/main/templates):

```
templates/<name>/
├── <name>.pkr.hcl       the Packer build config — exactly one *.pkr.hcl (or *.pkr.json) per directory
├── icon.png             optional catalog icon referenced by the icon_path variable (square, transparent PNG)
├── http/                Linux: preseed / kickstart / autoinstall files served to the installer
├── ansible/             playbooks run by the ansible provisioner at build time
├── scripts/             shell / PowerShell provisioner scripts
└── Autounattend.xml     Windows only: unattended install answer file (must be in the directory root)
```

The template name users put in a range config is the resolved `vm_name` of the `source` block, **not** the
directory name. Keep the `-template` suffix and prefix the name with this source's slug (`ludusplusplus-`) so it
never collides with a builtin or Bad Sector Labs template.

## Available templates

| Template | Description |
| --- | --- |
| `ludusplusplus-debian-13-x64-server-template` | Debian 13 (Trixie) minimal x64 server. Credentials `debian:debian`. Adapted from the [Ludus Packer starter](https://github.com/badsectorlabs/ludus_packer_template). |

Build with `ludus templates build -n <template-name>` after `ludus source add`.

## Authoring rules (enforced by CI)

The CI job `source-structure` runs `scripts/ludus_source_lint.py`, and the `packer` job runs `packer fmt -check`
and `packer validate` with the exact variables, environment, Packer version, and plugin set the Ludus server uses
(`ludus-reference/`). In short, a template must:

1. Declare the Ludus variable block exactly as documented (`proxmox_url`, `proxmox_host`, `proxmox_username`,
   `proxmox_password` (sensitive), `proxmox_storage_pool`, `proxmox_storage_format`, `proxmox_skip_tls_verify`
   (bool), `proxmox_pool`, `iso_storage_pool`, `ansible_home`, `ludus_nat_interface`) with **no defaults**.
   Packer rejects a `-var` that is not declared, so a missing one breaks every build.
2. Give every other variable a default — Ludus passes nothing else, and Packer fails on an unset variable.
3. Wire the Proxmox builder to those variables instead of local values: `proxmox_url`, `node`,
   `insecure_skip_tls_verify`, `pool`, `disks.storage_pool`, `disks.format`, `network_adapters.bridge`,
   `boot_iso.iso_storage_pool` (and `efi_config`/`tpm_config`/`additional_iso_files` storage pools when present).
   Never set `vm_id`, `template_name`, or `skip_convert_to_template`, and never hard-code API credentials.
4. Resolve `vm_name` to a literal ending in `-template` (Ludus reads it from the file), declare `variable "os"`
   with a literal Proxmox OS type (Ludus classifies the template from it), and use the `ssh` or `winrm`
   communicator with credentials that match the Ludus group_vars for that OS.
5. Set `ANSIBLE_HOME=${var.ansible_home}` and `skip_version_check = true` on every ansible provisioner, and keep
   every referenced path (playbooks, scripts, `http/`, `cd_files`) inside the template directory.
6. Provide a static `description` variable (shown in the catalog) and, for Windows, an `Autounattend.xml`.

Run `make lint` and `make packer-validate` locally before pushing.
