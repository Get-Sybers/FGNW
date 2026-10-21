A Naruto-themed multi-domain Active Directory range for [Ludus](https://docs.ludus.cloud/):
four AD forests / six domains (Land of Fire + Hidden Leaf, Land of Wind + Hidden Sand,
Hidden Sound) plus the isolated Akatsuki C2 forest, 9 GHOSTS user-emulation personas, decoy village content, real
Exchange 2019 OWA on the three Windows forests, and Postfix/Dovecot on the Sand macOS forest.
**→ New here? Start with [`Index.md`](Index.md) — the complete navigation guide.**

| Layer | What's in it |
| --- | --- |
| **Network** | 4 AD forests / 6 domains across 6 VLANs (Fire+Leaf, Wind+Sand, Sound, Akatsuki); `fire.ninja ↔ otogakure.ninja` bidirectional trust; DNS conditional forwarders; no internet once Phase 5 containment is live |
| **Active Directory** | ~106 provisioned AD accounts across 6 domains (from a 198-character roster); weak / spray-able passwords; shared local-admin hash; Kerberoastable SPN; AS-REP account; SID-history primitive |
| **Mail** | Real Exchange 2019 on `konoha-mail`; 70 mailboxes; 400+ real character-quote messages delivered via genuine SMTP |
| **User emulation** | 9 GHOSTS NPC personas — one per flagship workstation — generating themed web browsing, OWA hits, and AD "domain noise" during a simulated working day; reporting to the `ghost9` CT, GHOSTS 9.3.0 as a `get_sybers.lxc` container from the published ghost9 template (API `:5000`, UI `:4200`, Grafana `:3000`, n8n `:5678`) |
| **DFIR telemetry** | Velociraptor agent on every VM; Sysmon on Windows; sysmon-for-linux on Linux; ACSC baseline Windows event logging |
| **Attacker infra** | Kali workstation; attacker VM with 144-domain themed sinkhole and nginx offensive-tool cache; ninjasploitable webshell target |
| **Content** | Decoy documents on every domain (Leaf, Sand, Sound, Akatsuki, Naruto's personal workstation); per-domain themed village web portals (LOE 4) |

- (Over)Pass-the-Hash — shared local-admin hash across all Windows VMs
- Pass-the-Ticket / Overpass-the-Hash — via the `fire.ninja ↔ otogakure.ninja` forest trust
- Remote services lateral movement — SMB, WMI, RDP, WinRM (https/5986)
- SOCKS proxy pivoting
- Kerberoasting and AS-REP roasting
- Token impersonation and token creation
- SID-history abuse (planted primitive on `konoha-dc1`)
- Unrestricted file upload → webshell (ninjasploitable `/reports/intake.php`)
The range comes with a full guided red/blue scenario: **the Akatsuki's infiltration of the Allied
Shinobi Forces**, mapping every technique above to a lore beat and a real host/account/trust. See
[`docs/FGNW-CAMPAIGN.md`](docs/FGNW-CAMPAIGN.md).

| Variant | VMs | RAM | Use when |
| --- | --- | --- | --- |
| `small` | 9 | 64 GB | Quick validation; Leaf + Sound + infra only |
| `regular` (default) — **canonical** | 22 | 104 GB | The range. All 6 domains and all 9 personas. |
| `xl` | 23 | 112 GB | Canonical + the LOE-5 `modern-infra` VM |

1. **Read the prerequisites** — [`ludus-requirements.yml`](ludus-requirements.yml) lists every template,
   Nexus repo, and role that must exist on the Ludus server before `ludus range deploy` will succeed.
2. **Follow the deploy procedure** — [`docs/DEPLOY.md`](docs/DEPLOY.md) is the canonical
   phase-by-phase guide; `deploy.yml` is the single supported entry point.
3. **Verify it worked** — [`docs/deploy-verification-checklist.md`](docs/deploy-verification-checklist.md)
   has concrete pass/fail checks for every subsystem.
4. **Gather Nexus requirements automatically**
   - From blueprint facts:
     `python3 ci/nexus-requirements-gather.py blueprint --format yaml`
   - From a live deploy log (failed downloads/install due Nexus unavailability):
     `python3 ci/nexus-requirements-gather.py live-log --log-file /path/to/deploy.log --format yaml`
Ludus environment setup: <https://docs.ludus.cloud/>
Nine flagship characters each run a [GHOSTS](https://github.com/cmu-sei/GHOSTS) NPC client on their
own domain-joined workstation, generating themed web browsing, OWA/webmail visits, and light AD
"domain noise" (nltest, gpresult, nslookup) during a simulated working day. The range behaves like a
lived-in network, not a bare lab.
The personas: Naruto, Shikamaru, Kakashi, Tsunade, Guy (Leaf) · Orochimaru (Sound) · Pain, Zetsu
(Akatsuki) · Gaara (Sand).
For exactly what each persona does and when — the observable activity in telemetry — see
[`content/ghosts/persona-behaviour.md`](content/ghosts/persona-behaviour.md).

- [Bad Sector Labs](https://x.com/badsectorlabs) for guidance and testing on
  Ludus.
