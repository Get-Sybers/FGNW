A **read-only** fused range diagnostic. Runs on the Ludus host / control node and
drives the `ludus` CLI only — it never touches a range guest and never uses the
MCP. This is an S4 runtime-orchestration role (`doc/standards/02-Ansible-Standards.md` §
"Phases of a range asset").
It fuses `range list` and (only when the state is unhealthy) `range logs` into one
structured picture: it publishes a `ludus_range_health_result` fact — `rangeState`,
`rangeNumber`, `testingEnabled`, VM count, powered-on count, the names of any VMs
missing an IP, and the VM list — prints a one-line human report, and surfaces a
log tail when the state is `ERROR`/`FAILED`. Set `ludus_range_health_fail_on_unhealthy`
to turn it into a gate that asserts the range is fully healthy. It requires
`ludus_auth` to have run earlier in the play (it publishes `__ludus_api_key`).

| name | default | purpose |
| --- | --- | --- |
| `ludus_range_health_log_lines` | `40` | Trailing `range logs` lines surfaced when the state is ERROR/FAILED. |
| `ludus_range_health_fail_on_unhealthy` | `false` | When true, assert SUCCESS + all VMs powered on with IPs (gate use). Default report-only. |
| `ludus_range_health_bin` | `/usr/local/bin/ludus` | Path to the ludus CLI binary. |

**Nothing.** This is a range **health-check** role, and it is strictly read-only —
it publishes a fact and prints a report, and in its default mode cannot fail the
play at all. It introduces no vulnerability into any range guest, shares no
credential with a range host, and never reaches a guest, an infra service, or the
Proxmox management network.
