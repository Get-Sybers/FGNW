All notable changes to the `get_sybers.range` collection are documented here; the
source-level changelog (blueprint, task-roles, templates, the gate) is the repo-root
`CHANGELOG.md`. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this collection adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(§31: `0.y.z` until the interface is stable).

- `galaxy.yml` dependencies now carry upper bounds (`>=x.y.z,<next-major`), the
  collection carries a Galaxy-required tag, and `tox-ansible.ini` is `build_ignore`d (§2).
- Every role declares `min_ansible_version: "2.15"`, agreeing with `meta/runtime.yml`
  (`requires_ansible >=2.15.0`) and the `systemd_service` module the roles use (§2).
- Task names with a trailing variable place the variable at the end only
  (`ludus_range_deploy` attempt steps, `ghost9_ct`, `ghost9_server`) (§33).
- YAML style follows §16 across the roles (quoting, truthy, indentation) — mechanical.
- `ghost9_template` bake steps carry `creates`/`changed_when` and an FQCN `become_method`;
  `ghost9_ct`'s settle pause carries its named `no-handler` waiver (§7, §8, §17).
- Initial collection: `ludus_auth`, `ludus_range_config`, `ludus_range_deploy`,
  `ludus_testing`, `ludus_range_verify`, `ludus_range_health`, `ludus_range_teardown`,
  `ghost9_ct`, `ghost9_server`, `ghost9_template`.
[Unreleased]: <https://github.com/Get-Sybers/FGNW/compare/6581582...HEAD>
