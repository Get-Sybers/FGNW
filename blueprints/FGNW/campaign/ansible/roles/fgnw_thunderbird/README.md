# fgnw_thunderbird

Unified Mozilla **Thunderbird** mail-client role for the FGNW range. Dispatches
on `ansible_facts['os_family']` so the same role handles the Windows workstations
(konoha-ws1..5, oto-ws1, akatsuki-ws1/2) that talk IMAP/SMTP to their village's
Exchange server, **and** the Hidden Sand macOS workstation (suna-ws1) that talks
to the Postfix/Dovecot stack stood up by `fgnw_mac_mail_server`.

The role is called by [`FGNW-thunderbird.yml`](../../FGNW-thunderbird.yml) once
per workstation, with persona + mail-server vars derived from
`content/ghosts/persona-timelines.yml` and the per-village mail server.

## What it does

| OS family | Install | Configure |
| --- | --- | --- |
| Windows (`ansible_facts['os_family']: Windows`) | `chocolatey.chocolatey.win_chocolatey` installs `thunderbird` from the range's Nexus `chocolatey-proxy` repo | Drops `C:\Program Files\Mozilla Thunderbird\distribution\policies.json` with Mozilla's enterprise `EmailAccountSetup` policy |
| macOS (`ansible_facts['os_family']: Darwin`) | Expects Thunderbird to already be installed as a Homebrew cask (Phase 1c `FGNW-mac-dev.yml` -> `homebrew_casks: [thunderbird]`) — the install cannot run here because Phase 2 containment seals internet egress | Drops `/Applications/Thunderbird.app/Contents/Resources/distribution/policies.json` with the same Mozilla policy schema |

Both branches share one Jinja template
(`templates/policies.json.j2`) that renders Mozilla's `EmailAccountSetup` block
with the five identity + routing vars.

## Required vars (no defaults, by design)

A wrong default would silently point every workstation at the same server, so
the caller MUST pass these five:

| Var | Example |
| --- | --- |
| `fgnw_thunderbird_user` | `naruto.uzumaki` |
| `fgnw_thunderbird_display_name` | `Naruto Uzumaki` |
| `fgnw_thunderbird_mail_domain` | `konohagakure.fire.ninja` |
| `fgnw_thunderbird_imap_server` | `konoha-mail.konohagakure.fire.ninja` |
| `fgnw_thunderbird_smtp_server` | `konoha-mail.konohagakure.fire.ninja` |

## Protocol defaults

Plaintext **IMAP 143 + SMTP 25** range-wide. This matches:

- the Sand Postfix/Dovecot stack (`fgnw_mac_mail_server`), which runs no TLS; and
- the three village Exchange servers once `FGNW-thunderbird.yml`'s pre-step has
  enabled the `MSExchangeIMAP4` / `MSExchangeIMAP4BE` services and set
  `LoginType: PlainTextLogin` on them.

The whole range is sealed off the internet by Phase 2 containment, so only
VLAN-local SMTP/IMAP traffic reaches these ports. If a real TLS story ever
lands, flip the ports + `fgnw_thunderbird_socket_type` + `_authentication`
together with the server-side config.

## Example invocation

```yaml
- hosts: konoha-ws1
  tasks:
    - ansible.builtin.include_role:
        name: fgnw_thunderbird
      vars:
        fgnw_thunderbird_user: naruto.uzumaki
        fgnw_thunderbird_display_name: Naruto Uzumaki
        fgnw_thunderbird_mail_domain: konohagakure.fire.ninja
        fgnw_thunderbird_imap_server: konoha-mail.konohagakure.fire.ninja
        fgnw_thunderbird_smtp_server: konoha-mail.konohagakure.fire.ninja
```

## Design notes

- **No identity defaults.** `defaults/main.yml` only sets protocol/path/install
  defaults; the five identity vars are required. `meta/argument_specs.yml`
  enforces this at include time.
- **One policies template, two branches.** Mozilla's enterprise policy JSON is
  the same on Windows and macOS; only the on-disk path and the file-write module
  differ. Keeps the two branches from diverging the way `fgnw_mac_thunderbird`
  did against the never-existed Windows path.
- **Install is OS-local.** The Windows branch installs Thunderbird here (behind
  containment via Nexus choco); the macOS branch installs *earlier* (phase 1c,
  via brew cask, before containment). The role tolerates both because the
  configure step is identical.
