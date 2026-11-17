# slopMop main — report accuracy cross-check

Cross-checked the slopMop main report output against actual file contents on
konoha-ws1. 11 files read line-by-line from disk and compared to report claims.

## Verdict

Line references, watchlist attributions, activity classifications, and file
counts are accurate. The exposure section has significant username false
positives and the indicator section has a few IP false positives from version
strings.

---

## True positives (confirmed accurate)

| Claim | Files checked | Result |
| --- | --- | --- |
| File count: 82 (9 scripts + 70 outputs + 3 zip) | Full `Get-ChildItem -Recurse` listing | Exact match |
| Line-number references | 12 references across 6 files | All exact |
| Watchlist: SLOPMOP-KALI-ATTACKER on 10.1.99.99 | exfil-log.txt, lol-bitsadmin, collect-exfil, lolbin-chain | All contain 10.1.99.99 |
| Watchlist: STORM-0940 on graph/login/keyvault domains | entra-oauth, keyvault-reads, email-collection, graph-exfil | All contain the claimed domains |
| ServiceCreation at defender-kill:9 | defender-kill_20261116_161704.log | `sc.exe create KdySysDrv` exactly at line 9 |
| SHA256 hashes | defender-kill_20261116_161704.log | Both hashes match character-for-character |
| AppCredentialAddition at entra-oauth:11-14 | entra-oauth_20261116_163730.log | Add-MgApplicationPassword / Add-MgServicePrincipalPassword at exact lines |
| RoleAssignment at entra-oauth:15,18 | entra-oauth_20261116_163730.log | New-MgRoleManagementDirectoryRoleAssignment at exact lines |
| MailboxAccess emails (3 users) | email-collection_20261116_163741.log | admin@, gaara.sabaku@, naruto.uzumaki@ all present at claimed lines |
| KeyVaultSecretRead (3 vaults, 7 secrets each) | keyvault-reads_20261116_163735.log | All vault URIs and secret names present |
| ScheduledTaskCreation at lolbin-exec:39 | 20261116_210800_step08_lolbin-exec.ps1 | `schtasks /create` exactly at line 39 |
| FileDownload (bitsadmin) at lolbin-exec:22 | 20261116_210800_step08_lolbin-exec.ps1 | `bitsadmin /addfile` exactly at line 22 |
| Targeted: Administrator discovered from psremoting:2 | psremoting-lateral.txt | `User: fire\administrator` at line 2 |
| Targeted: 10.1.10.10 discovered at ad-recon:13 | 20261116_210600_step06_ad-recon.ps1 | `Invoke-Command -ComputerName 10.1.10.10` at line 13 |
| Credential masking | `-secrets masked` vs `-secrets shown` | `password` ↔ `pa*****d (8 chars)`, JWT and secret correctly toggled |
| Collection subdirs correctly parsed | 3 collection_* folders | Third folder has 5 files (no localusers.csv), report shows 5 — correct |

## False positives

### IP indicators from software version strings

| Reported IP | Actual source | Real value |
| --- | --- | --- |
| `0.77.2.0` | processes.csv FileVersion field | Velociraptor (digger.exe) version 0.77.2.0 |
| `0.77.3.0` | processes.csv ProductVersion field | Same binary, different version column |
| `8.53.0.77` | processes.csv version field | Another product version string |
| `255.255.255.0` | ipconfig.txt | Subnet mask, not an address |

These are version numbers and a subnet mask parsed as IPv4 indicators. The
regex catches any `\d+\.\d+\.\d+\.\d+` pattern without context-aware filtering.

### Exposure: username false positives

10 of 14 "exposed usernames" are Windows built-in group names or error message
fragments, not actual user accounts:

| Reported username | Actual source text | Why it's a false positive |
| --- | --- | --- |
| `The` | `The term 'Connect-AzAccount' is not recognized...` | First word of an error message |
| `This` | `NT AUTHORITY\This Organization` | Windows group name fragment |
| `Local` | `NT AUTHORITY\Local account` | Windows group name fragment |
| `NETWORK` | `NT AUTHORITY\NETWORK` | Windows pseudo-group |
| `NT` | `NT AUTHORITY\...` | Windows pseudo-domain prefix |
| `NTLM` | `NT AUTHORITY\NTLM Authentication` | Authentication protocol name |
| `Authenticated` | `NT AUTHORITY\Authenticated Users` | Windows group name |
| `Users` | `BUILTIN\Users` | Windows group name |
| `Administrators` | `BUILTIN\Administrators` | Windows group name |
| `SYSTEM` | schtasks running as SYSTEM | Built-in system account (debatable) |

The parser extracts the token after `\` in `DOMAIN\name` patterns but doesn't
filter against known Windows built-in groups or pseudo-domains. The word "The"
comes from an error message where `\T` appears in a file path.

Legitimate exposed usernames (4 of 14): `administrator`, `localuser`,
`naruto.uzumaki`, `Administrator`.

### Masking over-aggression

- `smtp-password` (a Key Vault **secret name**, not a password value) is masked
  as `smtp-pa*****d (8 chars)` — the word "password" inside the name triggers
  masking.
- `subject eq 'password reset'` in an email search URL is masked as
  `pa*****d (8 chars) reset` — the word "password" in a filter predicate is not
  a credential.

The masking logic matches the literal word `password` anywhere in a line without
distinguishing between a credential value and an incidental occurrence of the
word.

## Potential false negatives / gaps

### certutil T1140 not flagged as an activity

The lolbin-exec script runs `certutil -encode` / `certutil -decode` (ATT&CK
T1140 Deobfuscate/Decode Files). slopMop lists `certutil` as a detected tool
and correctly identifies Base64Blobs in the certutil output, but T1140 does not
appear as an activity or tactic. The script's own comment says
`# certutil encode/decode (T1140)`.

### Registry Run key persistence not a named activity

The lolbin-exec script creates and removes a Run key
(`HKCU:\...\CurrentVersion\Run`) via `Set-ItemProperty`. The report lists
`set-itemproperty` as a Persistence tool and maps the Persistence tactic, but
there is no named activity like "RegistryPersistence" comparable to
`ScheduledTaskCreation` or `ServiceCreation`. The persistence is detected at the
tool/tactic level but not at the activity level.

### MAC address not captured

A MAC address appears in wmic nicconfig output
(lol-wmic_20261116_152712.log:9) but is not extracted as an indicator. No MAC
address indicator type exists.

### Hostnames in ad-recon log not attributed

ad-recon_20261116_161658.log lists 6 AD computer names (JB-KONOHA-DC1 through
JB-KONOHA-WS5) plus JB-KONOHA-MAIL. The report's exposure section correctly
identifies these as devices but only attributes them to ad-discovery.csv and
ad-computers.csv — not to the ad-recon log. The timeline shows ad-recon with no
indicators. The devices are found elsewhere, so the gap is in attribution rather
than detection.

## Summary

| Category | Count | Accuracy |
| --- | --- | --- |
| File count | 82 | 100% — exact match |
| Line references checked | 12 | 100% — all exact |
| Watchlist attributions | 7 | 100% — all verified |
| Activity classifications | 9 types checked | 100% — all correct |
| IP indicators | 14 reported | 10 real IPs + 4 false positives (version strings + subnet mask) |
| Exposed usernames | 14 reported | 4 real + 10 false positives (group names / error fragments) |
| Targeted entities | 16 reported | All verified accurate |
| Credential masking | 4 secrets | Correct masking, 2 cases of over-aggressive matching |
| Activities: false negatives | 2 noted | certutil T1140, registry persistence — detected as tools but not as named activities |
