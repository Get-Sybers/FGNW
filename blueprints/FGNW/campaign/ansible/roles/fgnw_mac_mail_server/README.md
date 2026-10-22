# fgnw_mac_mail_server

Stands up the **Hidden Sand Village mail server** on macOS: Postfix (built into macOS) as the SMTP
MTA and Homebrew Dovecot for IMAP and LMTP delivery, the stack that replaced Exchange 2019 and OWA
for Sunagakure. The outcome is `suna-mail` accepting SMTP on 25 and IMAP on 143 (plaintext, inside
the sealed range) with a local mailbox for every Sand user of the shared OWA corpus, which the
unified `fgnw_thunderbird` role on suna-ws1 then logs into (its defaults are pinned to IMAP 143
plain and SMTP 25 plain to match).

It is called by [`FGNW-mac-mail.yml`](../../FGNW-mac-mail.yml) on `macos_dev`, limited to
`suna-mail` by a `when` on `inventory_hostname`, as step 2 of `deploy-tasks/phase4d-mac-services.yml`.
Dovecot itself is installed earlier, pre-containment, by `FGNW-mac-dev.yml` (Phase 1c,
`homebrew_installed_packages`); this role only configures and starts it, because a `brew install`
cannot reach the internet after Phase 2 containment.

## What it does

1. Resolves the Homebrew prefix at runtime (`brew --prefix`, `/usr/local` on the x86_64 guests) and
   derives the Dovecot config path `<prefix>/etc/dovecot/dovecot.conf`.
2. Loads `fgnw_mac_mail_server_user_corpus_file` and `ad/NARUTO/data/config.json` (relative to the
   play's directory), intersects the corpus keys with the users of
   `lab.domains[fgnw_mac_mail_server_domain]` and fails when nothing is left to seed. Same pattern
   as `fgnw_exchange_seed_mail`.
3. Writes `/etc/postfix/main.cf`: `myhostname` and `mydomain` from the inputs, `mynetworks` from
   `fgnw_mac_mail_server_relay_networks`, Maildir delivery handed to Dovecot over LMTP, Dovecot
   SASL, `maillog_file = /var/log/mail.log`. Notifies `Restart postfix` (`postfix reload`).
4. Writes `dovecot.conf`: `protocols = imap lmtp`, `mail_location = maildir:~/Maildir`, PAM passdb and
   passwd userdb, the LMTP and auth sockets under `/var/spool/postfix/private/`, log at
   `/var/log/dovecot.log`. Notifies `Restart dovecot` (`brew services restart dovecot`).
5. Creates a local account per user (`fgnw_mac_mail_server_user_shell`, home created, password
   `fgnw_mac_mail_server_user_password_default` hashed with SHA-512) and a `0700` `~/Maildir`.
6. Enables `system/org.postfix.master`, runs `postfix start`, and `brew services start dovecot` as
   root so Dovecot lands in the system LaunchDaemon domain (the only one allowed to bind 25 and 143).

## Inputs

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `fgnw_mac_mail_server_domain` | no | `sunagakure.wind.ninja` | Mail domain (`mydomain`) and the `config.json` domain whose users are seeded. |
| `fgnw_mac_mail_server_hostname` | no | `{{ inventory_hostname }}.{{ fgnw_mac_mail_server_domain }}` | Postfix `myhostname` and SMTP banner. |
| `fgnw_mac_mail_server_relay_networks` | no | `127.0.0.0/8, 10.0.0.0/8` | Postfix `mynetworks` (relay without authentication). |
| `fgnw_mac_mail_server_user_corpus_file` | no | `{{ playbook_dir }}/../content/OWA/user-inboxes.yml` | Controller-side inbox corpus whose keys become local mail accounts. |
| `fgnw_mac_mail_server_user_shell` | no | `/sbin/nologin` | Shell of the seeded accounts (mail-only). |
| `fgnw_mac_mail_server_user_password_default` | no | `Changeme1!` | Password of every seeded account; the Thunderbird IMAP/SMTP credential. Lab placeholder. |

The `fgnw_mac_mail_server_*` facts the tasks register or set (`brew_prefix`, `dovecot_conf`,
`inbox_data`, `ad_config`, `domain_users`, `users`, `postfix_enable`, `postfix_start`,
`dovecot_start`) are internal, not inputs.

## Privilege and platforms

- `brew --prefix` runs as the SSH user (Homebrew refuses to run as root); every other task and both
  handlers run with `become: true` (sudo via the inventory's `ansible_become_pass`).
- Platform: macOS on x86_64 (Homebrew under `/usr/local`; the prefix is resolved, not assumed).
- Prerequisites: Dovecot installed by Homebrew, the AD config and the OWA corpus on the controller,
  and at least one corpus user in the Sand domain.

## Idempotence

Yes, with one honest exception. The configs are rewritten only when they differ (the handlers fire
only then), accounts and Maildirs are created only when missing, `postfix start` and
`brew services start` report `ok` when the daemon is already running, and the user task re-applies
the same password (a fresh SHA-512 salt each run, same credential). The
`launchctl enable system/org.postfix.master` task reports `changed` on every run because its
`changed_when` is `rc == 0`.

## Failure and rollback

The assert stops the role cleanly when there is no Sand user to seed. A failure later leaves every
config already written in place: nothing is rolled back and no backup copies are kept. Handlers run
at the end of the play, so a run that fails after notifying one leaves the running daemon on its
previous configuration until the next successful run.

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
