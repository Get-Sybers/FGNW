# fgnw_exchange_seed_mail

Seeds one forest's **real Exchange mailboxes** with the FGNW character-quote corpus (plus the
LOE 2 alert entries) as genuine SMTP mail. The role runs on the Exchange server of each of the
three villages that still run Exchange (`konoha-mail`, `oto-mail`, `dark-mail`; the Hidden Sand
mail stack is `fgnw_mac_mail_server`), after `FGNW-exchange.yml` has installed Exchange. The
outcome is an inbox per real domain user filled with correspondence from named teammates, and an
end-of-seed marker on the server that records the delivery.

It is called by [`FGNW-exchange-seed-mail.yml`](../../FGNW-exchange-seed-mail.yml), once per
forest (`deploy-tasks/phase4b-exchange.yml` runs that play `--limit <forest>` right after the
Exchange install), with the forest identity derived from `inventory_hostname` in the play's vars.

## What it does

1. Asserts the caller set `fgnw_seed_mail_state_dir` and `fgnw_seed_mail_sentinel` (the
   end-of-seed marker the re-run guard depends on).
2. Loads `content/OWA/user-inboxes.yml` (the generated per-user inbox corpus) and
   `ad/NARUTO/data/config.json` (the AD population ground truth), both relative to the play's
   directory (the campaign's `ansible/`).
3. Keeps only the corpus keys that are real users of `lab.domains[fgnw_seed_mail_domain]`, and
   fails when that leaves nothing to seed rather than report a successful empty seed.
4. Sends every message of every kept recipient with `Send-MailMessage -SmtpServer localhost`
   (`ansible.windows.win_shell`), run as `<fgnw_seed_mail_admin_domain>\Administrator` through
   `runas`, with `no_log: true`. Curly quotes are normalised and single quotes doubled so the
   PowerShell string literals stay intact.
5. Creates `fgnw_seed_mail_state_dir` and writes `fgnw_seed_mail_sentinel` **last**, with the
   domain, host, recipient and message counts, the corpus SHA-1 and the UTC timestamp.

## Inputs

All inputs are supplied by the play; none has a safe default, so `defaults/main.yml` lists them
commented out. The names keep their historical `fgnw_seed_mail_` prefix.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `fgnw_seed_mail_domain` | yes | none | Recipient (mail) domain of this forest and key into `config.json` `lab.domains`, e.g. `konohagakure.fire.ninja`. |
| `fgnw_seed_mail_admin_domain` | yes | none | Forest root whose `Administrator` the send runs as (`runas`), e.g. `fire.ninja`. |
| `fgnw_seed_mail_admin_password` | yes | none | That Administrator's password (the lab-wide range credential). Secret: the play supplies it. |
| `fgnw_seed_mail_state_dir` | no (asserted) | none | Directory holding the end-of-seed marker, e.g. `C:\ProgramData\FGNW`. Tested with `is defined`, so no default. |
| `fgnw_seed_mail_sentinel` | no (asserted) | none | Full path of the marker file, e.g. `C:\ProgramData\FGNW\seed-mail.done`. Tested with `is defined`, so no default. |

"asserted" means the role's first task fails with a clear message when the variable is missing or
empty; `meta/argument_specs.yml` leaves those two unrequired so that assertion keeps its meaning.

`fgnw_inbox_data`, `fgnw_ad_config` (the loaded data) and the `__fgnw_seed_mail_*` facts are
internal, not inputs. `force_reseed` is read by the caller play, not by the role.

## Privilege and platforms

- Runs over WinRM as the inventory connection user; the send task alone escalates with
  `become_method: runas` to `<fgnw_seed_mail_admin_domain>\Administrator` using
  `fgnw_seed_mail_admin_password`. The marker tasks run as the connection user.
- Platform: Windows Server running Exchange 2019 (the `exchange_servers` inventory group).

## Idempotence

**No.** Sending mail is not repeatable: every run that reaches the send task delivers the whole
corpus again and duplicates every message already in the mailboxes. The guard lives in the caller
play, which probes `fgnw_seed_mail_sentinel` with `win_stat` and includes the role only when the
marker is absent or `force_reseed=true`; the role writes the marker only after the last message was
delivered, so a half-seeded forest (no marker) is seeded again in full on the next run.

## Failure and rollback

The two asserts stop the role cleanly (missing marker paths, nothing to seed). A failure inside the
send loop stops the role with the marker unwritten; the messages already delivered stay in the
mailboxes (mail cannot be unsent, nothing is rolled back) and the next run re-delivers the complete
corpus, so those recipients receive duplicates. Remove the marker file, or pass
`-e force_reseed=true` to the play, to deliver the corpus again on purpose.

## Example invocation

From `FGNW-exchange-seed-mail.yml`:

```yaml
- name: "Real-exchange: seed REAL Exchange mailboxes with the character-quote corpus + LOE 2 alerts"
  hosts: exchange_servers
  gather_facts: false
  vars:
    fgnw_exchange_map:
      konoha-mail: { domain: konohagakure.fire.ninja }
      oto-mail: { domain: otogakure.ninja }
      dark-mail: { domain: akatsuki.dark }
    fgnw_seed_mail_domain: "{{ fgnw_exchange_map[inventory_hostname].domain }}"
    fgnw_exchange_forest_root_map:
      konoha-mail: fire.ninja
      oto-mail: otogakure.ninja
      dark-mail: akatsuki.dark
    fgnw_seed_mail_admin_domain: "{{ fgnw_exchange_forest_root_map[inventory_hostname] }}"
    fgnw_seed_mail_admin_password: password
    fgnw_seed_mail_state_dir: C:\ProgramData\FGNW
    fgnw_seed_mail_sentinel: C:\ProgramData\FGNW\seed-mail.done
    force_reseed: false
  tasks:
    - name: Probe this forest's end-of-seed marker
      ansible.windows.win_stat:
        path: "{{ fgnw_seed_mail_sentinel }}"
      register: fgnw_seed_mail_sentinel_stat
    - name: Seed this forest's real mailboxes
      ansible.builtin.include_role:
        name: fgnw_exchange_seed_mail
      when: (force_reseed | bool) or (not fgnw_seed_mail_sentinel_stat.stat.exists)
      no_log: true
```
