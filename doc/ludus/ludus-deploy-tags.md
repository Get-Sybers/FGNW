Every tag Ludus ships, what governs it, and where to change it.
A tag only works with the operation whose playbook defines it.
`ludus range deploy -t start-testing` does nothing — `start-testing` lives in
`testing.yml`, which only `ludus testing start` runs.

| Playbook | Tags | Driven by | Surface |
| --- | --- | --- | --- |
| [`ludus.yml`](https://github.com/badsectorlabs/ludus/blob/f8d0295c77b1d1277ffd27eb3134f55f51f38862/ludus-server/ansible/range-management/ludus.yml) — 54 plays | 22 | `ludus range deploy` | **S2** |
| [`testing.yml`](https://github.com/badsectorlabs/ludus/blob/f8d0295c77b1d1277ffd27eb3134f55f51f38862/ludus-server/ansible/range-management/testing.yml) — 13 plays | 6 | `ludus testing start`/`stop`/`allow`/`deny` | **S4** |
| [`power.yml`](https://github.com/badsectorlabs/ludus/blob/f8d0295c77b1d1277ffd27eb3134f55f51f38862/ludus-server/ansible/range-management/power.yml) — 4 plays | 3 | range power ops, `ludus range rm` | **S4** |
| [`update.yml`](https://github.com/badsectorlabs/ludus/blob/f8d0295c77b1d1277ffd27eb3134f55f51f38862/ludus-server/ansible/range-management/update.yml) — 2 plays | 1 | `ludus-server --update` | server |
| [`range-access.yml`](https://github.com/badsectorlabs/ludus/blob/f8d0295c77b1d1277ffd27eb3134f55f51f38862/ludus-server/ansible/range-management/range-access.yml) — 3 plays | `always` | `ludus range access` | S4 |
| [`pre-run-checks.yml`](https://github.com/badsectorlabs/ludus/blob/f8d0295c77b1d1277ffd27eb3134f55f51f38862/ludus-server/ansible/range-management/pre-run-checks.yml) | `always` | included by all of the above | — |
| [`user-defined-roles.yml`](https://github.com/badsectorlabs/ludus/blob/f8d0295c77b1d1277ffd27eb3134f55f51f38862/ludus-server/ansible/range-management/user-defined-roles.yml) | `always` | included by `ludus.yml` | — |

`ludus range deploy [-t tag,...]`. Plays are positions in the fixed 54-play
sequence; **class** is position relative to `user-defined-roles` (plays 37–39),
the only point we author into — see rule 8 and "Phases of a range asset" in
[the house standard](../standards/02-Ansible-Standards.md).

| Tag | Plays | Class | What it does |
| --- | --- | --- | --- |
| `network` | 2–8 | P | Deploy + configure the router; VLANs; user network rules; inbound/outbound WireGuard (Enterprise) |
| `access-control` | 5 | P | Apply user-defined network rules to the router. **Undocumented upstream**; rides on `network` |
| `vm-deploy` | 9–10 | P | Deploy DC VMs, then non-DC VMs, and ensure powered on |
| `assign-ip` | 11, 14 | P | Collect VM names; configure static IP + hostname |
| `dns-rewrites` | 15–17 | P | Add all hosts to router DNS; apply user DNS rewrite rules |
| `sysprep` | 18–19 | P | Sysprep Windows VMs whose config sets `sysprep: true` |
| `dcs` | 20–22 | P | Configure primary DC, then additional DCs |
| `windows` | 23–24 | P | Windows base config — autologon, firewall, RDP, SMB, network sharing |
| `additional-tools` | 25–26 | P | Firefox, Chrome, VS Code, Burp, 7zip, Process Hacker, ILSpy |
| `custom-choco` | 27–28 | P | User-defined chocolatey packages |
| `domain-join` | 29–30 | P | Join Windows VMs to the domain |
| `install-office` | 31–32 | P | Microsoft Office |
| `install-visual-studio` | 33–34 | P | Visual Studio |
| `linux-packages` | 35–36 | P | User-defined Linux packages |
| **`user-defined-roles`** | **37–39** | **A** | **Apply user-defined roles to VMs — every `get_sybers.*` task-role runs here** |
| `user-management` | 40 | N | Add an AD user that can RDP. **Undocumented upstream** |
| `nexus` | 41–45 | N | Deploy + configure the Nexus cache VM, generate its admin password |
| `share` | 46–48 | N | Deploy the Ludus Share VM (`readonlyshare`, `readwriteshare`) |
| `allow-share-access` | 49 | N | Allow anonymous SMB access on Windows VMs |
| `generate-rdp` | 50 | N | Write the RDP zip. Do not call directly — use `ludus range rdp` |
| `custom-groups` | 51 | L | Ansible groups for `ludus range inventory` |
| `debug` | 54 | N | One-off task for Ludus development |

**Classes.** **P** precondition — done before our stage, assume it, never
reimplement. **A** the authoring surface. **L** later — runs after us; needing it
means the work is S3. **N** opt-in `never` — absent unless invoked; needing it
means an S4 prerequisite sequenced first and declared in the blueprint's
`ludus-requirements.yml`. **Nexus is the one this catches** — under rule 4 a
range has no internet.
`ludus testing start | stop`,`ludus testing allow | deny --ip | --domain`. All`never`.

| Tag | Plays | What it does |
| --- | --- | --- |
| `start-testing` | 4–5 | Snapshot every VM where `testing.snapshot` is true or undefined; block those VMs from the internet |
| `stop-testing` | 6–9 | Revert every VM to its snapshot; re-allow the subnet; fix time and check password expiry on DCs, then on Windows endpoints/servers |
| `allow-ip` | 10 | Allow VMs to reach an IP |
| `allow-domain` | 11 | Allow VMs to reach a domain |
| `deny-ip` | 12 | Deny a previously allowed IP |
| `deny-domain` | 13 | Deny a previously allowed domain |

> `stop-testing` **reverts to snapshot** — it is not just "unblock the internet".
> Anything done since `start-testing` is lost. Plays 8–9 exist because reverting
> rolls the clock back and Windows/AD notice.

| Tag | Plays | What it does |
| --- | --- | --- |
| `startup-range` | 2 | Start up range VMs |
| `stop-range` | 3 | Shut down range VMs |
| `destroy-range` | 3–4 | Shut down, then destroy. `ludus range rm` |
| Tag | Plays | What it does |

|---|:--:|---|
| `update` | 2 | `ludus-server --update`. Server-level, not a range operation — and the thing that reverts local patches to stock files |
Not selectable; runs regardless of `-t`. Present in `ludus.yml` (collect VM
names, collect DCs, collect non-DC Windows, write `/etc/hosts`, check Office
status), `pre-run-checks.yml`, `range-access.yml`, `testing.yml` (router power-on,
gather VMs/IPs) and `user-defined-roles.yml`.
Consequence: **a `-t` run is never only that tag** — the `always` plays run too,
including pre-run checks. Useful, and the reason a tagged deploy is not free.
These playbooks live on the Ludus **server**, not in this repo, and
`ludus-server --update` overwrites them. Two routes, in order of preference:

1. **Upstream** — <https://github.com/badsectorlabs/ludus>. A fix that belongs in
   Ludus should go there; both undocumented tags above are reasonable PRs on
   their own (`gettags` and `tags.md` omit `access-control` and
   `user-management`).
2. **Don't** — rule 5. If a tag already does the job, invoke it. Most reasons to
   patch these files are actually reasons to use a tag properly.
