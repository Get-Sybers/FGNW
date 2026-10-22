# ludus_tool_cache

Generic Linux tool-cache web server for a Ludus range. Installs nginx, renders a
static tool-download index page from the supplied catalogue, stages each tool's
binary into a `/tools/` directory, and serves the lot over HTTP from a catch-all
vhost. The outcome is an operator staging server from which range binaries can
be downloaded directly.

In the FGNW campaign the role is called by
[`FGNW-attacker-web.yml`](../../FGNW-attacker-web.yml), which loads
`content/www/attacker-tools.yml` and passes its `tool_categories` as the
catalogue.

## What it does

- Fails fast if `ludus_tool_cache_categories` is empty, telling the caller to
  load a tools YAML first.
- Routes apt through the range's Nexus Debian proxy and moves
  `/etc/apt/sources.list` aside (guarded by `removes:`) so package installs work
  under containment, then installs `nginx`.
- Creates `<web_root>/<tools_subdir>` owned by `www-data`.
- Fetches each tool that carries a `url` with `ansible.builtin.get_url`; an
  unreachable download is tolerated (`failed_when: false`) so one missing tool
  does not stop the build.
- Publishes controller-side local files: validates each `local_source`, stats
  them on `localhost`, fails with a combined list if any are missing, and copies
  the rest into the tools directory.
- Renders `index.html` listing every category and tool, linking to the staged
  filename or showing "manual install" where appropriate.
- Deploys a catch-all nginx vhost, enables it, removes nginx's default site,
  validates with `nginx -t`, then enables and restarts nginx.

## Inputs

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `ludus_tool_cache_categories` | no (but must be non-empty) | `[]` | Tool catalogue: list of category dicts (`name`, `description`, `tools[]`); each tool has `name`, `description`, `filename` and optionally `url`, `manual_install`, `local_file`, `local_source`. The role fails when it is empty. |
| `ludus_tool_cache_title` | no | `Tool Cache` | Heading and HTML title of the index page. |
| `ludus_tool_cache_subtitle` | no | `Pre-staged tools for range operations. All binaries are served from /tools/ for direct download.` | Lead paragraph on the index page. |
| `ludus_tool_cache_web_root` | no | `/var/www/html` | nginx document root. |
| `ludus_tool_cache_tools_subdir` | no | `tools` | Subdirectory of the web root for binaries and their URL path. |

## Privilege, platforms, idempotency

- **Privilege:** runs with `become: true` (edits apt sources, installs nginx,
  writes under `/var/www` and `/etc/nginx`). No Windows.
- **Platforms:** Debian-family Linux (nginx and the Nexus proxy lines are
  Debian/apt specific).
- **Idempotent:** largely. The apt-source rewrite (guarded by `removes:`),
  directory, file, copy and index tasks converge on re-run. Two steps are not
  strictly idempotent: the final `nginx` service is `state: restarted`, so it
  restarts every run, and `get_url` against a "latest" release URL re-fetches
  when upstream changes.

## Failure and rollback

There is no rollback. The role fails early when the catalogue is empty or a
declared `local_source` is missing, and `nginx -t` fails the run on an invalid
configuration (the previously loaded config keeps serving because the restart
runs after validation). A tool whose `url` is unreachable is intentionally left
out of the cache and the page still builds.

## Example invocation

Copied from [`FGNW-attacker-web.yml`](../../FGNW-attacker-web.yml):

```yaml
- hosts: attacker
  become: true
  vars_files:
    - ../content/www/attacker-tools.yml
  vars:
    ludus_tool_cache_title: 🔴 Akatsuki Tool Cache
    ludus_tool_cache_subtitle: >
      Pre-staged offensive tools for Fourth Great Ninja War range operations.
      All binaries are served from /tools/ for direct download.
    ludus_tool_cache_categories: "{{ tool_categories }}"
  tasks:
    - name: "Attacker-web: publish the Akatsuki tool cache"
      ansible.builtin.include_role:
        name: ludus_tool_cache
```
