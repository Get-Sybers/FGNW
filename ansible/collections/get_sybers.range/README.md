> **⚠ Read this distinction first — it will save every future reader.**
> The public `ludus_*` ecosystem (`badsectorlabs.ludus_adcs`, `aleemladha.ludus_elastic_agent`,
> `jasonmull.ludus_ghosts_client`, the `get_sybers.*` custom roles, …) are **in-range** roles: they
> run **inside a VM**, applied by Ludus's own deploy pipeline via a range config's `roles:` list.
> **This collection is the opposite.** It **orchestrates Ludus itself** — it drives the `ludus` CLI /
> v2 REST API from the *controller* to set range config, deploy and poll to SUCCESS, enter and verify
> containment, verify the end state, diagnose, and (opt-in) tear down.
House standard: `doc/standards/02-Ansible-Standards.md`. Mirrors the
`get_sybers.infra` foundation pattern (ludus-plusplus source).

- **CLI/API only, never the MCP.** Every role shells the `ludus` CLI or calls the v2 API. The Ludus
  MCP is the *assistant's* observation tool, **not** a pipeline dependency.
- **Secrets: env-only, never a file read.** `ludus_auth` delegates to the shared env-only check
  `get_sybers.ludus_auth_check` (a task-role under this source's `ansible/roles/`): the key comes
  from an exported `LUDUS_API_KEY` only — there is no credential-file fallback — and is
  published as the `no_log` fact `__ludus_api_key`. On a missing/dead key the play FAILS toward the
  admin auth play `get_sybers.cluster` `playbooks/ludus-ra-auth.yml`; it never escalates
  in-play. The key is never placed on argv. CLI tasks pass it via `environment:` under `no_log`.
- **Poll observed state, never a command's exit code** (kubernetes.core pattern). `rangeState=DESTROYED`
  can coexist with live VMs (ERR-14) — teardown guards on the VM *count*, not the state enum.
- **Guard before you parse** (ERR-13). Every `until:` short-circuits on `rc==0` and non-empty,
  `{`-prefixed stdout *before* `from_json`, so an empty dynamic-inventory read cannot raise inside the
  retry condition (an exception in `until:` is a task failure — it would kill all retries on poll 1).
- **Robust, not hardened.** These roles harden the *automation*; the ranges they deploy stay
  deliberately vulnerable — that is the product.

| Role | Purpose |
| --- | --- |
| `ludus_auth` | Auth entry point — composes the shared env-only `get_sybers.ludus_auth_check` (no resolution logic of its own since |
| `ludus_range_config` | Set the range config idempotently (get-compare-set); ERR-03 blueprint-vs-users drift guard. |
| `ludus_range_deploy` | Fire `range deploy` + wait to a terminal state (ERR-13-guarded poll); bounded transient-ERROR retry; idempotent skip when already SUCCESS. |
| `ludus_testing` | Enter containment (idempotent) + open only the required egress (idempotent). DEC-08 `--testing = containment ON`. Never runs `testing stop`. |
| `ludus_range_verify` | Assert the Ludus-observable end state (SUCCESS, all VMs powered-on + with IPs) + a negative control. |
| `ludus_range_health` | **Read-only** fused diagnostic (`range list` + `range logs` on trouble) → `ludus_range_health_result` fact + report. The D3 "diagnostics baked in" role. |
| `ludus_range_teardown` | ERR-14-correct destroy-and-confirm (poll to DESTROYED **and** 0 VMs). Opt-in; never touches Nexus; never auto-escalates to `rm-range`. |

```yaml
- hosts: localhost
  connection: local
  gather_facts: false
  roles:
    - get_sybers.range.ludus_auth
- hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - include_role: { name: get_sybers.range.ludus_range_config }
      vars: { ludus_range_config_src: /opt/ludus/users/range-admin/range-config.yml }
    - include_role: { name: get_sybers.range.ludus_range_deploy }
    - include_role: { name: get_sybers.range.ludus_testing }
    - include_role: { name: get_sybers.range.ludus_range_verify }
```

The ninja-war blueprint composes these + its own content plays. The range's GHOSTS server
CT is not this collection's either: phase 1b of the FGNW blueprint creates it from the
published `get_sybers.lxc` ghost9 template through that collection's `lxc_preflight` /
`lxc_guest` / `lxc_ghost9` roles (that collection's `deploy_ghost9_range` play, run by phase 1b).
`tests/local-gate.sh` runs the read-only test plays (auth, health, verify) syntax-checked + twice
(second run `changed=0`). The mutating roles (config/deploy/testing/teardown) are exercised by a live
range deploy, not the hermetic gate — running them in CI would deploy a real range.
