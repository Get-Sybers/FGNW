The exact, ordered command sequence to stand up this range. Run everything as the
**range-admin** API identity unless noted:

```bash
export LUDUS_API_KEY='<range-admin RA key>'
```

There are twelve ordered phase tokens and **the order matters**. Containment is now
immediately after VM build/deploy (with the ghost9 CT built just before it, while the
server still has egress), and verification is embedded in the final emulation phase
rather than a separate trailing phase.
`range_from_phase` takes a **token**, and each token runs the `deploy-tasks/` file of
the same name:

| Token | Runs | Phase |
| --- | --- | --- |
| `0` | `deploy-tasks/phase0-nexus.yml` | Nexus cache |
| `1` | `deploy-tasks/phase1-vms.yml` | `ludus range deploy` — VM build |
| `1b` | `deploy-tasks/phase1b-ghost9.yml` | ghost9 CT — the GHOSTS 9.3.0 server, a `get_sybers.lxc` container created from the published ghost9 template (pre-containment) |
| `1c` | `deploy-tasks/phase1c-macos-base.yml` | macOS dev base — Homebrew + mac-dev-playbook on the Sand macOS hosts (pre-containment; brew/cask fetches need egress) |
| `2` | `deploy-tasks/phase2-containment.yml` | containment (`--testing`) |
| `3` | `deploy-tasks/phase3-ad.yml` | AD provisioning / Shinju build (two Sand DCs still Windows) |
| `4` | `deploy-tasks/phase4-content.yml` | content playbooks |
| `4b` | `deploy-tasks/phase4b-exchange.yml` | real Exchange + mail seed on the three remaining Exchange forests (Konoha / Oto / Akatsuki) |
| `4c` | `deploy-tasks/phase4c-threat.yml` | threat emulation |
| `4d` | `deploy-tasks/phase4d-mac-services.yml` | macOS service stack — `dsconfigad` AD bind to sunagakure.wind.ninja, then Postfix/Dovecot (Sand mail) + mac browser defaults + mac decoy files + GHOSTS Universal client |
| `4e` | `deploy-tasks/phase4e-thunderbird.yml` | Thunderbird mail client — enable `MSExchangeIMAP4` on each village Exchange + install/preconfigure Thunderbird on every workstation (Konoha / Oto / Akatsuki Windows ws → village Exchange; Sand macOS ws → Postfix/Dovecot) |
| `5` | `deploy-tasks/phase5-emulation.yml`, then `deploy-tasks/phase5-verify.yml` | GHOSTS emulation, then verification |

Token order is the execution order: `0 1 1b 1c 2 3 4 4b 4c 4d 4e 5`. Resuming at a token
runs that phase and every phase after it.
That list is defined once, in `campaign/vars/common.yml`, and loaded by `deploy.yml`.
The deploy-pipeline version is `version:` in [`blueprint.yml`](../../blueprint.yml) (0.5.0). Bump
the minor when the phase sequence or a phase's contract changes, and record the change in the root
`CHANGELOG.md`.

**This is the only supported operator path. There should be no SSH hop in the deploy
procedure.**
Run from the `campaign/` directory of the registered source on the Ludus host.
`ludus source add` clones to `/opt/ludus/sources/<sourceID>/` — `/opt/ludus/blueprints/`
is part of the Ludus install and stays empty:

```bash
cd /opt/ludus/sources/<sourceID>/blueprints/FGNW/campaign
ansible-playbook deploy.yml
ansible-playbook deploy.yml -e range_variant=small
ansible-playbook deploy.yml -e range_variant=xl
ansible-playbook deploy.yml -e range_from_phase=4b
ansible-playbook deploy.yml -e range_skip_exchange=true
```

`deploy.yml` drives Phase 0 (Nexus), Phase 1 (`ludus range deploy` against the selected
range config), then the Phase 2–5 composition. It is the only orchestrator; to run just
the tail, resume it with `-e range_from_phase=<token>`.
Tags are per-playbook namespaces; the full reference is
[`doc/ludus/ludus-deploy-tags.md`](../../../../doc/ludus/ludus-deploy-tags.md). All tag classes used here apply to
`ludus.yml` (the range-deploy playbook) unless stated. Machine-readable inventory of every
tag and its status for this blueprint lives in `ludus-requirements.yml` §`ludus_deploy_tags`.
`ludus range deploy -t nexus` — the `nexus` tag is **never-tagged** (does not run in a
plain deploy). Phase 0 invokes it explicitly to bring the server-wide Nexus cache up before
any VM exists. All subsequent phases rely on Nexus because the range runs in `--testing`
mode and has no internet access once Phase 5 containment is active.
Plain `ludus range deploy` (no tag filter) runs the full built-in stage order so Ludus
handles its own pre-requisites in the correct sequence without reimplementing them:

| Tag | Class | Status in this blueprint |
| --- | --- | --- |
| `network` | P | ✓ Active — bridges, VLANs, routing for all VMs |
| `access-control` | P | ✓ Active — Proxmox firewall rules |
| `vm-deploy` | P | ✓ Active — creates VMs from named templates |
| `assign-ip` | P | ✓ Active — static IPs from range config |
| `dns-rewrites` | P | ✓ Active — 144+ rewrite entries on attacker-vm |
| `sysprep` | P | ✓ Active — all Windows VMs have `windows.sysprep: true` |
| `dcs` | P | **no-op** — promotes a `windows.domain:` VM to DC; no VM sets `windows.domain:` because the multi-forest AD topology (Land of Fire + Konoha, Land of Wind + Suna, Sound, Akatsuki-C2) is built by Shinju in Phase 2, not by Ludus |
| `windows` | P | ✓ Active — WinRM, base config on all Windows VMs |
| `additional-tools` | P | **no-op** — no VM sets `windows.install_additional_tools: true` |
| `custom-choco` | P | **no-op** — no VM sets `windows.chocolatey_packages:`; tool installs happen in Phase 3 via get_sybers.range_recon_tooling |
| `domain-join` | P | **no-op** — joins Windows VMs when `windows.domain:` is set; not set in any range config; Windows members are joined by Shinju in Phase 2; the one Linux domain join (ninjasploitable) uses FGNW-ninjasploitable-join.yml in Phase 3 because Ludus's tag only handles Windows |
| `install-office` | P | **no-op** — no VM sets `windows.office_version` |
| `install-visual-studio` | P | **no-op** — no VM sets `windows.visual_studio_version` |
| `linux-packages` | P | ✓ Active — attacker-vm declares `linux.packages: [ca-certificates]`; the only explicit usage in the range config |
| `user-defined-roles` | **A** | ✓ Active — every `roles:` entry per-VM runs here (plays 37–39) |
| `custom-groups` | L | **no-op** — no VM sets `ansible_groups:`; play 51 runs but builds no groups |

Class N tags **not needed** by this blueprint: `share`, `allow-share-access`, `user-management`,
`generate-rdp`, `debug`. None are invoked.
Phase 2 calls `get_sybers.range.ludus_testing`, which issues `ludus testing start`. These
tags belong to `testing.yml` (a separate Ludus playbook) — they are not part of
`ludus range deploy`. Every VM in all three range configs has
`testing: {snapshot: true, block_internet: true}`, so start-testing snapshots and seals
every VM, with no egress carve-outs. Verify with `ludus testing status` after Phase 2
completes.
Testing tags **not used**: `stop-testing` (run manually between scenario iterations),
`allow-ip`, `deny-ip`, `deny-domain`.

```text

Full deploy:       0 → 1 → 1b → 1c → 2 → 3 → 4 → 4b → 4c → 4d → 4e → 5
Post-build only:                      2 → 3 → 4 → 4b → 4c → 4d → 4e → 5

```

Containment now runs as **Phase 2**, immediately after VM build/deploy, and emulation
still starts only inside the sealed range (final Phase 5).
**Isolation model:**

- Every VM in the range configs now has `testing: {snapshot: true, block_internet: true}`.
- `ludus testing start` (Phase 2) snapshots all VMs and blocks all internet.
- Containment seals the range completely — no egress carve-outs.
- `ludus testing stop` reverts all VMs to the pre-Phase-2 snapshot (repeatable scenario runs).
**Why `ludus range deploy` alone does not stand up the scenario:**
`ludus range deploy` runs only the `roles:` declared per-VM in the range config. Everything
in Phases 2–5 (containment, AD build, Exchange, content seeding, campaign primitives,
emulation + verify) is cross-host post-build orchestration that cannot run as a single-VM role. A
range deployed without `deploy.yml` has VMs with roles applied but no AD, no mail, no
content, no personas, and no isolation.
For operators who DO have direct server access, run the Ansible orchestrator directly from the
blueprint checkout on the Ludus host:

```text

cd /opt/ludus/sources/<sourceID>/blueprints/FGNW/campaign
ansible-playbook deploy.yml
ansible-playbook deploy.yml -e range_variant=small
ansible-playbook deploy.yml -e range_variant=xl
ansible-playbook deploy.yml -e range_from_phase=4b
ansible-playbook deploy.yml -e range_fresh=true

```

**Deploy rules (encoded by `deploy.yml` and the phase tasks):**

1. **Ludus-first** — all range interaction is via `ludus` CLI (`range …`, `testing …`); no
   `qm`/`pvesh`/DB/filesystem poking to inspect or mutate range state unless no `ludus`
   command exists.
2. **Never destroy Nexus** — Nexus (192.0.2.2) is persistent server-wide infra, not a range
   VM. Teardown is `ludus range rm` (range-scoped); `-e range_fresh=true` skips Phase 0.
3. **Fix at build phase, documented** — deploy issues are fixed in the role/config/playbook
   and documented, never as a manual live-only command that containment would later break.
4. **Contain immediately after VM deploy** — Phase 2 runs directly after Phase 1.
5. **Exchange is default** — Phase 4b runs by default; `-e range_skip_exchange=true` opts
   out. ⚠️ The `aleemladha.ludus_exchange` role uses an Exchange 2019 ISO cached at
   `/opt/ludus/resources/iso` when it is present and otherwise attempts a ~6 GB download, which
   Phase-2 containment blocks. Stage the ISO before Phase 4b, or deploy with
   `-e range_skip_exchange=true`. See TROUBLESHOOTING.md.
`deploy.yml` polls `ludus range list --json` for `rangeState == SUCCESS` before moving on, derives
the range's second octet and the live per-deploy Debian SSH password automatically (no
manual `sed`/`ludus range inventory` lookups needed), and injects that Debian password into the
materialized infra inventory as a `[linux_infra:vars]` group var (ghosts/kali keep their own
per-host creds) so `FGNW-sysmon-linux.yml` runs as a single call — no per-play
`-e ansible_ssh_pass`, no `--limit` split. It runs **every** play in the phase sequence below — including
`FGNW-persona-autologon.yml` (Phase 4) and **Phase 4b Exchange by default** (real
Exchange 2019 install + mail seed — Exchange is a default part of the deploy, not opt-in). Flags:

- `range_skip_nexus=true` if the Nexus cache is already up (it's persistent, server-wide infra — see Phase 0).
- `range_skip_exchange=true` to opt OUT of Phase 4b for a quick run that doesn't need mail.
- `range_from_phase=<token>` to resume partway through instead of re-running earlier (slow)
  phases, e.g. after fixing an issue:
  `ansible-playbook deploy.yml -e range_variant=small -e range_from_phase=3`.
  Phase tokens match this doc's phase numbers (`0 1 1b 1c 2 3 4 4b 4c 4d 4e 5`).
It is **not** idempotent against an already-deployed range when run from phase 0 — Phase 1
reconfigures and redeploys the VMs. Use `-e range_from_phase=<token>` to resume/re-apply later phases
against a range that's already up, the same way you'd re-run one of the manual commands
below by hand.
**Run the Ansible orchestrator directly.** The sanctioned server-side entry point is
`deploy.yml`:

```text

ansible-playbook deploy.yml
ansible-playbook deploy.yml -e range_from_phase=4b
ansible-playbook deploy.yml -e range_fresh=true

```

It exists because the deploy needs a Ludus API key, and the orchestrator handles that through the
existing Ludus auth role instead of a shell wrapper.
**`range_fresh=true` is the exception, not the default.** Use it **only** when `range-config.yml`
has changed or the VM templates have changed. A plain re-deploy is idempotent and re-applies roles
without rebuilding VMs, so a resume is almost always the right move. `range_fresh` stays an opt-in
variable on this same entry point rather than a separate command.
**`range_fresh=true` teardown is two steps, in this order:**

1. **Normal destroy** — `ludus range rm` (aliases `rm-vms`, `destroy`). Destroys every VM but **keeps
   the range object**, which is literally what its help calls *"use this to start fresh with your range
   configuration."* The range object carries the range ID, user assignment and labels.
2. **Confirm removal** — poll until `rangeState == DESTROYED` **AND** `.VMs | length == 0`.

> ⚠ **`rangeState: DESTROYED` is not proof the VMs are gone.** Because step 1 keeps the range object,
> that state is fully compatible with VMs still existing — `DESTROYED` can be returned with
> **VMs still `poweredOn: true` in the same API response**. A state-only guard would then conclude
> "nothing to tear down", destroy nothing, and rebuild on top of stale VMs (old disk state, old AD
> membership), which is why the teardown also requires `.VMs | length == 0`.
`ludus range rm-range` (alias `destroy-range`, `--force`) additionally deletes the range **object**.
It is the heavier hammer and is **not** run automatically — if the normal destroy leaves VMs behind,
the teardown fails loudly and prints that command rather than escalating on its own.
**Containment is ON by default** for this range. The server-side orchestrator exposes
`range_testing`, and the shared Phase 2–5 composition intentionally always runs Phase 2.
**Direction of travel: keep orchestration in Ansible.** The deploy entry point should do no more
than run the Ansible deploy, parameterised by which variant (small vs full) and whether server-side
teardown is requested. The genuinely Ludus-native bits are Phase 0/1 (`range deploy`, `range config
set`) and Phase 2 (`testing start`/`allow`/`status`); those stay driven through the Ansible phase
tasks rather than ad-hoc shell wrappers.
The phase-by-phase commands below remain the reference for what each phase actually does,
for debugging a specific phase, or for running a step manually without the wrapper.

---
The shared Ludus Nexus cache is server-wide infra used by every range. Deploy it
once and leave it running. If it is ever rebuilt, just re-run the configure playbook.

```text

ludus range deploy -t nexus
ansible-playbook /opt/ludus/users/range-admin/.ansible/collections/ansible_collections/get_sybers/infra/playbooks/nexus-setup.yml

```

- `nexus-setup.yml` is idempotent and self-retrieves the Nexus admin password
  (from `/opt/ludus/users/range-admin/nexus-admin-password` or
  `/opt/ludus/install/nexus-admin-password`, falling back to `ludus range logs`).
- This makes the PowerShell Gallery available to Windows ranges through the cache,
  so the AD build (Phase 3) works without hammering the public internet.

```text

ludus range config set -f ../range-config.yml
ludus range deploy
ludus range list

```

`range-config.yml` is the only range config, and setting it by hand deploys all 23 VMs.
To deploy a variant, let `deploy.yml` cut it out of the superset for you — that is the
supported path, and it writes the rendered config into your own `users/` tree:

```text

ansible-playbook deploy.yml -e range_variant=small
ansible-playbook deploy.yml
ansible-playbook deploy.yml -e range_variant=xl

```

See [`RANGE-CONFIG-VARIANTS.md`](RANGE-CONFIG-VARIANTS.md) for the selection model.
The config has **no `network:` block** — normal networking. Blocking is applied later
(Phase 2) via testing mode, not a persistent firewall drop.
`deploy-tasks/phase1b-ghost9.yml` reads the range config's root-level
`ludus_extensions.ghost9` placement contract (`vlan`, `ip_last_octet`, `hostname_suffix`,
`api_port`, `ui_port`, `cores`, `memory_mb`, `rootfs_gb`, `template_image`,
`template_version`), writes it with the range number, the PVE token and the server
secrets into an owner-only extra-vars file (`~/.FGNW-deploy/ghost9-ct-vars.yml`, 0600,
shredded by the cleanup step) and runs `campaign/ansible/ghost9-range-ct.yml` with it.
That play composes the `get_sybers.lxc` collection (a git pin in
`blueprints/FGNW/requirements.yml`): FGNW's own read-only range preflight (the VNet
`r<N>` declared in `/etc/pve/sdn/vnets.cfg` and present on the node, its MTU readable, no
`*-ghosts` VM on the cluster), `lxc_preflight` (root, PVE node, `pct`), then `lxc_ghost9`
`container` — `lxc_guest` pulls the published ghost9 template
(`ghcr.io/get-sybers/lxc/ghost9`, digest-pinned to the `v0.1.1` tag: Debian 13, GHOSTS
9.3.0 / API v9, n8n and Grafana as native `systemd` services) into
`local:vztmpl/ghost9.tar` with Proxmox's OCI registry pull and creates CT `9000+N`
(`r<N>-ghost9`, pool `GHOST9`, unprivileged, `nesting=1`, `onboot=1`) on the range VNet
`r<N>` tag 99 at `10.<N>.99.51/24` gw `.254` with the bridge's MTU — a placement
postcheck re-reads `net0` from Proxmox; then `lxc_guest` `baseline` and `lxc_ghost9`
`server` run inside the CT over `community.proxmox.proxmox_pct_remote` (in-guest
firewall, PostgreSQL role/db, site config for the range address, service start, n8n
provisioning, health check). `campaign/ansible/ghost9-verify.yml -e ghost9_ct_range_number=<N>`
re-proves the API (`/swagger/v9/swagger.json` is `v9`, `/api/machines` answers), the UI
on `:4200` and — on the CT's node — the two guest markers, read-only.

**Prerequisites for phase 1b.** `deploy.yml` runs as root on the PVE node that hosts the
Ludus server (`pct`, `/etc/pve` and the OCI pull are root-only); Proxmox VE 9.1+ (the
`oci-registry-pull` storage API); the node reaches `ghcr.io` (or a mirror — point
`template_image` at it); ansible-core >= 2.19 with `python3-proxmoxer` and
`python3-requests` on that node; the collections of `blueprints/FGNW/requirements.yml`
installed by `ludus source add` (`get_sybers.lxc` from its git pin, `community.proxmox`
2.1.0); and a scoped Proxmox API token (`ghost9-deploy@pve`, pool `GHOST9`, minted by the
cluster collection) passed to `deploy.yml` as `-e @<0600 file>` defining the four
`ghost9_ct_api_*` vars — never inline on argv; the phase fails with instructions if the
token is absent.

**Ports.** The template's in-guest `nftables` firewall opens the API `:5000`
(`ApiRootUrl http://10.<N>.99.51:5000/api`, the same contract every client already
carries), the UI `:4200`, Grafana `:3000` and n8n `:5678` on the range VLAN; PostgreSQL
stays loopback-only.

**Secrets.** `ghost9_db_password`, `ghost9_n8n_owner_password` and
`ghost9_n8n_owner_email` (default `admin@ghosts.local`) are taken from `deploy.yml`'s
extra-vars when supplied; otherwise the two passwords are generated per deploy
(`lookup('password')`, 32 letters and digits) into 0600 files under `~/.FGNW-deploy/`
and written only into the 0600 extra-vars file — all of which the cleanup step shreds.
Generated n8n owner credentials are therefore not retained after the run: to keep n8n
access, supply the secrets to `deploy.yml` yourself.

**Known behaviour.** The server is GHOSTS 9.3.0 (the clients remain v9.0.0, on API v9).
Grafana (`:3000`) and n8n (`:5678`) are reachable on the range VLAN because the
template's firewall opens them. The template's API keeps GHOSTS' LLM animation settings
at their upstream defaults — a property of the `get_sybers.lxc` template; no Ollama
exists in the range. `lxc_guest` pulls the image only while `local:vztmpl/ghost9.tar` is
absent from the node's template cache, so a re-pin of `template_image` /
`template_version` needs that cached file removed first (and the CT recreated —
`lxc_ghost9` `server` refuses a guest whose marker carries another release). Ordering
is load-bearing: **after** Phase 1 (the CT attaches to the
range's SDN VNet, which `ludus range deploy` builds) and **before** Phase 2 (the OCI pull
needs the node's egress, and the CT is not a Ludus range object — containment neither
snapshots nor blocks it, and Phase 5 emulation needs it live). `ludus range rm` and the
`ludus testing` snapshots do **not** cover this CT; it is removed with
`ansible-playbook ghost9-range-ct.yml -e @<extra-vars file> -t destroy -e lxc_guest_confirm_destroy=true`
(the same range number and token vars — write a fresh 0600 file; the deploy's copy was
shredded). See the LIFECYCLE WARNING in `ansible/ghost9-range-ct.yml`.
The AD forests/domains/trusts/users are a **separate manual step**. It uses two merged
inventories keyed by `dict_key`; substitute `RANGENUMBER` with this range's second
octet (the `N` in the `10.N.0.0/16` network shown by `ludus range list`).
The AD-build inventory is **Windows-AD-hosts only** — the Phase-3 content plays target the
Windows AD host groups (dc/server/domain), so Linux infra + GHOSTS/OWA aliases must NOT be in
it (they live in the `*-infra` inventory used in Phases 4-5). For the SMALL range, the AD data
model must also be the 3-domain `config-small.json`.
**Never copy `config-small.json` over `config.json`.** That is the retired mechanism: it wrote
a *tracked* file, and a run killed before its restore left small AD data in `config.json`,
which every later resume skips past and which `fgnw_exchange_seed_mail` and
`FGNW-ninjasploitable-join` read at runtime. Copy the variant's config into a scratch dir and
repoint the chain with `-e data_path=` instead — extra-vars outrank the `data_path` default each
play sets for its `vars_files: {{ data_path }}/config.json`, so one flag repoints the whole chain.
`deploy.yml` does exactly this (into `~/.FGNW-deploy/ad-data/`).

```text

cd /opt/ludus/sources/<sourceID>/blueprints/FGNW/campaign/ansible
install -d -m 0700 ~/.FGNW-deploy/ad-data
install -m 0600 ../ad/NARUTO/data/config-small.json ~/.FGNW-deploy/ad-data/config.json
sed 's/RANGENUMBER/<N>/g' ../ad/NARUTO/providers/ludus/inventory-small.yml > /tmp/prov-inv.yml
for playbook in tgtdelegation.yml ad-data.yml lat.yml reboot.yml adcs.yml; do
  timeout 30m ansible-playbook -i ../ad/NARUTO/data/inventory-small -i /tmp/prov-inv.yml \
    -e data_path=$HOME/.FGNW-deploy/ad-data "$playbook"
done

```

- **Full range:** use `../ad/NARUTO/data/inventory` + `../ad/NARUTO/providers/ludus/inventory.yml`
  (AD-only, RANGENUMBER-substituted) and `config.json` (it has all 6 domains) as the
  `data_path` source.
- AD hosts are named by `dict_key` (dc01/dc02/dc05/srv03/srv08…); WinRM is https/5986.
- Promotion / join / trust are native (phase 1 `ludus range deploy`) and not in this tail, so
  there is no promotion re-run hazard here; the tail plays (content + attack primitives) are
  idempotent and safe to re-run.
- The `common` role auto-detects the Nexus (192.0.2.2:8081) and installs
  PackageManagement/PowerShellGet (+ the bundled NuGet provider) and the DSC modules
  from the `powershell-proxy` cache; it falls back to the internet if the Nexus is absent.
  It also points each host's DNS at its DC first (router as fallback) so the cross-forest
  trust setup can resolve the other forest (fixes A12).
Run with the **infra** inventory (`inventory-small-infra.yml` / `inventory-infra.yml` —
real-hostname `linux_infra`/`ghosts_clients`/`exchange_servers` groups), NOT the AD-build
inventory. Materialize it too. Order matters (later ones preflight earlier HTTP targets):

```text

sed 's/RANGENUMBER/<N>/g' ../ad/NARUTO/providers/ludus/inventory-small-infra.yml > /tmp/infra-inv.yml
ansible-playbook -i /tmp/infra-inv.yml FGNW-attacker-web.yml
ansible-playbook -i /tmp/infra-inv.yml FGNW-themed-sites.yml
ansible-playbook -i /tmp/infra-inv.yml FGNW-recon-tooling.yml
ansible-playbook -i /tmp/infra-inv.yml FGNW-ninjasploitable-content.yml
ansible-playbook -i /tmp/infra-inv.yml FGNW-ninjasploitable-join.yml
ansible-playbook -i $(pwd)/../ad/NARUTO/data/inventory-small -i /tmp/prov-inv.yml dnsforwarder.yml
ansible-playbook -i /tmp/infra-inv.yml FGNW-persona-autologon.yml
ansible-playbook -i /tmp/infra-inv.yml FGNW-decoy-content.yml
ansible-playbook -i /tmp/infra-inv.yml FGNW-browser-defaults.yml
ansible-playbook -i /tmp/infra-inv.yml FGNW-browser-extensions.yml
ansible-playbook -i /tmp/infra-inv.yml FGNW-acsc-logging.yml
ansible-playbook -i /tmp/infra-inv.yml FGNW-sysmon-linux.yml

```

If the range was rebuilt, clear the old SSH host keys first or the Linux plays fail with
`REMOTE HOST IDENTIFICATION HAS CHANGED`:
`for ip in <attacker> <ninjasploitable> <ghosts> <kali>; do ssh-keygen -f /root/.ssh/known_hosts -R $ip; done`
Linux hosts use the `debian` user with a per-range password. The deploy orchestrators inject it into the
materialized infra inventory automatically (as a `[linux_infra:vars]` group var). For a by-hand run,
get it from `ludus range inventory` and add `ansible_ssh_pass=<pw>` under `[linux_infra:vars]` in the
materialized inventory (ghosts/kali override it per-host, so this is safe for the whole group).
Phase 4b is a default phase: `deploy.yml` runs it automatically between Phase 4 and Phase 5, and
`-e range_skip_exchange=true` opts out. `FGNW-exchange.yml` (real per-forest Microsoft Exchange
2019) and `FGNW-exchange-seed-mail.yml` (real `Send-MailMessage` delivery of the
`content/OWA/user-inboxes.yml` quote corpus + LOE 2's alert messages) are the mail mechanism on the
three Windows mail servers — `konoha-mail` (Leaf), `oto-mail` (Sound) and `dark-mail` (Akatsuki).
The Sand forest's `suna-mail` is a macOS Postfix/Dovecot host (Phase 4d), not Exchange. On the small
range only `konoha-mail` exists (70 Leaf mailboxes, send connectors, OWA), so Phase 4b installs mail
there; on the full range each Windows mail server is installed one forest at a time — see the
commands below and [`OWA-REAL-VS-SIMULATED.md`](OWA-REAL-VS-SIMULATED.md).
Run manually, after Phase 4 (content) and before Phase 5 (emulation start):
**Small range**: only `konoha-mail` exists (`oto-mail`/`dark-mail` do not) — use
`inventory-small-infra.yml`. **Full range**: the three Windows mail servers exist — use
`inventory-infra.yml` (`suna-mail` is macOS Postfix/Dovecot, stood up in Phase 4d, not here). The
small range's own AD-build inventory never included `konoha-mail`, so `FGNW-exchange.yml`'s first
play domain-joins it directly — no separate manual step needed.

```text

sed 's/RANGENUMBER/<N>/g' ../ad/NARUTO/providers/ludus/inventory-infra.yml > /tmp/infra-inv.yml
ansible-playbook -i /tmp/infra-inv.yml FGNW-exchange.yml --limit konoha-mail
ansible-playbook -i /tmp/infra-inv.yml FGNW-exchange-seed-mail.yml --limit konoha-mail
ansible-playbook -i /tmp/infra-inv.yml FGNW-exchange.yml --limit oto-mail
ansible-playbook -i /tmp/infra-inv.yml FGNW-exchange-seed-mail.yml --limit oto-mail
ansible-playbook -i /tmp/infra-inv.yml FGNW-exchange.yml --limit dark-mail
ansible-playbook -i /tmp/infra-inv.yml FGNW-exchange-seed-mail.yml --limit dark-mail
ansible-playbook -i /tmp/infra-inv.yml FGNW-owa-cert.yml

```

Both playbooks need `ANSIBLE_ROLES_PATH=/opt/ludus/users/range-admin/.ansible/roles`
exported first when run directly via `ansible-playbook` (not through `ludus range deploy`,
which sets this automatically) — otherwise the vendored `aleemladha.ludus_exchange` role
won't resolve.

- **Cached ISO — avoid the ~6 GB download.** The `aleemladha.ludus_exchange` role caches the
  Exchange 2019 CU15 ISO (~6.0 GB) at
  `/opt/ludus/resources/iso/ExchangeServer2019-x64-cu15.iso` and guards its download step with
  `when: not exchange_iso_check.stat.exists`, so when the ISO is staged there the download is
  **skipped** and the install needs no live internet for it. Stage it before Phase 4b (containment
  blocks the fetch). **The cached ISO must stay readable by the `ludus` OS user** (the Ansible
  controller runs as `ludus`): keep it `ludus:ludus 0664` — if it lands `root:root 0660`, the
  role's "Copy Exchange ISO to windows host" step fails on read. If the file is missing, the role
  attempts the ~6 GB fetch over live internet. `FGNW-exchange.yml` reboots the VM multiple times
  during prereq install, so budget real time; a clean repeat against an already-installed host is
  minutes.
- `FGNW-exchange-seed-mail.yml`'s **send** is not idempotent — delivering the corpus twice
  duplicates every message — but the **decision to send is guarded per forest**. On a
  successful seed the role writes an end-of-seed marker
  (`C:\ProgramData\FGNW\seed-mail.done`) on that forest's own Exchange server, and the play
  probes for it before including the role. So a resume (`-e range_from_phase=4b` or lower) is
  a no-op for every already-seeded forest.
  - A seed that failed part-way leaves **no** marker, and is seeded again on the next run —
    the marker is written only after the whole send loop succeeded, so it can never be
    satisfied by a partial delivery the way a mailbox message count could.
  - To deliver the corpus again anyway, pass `-e force_reseed=true` (to `deploy.yml` or
    the play directly). Expect duplicates; that is the opt-in.
  - Still run it only after that forest's `FGNW-exchange.yml` run has completed successfully.
**Runs immediately after Phase 1.** GHOSTS's browsing targets (attacker sinkhole, OWA,
ninjasploitable) are all intra-range, so there is no functional reason to wait until
after emulation is running. Containing first also means emulation starts in the actual
end-state network posture instead of a temporarily-open one, so there's no window where
"looks deployed" and "actually contained" disagree.
Testing mode is the supported way to block a range from the internet (see the Ludus
networking/testing docs — the `network.rules` schema's `public` key either allows all
internet or none).

```text

ludus testing start
ludus testing status
ludus testing stop

```

```text

ansible-playbook -i /tmp/infra-inv.yml FGNW-ghosts-activity.yml

```

Kept as its own step (not bundled with AD provisioning) because provisioning needs
package access while emulation must run contained. Run this AFTER Phase 2 (containment) —
see above for why the range should already be contained before emulation starts.
**Personas run on the operator's local clock; "no activity" is often just off-shift.**
`persona-overrides.yml`'s `active_hours` are **local wall-clock time** (default
`08:00:00`-`18:00:00`) — write the time you want to *see* the personas working and do no UTC
maths. This playbook converts them to the `UtcTimeOn`/`UtcTimeOff` GHOSTS compares against
(range VMs run UTC), using this Ludus host's timezone, so it follows DST. The playbook prints
the mapping as it renders, e.g. `local 08:00:00-18:00:00 (UTC+0930) -> UTC 22:30:00-08:30:00`.
A local window normally **wraps midnight UTC** (`UtcTimeOn` > `UtcTimeOff`). That is expected and
correct — GHOSTS honours a wrapping window (verified on this range).
**Out of hours the personas do not go silent** — they keep ~10% of their activity running, so the
range isn't trivially "all traffic is 09:00-17:00". This renders as a second set of handlers on
the complement of the day window (the same events, delays multiplied — 12.6x for the default
08:00-18:00), which is why `timeline.json` has 8 handlers rather than 4. Tune or disable it:

```text

-e fgnw_ghosts_night_share=0.05
-e fgnw_ghosts_night_share=0

```

Only one shift is ever in-window at a time; the dormant one logs nothing. So outside *both*
windows-worth of events — i.e. a persona set to `night_share=0` after hours — GHOSTS is running
correctly but idle, logging only Quartz's `Batch acquisition of 0 triggers`.

```text

(Get-Date).ToUniversalTime()
(Get-Content C:\ludus\ghosts-client\config\timeline.json -Raw | ConvertFrom-Json).TimeLineHandlers |
  ForEach-Object { $_.UtcTimeOn + '-' + $_.UtcTimeOff }

```

If the operator is not in this server's timezone, pin the offset:
`ansible-playbook -i /tmp/infra-inv.yml FGNW-ghosts-activity.yml -e fgnw_ghosts_tz_offset=+0930`
Healthy emulation looks like: `ghosts` running in **session 1** (never session 0 — see the
interactive scheduled-task note), a timeline with events, and browser/cmd processes spawning
while in-window. To watch it on demand outside the window, temporarily widen
`UtcTimeOn`/`UtcTimeOff` in `timeline.json`, restart the `ghosts` scheduled task, then re-run
this playbook to restore the real timeline. Do **not** move the VM clock — these are AD-joined
hosts and Kerberos rejects >5 minutes of skew.
Check spawns against the ghosts process start time; stale browser/cmd processes from an earlier
run otherwise read as activity:

```text

$g = Get-Process ghosts
Get-Process chrome,firefox,msedge,cmd -ErrorAction SilentlyContinue |
  Where-Object { $_.StartTime -gt $g.StartTime }

```

Two new read-only, re-runnable playbooks — run them last, against the infra inventory,
to confirm the range is actually healthy instead of assuming a clean `ludus range deploy`

- no errors from the phases above means everything is working end-to-end:

```text

ansible-playbook -i /tmp/infra-inv.yml FGNW-verify-connectivity.yml
ansible-playbook -i /tmp/infra-inv.yml FGNW-verify-emulation.yml

```

- `FGNW-verify-connectivity.yml` checks: HTTP reachability from `konoha-ws1` to the
  attacker tool-cache / ninjasploitable report intake / the real Exchange OWA login page
  by DNS name (`https://mail.<domain>/owa/auth/logon.aspx`, cert validation disabled);
  and per-forest OWA cert-trust (best-effort). It prints a PASS/FAIL line per check, then
  a final `"GATE: assert every required check passed"` task **fails the play** (non-zero
  exit) if any required check did not pass — a clean exit means everything passed, not
  merely that the checks ran. Still safe to run at any point, including after
  containment — all its checks are intra-range, so nothing here is expected to start
  failing once `ludus testing start` is live.
- `FGNW-verify-emulation.yml` queries the GHOSTS API directly
  (`http://<ghosts_ip>:5000/api/machines`) and reports, per `ghosts_clients` host,
  whether it's registered, its `status`, and how stale its `lastReportedUtc` is (anything
  over 15 minutes old is flagged FAIL) — a repeatable check rather than a hand-run curl. It too ends in a gate
  (`"GATE: fail if any ghosts_clients host is unregistered or reporting stale telemetry"`)
  that **fails the play** if any `ghosts_clients` host is unregistered or stale, rather
  than just logging it.
Tear down with `ludus range rm`.

---
Or use the client/server orchestrator above for the small variant — see the invocation sections earlier in this document.

| | | |
| --- | --- | --- |
| 0 | Nexus (once) | `ludus range deploy -t nexus` → `ansible-playbook /opt/ludus/users/range-admin/.ansible/collections/ansible_collections/get_sybers/infra/playbooks/nexus-setup.yml` |
| 1 | VMs | `ansible-playbook deploy.yml -e range_variant=small` (renders the small variant out of `range-config.yml`, sets it, deploys) |
| 2 | Containment | `ludus testing start` |
| 3 | AD build | Promotion / child domains / joins / the fire↔oto trust are **native** — they run in phase 1 `ludus range deploy` (see `range-config.yml`). Phase-3 tail only: materialize inventory → run `tgtdelegation.yml → ad-data.yml (fgnw_ad_mgmt content) → lat.yml → reboot.yml` (+ `adcs.yml`). Defender-disable is native now (`windows.gpos: [disable_defender]`, phase 1) |
| 4 | Content | `FGNW-attacker-web.yml`, `FGNW-themed-sites.yml`, `FGNW-recon-tooling.yml` (regular/xl), `FGNW-ninjasploitable-content.yml`, `FGNW-ninjasploitable-join.yml`, `dnsforwarder.yml`, `FGNW-persona-autologon.yml`, `FGNW-decoy-content.yml`, `FGNW-browser-defaults.yml`, `FGNW-browser-extensions.yml`, `FGNW-acsc-logging.yml`, `FGNW-sysmon-linux.yml` |
| 4b | Exchange (default) | `FGNW-exchange.yml` → `FGNW-exchange-seed-mail.yml` (`--limit konoha-mail` small; the three Windows forests one-at-a-time full) → `FGNW-owa-cert.yml` (once) |
| 4c | Campaign primitives | `FGNW-campaign-setup.yml` (Kerberoast SPN + AS-REP, Leaf) — runs against konoha-dc1 via provider inventory |
| 4d | macOS services | `FGNW-mac-ad-bind.yml` → `FGNW-mac-mail.yml` (Sand Postfix/Dovecot) → `FGNW-mac-services.yml` |
| 4e | Thunderbird | `FGNW-thunderbird.yml` (Exchange IMAP enable + Thunderbird on every workstation) |
| 5 | Emulation + Verify | `FGNW-ghosts-activity.yml` → `FGNW-verify-connectivity.yml` + `FGNW-verify-emulation.yml` |
| 7 | Teardown | `ludus range rm` |
