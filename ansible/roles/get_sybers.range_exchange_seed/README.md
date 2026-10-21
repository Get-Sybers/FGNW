Seeds a forest's **real Exchange mailboxes** with the FGNW character-quote corpus (plus a set
of LOE-2 alert entries) as genuine SMTP mail. It derives the host's forest from its VM name,
loads the bundled corpus (`files/user-inboxes.yml`) and the AD ground truth
(`files/config.json`), filters the corpus to recipients that are **real AD users of this host's
own domain**, and sends each message via the forest's own Exchange over `localhost`. It runs on
each `-mail` VM at the Ludus `user-defined-roles` stage (S2), **after
`get_sybers.range_exchange`** has stood up the mail infrastructure. Host identity is derived
from `inventory_hostname`, so no `role_vars` are required.
`main.yml` is the only entry point. Because the SEND is not idempotent, the role probes an
end-of-seed marker first and **skips delivery when it is present**; the marker is written
**last**, only after every message in the loop has been delivered, so a half-seeded forest (no
marker) is seeded again on the next run. Set `range_exchange_seed_force=true` to deliver the
corpus again — which **duplicates every message**.

| name | default | purpose |
| --- | --- | --- |
| `range_exchange_seed_admin_password` | `password` | Shared lab forest-root Administrator password used to send as each mailbox. |
| `range_exchange_seed_force` | `false` | Re-run override; `true` re-delivers the corpus (duplicates every message). |
| `range_exchange_seed_state_dir` | `C:\ProgramData\FGNW` | Directory on the VM that holds the end-of-seed marker. |
| `range_exchange_seed_sentinel` | `C:\ProgramData\FGNW\seed-mail.done` | Full path of the end-of-seed marker probed to decide whether to seed. |
| `range_exchange_seed_org_map` | see `defaults/main.yml` | Per-forest mail (recipient) domain, keyed by `-mail` suffix. |
| `range_exchange_seed_forest_root_map` | see `defaults/main.yml` | Forest root each host authenticates against when sending. |

The `_rxs_*` variables (derived identity, loaded corpus, filtered recipient list) are
`set_fact` intermediates, not inputs, and are excluded from `meta/argument_specs.yml`.
This role is **content seeding**, not a security-control change — it introduces no new host
weakness of its own. What it does contribute to the range's deliberately-weak posture:

- **Recon-rich mailbox content.** Every seeded inbox is filled with realistic, readable mail
  from other named users, so a foothold on any mailbox yields organisational intelligence — who
  corresponds with whom, real display names and addresses across forests.
- **Scenario breadcrumbs.** The corpus includes hand-authored LOE-2 alert messages (RECON/DoS
  notices, cryptic "Root" invitations) planted as exercise leads.
- It leans entirely on the **deliberately-open mail infrastructure** that
  `get_sybers.range_exchange` stands up (shared weak admin credential, unauthenticated
  `localhost` submission, open cross-forest connectors) — the security weakening lives in that
  role; this one only fills it with mail.
