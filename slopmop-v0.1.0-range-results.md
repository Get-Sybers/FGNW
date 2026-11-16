# slopMop v0.1.0 — range test results

## 1. Environment

- **OS**: Proxmox VE 8.x (Debian 12 / Linux 7.0.14-8-pve), x86_64
- **Binary**: built from source (`git clone --branch v0.1.0 --depth 1`, commit 60b6e5c0)
- **Go toolchain**: 1.27.4 (fetched by the module), host Go 1.23.4
- **Range**: FGNW Ludus cyber range (range_id JB, second_octet 1, on beef-pi)
- **Artefacts copied from**: kali (10.1.99.99) via Ansible fetch, konoha-ws1 (10.1.10.21) via Ansible fetch

## 2. Runs tested

| Run | Scenario | Folder size |
| --- | --- | --- |
| kali | Linux attack chain: nmap recon, ldapsearch AD enum, certipy ADCS enum, impacket DCSync/psexec/wmiexec, exfil listener — across two subnets (Sand 10.1.20.0/24, Fire/Konoha 10.1.10.0/24). Plus STORM-0940 artefacts: password spray script, ARTEX-style structured agent log (.jsonl with 12 entries). 10 scripts + 33 output files. | 43 files |
| ws1 | Windows attack chain: AD discovery via PSRemoting, lateral movement to mail server, collection+zip, defense evasion (base64 obfuscation), exfiltration, LOLBin techniques (certutil, bitsadmin, wmic, schtasks, reg Run key, mshta, rundll32), .NET in-memory techniques (Add-Type C#, Reflection assembly load, download cradles, WMI/COM abuse). Plus STORM-0940 artefacts: Entra ID/OAuth abuse, Key Vault bulk reads, email collection via Graph, Graph API exfiltration to C2. 9 scripts + 62 output files. | 71 files |
| combined | Both runs in kali/ and ws1/ subdirectories under one folder. | 114 files |

## 3. Results table

| ID | Result | Notes |
| --- | --- | --- |
| **A1** | PASS | 7 rows, all 5 script rows match expected tools/tactics/transforms/outputs/intel. Steps 1–4 in correct order. |
| **A2** | PASS | finding list: STORM-0940 on 198.51.100.99 and .128; 4 tactic rows at correct severities; indicator types include GUID, GraphEndpoint, EntraLoginEndpoint, KeyVaultEndpoint, OAuthScope. report list: 6 files, 4 scripts, 2 outputs, 17 indicators, 4 tactics, 2 intel hits. campaign list: STORM-0940, 3 indicators. All match the brief. |
| **A3** | PASS | All 5 error cases return the expected exit code (1 or 2), error message on stderr, nothing on stdout. |
| **B1** | PASS | 84 files listed exactly once with `-r`. sha256 verified on a 10-file sample, 0 mismatches. Roles: 4 scripts (.sh), 78 outputs (.txt/.log/.csv/.bin), 2 other (.zip, correctly noted `binary`). |
| **B2** | PASS | Steps 1–4 ordered by timestamp embedded in filename (`20261116_HHMMSS`). Order matches execution order: nmap Sand → ldapsearch Sand → nmap Fire → ldapsearch Fire. |
| **B3** | PASS | 4/4 script tools correct: nmap (×2), ldapsearch (×2). No misses. |
| **B4** | PASS | All tools mapped to `Discovery`. No tool appeared in `tools` without contributing a tactic. |
| **B5** | PASS | 3/4 scripts linked to their outputs: step01→nmap-recon (via `-oN`), step02→ldapsearch-enum (via `>` redirect), step01b→nmap-recon-fire (via `-oN`). step02b produced no link because the script has no redirect — the output was captured by Ansible's task runner externally. This is correct behaviour. |
| **B6** | FAIL | See §5 below. kali: 30 indicators found. ws1: 13 indicators found. FQDNs in AD discovery CSV (konohagakure.fire.ninja) not extracted as Domain indicators — only the IP and GUID from that file were found. Domain names appear in LDAP referral URLs but not as standalone Domain findings. |
| **B7** | PASS | Watchlist expanded to 8 entries (SLOPMOP-KALI-ATTACKER + 7 STORM-0940 domains/IPs). Kali: 4 attributed findings (1 SLOPMOP-KALI-ATTACKER, 3 STORM-0940). WS1: 7 attributed findings (1 SLOPMOP-KALI-ATTACKER, 6 STORM-0940 on graph.microsoft.com, login.microsoftonline.com, vault.azure.net endpoints, 198.51.100.128). |
| **B8** | PASS | ARTEX-style `.jsonl` structured agent log (12 entries) deployed to kali. slopMop extracted 12 tools (nmap, ldapsearch, crackmapexec, impacket-secretsdump, impacket-psexec, Connect-MgGraph, Get-MgUser, Add-MgApplicationPassword, New-MgRoleManagementDirectoryRoleAssignment, Invoke-RestMethod, Get-AzKeyVaultSecret, curl), 5 tactics (Discovery, CredentialAccess, LateralMovement, Persistence, Exfiltration), and 12 indicators (GraphEndpoint, GUIDs, IPv4, URLs) from the `"command"` field in each JSON line. STORM-0940 attribution matched on 2 indicators (graph.microsoft.com, 198.51.100.128). |
| **B9** | PASS | kali `report list` (31 files, 4 scripts, 27 outputs, 30 indicators, 1 tactic, 1 intel hit) agrees with `file list` and `finding list` counts. Combined folder: `report list` returns all zeros because K1 (no `-r`). |
| **B10** | FAIL | See §6 below. |
| **C1** | PASS | 84 files hashed before and after a full set of commands. All sha256 identical, all mtimes identical, no files created in the artefact folder. |
| **C2** | NOT RUN | Proxmox host has no Sysmon/Procmon/auditd configured for this test. |
| **C3** | PASS | 33 ws1 output files have UTF-8 BOM (EF BB BF). slopMop extracted indicators from them (IPs, URLs, base64 blobs, encoded commands). No BOM-related failures. |
| **C4** | PASS | File containing ANSI escape sequences (`\x1b[31m`) listed cleanly as `test_escape.txt` with correct size and line count. No terminal corruption. |
| **C5** | PASS | 4 binary files (2 × .zip, 2 × .bin) listed with note `binary` and valid hashes. No crash, run continued. |
| **C6** | PASS | Folder 17 levels deep: listed with error naming the path, exit 1. Symlink to /etc/passwd: not followed, only the real file appeared. |
| **C7** | PASS (partial) | Empty folder: header printed, exit 0. Unreadable file: INCONCLUSIVE — running as root, cannot create a file root cannot read. |
| **C8** | PASS | 84 files, 760 KB total. `trace list -r`: 163 ms wall-clock, negligible memory. |
| **C9** | NOT RUN | Only Linux available on this host. |

## 4. Failures

### B6 — Domain indicators missed from AD output files

**Command**: `slopmop finding list --inputdir ws1 --intelfile range-watchlist.json -o json`

**Exit code**: 0

**Expected**: Domain indicators for `konohagakure.fire.ninja` (and subdomains like `JB-konoha-dc1.konohagakure.fire.ninja`) extracted from `ad-discovery.csv`.

**Actual**: Only IPv4 `10.1.10.10` and GUID `77afbe83-...` extracted from that file. The FQDN hostnames in CSV columns are not recognised as Domain indicators.

**Reproducer**: The file `ad-discovery.csv` contains:
```
"JB-KONOHA-DC1","JB-konoha-dc1.konohagakure.fire.ninja","Windows Server 2022 Standard Evaluation","10.1.10.10","77afbe83-321e-4b5e-8be6-8d19141ab256","True"
```

The domain `konohagakure.fire.ninja` appears six times in the CSV but is not found in `finding list`.

**Impact**: An analyst reading the slopMop output for a real incident would miss the AD domain names the attacker enumerated. For STORM-0940 scenarios (which target Entra ID tenants), the tenant domain is a critical indicator.

### B10 — Unsupported formats

**Ansible YAML playbooks (.yml)**: The attack chain was driven by Ansible. The `.yml` playbook files would be classified as `other` with no tool or tactic extraction. For AI-driven attacks using infrastructure-as-code frameworks (Ansible, Terraform, Pulumi), this is a coverage gap. Not tested directly because the playbooks were not placed in the artefact folder (they live in the git repo, not the capture directory).

**PowerShell via WinRM (no .ps1 on disk)**: 12 LOLBin and .NET tasks ran via Ansible's `win_shell` module. The commands executed as PowerShell but no `.ps1` files were written to disk. slopMop has no way to analyse these without the scripts. This is a limitation of the artefact collection method, not slopMop.

**CSV files**: Partial extraction — IPs and GUIDs found, but FQDNs not extracted (see B6).

## 5. Numbers

### Kali run (post-STORM-0940 artefacts)

| Metric | Value | Notes |
| --- | --- | --- |
| Files | 43 | 10 scripts, 33 outputs (was 31 files pre-STORM) |
| Tools in scripts | 19 | nmap, ldapsearch, certipy, impacket-*, crackmapexec, plus ARTEX JSONL tools |
| Tactics | 5 | Discovery, CredentialAccess, LateralMovement, Persistence, Exfiltration |
| IPv4 indicators | 20 | Subnet hosts + STORM-0940 C2 (198.51.100.x) |
| URL indicators | 8 | LDAP URIs, nmap.org, Graph API, C2 URLs |
| Domain indicators | 2 | graph.microsoft.com via ARTEX JSONL |
| GraphEndpoint | 2 | graph.microsoft.com from ARTEX structured log |
| GUID indicators | 4 | Entra role/app/tenant IDs from ARTEX log |
| Email indicators | 1 | admin@ from ARTEX log |
| MD5 indicators | 3 | NTLM hashes from DCSync output |
| Intel hits | 4 | 1 SLOPMOP-KALI-ATTACKER, 3 STORM-0940 |
| Findings | 43 | Up from ~15 pre-STORM |

### WS1 run (post-STORM-0940 artefacts)

| Metric | Value | Notes |
| --- | --- | --- |
| Files | 71 | 9 scripts, 62 outputs (was 53 files pre-STORM) |
| Tools in scripts | 80+ | AD recon, Defender kill, LOLBin, .NET, Entra, KeyVault, Graph, email cmdlets |
| Tactics | 8/8 | All MITRE tactics: Discovery, CredentialAccess, LateralMovement, Execution, Persistence, DefenseEvasion, Collection, Exfiltration |
| IPv4 indicators | 14 | Range hosts + STORM-0940 C2 |
| GraphEndpoint | 17 | graph.microsoft.com across 4 scripts + output logs |
| KeyVaultEndpoint | 3 | suna-keyvault, konoha-secrets, fire-prod-kv (.vault.azure.net) |
| EntraLoginEndpoint | 2 | login.microsoftonline.com |
| OAuthScope | 1 | graph.microsoft.com/.default |
| JWT | 1 | Fake bearer token (eyJhbG...) |
| Domain indicators | 10 | .onmicrosoft.com tenants, vault endpoints, blob storage |
| Email indicators | 3 | admin@, gaara.sabaku@, naruto.uzumaki@ |
| GUID indicators | 6 | Global Admin role, tenant, app, SP IDs |
| Base64Blob | 5 | Defense evasion + certutil evidence |
| EncodedCommand | 1 | schtasks base64 payload |
| Intel hits | 7 | 1 SLOPMOP-KALI-ATTACKER, 6 STORM-0940 |
| Findings | 79 | Up from ~13 pre-STORM |

## 6. Lists

### Tools with no tactic (B4)

None. Both `nmap` and `ldapsearch` mapped to `Discovery`.

### Missed indicators (B6)

| Indicator | Type | Source file | Notes |
| --- | --- | --- | --- |
| konohagakure.fire.ninja | Domain | ws1/ad-discovery.csv | FQDN in CSV column, 6 occurrences |
| sunagakure.wind.ninja | Domain | kali/ldapsearch-enum_*.txt | Embedded in LDAP referral URLs; extracted as URL, not Domain |
| konohagakure.fire.ninja | Domain | kali/ldapsearch-enum-fire_*.txt | Same pattern |

### False positives (B6)

None that would mislead an analyst. The nmap.org URLs and the GUID from RunspaceId are noise but clearly benign.

### Command field names in structured logs (B8)

ARTEX-style `.jsonl` file with `"command"` field. slopMop recognised the `command` field name from its `command_fields` list in `formats.json` and extracted all 12 commands. Tools detected: nmap, ldapsearch, crackmapexec, impacket-secretsdump, impacket-psexec, Connect-MgGraph, Get-MgUser, Add-MgApplicationPassword, New-MgRoleManagementDirectoryRoleAssignment, Invoke-RestMethod, Get-AzKeyVaultSecret, curl. Each command mapped to the correct tactic.

### Unsupported languages and formats (B10)

| Format | Role assigned | Extracted |
| --- | --- | --- |
| YAML (.yml) | other | Nothing |
| CSV (.csv) | output | IPs, GUIDs — not FQDNs |
| ZIP (.zip) | other (binary) | Nothing (expected) |
| BIN (.bin) | other (binary) | Nothing (expected) |
| PowerShell via WinRM | N/A (no file) | N/A |

## 7. Impact of K1–K7 on our artefacts

| ID | Impact |
| --- | --- |
| K1 | **High**. Our artefacts span two hosts (kali/, ws1/) in subdirectories and ws1 has collection_*/ subdirectories. `finding list` and `report list` returned zero results on the combined folder. We had to run them per-subfolder, and the collection subdirectory files (systeminfo.txt, ipconfig.txt, processes.csv, etc.) were invisible to finding/report. |
| K2 | **Medium**. STORM-0940 scripts now exercise cloud cmdlets (Connect-MgGraph, Get-AzKeyVaultSecret, Invoke-RestMethod, etc.) and slopMop maps them to multiple tactics. The tactic assignment is command-name-based (K2), so `Invoke-RestMethod` → Exfiltration even when used for data retrieval. Acceptable for STORM-0940 where the intent is exfiltration, but would over-classify defensive scripts. |
| K3 | **None**. Our watchlist used exact IPs (10.1.99.99). No CIDR ranges in the watchlist. |
| K4 | **None**. We used `-o json` for comparisons, which avoids the display quirk. |
| K5 | **None**. No quoted command paths in our scripts. |
| K6 | **High**. The range produced Windows event logs (Defender blocks, PowerShell ScriptBlock logging, Sysmon) from the LOLBin and .NET tasks, plus sign-in logs from PSRemoting lateral movement. slopMop cannot analyse any of these. For our use case (testing forensic detection of LOLBin and .NET in-memory attacks), the event logs are the primary evidence and slopMop sees none of it. |
| K7 | **Low**. We built from source on Linux without issue. |

## 8. Anything else

**Ansible-driven attacks leave no scripts on disk.** When an attacker (or red team) uses Ansible, Terraform, or similar IaC tools, the commands execute remotely via WinRM/SSH but no script files are written to the target. slopMop's design assumes the agent left scripts behind. For our Windows LOLBin + .NET run (12 techniques), slopMop saw the output logs but had zero scripts to trace — no tools, no tactics, no step ordering. An analyst would see only the raw indicator extraction from output files.

**Output files from LOLBin techniques contain tool names but slopMop does not extract tools from outputs.** The `lol-wmic_*.log` files contain `wmic os get`, `wmic process`, `wmic startup`. The `lol-schtasks_*.log` files contain `schtasks /create`, `schtasks /query`. The `net-addtype_*.log` files describe `Add-Type -TypeDefinition`. slopMop extracts indicators (IPs, URLs, base64) from these files but not tool invocations — tool extraction is script-only. This means the LOLBin and .NET evidence generates no MITRE tactic findings even though the techniques are clearly recorded in the output.

**UTF-8 BOM handled correctly.** All 33 ws1 output files written by PowerShell's `Out-File` had UTF-8 BOM (EF BB BF). slopMop handled them without error.

**DCSync NTLM hashes correctly identified as MD5 indicators.** The impacket-secretsdump output includes `Administrator:500:aad3b435b51404eeaad3b435b51404ee:8846f7eaee8fb117ad06bdd830b7586c:::` and slopMop extracted all three hash components (2 MD5, 1 SHA256-prefix). An analyst could use these for credential monitoring.

**Binary file handling is clean.** The .bin exfiltration captures and .zip collection archives were listed with their hashes and sizes, with note `binary`, no crash.

## 9. STORM-0940 coverage (slopMop#7)

Six gaps identified in the original test data were filled with `slopmop-storm0940-artefacts.yml`:

| Gap | Playbook step | Host | Result |
| --- | --- | --- | --- |
| Cloud identity / Entra ID | step11 entra-oauth.ps1 | ws1 | 10 indicators (GraphEndpoint, EntraLoginEndpoint, OAuthScope, GUIDs, JWT). Tactics: Exfiltration, Persistence. |
| ARTEX structured agent logs | step12 artex-logs.sh | kali | 12-entry `.jsonl` → 12 tools, 5 tactics, 12 indicators. B8 now PASS. |
| Password spray | step11 password-spray.sh | kali | crackmapexec not installed on kali (command not found), but script text parsed: tool=crackmapexec, tactic=CredentialAccess. |
| Key Vault bulk reads | step12 keyvault-reads.ps1 | ws1 | 3 KeyVaultEndpoint indicators (suna-keyvault, konoha-secrets, fire-prod-kv), 6 total. Tactics: CredentialAccess, LateralMovement. |
| Email / mailbox collection | step13 email-collection.ps1 | ws1 | 3 Email indicators, Graph message URLs, Search-Mailbox cmdlet. Tactics: Collection, Exfiltration, LateralMovement. |
| Graph API exfiltration | step14 graph-exfil.ps1 | ws1 | 7 Graph endpoints, C2 URL, azcopy reference. Tactic: Exfiltration. |

**Watchlist attribution**: expanded from 1 entry (SLOPMOP-KALI-ATTACKER) to 8 entries (+ 2 STORM-0940 IPs, 5 STORM-0940 domains). Kali: 4 attributed findings. WS1: 7 attributed findings.

**Indicator type coverage**: all indicator types in slopMop's `indicators.json` that apply to STORM-0940 are now exercised: GraphEndpoint, EntraLoginEndpoint, KeyVaultEndpoint, OAuthScope, JWT, Email, GUID, IPv4, URL, Domain, Base64Blob, EncodedCommand.

**Tactic coverage**: WS1 now hits all 8 MITRE tactics. Kali hits 5/8. Combined: 8/8.
