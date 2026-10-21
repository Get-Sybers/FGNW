# Changelog

All notable changes to the `get_sybers.templates` collection are documented here;
the source-level changelog (templates, shared roles, the gate) is the repo-root
`CHANGELOG.md`. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this collection
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (`0.y.z`
until the interface is stable).

## 0.1.0

### Added

- Initial collection, factored out of the per-template duplication under
  `templates/`. One shared copy of each, consumed by the `.pkr.hcl` builds via
  `requirements.yml` + `ansible-galaxy`, by FQCN:
  - `macos_template` role (was copied verbatim into all five `macos-*`
    templates) plus its bundled stdlib-only `proxmox_iso_download` module
    (`plugins/modules/`), and the `build.yml` / `macos_template_vars.yml` build playbook
    (`playbooks/`).
  - `windows_ngen` role (was `ansible/ngen.yml`, copied into three Windows
    templates) — .NET native-image generation.
  - `metasploitable_provision` role (was `ansible/provision.yml`, copied into
    both Metasploitable templates) — SSH host-key regeneration and guest-agent
    best-effort install for imported disk images.
