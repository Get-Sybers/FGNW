Arms the campaign's attacker workstation (Zetsu's `akatsuki-ws2`) with LOE 2's
recon-and-DoS tooling: **"the cannon"** — a vendored, rate-capped PowerShell TCP
flood script (an `hping3` stand-in for T1498.001 Direct Network Flood) — and a
**portable nmap** (the 7.92 win32 zip, no installer and no Npcap) plus the
VC++/Npcap runtime it needs to launch.
It is **not** a Phase-1 `range-config` role. It is called from
`FGNW-recon-tooling.yml` during **Phase 3 (post-deploy composition, S3)**, after
the Akatsuki tool-cache VM is up — it pulls its artifacts from that cache and
from Nexus (`192.0.2.2`), so it must run while networking is still normal, before
`ludus testing start` seals the range. nmap is fetched checksum-pinned and
fail-closed; the VC++ runtime and Npcap are best-effort (Npcap only matters for
raw `-sS` scans, and its silent install is time-bounded so it can never repeat
the ~11h unattended hang the full nmap installer once caused).

| `tasks_from:` | writes? | what it does |
| --- | --- | --- |
| `main.yml` | yes | deploy the cannon, install nmap + prereqs, verify |
| `cannon.yml` | yes | drop `cannon-flood.ps1` into `C:\ludus\recon-tooling\` |
| `nmap.yml` | yes | install portable nmap, the VC++ x86 runtime and best-effort Npcap; add nmap to PATH |
| `verify.yml` | no | assert nmap launches (connect-scan capable; non-fatal backstop) |
| name | default | purpose |

| --- | --- | --- |
| `range_recon_tooling_nmap_version` | `"7.92"` | nmap version — the last portable, Npcap-free win32 release. |
| `range_recon_tooling_nmap_zip_url` | Nexus raw-hosted URL (derives from version) | Where the portable zip is fetched from (Nexus, not nmap.org). |
| `range_recon_tooling_nmap_zip_sha256` | `b54c54d4…a3efa71e` | Checksum the zip is pinned against (fail-closed). |
| `range_recon_tooling_nmap_install_dir` | `C:\Tools` | Extraction dir, added to the system PATH. |
| `range_recon_tooling_nmap_vcredist_exe` | `VC_redist.x86.exe` | VC++ x86 runtime installer filename; nmap.exe will not start without it. |
| `range_recon_tooling_nmap_npcap_exe` | `npcap-1.50.exe` | Npcap installer filename (only raw `-sS` needs it). |
| `range_recon_tooling_npcap_install_timeout` | `300` | Seconds bounding the silent Npcap install so it can never hang the deploy. |
It does not weaken a defender — it **arms the attacker**. The deliberate act here
is equipping an attacker-controlled host with offensive capability a clean
workstation would not have:

- **Network reconnaissance:** nmap on `PATH`, able to sweep and port-scan the
  range (TCP connect `-sT` scans; raw `-sS` only if Npcap installed).
- **A denial-of-service tool:** `cannon-flood.ps1`, which opens repeated TCP
  connections against a target `host:port` to produce a Direct Network Flood
  (T1498.001).
- **A raw-packet capture driver:** Npcap, installed best-effort.
Both offensive tools are deliberately *restrained* rather than maximised, which
is the point of the emulation: the cannon is **rate-capped and self-terminating**
(≈20 conn/s for 30 s by default) so it generates a recognisable, profiled
DoS-*attempt* signature without actually degrading the shared range services, and
nmap is the connect-scan-only portable build. This is **offensive range content**
(attacker arming), not a change to any victim host's security posture.
