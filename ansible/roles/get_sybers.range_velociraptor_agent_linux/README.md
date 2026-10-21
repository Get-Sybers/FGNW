Installs the [Velociraptor](https://docs.velociraptor.app/) client (endpoint
DFIR) agent on a range **Linux** host and enrolls it against the range's
Velociraptor server. It creates `/opt/velociraptor-client`, waits for the
server, fetches the per-deploy client config (falling back to a delegated
`slurp` from the server when the API download fails), downloads the
checksum-pinned `linux-amd64` binary, installs a systemd unit, starts and
enables it, then verifies the end-state. It runs at the Ludus
`user-defined-roles` deploy stage (S2) — configuring a VM that already exists.

| `tasks_from:` | writes? | what it does |
| --- | --- | --- |
| `main.yml` | yes | create dir, wait for server, fetch client config, install binary + systemd unit, start/enable, then verify |
| `verify.yml` | no | assert the unit is `active` **and** `enabled` and the client config is present (re-runnable standalone with `-t verify`) |
| name | default | purpose |

| --- | --- | --- |
| `velociraptor_host` | *(required, no default)* | Velociraptor server to enroll against (IP or DNS hostname) |
| `velociraptor_version` | `v0.77.1` | pinned release tag; re-pin the checksum when changed |
| `velociraptor_version_patch` | `0.77.1` | version string in the release asset filename |
| `velociraptor_checksum` | `sha256:6636…d28a` | sha256 of the `linux-amd64` binary; `get_url` refuses a mismatch |
| `velociraptor_install_path` | `/opt/velociraptor` | install path on the *server*, used only by the config-fetch fallback |
**Nothing — this is defensive tooling.** Velociraptor is a DFIR / endpoint
visibility agent; deploying it *adds* monitoring to the range rather than
degrading the host's security posture. There is no vulnerability to assert here
(range standard §6), which is why the role ships a `verify.yml` that proves the
agent is running rather than one that proves a weakness is present.
The only posture relaxations are transport-level and documented per standard §6:
the client-config and binary downloads run with `validate_certs: no`. Integrity
is not left unguarded — the binary is gated by the pinned sha256 `checksum:`, and
agent↔server trust is anchored by the CA embedded in the downloaded client
config, not by the download's TLS. There is no Nexus mirror for the GitHub
release, so the binary is fetched from public GitHub (its URL in
`defaults/main.yml`), gated by the pinned sha256 `checksum:`.
