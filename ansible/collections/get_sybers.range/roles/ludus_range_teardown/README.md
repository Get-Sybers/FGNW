A range-scoped destroy that **confirms the VMs are actually gone** (ERR-14). Runs
on the Ludus host / control node and drives the `ludus` CLI only — it never
touches a range guest. This is an S4 runtime-orchestration role
(`doc/standards/02-Ansible-Standards.md` § "Phases of a range asset").
`ludus range rm` destroys VMs but **keeps** the range object, so
`rangeState=DESTROYED` is fully compatible with VMs still existing. This role
therefore guards on `rangeState` **and** the live VM count, never state alone: it
stops testing first if enabled (the snapshot revert `testing stop` performs is
harmless when the VMs are about to be deleted), runs `range rm --no-prompt`, then
polls until the range is `DESTROYED` with 0 VMs. If VMs survive, it **fails
loudly** and prints the heavier `rm-range` command rather than escalating on its
own. It requires `ludus_auth` to have run earlier in the play (it publishes
`__ludus_api_key`).

| name | default | purpose |
| --- | --- | --- |
| `ludus_range_teardown_poll_retries` | `90` | Poll iterations for DESTROYED + 0 VMs after `range rm` (90 x 10s = 15 min). |
| `ludus_range_teardown_poll_delay` | `10` | Seconds between post-destroy polls. |
| `ludus_range_teardown_testing_poll_retries` | `30` | Poll iterations for testingEnabled=false after `testing stop` (30 x 10s = 5 min). |
| `ludus_range_teardown_testing_poll_delay` | `10` | Seconds between testing-stop polls. |
| `ludus_range_teardown_bin` | `/usr/local/bin/ludus` | Path to the ludus CLI binary. |

**Nothing.** This is a range **teardown** role. It runs on the Ludus host against
the Ludus API, introduces no vulnerability into any range guest, and never reaches
a guest, an infra service, or the Proxmox management network. Its scope is
deliberately narrow and *conservative*, not permissive: it is range-scoped
(`range rm`), never destroys Nexus, never deletes the range object on its own, and
refuses to report success until it has proven both the state and the VM count are
empty — so a caller cannot silently rebuild on stale VMs.
