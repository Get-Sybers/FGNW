**ACSC-Linux-Port-Sysmon** — one Sysmon-for-Linux baseline for every Linux
target in this source, plus the ACSC retention target applied to journald.
This is the Linux counterpart of two Windows roles:

| Windows | Linux (this role) |
| --- | --- |
| [`get_sybers.sysmon`](../get_sybers.sysmon/) → `acsc-sysmon-config.xml` | `templates/acsc-linux-port-sysmon.xml.j2` |
| [`get_sybers.acsc_event_logging`](../get_sybers.acsc_event_logging/) → channel `MaxSize` | [`tasks/retention.yml`](tasks/retention.yml) → journald |

It is a **standalone task-role**, not a collection role, because it is used by
more than one galaxy — see rule 6 in
`doc/standards/02-Ansible-Standards.md`. Call it by
plain name from a range config's `roles:` or from any collection's playbooks; no
cross-collection dependency is created.
Nothing here is on by default — the role installs only where a blueprint,
template or playbook asks for it, and every knob is settable from outside.
**Note on variable naming:** Ludus passes `role_vars` to *all* user-defined roles
on a VM, not to one role (see the [Ludus docs](https://docs.ludus.cloud/)),
so every variable here is prefixed `acsc_sysmon_` to stay collision-free
alongside other roles on the same VM. Every input is declared in
[`defaults/main.yml`](defaults/main.yml) (with its rationale) and typed in
[`meta/argument_specs.yml`](meta/argument_specs.yml), validated before any
task runs (§3/§10). Privilege: root. Idempotent: yes. Rollback: `sysmon -u force`
and remove the journald drop-in; the role does not uninstall.

```yaml
  - vm_name: '{{ range_id }}-fire-dc1'
    roles:
      - get_sybers.acsc_linux_port_sysmon
    role_vars:
      acsc_sysmon_profile: guest
      acsc_sysmon_artefacts:
        - { name: sysinternalsebpf, version: "1.4.0", sha256: "…", deb: "sysinternalsebpf_1.4.0_amd64.deb" }
        - { name: sysmonforlinux,   version: "1.3.5", sha256: "…", deb: "sysmonforlinux_1.3.5_amd64.deb" }
```

Range-wide instead of per-VM: put the same keys under `global_role_vars:` at the
top level of the range config.
Add a playbook to the template's own `ansible/` directory and point the
provisioner at it — the same shape the estate's Packer templates use:

```yaml
- hosts: default
  become: true
  roles:
    - get_sybers.acsc_linux_port_sysmon
```

```hcl
provisioner "ansible" {
  playbook_file   = "ansible/acsc-sysmon.yml"
  extra_arguments = ["--extra-vars", "@ansible/acsc-sysmon-vars.yml"]
}
```

Baking it into the image means every VM from that template ships instrumented,
with no per-range `roles:` entry. Set `ANSIBLE_ROLES_PATH` to this source's
`ansible/roles/` (or vendor the role into the template) so Packer can resolve it
at build time.
Call it by plain name — no FQCN, no cross-collection dependency (rule 6):

```yaml
- ansible.builtin.include_role:
    name: get_sybers.acsc_linux_port_sysmon
  vars:
    acsc_sysmon_profile: hypervisor
```

```yaml
acsc_sysmon_profile: hypervisor
acsc_sysmon_profile: guest
```

`hypervisor` makes `NetworkConnect` exclusion-based and drops intra-cluster
traffic — Ceph OSD/MON, corosync, the OpenFabric storage mesh — which otherwise
moves multiple Gb/s and drowns the log. What survives is egress leaving the
cluster. `guest` leaves `NetworkConnect` unfiltered: on a range VM the lateral
movement *is* the signal, and on an infra guest egress should be rare.
Both profiles keep `FileCreate`/`FileDelete` include-based on
`acsc_sysmon_watched_paths`, and leave process lineage unfiltered.
Sysmon is built **into** the LXC — this role installs and configures there
exactly as it does on a VM or a node. It does not decide whether a host is
worth instrumenting.
Two things it deliberately leaves alone:

- **Whether eBPF probes can load in a given container** is a container *build*
  setting — the capabilities and features the CT is created with (see
  `get_sybers.infra.infra_guest`). `sysinternalsebpf` needs `CAP_BPF` /
  `CAP_SYS_ADMIN` in the initial user namespace plus `bpf(2)`, tracefs and perf
  events. If a CT needs those, build it with them; that is not a config role's
  call to veto.
- **How events are collected and shipped** is a separate role, still to be
  designed.
`acsc_sysmon_container_policy` exists for when you *do* want an opinion:
`ignore` (default, just install), `warn` (install, note an eBPF-hostile
platform), `fail` (opt-in gate — stop instead of installing).
Sysmon for Linux implements only the subset of the schema eBPF can observe. The
Windows baseline's `ImageLoad` (3 rules), `RegistryEvent` (2) and
`CreateRemoteThread` (1) are still *parsed* on Linux but never fire, so they are
omitted here rather than carried as dead config that reads like coverage.
Ported: `ProcessCreate`, `ProcessTerminate`, `ProcessAccess`, `NetworkConnect`,
`DnsQuery`, `FileCreate`, `FileCreateTime`, `FileDelete`, `FileDeleteDetected`,
`RawAccessRead`.
ACSC targets **≥ 18 months**. Windows has one lever (`MaxSize`); Sysmon for Linux
writes to syslog, so the levers are journald's `MaxRetentionSec` **and**
`SystemMaxUse` — whichever is hit first wins. `Storage=persistent` is the
precondition: Debian's default keeps the journal in tmpfs, where no retention
setting means anything.
Same honesty as the Windows role: this **aims at** 18 months on a
typically-busy host. A noisy hypervisor, or one under attack, still rolls events
off sooner. Forward off-host if you need a guarantee.
Set `acsc_sysmon_manage_retention: false` to leave journald alone.
The caller stages the digest-gated `.deb`s on the controller at
`acsc_sysmon_stage_dir` first — `sysinternalsebpf` **before** `sysmonforlinux`,
which hard-depends on it. `acsc_sysmon_artefacts` defaults to empty so an
unconfigured call fails loudly instead of installing nothing and reporting
success.
Ranges run `--testing` (rule 4), so a range VM has no internet — stage from
Nexus. The calling play does the staging for cluster nodes.

```yaml
acsc_sysmon_artefacts:
  - { name: sysinternalsebpf, version: "1.4.0", sha256: "…", deb: "sysinternalsebpf_1.4.0_amd64.deb" }
  - { name: sysmonforlinux,   version: "1.3.5", sha256: "…", deb: "sysmonforlinux_1.3.5_amd64.deb" }
```

`tasks/main.yml` is a **dispatcher**: every decision is a `when:` on an
`include_tasks`, and every included file is a flat list of unconditional
actions.

```text
tasks/main.yml ── preflight.yml                  inputs, digests, container detect — tagged `always`
               ├─ preflight-container-fail.yml   (container + policy=fail)
               ├─ preflight-container-warn.yml   (container + policy=warn)
               ├─ install.yml                    push, re-verify digests, apt
               ├─ configure.yml                  render config, read service facts
               ├─ configure-install.yml          sysmon -i    (unit absent)
               ├─ configure-reapply.yml          sysmon -c    (unit present + config changed)
               ├─ service.yml                    enable + start
               ├─ retention.yml                  journald drop-in  (manage_retention)
               │    ├─ retention-persistent-dir.yml  (storage=persistent)
               │    (restart: handlers/main.yml)       (drop-in changed)
               └─ verify.yml                     sysmon -s
                    └─ verify-schema.yml         (eBPF expected to work)
```

Measured with `scripts/check-density.py`'s walker: **19 action
tasks, 0 carrying `when:`** — against a tracked-task-role baseline of 16%.
One change is more than a move. The install loop used to carry
`when: item.version not in ansible_facts.packages[...]` on the `apt` task
itself. Rule 8 is explicit that *"idempotence is module semantics, never
`when: not already_installed`"* — so the already-at-pinned-version filter is now
resolved into a list (`__acsc_sysmon_to_install`) and the `apt` task loops over
it unconditionally. An empty list is an honest no-op; a per-item `when:` was a
hidden branch.
`tasks/preflight.yml` mutates nothing and is tagged `always`, so a `--tags` run
cannot skip validation and then mutate a host.

```bash
ansible-playbook … --check --tags always
ansible-playbook … --check
```

It refuses on an unimplemented profile, a non-Debian `os_family` (this role has
no dnf/rpm path and claiming a platform without one is the house standard's
"critical" finding), an empty or malformed `acsc_sysmon_artefacts`, an
unimplemented container policy, and — added at promotion — **any artefact
without a 64-hex sha256**. That last one matters: the role re-verifies each
digest on the target after transport, and an entry with no `sha256` would have
compared against `None` and passed vacuously. A gate that is present and does
nothing is worse than no gate.
Honest limit of `--check`: `sysmon -i` / `sysmon -c` are `command` tasks and are
skipped, so on a host without Sysmon `--check` reports the transport and config
plan but cannot prove the install.
`tasks/configure.yml` renders the Sysmon config with
`template: validate: "xmllint --noout %s"`. That runs **on the target**, and
`xmllint` ships in `libxml2-utils`, which is `Priority: optional` — not in a
minimal Debian install. Verified absent on all three PVE cluster nodes
(`pi-01`, `pi-02`, `pi-03`), which are exactly this role's `hypervisor`
targets. Without a check the run dies mid-configure with a bare
"command not found" from a validate step, which reads like a template bug.
Preflight now probes for it and refuses with a message naming
`apt install libxml2-utils`, and `acsc_sysmon_validate_config: false` is a
supported way out that `omit`s the validator rather than silently templating an
unvalidated file that looks validated.
The role does not trust "the unit is active" as evidence — it runs `sysmon -s`
and asserts the loaded schema is the one it shipped, and reads back
`systemd-analyze cat-config systemd/journald.conf` to assert the retention
values are the *effective* ones and not overridden by a later drop-in.
