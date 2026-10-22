# fgnw_mac_dsconfigad

Thin, idempotent wrapper around Apple's `dsconfigad`, the macOS-supported way to make a Mac a
client of a Windows Active Directory domain. The role binds the host to
`fgnw_mac_dsconfigad_domain` only when it is not already bound and asserts the bind afterwards;
the outcome is a macOS host that is a computer object of the Sand child domain
(`sunagakure.wind.ninja`) and authenticates its users against the Sand DC.

It is called by [`FGNW-mac-ad-bind.yml`](../../FGNW-mac-ad-bind.yml) on the `macos_dev` hosts
(suna-ws1, suna-mail), step 1 of `deploy-tasks/phase4d-mac-services.yml`: after Phase 3 has
built the Sand DCs and with containment up (only internet egress is sealed; VLAN traffic to the
DC is unaffected).

## What it does

1. Reads the current directory-service state with `dsconfigad -show` (never fails, never changes).
2. Sets `fgnw_mac_dsconfigad_already_bound`: whether the target domain appears in that output.
3. Already bound: prints a debug line and skips the bind.
4. Not bound: asserts `fgnw_mac_dsconfigad_admin_user` and `fgnw_mac_dsconfigad_admin_password`
   are non-empty, composes the argv (`-add <domain> -computer <name> [-ou <ou>] -username <user>
   -password <password>`) and runs `dsconfigad -add`, both steps with `no_log: true`.
5. Re-reads `dsconfigad -show` and asserts the domain is now present; the failure message lists the
   usual causes (the host cannot resolve the domain's AD SRV records, or clock skew against the DC
   exceeds the 5 minutes Kerberos tolerates) and the `dsconfigad -show` output.

The role does not change the host's resolver: the DC's address and DNS come from the range's VLAN
networking.

## Inputs

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `fgnw_mac_dsconfigad_domain` | no | `sunagakure.wind.ninja` | AD domain to bind to. |
| `fgnw_mac_dsconfigad_computer` | no | `{{ (inventory_hostname \| upper)[:15] }}` | AD computer object name; AD caps the pre-Windows-2000 name at 15 characters. |
| `fgnw_mac_dsconfigad_ou` | no | `""` | Optional OU path; empty means Apple's default (the domain's Computers container). |
| `fgnw_mac_dsconfigad_admin_user` | no (asserted when binding) | `""` | AD principal allowed to join computers, e.g. `domainadmin`. The play supplies it. |
| `fgnw_mac_dsconfigad_admin_password` | no (asserted when binding) | `""` | That principal's password. Secret: the play supplies it; never set it in defaults. |

The two credentials default to empty strings so the role can be included on an already-bound host
without them; when a bind is needed the role asserts both are non-empty and fails with a message
that points at the play.

`fgnw_mac_dsconfigad_before` and `fgnw_mac_dsconfigad_after` (the registered `dsconfigad -show`
runs), `fgnw_mac_dsconfigad_already_bound` and `fgnw_mac_dsconfigad_argv` are facts the role sets
for itself, not inputs.

## Privilege and platforms

- Both `dsconfigad -show` reads and the `dsconfigad -add` run with `become: true` (sudo with the
  inventory's `ansible_become_pass`); the fact and assert tasks do not escalate.
- The argv composition and the bind run with `no_log: true`; the caller play also sets `no_log` on
  the include.
- Platform: macOS (the range's macos-sequoia-15 template hosts).

## Idempotence

Yes. The bind runs only when `dsconfigad -show` does not already list the target domain; on a bound
host the role reports no change. The `-add` task reports `changed` only when `dsconfigad` exits 0.

## Failure and rollback

A missing bind principal or an unsuccessful bind stops the role with a labelled assert message, and
a non-zero `dsconfigad -add` fails that task outright. Nothing is rolled back: the role never runs
`dsconfigad -remove`, so a failed or partial bind is left for the operator to inspect with
`dsconfigad -show`.

## Example invocation

From `FGNW-mac-ad-bind.yml`:

```yaml
- name: AD-bind the Sand macOS hosts to sunagakure.wind.ninja
  hosts: macos_dev
  gather_facts: true
  vars:
    __lab_admin_user: domainadmin
    __lab_admin_password: password
  tasks:
    - name: Run the dsconfigad wrapper
      ansible.builtin.include_role:
        name: fgnw_mac_dsconfigad
      vars:
        fgnw_mac_dsconfigad_admin_user: "{{ __lab_admin_user }}"
        fgnw_mac_dsconfigad_admin_password: "{{ __lab_admin_password }}"
      no_log: true
```
