Deploys the calling user's range via the `ludus` CLI and **waits for a terminal
state**. Runs on the Ludus host / control node and drives the Ludus API only — it
never touches a range guest. This is an S4 runtime-orchestration role
(`doc/standards/02-Ansible-Standards.md` § "Phases of a range asset").
It separates *fire* from *wait* and polls the **observed** `rangeState`, never the
deploy command's exit code: a first deploy commonly ends `rangeState=ERROR`
because a VM had not reported its guest-agent IP when its roles ran, and
re-running the idempotent deploy clears it. Attempts are **bounded** so a
genuinely broken deploy still exits, and a poll-budget timeout is fatal (it will
not re-fire on an in-flight deploy). It requires `ludus_auth` to have run earlier
in the play (it publishes `__ludus_api_key`).

| file | entry point? | what it does |
| --- | --- | --- |
| `main.yml` | **yes** — the only one | preflight → read state → skip-if-SUCCESS → bounded attempt loop → assert SUCCESS |
| `attempt.yml` | no (internal `include_tasks`, looped) | one bounded attempt: re-check state, fire unless already DEPLOYING, poll to terminal, classify SUCCESS/FAILED/ERROR/timeout, capture ERROR diagnostics |
| `state.yml` | no (internal `include_tasks`) | read `range list --json` into `__ludus_state` / `__ludus_vmcount` / `__ludus_testing`, safe on a never-deployed range |

| name | default | purpose |
| --- | --- | --- |
| `ludus_range_deploy_tags` | `[]` (in defaults) | `-t` deploy tags; empty = full deploy. Any value disables the already-SUCCESS skip. |
| `ludus_range_deploy_limit` | `""` | `--limit` target; non-empty disables the skip. |
| `ludus_range_deploy_only_roles` | `""` | `--only-roles <role>`; non-empty disables the skip. |
| `ludus_range_deploy_force` | `false` | Re-apply even if already SUCCESS. |
| `ludus_range_deploy_max_attempts` | `3` | Max fire+poll attempts (preflight asserts >= 1). |
| `ludus_range_deploy_error_retry` | `true` | Retry a transient ERROR by re-firing the idempotent deploy. |
| `ludus_range_deploy_poll_retries` | `270` | Poll iterations to a terminal state (270 x 20s = 90 min). |
| `ludus_range_deploy_poll_delay` | `20` | Seconds between polls. |
| `ludus_range_deploy_capture_errors` | `true` | Persist each errored attempt's `range errors` before logs roll over (#320); best-effort. |
| `ludus_range_deploy_error_capture_dir` | `$HOME/.ludus-deploy-errors` (in defaults) | Where errored-attempt diagnostics are written. |
| `ludus_range_deploy_bin` | `/usr/local/bin/ludus` | Path to the ludus CLI binary. |

**Nothing.** This is a range **deploy-orchestration** role. It runs on the Ludus
host against the Ludus API, introduces no vulnerability into any range guest,
shares no credential with a range host, and never reaches a guest, an infra
service, or the Proxmox management network. Its notable safety behaviours are the
opposite of a weakening: the overlap guard refuses to fire a **rival** deploy
while one is already in flight (concurrent deploys were observed corrupting each
other), and a non-terminal poll timeout fails loudly rather than re-firing.
