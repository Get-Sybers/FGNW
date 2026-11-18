# slopMop main (unreleased) — range test results

## 1. Environment

- **Binary**: built from source (`git clone` main branch, commit 73c1784)
- **Go toolchain**: 1.27.4 (fetched by the module), host Go 1.23.4
- **Build**: `GOOS=windows GOARCH=amd64 go build -o bin/slopmop-main-windows-amd64.exe ./cmd/slopmop`
- **Binary size**: 6.3 MB (deployed as `C:\slopmop-main.exe`)
- **Range**: FGNW Ludus cyber range (range_id JB, second_octet 1)
- **Host**: konoha-ws1 (10.1.10.21), Windows Server 2019
- **Artefact folder**: `C:\slopmop-capture` — 65 items (9 scripts, 53+ outputs, 3 zips)
- **Watchlist**: `C:\slopmop-watchlist.json` — 8 entries (SLOPMOP-KALI-ATTACKER + STORM-0940)

## 2. CLI redesign (main vs v0.3.0)

| Aspect | v0.3.0 | main |
| --- | --- | --- |
| Pattern | `slopmop NOUN VERB [selectors] [--params]` | `slopmop -inputdir <folder> VERB [section ...] [options]` |
| Verbs | `list` on each noun (file, trace, finding, report, campaign) | Single verb: `report` |
| Output to disk | Redirect stdout (`> file.txt`) | Built-in `-outdir <folder>` saves 7 files |
| Credential masking | None | `-secrets masked\|shown` (masked by default) |
| Intel format | JSON watchlist only | JSON watchlist + STIX 2.1 |
| Section selection | Separate nouns: `finding list`, `report list` | `report [section ...]` with named sections |

## 3. Report sections (main)

| Section | Description |
| --- | --- |
| `summary` | Counts: files, indicators, activities, tactics, targeted, exposed, intel hits |
| `timeline` | Each file in chronological order with step number, role, indicators, watchlist hits |
| `findings` | Activities, indicators, tactics — most severe first, with ATT&CK + ATLAS IDs |
| `files` | Files holding a high-severity finding |
| `targeted` | Hardcoded usernames, emails, hostnames, IPs in scripts — with prior/discovered classification |
| `exposure` | Passwords, usernames, emails, devices, IPs — with collected/used classification |
| `impact` | What findings mean, with targets and evidence lines |
| `remediation` | What to do, most urgent first, with targets and evidence |
| `mitigation` | MITRE ATT&CK + ATLAS mitigations for techniques found |

Sections **targeted** and **exposure** are new in main (not present in v0.3.0).

## 4. Summary comparison

| Metric | v0.3.0 | main | Notes |
| --- | --- | --- | --- |
| Files detected | 65 (9 scripts, 53 outputs, 3 other) | 82 (9 scripts, 70 outputs, 3 other) | +17 outputs — main recurses into collection zips |
| Findings (severity) | 86 (49 high / 15 med / 22 low) | n/a — restructured as activities+indicators+tactics | Findings split into typed categories |
| Activities | 14 types | 17 types | +FileUpload, +ReflectiveCodeLoading, +RuntimeCompilation |
| Tactics | 12 | 12 | Same coverage |
| Watchlist hits | 7 | 7 | Same: SLOPMOP-KALI-ATTACKER + STORM-0940 |
| Indicators | Not broken out | 71 (across 13 indicator types) | New granularity |
| Targeted entities | n/a | 16 (1 user, 3 emails, 8 hosts, 4 IPs) | New section |
| Exposed entities | n/a | 46 (4 secrets, 14 users, 3 emails, 13 devices, 12 IPs) | New section |
| Impacts | Present | 13 (10 high / 2 med / 1 low) | Restructured with targets and basis |

## 5. New indicator types (main)

v0.3.0 tracked IPv4, Domain, URL, Email. Main adds:

- **Base64Blob** (5) — encoded payloads
- **EncodedCommand** (1) — PowerShell encoded commands
- **EntraLoginEndpoint** (2) — Entra ID/OAuth token endpoints
- **GUID** (6) — application and tenant IDs
- **GraphEndpoint** (17) — Microsoft Graph API calls
- **JWT** (1) — JSON Web Tokens (masked by default)
- **KeyVaultEndpoint** (3) — Azure Key Vault URIs
- **OAuthScope** (1) — OAuth permission scopes
- **SHA256** (2) — file hashes (defender-kill driver)

## 6. New activity types (main)

| Activity | Tactic | ATT&CK | New? |
| --- | --- | --- | --- |
| FileUpload | Exfiltration | T1048, AML.T0025 | Yes |
| ReflectiveCodeLoading | Stealth | T1620 | Yes |
| RuntimeCompilation | Stealth | T1027.004, AML.T0123 | Yes |

## 7. Credential masking test

| Mode | Password field | JWT field | Secret field |
| --- | --- | --- | --- |
| `-secrets masked` (default) | `pa*****d (8 chars)` | `ey********e (46 chars)` | `wJ********n (41 chars)` |
| `-secrets shown` | `password` | `eyJhbGciOiJSUzI1NiJ9.eyJhdWQiOiJncmFwaCJ9.fake` | `wJk8Q~fake-secret-for-artefact-generation` |

Masking preserves first 2 and last 1 character with length in parentheses.

## 8. Disk output test (`-outdir`)

Command: `slopmop-main.exe -inputdir "C:\slopmop-capture" report -intelfile "C:\slopmop-watchlist.json" -outdir "C:\slopmop-main-report"`

| File | Size | Content |
| --- | --- | --- |
| report.txt | 82,071 | Full human-readable report (all sections) |
| report.json | 135,349 | Complete structured report |
| findings.json | 53,561 | Activities, indicators, tactics |
| trace.json | 28,087 | Timeline/trace data |
| files.json | 23,531 | File metadata and classifications |
| exposure.json | 13,243 | Exposed credentials, accounts, devices, IPs |
| targeted.json | 6,437 | Hardcoded targets in scripts |

Total: ~342 KB across 7 files.

## 9. ATLAS coverage (new in main)

Main maps findings to both ATT&CK and ATLAS technique IDs:

- AML.T0012 (Valid Accounts) on TokenRequest
- AML.T0025 (Exfiltration) on FileUpload
- AML.T0050 (Command and Script Execution) on ProcessStart
- AML.T0072 (Resource Hijacking) on FileDownload
- AML.T0075 (Discovery) on GraphDirectoryEnumeration, DirectorySearch, KeyVaultKeyEnumeration
- AML.T0102 (AI Agent Abuse) on "Commands generated by an AI agent"
- AML.T0123 (Runtime Compilation) on RuntimeCompilation
- AML.T0126 (Collection) on MailboxAccess

Mitigation section includes AML.M* entries: M0005, M0011, M0019, M0020, M0022, M0039, M0043.

## 10. Notable improvements

1. **AI agent detection**: Main flags "Commands generated by an AI agent" as a medium-severity impact, noting that generated commands vary between runs and evade signature-based detection. Suggests AML.M0020 (Generative AI Guardrails) and AML.M0022 (Model Alignment) as mitigations.
2. **Targeted vs Exposure split**: Targeted shows what the attacker hardcoded (prior knowledge vs discovered). Exposure shows what was collected or leaked from outputs.
3. **Transform detection**: Scripts analysed for Base64Encode, Base64Decode, GZip, Stream, TextEncoding, SecureString transforms.
4. **Tool extraction**: Each script's tools/cmdlets listed in the timeline (e.g., `invoke-command`, `certutil`, `bitsadmin`).
5. **Step numbering**: Timeline assigns step numbers parsed from script filenames (step06..step14).
6. **Impact targets**: Each impact lists specific affected resources (vaults, tenants, mailboxes, services, tasks).
7. **Remediation ordering**: Prioritized from most urgent (revoke sessions) to least (follow enumerated resources).

## 11. Regressions / issues

None observed. All v0.3.0 capabilities are preserved or improved. The CLI change is breaking but the tool prints migration hints (`next:` lines in help output).
