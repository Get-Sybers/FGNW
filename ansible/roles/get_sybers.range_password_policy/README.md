Sets a DC's **Default Domain Policy** (the domain-wide account/password policy) to the lab's
deliberately-loosened values, so the short, weak passwords carried in the AD contract are
admitted when accounts are created. No Ansible module edits the Default Domain Policy
(`microsoft.ad.pso` manages fine-grained PSOs only), so the role drives
`Set-ADDefaultDomainPasswordPolicy` through `ansible.windows.win_powershell`. The script is
**check-then-set** — it reads the live policy first and writes only the fields that differ, so a
re-run over an already-converged domain reports no change and `--check` predicts the change
without applying it. A task-level retry rides out the ADWS (tcp/9389) startup gap after the DC's
pre-run reboot.
`main.yml` is the only entry point. It runs on a DC at the Ludus `user-defined-roles` stage
(S2), **ahead of `get_sybers.range_ad_mgmt`** so the loosened policy is in force before the
contract's users are created.
The five tunables are bare-named (ported verbatim from the campaign `password_policy` role)
rather than role-prefixed, and all default in `defaults/main.yml`. `LockoutThreshold` and
`MinPasswordLength` are strings by design — the PowerShell param block types them `[String]`
then coerces to `[Int]`.

| name | default | purpose |
| --- | --- | --- |
| `try_before_lock` | `"0"` | `LockoutThreshold` — failed attempts before lockout; `0` = **never lock out**. |
| `pass_length` | `"5"` | `MinPasswordLength` — minimum password length. |
| `lock_duration` | `"00:00:00"` | `LockoutDuration` (hh:mm:ss). |
| `lock_observation` | `"00:00:00"` | `LockoutObservationWindow` (hh:mm:ss). |
| `complexity` | `false` | `ComplexityEnabled` — `false` disables Windows password complexity. |

`pw_policy_result` is a `register` fact, not an input, and is excluded from
`meta/argument_specs.yml`.
This role's entire purpose is to **weaken the domain password policy**, and it is the most
directly offensive-by-design role of the set:

- **Account lockout is disabled** (`LockoutThreshold = 0`) — unlimited failed logons, so
  password spraying and online brute force run with no lockout risk.
- **Minimum password length dropped to 5** and **complexity disabled**, so trivial, short lab
  passwords are accepted and are far easier to crack offline.
- **Passwords never expire** — the script pins `MaxPasswordAge` to the "never" sentinel, so a
  captured credential stays valid for the life of the range.
The script keeps `ReversibleEncryptionEnabled = $false` (it does not enable reversible
encryption); every other change above loosens the policy.
