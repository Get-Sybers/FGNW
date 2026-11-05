# Ansible content

Roles and collections shipped by this source. Both are installed per user by `ludus source add`
(instance-wide with `--global`) and can be vendored as git submodules.

- [`roles/`](./roles/README.md) — one standard Ansible role per directory (`tasks/main.yml`, `meta/main.yml` required).
- [`collections/`](./collections/README.md) — one Ansible collection per directory (`galaxy.yml` required).

Nothing is vendored yet. Add a role with `git submodule add <repo> ansible/roles/<name>` or by committing the
role directory directly, then reference it from a blueprint's `range-config.yml`.
