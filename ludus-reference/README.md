# Ludus reference data

Facts about how the Ludus server builds templates and validates sources, copied from the upstream
repositories so CI enforces **Ludus' own definitions** rather than a hand-written list. Each file records its
provenance; `versions.json` holds the upstream commits everything was generated from.

| File | What it is | Upstream source |
| --- | --- | --- |
| `versions.json` | Packer and plugin versions the Ludus server installs | `ludus-server/dependency_updates.go`, `ludus-server/ansible/proxmox-install/stage-3.yml` |
| `packer-variables.json` | The `-var`s, `PKR_VAR_` variables and environment Ludus passes to `packer build` | `ludus-api/api_template_management.go`, `docs/docs/using-ludus/templates.md` |
| `proxmox-bindings.json` | Which Proxmox builder attributes must be driven by those variables, name rules, OS detection, ansible provisioner rules | builtin templates, `ludus-server/packer/README.md`, docs |
| `credentials.json` | Credentials Ludus uses per guest OS when deploying ranges | `ludus-server/ansible/range-management/group_vars/*.yml` |
| `templates.json` | Template names that already exist on every Ludus server (builtins + auto-registered Bad Sector Labs source) | `ludus-server/packer/*`, `ludus-source-bsl/templates/*` |
| `range-config.jsonschema` | The range config schema Ludus validates blueprints against (verbatim copy) | `ludus-server/ansible/user-files/range-config.jsonschema` |

## Refreshing

```bash
make update-reference          # re-derive everything from upstream main and rewrite these files
make check-reference           # exit non-zero if upstream main has drifted from the vendored copies
```

The `ludus-reference-drift` workflow runs the check weekly and opens an issue when Ludus changes something
these rules depend on. Review the diff, run `make update-reference`, adjust the linter if a rule changed, and
commit the result.
