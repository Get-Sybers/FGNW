Concrete post-deploy checks for the range. Work through this list each time the range is deployed to
confirm each built piece actually works (not just that the config parses), and to cover the
full-range pieces the small-range deploys do not exercise.
Order of operations for a full bring-up:

1. `ludus range config set -f range-config.yml` then `ludus range deploy` (provisions VMs + roles).
   That file is the 23-VM superset, so setting it by hand gives the `xl` set; to verify a specific
   variant, deploy it with `ansible-playbook deploy.yml -e range_variant=<small|xl>` instead and
   let the preflight render it (see [`RANGE-CONFIG-VARIANTS.md`](RANGE-CONFIG-VARIANTS.md)).
2. AD promotion, child domains, member joins and the `fire ↔ oto` trust are **native** — built by
   `ludus range deploy` in step 1 (see the `domain:`/`roles:` blocks in
   [`range-config.yml`](../../range-config.yml)). Then run the Phase-3 tail against the AD
   inventories: `tgtdelegation.yml → ad-data.yml` (owned `fgnw_ad_mgmt` directory content) `→
   lat.yml → reboot.yml`, plus `adcs.yml`; `deploy-tasks/phase3-ad.yml` drives this.
3. Run the manual post-deploy playbooks: `ad-data.yml` (if not already), `FGNW-attacker-web.yml`,
   `FGNW-themed-sites.yml`, `FGNW-recon-tooling.yml`, `FGNW-ninjasploitable-content.yml`,
   `FGNW-ninjasploitable-join.yml`, `dnsforwarder.yml`, `FGNW-persona-autologon.yml`,
   `FGNW-decoy-content.yml`, `FGNW-browser-defaults.yml`, `FGNW-browser-extensions.yml`,
   `FGNW-acsc-logging.yml`, `FGNW-sysmon-linux.yml`, `FGNW-ghosts-activity.yml`.
4. Work through the checks below.
Notation: `10.<r>.` = `10.<range_second_octet>.`. Windows checks run over WinRM (this range uses
`ansible_winrm_scheme: https`, port 5986).

---

- `ludus range list` shows all 9 workstations `SUCCESS`/powered-on with expected IPs:
      konoha-ws1..5 = `10.<r>.10.21`–`.25`, oto-ws1 = `10.<r>.30.11`,
      akatsuki-ws1/2 = `10.<r>.87.11`/`.12`, suna-ws1 = `10.<r>.20.11`.
- Each is at the intended spec (**4 GB / 2 vCPU** — bumped for the native Selenium browser; the
      small range's konoha-ws1/oto-ws1 are 6 GB / 2 vCPU) — check the Proxmox VM config or
      `ludus range list` detail.
- Chrome + a version-**matched** chromedriver installed (`range_ghosts_browser` role): on a
      workstation, `& 'C:\Program Files\Google\Chrome\Application\chrome.exe' --version` and
      `chromedriver --version` show the SAME Chrome major version, and `ghosts.exe` drives a **visible**
      Chrome window in the console session (BrowserChrome, `isheadless=false`). See the
      `get_sybers.range_ghosts_browser` role README.
- No IP/hostname collision anywhere in `ludus range list`.
- Host RAM/CPU on the node stayed within limits under load (this pushed vCPU oversubscription
      up; watch for contention during the AD provisioning storm).
- Each flagship WS is domain-joined to the right domain:
      `nltest /dsgetdc:<domain>` from the box succeeds; `echo %USERDOMAIN%` = expected NetBIOS
      (KONOHA / OTO / AKATSUKI / SUNA).
- `konoha-mail` is domain-joined to `konohagakure.fire.ninja` — confirm it's a member server:
      `(Get-WmiObject Win32_ComputerSystem).PartOfDomain` = True and `.Domain` = the Leaf FQDN.
- The flagship character resolves as a real AD user and is in the box's Remote Desktop Users:
      e.g. on konoha-ws1, `net localgroup "Remote Desktop Users"` contains `KONOHA\naruto.uzumaki`.
      Repeat per box (naruto/shikamaru/kakashi/tsunade/might.guy/orochimaru/pain/zetsu).
- All 4 populated domains actually populated from `config.json`
      (`Get-ADUser -Filter *` counts roughly match: Leaf ~70+, Sand 7+, Sound 7+, Akatsuki 14+).
- `akatsuki-dc1` promoted as domain **`akatsuki.dark`** (NOT `.ninja`):
      on akatsuki-dc1, `(Get-ADDomain).DNSRoot` = `akatsuki.dark`, `.NetBIOSName` = `AKATSUKI`.
- AD object paths use `DC=akatsuki,DC=dark` (e.g. `Get-ADUser pain -Properties DistinguishedName`).
- `grep -ri 'akatsuki\.ninja'` across the deployed config finds nothing (already true in-repo).
- Playbook ran clean on all 6 DCs (`hosts: dc`), no errors.
- On each DC, conditional forwarders exist for every *other* domain:
      `Get-DnsServerZone | Where ZoneType -eq 'Forwarder'` lists the other five domains
      (including `akatsuki.dark`).
- Cross-forest resolution actually works from a workstation that has **no AD trust** to the
      target — e.g. from suna-ws1 (Wind forest): `nslookup -type=SRV _ldap._tcp.dc._msdcs.konohagakure.fire.ninja`
      returns the Leaf DC. (This is the case the old hardcoded timeline would have failed; it should
      now resolve.)
- Isolation preserved: DNS resolves, but there's still **no Kerberos/NTLM trust** to Akatsuki
      (`nltest /domain_trusts` from a village box does not list `akatsuki.dark` as trusted).
- GHOSTS API server up: `curl http://10.<r>.99.51:5000/swagger/v9/swagger.json` reports
      `"version": "v9"` and the UI on `http://10.<r>.99.51:4200/` renders, from kali or a
      workstation; `ansible-playbook ghost9-verify.yml -e ghost9_ct_range_number=<r>` from the
      Ludus host proves the same plus the guest markers (the ghost9 CT is a `get_sybers.lxc`
      container, not a VM).
- `FGNW-ghosts-activity.yml` ran clean against all 9 `[ghosts_clients]` (no host skipped, no
      "no persona" failure).
- On each WS, `C:\ludus\ghosts-client\config\application.json` `ApiRootUrl` =
      `http://10.<r>.99.51:5000/api`, and `ghosts.exe` is running (`Get-Process ghosts`).
- Each WS's `timeline.json` is the persona-specific render (spot-check: konoha-ws1's browse
      handler contains `ichiraku-ramen`/Leaf URLs and `nltest /dsgetdc:konohagakure.fire.ninja`;
      akatsuki-ws1 contains `ame-portal.rain` and `nltest /dsgetdc:akatsuki.dark`).
- akatsuki-ws2 (Zetsu, no OWA inbox) timeline has the OWA index open but **no** own-inbox open
      (the conditional worked).
- Flagship overrides applied (spot-check `timeline.json`): konoha-ws1 has a signature handler
      hammering `ichiraku-ramen.com` at short (~1–2 min) delays; konoha-ws5 (Guy) handlers show
      `UtcTimeOn: 05:00:00`/`UtcTimeOff: 21:00:00`; suna-ws1 (Gaara) shows `00:00:00`/`23:59:00`;
      konoha-ws3 (Kakashi) signature handler uses long (~8–12 min) idle delays.
- The clients register/report in to the GHOSTS server (visible in the GHOSTS UI on `:4200`
      and the Grafana dashboards on `:3000` the ghost9 template carries).
- Attacker sinkhole up: `http://10.<r>.99.50/` returns 200 (the tool-cache landing page).
      Note this is VLAN **99** `.50` — the timeline template was corrected from a stale `.50.50`.
- Themed sites deployed (`FGNW-themed-sites.yml`): `nginx -t` passed; from a WS,
      `http://www.konoha-portal.leaf/`, `http://www.shinobi-world-news.com/`,
      `http://www.ichiraku-ramen.com/` each render a **distinct** archetype page (portal/news/shop),
      not the tool-cache placeholder — confirms the `$host`-root vhost coexists with the tool cache.
- `FGNW-ninjasploitable-content.yml` ran clean over SSH (`[linux_infra]` group; confirm the
      `localuser`+password/key actually works for the Debian VM — adjust inventory if not).
- Report intake page up: `http://10.<r>.90.10/reports/intake.php` renders the Fire/Leaf form.
- Upload works and is unvalidated (the intended vuln): submitting any file returns
      "Report filed" and it's reachable under `/uploads/<ninja>_<filename>`.
- VLAN10 (Leaf) → VLAN90 (ninjasploitable) reachability: a Leaf workstation can actually load
      the intake URL (this is the cross-VLAN question — no `network:` ACL block is defined).
- Leaf GHOSTS personas (konoha-ws1..5) have the intake URL in their `timeline.json`; non-Leaf
      personas do not.
Konoha/Leaf (`konoha-mail`):
- Real Exchange 2019 CU15 ISO URL set in `FGNW-exchange.yml`.
- Exchange installed on konoha-mail (`Get-Service MSExchangeFrontendTransport` → Running,
      auto-start). The small range's AD-build inventory never included the `-owa` hosts, so
      `FGNW-exchange.yml`'s own first play domain-joins it directly (to its forest root, not its own
      child domain).
- User mailboxes created on konoha-mail (`Get-Mailbox` → the real Leaf users).
- All AD groups mail-enabled on konoha-mail (`Get-DistributionGroup`/`Get-Group` confirms).
- Cross-forest send connectors present on konoha-mail (`Get-SendConnector` shows all 3
      `to-<other domain>` connectors).
- Real OWA login page responds (`https://localhost/owa/` → HTTP 200).
- Real mail delivery: `FGNW-exchange-seed-mail.yml` delivers the character-quote corpus via
      genuine `Send-MailMessage`/SMTP.
- Spot-check a few real mailboxes (e.g. `naruto.uzumaki`) actually received mail from their real
      correspondents (Kakashi, Sai, Sakura for Naruto, per `content/ghosts/email-relationships.yml`) —
      confirms the relationship graph's output actually landed, not just that the send count looks right.
- Real end-to-end CROSS-FOREST test: send from a Leaf mailbox to a Sound/Akatsuki address →
      delivered; reply to a non-existent (throwaway Akatsuki) address → NDR bounce. Needs Sound/Akatsuki
      to have Exchange installed — the send connectors exist on Leaf's side but the other ends need to
      be live targets.
- Delivered messages' From headers carry each sender's own forest domain
      (`<sender>@sunagakure.wind.ninja`, `@otogakure.ninja`, `@akatsuki.dark`, …), since
      `user-inboxes.yml` records `from_address` per sender forest and the seed play sends with it.
Sound/Akatsuki (`oto-mail`/`dark-mail`) — full range only (the Sand forest's `suna-mail` is
macOS Postfix/Dovecot, not Exchange — verify it separately per Phase 4d):
- Exchange installed on oto-mail / dark-mail (`--limit <host>`, full range only).
- User mailboxes created per forest (`Get-Mailbox` returns each domain's users).
- All AD groups mail-enabled per forest.
- Cross-forest send connectors present on each (`to-<other domain>` ×3 per org).
- `FGNW-exchange-seed-mail.yml` run once per forest (NOT idempotent — don't re-run against
      an already-seeded forest, it duplicates messages).
- Real cross-forest end-to-end test (Leaf ↔ Sound ↔ Akatsuki delivery + NDR bounce on a bad
      address) — only meaningful once the three Windows forests have Exchange installed.
- `FGNW-campaign-setup.yml` ran clean against `konoha-dc1`.
- Kerberoastable service account present: `Get-ADUser svc-missionboard -Properties ServicePrincipalNames`
      shows the SPN; the account has a weak (crackable) password.
- AS-REP account set: `Get-ADUser konohamaru.sarutobi -Properties userAccountControl` has
      DoesNotRequirePreAuth.
- Spot-check the campaign's real paths exist: fire↔oto trust (`Get-ADTrust`), shared local-admin
      hash reuse works for PtH across `konoha-ws1..5`, and `ninjasploitable /reports/intake.php` accepts
      an unrestricted upload.
- After leaving the range running through a simulated working-day window (timelines are on
      12:00–23:00 UTC), telemetry shows per-workstation activity: browser launches to themed
      domains, OWA hits, and the AD-noise commands (`nltest`/`gpresult`/`nslookup`).
- Activity is attributable per-box (different source workstation + logged-on identity per
      persona), not all coming from one host.

---

- **vCPU oversubscription** — provisioning many Windows VMs at once is the heaviest moment;
  slow/timeout failures here are resource contention, not config errors.
- **Shinju two-inventory merge** — the AD layer needs BOTH `-i ../ad/NARUTO/data/inventory` and
  `-i ../ad/NARUTO/providers/ludus/inventory.yml`; Phase 2 passes both to every playbook in the
  chain. A new host missing from *either* inventory (or `config.json`) silently drops out of AD
  provisioning.
- **Manual post-deploy ordering** — `FGNW-ghosts-activity.yml` preflights the attacker sinkhole
  (fail-fast if `FGNW-attacker-web.yml` hasn't run) and the real Exchange OWA login page by DNS name
  (best-effort — warns, does not fail; a forest with no `-owa` VM legitimately can't reach webmail).
- **2 vCPU / 4 GB Windows workstations** (small-range konoha-ws1/oto-ws1 are 6 GB) — the GHOSTS
  client drives a real Chrome window via the `range_ghosts_browser` role, heavier than a
  single-core load; if `ghosts.exe` or Chrome is sluggish to start, bump the spec.
- **GHOSTS OWA-check** — the BrowserChrome handler opens each persona's own-forest OWA logon page
  (`/owa/auth/logon.aspx`) as a browser-history/visual signal only; OWA is forms-based auth, so
  opening the page does not authenticate.
