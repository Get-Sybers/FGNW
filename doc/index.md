# Get-Sybers FGNW

The Get-Sybers FGNW repository is a [Ludus](https://docs.ludus.cloud/) source: the range tier of the Get-Sybers lab. It ships the
**Fourth Great Ninja War** blueprint — a multi-domain Active Directory lateral-movement lab (Hidden Leaf / Hidden Sand / Hidden
Sound domains plus the isolated Akatsuki forest, decoy village content, GHOSTS user emulation, real Exchange 2019) — together
with everything the blueprint deploys from: the `get_sybers.range` collection that drives the Ludus CLI and API from the
controller, the `get_sybers.templates` collection the Packer builds share, the task-roles under `ansible/roles/` (the range
roles, and the cross-tier roles for Ludus authentication, Sysmon, ACSC event logging and forwarding, the auditd and Sysmon
Linux ports and Zeek), and the Packer template library (the Windows AppX-fix images, Exchange 2019, FLARE VM, Metasploitable
2/3, OpenCore macOS and Ninjasploitable).

`ludus source add https://github.com/Get-Sybers/FGNW --all` registers it on a Ludus server; `ludus blueprint apply
<sourceID>/FGNW` creates the range configuration, and `blueprints/FGNW/campaign/deploy.yml` runs the deploy phases on the
Ludus host. The GHOSTS server container comes from the ghost9 template of the sibling `get_sybers.lxc` collection
([get-sybers/lxc](https://github.com/Get-Sybers/LXC)), pinned in `requirements.yml`.

---

## In this documentation

| | |
| --- | --- |
| [The FGNW blueprint](../blueprints/FGNW/README.md) | **What the range is** and how it is registered, built and applied; the `target_node:` placeholders every operator replaces |
| [Deploy guide](../blueprints/FGNW/campaign/docs/DEPLOY.md) | **The full procedure**: the phase orchestrator, its resume tokens, variants, the ghost9 phase, verification |
| [Campaign index](../blueprints/FGNW/campaign/Index.md) | **Where everything in the campaign lives**: plays, roles, AD data, content corpora, the other campaign documents — [quick deploy](../blueprints/FGNW/campaign/docs/QUICK-DEPLOY.md), [client-side deploy](../blueprints/FGNW/campaign/docs/CLIENT-DEPLOY.md), [the small range](../blueprints/FGNW/campaign/docs/SMALL-RANGE.md), [range-config variants](../blueprints/FGNW/campaign/docs/RANGE-CONFIG-VARIANTS.md), [troubleshooting](../blueprints/FGNW/campaign/docs/TROUBLESHOOTING.md), [the campaign scenario](../blueprints/FGNW/campaign/docs/FGNW-CAMPAIGN.md), [the verification checklist](../blueprints/FGNW/campaign/docs/deploy-verification-checklist.md) |
| [`get_sybers.range`](../ansible/collections/get_sybers.range/README.md) | **The orchestration collection**: authenticate, set the range config, deploy and poll, enter containment, verify, diagnose, tear down |
| [`get_sybers.templates`](../ansible/collections/get_sybers.templates/README.md) | **The template-baking collection**: the OpenCore macOS role, the Windows ngen role, the Metasploitable provisioning role |
| [Packer templates](../templates/README.md) | **The template library**: one directory per image, what each registers as and what it is for |
| [Ludus deploy tags](ludus/ludus-deploy-tags.md) | **Reference**: every tag `ludus range deploy` and `ludus testing` ship, what drives it, and the class it falls in |
| [Standards](standards/02-Ansible-Standards.md) | **The house rules** every role, play and repository control is held to: the Ansible standard, the [CI workflow](standards/03-ansible-ci-workflow.md), [linting, conformance and the merge gate](standards/04-Linting-and-Conformance.md) |

Every task-role documents its own contract in its `README.md` under [`ansible/roles/`](../ansible/roles), and every
collection role under [`ansible/collections/`](../ansible/collections).

---

## Project and community

The Get-Sybers FGNW source is free software: the source, the blueprint, the task-roles and the templates under the
[MIT License](../LICENSE); the two collections under the GNU Affero General Public License v3.0 (their own `LICENSE`
files). It is part of the Get-Sybers lab, alongside the cluster tier in
[get-sybers/proxmaxxing](https://github.com/Get-Sybers/proxmaxxing) (`get_sybers.cluster`), which operates the Proxmox
nodes and the Ludus server the range runs on, and the hardened LXC tier in [get-sybers/lxc](https://github.com/Get-Sybers/LXC)
(`get_sybers.lxc`), which builds the ghost9 container the range's user emulation reports to.

- [Contribute to the project](../CONTRIBUTING.md)
- [Report a vulnerability](../SECURITY.md)
- [Code of conduct](../CODE_OF_CONDUCT.md)
- [Maintainers](../MAINTAINERS)
