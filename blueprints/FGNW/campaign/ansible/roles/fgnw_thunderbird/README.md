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
| Windows (`ansible_facts['os_family']: Windows`) | Fetches `thunderbird-<version>-win64-en-US.exe` from the range Nexus (`raw-hosted/tools/`, sha512-pinned) and runs it silently when Thunderbird is absent or not the pinned version | Drops `C:\Program Files\Mozilla Thunderbird\distribution\policies.json` with Mozilla's enterprise `EmailAccountSetup` policy |
| macOS (`ansible_facts['os_family']: Darwin`) | Fetches `thunderbird-<version>-mac-en-US.dmg` from the same place, attaches it and copies `Thunderbird.app` into `/Applications` when absent or not the pinned version | Drops `/Applications/Thunderbird.app/Contents/Resources/distribution/policies.json` with the same Mozilla policy schema |

Both branches share one Jinja template
(`templates/policies.json.j2`) that renders Mozilla's `EmailAccountSetup` block
with the five identity + routing vars.

## Where the installers come from, and why

Phase 4e runs inside Phase 2 containment, which seals internet egress. Neither
package manager can install Thunderbird there: the community Chocolatey
`thunderbird` package is a stub whose install script downloads the installer
from `download.mozilla.org` at install time (Nexus's `chocolatey-proxy` mirrors
only the package metadata, never that download), and a Homebrew cask fetches
from Mozilla's CDN the same way. So the role installs from the two installers
that [`nexus-cache-thunderbird.yml`](../../nexus-cache-thunderbird.yml) caches
on the range Nexus in Phase 0, while the controller still has internet:

| Artifact | Nexus path | Pin |
| --- | --- | --- |
| Windows installer | `raw-hosted/tools/thunderbird-<version>-win64-en-US.exe` | `fgnw_thunderbird_win_sha512` |
| macOS DMG | `raw-hosted/tools/thunderbird-<version>-mac-en-US.dmg` | `fgnw_thunderbird_mac_sha512` |

The pins are Mozilla's own, from
`https://archive.mozilla.org/pub/thunderbird/releases/<version>/SHA512SUMS`.
To move to a new release, change `fgnw_thunderbird_version` and both pins in
`defaults/main.yml` together, then run the cache play again before the next
containment; the role reinstalls wherever the installed version differs.

## Required vars (no defaults, by design)

A wrong default would silently point every workstation at the same server, so
the caller MUST pass these five:

| Var | Example |
| --- | --- |
| `fgnw_thunderbird_user` | `naruto.uzumaki` |
| `fgnw_thunderbird_display_name` | `Naruto Uzumaki` |
| `fgnw_thunderbird_mail_domain` | `konohagakure.fire.ninja` |
| `fgnw_thunderbird_imap_server` | `mail.konohagakure.fire.ninja` |
| `fgnw_thunderbird_smtp_server` | `mail.konohagakure.fire.ninja` |

The mail-server name is `mail.<domain>`: the A record the `dnsforwarder` role
publishes on each village DC (Phase 4). It is the only name the range's DNS
has for the mail servers — the VMs register under their Ludus hostnames
(`<range-id>-konoha-mail`, in the forest-root zone for Exchange) and the Sand
Mac never registers at all — so `vars/FGNW-thunderbird-map.yml` uses it.

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
        fgnw_thunderbird_imap_server: mail.konohagakure.fire.ninja
        fgnw_thunderbird_smtp_server: mail.konohagakure.fire.ninja
```

## Design notes

- **No identity defaults.** `defaults/main.yml` only sets installer / path /
  protocol defaults; the five identity vars are required.
  `meta/argument_specs.yml` enforces this at include time.
- **One policies template, two branches.** Mozilla's enterprise policy JSON is
  the same on Windows and macOS; only the on-disk path and the file-write module
  differ.
- **Install is version-checked, not package-managed.** Each branch reads the
  installed version (`thunderbird.exe`'s product version, the app bundle's
  `CFBundleShortVersionString`), installs only when it is absent or differs
  from `fgnw_thunderbird_version`, and verifies the result before writing the
  policy. The Windows installer runs with `/S /PreventRebootRequired=true
  /RemoveDistributionDir=false /MaintenanceService=false`, so an upgrade keeps
  `distribution\policies.json` and no updater is installed into a range that
  cannot reach Mozilla anyway.
