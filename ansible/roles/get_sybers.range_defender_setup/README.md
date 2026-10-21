Enables and configures **Microsoft Defender** on a range Windows VM and prepares it for
Defender for Endpoint portal onboarding. It installs the `Windows-Defender` features, renders
and runs a **check-then-set** configuration script (real-time protection, cloud-delivered
protection, network protection, sample submission and the scheduled quick-scan time), asserts
the run succeeded, and drops operator reference files (a README and a desktop shortcut) with the
manual onboarding steps. It runs at the Ludus `user-defined-roles` stage (S2). The
configuration script reads `Get-MpPreference` first and applies only settings that differ,
printing a `DEFENDER-CONFIG: CHANGED/NOCHANGE` marker that drives `changed_when`, so a second
converge reports zero changes.

| `tasks_from:` | what it does |
| --- | --- |
| `main.yml` | install → configure → verify |
| `install.yml` | create the setup directory, enable the `Windows-Defender` features |
| `configure.yml` | render + run the check-then-set config script, assert it succeeded, write the operator README/shortcut |
| `verify.yml` | report the final setup status (tag-gated: `--tags verify`) |
| name | default purpose |

| --- | --- | --- |
| `range_defender_setup_dir` | `C:\DefenderSetup` | Directory on the VM holding the generated `Configure-Defender.ps1` and `README.txt`. |
| `range_defender_setup_quick_scan_time` | `120` | Scheduled quick-scan time, in minutes after midnight (`120` = 02:00). |
`defender_features` and `defender_config` are `register` facts, not inputs, and are excluded
from `meta/argument_specs.yml`.
**Nothing** — this is a **management / setup** role, and it is the exception in this set. Rather
than degrading the guest's security posture it does the opposite: it turns Defender **on** and
stands it up as a detection/EDR surface, for blue-team and detection-engineering scenarios that
want a monitored range host. There is no intentional vulnerability to verify here; `verify.yml`
confirms the setup completed, not that a weakness is present.
One posture note, not a weakness: the config script sets `SubmitSamplesConsent = SendAllSamples`
and `MAPSReporting = Advanced`, i.e. it opts the host into sending samples/telemetry to
Microsoft's cloud. On a contained range those outbound calls do not leave the range, but the
consent is set regardless — adjust it for scenarios where that matters.
