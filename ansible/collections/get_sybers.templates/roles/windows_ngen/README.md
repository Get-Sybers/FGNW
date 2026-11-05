# get_sybers.templates.windows_ngen

Run .NET native-image generation (ngen) during a Windows template bake.

Factored out of the `ansible/ngen.yml` playbook that was copied verbatim into the
`win11-22h2-x64-enterprise-appxfix`, `win2022-server-x64-appxfix`, and
`win2022-exchange2019-x64` templates.

## What it does

Calls `community.windows.win_dotnet_ngen`, which drains the ngen queue for every
installed .NET runtime so the JIT cost is paid once at build time instead of on
every range deploy.

## Inputs

None. See `meta/argument_specs.yml`.

## Outcome / idempotence

Idempotent as the module defines it: `changed` only while there is queued ngen
work; a second run on a drained queue reports `ok`.

## Requirements

- A Windows target reached over WinRM (the Packer `ansible` provisioner).
- Collection dependency `community.windows` (declared in `galaxy.yml`, pinned in
  the consuming template's `requirements.yml`).

## Example

```yaml
- name: "Generate native .NET images (ngen) for the Windows template"
  hosts: all
  gather_facts: false
  roles:
    - get_sybers.templates.windows_ngen
```
