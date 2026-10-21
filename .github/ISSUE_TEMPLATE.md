The template below is for bug reports and support questions. Remove what does
not apply and add what helps. Never paste a credential, an API key, a Ludus
admin key or a vaulted file.

# Required information

- Ludus server version (`ludus version`) and Proxmox VE version (`pveversion`):
- FGNW blueprint version (`blueprints/FGNW/blueprint.yml`), or the branch and commit:
- `ansible-core` version on the deploy controller (`ansible --version`):
- The range variant (`range_variant`), the deploy phase token and the `-e` inputs you ran it with (values redacted where secret):
- For a range problem, the output of `ludus range status` and `ludus range list --json` (range number only):

# Issue description

A brief description of what failed or what could be improved.

# Steps to reproduce

1. Step one
2. Step two
3. Step three

# Information to attach

- [ ] the deploy output with `-vv` (secret-bearing tasks are `no_log` and print nothing)
- [ ] `ludus range logs` for a Ludus-side failure
- [ ] for the ghost9 container, `pct config <vmid>` on the node and the GHOSTS API probe from `ghost9-verify.yml`
