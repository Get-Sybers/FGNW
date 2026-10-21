Installs **Google Chrome (stable)** + a **version-matched `chromedriver`** on a Fourth Great
Ninja War GHOSTS workstation, so the GHOSTS **`BrowserChrome`** timeline handler can drive a
real, non-headless browser in the persona's interactive autologon session (rather than a
`cmd /c start "" "http://…"` URL launch).
The role is deliberately fail-loud — a browser that will not launch fails the deploy rather than
degrading silently.

1. Installs `googlechrome` and `chromedriver` via `win_chocolatey` (no source is hardcoded, so
   the installs hit whatever source the VM has. Whether anything sets a chocolatey source on
   range VMs — and whether the Nexus choco proxy is actually in the install path — is an open
   question).
2. **Disables Chrome auto-update** (Google Update policy keys) so Chrome can't silently drift off
   the pinned chromedriver — the single most common `BrowserChrome` breakage.
3. Verifies `chrome.exe` at its default path and `chromedriver.exe` on the system PATH.
4. **Overwrites the stale chromedriver GHOSTS bundles in its own dir** (`C:\ludus\ghosts-client\`)
   with the matched binary — a driver in the app dir shadows the one on PATH, so a bundled-old +
   installed-new-Chrome combo would otherwise fail.

- Chrome at `C:\Program Files\Google\Chrome\Application\chrome.exe`
- `chromedriver.exe` on PATH **and** matched inside `C:\ludus\ghosts-client\`
- Chrome frozen at the chromedriver's version
The `BrowserChrome` handler in `ansible/templates/FGNW-ghosts.timeline.json.j2` (with
`isheadless: "false"`) drives that browser; nothing else is needed on the timeline side.
- Register the role (custom-role-copy gotcha: each Ludus user keeps an independent copy under
  `users/<user>/.ansible/roles/<role>/` that `ludus ansible role add` does NOT refresh — see
  [`campaign/docs/TROUBLESHOOTING.md`](../../../blueprints/FGNW/campaign/docs/TROUBLESHOOTING.md)):
  `ludus ansible role add -d ./ansible/roles/get_sybers.range_ghosts_browser` (from the source repo root)
- Add `get_sybers.range_ghosts_browser` to each GHOSTS workstation's `roles:` in `range-config.yml`,
  **after `jasonmull.ludus_ghosts_client`** (so step 4 can overwrite the bundled driver).
- It installs from Nexus/internet, so it runs during the **build phase** — before
  `ludus testing start` containment cuts internet.
A real Selenium Chrome is far heavier than a URL launch. The GHOSTS workstations were bumped to
**4 GB / 2 vCPU** alongside this role (see `range-config.yml` and the plan doc §6). Do not run this
on the old 2 GB / 1 vCPU spec.
`defaults/main.yml` exposes `range_ghosts_browser_chrome_version` /
`range_ghosts_browser_driver_version` (empty = chocolatey latest for both at deploy, normally
matched). Pin both to the same version for a guaranteed match across redeploys.
