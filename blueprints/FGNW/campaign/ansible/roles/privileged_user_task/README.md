# privileged_user_task

Plants a boot-triggered Windows scheduled task that runs as a privileged domain
account, so that account's token stays resident in memory for the
Pass-the-Hash / token-impersonation workshop. The outcome is a workstation that,
from boot onward, holds a privileged credential artefact for the lab to collect.

The role is called by [`lat.yml`](../../lat.yml) against the workstation
(retargeted to `konoha-ws1`), with the identity set inline and the password
sourced from the AD data model (`config.json`).

## What it does

- Asserts that `privileged_user_task_username`, `privileged_user_task_domain`
  and `privileged_user_task_password` are all set, failing with a clear message
  otherwise.
- Registers a scheduled task (`community.windows.win_scheduled_task`) that, on a
  boot trigger, runs `cmd.exe /c timeout` for
  `privileged_user_task_persistent_process_duration` seconds as
  `username@domain`, restarting at boot and on failure. The task write is
  `no_log: true`.
- Starts the task immediately with `schtasks /run`
  (`ansible.windows.win_command`) so the token is resident without a reboot.

## Inputs

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `privileged_user_task_password` | yes | _(none, secret)_ | Password for the privileged account. No default by design; the play supplies it from `config.json`. |
| `privileged_user_task_username` | no | `gaara` | sAMAccountName of the privileged account. |
| `privileged_user_task_domain` | no | `sunagakure.wind.ninja` | Domain of the account; used as `user@domain`. |
| `privileged_user_task_persistent_process_name` | no | `PersistentDomainAdminProcess` | Name of the scheduled task. |
| `privileged_user_task_persistent_process_description` | no | _(workshop description)_ | Description recorded on the task. |
| `privileged_user_task_persistent_process_duration` | no | `14400` | Seconds the planted process sleeps per run. |
| `privileged_user_task_run_level` | no | `highest` | Run level the task executes at. |
| `privileged_user_task_logon_type` | no | `password` | Logon type used to authenticate the account. |
| `privileged_user_task_restart_on_failure` | no | `true` | Restart the task after a failure. |
| `privileged_user_task_restart_count` | no | `3` | Number of restart attempts on failure. |
| `privileged_user_task_stop_if_going_on_batteries` | no | `false` | Stop the task on battery power. |
| `privileged_user_task_start_when_available` | no | `true` | Run as soon as possible after a missed start. |
| `privileged_user_task_execution_time_limit` | no | `PT0S` | Task execution time limit (ISO 8601); `PT0S` is no limit. |
| `privileged_user_task_trigger_execution_time_limit` | no | `PT0S` | Boot-trigger execution time limit (ISO 8601); `PT0S` is no limit. |

## Privilege, platforms, idempotency

- **Privilege:** runs over WinRM as the connecting account, which needs local
  administrator rights to register a scheduled task that runs as another
  account and stores its password. No `become`.
- **Platforms:** Windows. The host must be Windows (the Hidden Sand workstation
  became macOS, so `lat.yml` retargets this role to a Konoha Windows
  workstation).
- **Idempotent:** partly. The scheduled-task registration converges, but the
  final "start now" step uses `ansible.windows.win_command: schtasks /run` with
  `changed_when: rc == 0`, so it runs and reports changed on every invocation
  and re-triggers the resident process.

## Failure and rollback

There is no rollback. The assert stops the play before any change if the
identity or password is missing. If the task registers but the immediate start
fails, the task remains registered and will still run at the next boot. A task
left from a previous run is updated in place, not removed.

## Example invocation

Copied from [`lat.yml`](../../lat.yml):

```yaml
- name: Schedule task for privileged user hash on workstation (retargeted to Konoha)
  hosts: konoha-ws1
  vars_files:
    - "{{ data_path }}/config.json"
  vars:
    data_path: ../ad/NARUTO/data
    privileged_user_task_domain: konohagakure.fire.ninja
    privileged_user_task_username: naruto.uzumaki
    privileged_user_task_password: "{{ lab.domains[privileged_user_task_domain].users[privileged_user_task_username].password }}"
  roles:
    - privileged_user_task
```
