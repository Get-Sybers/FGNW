Blueprints shipped by this Ludus source. Each `blueprints/<id>/` directory holds
one blueprint:

```text
blueprints/<id>/
├── blueprint.yml
├── range-config.yml
├── requirements.yml
└── thumbnail.png
```

Reference: <https://docs.ludus.cloud/docs/using-ludus/sources>
A FGNW-themed multi-domain Active Directory lateral-movement lab: Hidden Leaf /
Hidden Sand / Sound-village domains plus the isolated Akatsuki forest, decoy
village content, and GHOSTS user emulation.

```text
blueprints/FGNW/
├── blueprint.yml
├── range-config.yml
├── requirements.yml
└── campaign/
```

There is a single range config. Variants are selected out of it at deploy time with
`ansible-playbook deploy.yml -e range_variant=<small|xl>` — `small` is a 9-VM single-node
subset, the default is the 22-VM range, and `xl` is all 23 including `modern-infra`. See
`FGNW/campaign/docs/RANGE-CONFIG-VARIANTS.md`.
`ludus source add` reads only the three files above. Everything else the range
needs to be *populated* after `ludus range deploy` — AD build, decoy content,
GHOSTS emulation, verification — lives under `campaign/` and is run by hand:

| Path | What it is |
| --- | --- |
| `campaign/deploy.yml` | the orchestrator — the only supported operator entry point |
| `campaign/deploy-tasks/phase*.yml` | one file per deploy phase, each named for its resume token — see `campaign/docs/DEPLOY.md` |
| `campaign/ansible/` | the FGNW-\*.yml playbooks and the AD-build roles they apply |
| `campaign/ad/NARUTO/` | AD data, providers, and scripts |
| `campaign/content/` | the range content corpus (AD users, OWA mail, websites, personas, decoy files) |
| `campaign/docs/` | deploy guide, campaign design, troubleshooting, plans |
| `campaign/tests/` | per-slice deploy fixtures |
| `campaign/ludus-requirements.yml` | Ludus **platform** prerequisites: templates to build, Nexus repos to create |

The `campaign/` tree is internally coupled by relative paths (`{{ playbook_dir }}/../content/…`,
`../ad/NARUTO/…`), so it moves as a unit — do not relocate pieces of it
individually.

### `target_node:` is a placeholder — edit it for your cluster

`range-config.yml` ships `target_node: pi-01` / `pi-02` / `pi-03` as neutral
placeholders. Ludus requires each `target_node:` to name a Proxmox node that
actually exists on your cluster, so before you deploy, replace every
`pi-0{1,2,3}` with the names of the Proxmox nodes you want each VM to land on.
A three-node cluster uses all three; a single-node cluster collapses them to
one name. The three bands keep the VM-to-node spread the blueprint was tuned
for (where the controller, Exchange, and the attacker live); match that spread
to your own cluster if you have the capacity, or override freely if you do
not.
The **FGNW-specific** range-VM task-roles these configs reference
(`get_sybers.range_ghosts_browser`, `get_sybers.range_recon_tooling`,
`get_sybers.range_ninjasploitable_server`) are vendored at `../../ansible/roles/`,
because that is the only path `ludus source add` reads.
The **shared** telemetry roles (`get_sybers.sysmon`, `get_sybers.sysmon_linux`,
`get_sybers.acsc_event_logging`) ship from the same `ansible/roles/` directory and
resolve from the per-user roles path at deploy, installed by `ludus source add`
of this source rather than via Ansible Galaxy.
`campaign/ansible/ansible.cfg` puts both `../../../../ansible/roles` (the vendored
FGNW roles) and the per-user roles tree on `roles_path`, so the campaign playbooks
that apply these roles by name (`FGNW-acsc-logging.yml`, `FGNW-sysmon-linux.yml`,
`FGNW-recon-tooling.yml`) resolve whether the role is vendored or source-installed.
Register the source and build the templates it needs:

```bash
ludus source add https://github.com/Get-Sybers/FGNW --all
ludus templates build -n win2022-server-x64-appxfix-template,win10-22h2-x64-enterprise-appxfix-template,win2022-exchange2019-x64-template,ninjasploitable-x64-server-template
# Hidden Sand Village (Sunagakure) runs on macOS — suna-ws1 (workstation) and suna-mail
# (Postfix/Dovecot). The macOS template builds in two phases around a one-time interactive
# install, and you must pin the installer ISO first — see templates/macos-sequoia-15/README.md.
ludus templates add -d templates/macos-sequoia-15
ludus templates build -n macos-sequoia-15-template   # PREPARE; after the interactive install, re-run the same command to FINALIZE
ludus blueprint apply <sourceID>/FGNW
```

**Hidden Sand Village is macOS** (as of blueprint 0.3.0): `suna-ws1` (Gaara's
workstation) and `suna-mail` run macOS Sequoia 15. The two Sand DCs (`wind-dc1`,
`suna-dc1`) stay Windows — macOS has no AD DS. mac-dev-playbook (homebrew +
dotfiles/dock/mas via `geerlingguy.mac`) is the dev-base layer; the campaign's
`fgnw_mac_*` roles rebuild the per-host roles the Windows path provided (GHOSTS
Universal client, Postfix+Dovecot mail server, browser defaults via the unified
`fgnw_browser_defaults` role, decoy files via the unified `fgnw_decoy_files`
role). AD membership is automated too — the `fgnw_mac_dsconfigad` role binds
both Macs to `sunagakure.wind.ninja` at the start of Phase 4d. See phases `1c`
and `4d` in `campaign/docs/DEPLOY.md`.

**Thunderbird is the mail client everywhere** (as of blueprint 0.4.0, Phase
`4e`): every workstation — Konoha / Oto / Akatsuki Windows plus Sand macOS —
gets Mozilla Thunderbird installed and preconfigured against its village mail
server by the unified `fgnw_thunderbird` role (`ansible_facts['os_family']` dispatch,
Chocolatey install on Windows + policies.json alongside the Phase-1c-staged
Homebrew cask on macOS). Phase 4e also enables `MSExchangeIMAP4` on each
Konoha / Oto / Akatsuki Exchange server with `LoginType: PlainTextLogin` so
Thunderbird can connect over VLAN-local IMAP+SMTP without TLS. Per-persona
identity is read from `content/ghosts/persona-timelines.yml`.

**The GHOSTS server is a `get_sybers.lxc` container** (as of blueprint 0.5.0, Phase
`1b`): the `get_sybers.lxc` collection's `deploy_ghost9_range` play, which phase 1b runs by
its collection-qualified name (`ansible-playbook get_sybers.lxc.deploy_ghost9_range`), creates CT `9000+N` (`r<N>-ghost9`) on the
range VNet at `10.<N>.99.51` from the published ghost9 template
(`ghcr.io/get-sybers/lxc/ghost9`, digest-pinned in `range-config.yml`
`ludus_extensions.ghost9`: Debian 13, GHOSTS 9.3.0 / API v9, n8n and Grafana as native
services) through the `get_sybers.lxc` roles — `lxc_preflight`, `lxc_ghost9`
`container`, `lxc_guest` `baseline`, `lxc_ghost9` `server` — and the clients keep
`ApiRootUrl http://10.<N>.99.51:5000/api`; the UI is on `:4200`, Grafana on `:3000`,
n8n on `:5678`. `requirements.yml` pins `get_sybers.lxc` as a git source (no release tag
yet) and its `community.proxmox` dependency; phase 1b runs as root on the PVE node that
hosts the Ludus server and needs a scoped Proxmox API token (`ghost9_ct_api_*` extra-vars).
The CT is not a Ludus range object: `ludus range rm` does not remove it —
`ansible-playbook get_sybers.lxc.deploy_ghost9_range -e @<extra-vars file> -t destroy -e lxc_guest_confirm_destroy=true` does. See phase
`1b` in `campaign/docs/DEPLOY.md`.

Then run the deploy. **Do not call `ludus range deploy` yourself** — `deploy.yml`
drives it as Phase 1, after bringing Nexus up in Phase 0:

```bash
cd /opt/ludus/sources/<sourceID>/blueprints/FGNW/campaign
ansible-playbook deploy.yml
```

Full procedure, variants and phase tokens: [`campaign/docs/DEPLOY.md`](campaign/docs/DEPLOY.md).
