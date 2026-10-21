Installs the [Velociraptor](https://docs.velociraptor.app/) client (endpoint
DFIR) agent on a range **Windows** host and enrolls it against the range's
Velociraptor server. It preflights its inputs, derives the server hostname
(`velociraptor_host` verbatim when it is a hostname, or `<range_id>-velociraptor`
when it is an IP), adds a DNS A record for the server when the target is a domain
controller, downloads the checksum-pinned `windows-amd64.exe`, fetches the
per-deploy client config (with a delegated `slurp` fallback), installs and starts
the `Velociraptor` Windows service, and opens an outbound firewall rule. It runs
at the Ludus `user-defined-roles` deploy stage (S2).

| `tasks_from:` | writes? | what it does |
| --- | --- | --- |
| `main.yml` | yes | preflight → hostname/DNS → download binary + config → install/start service → firewall rule → verify |
| `preflight.yml` | no | assert `velociraptor_host` is present and hostname- or IPv4-shaped, and that `range_id` yields a valid derived hostname in the IP branch |
| `verify.yml` | no | assert the `Velociraptor` service exists, is `running` and `auto`-start, and the client config is on disk |
| name | default | purpose |

| --- | --- | --- |
| `velociraptor_host` | *(required, no default)* | Velociraptor server to enroll against; hostname or IPv4 |
| `range_id` | *(no default; Ludus-injected)* | range identifier, used only when `velociraptor_host` is an IP to derive `<range_id>-velociraptor` |
| `velociraptor_version` | `v0.77.1` | pinned release tag; re-pin the checksum when changed |
| `velociraptor_version_patch` | `0.77.1` | version string in the release asset filename |
| `velociraptor_checksum` | `sha256:c91c…d55e` | sha256 of the `windows-amd64.exe`; `win_get_url` refuses a mismatch |
| `velociraptor_install_path` | `/opt/velociraptor` | install path on the *server*, used only by the config-fetch fallback |
**Nothing — this is defensive tooling.** Velociraptor is a DFIR / endpoint
visibility agent; deploying it *adds* monitoring to the range rather than
degrading the Windows host's security posture. There is no vulnerability to
assert (range standard §6), so the role ships a `verify.yml` proving the agent
runs rather than one proving a weakness.
Two posture relaxations exist, both transport-level and documented per standard
§6:

- The client-config and binary downloads run with `validate_certs: no`. Binary
  integrity is gated by the pinned sha256 `checksum:`, and agent↔server trust is
  anchored by the CA embedded in the downloaded client config.
- An **outbound** firewall rule (TCP 8000-8001) is added so the agent can reach
  its server — egress for the agent only, not inbound exposure.
The DNS-record task is `failed_when: false` by design (a DC that cannot write the
record must not fail the deploy); it is a convenience, not a weakening, and the
agent still enrolls via the config it downloads.
