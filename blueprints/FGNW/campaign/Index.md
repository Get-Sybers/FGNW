The authoritative navigation point for this blueprint. Open this file first; it tells you
which document to open next. If two docs disagree, the one named canonical here wins.
This blueprint is the range tier of the Get-Sybers lab — see the cross-repo map
at the end of this file.

---

| You want to… | Read |
| --- | --- |
| **Understand what this range is** | [`README.md`](README.md) → [`docs/FGNW-CAMPAIGN.md`](docs/FGNW-CAMPAIGN.md) |
| **Deploy the range for the first time** | [`ludus-requirements.yml`](ludus-requirements.yml) (prerequisites checklist), then [`docs/DEPLOY.md`](docs/DEPLOY.md) |
| **Resume or re-run a specific phase** | [`docs/DEPLOY.md`](docs/DEPLOY.md) — `range_from_phase=<token>` section |
| **Verify the deploy actually worked** | [`docs/deploy-verification-checklist.md`](docs/deploy-verification-checklist.md) |
| **Something broke — fix it** | [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) |
| **Use the range as a red/blue scenario** | [`docs/FGNW-CAMPAIGN.md`](docs/FGNW-CAMPAIGN.md) — guided attack-chain walkthrough |
| **Understand GHOSTS persona activity** | [`content/ghosts/persona-behaviour.md`](content/ghosts/persona-behaviour.md) |
| **Deploy only the small (9-VM) variant** | [`docs/SMALL-RANGE.md`](docs/SMALL-RANGE.md) |

---
Everything Ludus reads sits at `blueprints/FGNW/`. The `campaign/`
subdirectory (this file's home) holds all orchestration, content, and docs; Ludus ignores it
but `deploy.yml` uses it entirely.

```text
blueprints/FGNW/
├── blueprint.yml              Ludus blueprint manifest (id, name, config pointer)
├── range-config.yml           THE range config — the 23-VM superset plus the
│                              `ludus_extensions.variants` map every variant is cut from
└── campaign/                  All orchestration, content, and docs (Ludus ignores this)
    ├── README.md              One-paragraph intro — start here if you've never seen the range
    ├── Index.md               ← this file: complete doc map
    ├── LICENSE                MIT — the campaign's own licence
    ├── ludus-requirements.yml Prerequisites checklist: templates, Nexus, roles, deploy tags
    ├── deploy.yml             Only supported entry point — runs tokens 0 1 1b 1c 2 3 4 4b 4c 4d 4e 5
    │
    ├── ad/                    Active Directory build data (Shinju)
    │   └── NARUTO/
    │       ├── data/          config.json (AD schema for all 6 forests), config-small.json,
    │       │                  and the host inventory files used by the Shinju playbook chain
    │       └── providers/
    │           └── ludus/     inventory.yml, inventory-small.yml, *-infra.yml variants
    │                          (RANGENUMBER placeholder — substitute the range second octet)
    │
    ├── ansible/               Post-deploy playbooks and the campaign's own roles
    │   ├── FGNW-*.yml         22 FGNW-prefixed playbooks — run in Phases 4–5 (see below)
    │   ├── ad-data.yml        AD content (OUs/groups/users) via fgnw_ad_mgmt, Phase 3
    │   ├── ansible.cfg        Ansible config for this blueprint
    │   └── roles/             The campaign's own roles (fgnw_*, adcs, …); third-party roles come from GitHub via the blueprint's requirements.yml
    │
    ├── content/               Range universe data — source files and generated artefacts
    │   ├── README.md          Complete data-source inventory (what every file is, how to regenerate)
    │   ├── AD/                AD character source data (characters.csv — 198 characters)
    │   ├── OWA/               Email content (user-inboxes.yml generated, email-content.csv source)
    │   ├── filesystem/        Decoy document tree definitions (source + generated YAML)
    │   ├── ghosts/            GHOSTS persona data, behaviour docs, email relationship graph
    │   └── www/               Themed-site data, browser bookmarks, attacker-tools catalogue
    │
    ├── deploy-tasks/          Phase task files included by deploy.yml; each named for its token
    │   ├── phase0-nexus.yml           Nexus cache bring-up (server-wide; once)
    │   ├── phase1-vms.yml             VM provision via `ludus range deploy`
    │   ├── phase1b-ghost9.yml         The ghost9 CT — GHOSTS 9.3.0 as a get_sybers.lxc container from the
    │   │                              published ghost9 template; built pre-containment
    │   ├── phase2-containment.yml     `ludus testing start` (no egress carve-outs)
    │   ├── phase3-ad.yml              Runs the Shinju playbook chain for AD build
    │   ├── phase4-content.yml         Post-deploy content playbooks (tools, personas, decoy files)
    │   ├── phase4b-exchange.yml       Exchange 2019 install + mail seed
    │   ├── phase4c-threat.yml         Threat artefact planting (implants, LOE-3 campaign primitives)
    │   ├── phase5-emulation.yml       GHOSTS NPC emulation start (must run AFTER containment)
    │   ├── phase5-verify.yml          Post-deploy verification (connectivity + emulation gates)
    │   ├── materialize-infra-inv.yml  Helper: materialises the infra inventory with per-range credentials
    │   ├── run-playbook.yml           Helper: runs one Shinju playbook against both inventories
    │   └── cleanup-credentials.yml    Shreds the run's credential-bearing files and proves they are gone
    │
    ├── docs/                  All user-facing documentation (see map below)
    ├── tests/                 Isolated sub-range deploy fixtures for unit testing individual subsystems
    ├── filter_plugins/        Ansible filters used by deploy.yml (fgnw_variants.py — variant selection)
    └── ci/                    CI support scripts (syntax-check.sh, variant-filter-selftest.py)
```

---

| Doc | What it covers | When to read it |
| --- | --- | --- |
| [`docs/DEPLOY.md`](docs/DEPLOY.md) | **Canonical deploy procedure** — phase-by-phase commands, `deploy.yml` flags, isolation model, Exchange notes | Before and during any deploy |
| [`ludus-requirements.yml`](ludus-requirements.yml) | Machine-readable prerequisites checklist — templates to build, Nexus repos, roles to install, Ludus deploy-tag inventory | Before first deploy; after any Ludus upgrade |
| [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) | Failure runbook — rangeState=ERROR recovery, Nexus issues, Exchange errors, AD build failures, sysmon_linux timing | When something breaks |
| [`docs/deploy-verification-checklist.md`](docs/deploy-verification-checklist.md) | Post-deploy checks — per-subsystem pass/fail assertions | After every full deploy |
| [`docs/SMALL-RANGE.md`](docs/SMALL-RANGE.md) | Small range topology (9 VMs), footprint table, what's kept vs dropped | When deploying the small variant |
| [`docs/RANGE-CONFIG-VARIANTS.md`](docs/RANGE-CONFIG-VARIANTS.md) | The single-config model — how `-e range_variant=` cuts small/regular/xl out of one file, and how to add a VM or a variant | Before editing `range-config.yml` |
| [`docs/CLIENT-DEPLOY.md`](docs/CLIENT-DEPLOY.md) | Client-side deploy path (Ludus CLI over the v2 API) — builds the range VMs + native AD and containment; the scenario tail runs server-side via `deploy.yml` | When driving the range build from a client |
| Doc | What it covers | |

| --- | --- |
| [`docs/FGNW-CAMPAIGN.md`](docs/FGNW-CAMPAIGN.md) | Guided red/blue attack-chain walkthrough — Akatsuki infiltration, technique-by-technique with real host/account/trust references |
| [`content/ghosts/persona-behaviour.md`](content/ghosts/persona-behaviour.md) | What each GHOSTS persona does at runtime — the observable telemetry a defender will see |

| Doc | What it covers |
| --- | --- |
| [`docs/ghosts-emulation.md`](docs/ghosts-emulation.md) | GHOSTS emulation design: the persona model and the data-regeneration scripts |
| [`docs/OWA-REAL-VS-SIMULATED.md`](docs/OWA-REAL-VS-SIMULATED.md) | Real Exchange 2019 / OWA on the three Windows forests |
| [`docs/ADCS.md`](docs/ADCS.md) | ADCS / ESC1 cert path on the Sand forest |
| [`docs/MODERN-INFRA.md`](docs/MODERN-INFRA.md) | The modern-infra stack shipped in the `xl` range variant (LOE 5) |
| [`docs/range-design.md`](docs/range-design.md) | Range design: the AD model and the content layers |

---
All 22 `FGNW-*.yml` playbooks live in `ansible/`. They run against the infra inventory
(`inventory-{small-,}infra.yml`) unless noted. The phase each belongs to matches
`deploy-tasks/phase4-content.yml` / `phase4b-exchange.yml` / `phase4c-threat.yml` /
`phase5-emulation.yml`.

| Playbook | Phase | What it does |
| --- | --- | --- |
| `FGNW-attacker-web.yml` | 4 | Nginx tool-cache + 144-domain themed sinkhole on the attacker VM |
| `FGNW-themed-sites.yml` | 4 | Per-domain themed pages on the attacker nginx (LOE 4 village portals) |
| `FGNW-recon-tooling.yml` | 4 | nmap (portable) + cannon script on akatsuki-ws2 (regular/xl only) |
| `FGNW-ninjasploitable-content.yml` | 4 | Themes ninjasploitable as the Leaf mission-report intake (`/reports/intake.php`) |
| `FGNW-ninjasploitable-join.yml` | 4 | Domain-joins ninjasploitable to `fire.ninja` (Linux domain member) |
| `FGNW-persona-autologon.yml` | 4 | Forces each flagship's first interactive domain logon via autologon + reboot |
| `FGNW-decoy-content.yml` | 4 | Plants decoy documents on Leaf/Sound/Akatsuki DCs and Naruto's workstation |
| `FGNW-browser-defaults.yml` | 4 | Configures per-persona browser homepage and bookmarks on GHOSTS workstations |
| `FGNW-browser-extensions.yml` | 4 | Installs the Konoha form-helper Chrome extension on Leaf workstations |
| `FGNW-acsc-logging.yml` | 4 | Applies ACSC-baseline Windows event-logging config (calls `get_sybers.acsc_event_logging`) |
| `FGNW-sysmon-linux.yml` | 4 | Applies `get_sybers.sysmon_linux` to all Linux infra hosts in one call |
| `FGNW-exchange.yml` | 4b | Real Exchange 2019 CU15 install — domain-join, mailboxes, groups, send connectors |
| `FGNW-exchange-seed-mail.yml` | 4b | Real SMTP mail delivery of the quote corpus to all Exchange mailboxes (NOT idempotent) |
| `FGNW-owa-cert.yml` | 4b | Issues OWA cert matching `mail.<domain>` and trusts it on workstations (UNTESTED) |
| `FGNW-campaign-setup.yml` | 4c | Plants LOE-3 primitives: Kerberoastable SPN + AS-REP account on `konoha-dc1` |
| `FGNW-ghosts-activity.yml` | 5 | Renders and deploys GHOSTS persona timelines to all GHOSTS workstations |
| `FGNW-verify-connectivity.yml` | 5 | Read-only: checks HTTP targets (attacker tool-cache, ninjasploitable intake, per-forest OWA); fails the play if any check misses |
| `FGNW-verify-emulation.yml` | 5 | Read-only: queries GHOSTS API per persona; fails if any host is unregistered or stale |
| `get_sybers.lxc.deploy_ghost9_range` (imported) | 1b | The `get_sybers.lxc` collection's play, run by its collection-qualified name: the GHOSTS server CT from the ghost9 template (`lxc_preflight` → `lxc_ghost9` `container` → `lxc_guest` `baseline` → `lxc_ghost9` `server`); `-t destroy` removes it |
| `ghost9-verify.yml` | 1b | Read-only: GHOSTS API v9 + `/api/machines` + UI `:4200` on the range VLAN |
| `ghost9-emulation-proof.yml` | — | Writes machine/timeline/activity records through the real client API routes to prove a server executes the FGNW emulation (point it at a server under test, never a live range) |

AD promotion, child domains, member joins and the fire↔oto forest trust are built by
`ludus range deploy` itself (native `primary-dc` + `badsectorlabs.ludus_windows_utils`
roles). Phase 3 (`deploy-tasks/phase3-ad.yml`) then runs the post-AD tail —
`tgtdelegation.yml`, `ad-data.yml` (owned content via `fgnw_ad_mgmt`), `lat.yml`,
`reboot.yml`, then `adcs.yml` (Defender-disable is native — `windows.gpos: [disable_defender]`,
phase 1). `dnsforwarder.yml` needs **both**
inventories (AD-only + providers) and is called in Phase 4 by
`deploy-tasks/phase4-content.yml`.

---
`content/README.md` is the authoritative inventory for this directory. Quick reference:

| Path | Kind | What it is |
| --- | --- | --- |
| `content/AD/characters.csv` | source | 198 AD characters: sAMAccountName, display name, village, role, groups, manager, description |
| `content/OWA/email-content.csv` | source | 543 character quotes formatted as inter-village correspondence |
| `content/OWA/user-inboxes.yml` | **generated** | Per-user inbox data consumed by `FGNW-exchange-seed-mail.yml` |
| `content/filesystem/documents.txt` | source | Hand-authored village document-tree definitions |
| `content/filesystem/village-folders.yml` | **generated** | Flat file-path list consumed by `fgnw_decoy_files` role |
| `content/ghosts/persona-timelines.yml` | **generated** | Per-GHOSTS-client persona data consumed by `FGNW-ghosts-activity.yml` |
| `content/ghosts/persona-overrides.yml` | source | Hand-authored per-character GHOSTS behaviour overrides (pace, hours, signature URLs) |
| `content/ghosts/persona-behaviour.md` | reference | Runtime docs — what each persona does; the observable telemetry |
| `content/ghosts/email-relationships.yml` | **generated** | AD-derived correspondent graph (893 edges; drives mail delivery routing) |
| `content/ghosts/FGNW-intel-automation.md` | reference | GHOSTS automated intel-tip email design (RECON ALERT / DOS ALERT) |
| `content/www/FGNW_character_websites.csv` | source | 173 themed URLs; drives `dns_rewrites` and browser bookmarks |
| `content/www/village-bookmarks.yml` | **generated** | Per-village bookmark list consumed by `fgnw_browser_defaults` |
| `content/www/attacker-tools.yml` | source | Categorised offensive tool list for the attacker VM nginx download page |
| `content/www/site-archetypes.yml` | **generated** | 144 domains → archetype mapping; drives themed-site page rendering |
| `content/www/character-profiles.yml` | **generated** | Per-character jutsu + quotes for LOE-4 themed-site content depth |

Regeneration scripts for generated files are embedded in `content/README.md` and `docs/ghosts-emulation.md`.

---
The Get-Sybers lab spans several repositories. Each has its own root index; start at the one that owns what you're changing.

| Repo | Owns | Index |
| --- | --- | --- |
| **`blueprints/FGNW/`** (here) | The range blueprint: configs, phases, content, AD build. Ships from `Get-Sybers/FGNW`. | this file · [`../../README.md`](../../README.md) |
| [**Get-Sybers/FGNW**](https://github.com/Get-Sybers/FGNW) | Range tier: this blueprint, `get_sybers.range`, range task-roles + templates | [`README.md`](https://github.com/Get-Sybers/FGNW/blob/main/README.md) |
| [**Get-Sybers/proxmaxxing**](https://github.com/Get-Sybers/proxmaxxing) | Cluster tier: `get_sybers.cluster` — the Proxmox nodes and the Ludus server | [`README.md`](https://github.com/Get-Sybers/proxmaxxing/blob/main/README.md) |
| [**Get-Sybers/LXC**](https://github.com/Get-Sybers/LXC) | LXC tier: `get_sybers.lxc` — the ghost9 container the range's user emulation reports to | [`README.md`](https://github.com/Get-Sybers/LXC/blob/main/README.md) |
| **Get-Sybers/ludus-plusplus** | Infra tier: `get_sybers.infra` — the Nexus cache the deploy seeds | — |
| **Get-Sybers/ludus-client** | Client-side tooling (the `ludus` CLI; no Ansible control node) | — |
