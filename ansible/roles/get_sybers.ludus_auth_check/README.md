**ENV-ONLY Ludus API auth check.** Proves the `LUDUS_API_KEY` environment
variable is present, correctly shaped, live, and the expected identity — then
publishes it as a `no_log` fact for consumer roles. Fails fast at the top of a
play instead of hours into a deploy on a stale or wrong key.
This is a **standalone task-role**, not a collection role, because it is used by
more than one galaxy — rule 6 in
`doc/standards/02-Ansible-Standards.md`. Call it by plain
name; no cross-collection dependency is created. It is consumed by
[FGNW](https://github.com/Get-Sybers/FGNW) (`range.ludus_auth`) and
`ludus-plusplus`.
This role **never reads any file** — it never stats, slurps, or looks up a
credential; it includes no secrets vault and knows no vault path except as
failure-message text. The **only** key source is the `LUDUS_API_KEY` environment
variable of the `ansible-playbook` process.
Key *delivery* is the calling context's job — the sanctioned injection path is
`get_sybers.cluster`'s
[`playbooks/ludus-ra-auth.yml`](https://github.com/Get-Sybers/proxmaxxing/blob/main/playbooks/ludus-ra-auth.yml),
which authenticates and exports `LUDUS_API_KEY` before this role runs.
The decisions live in [`tasks/main.yml`](tasks/main.yml) as decision-gated
includes (rule 8 — the `when:` sits on the include, driven by caller vars):

- **[`resolve.yml`](tasks/resolve.yml)** — read the env key and shape-check it.
  Always runs.
- **[`liveness.yml`](tasks/liveness.yml)** — a live `/whoami` round-trip proving
  the key authenticates *and* is `ludus_expected_user`. Runs unless
  `ludus_auth_skip_liveness`.
- **[`admin.yml`](tasks/admin.yml)** — require the identity to be a Ludus admin.
  Runs only when `ludus_auth_require_admin`.
The `ludus` CLI exits `rc=0` on an invalid API key (`[ERROR] Invalid API key` on
stderr only), so the CLI return code can *never* be an auth signal. The `/whoami`
**HTTP status** asserted here is the boundary.
Documented with a schema in
[`meta/argument_specs.yml`](meta/argument_specs.yml); defaults in
[`defaults/main.yml`](defaults/main.yml).

| Variable | Default | Purpose |
| --- | --- | --- |
| `ludus_api_url` | `https://127.0.0.1:8080/api/v2` | Base URL of the local Ludus v2 API. |
| `ludus_auth_validate_certs` | `false` | TLS verification for `/whoami`. Default `false` for the stock loopback API on its self-signed cert; set `true` when pointing at a trusted-certificate endpoint. |
| `ludus_expected_user` | `RA` | The userID the key **must** authenticate as. |
| `ludus_auth_require_admin` | `false` | Require the identity to be a Ludus admin (`isAdmin` from `/whoami`). Incompatible with `ludus_auth_skip_liveness=true`. |
| `ludus_auth_skip_liveness` | `false` | Skip the live `/whoami` round-trip and validate key shape only. |
| Fact | `no_log` | Meaning |

|---|---|---|
| `__ludus_api_key` | yes | The key, for consumer roles. |
| `__ludus_key_source` | no | Always `"environment"`. |
| `ludus_auth_status` | no | `/whoami` HTTP status (liveness path). |
| `ludus_auth_user` | no | The authenticated userID (liveness path). |
| `ludus_auth_is_admin` | no | Whether that identity is a Ludus admin (liveness path). |
[`tasks/verify.yml`](tasks/verify.yml) (documented in `argument_specs.yml` as the
`verify` entry point) is a positive check that the expected identity was
established, plus a negative control that a known-invalid key is rejected.
