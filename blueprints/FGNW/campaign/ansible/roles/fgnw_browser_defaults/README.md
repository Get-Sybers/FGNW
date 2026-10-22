# fgnw_browser_defaults

Village browser defaults for an FGNW range workstation. The role sets the village homepage and
bookmark bar for the browsers each persona uses, rendered from the shared village corpus
[`content/www/village-bookmarks.yml`](../../../content/www/village-bookmarks.yml). It dispatches
on `ansible_facts['os_family']`, so one role serves the Windows workstations of Konoha, Sound and
Akatsuki and the macOS hosts of Hidden Sand. The outcome is a browser that opens on the village
portal with the village's own and the shared bookmarks in place.

## What it does

`tasks/main.yml` loads the corpus with `include_vars`, fails when `fgnw_browser_defaults_village`
has no `village_bookmarks` entry, and computes the two facts the OS branches consume:
`fgnw_browser_defaults_homepage` (`http://` plus the village's `village_homepage` entry; the
themed sites listen on port 80 only) and `fgnw_browser_defaults_bookmark_list` (the village's
bookmarks followed by `shared_bookmarks`). It then includes one branch and fails on any other
OS family.

| OS family | Branch | Writes |
| --- | --- | --- |
| Windows | `tasks/windows.yml` | `HKU:\.DEFAULT\Software\Microsoft\Internet Explorer\Main` start page; Edge machine policies under `HKLM:\SOFTWARE\Policies\Microsoft\Edge` (`HomepageLocation`, `HomepageIsNewTabPage=0`, `RestoreOnStartup=4`, `RestoreOnStartupURLs\1`, `BookmarkBarEnabled=1`); `C:\Users\Public\Desktop\Bookmarks\<village>-bookmarks.html` in Netscape bookmark format |
| Darwin (macOS) | `tasks/macos.yml` | `/Applications/Firefox.app/Contents/Resources/distribution/policies.json` (`Homepage` and `ManagedBookmarks`); `/Library/Managed Preferences/com.google.Chrome.plist` (`HomepageLocation`, `HomepageIsNewTabPage`, `RestoreOnStartup=4`, the startup URL) |

## Inputs

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `fgnw_browser_defaults_village` | yes | none | Key into `village_bookmarks` and `village_homepage` of the corpus, for example `Hidden Leaf Village`. |

`meta/argument_specs.yml` declares the one input as required; `defaults/main.yml` lists it
commented out, because a default village would point every workstation at the same portal. The
corpus path is fixed at `{{ playbook_dir }}/../content/www/village-bookmarks.yml`, so the
calling play lives in `ansible/`.

Facts the role sets for its own branches and leaves behind on the host:
`fgnw_browser_defaults_bookmark_data`, `fgnw_browser_defaults_homepage` and
`fgnw_browser_defaults_bookmark_list`.

## Privilege and platforms

- Windows: runs as the WinRM connection user without `become`; writing `HKLM` and
  `HKU\.DEFAULT` policy values needs a local administrator.
- macOS: every task runs with `become: true` (sudo through the inventory's
  `ansible_become_pass`), because the Firefox app bundle and `/Library/Managed Preferences` are
  root-owned.
- Windows and macOS (`Darwin`) only; any other `os_family` fails the role before it writes
  anything. Facts have to be gathered, because the dispatch reads `ansible_facts['os_family']`.

## Idempotence

Yes. `win_regedit`, `win_file` and `win_copy` on Windows and `file` and `copy` on macOS change
only what differs; the corpus load and the two `set_fact` tasks are read-only. A second run
reports no change.

## Failure and rollback

An unknown village or an unsupported OS family fails the role before any write. A write that
fails stops the role on that host and leaves the values already written in place; nothing is
rolled back.

## Example invocation

From [`FGNW-browser-defaults.yml`](../../FGNW-browser-defaults.yml); the macOS hosts get the same
include from [`FGNW-mac-services.yml`](../../FGNW-mac-services.yml) with `Hidden Sand Village`:

```yaml
- name: Hidden Leaf Village browser defaults
  hosts: konoha-ws1
  tasks:
    - name: "Browser-defaults: apply the village browser defaults: Hidden Leaf Village"
      ansible.builtin.include_role:
        name: fgnw_browser_defaults
      vars:
        fgnw_browser_defaults_village: Hidden Leaf Village
```
