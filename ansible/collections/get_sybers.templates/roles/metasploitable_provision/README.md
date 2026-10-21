# get_sybers.templates.metasploitable_provision

One-time provisioning for an imported-disk-image Linux template before it is
converted to a Ludus template.

Factored out of the `ansible/provision.yml` playbook that was copied verbatim
into the `metasploitable-2` and `metasploitable-3` templates (run by each
template's `scripts/import.sh` over SSH).

## What it does

1. Regenerates the SSH host keys and restarts sshd, so templated clones do not
   share host keys.
2. Clears `/etc/machine-id` (a harmless no-op on pre-systemd images).
3. Best-effort installs `qemu-guest-agent` (the mirrors for these very old
   distros are usually dead, so this is allowed to fail) and reports whether it
   succeeded.

Every task uses `ansible.builtin.raw`, because these guests (Ubuntu 8.04 / 14.04)
may not have a usable Python interpreter for the normal modules.

## Inputs

None. See `meta/argument_specs.yml`.

## Outcome / idempotence

Not idempotent by design — host-key regeneration is a deliberate, run-once
action performed immediately before the VM is shut down and templated. Run it
once per bake (as `import.sh` does), not as a reconvergence loop.

## Requirements

- SSH reachability to the imported guest (set up by the template's `import.sh`).
- No collection dependencies (built-ins only).
