**ACSC "Windows Event Logging and Forwarding" baseline** — the retention sizing
and audit-policy subset of the guidance that is expressible as a per-host Ansible
role.
Implements the part of the Australian Cyber Security Centre (ACSC,
[cyber.gov.au](https://www.cyber.gov.au/resources-business-and-government/maintaining-devices-and-systems/system-hardening-and-administration/system-hardening/windows-event-logging-and-forwarding))
"Windows Event Logging and Forwarding" technical guidance that a config-management
role can own, tracking the ACSC reference repo
[AustralianCyberSecurityCentre/windows_event_logging](https://github.com/AustralianCyberSecurityCentre/windows_event_logging).
This is a **standalone task-role**, not a collection role, because it is used by
more than one galaxy — rule 6 in
`doc/standards/02-Ansible-Standards.md`. Call it by plain
name from a range config's `roles:` or from any collection's playbooks; no
cross-collection dependency is created. It is referenced by bare name in the
[FGNW](https://github.com/Get-Sybers/FGNW) blueprint's `range-config.yml`. Its
Linux counterpart is [`get_sybers.acsc_linux_port_sysmon`](../get_sybers.acsc_linux_port_sysmon/).
The decisions live in [`tasks/main.yml`](tasks/main.yml) as decision-gated
includes (rule 8 — a `when:` belongs on an include, never buried in an action):

- **[`classic_logs.yml`](tasks/classic_logs.yml)** — set the `MaxSize` of the
  Security / Application / System classic Event Log channels (and the PowerShell
  Operational channel).
- **[`audit_policy.yml`](tasks/audit_policy.yml)** — enable full command-line
  auditing on process-creation events (4688) and PowerShell Script Block Logging
  (4104).
Windows classic Event Log channels have **no** "keep N months" setting — `MaxSize`
(the ring-buffer size before the oldest events roll off) is the only real lever.
The ACSC headline numbers this role applies:

| Channel | MaxSize |
| --- | --- |
| Security | 2 GB (`2147483648`) |
| Application / System | 64 MB (`67108864`) |
| PowerShell/Operational | 64 MB (same reasoning) |

Target retention is **≥ 18 months**. A bigger log *approximates* 18 months on a
typically-busy host — it is **not** a guarantee. A noisy DC, or a box under active
attack, can still roll events off sooner even at these sizes. Treat the size bump
as "aiming for" 18 months, not "achieving" it; forward off-host if you need a
guarantee.

- **Classic logs** (Security / Application / System) are configured under the
  log's own EventLog *service* key:
  `HKLM:\SYSTEM\CurrentControlSet\Services\EventLog\<Name>\MaxSize`
- **Modern "Applications and Services Logs" channels** (PowerShell/Operational
  here; Sysmon/Operational in the [`get_sybers.sysmon`](../get_sybers.sysmon/)
  role) live under a different hive shape entirely:
  `HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WINEVT\Channels\<Channel>\MaxSize`
Writing a classic log's `MaxSize` under the WINEVT root (or vice versa) silently
no-ops. For the classic logs the registry value alone is a policy-style setting
that a running Eventlog service doesn't always pick up immediately, so the role
also runs `wevtutil sl <Log> /ms:<bytes>` — Microsoft's documented mechanism to
apply the same setting without a reboot.
The retention sizing is only useful if the events are high-fidelity — a big log
full of low-fidelity events is still a low-fidelity log. So the companion audit
settings (also ACSC / Essential-Eight recommended):
- **Command-line auditing on 4688** — without it, 4688 records the process image
  but not its arguments, hiding base64/IEX payloads passed on the command line
  (the single highest-value 4688 enrichment).
- **PowerShell Script Block Logging** — records the deobfuscated contents of
  executed script blocks (`Microsoft-Windows-PowerShell/Operational`, event
  4104), high value against fileless/obfuscated PowerShell.
None. This role encodes a **fixed baseline** — the ACSC numbers and audit
settings above are the point, so there are no tunables to drift. Change the
baseline by editing the role, not by overriding a variable per range. The
contract is stated as such in [`meta/argument_specs.yml`](meta/argument_specs.yml)
(`options: {}`) and [`defaults/main.yml`](defaults/main.yml) (§3).
The `wevtutil` applies are handlers ([`handlers/main.yml`](handlers/main.yml)),
notified only by a registry write that actually changed, so a converged re-run
reports zero changed (§7/§22). Privilege: local administrator. Rollback: none
automated — restore the previous `MaxSize`/audit registry values by hand.
