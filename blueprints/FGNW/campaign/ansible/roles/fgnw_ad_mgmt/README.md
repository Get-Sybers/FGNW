# fgnw_ad_mgmt

Directory realizer for the FGNW owned AD-build layer. On each domain controller the role takes
the domain's entry of the AD data model (`ad/NARUTO/data/config.json`, `lab.domains[<domain>]`)
and realizes it in Active Directory: the organisational units, the groups per scope, the users
with their group memberships and the declared group members, then makes sure the built-in
`Administrator` is a Domain Admin. The outcome is a domain whose directory content matches the
contract, ready for the Phase 3 plays that follow (`lat.yml`, `reboot.yml`, `adcs.yml`).

## What it does

`tasks/main.yml` includes four stage files in order, each one task per action on the
`microsoft.ad` modules, then runs one closing task:

| Stage | Task file | Action |
| --- | --- | --- |
| Organisational units | `tasks/ous.yml` | `microsoft.ad.ou` creates every key of `ad_ou` under its `path` |
| Groups | `tasks/groups.yml` | `microsoft.ad.group` creates the `universal`, `global` and `domainlocal` groups of `ad_groups` under their `path`, with `managed_by` when set |
| Users | `tasks/users.yml` | an `assert` rejects records without `firstname`, `password` or `groups`, or with a `path` that is not a DN; then `microsoft.ad.user` creates each user (`update_password: on_create`, `password_never_expires`, membership of `groups`, container from `path` or `CN=Users` of `domain`) under `no_log` |
| Memberships | `tasks/memberships.yml` | `microsoft.ad.group` adds the `members` declared on each group, per scope |
| Closing | `tasks/main.yml` | `microsoft.ad.group` adds `Administrator` to `Domain Admins` |

The role dispatches on nothing: it runs the same stages on every DC and acts on the data the play
hands it for that DC's domain.

## Inputs

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `ad_ou` | no | `{}` | OUs keyed by name; each value carries `path`, the DN the OU is created under. |
| `ad_groups` | no | `{}` | Groups by scope: the keys `universal`, `global` and `domainlocal` each hold a dict keyed by group name with `path` (container DN), optional `managed_by` and optional `members`. A missing scope is skipped. |
| `ad_users` | no | `{}` | Users keyed by sAMAccountName with `firstname`, `password` and `groups` (required), optional `surname` (defaults to the first name), `enabled` (default `true`), `city`, `description` and `path` (a DN; without it the user lands in `CN=Users`). Carries passwords: `no_log` in the spec and on the create task. |
| `domain` | yes | none | DNS name of the domain this DC serves, for example `konohagakure.fire.ninja`; it builds the `CN=Users,DC=...` default container and labels the validation messages. |

The four names are the AD-build contract's own and carry no `fgnw_ad_mgmt_` prefix.
`meta/argument_specs.yml` types and describes them: `ad_ou`, `ad_groups` and `ad_users` fall
back to empty collections inside the tasks, `domain` is required. `defaults/main.yml` lists the
four commented out, because the lint gate's role-prefix rule rejects an uncommented default
under these names, and the play supplies every one of them.

## Privilege and platforms

- Runs as the WinRM connection user on the domain controller, without `become`; the
  `microsoft.ad` modules act with that user's rights, which have to cover creating OUs, groups
  and users in the domain.
- Windows Server domain controllers of the range (`ad-data.yml` targets the `dc` group).

## Idempotence

Yes. Every `microsoft.ad` module creates only what is missing and adds only the members that
are not there yet (`members.add`); `update_password: on_create` leaves an existing user's
password alone, so a second run reports no change. The validation `assert` is read-only.

## Failure and rollback

A user record that lacks `firstname`, `password` or `groups`, or carries a malformed `path`,
fails the host before any user is created, with the offending keys named in the message. A
module error fails the host at that task; objects already created stay in the directory.
Nothing is rolled back, and the role never deletes an OU, group, user or membership.

## Example invocation

From [`ad-data.yml`](../../ad-data.yml) (Phase 3, run with the AD-build and the provider
inventories; the `password_policy` lines belong to the other role of the same play):

```yaml
- name: DCs AD data configuration
  hosts: dc
  vars_files:
    - "{{ data_path }}/config.json"
  roles:
    - role: password_policy
      tags: policy
      password_policy_try_before_lock: "0"
      password_policy_pass_length: "5"
      password_policy_lock_duration: 00:00:00
      password_policy_lock_observation: 00:0:00
      password_policy_complexity: false
    - { role: fgnw_ad_mgmt, tags: ad_domain_data }
  vars:
    data_path: ../ad/{{ domain_name }}/data
    hostname: "{{lab.hosts[dict_key].hostname}}"
    domain: "{{lab.hosts[dict_key].domain}}"
    domain_username: "{{domain}}\\Administrator"
    domain_password: "{{lab.domains[domain].domain_password}}"
    domain_server: "{{lab.hosts[dict_key].hostname}}.{{domain}}"
    ad_users: "{{lab.domains[lab.hosts[dict_key].domain].users}}"
    ad_ou: "{{lab.domains[lab.hosts[dict_key].domain].organisation_units  | default({}) }}"
    ad_groups: "{{lab.domains[lab.hosts[dict_key].domain].groups}}"
```
