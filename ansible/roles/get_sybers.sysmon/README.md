**Install and configure Sysmon** (Sysinternals) on Windows hosts, and keep its
configuration converged — without a per-run telemetry gap.
This is a **standalone task-role**, not a collection role, because it is used by
more than one galaxy — rule 6 in
`doc/standards/02-Ansible-Standards.md`. Call it by plain
name from a range config's `roles:` or from any collection's playbooks; no
cross-collection dependency is created. It is referenced by bare name in the
[FGNW](https://github.com/Get-Sybers/FGNW) blueprint's `range-config.yml` and is
reusable on any Windows range.
The decisions live in [`tasks/main.yml`](tasks/main.yml) as decision-gated
includes (rule 8 — a `when:` belongs on an include, never buried in an action):

- **service absent** → first-time install (`Sysmon64.exe -i`).
- **service present + config bytes changed** → in-place reconfigure (`-c`) of the
  *running* Sysmon, so the ETW session and event stream are never interrupted.
- **service present + config unchanged** → a true no-op.
Sysmon is never uninstalled+reinstalled on a converged re-run, so there is no
telemetry gap and no extra WinRM `win_command` failure surface.
Deploys the **ACSC Sysmon baseline** ([`files/acsc-sysmon-config.xml`](files/acsc-sysmon-config.xml))
— the config referenced by the ACSC (Australian Cyber Security Centre,
cyber.gov.au) "Windows Event Logging and Forwarding" guidance, from
[AustralianCyberSecurityCentre/windows_event_logging](https://github.com/AustralianCyberSecurityCentre/windows_event_logging).
All optional. Every input is declared in [`defaults/main.yml`](defaults/main.yml)
and typed in [`meta/argument_specs.yml`](meta/argument_specs.yml) (§3/§4);
`sysmon_zip_checksum` defaults to `""`, which the download task turns into an
omitted parameter. Ludus passes `role_vars` to every user role on a VM, so keep
the role-name prefix.

| Variable | Default | Purpose |
| --- | --- | --- |
| `sysmon_download_url` | Nexus `sysinternals-proxy` URL (`http://192.0.2.2:8081/...`) | Where to fetch `Sysmon.zip`. Routed through the shared Ludus Nexus cache so it works under `ludus testing` containment; override for a different mirror. |
| `sysmon_zip_checksum` | `omit` | Sysinternals ships a **rolling** `Sysmon.zip` with no stable published digest, so no checksum is pinned by default. Set `-e sysmon_zip_checksum=sha256:…` to pin a vetted build for a reproducible range. |
| `nexus_host` / `nexus_port` | `192.0.2.2` / `8081` | Shared range Nexus cache endpoint — a range-level identity, not a role input; it is baked into the default `sysmon_download_url`. |

Privilege: local administrator on the Windows host (Ludus runs user roles so).
Idempotent: yes — a converged re-run reports zero changed. Rollback: remove the
`Sysmon64` service with `Sysmon64.exe -u`; the role does not uninstall.
`verify` — the verify include is tagged so you can re-run just the "service is
running" check.
