Resolves and validates the Ludus API identity **once** at the start of a range
run, then republishes it (as a `no_log` fact) for the rest of the
`get_sybers.range` collection to use. It is the collection's single auth entry
point: the consumer roles (`ludus_range_*`, `ludus_testing`) assert
`__ludus_api_key is defined` and rely on this role having run first. It holds no
resolution logic of its own — the check is delegated to the shared
`get_sybers.ludus_auth_check` task-role, which is **env-only**: an exported
`LUDUS_API_KEY` is the only key source, with no file fallback. It runs against
the local Ludus v2 API — it drives Ludus, never a guest (surface S4).
Key **delivery** belongs to the calling context: export `LUDUS_API_KEY`, or run
through `get_sybers.cluster` `playbooks/ludus-ra-auth.yml`, which proves the
PocketBase-homed key and exports it. A path is not a secret, and the key itself
is never placed on argv or in playbook output.

| `tasks_from:` | writes? | what it does |
| --- | --- | --- |
| `main.yml` | fact only | run the shared env-only check; publish `__ludus_api_key` (`no_log`), `__ludus_key_source`, `ludus_auth_status`, `ludus_auth_user` |
| `verify.yml` | no | run the shared check's controls — positive (the expected identity was established) plus a negative control (a known-invalid key is rejected) |
| name | default | purpose |

| --- | --- | --- |
| `ludus_auth_api_url` | `https://127.0.0.1:8080/api/v2` | base URL of the local Ludus v2 API |
| `ludus_auth_expected_user` | `RA` | the userID the key **must** authenticate as (confirmed via `/whoami`) |
| `ludus_auth_skip_liveness` | `false` | skip the live `/whoami` round-trip and validate the key shape only |
**Nothing — it is a containment control, not a weakening.** This role is a guard:
it fails the run *early* if the Ludus API key is missing, malformed, or
authenticates as the wrong identity, before any state-changing range command
runs three phases deep. That directly serves the range standard's containment
posture (§1) — deploy credentials are validated and scoped, never shared or
assumed — and it never touches a range guest, so it introduces no vulnerability
into one.
Key handling is deliberately **narrowed**, not loosened: env-only delivery (the
former hand-rolled vault/file read in a range-visible role was stripped), and the
resolved key is republished only as a `no_log` fact.
