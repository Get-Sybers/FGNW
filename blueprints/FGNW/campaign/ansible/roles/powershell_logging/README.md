# powershell_logging

Enables the three PowerShell audit policies the FGNW blue-team detection lab
depends on -- **script block logging**, **module logging** and **over-the-shoulder
transcription** -- by writing their Group Policy registry values under
`HKLM:\SOFTWARE\Policies\Microsoft\Windows\PowerShell`. The outcome is a Windows
host that records PowerShell activity to the event log and to on-disk
transcripts, giving the detection lab something to hunt.

The role is called by [`lat.yml`](../../lat.yml) against the `domain` hosts with
no overrides, so it applies its defaults (all three streams on).

## What it does

- Writes `EnableScriptBlockLogging` when
  `powershell_logging_script_block_enabled` is true.
- Writes `EnableModuleLogging` and the `ModuleNames` scope value (default `*`,
  every module) when `powershell_logging_module_enabled` is true.
- Writes `EnableTranscripting`, the `OutputDirectory` and
  `EnableInvocationHeader` when `powershell_logging_transcription_enabled` is
  true.

Every value is a `dword` or `string` set with `ansible.windows.win_regedit`.
The booleans are rendered to the registry as `0`/`1` via the `| int` filter.

## Inputs

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `powershell_logging_script_block_enabled` | no | `true` | Enable script block logging. |
| `powershell_logging_module_enabled` | no | `true` | Enable module logging and write the module-name scope. |
| `powershell_logging_module_names` | no | `"*"` | Module-name filter module logging covers; `*` logs every module. |
| `powershell_logging_transcription_enabled` | no | `true` | Enable transcription and write its directory and invocation-header value. |
| `powershell_logging_transcription_output_directory` | no | `C:\Windows\Temp\PowerShellTranscripts` | Directory transcripts are written to. |
| `powershell_logging_invocation_header_enabled` | no | `true` | Stamp an invocation header into each transcript. |

## Privilege, platforms, idempotency

- **Privilege:** runs over WinRM as the connecting account; writes under
  `HKLM`, so that account needs local administrator rights. No `become`.
- **Platforms:** Windows Server 2019 and 2022.
- **Idempotent:** yes. Every task is `ansible.windows.win_regedit` with
  `state: present` and a fixed value, so a host already carrying these values
  reports no change on re-run.

## Failure and rollback

There is no rollback. A registry write that fails stops the play with the
module's error; values written earlier in the run remain. Disabling a stream
later (toggle set to false) stops the role writing its "enabled" value but does
not delete a value a previous run set, because the tasks only write when their
toggle is true.

## Example invocation

Copied from [`lat.yml`](../../lat.yml):

```yaml
- name: Enable PowerShell Script Block Logging on Windows hosts
  hosts: domain
  roles:
    - powershell_logging
```
