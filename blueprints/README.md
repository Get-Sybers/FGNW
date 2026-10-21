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
The **FGNW-specific** range-VM task-roles these configs reference
(`get_sybers.range_ghosts_browser`, `get_sybers.range_recon_tooling`,
`get_sybers.range_ninjasploitable_server`) are vendored at
`ansible/roles/` (at the source root), because that is the only path `ludus source add` reads.
The shared telemetry roles (`get_sybers.sysmon`, `get_sybers.sysmon_linux`,
`get_sybers.acsc_event_logging`) ship from the same `ansible/roles/` directory;
they are invoked by name and resolve from the per-user roles path at deploy.
`campaign/ansible/ansible.cfg` sets `roles_path` to reach them, so the campaign
playbooks that apply the same roles by name (`FGNW-acsc-logging.yml`,
`FGNW-sysmon-linux.yml`, `FGNW-recon-tooling.yml`) still resolve.
Register the source and build the templates it needs:

```bash
ludus source add https://github.com/Get-Sybers/FGNW --all
ludus templates build -n win2022-server-x64-appxfix-template,win10-22h2-x64-enterprise-appxfix-template,win2022-exchange2019-x64-template,ninjasploitable-x64-server-template
ludus blueprint apply <sourceID>/FGNW
```

Then run the deploy. **Do not call `ludus range deploy` yourself** — `deploy.yml`
drives it as Phase 1, after bringing Nexus up in Phase 0:

```bash
cd /opt/ludus/sources/<sourceID>/blueprints/FGNW/campaign
ansible-playbook deploy.yml
```

Full procedure, variants and phase tokens: [`campaign/docs/DEPLOY.md`](FGNW/campaign/docs/DEPLOY.md).
