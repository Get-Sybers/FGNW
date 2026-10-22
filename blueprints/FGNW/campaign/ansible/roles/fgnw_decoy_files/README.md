# fgnw_decoy_files

Unified decoy-document role for the FGNW range. Plants one village's share of the
Fourth Great Ninja War document corpus (`content/filesystem/village-folders.yml`)
under a caller-chosen root, and dispatches on `ansible_facts['os_family']` so the
same role serves the Windows domain controllers and Naruto's workstation
([`FGNW-decoy-content.yml`](../../FGNW-decoy-content.yml)) **and** the Hidden Sand
macOS workstation suna-ws1 ([`FGNW-mac-services.yml`](../../FGNW-mac-services.yml)).
The outcome is a browsable directory tree of lore-accurate documents (authored
content where it exists, a one-line placeholder elsewhere) for the red team to find.

## What it does

1. Loads `content/filesystem/village-folders.yml` (relative to the play's directory, the
   campaign's `ansible/`) and fails when `fgnw_decoy_files_village` has no entry there.
2. Sets the file list for the village (`fgnw_decoy_files_list`, an internal fact).
3. Dispatches on the OS family:

| OS family | Tasks file | Mechanism |
| --- | --- | --- |
| `Windows` | `tasks/windows.yml` | `ansible.windows.win_file` creates each parent directory, `ansible.windows.win_copy` writes each file (CRLF placeholder); no `become` |
| `Darwin` | `tasks/macos.yml` | `ansible.builtin.file` creates the root and each parent directory (`0755`), `ansible.builtin.copy` writes each file (`0644`), every task `become: true` |
| anything else | none | fails loudly; `gather_facts` must have run for the dispatch to work |

For every relative path in the list, the content is the authored document
`content/filesystem/documents/<village>/<path>` when it exists on the controller, else the
placeholder `<basename> - decoy document, <village>, Fourth Great Ninja War range content pack.`
Both branches write with `force: false`, so a file that already exists on the host is left untouched.

## Inputs

Both inputs are required and have no default; `meta/argument_specs.yml` enforces this at include
time and `defaults/main.yml` lists them commented out.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `fgnw_decoy_files_village` | yes | none | Key into `village-folders.yml` (`village_documents`) and the directory name under `content/filesystem/documents/`, e.g. `Hidden Leaf Village (Konohagakure)`. |
| `fgnw_decoy_files_root` | yes | none | Destination root in the host's own path syntax: `C:\Shares\Documents` or `C:\Users\naruto.uzumaki` on Windows, `/Users/Shared/Documents` on macOS. |

`fgnw_decoy_files_village_documents` (the loaded YAML) and `fgnw_decoy_files_list` (the selected
file list) are facts the role sets for itself, not inputs.

## Privilege and platforms

- Windows: runs as the WinRM connection user (the range inventory's local Administrator); no `become`.
- macOS: every task sets `become: true` (sudo with the inventory's `ansible_become_pass`).
- Platforms: Windows (domain controllers and workstations) and macOS (`os_family` `Darwin`).

## Idempotence

Yes. Directory creation converges, and the file writes use `force: false`, so a second run reports
every task `ok`. The flip side: an authored document that changes after the first run is not pushed
over the existing decoy; delete the file on the host to have it planted again.

## Failure and rollback

The role stops before touching the host when the village has no entry in `village-folders.yml`, or
when the OS family is neither Windows nor Darwin. A failure inside the file loop leaves the files
already planted in place; nothing is rolled back, and re-running the role completes the set.

## Example invocation

From `FGNW-decoy-content.yml` (Windows):

```yaml
- name: Plant Hidden Leaf Village decoy documents
  hosts: konoha-dc1
  tasks:
    - name: "Decoy-content: plant the village decoy documents: Hidden Leaf Village"
      ansible.builtin.include_role:
        name: fgnw_decoy_files
      vars:
        fgnw_decoy_files_village: Hidden Leaf Village (Konohagakure)
        fgnw_decoy_files_root: C:\Shares\Documents
```

From `FGNW-mac-services.yml` (macOS):

```yaml
- name: Hidden Sand Village — decoy documents (workstation only; unified Win/Mac role, macOS branch)
  hosts: macos_dev
  tasks:
    - name: "Decoy-content: plant Sand decoy documents"
      ansible.builtin.include_role:
        name: fgnw_decoy_files
      vars:
        fgnw_decoy_files_village: Hidden Sand Village (Sunagakure)
        fgnw_decoy_files_root: /Users/Shared/Documents
      when: inventory_hostname == 'suna-ws1'
```
