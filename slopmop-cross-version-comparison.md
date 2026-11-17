# slopMop cross-version comparison — FGNW range testing

Versions tested on the FGNW Ludus cyber range (range_id JB, second_octet 1)
against the same artefact set on konoha-ws1 (`C:\slopmop-capture`, 82 files).

## Version matrix

| | v0.1.0 | v0.3.0 | main (73c1784) | v0.5.0 | v0.5.3 |
| --- | --- | --- | --- | --- | --- |
| Binary size | 5.8 MB | ~6 MB | 6.3 MB | 8.1 MB | 8.5 MB |
| Go module | 1.27.4 | 1.27.4 | 1.27.4 | 1.27.4 | 1.27.4 |
| CLI pattern | `slopmop NOUN VERB` | `slopmop NOUN VERB` | `slopmop -inputdir VERB [section]` | same as main | same as main |
| Recurse into zips | No | No | Yes | Yes | Yes |
| Files detected (ws1) | 71 | 65 | 82 | 82 | 82 |
| Credential masking | No | No | Yes (`-secrets`) | Yes | Yes |
| Disk output (`-outdir`) | No | No | 7 files | 10 files | 10 files |
| STIX 2.1 intelfile | No | No | Yes | Yes | Yes |
| ATLAS coverage | No | No | Yes (AML.T*) | Yes | Yes |
| HTML report | No | No | No | Yes | Yes |
| Markdown report | No | No | No | Yes | Yes |
| ARTEX intents section | No | No | No | Yes (empty for this data) | Yes (hidden when empty) |
| ISO-8601 timestamps | No | No | No | No | Yes |
| Subject groups (targeted) | No | No | No | No | Yes |
| Resource limiting | No | No | No | No | Yes (`-cores`, `-memory`) |
| Cross-drive outdir | N/A | N/A | N/A | Bug | Fixed |

## Analysis engine progression

### v0.1.0 → v0.3.0

v0.3.0 was not tested standalone against the ws1 artefacts — the v0.1.0 doc
covers both kali and ws1 runs with the full test matrix (A1-C9). v0.3.0 was the
baseline referenced in the main comparison.

### v0.3.0 → main

| Metric | v0.3.0 | main | Delta |
| --- | --- | --- | --- |
| Files detected | 65 | 82 | +17 (zip recursion) |
| Findings model | 86 flat (49H/15M/22L) | Activities + Indicators + Tactics | Restructured |
| Activity types | 14 | 17 | +FileUpload, +ReflectiveCodeLoading, +RuntimeCompilation |
| Indicator types | 4 (IPv4, Domain, URL, Email) | 13 | +Base64Blob, EncodedCommand, EntraLoginEndpoint, GUID, GraphEndpoint, JWT, KeyVaultEndpoint, OAuthScope, SHA256 |
| Tactics | 12 | 12 | Same |
| Watchlist hits | 7 | 7 | Same |
| New sections | — | targeted, exposure | Entity-focused analysis |
| New mitigations | ATT&CK only | ATT&CK + ATLAS (AML.M*) | Dual framework |

### main → v0.5.0

The analysis engine is **identical**. A byte-level diff of the text report shows
only 3 changed lines:

1. New empty "Intents" section header (ARTEX intent folder detection)
2. Footer listing additional output files (report.md, report.html, intents.json)

All finding counts, line references, activity classifications, indicator
extractions, and watchlist attributions are unchanged.

### v0.5.0 → v0.5.3

The analysis engine is still identical — same 82 files, 71 indicators, 17
activities, 12 tactics, 16 targeted, 46 exposed, 7 intel hits. Changes are in
presentation and tooling:

| Change | Detail |
| --- | --- |
| Cross-drive outdir fix (v0.5.1) | `within()` rewritten; nonexistent drives no longer false-positive |
| Parallelism (v0.5.1) | `-cores` and `-memory` flags for resource limiting |
| Linear report assembly (v0.5.2) | Performance fix for large evidence sets |
| Subject groups in Targeted (v0.5.3) | Entities grouped by type (Service, Task, Application, etc.) |
| AI-agent impact lowered (v0.5.3) | `[!]` medium → `[i]` informational; AML.M0020/M0022 follow |
| Empty sections hidden (v0.5.3) | Intents section omitted when empty |
| ISO-8601 timestamps (v0.5.3) | `20261116_092151` → `2026-11-16T09:21:51Z` |
| Overflow references (v0.5.3) | `and N more in the saved findings` |
| Duplicate evidence removed (v0.5.3) | Impact/remediation sections deduplicated |

Impacts changed from 12 (9H/2M/1L) to 13 (10H/1M/2L) because the AI-agent
impact was separated and reclassified. Text report grew ~17% (82 KB → 96 KB)
from longer timestamps, subject groups, and overflow references.

## Accuracy (ws1 artefacts, 11 files cross-checked)

These findings apply to both main and v0.5.0 (identical engine).

### What it gets right

- **File count**: 82/82 (100%) — exact match including zip contents
- **Line references**: 12/12 checked, all exact
- **Watchlist attributions**: 7/7 verified against file contents
- **Activity classifications**: 17/17 correct (ServiceCreation, AppCredentialAddition, RoleAssignment, MailboxAccess, KeyVaultSecretRead, ScheduledTaskCreation, FileDownload, etc.)
- **Targeted entities**: 16/16 accurate (users, emails, hosts, IPs)
- **SHA256 hashes**: Character-for-character match
- **Credential masking**: Correct toggle between masked/shown for all 4 secrets

### What it gets wrong

**IP false positives (4 of 14 IPv4 indicators)**

| False positive | Source | Root cause |
| --- | --- | --- |
| `0.77.2.0` | processes.csv FileVersion | Version string parsed as IP |
| `0.77.3.0` | processes.csv ProductVersion | Version string parsed as IP |
| `8.53.0.77` | processes.csv version field | Version string parsed as IP |
| `255.255.255.0` | ipconfig.txt | Subnet mask parsed as IP |

Root cause: IPv4 regex matches `\d+.\d+.\d+.\d+` without CSV column context
or reserved-range filtering.

**Username false positives (10 of 14 exposed usernames)**

Windows built-in groups and error fragments extracted as usernames by parsing
`DOMAIN\name` patterns without a built-in group allowlist: `The`, `This`,
`Local`, `NETWORK`, `NT`, `NTLM`, `Authenticated`, `Users`, `Administrators`,
`SYSTEM`. Only 4 of 14 are real users.

**Masking over-aggression (2 cases)**

Keyword `password` in a Key Vault secret name (`smtp-password`) and an email
search filter (`subject eq 'password reset'`) triggers masking where no
credential value is present.

### What it misses

| Gap | Detail | MITRE |
| --- | --- | --- |
| certutil encode/decode | Listed as tool, not flagged as activity | T1140 |
| Registry Run key persistence | Detected as Persistence tool, no named activity | T1547.001 |
| MAC address | Present in wmic output, no indicator type | — |
| Hostnames in ad-recon log | Attributed to ad-discovery.csv only | — |

## Known limitations (from v0.1.0 test matrix)

| ID | Issue | Severity | Still present in v0.5.0? |
| --- | --- | --- | --- |
| B6 | FQDN not extracted from CSV columns | Medium | Yes — same regex approach |
| B10 | No YAML/Ansible playbook analysis | Low | Yes — out of scope |
| K1 | No recursive folder support (v0.1.0) | High | **Fixed** — main/v0.5.0 recurse |
| K2 | Tactic assignment is command-name-based | Medium | Yes — acceptable for attack scripts |
| K6 | No Windows event log (.evtx) analysis | High | Yes — out of scope |

## Output format progression

| Format | v0.1.0 | main | v0.5.0 |
| --- | --- | --- | --- |
| stdout text | Yes | Yes | Yes |
| report.txt (via -outdir) | No | Yes | Yes |
| report.json | No | Yes | Yes |
| findings.json | No | Yes | Yes |
| trace.json | No | Yes | Yes |
| files.json | No | Yes | Yes |
| exposure.json | No | Yes | Yes |
| targeted.json | No | Yes | Yes |
| report.md | No | No | Yes |
| report.html | No | No | Yes |
| intents.json | No | No | Yes |

## HTML report (v0.5.0)

Self-contained 155 KB single file. Dark mode via `prefers-color-scheme`, CSP
(`default-src 'none'; style-src 'unsafe-inline'`), no external dependencies,
responsive layout, print stylesheet. All line references and data verified
identical to text output.

## Recommendation

v0.5.3 is the version to use. It has the same analysis engine as v0.5.0 and the
unreleased main build, fixes the cross-drive outdir bug, adds subject groups to
the Targeted section, normalises timestamps to ISO-8601, hides empty sections,
adds resource limiting for shared machines, and correctly classifies the
AI-agent detection as informational rather than medium.

The false positives (version-string IPs, Windows group usernames, over-aggressive
password masking) are cosmetic — they don't mask real findings and an analyst can
filter them. The false negatives (certutil T1140, registry persistence activity
naming) are minor gaps — the underlying tools and tactics are detected, just not
elevated to named activities. The MAC address and FQDN-from-CSV gaps are feature
requests.
