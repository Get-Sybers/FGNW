# Get-Sybers FGNW

A [Ludus](https://docs.ludus.cloud/) source: the range tier of the Get-Sybers
lab. It ships the **Fourth Great Ninja War** blueprint — a multi-domain Active
Directory lateral-movement lab (Hidden Leaf / Hidden Sand / Hidden Sound
domains plus the isolated Akatsuki forest, decoy village content, GHOSTS user
emulation, real Exchange 2019) — and everything the blueprint deploys from: the
`get_sybers.range` collection that drives the Ludus CLI and API from the
controller, the `get_sybers.templates` collection the Packer builds share, the
task-roles under `ansible/roles/` and the Packer template library.

Documentation starts at [`doc/index.md`](doc/index.md).

## Layout

```text
.
├── source.yml                  # the Ludus source manifest
├── requirements.yml            # the pinned collections the plays and the gate install
├── blueprints/FGNW/            # blueprint.yml, range-config.yml, requirements.yml, campaign/
├── ansible/collections/        # get_sybers.range, get_sybers.templates (AGPL-3.0-only)
├── ansible/roles/              # the task-roles (range roles and the cross-tier roles)
├── templates/                  # the Packer templates, one directory per image
├── doc/                        # index, the house standards, the Ludus deploy-tags reference
├── scripts/                    # conform (the house gate), check-*.py (the static gates), upgrade
└── .github/workflows/          # CI (lint + conform → all_green), links, scorecard, pin updates
```

The task-roles are the `get_sybers.range_*` roles the range config applies to
its VMs (Defender setup, Exchange and OWA, browser bookmarks, recon tooling,
the Ninjasploitable target, Velociraptor) and the cross-tier roles the
campaign plays apply: `get_sybers.ludus_auth_check`, `get_sybers.sysmon`,
`get_sybers.sysmon_linux`, `get_sybers.acsc_event_logging`,
`get_sybers.acsc_event_forwarding`, `get_sybers.acsc_linux_port_auditd`,
`get_sybers.acsc_linux_port_sysmon` and `get_sybers.zeek_sensor`. The
templates are the Windows AppX-fix images (Server 2022, Windows 10 and 11
Enterprise), Exchange 2019, FLARE VM, Metasploitable 2 and 3, five OpenCore
macOS releases and Ninjasploitable ([`templates/README.md`](templates/README.md)).

## Register the source and deploy FGNW

On a Ludus server, register the source, apply the blueprint and build the
templates the range names; then run the campaign's deploy orchestrator on the
Ludus host — it drives `ludus range deploy` itself as its Phase 1:

```bash
ludus source add https://github.com/Get-Sybers/FGNW --all
ludus blueprint apply <sourceID>/FGNW
ludus templates build -n win2022-server-x64-appxfix-template,win10-22h2-x64-enterprise-appxfix-template,win2022-exchange2019-x64-template,ninjasploitable-x64-server-template
cd /opt/ludus/sources/<sourceID>/blueprints/FGNW/campaign
ansible-playbook deploy.yml
```

`range-config.yml` names its Proxmox nodes `pi-01`, `pi-02` and `pi-03`;
replace them with the nodes of your cluster before deploying. The blueprint
README ([`blueprints/FGNW/README.md`](blueprints/FGNW/README.md)) explains the
placeholders, the macOS hosts and the Thunderbird mail clients; the deploy
guide ([`blueprints/FGNW/campaign/docs/DEPLOY.md`](blueprints/FGNW/campaign/docs/DEPLOY.md))
is the full procedure with its phase tokens and variants. The GHOSTS server
container the range's user emulation reports to is created by the `get_sybers.lxc`
collection's `deploy_ghost9_range` play from its ghost9 template
([get-sybers/lxc](https://github.com/Get-Sybers/LXC)): `requirements.yml` pins the
collection and Phase 1b runs the play by its collection-qualified name. The
third-party roles the campaign applies are installed from their GitHub repositories
by `blueprints/FGNW/requirements.yml`; this repository carries no copy of Ansible
another repository owns.

## Linting locally

```sh
make deps        # the pinned toolchain (test-requirements.txt) and collections (requirements.yml)
prek install     # the git hooks: lint, secrets, commit-msg
make conform     # every prek hook on every file, then scripts/conform
```

`scripts/conform` is the house gate: yamllint, ansible-lint with the
production profile over the source and over a scratch copy of the Packer
template plays, a syntax check of every play, the pin discipline
(`scripts/check-pins.py`), the static gates (`scripts/check-*.py`, scoped by
`scripts/gates.yml`) and the role must-haves. The hook versions live in
`.pre-commit-config.yaml`, the toolchain versions in `test-requirements.txt`,
the collection pins in `requirements.yml`.

## CI

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on pull requests
and pushes to `main`: `lint` (the prek hooks over every file and the must-have
files) and `conform` (the gate above with the pinned collections installed),
joined by `all_green`, the one status check the branch ruleset requires. The
links workflow checks the documentation's links nightly, the scorecard
workflow runs OpenSSF Scorecard, and the update workflow raises the hook
revisions and collection pins weekly into a pull request.

## License

The Ludus source, the FGNW blueprint and campaign, the first-party task-roles
under `ansible/roles/` and the Packer templates are released under the MIT
License ([`LICENSE`](LICENSE); the campaign carries its own copy). The two
collections, `get_sybers.range` and `get_sybers.templates`, are released under
the GNU Affero General Public License v3.0 only (`AGPL-3.0-only`, the
`LICENSE` beside each `galaxy.yml`). The third-party roles the blueprint installs from GitHub, and the bundled
`wireshark` role, keep the licence their own metadata names.
