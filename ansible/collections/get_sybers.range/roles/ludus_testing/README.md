Puts a range into **contained** (internet-blocked) testing mode and opens **only**
the required egress. Runs on the Ludus host / control node and drives the `ludus`
CLI only — it never touches a range guest. This is an S4 runtime-orchestration
role (`doc/standards/02-Ansible-Standards.md` § "Phases of a range asset") and the
"`--testing` = containment ON" control.
It is idempotent in both halves: it skips `testing start` if the range is already
in testing mode (polling until `testingEnabled=true` when it does start), and it
adds each required allow entry only if a token-boundary match against
`testing status` shows it absent — so `example.com` does not shadow
`example.co`, nor `10.1.0.2` shadow `10.1.0.20`. It **never** runs
`testing stop`: stop reverts every VM to the pre-testing snapshot, which is
destructive and out of scope. It requires `ludus_auth` to have run earlier in the
play (it publishes `__ludus_api_key`).

| `tasks_from:` | what it does |
| --- | --- |
| `main.yml` | enter containment (idempotent) → open only the listed domain/IP egress (idempotent) |
| `verify.yml` | assert containment is ON, every listed allow entry is present, and an un-allowed probe domain is absent (negative control) |
| name | default purpose |

| --- | --- | --- |
| `ludus_testing_allow_domains` | `[]` (in defaults) | Domains a contained range may still reach (`testing allow -d`). Pass one only when its target is deployed. |
| `ludus_testing_allow_ips` | `[]` (in defaults) | IPs a contained range may still reach (`testing allow -i`). |
| `ludus_testing_poll_retries` | `30` | Poll iterations for `testingEnabled=true` after start (30 x 10s = 5 min). |
| `ludus_testing_poll_delay` | `10` | Seconds between testing-start polls. |
| `ludus_testing_bin` | `/usr/local/bin/ludus` | Path to the ludus CLI binary. |
**Nothing — it is the containment control itself.** Far from introducing a
weakness, this role *engages* the range's isolation (`ludus testing start` blocks
internet egress for every VM). Its only outward-facing surface is the allow-list,
and that is a **declared, narrow egress exception**, not a weakening of any guest:
the range standard (§1) requires exactly this — "range-to-range isolation unless a
scenario explicitly requires otherwise, and that exception is declared in the
range config rather than assumed." Each allow is token-boundary matched so it
cannot accidentally admit a longer domain or IP, and the role never opens egress
that a caller did not list. It touches no guest, shares no credential with a range
host, and never reaches an infra service or the Proxmox management network.
