This file records the origin and license of the campaign's content, so the bundled
third-party roles stay under their own upstream licenses rather than being filed under the
authors' copyright.

## A. Original work

The Fourth Great Ninja War campaign is the original work of Get-Sybers, under the MIT
[`LICENSE`](LICENSE).

**Roles** (`ansible/roles/`): `fgnw_ad_mgmt`, `fgnw_browser_defaults`,
`fgnw_browser_extensions`, `fgnw_decoy_files`, `fgnw_exchange_seed_mail`,
`fgnw_modern_infra`, `fgnw_themed_sites`, `ludus_tool_cache`, `adcs`, `dnsforwarder`,
`move_to_ou`, `password_policy`, `powershell_logging`, `privileged_user_task`.

**Playbooks** (`ansible/`): all `FGNW-*.yml` and `ghost9-*.yml` playbooks, plus
`ad-data.yml`, `adcs.yml`, `dnsforwarder.yml`, `lat.yml`, `reboot.yml`,
`tgtdelegation.yml`.

**Content & data**: `content/` (the Naruto documents, GHOSTS personas, themed material);
and the lab data under `ad/NARUTO/data/` — the scenario values (domains, users, groups,
the whole Fourth Great Ninja War world) are the authors' own.

## B. Third-party

Third-party roles that retain their own upstream licenses (installed from their GitHub
repositories by `blueprints/FGNW/requirements.yml` unless marked bundled):

| Role | Origin / license |
| --- | --- |
| `aleemladha.ludus_exchange` | <https://github.com/aleemladha/ludus_exchange>, commit `319bb51d`; GPL-3.0 |
| `geerlingguy.docker` | <https://github.com/geerlingguy/ansible-role-docker>, 7.5.5; MIT |
| `wireshark` | bundled; MIT (`meta/main.yml`) |

---

*Scope note:* the campaign is a single work of the authors (MIT), aggregated with a few
third-party roles that retain their own licenses (bucket B). This file exists so that
boundary stays explicit rather than implied by a single top-level `LICENSE`.
