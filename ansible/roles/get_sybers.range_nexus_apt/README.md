Repoints an apt-based range VM at the range's Nexus apt proxies
(`192.0.2.2:8081`) so `apt` keeps working inside the contained range, where the
stock public mirrors are sealed off by `ludus testing start` (and, even
uncontained, a reverted VM's clock rejects their `Release` files). It maps
Debian to the `debian-proxy` / `debian-security-proxy` repos and Kali to
`kali-proxy`, disables the stock public sources, and refreshes the cache. A
distro with no Nexus base-OS proxy (e.g. Ubuntu) is skipped with `end_host`.
It configures one VM in place, so it is a task-role (S2). Run it **first** on
each apt VM, before any role that apt-installs — it is the extension of the
`sources.list` rewrite in
`campaign/ansible/FGNW-ninjasploitable-join.yml`. The Nexus proxies must already
be up (an `-t nexus` / campaign phase-0 prerequisite); apt has no fallback once
the public sources are disabled.

| name | default | purpose |
| --- | --- | --- |
| `range_nexus_apt_base` | `"http://192.0.2.2:8081/repository"` | Base URL of the range Nexus endpoint; the per-distro `deb` lines are built from it. |
| `range_nexus_apt_sources` | see `defaults/main.yml` | Per-distro Nexus source lines keyed by `ansible_distribution` (Debian, Kali). A distro absent from the map is skipped. |
| `range_nexus_apt_tolerate_clock_skew` | `true` | Write `apt.conf.d/99-nexus-clockskew` to tolerate a reverted VM's clock skew. |
| `range_nexus_apt_max_future_seconds` | `"86400"` | `Acquire::Max-FutureTime` seconds written when clock-skew tolerance is on. |

No exploitable weakness on the guest — this is **package-distribution plumbing**
(infra-shaped), not attack surface. It installs nothing vulnerable, opens no
port, and disables no host defence.
The one intentional security relaxation is to `apt`'s own metadata checking:
with `range_nexus_apt_tolerate_clock_skew` (default `true`) it writes
`Acquire::Check-Valid-Until "false"` and a large `Acquire::Max-FutureTime`, so
apt stops rejecting the upstream-dated `Release` files the Nexus proxies serve
when a reverted range VM's clock runs hours behind real time. That relaxes apt's
protection against stale/replayed repository metadata — accepted here because the
path is range-internal and Nexus-trusted, and a range that cannot run `apt`
wastes more time than the check saves. Set the variable `false` on any VM whose
clock is trustworthy. Disabling the stock public sources is containment, not a
weakening: under `--testing` they are unreachable anyway.
