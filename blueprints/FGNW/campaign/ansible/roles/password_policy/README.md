# password_policy

Converges a domain's **Default Domain Policy** to the lab's password and lockout
values. Run on a domain controller, the role reads the current policy, compares
it against the requested values, and writes only the settings that have drifted.
The outcome is a Default Domain Policy that matches the lab's (deliberately weak)
password rules. This is lab tooling, not production hardening.

The role is called by [`ad-data.yml`](../../ad-data.yml) against the `dc` hosts,
with the five values passed inline.

## What it does

- Runs one `ansible.windows.win_powershell` task that resolves the current
  domain and reads `Get-ADDefaultDomainPasswordPolicy`.
- Builds a drift list by comparing the current lockout threshold, minimum
  password length, lockout duration, lockout observation window and complexity
  flag against the requested values, plus two fixed targets: reversible
  encryption off and maximum password age set to never-expire.
- Only when something drifted, calls `Set-ADDefaultDomainPasswordPolicy` (under
  `ShouldProcess`) to apply every value, and reports `changed`. The task returns
  the list of drifted settings.
- Retries up to 12 times (15s apart) so it tolerates a DC that is still coming
  up.

## Inputs

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `password_policy_try_before_lock` | no | `"0"` | Account-lockout threshold (failed attempts before lockout); `"0"` disables lockout. |
| `password_policy_pass_length` | no | `"5"` | Minimum password length. |
| `password_policy_lock_duration` | no | `"00:00:00"` | Lockout duration (TimeSpan string). |
| `password_policy_lock_observation` | no | `"00:00:00"` | Lockout observation window (TimeSpan string). |
| `password_policy_complexity` | no | `false` | Whether password complexity is enforced. |

Reversible encryption (off) and maximum password age (never-expire) are fixed in
the task and are not inputs.

## Privilege, platforms, idempotency

- **Privilege:** runs over WinRM against the domain controller as the connecting
  account (which must be able to set the default domain policy); no `become`.
- **Platforms:** Windows (domain controller with the AD PowerShell module).
- **Idempotent:** yes, by design. The task computes drift first and calls
  `Set-ADDefaultDomainPasswordPolicy` only when at least one value differs, so a
  converged domain reports no change on re-run.

## Failure and rollback

There is no rollback. The write applies all values together; a failure during
the set leaves the policy partially updated and stops the play. The retry loop
only re-attempts the whole converge step while the DC is unreachable or the
module has not yet succeeded.

## Example invocation

Copied from [`ad-data.yml`](../../ad-data.yml):

```yaml
- name: DCs AD data configuration
  hosts: dc
  roles:
    - role: password_policy
      tags: policy
      password_policy_try_before_lock: "0"
      password_policy_pass_length: "5"
      password_policy_lock_duration: 00:00:00
      password_policy_lock_observation: 00:0:00
      password_policy_complexity: false
```
