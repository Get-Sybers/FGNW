# Range design: the AD model and content layers

The Fourth Great Ninja War range is a FGNW-themed rebrand of a Shinju-based
multi-domain AD lateral-movement lab (`ad/NARUTO`): the underlying attack paths
(parent domain, child domain, external trusted forest) reskinned as hidden
villages, with decoy infrastructure (the ninjasploitable target, the attacker
web server, Exchange/OWA, village file shares, simulated internet traffic) that
makes the range read as a lived-in network rather than a bare lab. This document
is the design reference for the AD data model and the content-generation layers;
the live VM topology is in [`range-config.yml`](../../range-config.yml),
[`SMALL-RANGE.md`](SMALL-RANGE.md) and [`FGNW-CAMPAIGN.md`](FGNW-CAMPAIGN.md).

## Domains and forests

Six domains across four forests, built natively by `ludus range deploy`
(`domain:` blocks + `badsectorlabs.ludus_windows_utils` roles):

| Domain FQDN | NetBIOS | Village / Land | DC hostname | VLAN | Role |
| --- | --- | --- | --- | --- | --- |
| `fire.ninja` | FIRE | Land of Fire (forest root) | `fire-dc1` | 10 | parent DC |
| `konohagakure.fire.ninja` | KONOHA | Hidden Leaf (child of Fire) | `konoha-dc1` | 10 | child DC |
| `wind.ninja` | WIND | Land of Wind (forest root) | `wind-dc1` | 20 | parent DC |
| `sunagakure.wind.ninja` | SUNA | Hidden Sand (child of Wind) | `suna-dc1` | 20 | child DC |
| `otogakure.ninja` | OTO | Hidden Sound (external forest) | `oto-dc1` | 30 | parent DC |
| `akatsuki.dark` | AKATSUKI | Akatsuki (isolated) | `akatsuki-dc1` | 87 | parent DC |

Trusts:

- `fire.ninja` ⇄ `otogakure.ninja` — bidirectional external forest trust, the
  one external trust in the range and the cross-forest attack path.
- `akatsuki.dark` — no trust; the isolated rogue org.
- Parent-child trusts (`fire.ninja` ⇄ `konohagakure.fire.ninja`,
  `wind.ninja` ⇄ `sunagakure.wind.ninja`) are automatic from the child-domain
  join.

Domain admins: `naruto.uzumaki` (Leaf), `gaara` (Sand), `orochimaru` (Sound),
`pain` (Akatsuki). The Land roots `fire.ninja` and `wind.ninja` are structural
forest roots; `fire.ninja` additionally carries two real users (`fire.daimyo`,
`shijimi`) in its `Daimyo Council` OU, and `wind.ninja` is userless.

## The AD data model

`ad/NARUTO/data/config.json` is generated from `content/AD/characters.csv` (198
characters). The domain FQDNs, `{land/village}-dc1` hostnames, OUs, groups and
user assignments all derive from the CSV:

- **OUs** are village-themed — Leaf: Kage Office, Jonin Corps, Special
  Operations, Medical Wing, Academy; Sand: Kazekage Office, Jonin Division,
  Puppet Corps, Recruits; Sound: Sound Council, Sound Five, Sound Recruits. OU
  placement follows each character's title/primary group.
- **Groups** come from the CSV's pipe-separated `groups` column, filtered per
  domain, with AD group nesting via the `members` field — Leaf `ANBU` contains
  `Root`, `Konoha Jonin` contains the named teams; Sand `Sand Jonin` contains
  `Sand Siblings`; Sound `Sound Five` contains `Kaguya Clan`.
- **Population**: Leaf ~70 active users (plus ~6 disabled), Sand ~7 (plus 1
  disabled), Sound ~7, Akatsuki ~14.

### Defector / missing-nin accounts

A character is a defector when their home `village` and current `department`
disagree in `characters.csv` (e.g. Orochimaru: village = Leaf, department =
Sound). Such a character gets **two** accounts: an active one in the domain they
operate in, and a disabled (`enabled: false`) legacy account in their original
village's domain. This is a deliberate attack-path hook — dormant
privileged-adjacent accounts for "account exists but is disabled" recon and
old-password reuse across the disabled/active pair, and the mechanism behind the
undercover-correspondence flavour (an operator sending mail from a disabled home
identity). Leaf carries six banished accounts (Itachi, Orochimaru, Madara,
Obito, Kabuto, Sasori's puppet identity); Sand carries one (Sasori).

## Content layers

| Layer | Source → generated | Consumer |
| --- | --- | --- |
| Decoy documents | `content/filesystem/documents.txt` → `village-folders.yml` | `fgnw_decoy_files` via `FGNW-decoy-content.yml` |
| Browser defaults | `content/www/FGNW_character_websites.csv` → `village-bookmarks.yml` | `fgnw_browser_defaults` via `FGNW-browser-defaults.yml` |
| Themed sites | `FGNW_character_websites.csv` → `site-archetypes.yml` | `fgnw_themed_sites` via `FGNW-themed-sites.yml` |
| DNS sinkhole | the 144 domains in `FGNW_character_websites.csv` | `dns_rewrites` on the `attacker` VM |
| Attacker web | `content/www/attacker-tools.yml` | `ludus_tool_cache` via `FGNW-attacker-web.yml` |
| GHOSTS personas | see [`ghosts-emulation.md`](ghosts-emulation.md) | `FGNW-ghosts-activity.yml` |

- **Decoy files.** `documents.txt`'s hand-authored ASCII folder trees (per
  village/org, plus a non-village `Naruto Uzumaki (Personal Workstation)` key)
  are parsed into `village-folders.yml`; `fgnw_decoy_files` materialises one
  village's tree under a given root as placeholder or authored files
  (`force: false`, so re-runs do not stomp edits). The Naruto workstation key
  plants everyday-messy-user artifacts (duplicate downloads, a cleartext
  passwords file, notepad reminders) into his own `C:\Users\naruto.uzumaki`
  profile on `konoha-ws1` rather than the shared village drive.
- **Browser defaults.** `village-bookmarks.yml` sets a machine-wide homepage and
  bookmark list (`HKU\.DEFAULT` + a Public-Desktop bookmarks HTML file), not
  per-character. `FGNW_user_homepage_mapping.csv` holds the per-character
  mapping and feeds the GHOSTS persona baseline instead.
- **Attacker web and sinkhole.** The `attacker` VM runs nginx from
  `ludus_tool_cache` (a themed tool-download page) with a catch-all vhost, and
  the range's `dns_rewrites` resolve all 144 themed domains to it.
- **Ninjasploitable.** `range_ninjasploitable_server` (Apache + PHP + MySQL +
  vsftpd, intentionally weak) is the "Ichiraku" webshell-upload target, themed
  as the Leaf mission-report intake (`/reports/intake.php`) by
  `FGNW-ninjasploitable-content.yml` and domain-joined to `fire.ninja` by
  `FGNW-ninjasploitable-join.yml`.
