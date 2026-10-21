Disables Windows telemetry and diagnostic data collection on a **range Windows VM**
(curated for **Server 2022**). Runs at the `user-defined-roles` stage (S2) — add it to a
Windows VM's `roles:` list in a range config.
It sets the telemetry-off registry policy, disables the DiagTrack/dmwappushservice/diagnostics
services (via `\Services\<svc>\Start=4`), stops the telemetry ETW AutoLoggers, and disables the
CEIP/Appraiser/diagnostics **scheduled tasks**. Values apply fully after the next reboot (which a
range deploy performs).
Ported from [EXLOUD/Windows-Telemetry-Disabler](https://github.com/EXLOUD/Windows-Telemetry-Disabler)
(MIT). Only the *declarative operations* were reimplemented in idempotent Ansible — the project's
bundled `superUser.exe` (a TrustedInstaller privilege-escalation binary), `launcher.bat`, and UI
are **not** used. The source's consumer-only Win10/11 items (Cortana, widgets, Copilot, input
prediction, Wi-Fi Sense, etc.) are intentionally excluded as N/A on Server 2022. Full provenance:
[`meta/upstream.yml`](meta/upstream.yml).
The range is `--testing`-contained (no egress), so this is realism / defense-in-depth rather than
a functional necessity — telemetry cannot leave the range regardless.
No exploitable weakness is introduced. This role **reduces Microsoft-facing telemetry and
diagnostic signal** on the host — an OPSEC/realism posture for the range, not a vulnerability.
It leaves local security logging (Event Log, Sysmon) untouched, so blue-team visibility
inside the range is unaffected.

```yaml
roles:
  - get_sybers.range_telemetry_disable
```

Everything the role acts on is data in [`defaults/main.yml`](defaults/main.yml) — override
`range_telemetry_registry` or `range_telemetry_scheduled_tasks` to add/remove entries. The role
itself contains no conditionals (repo rule 8).
The `verify` tag asserts `DiagTrack\Start == 4` and `DataCollection\AllowTelemetry == 0`.
