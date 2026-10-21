Pushes a range configuration to Ludus **idempotently**. Runs on the Ludus host /
control node and drives the `ludus` CLI only — it never touches a range guest.
This is the phase-A3 "range config set" hook (`doc/standards/02-Ansible-Standards.md` §
"Phases of a range asset").
What it does, in order: optionally materializes a blueprint master over the
`users/` copy so the two cannot disagree (ERR-03); asserts the config is a real
file under the CLI-wrapper's `users/` root (the wrapper refuses `config set -f`
from anywhere else); preflights that every `template:` the config references is
actually **built**, not merely registered; then compares the **parsed** live and
desired YAML and runs `range config set -f` only when they genuinely differ — so
a second run reports `changed=0` even though `config set` is not itself a query.
It requires the `ludus_auth` role to have run earlier in the play (it publishes
the `__ludus_api_key` fact); the `config | preflight` task asserts this.

| name | default | purpose |
| --- | --- | --- |
| `ludus_range_config_src` | `""` | Path under `ludus_range_config_users_root` to the range-config.yml to push. Effectively required; real guard is the preflight/stat asserts, not `required:`. |
| `ludus_range_config_blueprint_src` | `""` | Optional blueprint master copied over `ludus_range_config_src` before the push (ERR-03). Empty pushes an already-placed file unchanged. |
| `ludus_range_config_template_check` | `true` | Resolve every referenced `template:` against `templates list --json` and refuse an unbuilt/unknown one before pushing. |
| `ludus_range_config_users_root` | `/opt/ludus/users` | The only root the CLI wrapper permits `config set` from; both path asserts key on it. |
| `ludus_range_config_bin` | `/usr/local/bin/ludus` | Path to the ludus CLI binary. |

**Nothing.** This is a range **config-generation / orchestration** role. It runs
on the Ludus host against the Ludus API, introduces no vulnerability into any
range guest, shares no credential with a range host, and touches neither a guest
filesystem nor the Proxmox management network. Its safety posture is the reverse
of a weakening: it *refuses* to push a config that names an unbuilt template or
that sits outside the CLI-wrapper's guarded `users/` root.
