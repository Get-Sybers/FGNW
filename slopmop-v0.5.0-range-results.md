# slopMop v0.5.0 — range test results + accuracy cross-check

## 1. Environment

- **Binary**: `slopmop-v0.5.0-windows-amd64.exe` (8.1 MB, from GitHub release)
- **Deployed as**: `C:\slopmop-v5.exe` on konoha-ws1
- **Range**: FGNW Ludus cyber range (range_id JB, second_octet 1)
- **Host**: konoha-ws1 (10.1.10.21), Windows Server 2019
- **Artefact folder**: `C:\slopmop-capture` — 82 files (9 scripts, 70 outputs, 3 zips)
- **Watchlist**: `C:\slopmop-watchlist.json` — 8 entries (SLOPMOP-KALI-ATTACKER + STORM-0940)

## 2. What's new in v0.5.0 vs main (unreleased)

The analysis engine is identical — a byte-level diff of the text report shows only
2 changes:

1. **New `intents` section**: "each ARTEX intent, by its run folder i\<number\>:
   its period and its ATT&CK and ATLAS techniques". Empty (`none`) for artefacts
   without ARTEX structured intent folders.
2. **3 new output files**: `report.html` (155 KB), `report.md` (84 KB),
   `intents.json` (empty `[]`).

| Output file | main | v0.5.0 | Change |
| --- | --- | --- | --- |
| report.txt | 82,071 | 82,193 | +122 bytes (intents section header) |
| report.md | — | 84,625 | New |
| report.html | — | 155,879 | New |
| intents.json | — | 3 | New (empty) |
| report.json | 135,349 | 135,349 | Identical |
| findings.json | 53,561 | 53,561 | Identical |
| files.json | 23,531 | 23,531 | Identical |
| trace.json | 28,087 | 29,727 | +1,640 (likely intents metadata) |
| exposure.json | 13,243 | 13,243 | Identical |
| targeted.json | 6,437 | 6,437 | Identical |

All finding counts, line references, and analysis numbers are unchanged from
main. Every accuracy finding from the main cross-check applies equally to
v0.5.0.

## 3. HTML report

Self-contained single-file HTML with:

- Light/dark mode via `prefers-color-scheme` media query
- CSS custom properties for theming (`--high`, `--medium`, `--low`, `--clear`)
- Content Security Policy: `default-src 'none'; style-src 'unsafe-inline'`
- No external dependencies (all CSS inline)
- Responsive layout (`max-width: 1100px`)
- Print stylesheet (`@media print`)
- Semantic HTML: tables for data, `<nav>` for section links
- Monospace font for file references and code values
- HTML entities properly escaped (`&#34;`, `&gt;`, `&#43;`)

All line references verified present in HTML output — same data as text report.

## 4. Markdown report

Standard GitHub-flavored Markdown with:

- Backtick code spans for file references and indicator values
- Markdown tables for tabular data
- Bold labels for key/value pairs
- Escaped brackets for severity markers

All line references verified present in MD output — same data as text report.

## 5. Accuracy cross-check results

Methodology: 11 artefact files read line-by-line from konoha-ws1 with
PowerShell `Get-Content` and line numbers, then compared to report claims.

### Confirmed accurate

| Claim | Verified |
| --- | --- |
| File count: 82 (9 scripts + 70 outputs + 3 zip) | Exact match against `Get-ChildItem -Recurse` |
| 12 specific line-number references | All exact against numbered file contents |
| 7 watchlist attributions | All verified: 10.1.99.99 in exfil/bitsadmin/collect-exfil/lolbin-chain; graph.microsoft.com, login.microsoftonline.com, keyvault domains, 198.51.100.128 in STORM-0940 files |
| ServiceCreation: `sc.exe create KdySysDrv` at defender-kill:9 | Exact match |
| SHA256 hashes (2) in defender-kill | Character-for-character match |
| AppCredentialAddition at entra-oauth:11-14 | All 4 lines exact |
| RoleAssignment at entra-oauth:15,18 | Both lines exact |
| MailboxAccess: 3 email addresses at claimed lines | All present and correct |
| KeyVaultSecretRead: 3 vaults, 7 secrets each | All vault URIs and secret names verified |
| ScheduledTaskCreation at lolbin-exec:39 | Exact match |
| FileDownload (bitsadmin) at lolbin-exec:22 | Exact match |
| Targeted: Administrator discovered via psremoting:2 | `User: fire\administrator` at line 2 |
| Credential masking: `password` ↔ `pa*****d (8 chars)` | Correct toggle with `-secrets shown` |
| 3rd collection folder has 5 files (no localusers.csv) | Report shows 5 — correct |

### False positives

**IP indicators from software version strings (4 of 14 IPv4)**

| Reported IP | Actual value | Source field |
| --- | --- | --- |
| `0.77.2.0` | Velociraptor digger.exe FileVersion | processes.csv column 11 |
| `0.77.3.0` | Velociraptor digger.exe ProductVersion | processes.csv column 12 |
| `8.53.0.77` | Another product version string | processes.csv |
| `255.255.255.0` | Subnet mask | ipconfig.txt |

The IPv4 regex matches any `\d+.\d+.\d+.\d+` without CSV column context.

**Username false positives (10 of 14 exposed usernames)**

| Reported | Actual source | Classification |
| --- | --- | --- |
| `The` | Error: `The term 'Connect-AzAccount'...` | Error message fragment |
| `This` | `NT AUTHORITY\This Organization` | Windows group |
| `Local` | `NT AUTHORITY\Local account` | Windows group |
| `NETWORK` | `NT AUTHORITY\NETWORK` | Windows pseudo-group |
| `NT` | `NT AUTHORITY\...` prefix | Windows pseudo-domain |
| `NTLM` | `NT AUTHORITY\NTLM Authentication` | Auth protocol |
| `Authenticated` | `NT AUTHORITY\Authenticated Users` | Windows group |
| `Users` | `BUILTIN\Users` | Windows group |
| `Administrators` | `BUILTIN\Administrators` | Windows group |
| `SYSTEM` | schtasks running as SYSTEM | Built-in system account |

Legitimate usernames (4): `administrator`, `localuser`, `naruto.uzumaki`,
`Administrator`.

**Masking over-aggression (2 cases)**

- `smtp-password` (Key Vault secret **name**) → `smtp-pa*****d (8 chars)` —
  the word "password" in the name triggers masking.
- `subject eq 'password reset'` (email search filter) → masked — the word
  "password" in a predicate is not a credential value.

### False negatives / gaps

| Gap | Detail |
| --- | --- |
| certutil T1140 not flagged | `certutil -encode/-decode` listed as a tool but T1140 is not an activity or tactic |
| Registry Run key not a named activity | `Set-ItemProperty` on `CurrentVersion\Run` detected as Persistence tool, no "RegistryPersistence" activity |
| MAC address not captured | A MAC address in wmic nicconfig output — no MAC indicator type |
| Hostnames in ad-recon log | 6 AD computer names present but attributed only to ad-discovery.csv, not to ad-recon log |

### Summary table

| Category | Count | Accurate | False positive | False negative |
| --- | --- | --- | --- | --- |
| File count | 82 | 82 (100%) | 0 | 0 |
| Line references | 12 checked | 12 (100%) | 0 | 0 |
| Watchlist hits | 7 | 7 (100%) | 0 | 0 |
| Activities | 17 | 17 (100%) | 0 | 2 not flagged (T1140, T1547.001) |
| IP indicators | 14 | 10 (71%) | 4 (version/mask) | 0 |
| Exposed usernames | 14 | 4 (29%) | 10 (groups/errors) | 0 |
| Credential masking | 4 secrets | 4 (100%) | 2 over-masks | 0 |
| Targeted entities | 16 | 16 (100%) | 0 | 0 |

## 6. Commands used

```powershell
# Deploy
# (Ansible win_copy from proxmox host)

# Full report with watchlist and disk output
C:\slopmop-v5.exe -inputdir "C:\slopmop-capture" report -intelfile "C:\slopmop-watchlist.json" -outdir "C:\slopmop-v5-report"

# Exposure with secrets shown
C:\slopmop-v5.exe -inputdir "C:\slopmop-capture" report exposure -secrets shown

# Section help
C:\slopmop-v5.exe -inputdir "C:\slopmop-capture" report --help
```
