Operator/range documentation for **what the emulated users actually do** on this range. This is the
runtime behaviour of the [cmu-sei/GHOSTS](https://github.com/cmu-sei/GHOSTS) NPC clients as
currently programmed — the observable activity a defender or analyst will see in telemetry
(Sysmon, DNS logs, OWA hits, Windows event logs). This is the LOE 1 ("general noise / BAU")
layer of the emulation design; see `docs/ghosts-emulation.md` for the emulation design and the
data-regeneration scripts.

| Piece | File |
| --- | --- |
| Which VMs run a GHOSTS client | `range-config.yml` (`jasonmull.ludus_ghosts_client` role) + `[ghosts_clients]` group in `ad/NARUTO/providers/ludus/inventory.yml` |
| Per-persona data (browse list, domain, OWA) | `content/ghosts/persona-timelines.yml` — **generated** from `content/www/FGNW_user_homepage_mapping.csv` (+ OWA inbox presence from `content/OWA/user-inboxes.yml`) |
| The timeline that gets deployed | `ansible/templates/FGNW-ghosts.timeline.json.j2` |
| The playbook that renders + deploys it | `ansible/FGNW-ghosts-activity.yml` (manual post-deploy step) |
| GHOSTS API server the clients report to | the `r<range>-ghost9` CT (GHOSTS 9.3.0, a `get_sybers.lxc` container from the published ghost9 template; Phase 1b), `10.<range>.99.51:5000/api`, UI `:4200` |

Activity is **per-workstation**, one flagship character per box. There is exactly one GHOSTS client
per flagship (9 total: 5 Leaf, 1 Sound, 2 Akatsuki, 1 Sand), each domain-joined to that character's
domain, so the activity is attributable to a distinct machine + logged-on identity in telemetry.

| Workstation | Character | Domain (VLAN) | Homepage | OWA inbox on konoha-mail? |
| --- | --- | --- | --- | --- |
| konoha-ws1 | Naruto Uzumaki (7th Hokage) | konohagakure.fire.ninja (10) | <www.konoha-portal.leaf> | yes |
| konoha-ws2 | Shikamaru Nara | konohagakure.fire.ninja (10) | <www.konoha-portal.leaf> | yes |
| konoha-ws3 | Kakashi Hatake | konohagakure.fire.ninja (10) | <www.konoha-portal.leaf> | yes |
| konoha-ws4 | Tsunade (5th Hokage) | konohagakure.fire.ninja (10) | <www.konoha-portal.leaf> | yes |
| konoha-ws5 | Might Guy | konohagakure.fire.ninja (10) | <www.konoha-portal.leaf> | yes |
| oto-ws1 | Orochimaru | otogakure.ninja (30) | <www.konoha-portal.leaf>* | yes |
| akatsuki-ws1 | Pain | akatsuki.dark (87) | <www.ame-portal.rain> | yes |
| akatsuki-ws2 | Zetsu | akatsuki.dark (87) | <www.shinobi-world-news.com> | **yes** |
| suna-ws1 | Gaara (5th Kazekage) | sunagakure.wind.ninja (20) | <www.suna-portal.sand> | yes |

\* Orochimaru's homepage/favourites come from his **home** village (Leaf) in the source data, not
his current Sound affiliation — an intentional artifact of his defector/undercover dual identity
(active Oto account + disabled Konoha account; see `docs/range-design.md`). His workstation is in Sound, but
his browsing still leans Leaf-flavoured.
Every persona's `timeline.json` has the same concurrent, looping handlers, differing in the persona's
data (browse URLs, AD domain, OWA user) plus a **hand-authored flagship override** (a signature
handler, a pace, and an activity window). By default handlers run **12:00–23:00 UTC** (a simulated
working day); some characters override that window.
Each flagship has a small set of **signature sites** they obsessively/repeatedly visit, opened in a
dedicated handler whose loop speed is set by the character's `pace` (obsessive ≈ 1–2 min between
hits, normal ≈ 3–5 min, idle ≈ 8–12 min). This is what makes characters observably distinct even
where their baseline browse list overlaps:

| Workstation | Character | Signature sites | Pace | Activity window (UTC) |
| --- | --- | --- | --- | --- |
| konoha-ws1 | Naruto | ichiraku-ramen.com | obsessive | 12:00–23:00 |
| konoha-ws2 | Shikamaru | nara-shadow-tactics.com | obsessive | 12:00–23:00 |
| konoha-ws3 | Kakashi | sharingan-users.net | **idle** (low/slow) | 12:00–23:00 |
| konoha-ws4 | Tsunade | konoha-hospital.med, missionboard.net | normal | 12:00–23:00 |
| konoha-ws5 | Might Guy | mightyguy-youth.com, springtimeofyouth.net | obsessive | **05:00–21:00** (early) |
| oto-ws1 | Orochimaru | orochimaru-research.com, cursemark-community.net, snake-summons-registry.com | normal | 12:00–23:00 |
| akatsuki-ws1 | Pain | pain-gospel.rain, philosophyofpain.com, painispeace.rain | normal | 12:00–23:00 |
| akatsuki-ws2 | Zetsu | konoha/suna/oto portals, bingobookwanted.com, missionboard.net | obsessive | 12:00–23:00 |
| suna-ws1 | Gaara | gaara-for-kazekage.com, kazekage-office.gov.sand | normal | **00:00–23:59** (24/7) |

Zetsu's signature is deliberately **cross-village portal enumeration** — the BAU-flavoured recon that
LOE 2's automated intel injects will trigger off. Overrides live in
`content/ghosts/persona-overrides.yml` (hand-authored source).
The three baseline handlers below are shared by all personas (data-driven), and inherit each
persona's activity window from its override.
The baseline browse handler is a GHOSTS **`BrowserChrome`** handler (real, non-headless Chrome via
Selenium, installed by the `get_sybers.range_ghosts_browser` role), which manages its own browser
lifecycle. It opens, in order:

1. The attacker/tool-cache **sinkhole landing page** (`http://10.<range>.99.50/`) — every persona
   hits this, so all the themed domains resolve somewhere.
2. The persona's **9 browsing URLs** (homepage + the character-specific head of their favourites
   list). These are FGNW-themed domains (e.g. Naruto → `konoha-portal.leaf`, `hokage-office.gov.leaf`,
   `ichiraku-ramen.com`, `nara-shadow-tactics.com`; Pain → `ame-portal.rain`, `pain-gospel.rain`,
   `rinnegan-studies.com`, `akatsuki-manifesto.dark`) that all resolve to the attacker sinkhole via
   its catch-all vhost + the range `dns_rewrites`.
Between each page the client waits a **randomised 2–5 minutes** (`DelayAfter` drawn at render time),
so the cadence looks human and isn't identical across boxes.
3. Opens the real Exchange **OWA login page** for the persona's own forest, by DNS name
   (`https://mail.<forest-domain>/owa/auth/logon.aspx` — e.g. `mail.konohagakure.fire.ninja` for a
   Leaf persona). This is a browser-history/visual signal only — OWA is forms-based auth, so opening
   the page does not authenticate. Best-effort: a forest with no `-owa` mail server (Sound/Akatsuki
   in the small range) simply doesn't resolve and the browse is a soft no-op.

Between loops the handler idles before browsing the list again; it drives one Chrome instance per
shift rather than leaving stale per-URL windows behind.
Light Active Directory reconnaissance-flavoured commands a normal domain user's session generates,
all scoped to the **persona's own domain**:

- `echo %USERDOMAIN%` / `%LOGONSERVER%`
- `nltest /dsgetdc:<persona domain>` (DC discovery)
- `nltest /domain_trusts` (trust enumeration)
- `gpresult /r` (applied-policy read)
- `nslookup -type=SRV _ldap._tcp.dc._msdcs.<persona domain>` (DC SRV lookup), then idles ~15 min.
Because the cross-village DNS forwarders are active (`ansible/dnsforwarder.yml`), these lookups
resolve correctly even for the isolated domains; the noise stays scoped to each host's own domain
for BAU realism (cross-domain recon is not part of this baseline).

| Handler | Starts (UTC) | Between-step delay | Notes |
| --- | --- | --- | --- |
| Web browsing | 12:00 | random 2–5 min | 1 sinkhole + 9 persona URLs per loop |
| Webmail/OWA | 12:30 | 3 min steps, ~20 min idle | own-inbox step only if seeded |
| Domain noise | 13:00 | 10 s steps, ~15 min idle | scoped to own domain |
| (all) | off at 23:00 | — | simulated working day |

- **Baseline browse lists still overlap for the Leaf 5.** The generated
  `FGNW_user_homepage_mapping.csv` gives all five Leaf characters the same homepage/favourites
  head, so their *baseline* browsing handler looks similar. What differentiates them is the
  **signature handler + pace + activity window** above (Naruto's ramen obsession, Kakashi's idle
  pace, Guy's 5am window, etc.). Deeper per-character differentiation (mission-report cadence, email
  behaviour) is sketched in `FGNW-user-emulation-behaviour.md` as reference, not driven by this layer.
- **BAU only.** This is the LOE 1 layer. The automated intel injects (LOE 2) are documented in
  `FGNW-intel-automation.md`, and the scripted attack chain (LOE 3) in `docs/FGNW-CAMPAIGN.md`.
If `FGNW_user_homepage_mapping.csv` or the OWA inbox set changes, regenerate
`persona-timelines.yml` with the script recorded in `docs/ghosts-emulation.md` (LOE 1). Do not
hand-edit the generated file.
