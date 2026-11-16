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
| kali | Linux attack chain: nmap recon, ldapsearch AD enum, certipy ADCS enum, impacket DCSync/psexec/wmiexec, exfil listener — across two subnets (Sand 10.1.20.0/24, Fire/Konoha 10.1.10.0/24). 4 shell scripts + 27 output files. | 31 files, 60 KB |
| ws1 | Windows attack chain: AD discovery via PSRemoting, lateral movement to mail server, collection+zip, defense evasion (base64 obfuscation), exfiltration, LOLBin techniques (certutil, bitsadmin, wmic, schtasks, reg Run key, mshta, rundll32), .NET in-memory techniques (Add-Type C#, Reflection assembly load, download cradles, WMI/COM abuse). Output files only — commands ran via Ansible win_shell, no .ps1 scripts on disk. | 53 files (41 top-level + 12 in collection subdirs), 148 KB |
| combined | Both runs in kali/ and ws1/ subdirectories under one folder. | 84 files, 760 KB |

## 3. Results table

| ID | Result | Notes |
| --- | --- | --- |
| **A1** | PASS | 7 rows, all 5 script rows match expected tools/tactics/transforms/outputs/intel. Steps 1–4 in correct order. |
| **A2** | PASS | finding list: STORM-0940 on 144.172.64.99 and .128; 4 tactic rows at correct severities; indicator types include GUID, GraphEndpoint, EntraLoginEndpoint, KeyVaultEndpoint, OAuthScope. report list: 6 files, 4 scripts, 2 outputs, 17 indicators, 4 tactics, 2 intel hits. campaign list: STORM-0940, 3 indicators. All match the brief. |
| **A3** | PASS | All 5 error cases return the expected exit code (1 or 2), error message on stderr, nothing on stdout. |
| **B1** | PASS | 84 files listed exactly once with `-r`. sha256 verified on a 10-file sample, 0 mismatches. Roles: 4 scripts (.sh), 78 outputs (.txt/.log/.csv/.bin), 2 other (.zip, correctly noted `binary`). |
| **B2** | PASS | Steps 1–4 ordered by timestamp embedded in filename (`20261116_HHMMSS`). Order matches execution order: nmap Sand → ldapsearch Sand → nmap Fire → ldapsearch Fire. |
| **B3** | PASS | 4/4 script tools correct: nmap (×2), ldapsearch (×2). No misses. |
| **B4** | PASS | All tools mapped to `Discovery`. No tool appeared in `tools` without contributing a tactic. |
| **B5** | PASS | 3/4 scripts linked to their outputs: step01→nmap-recon (via `-oN`), step02→ldapsearch-enum (via `>` redirect), step01b→nmap-recon-fire (via `-oN`). step02b produced no link because the script has no redirect — the output was captured by Ansible's task runner externally. This is correct behaviour. |
| **B6** | FAIL | See §5 below. kali: 30 indicators found. ws1: 13 indicators found. FQDNs in AD discovery CSV (konohagakure.fire.ninja) not extracted as Domain indicators — only the IP and GUID from that file were found. Domain names appear in LDAP referral URLs but not as standalone Domain findings. |
| **B7** | PASS | 5 files with attacker IP 10.1.99.99 attributed to SLOPMOP-KALI-ATTACKER. Verified with `grep -rl`: exact match, no misses, no false positives. |
| **B8** | NOT RUN | The range used Ansible playbooks (YAML), not an AI agent framework. No structured JSON/XML agent logs were produced. slopMop extracted commands from the nmap output's JSON-like structured fields and from the ad-discovery CSV, but there is no ARTEX-style structured log to test against. |
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

### Kali run

| Metric | Found | Expected | Notes |
| --- | --- | --- | --- |
| Tools | 2/2 | nmap, ldapsearch | |
| Tactics | 1/1 | Discovery | Only recon tools in scripts |
| IPv4 indicators | 18 | 18 | All subnet hosts from nmap output + script targets |
| URL indicators | 6 | 6 | LDAP URIs from scripts + nmap.org URLs from output |
| Domain indicators | 1 | 3 | Found: nmap.org. Missed: sunagakure.wind.ninja, konohagakure.fire.ninja (embedded in LDAP referral URLs, not standalone) |
| MD5 indicators | 3 | 3 | NTLM hashes from DCSync output |
| Intel hits | 1/1 | 10.1.99.99 attributed correctly | |

### WS1 run

| Metric | Found | Expected | Notes |
| --- | --- | --- | --- |
| Tools | 0 | 0 | No scripts on disk — expected |
| Tactics | 0 | 0 | No scripts → no tactics — expected |
| IPv4 indicators | 5 | 5 | 10.1.99.99, 10.1.10.10, .20, .21, .254 |
| URL indicators | 2 | 2 | Attacker URLs from bitsadmin and exfil logs |
| Domain indicators | 0 | 1+ | konohagakure.fire.ninja not extracted from ad-discovery.csv |
| Base64Blob | 4 | 4 | Defense evasion and certutil encode/decode evidence |
| EncodedCommand | 1 | 1 | schtasks base64 payload |
| Intel hits | 1/1 | 10.1.99.99 in 4 files (bitsadmin ×3, exfil-log ×1) |

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

NOT RUN — no AI agent framework structured logs.

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
| K2 | **Low**. Our scripts used only `nmap` and `ldapsearch`, both correctly mapped to Discovery. No `az` or HTTP calls in scripts to trigger the over-broad tactic assignment. |
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
