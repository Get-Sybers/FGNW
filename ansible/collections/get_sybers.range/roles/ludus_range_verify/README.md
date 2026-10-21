Asserts the **Ludus-observable** end state of a range — the orchestration layer's
positive-plus-negative check. Runs on the Ludus host / control node and drives the
`ludus` CLI only — it never touches a range guest. This is an S4
runtime-orchestration role (`doc/standards/02-Ansible-Standards.md` § "Phases of a range
asset").
It owns the invariants Ludus itself reports: `rangeState` is `SUCCESS`, every VM
is powered on, every VM holds a non-empty IP, and (optionally) the VM count is
exact. A **negative control** — asserting a bogus VM name is absent — proves the
VM list is real rather than an empty list that passes everything. Deep in-range
connectivity and emulation verification (HTTP targets, agent health, persona
telemetry) is blueprint-specific and stays in the campaign's own verify tasks;
this role covers only what the Ludus API exposes. It requires `ludus_auth` to have
run earlier in the play (it publishes `__ludus_api_key`).

| name | default | purpose |
| --- | --- | --- |
| `ludus_range_verify_require_success` | `true` | Assert `rangeState` is SUCCESS. |
| `ludus_range_verify_require_powered_on` | `true` | Assert every VM is powered on. |
| `ludus_range_verify_require_ips` | `true` | Assert every VM has a non-empty IP. |
| `ludus_range_verify_expect_vmcount` | `0` | Exact VM count to assert; 0 disables the check. |
| `ludus_range_verify_bin` | `/usr/local/bin/ludus` | Path to the ludus CLI binary. |

**Nothing.** This is a range **verification** role, and it is read-only — it only
asserts observable state. It introduces no vulnerability into any range guest,
shares no credential with a range host, and never reaches a guest, an infra
service, or the Proxmox management network. The negative control exists precisely
to stop the verifier from *weakening itself* into an empty-passes-everything check.
