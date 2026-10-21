Drops operator convenience aids for reaching a range service's web GUI onto a
range Windows VM: a Netscape-format bookmark HTML file for Firefox and one for
Chrome (both under `C:\Users\Public\Desktop\Bookmarks\`), a Firefox desktop
shortcut, and a `<title>-Access-Instructions.txt` on the desktop. It configures
one VM in place, so it runs as a task-role at the `user-defined-roles` stage
(S2). `preflight.yml` asserts the two mandatory inputs before anything is
written.
The role is intentionally forgiving about the shortcut: the `.lnk` hard-codes
the default Firefox install path and is created under `ignore_errors`, because
the HTML import files are the real deliverable and a VM without Firefox (or with
it installed elsewhere) must not fail the whole role.

| `tasks_from:` | writes? | what it does |
| --- | --- | --- |
| `main.yml` | yes | preflight, then write the bookmark HTML files, the desktop shortcut and the instructions file |
| `preflight.yml` | no | assert `bookmark_url` and `bookmark_title` are non-empty |
| name | default | purpose |

| --- | --- | --- |
| `bookmark_url` | `""` | URL to bookmark (e.g. `https://server:8889`). Effectively required — `preflight.yml` asserts it. |
| `bookmark_title` | `""` | Bookmark display title and desktop-file basename. Effectively required — `preflight.yml` asserts it. |
| `bookmark_category` | `"Lab Resources"` | Folder name shown when the HTML bookmarks are imported. |
| `bookmark_username` | `""` | Optional username written into the instructions file; empty omits the line. |
| `bookmark_password` | `""` | Optional password written into the instructions file (the writing task carries `no_log`); empty omits the line. |
Nothing about the host's security posture. This is **operator-facing content**,
not an exploitation target: it disables no defence, installs no vulnerable
software, and opens no port. It only writes desktop files that point a human at
a lab service's web UI.
The one thing worth naming honestly: when `bookmark_password` is set, the
instructions file holds that credential in plaintext under
`C:\Users\Public\Desktop`, readable by any user of the box. That is lab
documentation for a disposable range service (the credential is itself a
throwaway range credential), not a secret, and the task that writes it carries
`no_log` so it does not leak into Ansible output. If that placement is
undesirable for a given scenario, leave `bookmark_username` / `bookmark_password`
unset and those lines are omitted entirely.
