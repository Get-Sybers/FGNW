A guided, lore-accurate attack-chain walkthrough (LOE 3) that ties this range's techniques together
as one story: **the Akatsuki's infiltration of the Allied Shinobi Forces.** Every host, account,
trust, and foothold named below is real in this range — see `range-config.yml`, `ad/NARUTO/data/
config.json`, and the plan docs.
This is a **red-team narrative + blue-team observation guide**. It's a training scenario for
authorized use on this lab only. `10.<r>.` = `10.<range_second_octet>.`.

- **Akatsuki** = the adversary. Domain `akatsuki.dark` (VLAN 87), deliberately **isolated / no AD
  trust** — the rogue org outside the shinobi nations. C2/tooling home.
- **Tool cache**: `attacker` VM (`10.<r>.99.50`) — the Akatsuki pre-staged offensive tooling (see
  `FGNW-attacker-web.yml`). **Zetsu** (`akatsuki-ws2`) is the recon/enumeration persona (his GHOSTS
  profile already cycles village portals + the bingo book — that's the BAU cover for real recon).
  **Pain** (`akatsuki-ws1`) is the operation lead.
- **Objective**: reach the jinchūriki/bijuu intelligence held by the villages — modelled as
  domain-admin control of Konoha (Leaf) and a cross-forest pivot into Sound.
- **Konoha / Leaf** (`konohagakure.fire.ninja`, VLAN 10) — child of the Land of Fire forest root
  (`fire.ninja`). 5 flagship workstations `konoha-ws1..5`, DA `naruto.uzumaki`.
- **Fire ↔ Sound trust**: `fire.ninja` ⇄ `otogakure.ninja` **bidirectional forest trust** — the one
  external trust in the range, and the cross-forest attack path. `sidhistory.ps1` is wired on
  `konoha-dc1` (SID-history primitive on that trust).
- **Orochimaru** — the human bridge: **active** account in Sound (`otogakure.ninja`, DA) **and a
  disabled legacy account** in Konoha (his home village). The classic missing-nin dual identity.
- **Shared local-admin password** — every Windows host uses the same local admin secret, so one
  cracked/pass-the-hash local admin unlocks lateral movement across all of them.
- **Weak domain passwords** — user passwords are seeded and predictable (the lore mottos:
  `WillOfFire1`, `Hokage123`, `Believe1t` …) — sprayable.
- **Ichiraku mission-report intake** — `ninjasploitable` (`10.<r>.90.10/reports/intake.php`), an
  **unrestricted file upload** (→ webshell). The "civilian" Land-of-Fire report server.
Zetsu's workstation already generates cross-village portal enumeration + bingo-book lookups as BAU
noise; the real recon rides that cover. Enumerate the villages' public portals (now real sites, LOE 4)
and the mission board (`www.missionboard.net`) for shinobi names → build a user list.
Zetsu also runs **real** `nmap` host/service discovery and `--script vuln` scanning against the
Fire+Leaf subnet (VLAN 10) and the Sand subnet (VLAN 20) — never sourced from those villages, only
targeting them — plus a rate-capped "cannon" DoS attempt against Leaf's OWA portal and Sand's DC
(`content/ghosts/persona-overrides.yml`'s `akatsuki-ws2.recon_legs`, rendered into
`FGNW-ghosts.timeline.json.j2`). This is deliberately the **loud, expected-to-be-caught** half of
the campaign — see the technique map below for how it's meant to read differently from Phases 2–5's
quiet, credentialed techniques.
*Blue view:* directory-enumeration spikes in DNS logs, a burst of nmap-flavoured connections
across VLANs 10/20, and a short connection-flood burst against konoha-mail/suna-dc1 — exactly the
`content/ghosts/FGNW-intel-automation.md` "RECON ALERT" / "DOS ALERT" triggers (LOE 2).
- **Password spray** (low-and-slow, the Akatsuki lore behavior): spray the weak mottos against Leaf
  OWA / a village portal, staying under lockout. Lands a low-priv Leaf shinobi account.
- **Webshell**: upload a PHP webshell through the Ichiraku report intake (`/reports/intake.php`, no
  validation) → code execution on `ninjasploitable` (VLAN 90). Foothold in the "civilian" net.
*Blue view:* spray = auth-failure pattern; webshell = new file under `/uploads/` + apache child procs.
From the foothold, harvest credentials (LSASS / SAM / cached). Because the **local admin secret is
shared**, one local-admin hash is a master key. **(Over)Pass-the-Hash** with it.
Pass-the-hash the shared local admin (or a sprayed domain user) laterally across the flagship
workstations `konoha-ws1..5` over **SMB, WMI, RDP, and WinRM** (note WinRM here is **https/5986**).
Pivot through a **SOCKS** proxy from the foothold to reach the internal VLAN. Each box is a named
shinobi's machine (Naruto/Shikamaru/Kakashi/Tsunade/Guy) — hop toward one with privileged group
membership.
*Blue view:* remote-service auth from an unusual source host; Sysmon process/network telemetry.
- **Kerberoasting**: request service tickets for the Leaf service account with an SPN and crack it
  offline (weak password). *(Requires the campaign-setup primitive — see below.)*
- **Token impersonation / creation**: impersonate a logged-on privileged token on a compromised host
  to act as a higher-privileged Leaf user, climbing toward DA `naruto.uzumaki`.
The prize path. With Konoha compromised, abuse the **`fire.ninja` ⇄ `otogakure.ninja` trust**:
- **Orochimaru's dual identity** is the narrative bridge — his disabled Konoha account and active
  Sound DA account tie the two forests together (old-password reuse / undercover recon hook).
- **SID history** (`sidhistory.ps1` primitive on `konoha-dc1`) / **Pass-the-Ticket / Overpass-the-Hash**
  across the trust to authenticate into `otogakure.ninja` and reach Sound DA (`orochimaru`).
*Blue view:* cross-forest TGS/referral traffic; the intel-automation "cross-village recon" broadcast.
Consolidate control, collect the jinchūriki/bijuu intel, and exfil back to the **isolated
`akatsuki.dark`** C2 via the tool-cache/attacker net. Pain closes the operation.

| README technique | Phase | Concrete element in this range |
| --- | --- | --- |
| (over)Pass-the-Hash | 2–3 | Shared local-admin hash across all Windows hosts |
| Pass-the-Ticket / Overpass-the-Hash | 5 | fire.ninja ⇄ otogakure.ninja trust |
| Remote services (SMB/WMI/RDP/WinRM) | 3 | konoha-ws1..5 (WinRM https/5986) |
| SOCKS PtH | 3 | pivot from ninjasploitable/foothold into the AD VLANs |
| Kerberoasting | 4 | planted Leaf SPN service account (campaign-setup) |
| Token impersonation / creation | 4 | privileged tokens on compromised Leaf hosts |
| (bonus) SID history abuse | 5 | `sidhistory.ps1` on konoha-dc1 |
| (bonus) Unrestricted upload → webshell | 1 | `ninjasploitable` `/reports/intake.php` |
| T1595.001 Active Scanning: Scanning IP Blocks | 0 | Zetsu's nmap sweeps, VLAN 10 (Fire+Leaf) + VLAN 20 (Sand) |
| T1595.002 Active Scanning: Vulnerability Scanning | 0 | Zetsu's `nmap --script vuln`, same targets |
| T1498.001 Network DoS: Direct Network Flood | 0 | Zetsu's rate-capped "cannon" vs konoha-mail (80) + suna-dc1 (445) |

**Loud vs. quiet, on purpose:** Phase 0's scanning/DoS techniques (T1595.\*, T1498.001) are meant to
be caught — they're the profiled, MITRE-tagged noise that `content/ghosts/FGNW-intel-automation.md`'s RECON
ALERT/DOS ALERT emails react to, and their behavioral signature (subnet-wide sweeps, obvious tool
flags, a short bounded flood, then silence) is deliberately distinct from Phases 2–5's real
compromise techniques ((over)Pass-the-Hash, Kerberoasting, token impersonation, SID history), which
stay quiet and credentialed rather than noisy and scan-shaped. A discoverable dossier documenting
this exact TTP split lives on `konoha-dc1` and `suna-ws1` (see `content/filesystem/documents.txt`'s
classified Mission Reports entries) for a blue-team player who finds it to correlate against.
Most of the chain uses surface that already exists (trust, shared local admin, weak creds, webshell,
SID-history). Two primitives need planting so the **Kerberoasting** and **AS-REP roasting** beats are
actually exercisable — implemented in `ansible/FGNW-campaign-setup.yml` and **auto-wired as
Phase 4c** of `deploy.yml` (runs automatically after the AD build and content seeding):

- a Leaf **service account with an SPN + weak password** (`svc-missionboard`, kerberoastable),
  themed as the Konoha mission-board service;
- one Leaf account flagged **`DoesNotRequirePreAuth`** (`konohamaru.sarutobi`, AS-REP roastable),
  themed as a careless genin.
No manual step is required — these objects are planted during every standard `deploy.yml` run.
Everything else in the chain is live-deploy exercisable as-is.
This is a DFIR range (Sysmon + ACSC event logging on every Windows VM; GHOSTS BAU noise; the intel-automation loop).
The campaign doubles as a detection exercise: each phase above lists the telemetry it generates, and
LOE 2's automated intel injects are the in-world "SOC" reacting to phases 0/1/5. Run the campaign,
then hunt it in the telemetry.
