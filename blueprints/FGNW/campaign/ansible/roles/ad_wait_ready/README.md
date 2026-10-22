# ad_wait_ready

Readiness gate for a Windows domain controller. The role polls the target until its directory
is serving again, after a promotion or a reboot, and only then lets the play continue. It
changes nothing on the host; the outcome is a play that does not run directory work against a
DC whose services are still starting.

No play in this repository applies this role. Its contract below is written from its tasks.

## What it does

One task runs [`files/wait-ad-ready.ps1`](files/wait-ad-ready.ps1) through
`ansible.builtin.script` and retries it until the script exits 0:

| Check | Always | With `ad_wait_ready_require_dc: true` |
| --- | --- | --- |
| Services running | `NTDS`, `DNS`, `Netlogon` | plus `kdc` |
| Directory answers | `Get-ADDomain` succeeds (needs AD Web Services) | same |
| Host is a DC | not checked | `Get-ADDomainController -Identity $env:COMPUTERNAME` succeeds |
| Shares advertised | not checked | `SYSVOL` and `NETLOGON` appear in `Get-SmbShare` |

The flag reaches the script through the `AD_WAIT_REQUIRE_DC` environment variable. A failed
attempt is retried after `ad_wait_ready_delay` seconds, up to `ad_wait_ready_retries` times
(60 retries of 10 s, ten minutes, by default).

## Inputs

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `ad_wait_ready_require_dc` | no | `false` | Also require the host's own DC identity, the `kdc` service and the SYSVOL/NETLOGON shares. |
| `ad_wait_ready_retries` | no | `60` | Retries of the probe before the task fails for the host. |
| `ad_wait_ready_delay` | no | `10` | Seconds between two attempts. |

`meta/argument_specs.yml` types and describes the same three inputs; each has a default in
`defaults/main.yml`.

## Privilege and platforms

- Runs as the WinRM connection user, without `become`. The probe reads service state, the
  directory and the local share list and writes nothing.
- Windows Server domain controllers: the `NTDS`, `DNS` and `Netlogon` services and the
  ActiveDirectory PowerShell module the script needs exist only there. No other OS family is
  handled.

## Idempotence

Yes. The role is read-only: the task carries `changed_when: false` and the script writes
nothing, so a run reports no change whether the DC was ready on the first attempt or the last.

## Failure and rollback

When the probe still fails after the last retry the task fails for that host, with the
script's last error (`<service> not running`, the `Get-ADDomain` exception or
`SYSVOL/NETLOGON not shared yet`) in the result. There is nothing to roll back because nothing
was changed.

## Example invocation

No play in this repository applies this role. A caller includes it on a domain controller right
after the step whose reboot it has to wait out:

```yaml
- hosts: dc
  tasks:
    - name: Wait for the directory to serve again
      ansible.builtin.include_role:
        name: ad_wait_ready
      vars:
        ad_wait_ready_require_dc: true
```
