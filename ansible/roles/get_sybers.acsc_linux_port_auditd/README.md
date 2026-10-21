**ACSC-Linux-Port-Auditd** — the auditd half of the Linux port of the ACSC
baseline, built on Florian Roth / Nextron Systems' *Best Practice Auditd
Configuration*, adapted for Debian/Proxmox, and applying the ACSC retention
intent to auditd's own log rotation.
The Linux port has two halves, one per Windows original:

| Windows | Linux |
| --- | --- |
| [`get_sybers.sysmon`](../get_sybers.sysmon/) → `acsc-sysmon-config.xml` | [`get_sybers.acsc_linux_port_sysmon`](../get_sybers.acsc_linux_port_sysmon/) |
| [`get_sybers.acsc_event_logging`](../get_sybers.acsc_event_logging/) → 4688 + audit policy | **this role** |
| … its `MaxSize` retention sizing | this role's [`tasks/retention.yml`](tasks/retention.yml), and the Sysmon role's for journald |

It is a **standalone task-role**, not a collection role, because it is used by
more than one galaxy — cluster nodes, infra VM guests and range Linux VMs. See
rule 6 in `doc/standards/02-Ansible-Standards.md`. Call
it by plain name from a range config's `roles:` or from any collection's
playbooks; no cross-collection dependency is created. It declares no collection
dependencies either — everything it uses is `ansible.builtin`.
The sibling is `get_sybers.acsc_linux_port_sysmon`, implementing
*ACSC-Linux-Port-Sysmon*: "the ACSC baseline, ported to Linux, expressed through
Sysmon". This is the same baseline ported to Linux and expressed through the
other mechanism, so it is `acsc_linux_port_auditd` implementing
*ACSC-Linux-Port-Auditd*. Variables are prefixed `acsc_auditd_`, mirroring
`acsc_sysmon_`. The name says which baseline, which platform and which tool, in
that order — the same three things, in the same order, as its sibling.
Vendored verbatim, not fetched at run time — ranges run `--testing` and range
VMs have no internet (rule 4).

| | |
| --- | --- |
| Upstream | <https://github.com/Neo23x0/auditd> (Nextron Systems) |
| File | `audit.rules` → [`files/upstream/Neo23x0-audit.rules`](files/upstream/Neo23x0-audit.rules) |
| Commit | `038e70832e487b76cfd2a2e4f07f360a40989be9` (2026-05-04) |
| sha256 | `922b43e7b7c4ce386749a0e63c3a228a13854277de2ef092eddb536a8fa4142e` |
| Licence | Apache-2.0 — [`files/upstream/LICENSE`](files/upstream/LICENSE) |

That commit was `master` at vendoring time; the two are byte-identical.
The vendored file is **provenance, not the deployed artefact**. What gets
deployed is [`templates/acsc-linux-port-auditd.rules.j2`](templates/acsc-linux-port-auditd.rules.j2),
derived from it, which annotates every change in place: `[+]` addition, `[~]`
adaptation, `[-]` upstream rule not rendered and why. Upstream **key names are
preserved** wherever the rule is upstream's, so Sigma and SIEM content written
against the Neo23x0 ruleset matches unmodified — which is the whole premise of
that project ("detection intelligence belongs in Sigma, not the ruleset").
Every one of these is commented in the template rather than silently dropped.

| Upstream | Here | Why |
| --- | --- | --- |
| `-i` (ignore errors) | **off** by default | `-i` turns "this rule did not load" into silence. Instead every path-bearing rule is stat'd first and only what exists is rendered — and what was skipped is printed. |
| `-w PATH -p PERM -k KEY` | `-a always,exit -F dir=\|path= -F perm= -F key=` | auditd itself warns "Old style watch rules are slower"; that matters on a hypervisor. Equivalent semantics. |
| `-F subj_type=crond_t` cron filters | **dropped** | Needs SELinux. Debian/Proxmox use AppArmor, where `subj_type` is not a valid field — upstream tolerates it only because of `-i`. No replacement is needed: the cron noise those rules suppress comes from the execve firehose, which is not rendered here. |
| `auid>=1000` literal | rendered from `acsc_auditd_uid_min`, **asserted against `/etc/login.defs`** | This is upstream's own instruction ("auditd rules do not support variables, so this substitution must be done at deploy time"). Asserted rather than assumed, so a host with a different `UID_MIN` cannot end up with rules matching the wrong set of users. |
| `-w /etc/audisp/` | plus `/etc/audit/plugins.d/` | auditd 3.x/4.x moved the dispatcher config; Debian 13 ships 4.x. |
| `-w /lib/systemd/` | **dropped** | Merged-`/usr`: `/lib` → `/usr/lib`, so it is the same watch as `/usr/lib/systemd` with the same key. A duplicate rule can be rejected, and without `-i` that aborts the whole load. |
| `-w /etc/bashrc` | plus `/etc/bash.bashrc` | Debian's spelling. The RHEL path stays and is filtered out by the existence check. |
| `-w /etc/openldap/` | plus `/etc/ldap/` | Debian's spelling. |
| — | plus `/etc/netplan/`, `/etc/systemd/network/` | Ubuntu range VMs and systemd-networkd hosts. |
| Filebeat, CrowdStrike Falcon, `vmtoolsd` rules | **dropped** | No Beats agent, no Falcon sensor, and these are KVM/Proxmox guests running qemu-guest-agent. Carrying them would be dead config that reads like coverage. |
| `modules` rule with `-F auid!=unset` | filter **removed** | Upstream restricts module loads to attributable ones. A module loaded by a service (`auid=unset`) is precisely the rootkit case, and module loads are rare enough here that the volume is nil. |
| — | plus `privesc`, `sudo_exec`, `su_exec`, `audit_tools`, PVE tool watches | See "Complementing Sysmon" and "Profiles". |
| — | plus `/etc/pve` **explicitly not watched** | pmxcfs is FUSE and cannot carry an inode watch. The PVE admin surface is audited at the tool layer instead — which is also the layer that carries `auid`. |

```yaml
acsc_auditd_profile: hypervisor
acsc_auditd_profile: guest
```

`hypervisor` adds the PVE admin surface (`pveum`, `pct`, `qm`, `pvesh`, `pvecm`,
`pveceph`, `ceph`, `zpool`, `zfs`, `/etc/ceph/`, `/etc/frr/`) and suppresses
three upstream groups that a Ceph node cannot carry — listed, with reasons, in
`acsc_auditd_hypervisor_suppress`:

- `unauthedfileaccess_system` — daemon-originated `EACCES`/`EPERM` opens. The
  OSDs, `pvestatd` and `pvedaemon` generate these continuously.
- `ipc` — SysV IPC. Ceph and the PVE daemons use it heavily.
- `system_binary_writes` — the `/usr` and `/bin` write watches. Every apt or PVE
  upgrade writes thousands of files under `/usr`. `/boot` is deliberately *not*
  suppressed: small, rare, always interesting.
Set it to `[]` on a node you have measured and found can carry the full set.
`guest` renders everything. Both profiles keep the entire integrity, identity,
persistence and exploitation-primitive coverage.
The split: **auditd
answers "who touched this file / ran this tool"**, with login-uid (`auid`)
attribution that survives `su` and `sudo`; **Sysmon answers "what is the process
tree and where did it connect"**, with full argv, image hash and parent lineage.
With `acsc_auditd_sysmon_complement: true` (the default) the rule groups in
`acsc_auditd_sysmon_covered` are not rendered at all:

| Not rendered | Covered instead by |
| --- | --- |
| `process_creation` — unfiltered `execve`/`execveat` | Sysmon EventID 1 (ProcessCreate), which carries strictly more |
| `network_connect_4` / `_6` — successful `connect()` | Sysmon EventID 3 (NetworkConnect) |
| `network_socket_created` — `socket(AF_INET/AF_INET6)`, the single highest-volume group upstream ships | Sysmon EventID 3 |

Set it `false` on a host where Sysmon is refused (unprivileged LXC, no eBPF) to
get the full upstream set.
Deliberately **not** treated as Sysmon-covered, because they are not:

- `privesc` — a *narrowed* `execve` rule (`uid!=euid`, `euid=0`). Sysmon has no
  `auid`, so "which human escalated" is only answerable here. This is the one
  execution rule Sysmon cannot replace.
- `raw_network_socket_created` — Sysmon for Linux reports NetworkConnect, not
  `AF_PACKET`/`SOCK_RAW` socket creation.
- `tracing` (ptrace) — overlaps Sysmon ProcessAccess, kept for the `auid` and
  for the requests Sysmon's filter set does not cover.
- `sudo_exec` / `su_exec` and the PVE tool watches — per-binary execution
  watches, cheap, and the replacement for the execve firehose that is no longer
  rendered.
One interaction worth knowing: Sysmon for Linux **is** eBPF-based, so
`sysinternalsebpf` loading its probes appears under key `bpf` at every Sysmon
start. That is expected, and useful — it makes an eBPF load that is *not*
Sysmon's the thing that stands out.
**It cannot work in any LXC container, privileged or unprivileged, and the role
refuses.** This was checked against the kernel rather than assumed.
`kernel/audit.c`, `audit_netlink_ok()` — the gate every audit netlink message
passes through — reads, verbatim:

```c
 /* Only support initial user namespace for now. */
 ...
 if (current_user_ns() != &init_user_ns)
  return -ECONNREFUSED;
 ...
 case AUDIT_GET: case AUDIT_SET: case AUDIT_LIST_RULES:
 case AUDIT_ADD_RULE: case AUDIT_DEL_RULE: ...
  /* Only support auditd and auditctl in initial pid namespace
   * for now. */
  if (task_active_pid_ns(current) != &init_pid_ns)
   return -EPERM;
  if (!netlink_capable(skb, CAP_AUDIT_CONTROL))
   err = -EPERM;
```

Three things follow, and they are why the refusal is unconditional rather than
"unprivileged only":

1. **Unprivileged LXC** — `infra_guest`'s default (`unprivileged: true`) — runs
   in a child user namespace and fails the *first* check. Every audit netlink
   message returns `-ECONNREFUSED`. That error is a **deliberate lie**: the
   kernel comment says it is returned so PAM believes audit was never compiled
   in and lets logins proceed. The container therefore cannot distinguish "audit
   is forbidden to me" from "this kernel has no audit" — exactly the silent
   nothing the house standard
   exists to refuse.
2. **Privileged LXC still fails**, because the PID-namespace check comes *before*
   the capability check and LXC always gives a container its own PID namespace.
   Granting `CAP_AUDIT_CONTROL` does not help.
3. **And if it somehow did**, it would be worse: there is one global `audit_pid`,
   so a container auditd that registered would take the host's audit stream away
   from the host's own auditd.
What auditd itself does there: fails to start with *"Error setting audit daemon
pid (Operation not permitted)"* / *"Unable to set initial audit startup state to
'enable', exiting"*. Its only container-viable mode is `local_events = no` in
`auditd.conf`, which turns it into a pure log **aggregator for other hosts** and
collects nothing about itself. That is a different product from what this role
deploys and is explicitly out of scope.
**How the role handles it.** Two preflight checks, both before any mutation:

- `systemd-detect-virt --container` — catches any container, including the
  privileged case that check 2 would miss.
- `/proc/self/uid_map` — the decisive one, because it is the exact condition the
  kernel tests. Initial user namespace reads `0 0 4294967295`; a child user
  namespace reads a real mapping such as `0 100000 65536`.
Either one trips and the role **fails loudly** with the reasoning, rather than
installing a daemon that can never register. `acsc_auditd_allow_container: true`
overrides it — only on a target where you have run `auditctl -s` by hand and
seen it succeed.
**The coverage answer**, same shape as the Sysmon sibling's: an LXC container's
processes *are* host processes in a namespace, so the PVE node's own auditd
already sees their syscalls. Run this role on the node with
`acsc_auditd_profile: hypervisor`. The honest caveat is that those records carry
the **host-side (mapped) uid and host pid, with no container attribution** — the
kernel's audit container-id work was never merged. Container-local process
detail comes from the node's Sysmon instead.
ACSC targets **≥ 18 months**, and reaches for it by sizing the log so events are
not overwritten first. Windows has one lever (`MaxSize`). journald has two
(`SystemMaxUse` **and** `MaxRetentionSec` — size and age, whichever is hit
first). auditd has **only the size lever**:

> `max_log_file` (MiB) × `num_logs` is the entire ceiling. There is **no
> age-based setting in `auditd.conf` at all** — nothing corresponding to
> journald's `MaxRetentionSec`. auditd cannot be told "keep 18 months".
So the same caveat the Windows and Sysmon roles carry is **weaker still** here.
This **aims at** 18 months on a typically-busy host; it does not guarantee it. A
noisy hypervisor, or one under active attack, rolls events off sooner and
nothing in this role prevents that. Forward off-host if you need a guarantee —
`audispd-plugins` is installed for exactly that, but configuring a remote sink is
a separate decision and is deliberately not made here.
Default: `16 × 256 MiB = 4 GiB`, deliberately the same figure the Sysmon sibling
gives journald (`acsc_sysmon_journal_max_use`), so the two halves cost the same
and can be sized together. The role **refuses** to apply the ceiling unless the
audit filesystem has it plus `acsc_auditd_min_free_headroom_mb` (2 GiB) free.
Disk actions are `ROTATE`/`SYSLOG`, never `SUSPEND`/`HALT`/`SINGLE` — Debian's
stock `admin_space_left_action = SUSPEND` stops a hypervisor logging on a full
`/var`, and the stock `disk_full_action` can wedge it. `max_log_file_action =
keep_logs` was considered and rejected: it never deletes a rotation, which raises
retention by trading it for filling the filesystem.
Set `acsc_auditd_manage_retention: false` to leave `auditd.conf` alone.
This role lands in `ansible/roles/` rather than inside a collection because of
rule 6: auditd is wanted on cluster nodes, infra VM guests *and* range Linux
VMs — three galaxies — so it must be reachable by plain name from anywhere, not
from one collection where only a 3-part FQCN could get to it. Genuinely
site-specific watches (service-account SSH dirs, wrapper binaries) are the
caller's to pass via `acsc_auditd_extra_watch_candidates`; anything needing a
collection dependency (e.g. a ZFS free-space floor) belongs in the calling play.
Audit **keys** are upstream's wherever the rule is upstream's, so Sigma content
written against the Neo23x0 ruleset matches unmodified.
`tasks/main.yml` is a **dispatcher**: every decision is a `when:` on an
`include_tasks`, and every included file is a flat list of unconditional
actions.

```text
tasks/main.yml ── preflight.yml               profile, platform, container refusal — tagged `always`
               ├─ install.yml                 apt + systemd
               ├─ install-plugins.yml         (install_plugins)
               ├─ preflight-postinstall.yml   libaudit version, UID_MIN
               ├─ retention-preflight.yml     free-space assert   (manage_retention)
               ├─ retention.yml               auditd.conf         (manage_retention)
               │    └─ retention-reload.yml   SIGHUP + marker     (daemon predates config)
               ├─ paths.yml                   stat every candidate path
               ├─ ruleset.yml                 remove stale, render, read back
               ├─ load.yml                    decide              (rendered file exists)
               │    └─ load-apply.yml         augenrules + assert + marker
               └─ verify.yml                  kernel readback     (rendered file exists)
                    └─ verify-e2e.yml         ausearch probe      (audit_tools key declared)
```

Measured with `scripts/check-density.py`'s walker: **33 action
tasks, 1 carrying `when:`** (3%) — against a tracked-task-role baseline of 16%.
The one remaining is the `--check` notice in the dispatcher itself, which is
where a decision is supposed to live.
`tasks/preflight.yml` mutates nothing and is tagged `always`, so a `--tags` run
cannot skip validation and then change a host. It refuses, before the first
apt transaction, on: an unimplemented profile, a non-Debian `os_family`,
`acsc_auditd_stale_rule_files` entries containing a path separator (they are fed
into a removal loop under `/etc/audit/rules.d`), and — the substantive one —
**any container at all**, decided from `/proc/self/uid_map` and
`systemd-detect-virt`, because `audit_netlink_ok()` refuses every audit netlink
message from outside the initial user and PID namespaces.

```bash
ansible-playbook … --check --tags always
ansible-playbook … --check
```

`--check` is honest but partial, and the role says so in its own output rather
than in a footnote: on a host that has already converged it exercises the whole
chain; on a fresh one the template writes nothing, so there is nothing to read
back and the load and verification steps are **skipped with an explicit
message** naming why. A skipped verification that announces itself is the
difference between a partial dry run and a false green.
This role apt-installs `auditd` from whatever sources the target already has.
That is worth stating plainly because two sibling roles do the opposite:
`get_sybers.acsc_linux_port_sysmon` and `get_sybers.zeek_sensor` both refuse to
install unless a digest-pinned artefact was staged by the caller.
The asymmetry is defensible for a PVE node — cluster nodes already pull Debian
and Proxmox packages directly from `deb.debian.org` and `download.proxmox.com`,
ungated. It is **weaker on a range Linux VM**: the Ludus Nexus
proxies nuget/chocolatey and three Microsoft apt repos, and **no Debian
archive** (verified against the live Nexus repository list), so a `guest`-profile
run has no gated source to install from and reaches the public mirror during the
deploy window. Not a blocker — auditd is a stock distribution package and the
window closes before containment — but it is not the Nexus-only posture the rest
of the tree holds, and it should not be discovered later.
The role does not trust a rendered file or an `active` unit as evidence.
[`tasks/verify.yml`](tasks/verify.yml) — run at the end of every convergence, and
callable standalone with `tasks_from: verify`:

1. **Control block** — reads `auditctl -s` and asserts `enabled`, `failure`,
   `backlog_limit`, `backlog_wait_time` and `rate_limit` are the values the
   ruleset asked for. This half produces no rules at all, so it is invisible to
   `auditctl -l` and can fail completely without anything looking wrong. It is
   also what catches the `zz-` load-order trap regressing.
2. **Every key, not a sample** — reads the *deployed file* back, extracts every
   key it declares, and asserts each one is present in `auditctl -l`. A
   partially-loaded ruleset cannot pass. This is what makes
   `acsc_auditd_ignore_errors: true` survivable at all: even with upstream's `-i`
   silently dropping a rule, the missing key fails here.
3. **End to end** — `/usr/sbin/auditctl` is itself a watched binary
   (`key=audit_tools`), so the `auditctl -l` above *is* an auditable event that
   has definitely just happened. `ausearch --input-logs -k audit_tools` must
   return it. `--input-logs` is load-bearing: without a TTY, ausearch reads STDIN
   instead of the audit logs, and Ansible hands tasks an empty stdin, so it
   reports `<no matches>` no matter what the log contains.
4. **Reported, never asserted** — whether the kernel cmdline has `audit=1`.
   Setting it needs a reboot; the consequence (events before auditd starts are
   not captured) is stated rather than hidden.
The rule load itself converges by comparison, not by a handler: a handler does
not fire on a failed run, so a failure between render and flush leaves the file
correct and the kernel on stock rules. The role reloads when the rendered file
differs from a state marker **or** when the kernel is missing keys the file
declares, so `auditctl -D` by hand self-heals on the next run.

- **`--check` on a host this role has never converged** stops at the read-back:
  the template wrote nothing, so there is no file to read and the load and every
  verification step are skipped with an explicit note. That is the honest limit
  of check mode for a role that installs a package and loads kernel state; on an
  already-converged host `--check` is meaningful.
- **Retention sizing cannot be proven at converge time.** The role asserts the
  `auditd.conf` keys are set exactly once to exactly its values, and that the
  filesystem can hold the ceiling. Whether 4 GiB actually holds 18 months is a
  function of this host's event rate and is unknowable in advance — see the
  caveat above.
Every variable is documented inline in [`defaults/main.yml`](defaults/main.yml)
and typed in [`meta/argument_specs.yml`](meta/argument_specs.yml), validated
before any task runs (§3/§10). The ones you are most likely to set:

```yaml
acsc_auditd_profile: guest
acsc_auditd_package_version: ""
acsc_auditd_sysmon_complement: true
acsc_auditd_extra_watch_candidates: []
acsc_auditd_stale_rule_files: []
acsc_auditd_max_log_file_mb: 256
acsc_auditd_num_logs: 16
acsc_auditd_manage_retention: true
acsc_auditd_immutable: false
acsc_auditd_allow_container: false
```

`vars/main.yml` holds the derived composition (which watch list applies, which
groups are suppressed, which paths to stat) and is not meant to be overridden.

```yaml
- hosts: linux_targets
  roles:
    - get_sybers.acsc_linux_port_auditd
- hosts: proxmox_cluster
  serial: 1
  tasks:
    - ansible.builtin.include_role:
        name: get_sybers.acsc_linux_port_auditd
      vars:
        acsc_auditd_profile: hypervisor
        acsc_auditd_package_version: "1:4.0.2-2+b2"
        acsc_auditd_stale_rule_files: [zz-get-sybers.rules]
        acsc_auditd_extra_watch_candidates:
          - { path: /home/infra-node/.ssh/, kind: dir, perm: wa, key: ssh_authz, why: "forced-command grant" }
```
