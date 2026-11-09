# fgnw_mac_ghosts_client

Installs the **GHOSTS v9 Universal client** (the cross-platform client of cmu-sei/GHOSTS) on the
Hidden Sand macOS workstation and runs it so the Gaara persona browses realistically — a **visible
Chrome** driven by the client's `BrowserChrome` handler, the macOS counterpart of what
`jasonmull.ludus_ghosts_client` + Selenium Chrome do on the Windows workstations.

## Why it installs from the Nexus (and builds from source)

GHOSTS publishes **no prebuilt macOS client** — the release ships `universal`/`lite` clients only
for `linux-x64/arm64` and `win-x64/x86`. The client's project *does* target `osx-x64`, so
[`nexus-cache-ghosts-universal.yml`](../../nexus-cache-ghosts-universal.yml) (Phase 0, on the
controller) **builds the osx-x64 client from source**, downloads **Chrome for Testing +
chromedriver** (mac-x64), and uploads all three to the range Nexus (`raw-hosted`, `tools/`). This
role then installs them from the Nexus, so the Mac needs no internet in either phase.

The role is called twice per deploy, selected by `fgnw_mac_ghosts_client_phase`:

| Phase | Play | phase | Why there |
| --- | --- | --- | --- |
| 1c | [`FGNW-mac-prestage.yml`](../../FGNW-mac-prestage.yml) | `prestage` | install the client + browser from the Nexus |
| 4d | [`FGNW-mac-services.yml`](../../FGNW-mac-services.yml) | `service` | load the LaunchAgent once AD is up |

Both plays limit the include to `suna-ws1`.

## What it does

`tasks/prestage.yml` (`prestage` or `all`):

1. Creates the install, config and log directories.
2. Fetches `ghosts-client-universal-osx-x64.tar.gz`, `chrome-mac-x64.zip` and
   `chromedriver-mac-x64.zip` from the Nexus `tools/` path.
3. Extracts the client (with `tar xzf` — BSD tar; the `unarchive` module requires GNU tar), installs
   Chrome for Testing + chromedriver under `<install_dir>`, and clears the quarantine xattr.
4. Rewrites `ApiRootUrl` in `config/application.json` to `fgnw_mac_ghosts_client_api_url`.
5. Hands `<install_dir>` and the log dir to `fgnw_mac_ghosts_client_run_user`.

`tasks/service.yml` (`service` or `all`):

1. Writes `/Library/LaunchAgents/<label>.plist` that runs
   `<install_dir>/Ghosts.Client.Universal` (the real apphost — not `ghosts`).
2. Bootstraps it into the run-user's GUI session (`launchctl bootstrap gui/<uid> …`) so the browser
   is **visible** in that user's desktop; an "already loaded" answer counts as success.

The persona timeline itself (a `BrowserChrome` handler over Gaara's themed sites, with
`executable-location` set to the installed Chrome) is deployed by the GHOSTS activity layer, not by
this role.

## Inputs

See `meta/argument_specs.yml` for the full list and defaults. Key ones:
`fgnw_mac_ghosts_client_nexus_base` (where the client + browser come from),
`fgnw_mac_ghosts_client_binary` (`Ghosts.Client.Universal`),
`fgnw_mac_ghosts_client_run_user` (the GUI user the client runs as), and
`fgnw_mac_ghosts_client_phase`.

## Privilege and platforms

- Tasks that write under `/usr/local`, `/Library/LaunchAgents` and `/var/log` use `become: true`;
  the client then runs **unprivileged** as the GUI user.
- Platform: macOS (the range's macos-sequoia-15 template).
