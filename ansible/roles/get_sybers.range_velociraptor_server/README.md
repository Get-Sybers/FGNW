Installs and configures a [Velociraptor](https://docs.velociraptor.app/) DFIR
**server** on a range Linux host. It downloads the checksum-pinned `linux-amd64`
binary, renders a merge config (`templates/server.merge.json.j2`), generates the
server config, splits out the client config, builds and installs the server
`.deb`, creates the administrator account, and restarts the service **only when
server state actually changed** (a handler, not an unconditional restart). It
then verifies the service, the frontend port agents connect to, and the GUI/API
HTTPS endpoint. The agents deployed by the companion
`get_sybers.range_velociraptor_agent_linux` and
`get_sybers.range_velociraptor_agent_windows` roles enroll against this server.

| `tasks_from:` | writes? | what it does |
| --- | --- | --- |
| `main.yml` | yes | download binary, render/generate server + client config, install `.deb`, add admin user, restart-on-change, then verify |
| `verify.yml` | no | assert the service is active and the frontend/GUI ports and both configs are healthy (re-runnable standalone with `-t verify`) |
| name | default | purpose |

| --- | --- | --- |
| `velociraptor_host` | *(required, no default)* | hostname/IP the generated server config advertises to agents |
| `velociraptor_admin_password` | *(required, no default)* | administrator password; never hardcoded (the task sets `no_log`) |
| `velociraptor_admin_user` | `admin` | administrator username |
| `velociraptor_frontend_port` | `8000` | frontend port agents connect to; baked into the config and probed by verify |
| `velociraptor_gui_port` | `8889` | GUI/API HTTPS port; baked into the config and probed by verify |
| `velociraptor_version` | `v0.77.1` | pinned release tag; re-pin the checksum when changed |
| `velociraptor_version_patch` | `0.77.1` | version string in the release asset filename |
| `velociraptor_checksum` | `sha256:6636…d28a` | sha256 of the `linux-amd64` binary; `get_url` refuses a mismatch |
| `velociraptor_install_path` | `/opt/velociraptor` | directory the binary, configs and `.deb` are written to |
**Nothing — this is defensive infrastructure.** A Velociraptor server is the
collection point for DFIR / endpoint telemetry across the range; standing it up
*adds* investigative capability rather than degrading any host's security
posture. There is no vulnerability to assert (range standard §6), which is why
`verify.yml` proves the server is answering rather than proving a weakness.
Posture notes, documented per standard §6:

- The binary download uses `validate_certs: false`; integrity is enforced by the
  pinned sha256 `checksum:`. There is no Nexus mirror for the GitHub release (its
  URL is in `defaults/main.yml`).
- The server binds its frontend, GUI and API to `0.0.0.0` and serves a
  self-signed certificate (minted by `velociraptor config generate`). This is how
  agents and operators reach it inside the range; `verify.yml` probes the GUI
  with `validate_certs: false` for the same reason. It is standard Velociraptor
  operation, not a deliberate vulnerability.
