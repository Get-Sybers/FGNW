# move_to_ou

Relocates existing domain computer objects into their target organisational
unit. Run on a domain controller, the role reads the lab host inventory, finds
the in-scope member computers that already exist in the directory, and moves
each to the OU named by its inventory entry. The outcome is that every provisioned
member computer sits in its intended OU; nothing else is created or changed.

The role is called by [`ad-data.yml`](../../ad-data.yml) against the `dc` hosts,
with `hosts_dict` and `member_domain` taken from the lab data model.

## What it does

- Iterates `hosts_dict` and, for each entry that is **not** a DC, is in
  `member_domain`, and is **not** LAPS-managed, runs a `Get-ADComputer` probe
  (`ansible.windows.win_shell`) that reports `EXISTS` or `MISSING`. The probe is
  read-only (`changed_when: false`).
- For every object the probe reported as `EXISTS`, relocates it with
  `microsoft.ad.computer` to the OU given by that entry's `path` (empty path =
  default Computers container).

Objects reported `MISSING` are skipped, so the role dispatches on the live state
of the directory as well as on the inventory: it only moves computers that have
already joined.

## Inputs

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `hosts_dict` | yes | _(none)_ | Lab host inventory keyed by host key; each value has `hostname`, `type`, `domain`, optional `path` (target OU DN) and `use_laps`. Not prefixed; the play passes `lab.hosts`. |
| `member_domain` | yes | _(none)_ | Domain whose member computer objects are in scope. Not prefixed; the play passes `lab.hosts[dict_key].domain`. |

## Privilege, platforms, idempotency

- **Privilege:** runs over WinRM against the domain controller as the connecting
  (AD-privileged) account; no `become`. Directory writes need rights to move
  computer objects.
- **Platforms:** Windows (domain controller with the AD RSAT / `microsoft.ad`
  modules available).
- **Idempotent:** yes. The probe never reports changed, and
  `microsoft.ad.computer` reports changed only when an object actually moves, so
  a second run with every computer already in place is a no-op.

## Failure and rollback

There is no rollback. A probe or move failure stops the play with the module's
own error; objects already moved in that run stay moved. Because the move is
driven by the probe result, a computer that does not yet exist is skipped rather
than failing the run.

## Example invocation

Copied from [`ad-data.yml`](../../ad-data.yml):

```yaml
- name: Move to OU
  hosts: dc
  vars_files:
    - "{{ data_path }}/config.json"
  roles:
    - { role: move_to_ou, tags: move_to_ou }
  vars:
    data_path: ../ad/{{ domain_name }}/data
    hosts_dict: "{{ lab.hosts }}"
    member_domain: "{{ lab.hosts[dict_key].domain }}"
```
