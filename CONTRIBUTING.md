# Contributing

## Pull requests

Changes to this project are proposed as pull requests on GitHub at
<https://github.com/Get-Sybers/FGNW>. A pull request is reviewed there and,
once green on `all_green`, merged into `main`.

The branch ruleset (`.github/rulesets/main.json`) requires the CI workflow's
`all_green` status check (prek over every file, the must-have files, and the
house gate `scripts/conform`: yamllint, ansible-lint, the Packer template plays,
the play syntax checks, the pin discipline, the static gates and the role
must-haves), dismisses stale reviews on push, and asks an extra approval for
commits not attributed to the pull request's author; it sets no approval count
of its own and allows merge, squash and rebase merges. Branches are named
`<type>/<description>` (`feat/zeek-sensor-profile`); the pull request title is a
Conventional Commit (`feat(fgnw_thunderbird): …`, `fix(templates): …`), because
a squash merge uses it as the commit message.

## Before you open one

```sh
make deps        # the pinned toolchain (test-requirements.txt) and collections (requirements.yml)
prek install     # the git hooks: lint, secrets, commit-msg
make conform     # the full local gate: every prek hook, then scripts/conform
```

`make conform` runs the same commands CI runs, with the same configuration
files, so what passes locally passes on the pull request. A change to a
collection's plugins or roles needs a fragment under that collection's
`changelogs/fragments/`; every other change gets an entry under *Unreleased* in
`CHANGELOG.md`. A change to behaviour or an interface updates the documentation
under `doc/`, the blueprint's `campaign/docs/` and the role's `README.md`.

## Nothing site-specific goes in

The repository describes a range, not a site. A pull request never adds a
Proxmox node name, a management or storage address, a cluster name, a
credential or anything else that identifies one deployment: `range-config.yml`
names its nodes `pi-01`, `pi-02` and `pi-03`, which every operator replaces
before deploying; addresses in documentation and role defaults use the RFC 5737
documentation ranges (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`); the
only passwords in the tree are the lab's own synthetic Active Directory
accounts, which the range creates on deploy. Vendored third-party payloads
(`files/upstream/`, the ACSC subscriptions) stay byte-identical to the commit
their role's `meta/upstream.yml` records; a change to one is a re-vendoring
with the record updated, never an edit.

## The standards

[`doc/standards/`](doc/standards/02-Ansible-Standards.md) carries the house
rules every role and play is held to: a role performs actions and a playbook
decides which run, every value arrives through the native variable system,
every task is idempotent and honest about change. The CI workflow and the
linting and conformance gate are the standards' own
([`03`](doc/standards/03-ansible-ci-workflow.md),
[`04`](doc/standards/04-Linting-and-Conformance.md)). A change that needs an
exception to a rule is discussed in the pull request, never waived in the code.

## License and copyright

By default, any contribution to this project is made under the MIT License
(see `LICENSE`): the Ludus source, the blueprint and campaign, the task-roles
under `ansible/roles/` and the Packer templates. A contribution to the
`get_sybers.range` or `get_sybers.templates` collection under
`ansible/collections/` is made under the GNU Affero General Public License v3.0
only (`AGPL-3.0-only`, the `LICENSE` beside each `galaxy.yml`). The author of a
change remains the copyright holder of their contribution; there is no
copyright assignment.

## Security

Do not open a public issue for a security problem. Use
**Security → Report a vulnerability** on the repository; see `SECURITY.md`.
