# fgnw_themed_sites

Renders and serves the FGNW range's themed per-domain web content on the
attacker/web Linux host. For each site in `site_pages` the role creates a
dedicated document root, renders an `index.html` from that site's archetype
template, and publishes a single name-based nginx vhost that serves every
domain from its own root. The outcome is a running nginx that answers each
fictional domain with its own themed page.

The role is called by
[`FGNW-themed-sites.yml`](../../FGNW-themed-sites.yml), which loads the page
data (`site_pages`, `site_content_links`, `character_profiles`,
`general_techniques`) from `content/www/` and includes the role once against
the `attacker` host.

## What it does

- Installs `nginx` from the distro package repository (`ansible.builtin.apt`).
- Builds a per-village link index (`__village_index`) so each page can list its
  related sites.
- Creates `fgnw_themed_sites_root/<url>` for every entry in `site_pages`, owned
  by `www-data`.
- Renders each site's `index.html` from `templates/<archetype>.html.j2`
  (`news`, `wiki`, `portal`, `forum`, `shop`, `fansite`), passing the page, its
  related sites, its content-links entry and its village accent colour.
- Writes one name-based nginx vhost (`server_name` is every site URL; `root` is
  `$host`) and symlinks it into `sites-enabled`.
- Runs `nginx -t` to validate the configuration; nginx is reloaded through a
  handler only when the vhost or its symlink changed.

The archetype templates read the page data directly: `character_profiles` and
`general_techniques` are consulted by the `wiki` and `fansite` templates only
when a site's `site_content_links` entry names characters, techniques or a full
index, so they are optional.

## Inputs

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `site_pages` | yes | _(none)_ | List of site dicts (`url`, `village`, `category`, `archetype`, `description`). Not prefixed; loaded from `content/www/site-archetypes.yml`. |
| `site_content_links` | no | `{}` | Per-URL enrichment keyed by site url (`characters`, `general_techniques`, `full_index`). Not prefixed; from `content/www/site-content-links.yml`. |
| `character_profiles` | no | _(none)_ | Character jutsu/quote data keyed by name. Not prefixed; from `content/www/character-profiles.yml`. |
| `general_techniques` | no | _(none)_ | Technique names for wiki full-index pages. Not prefixed; from `content/www/character-profiles.yml`. |
| `fgnw_themed_sites_root` | no | `/var/www/sites` | Web root holding one document root per site url. |
| `fgnw_themed_sites_nginx_conf` | no | `/etc/nginx/sites-available/FGNW-themed-sites.conf` | Path of the vhost file this role writes. |
| `fgnw_themed_sites_nginx_link` | no | `/etc/nginx/sites-enabled/FGNW-themed-sites.conf` | Path of the sites-enabled symlink. |
| `fgnw_themed_sites_village_colors` | no | 11-village accent map | Accent colour per village; a village with no entry falls back to the archetype's own colour. |

## Privilege, platforms, idempotency

- **Privilege:** runs with `become: true` (installs packages, writes under
  `/var/www` and `/etc/nginx`). No Windows.
- **Platforms:** Debian-family Linux (nginx installed through `apt`).
- **Idempotent:** yes. The package, directory, template, file and symlink tasks
  converge; the per-village index is built with `set_fact`; `nginx -t` is a
  read-only check (`changed_when: false`); and the reload fires only when the
  vhost or symlink changed.

## Failure and rollback

There is no rollback. `nginx -t` fails the run if the rendered configuration is
invalid, which leaves the new vhost file on disk but does not reload the running
server, so the previously loaded configuration keeps serving. A failure of the
package install or a template render stops the play with the module's own error.

## Example invocation

Copied from [`FGNW-themed-sites.yml`](../../FGNW-themed-sites.yml):

```yaml
- hosts: attacker
  become: true
  vars_files:
    - ../content/www/site-archetypes.yml
    - ../content/www/site-content-links.yml
    - ../content/www/character-profiles.yml
  tasks:
    - name: Render + serve themed sites
      ansible.builtin.include_role:
        name: fgnw_themed_sites
```
