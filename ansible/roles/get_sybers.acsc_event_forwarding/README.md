The Ansible port of ACSC's Windows Event Forwarding scripts — the **collection**
half of the *Windows Event Logging and Forwarding* guidance.

| ACSC script | What this role does instead |
| --- | --- |
| `events/add_subscriptions.ps1` | `wecutil cs` per subscription, but only for ones not already present |
| `events/set_subscriptions_sources.ps1` | `wecutil ss <name> /adc:<SDDL>` for each |
| `events/wmi_auditing/wmi_auditing.ps1` | vendored unmodified, run behind an idempotency guard |

Three roles implement three separate halves of the same ACSC guidance — they do
not overlap:

| Role | Job |
| --- | --- |
| `get_sybers.sysmon` | **generates** Sysmon events on each host |
| `get_sybers.acsc_event_logging` | **retains** them — channel `MaxSize`, audit policy, script-block logging |
| **this role** | **collects** them — WEF subscriptions on a collector |

**Run this on the collector**, not on source computers. Pointing sources at a
collector is a GPO/registry job (`SubscriptionManager`) and is out of scope here.
Vendored from `AustralianCyberSecurityCentre/windows_event_logging` at commit
**`59041b5d4586789a751171fb752be1624ad5e3b4`** (2025-02-05, sole branch
`master`) — 28 `*_sub.xml` across 16 event categories, plus `wmi_auditing.ps1`.
Upstream licence (Copyright 2017 Commonwealth of Australia) is carried at
`files/subscriptions/LICENSE.ACSC`.
Re-verify after an upstream bump:

```bash
git clone --depth 1 https://github.com/AustralianCyberSecurityCentre/windows_event_logging.git /tmp/acsc-wel
for f in ansible/roles/get_sybers.acsc_event_forwarding/files/subscriptions/*_sub.xml; do
  u=$(find /tmp/acsc-wel/events -name "$(basename "$f")"); cmp -s "$f" "$u" || echo "DIFFERS: $(basename "$f")"
done
```

Subscriptions are selected by **`SubscriptionId`** — the value inside the XML,
not the filename.

```yaml
    roles:
      - get_sybers.acsc_event_forwarding
    role_vars:
      acsc_wef_subscriptions:
        - "Sysmon - Process"
        - "Sysmon - Networking"
        - "Account Logons"
        - "Windows PowerShell - Script Block Tracing (v5+)"
      acsc_wef_enable_subscriptions: true
```

Leave `acsc_wef_subscriptions` empty to install all 28. A name that does not
match a vendored subscription is a **hard failure**, not a skip — a typo must
not quietly install nothing.
Every input is declared in [`defaults/main.yml`](defaults/main.yml) (with its
rationale) and typed in [`meta/argument_specs.yml`](meta/argument_specs.yml),
which is validated before any task runs (§3/§10). Privilege: local
administrator on the collector. Idempotent: yes — only what is missing or
changed is acted on. Rollback: `wecutil ds <SubscriptionId>` per subscription;
the role does not remove subscriptions.
The 28 available IDs span: Account Lockouts / Logons / Modifications, AppLocker,
EMET, Event Forwarding Errors, Event Log Cleared, File Share, Object Access
Auditing, Process Tracking, Scheduled Tasks, Services, Sysmon (9 separate
subscriptions), Windows Error Reporting, Windows PowerShell (4), WMI Auditing (2).
**The vendored set is NOT all-disabled.** Counted at upstream
`59041b5`:

```bash
$ grep -h "<Enabled>" files/subscriptions/*_sub.xml | sort | uniq -c
     15     <Enabled>false</Enabled>
     13     <Enabled>true</Enabled>
```

That mattered. The role used to run its enable step *only* when
`acsc_wef_enable_subscriptions` was true, so on the default (`false`) those 13
subscriptions were created, started collecting immediately, and were never
touched — and `verify.yml` then asserted `Enabled:true == false` and **failed on
the default configuration**. `tasks/enable.yml` is now unconditional and sets
the state explicitly in both directions, so the role's declared intent beats
whatever the XML happens to say and `false` genuinely disables.
**The upstream WMI script is not idempotent.** `wmi_auditing.ps1` does
`$Descriptor.SACL += $ACE` unconditionally, so each run appends another eight
ACEs — ten runs leaves eighty. It also suppresses its own errors
(`-EA SilentlyContinue`, `Write-Debug`) and returns `1` for "complete with
errors". The script is vendored **unmodified** for provenance;
[`tasks/wmi-auditing.yml`](tasks/wmi-auditing.yml) supplies the guard it lacks —
count existing audit ACEs on `root\cimv2` first, skip if already ≥ 4, force
`$DebugPreference` so failures are legible, and assert the SACL actually changed
afterwards.
It runs only when a `WMI Auditing` subscription is requested, because those two
subscriptions collect nothing without it.
`tasks/main.yml` is a **dispatcher**: every decision is a `when:` on an
`include_tasks`, and every included file is a flat list of unconditional
actions. No task inside this role decides whether it applies.

```text
tasks/main.yml ── preflight.yml            input + platform validation, tagged `always`
               ├─ collector.yml            wecutil qc          (configure_collector)
               ├─ subscriptions.yml        stage XML + wecutil cs
               ├─ update-existing.yml      wecutil ss /cf      (update_existing)
               ├─ wmi-auditing.yml         SACL guard          (wmi_auditing)
               │    └─ wmi-auditing-apply.yml   the vendored ACSC script
               ├─ sources.yml              wecutil ss /adc     (set_sources)
               ├─ enable.yml               wecutil ss /e:true  (enable_subscriptions)
               └─ verify.yml               readback asserts
                    └─ verify-sources.yml  (set_sources)
```

Measured with `scripts/check-density.py`'s walker: **17 action
tasks, 0 carrying `when:`** — against a tracked-task-role baseline of 16%.
`tasks/preflight.yml` refuses before anything is changed: non-Windows host,
a non-boolean enable flag, an `acsc_wef_source_sddl` that is not SDDL-shaped, a
vendored subscription file with no `<SubscriptionId>`, a requested ID that does
not exist in the vendored set, and an empty resolved set. It is tagged `always`,
so a `--tags` run cannot skip validation and then mutate the collector.
Preflight performs no mutation, so it is the dry-run surface:

```bash
ansible-playbook … --check --tags always
ansible-playbook … --check
```

`--check` is meaningful throughout — every mutating module used here
(`win_file`, `win_copy`) supports check mode, and the `wecutil` reads carry
`check_mode: false` so the plan is computed from the collector's real state. The
`wecutil` **writes** are `win_command` and are therefore skipped under `--check`,
so a first run against an unconfigured collector reports what it would create
but cannot prove the creation. That is the honest limit, not a claim of full
dry-run fidelity.
The role does not treat a zero exit code as proof. After the run it re-reads
`wecutil es` and asserts every requested subscription is present, then
`wecutil gs <name>` per subscription and asserts (a) the enabled state matches
what was asked for and (b) `AllowedSourceDomainComputers` is non-empty when
`acsc_wef_set_sources` is on — a subscription with no source computers collects
nothing while looking healthy. `wecutil` returning 0 is not evidence a
subscription exists.
**Never executed against a live collector.** As of promotion this role has been
YAML- and Ansible-parsed (`ansible-playbook --syntax-check` over `tasks/main.yml`
and over every task file individually, ansible-core 2.16.19) and its vendored
bytes re-verified against upstream with `check-upstream.py --fetch`. It has not
been run on a Windows Event Collector. Treat the first run as a canary.
Configuring **source computers** to forward to this collector — the
`SubscriptionManager` GPO/registry setting — and the WinRM listener and firewall
rules on those sources. Those are fleet policy, not collector state.
