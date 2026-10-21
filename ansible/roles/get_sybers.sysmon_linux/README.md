**Install Microsoft's official [Sysmon for Linux](https://github.com/Sysinternals/SysmonForLinux)**
on Debian-family hosts, so every VM in a range carries Sysmon telemetry — not
just the Windows boxes (the [`get_sybers.sysmon`](../get_sybers.sysmon/) role
covers those).
This is a **standalone task-role**, not a collection role, because it is used by
more than one galaxy — rule 6 in
`doc/standards/02-Ansible-Standards.md`. Call it by plain
name from a range config's `roles:` or from any collection's playbooks; no
cross-collection dependency is created. It is placed by bare name on the
`sysmon_linux` VM targets in the [FGNW](https://github.com/Get-Sybers/FGNW)
`range-config.yml` (attacker, ninjasploitable — Debian 12 "bookworm" — and kali).
The decisions live in [`tasks/main.yml`](tasks/main.yml) as decision-gated
includes (rule 8 — a `when:` belongs on an include, never buried in an action):

- **preflight** — resolve the distro→repo mapping, probe the Nexus cache, and
  assert reachability. Read-only by construction; changes nothing on the target.
- **install** — install the vendored Microsoft signing key, register the
  Microsoft apt repo *through Nexus*, `apt-get update` scoped to just that one
  source list, then `apt install sysmonforlinux`.
- **configure** — deploy the baseline config and register/start the service.
The service module semantics make a converged re-run a true no-op; nothing is
uninstalled+reinstalled.
Microsoft ships Sysmon for Linux from its own apt repo
(`packages.microsoft.com`), per SysmonForLinux's `INSTALL.md`. This role reaches
that repo **only** through the shared Ludus Nexus apt-proxy
(`msft-debian-prod-proxy` / `msft-ubuntu-prod-proxy`), so it works under
`ludus testing` containment exactly like the Windows Sysmon role's
sysinternals-proxy.
The apt trust anchor (Microsoft's release-signing key) is **vendored** in
[`files/microsoft-prod.gpg`](files/microsoft-prod.gpg) — pre-dearmored, so no `gpg` binary is
needed on the minimal Debian/Ubuntu templates — rather than fetched at install
time. That means the Nexus path needs no other external reachability at all.
**Policy:** if Nexus is down and the Microsoft repo is
not already registered, the role **fails** rather than pulling
`packages-microsoft-prod.deb` straight from the internet. Range VMs must never
fall back to the internet.
`sysmonforlinux` and `sysinternalsebpf` themselves fetch fine from Nexus, but
`sysmonforlinux`'s apt `Depends:` pulls in **non-Microsoft** packages Nexus does
not proxy — `libssl-dev` on every distro, plus `libjson-glib-1.0-0` /
`libjson-glib-1.0-common` on Debian — and apt then tries `deb.debian.org` /
`security.ubuntu.com` / `kali.download`, all blocked under containment. So the
Nexus path alone only gets partway while contained. Real completion needs one of:
- **Run this role during Phase 3** (normal range networking) — the intended,
  documented default.
- Extend Nexus with apt-proxy repos for the base-OS archives too (a larger
  Nexus addition than the Microsoft-only proxies).
- Temporarily `ludus testing allow -d <those domains>` — a user call, not made
  unilaterally.
All optional. The role's one input is declared in
[`defaults/main.yml`](defaults/main.yml) and typed in
[`meta/argument_specs.yml`](meta/argument_specs.yml) (§3/§4); the Nexus endpoint
is a range-level identity the role reads with a fallback. Ludus passes
`role_vars` to every user role on a VM, so keep any prefix collision-free.

| Variable | Default | Purpose |
| --- | --- | --- |
| `nexus_host` / `nexus_port` | `192.0.2.2` / `8081` | Shared range Nexus apt-proxy endpoint (defined at range level; role falls back to these). |
| `sysmon_linux_kali_debian_version` | `"12"` | On Kali, which Debian codename's Microsoft repo to register (Kali isn't an officially supported target — see below). Set to `"13"` etc. if bookworm packages don't satisfy Kali's newer libc/deps. |

Privilege: root (`become`) on the target. Idempotent: yes — a converged re-run
is a no-op. Rollback: `sysmon -u force` then `apt remove sysmonforlinux`; the
role does not uninstall.
Deploys [`files/sysmon-linux-baseline-config.xml`](files/sysmon-linux-baseline-config.xml) as the Sysmon config.
The binary lands at `/usr/bin/sysmon`; the config is read from
`/etc/sysmon/config.xml`.
Microsoft officially supports Ubuntu / Debian / Azure Linux / Fedora / RHEL /
openSUSE / SLES (per `INSTALL.md`). **Kali is not** an official target — it is
Debian-testing/sid-derived and dpkg/apt-compatible, so this role's best-effort
fallback registers the Debian 12 (bookworm) Microsoft repo on Kali too,
overridable with `sysmon_linux_kali_debian_version`. The Kali path is flagged
**unverified against a real Kali host** in the task comments; treat it as
best-effort.
