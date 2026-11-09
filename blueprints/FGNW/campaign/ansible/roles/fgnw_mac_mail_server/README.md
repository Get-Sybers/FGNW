# fgnw_mac_mail_server

Stands up the **Hidden Sand Village mail server** on macOS (`suna-mail`): the stock Postfix binary as
the SMTP MTA and a from-source Dovecot for IMAP and LMTP delivery, the stack that replaced Exchange
2019 and OWA for Sunagakure. The outcome is `suna-mail` accepting SMTP on 25 and IMAP on 143
(plaintext, inside the sealed range) with a virtual mailbox for every Sand user of the shared OWA
corpus, authenticating with that user's own Active Directory password. The unified `fgnw_thunderbird`
role on `suna-ws1` then logs into it (its defaults are pinned to IMAP 143 plain and SMTP 25 plain to
match).

It is called by [`FGNW-mac-mail.yml`](../../FGNW-mac-mail.yml) on `macos_dev`, limited to `suna-mail`
by a `when` on `inventory_hostname`, as step 2 of `deploy-tasks/phase4d-mac-services.yml`.

## Why it is built this way

Two macOS realities make this role unlike a Linux mail host, and both were confirmed on the live
range:

- **Dovecot is built from source.** GHOSTS-style, the Dovecot source tarball is cached on the range
  Nexus by `campaign/ansible/nexus-cache-dovecot.yml` (Phase 0, controller-side). The Sand macs ship
  no Homebrew and Phase 2 seals egress, so a `brew install` or a bottle download cannot work inside
  containment; instead this role builds the cached source with the Command Line Tools `clang`. Only
  one portability flag is needed (`st_atim`/`st_ctim` → `st_atimespec`/`st_ctimespec`), the build is
  plaintext-only (`--with-ssl=no`), and the result installs under `/usr/local/fgnw-dovecot`.
- **Postfix runs from a writable alternate config directory.** Apple's Postfix config under
  `/etc/postfix` is SIP-protected: unwritable even as root and pinned to `inet_interfaces =
  loopback-only`. The role never touches it. It copies `master.cf` out to
  `/usr/local/fgnw-postfix/conf`, writes its own `main.cf` there, and runs `postfix -c <dir>`.

## What it does

1. Loads the OWA inbox corpus and `ad/NARUTO/data/config.json`, and builds the Sand mailbox list:
   every corpus user who belongs to `fgnw_mac_mail_server_domain`, paired with that user's AD
   password. Fails cleanly when the intersection is empty.
2. Creates the Dovecot service accounts with the `ansible.builtin.group` and `ansible.builtin.user`
   modules: a dedicated mail user (`_fgnwmail`), a login user (`_fgnwnull`), and the `dovecot` group
   the built-in service listeners expect (macOS has none of these).
3. Fetches the Dovecot source from the Nexus (sha256-pinned) and builds it, guarded by a `creates`
   on the installed binary so the slow build runs only once.
4. Writes `dovecot.conf` (plaintext `imap lmtp`, `auth_username_format = %Ln`, `default_vsz_limit =
   0`, a `passwd-file` passdb and `static` userdb for virtual Maildirs) and the `dovecot-users`
   passwd-file (`0640`, group-readable by the auth worker). Notifies `Restart dovecot`.
5. Writes the Postfix `main.cf` in the alt config dir (LMTP delivery to Dovecot, empty
   `local_recipient_maps` so the virtual users are accepted, Dovecot SASL) and copies out
   `master.cf`. Stops and disables the stock loopback Postfix. Notifies `Restart postfix`.
6. Installs a LaunchDaemon for each service (`com.fgnw.dovecot`, `com.fgnw.postfix`) and loads them
   with the official `community.general.launchd` module (`state: started`), so both bind their
   privileged ports and survive reboots. The stock Apple Postfix daemon is unloaded with the same
   module and then persistently disabled.

## Inputs

All inputs have lab-safe defaults and the caller passes nothing; see
[`meta/argument_specs.yml`](meta/argument_specs.yml) for the full list. The ones most likely to be
overridden:

| Variable | Default | Description |
| --- | --- | --- |
| `fgnw_mac_mail_server_domain` | `sunagakure.wind.ninja` | Mail domain and the `config.json` domain whose users are seeded. |
| `fgnw_mac_mail_server_dovecot_version` | `2.3.21` | Dovecot version to build (2.3.x only). |
| `fgnw_mac_mail_server_dovecot_prefix` | `/usr/local/fgnw-dovecot` | Dovecot install prefix and mailbox root. |
| `fgnw_mac_mail_server_postfix_dir` | `/usr/local/fgnw-postfix/conf` | Writable Postfix config directory. |

## Privilege and platforms

- Every task runs with `become: true` (sudo via the inventory's `ansible_become_pass`).
- Platform: macOS on x86_64 (SIP enabled, no Homebrew). The build needs the Command Line Tools.
- Prerequisites: the Dovecot source cached on the Nexus (Phase 0), the AD config and OWA corpus on
  the controller, and at least one corpus user in the Sand domain.

## Idempotence

Yes. The source build is skipped once the binary exists (`creates`), the service accounts report
`changed` only when actually created, configs are rewritten only when they differ (the handlers fire
only then), and `community.general.launchd` (`state: started`) loads each daemon only when it is not
already running. The passwd-file is written with `no_log`.

## Example invocation

From `FGNW-mac-mail.yml`:

```yaml
- name: Sand mail server — Postfix + Dovecot on suna-mail
  hosts: macos_dev
  gather_facts: true
  tasks:
    - name: Stand up Postfix + Dovecot
      ansible.builtin.include_role:
        name: fgnw_mac_mail_server
      when: inventory_hostname == 'suna-mail'
```
