**Zeek network security monitor**, deployed as a passive sensor — with the
vantage point treated as something to be **proven**, not assumed.
This is a **standalone task-role**, not a collection role, because it is built
for more than one galaxy: `get_sybers.cluster` can deploy it to the PVE nodes
and `get_sybers.range` can deploy it to the range router — neither wires it in
yet. Rule 6 in
`doc/standards/02-Ansible-Standards.md`: a role inside
a collection is reachable only by 3-part FQCN and would create a cross-collection
dependency. Call this one by plain name from a range config's `roles:` or from
any collection's playbooks.
> **Note on placement vs. invocation.** "Standalone task-role" is about where the
> role *lives*, not where it *runs*. Its primary caller should be a cluster-layer
> playbook, because a sensor that lives in a range's lifecycle is destroyed by
> `ludus range rm` and reverted by `ludus testing stop`. See
> *Wiring it up* below.

---
Zeek only sees what reaches its interface. Working out where that is in this
topology is most of the design, so here is the reasoning and the evidence.
**1. Range VNets are VLAN-aware VXLAN bridges, one per range, on every node.**
[`cluster-sdn-setup.yml`](https://github.com/Get-Sybers/proxmaxxing/blob/main/playbooks/cluster-sdn-setup.yml)
creates them:

```yaml
sdn_zone: ludus
nat_vnet: ludusnat
range_vnets:
  - { number: 1, users_group: ludus_users }
cluster_peers: "192.0.2.11,192.0.2.12,192.0.2.13"
```

with `--vnet r<N> --tag <N> --vlanaware 1`. Each `r<N>` materialises as a Linux
bridge device on each node, MTU 1450 (`mtu 1450` is "owned by Proxmox SDN in
`/etc/network/interfaces.d/sdn`", per the same file).
**2. Same-VLAN traffic never leaves the node it is on.** Two VMs on VLAN 10 on
the same node exchange frames through that node's `r<N>` bridge. The frames are
switched, never routed, and never touch the range router.
**3. The range router is the gateway for every VLAN, and only that.** Ludus gives
it `10.<range>.<vlan>.254/24` on one hot-added NIC per VLAN
(`add-vlan-to-router.yml` upstream), so *inter-VLAN* and *egress* traffic
hairpins through it — and nothing else does.
There is **no single vantage point that sees everything**.

| Vantage point | Sees | Misses |
| --- | --- | --- |
| PVE node, on `r<N>` | same-VLAN intra-node, inter-VLAN, cross-node (post-decap) | traffic on *other* nodes |
| Range router | inter-VLAN, egress | **all same-VLAN traffic** — i.e. most lateral movement |
| Dedicated sensor VM on a VNet | flooded frames only | learned unicast, unless fed a mirror |

Because a Linux bridge forwards learned unicast only out the owning port, a
promiscuous *guest* NIC on a VNet sees almost nothing. The **host** bridge device
is different: the kernel clones frames it forwards to the bridge device itself,
which is what makes host-level capture work at all.
So: **per-node Zeek on the PVE cluster nodes is the primary sensor** (profile
`hypervisor`), capturing each node's local `r<N>` VNet bridges plus `ludusnat`
where it exists. Consequences worth stating:

- Cross-node traffic is captured **after VXLAN decapsulation**, as plain inner
  802.1Q frames. Zeek never has to parse VXLAN, and **no raw packets cross the
  operator LAN** — only compact JSON logs leave the node. That matters: the
  VXLAN underlay rides the 1 Gb LAN alongside corosync.
- Cross-node flows are seen **twice**, once per node. Tag by sensor and dedupe
  downstream.
- The **inner 802.1Q tag is the only thing** that says which range VLAN
  (10/20/30/87/90/99) a flow was on, since one VLAN-aware VNet carries all of
  them. Hence `zeek_sensor_vlan_logging` defaults on.
The range router (`chokepoint`) is a **complement**, not an alternative: it is
the one place with a range-wide L3 view and it sees egress in one pass, but it
is structurally blind to same-VLAN lateral movement. That blind spot is written
into the deployed `local.zeek` itself, not just here.
- **`brctl setageing <br> 0` (hub mode).** Ludus's own networking docs suggest
  it, but that guidance predates the SDN cutover and was written for the old
  per-range `vmbr100X` bridges. On a VXLAN VNet, unknown-unicast is head-end
  replicated to **every remote VTEP**, so forcing flooding would push intra-node
  range traffic across the shared 1 Gb underlay. It also changes range semantics
  (every guest starts seeing every frame) and may be undone whenever SDN
  regenerates its config.
- **GRE/ERSPAN mirror to a central sensor.** Full raw traffic over the same
  contended underlay, plus MTU-1450-inside-1500 fragmentation.
- **Per-VM Zeek.** Linux-only in a 19-Windows/4-Linux range, destroyed by
  teardown, and visible to the in-range attacker simulation.
None of the above is left as an assumption. The role **asserts** its
preconditions and refuses rather than installing a sensor that sees nothing —
see *Preconditions* below.

---
Same shape as `get_sybers.acsc_linux_port_sysmon`'s `acsc_sysmon_profile`.

```yaml
zeek_sensor_profile: hypervisor
zeek_sensor_profile: chokepoint
```

**`hypervisor`** discovers its capture set from the bridge devices matching
`zeek_sensor_hypervisor_iface_pattern` (`^(r[0-9]+|ludusnat)$`), so a range VNet
added later is picked up on the next converge. Deliberately **not** matched:
`vmbr0`/`nic0` (operator LAN — out of scope until separately authorised), the
`vmbr9xx` sealed infra bridges, and the encapsulated `vxlan_*` underlay
(capturing there would give VXLAN-wrapped duplicates of what the VNet bridge
already shows in the clear). Add any of them explicitly if that is really wanted.
**`chokepoint`** *requires* `zeek_sensor_capture_interfaces`. There is no safe
auto-discovery on a router: including the WAN interface alongside the per-VLAN
interfaces double-counts every NATed flow. The canonical target is
`<range_id>-router-debian11-x64` — note **Debian 11**, so the package source has
to serve bullseye.
Anything other than these two fails the preflight rather than silently picking
one

---

A Zeek that runs and captures zero packets is a silent success, which
the house standard
forbids. Every one of these is a hard failure, not a warning:

| | | |
| --- | --- | --- |
| 1 | `zeek_sensor_profile` is `hypervisor` or `chokepoint` | else the capture model is undefined |
| 2 | Exactly one install source is configured | both default empty, so an unconfigured call fails instead of installing nothing |
| 3 | Not an unprivileged LXC | no host bridges, no `CAP_NET_RAW` in the initial userns |
| 4 | `os_family == Debian` | the RedHat/SUSE half of upstream was dropped, not carried untested |
| 5 | `hypervisor` ⇒ `/etc/pve` exists | the whole VNet-bridge model is Proxmox-specific |
| 6 | **≥ 1 capture interface resolved** | a discovery glob matching nothing is the canonical "silently matched nothing" bug — it would yield an empty `node.cfg` on a green run |
| 7 | Every capture interface **exists** | a typo'd interface name otherwise installs a blind sensor |
| 8 | Every capture interface is **administratively UP** | a DOWN interface delivers nothing (operational `state DOWN` on a portless bridge is tolerated — it will carry traffic once a tap is enslaved) |
| 9 | Free space on `/var` exceeds the log ceiling | otherwise the pruner can never reach its ceiling and the volume fills first |
| 10 | Nexus answers, with **no internet fallback** | rule 4 / standing repo policy |
| 11 | The `signed-by` keyring exists | a missing one makes `apt update` fail looking like a network fault |
| 12 | Staged `.deb` digests re-verified **on the target** | proves the bytes survived transport |
| 13 | `zeekctl` is on `PATH` after install | the package set did not contain what was assumed |
| 14 | `zeekctl config` reports `cfgdir`/`sitepolicypath`/`logdir`/`spooldir` | paths are **derived**, never guessed |
| 15 | File capabilities read back present | `setcap` silently no-ops on `nosuid`/no-xattr mounts |
| 16 | **GRO/LRO are off** | else the kernel hands Zeek coalesced frames that were never on the wire, and its length/sequence analysis is confidently wrong |
| 17 | **Every interface delivers unicast frames** | see below |

Before any configuration is written, [`tasks/capture_gate.yml`](tasks/capture_gate.yml)
runs a bounded promiscuous `tcpdump` on each resolved interface and requires real
frames — filtered to **`not broadcast and not multicast`**.
That filter is the point. Every host on a segment sees ARP and mDNS, so a probe
that accepts any frame at all passes on an interface forwarding nothing.
Requiring **unicast** is what distinguishes *"the kernel is cloning forwarded
frames to this bridge device"* — the assumption the whole `hypervisor` profile
rests on — from *"this interface exists and is noisy"*.
Set `zeek_sensor_require_packets: false` only to converge **before** the range
exists. The run then prints an explicit `UNVERIFIED` warning, because a skipped
correctness check that leaves no trace is how "merged, green, never executed"
happens

---

`tasks/main.yml` and the two heaviest task files are **dispatchers**: every
decision is a `when:` on an `include_tasks`, and every included file is a flat
list of unconditional actions.

```text
tasks/main.yml ── preflight.yml                      inputs, platform, capture set — tagged `always`
               │    └─ preflight-hypervisor.yml      PVE-node check       (profile=hypervisor)
               │         └─ preflight-discover-bridges.yml   (no explicit interfaces)
               ├─ install.yml                        dispatcher + layout discovery
               │    ├─ install-nexus-apt.yml         (install_source=nexus_apt)
               │    │    └─ install-nexus-keyring.yml    (keyring_src supplied)
               │    ├─ install-staged-deb.yml        (install_source=staged_deb)
               │    └─ install-service-account.yml   (user != root)
               │         └─ install-setcap.yml       (caps not already set)
               ├─ capture_gate.yml                   dispatcher — THE honesty gate
               │    ├─ capture-offloads.yml          (disable_offloads non-empty)
               │    ├─ capture-offloads-assert.yml   (require_offloads_off)
               │    ├─ capture-packets.yml           (require_packets)
               │    └─ capture-packets-skipped.yml   (NOT require_packets — says so loudly)
               ├─ … directories, node.cfg, local.zeek, zeekctl.cfg, zeekctl check
               ├─ daemon-reload.yml                  (a unit changed)
               ├─ redeploy.yml                       (configuration changed)
               ├─ retention.yml                      (manage_retention)
               │    └─ retention-daemon-reload.yml   (a pruner unit changed)
               └─ verify.yml
                    ├─ verify-packets.yml            (require_packets)
                    └─ verify-retention.yml          (manage_retention)
```

Measured with `scripts/check-density.py`'s walker: **60 action
tasks, 0 carrying `when:`** — against a tracked-task-role baseline of 16%.
Two of the changes are more than relocation:

- `tasks/install.yml` carried `when: zeek_sensor_install_source == '…'` on
  **thirteen separate tasks** — two entire mutually-exclusive install paths
  interleaved in one file. They are now two files chosen once.
- the staged-`.deb` loop carried
  `when: item.version not in ansible_facts.packages[…]` on the `apt` action.
  Rule 8: *"idempotence is module semantics, never `when: not
  already_installed`"* — so the filter is resolved into a list and `apt` loops
  over it unconditionally. Same for the "which offloads could not be changed"
  report, which is now a `rejectattr` filtered loop instead of a per-item
  `when:`.
This role is unusual in the tree in having a full `meta/argument_specs.yml` —
**43 options, checked at promotion to cover `defaults/main.yml` exactly** (no
option missing, none extra, no default disagreeing). Ansible validates it before
the first task runs, so a mistyped variable name or a bad `choices` value is a
failure *before* anything is touched, not a surprise mid-run.
`tasks/preflight.yml` mutates nothing and is tagged `always`, so a `--tags` run
cannot skip validation and then mutate a host:

```bash
ansible-playbook … --check --tags always
ansible-playbook … --check
```

It refuses on an unimplemented profile or install source, an install source that
is **selected but not configured**, an empty service-account name, a non-Debian
`os_family`, an unprivileged LXC, a `hypervisor` profile on a host with no
`/etc/pve`, an empty resolved capture set, a capture interface that does not
exist or is administratively DOWN, and insufficient free space for the
configured log ceiling.
Honest limit of `--check`: the capture gate's `tcpdump` probe and every
`zeekctl` invocation are `command` tasks and are skipped, so `--check` proves
the inputs and the plan but **cannot** prove the vantage point sees traffic.
That gate only means something on a real run.
[`tasks/verify.yml`](tasks/verify.yml) trusts nothing the role just did.
`state: started` proves systemd started something; it does not prove Zeek parsed
our policy, that any worker survived, that a packet reached the analyser, or that
retention will ever be enforced.

1. **`zeekctl status`** — every configured node is `running`, and there are at
   least as many running nodes as capture interfaces. A worker that crashed on a
   bad policy shows here while the oneshot unit still reports success.
2. **`zeekctl netstats` → `recvd > 0`** — *Zeek's own* counter, not ours and not
   the kernel's. This is the difference from the capture gate: the gate proved
   the **interface** delivers frames; this proves the **analyser** received them,
   i.e. that `node.cfg` names the same interfaces and `PcapFilter` is not
   discarding everything. Capture loss is *reported*, not asserted — the right
   response to drops is tuning, not aborting a converge.
3. **Policy identity** — the deployed `local.zeek` carries this role's marker,
   and `zeekctl check` re-parses the live configuration.
4. **`conn.log` written in the last hour** — `recvd > 0` says frames reached the
   analyser; a `conn.log` says the analyser turned them into evidence. A broken
   logging framework gives the first without the second.
5. **`zeekctl config` readback** — `logexpireinterval` and `cronenabled` are
   asserted from the **effective** configuration, never from the file we wrote.
6. **Both timers active** — see below.
Re-runnable on its own: `--tags zeek-sensor-verify`.
Stated plainly rather than implied:

- Seeing *some* unicast does not prove *all* forwarded unicast is visible.
  Establishing that needs generated traffic of each class — same-VLAN intra-node,
  inter-VLAN via the router, cross-node via VXLAN — with a known-answer check.
  That is a range-deployment test, not something a converge can perform.
- Traffic that never crosses a host bridge is invisible to **any** placement:
  VM-loopback, nested virtualisation, container-to-container inside a VM.
- Operator-LAN device↔device traffic through the physical switch is out of scope
  and needs a SPAN-capable switch or on-device agents.
- Flows bisected by live migration appear as partial flows on two sensors.

---
Both were in the file whose header calls itself *"the authoritative check"*, and
both are now covered by negative tests run against this role's own bytes.
**The GRO/LRO assertion could pass on no data.** The `ethtool -k` probe carries
`failed_when: false`, so an interface ethtool could not read returned `rc=1`
with empty stdout — and an assertion phrased purely as *"the string
`generic-receive-offload: on` is not present"* is trivially true of an empty
string. Measured here: `ethtool -k nosuchdev0` → rc 1, stdout empty, errors on
stderr. The assertion now requires `rc == 0` and the presence of the GRO key
before it will accept anything, and reports the two failure modes differently.
(The pre-promotion role skipped failed probes with `when: item.rc == 0`, which
was also wrong — silently skipping — but it did not report success.)
**The packet counter crashed on the case it exists to catch.**
`map('regex_search', '([0-9]+) packets? captured', '\\1')` raises
`AttributeError: 'NoneType' object has no attribute 'group'` inside the filter
as soon as one input does not match, and the non-matching input is precisely the
interesting one: a device `tcpdump` could not open prints
`No such device exists` and no counter line. The exception fired before
`map('default', ['0'], true)` could supply a fallback, so the gate died with a
Jinja traceback rather than its own diagnosis. Replaced with `regex_findall`,
which yields `[]` for a non-match. Verified on the role's own bytes:

```text

stderrs: ["12 packets captured", "0 packets captured", "tcpdump: r9: No such device exists"]
  regex_search(..., '\\1')  -> AttributeError
  regex_findall(...)         -> [['12'], ['0'], []]
  ... | default(['0'],true) | first | int  -> [12, 0, 0]

```

The failed interface now scores 0 and the gate fails on it, which is the
intended behaviour.
Same ACSC intent as
[`get_sybers.acsc_linux_port_sysmon/tasks/retention.yml`](../get_sybers.acsc_linux_port_sysmon/tasks/retention.yml),
and the same honesty about it.
ACSC targets **≥ 18 months**. Windows has one lever (`MaxSize`); Sysmon for Linux
writes to syslog so its levers are journald's. **Zeek is neither** — it keeps its
own rotated tree under `LogDir` and journald has nothing to do with it. Setting
the sysmon role's journald drop-in would not extend a single Zeek log by a
second. The levers here are:

| Lever | What it does |
| --- | --- |
| `LogExpireInterval` (548 days) | the **age** limit |
| `StatsLogExpireInterval` (30) | diagnostics are not evidence |
| `LogRotationInterval` (3600 s) | live → dated archive |
| `zeek-sensor-prune` + timer | the **size** ceiling zeekctl does not have |

**Same caveat as the sysmon role, and it bites harder here:** this **aims at** 18
months; it does not guarantee it. Zeek logs are an order of magnitude bulkier
than Sysmon's, so on any busy range the **size** ceiling is reached long before
the age limit — at which point real retention is whatever fits in
`zeek_sensor_log_max_use_mb`. Forward off-host for a guarantee.
Two traps the role closes rather than inherits:

- **`LogExpireInterval` is enforced by `zeekctl cron`, not by Zeek.** Set without
  that cron running, it is a number in a file that deletes nothing — and a
  crashed worker is never restarted either. The role installs a systemd timer and
  `verify.yml` asserts it is **active**. A retention policy that silently does
  nothing is the same failure class as a task that silently matches nothing.
- **zeekctl has no size lever at all.** Without one, 548 days will fill a PVE
  node's root volume months before expiring anything — which takes the
  *hypervisor* down, not just the sensor. The pruner deletes whole dated
  directories oldest-first (never individual files: a half-pruned day is evidence
  that silently lies), and **refuses to prune below
  `zeek_sensor_log_prune_floor_days`, exiting non-zero instead**. A ceiling that
  silently eats everything is worse than one that stops and complains.
`zeek_sensor_manage_retention: false` leaves all of it alone.

---
Three tools, three questions, no overlap by design.

| | Question it answers | Blind to |
| --- | --- | --- |
| **Zeek** (this role) | *What happened on the wire?* Sessions, protocols, TLS/SSH/HTTP/DNS/SMB metadata, certificates, files **transferred**, service and software inventory observed from traffic | anything a process did that produced no packets |
| **Sysmon** ([`acsc_linux_port_sysmon`](../get_sybers.acsc_linux_port_sysmon/), [`sysmon`](../get_sybers.sysmon/)) | *Which process did it?* Process lineage with full argv, image hashes of what was **executed**, per-host `NetworkConnect`, `DnsQuery`, `ProcessAccess` | anything on a host without an agent — including the range's 19 Windows VMs if the agent is not there, and every network device |
| **auditd** | *Who did it, under which identity?* File and command attribution with login-uid | the network entirely |

The distinctions that keep them from duplicating each other:

- **Sysmon's `NetworkConnect` is not Zeek's `conn.log`.** Sysmon records that a
  process opened a socket, from **one endpoint's** point of view, and only on
  hosts running the agent. Zeek records the **session** — both directions, the
  protocol, what was negotiated, what was transferred — for **every** host on the
  segment including those with no agent at all.
- **Hashing is not duplicated.** Sysmon hashes what was **executed**; Zeek's
  `hash-all-files` hashes what was **transferred**.
- **The two are joined, not merely adjacent.** `zeek_sensor_community_id`
  defaults on, so `conn.log` carries a Community ID — the same deterministic
  5-tuple hash Sysmon's `NetworkConnect` events produce. "Which process opened
  this session?" becomes a join key rather than manual timestamp-and-port
  correlation. Without it the two datasets sit side by side and never meet.
- **Zeek deliberately does not do file-integrity or process work.** No AIDE, no
  process monitoring — that is auditd's and Sysmon's ground, and duplicating it
  would just double the volume.
The practical consequence: the **only** telemetry covering the range's Windows
VMs at the network layer, and the only telemetry at all for anything without an
agent, is this role.

> `get_sybers.cluster`'s `cluster-audit-logging.yml` stages Sysmon and configures
> auditd on the PVE nodes; this role is the network-layer equivalent. Wiring Zeek
> into that play is covered under *Wiring it up* below.

---
Rule 4: every range runs `--testing`, so range VMs have no internet, and the
standing repo policy is fail-closed — `get_sybers.sysmon_linux` has no
direct-internet fallback, for exactly this reason. There is
therefore no third path. Configure **one**:

```yaml
zeek_sensor_install_source: nexus_apt
zeek_sensor_nexus_repo: debian-trixie-proxy
zeek_sensor_nexus_repo_codename: trixie
```

```yaml
zeek_sensor_install_source: staged_deb
zeek_sensor_artefacts:
  - { name: zeek, version: "…", sha256: "…", deb: "zeek_…_amd64.deb" }
```

Both default to empty, so an unconfigured call fails loudly rather than
installing nothing and reporting success.
> **Prerequisite.** `campaign/ludus-requirements.yml` records that no Nexus proxy
> exists for base-OS apt repos; path A requires creating one for the distro repo
> carrying `zeek`, and path B requires a caller that stages the pinned `.debs`.
The apt refresh is scoped to this role's list only
(`-o Dir::Etc::sourcelist=… -o Dir::Etc::sourceparts=-`), so a blanket
`apt update` never reaches repos a contained host cannot see.

---

```yaml
- hosts: proxmox_cluster
  serial: 1
  roles:
    - role: get_sybers.zeek_sensor
      vars:
        zeek_sensor_profile: hypervisor
        zeek_sensor_nexus_repo: debian-trixie-proxy
        zeek_sensor_nexus_repo_codename: trixie
```

```yaml
- role: get_sybers.zeek_sensor
  vars:
    zeek_sensor_profile: chokepoint
    zeek_sensor_capture_interfaces: [ens19, ens20, ens21]
    zeek_sensor_nexus_repo_codename: bullseye
```

This role does **not** modify `cluster-audit-logging.yml`. To wire Zeek into that
play, mirror its Sysmon handling: extend play 1's staging with the Zeek artefacts
(path B) or assert the Nexus proxy repo (path A), then add a third `include_role`
in play 2 after the Sysmon block, `serial: 1` as it already is. Its `stage_dir`
(`/var/cache/get-sybers/audit-logging`) and this role's default
(`/var/cache/get-sybers/zeek-sensor`) are separate on purpose.
Remember `ludus ansible role` has no refresh: re-add the role before redeploying
or the previously copied version is what runs

---

Adapted from **[juju4/ansible-zeek](https://github.com/juju4/ansible-zeek)**
@ **`f300b5468ab0a2547cfd6434d31c77b5df0bd4a3`** (2026-08-01),
**BSD-2-Clause**, Copyright (c) 2015 juju4. Content was **vendored, not
submoduled** — Ludus clones sources with `--recurse-submodules`, so a submodule
would add clone weight and pin us to upstream's release cadence.
`templates/local.zeek.j2`, `templates/node.cfg.j2` and
`templates/systemd-bro.service.j2` are the basis of this role's equivalents; the
unprivileged-user + file-capabilities pattern and the zeekctl option set are
upstream's. `redef ignore_checksums = T` is upstream's and is kept verbatim.

| Upstream | Here | Why |
| --- | --- | --- |
| opensuse OBS repo / source build, over the internet | Nexus apt proxy or staged digest-pinned `.debs` | rule 4 — ranges have no internet, and repo policy is fail-closed |
| one interface, from `bro_nodes_if` or the default route | one worker per resolved interface; standalone for 1, local cluster for N | a PVE node's traffic is spread across many VNet bridges, and the default-route interface is the operator LAN — the one thing out of scope |
| `vars/Debian-1x.yml` with hardcoded paths | paths **derived** from `zeekctl config` | Debian packages to `/etc/zeek`, zeek.org to `/opt/zeek`; hardcoded per-release path tables rot |
| `broids_*_enable` flags, default off, for VLAN/MAC logging | on by default | the inner 802.1Q tag is the only VLAN attribution available on a VLAN-aware VNet |
| `Type=forking`, `broctl start`, no `ExecStop`, in `/lib` | `Type=oneshot` + `RemainAfterExit`, `deploy`, `ExecStop`, `Restart=on-failure`, in `/etc` | zeekctl is not a daemon, so forking heuristics make the unit state meaningless; `/lib` belongs to the package manager |
| `LogExpireInterval: 90` days | 548 days + a size ceiling + an enforcing timer | ACSC ≥ 18 months; zeekctl has no size lever and the age lever does nothing without cron |
| no capture preconditions at all | the entire preflight and capture gate | upstream will happily configure `interface=eth0` on a host with no `eth0` |
| `zeekctl.cfg` edited by `replace` with `backup: yes` | `lineinfile` **plus** an effective-value readback | the mutation being regex-based is only acceptable because the result is asserted |

- **`frameworks/files/detect-MHR`** and **`protocols/ssl/notary`** — live internet
  lookups (Team Cymru MHR over DNS; ICSI notary).
- **JA3/JA4, `cs-bro`, `jonschipp-bro`, `sooshie-bro`, `securitykitten`** —
  upstream git-clones these from GitHub at deploy time. Stage locally and add via
  `zeek_sensor_intel_files` if wanted.
- **MISP integration** (`tasks/misp-integration.yml`) — pulls indicators over
  HTTP from a MISP server.
- **`zkg`** (`tasks/zkg.yml`) — `pip install` from PyPI.
- **`protocols/ssh/geo-data`** — needs a MaxMind database that is neither shipped
  nor fetchable here; it would load and populate nothing.
- **Mail** (`MailConnectionSummary`, `notice/extend-email`, `tasks/reporting.yml`)
  — no MTA on a PVE node, no route out of a sealed range. Explicitly disabled in
  `zeekctl.cfg` rather than left at its default.
- **AIDE** (`tasks/aide-hids.yml`) and **monit** (`tasks/monit.yml`) — file
  integrity is auditd's ground and process supervision is systemd's.
- **RedHat / SUSE / Ubuntu ≤ 16.04 support** and the `bro`-era init.d path — not
  carried untested. The preflight fails loudly on a non-Debian host rather than
  half-working.
- **`meta` dependencies `juju4.redhat_epel` and `juju4.ipsumdump`** — the first is
  RedHat-only, the second serves only the dropped mail summary.

---
Every variable is documented inline in [`defaults/main.yml`](defaults/main.yml)
and typed in [`meta/argument_specs.yml`](meta/argument_specs.yml), which is
validated before any task runs. The ones most likely to need setting:

| Variable | Default | Notes |
| --- | --- | --- |
| `zeek_sensor_profile` | `hypervisor` | `hypervisor` \| `chokepoint` |
| `zeek_sensor_capture_interfaces` | `[]` | **required** for `chokepoint` |
| `zeek_sensor_hypervisor_iface_pattern` | `^(r[0-9]+\|ludusnat)$` | matching zero devices is a hard failure |
| `zeek_sensor_install_source` | `nexus_apt` | `nexus_apt` \| `staged_deb` |
| `zeek_sensor_nexus_repo` / `_codename` | `""` | empty ⇒ preflight fails |
| `zeek_sensor_require_packets` | `true` | the capture gate + `recvd > 0` |
| `zeek_sensor_capture_probe_filter` | `not broadcast and not multicast` | requiring unicast is the point |
| `zeek_sensor_user` | `zeek` | unprivileged + capabilities; `root` to disable |
| `zeek_sensor_log_expire_days` | `548` | ≈ 18 months, an aim not a guarantee |
| `zeek_sensor_log_max_use_mb` | `20480` | the ceiling that usually binds first |
| `zeek_sensor_local_nets` | range/build/infra space | without it Zeek calls everything remote |

`always` (preflight), `zeek-sensor-install`, `zeek-sensor-capture`,
`zeek-sensor-retention`, `zeek-sensor-verify`.

---
Limitations and prerequisites:

- **No internet (rule 4), fail-closed.** `zeek_sensor_install_source` is `nexus_apt` or `staged_deb`, both empty by default so an unconfigured call fails loudly. `nexus_apt` needs a Zeek apt-proxy repository in the Ludus Nexus (which carries no Zeek repository), and `staged_deb` needs a caller that stages digest-pinned `.debs`; configuring one of these is a prerequisite before deploy.
- **The `hypervisor` profile assumes forwarded unicast is visible on the `r<N>` SDN bridge.** The capture gate tests this at deploy time rather than assuming it; if a bridge does not forward unicast to the sensor, the fallback is per-node `tc mirred` from the bridge slave ports to a local dummy interface, which keeps the per-node, zero-underlay-cost properties.
- **Paths and parsers are derived and asserted.** `zeekctl` is located on `PATH` and every path is derived from `zeekctl config`; the `zeekctl netstats` / `zeekctl config` parsers are asserted, so a package-layout or output-format change fails loudly rather than passing silently.
- **Live-internet Zeek features are off** (detect-MHR, the ICSI notary, JA3/JA4 and other GitHub-cloned scripts, MISP, `zkg`, the MaxMind geo-data, and mail reporting) — a sealed range has no route out; stage any wanted intel locally via `zeek_sensor_intel_files`.
