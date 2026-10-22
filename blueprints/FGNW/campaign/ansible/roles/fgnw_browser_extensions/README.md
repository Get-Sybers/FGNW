# fgnw_browser_extensions

Managed browser extensions for the FGNW GHOSTS workstations. The role force-installs extensions
through Microsoft Edge's `ExtensionInstallForcelist` policy: two benign extensions from the Edge
Add-ons store for baseline realism, and one deliberately risky extension, "Konoha Form Helper",
served from an update feed on the attacker VM, the range's browser-extension initial-access and
persistence vector described in [`docs/MODERN-INFRA.md`](../../../docs/MODERN-INFRA.md). The
outcome is an Edge that installs the three extensions on its next policy refresh.

## What it does

1. `ansible.windows.win_regedit` ensures `HKLM:\SOFTWARE\Policies\Microsoft\Edge` exists.
2. For each entry of `fgnw_browser_extensions_benign`, in list order, writes
   `HKLM:\SOFTWARE\Policies\Microsoft\Edge\ExtensionInstallForcelist\<n>` (numbered from 1) with
   the value `<id>;<fgnw_browser_extensions_update_url>`.
3. Writes the entry numbered one past the benign list with
   `<fgnw_browser_extensions_risky.id>;<fgnw_browser_extensions_risky.update_url>`.

Edge applies the policy on its next policy refresh or launch and installs the listed extensions
without user consent; the role neither launches nor restarts Edge.

## Inputs

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `fgnw_browser_extensions_benign` | no | uBlock Origin (`odfafepnkmbhccpbejgmiehpchacaeak`), Grammarly (`cnlefmmeadmemmdciolhbnfeacpdfbkd`) | List of `{name, id}`: `name` is a label used in task output, `id` the 32-character extension id in the Edge Add-ons store. |
| `fgnw_browser_extensions_update_url` | no | `https://edge.microsoft.com/extensionwebstorebase/v1/crx` | Update URL written after every benign extension id. |
| `fgnw_browser_extensions_attacker_ip` | no | `ATTACKER_VM_IP` | Address of the attacker VM that hosts the risky extension's update feed; interpolated into the default `fgnw_browser_extensions_risky.update_url`. |
| `fgnw_browser_extensions_risky` | no | `name: Konoha Form Helper`, `id: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`, `update_url: http://<fgnw_browser_extensions_attacker_ip>/extensions/konoha-form-helper/update.xml` | The self-hosted risky extension, written as the last forcelist entry: `name` (label), `id` and `update_url` (the feed Edge fetches the CRX from). |

Every input has a default, so [`FGNW-browser-extensions.yml`](../../FGNW-browser-extensions.yml)
passes nothing; `meta/argument_specs.yml` types and describes them. No play in this repository
sets `fgnw_browser_extensions_attacker_ip`, so the risky update URL as deployed carries the
literal placeholder `ATTACKER_VM_IP`; a caller that sets the variable (inventory, `-e` or the
include's `vars`) gets the real feed address in the policy.

## Privilege and platforms

- Runs as the WinRM connection user, without `become`; writing `HKLM` policy values needs a
  local administrator.
- Windows workstations with Microsoft Edge; the play targets the `ghosts_clients` inventory
  group. There is no OS dispatch and no macOS or Linux branch.

## Idempotence

Yes. `win_regedit` writes a value only when it differs, so a second run reports no change. The
role never deletes entries: an entry written by an earlier run with a longer benign list stays
in the registry.

## Failure and rollback

A registry write that fails stops the role on that host; entries already written stay. Nothing
is rolled back and no entry is removed.

## Example invocation

[`FGNW-browser-extensions.yml`](../../FGNW-browser-extensions.yml):

```yaml
- name: Force-install browser extensions on GHOSTS workstations
  hosts: ghosts_clients
  tasks:
    - name: "Browser-extensions: force-install the browser extensions"
      ansible.builtin.include_role:
        name: fgnw_browser_extensions
```
