# Ansible roles

Each `ansible/roles/<name>/` directory is a standard Ansible role:

```
ansible/roles/<name>/
├── tasks/main.yml       required — the role's tasks
├── meta/main.yml        required — galaxy_info.description shows in the Ludus catalog; author + role_name form the installed identity
├── meta/version.yml     optional — `version:` shown by Ludus (overrides git tag detection)
├── defaults/main.yml    default variables
└── handlers/main.yml    handlers
```

Ludus installs a local role under its galaxy identity (`<galaxy_info.author>.<galaxy_info.role_name>`) when
`meta/main.yml` defines both, otherwise under the directory name; blueprints reference whichever name results.
A local role with the same name as a galaxy role in a blueprint's `requirements.yml` wins over galaxy.

Start new roles from the [Ludus role template](https://github.com/badsectorlabs/ludus_ansible_role_template).
CI runs `ansible-lint` and the structural checks in `scripts/ludus_source_lint.py` over every role here.
