A Debian 12 target with the packages and vulnerable web content the FGNW
"ninjasploitable" host needs **baked into the image at build**, so a fresh clone
already serves the themed attack surface before any deploy step. Derived from the community
[`ludus-source-bsl`](https://github.com/badsectorlabs/ludus-source-community) Debian
template (proxmox-iso + preseed), retargeted to Debian 12.1.0.
Both apt sets that get blocked once the range is contained:

- **Vulnerable-service packages** (`get_sybers.range_ninjasploitable_server`): `apache2`,
  `apache2-utils`, `php`+modules, `libapache2-mod-php`, `mariadb-server`/`-client`,
  `python3-pymysql`, `vsftpd`, `openssh-server`, `samba`, `postgresql`.
- **AD-join packages** (`FGNW-ninjasploitable-join.yml`): `realmd`, `sssd`, `sssd-tools`,
  `adcli`, `samba-common-bin`, `krb5-user`, `packagekit`, `libnss-sss`, `libpam-sss`,
  `oddjob`, `oddjob-mkhomedir`.
- **Vulnerable web content**:
  - `/var/www/html/vulnerable/login.php` (SQLi demo)
  - `/var/www/html/vulnerable/upload.php` + `/var/www/html/uploads` (unvalidated upload)
  - `/var/www/html/reports/intake.php` + `/var/www/html/reports` (Land of Fire intake portal)
  - `/var/www/html/index.html` themed landing page
  - Apache module enables (`php`, `rewrite`, `headers`)
  - MariaDB intentional vulnerability (`root` passwordless + `vulnerable_db`)
Deploy-time tasks are reduced to range/domain-specific runtime configuration
(notably the `fire.ninja` AD join and per-range IP/DNS decisions) plus
non-content host settings like user/FTP config. Baked content is marker-gated so
deploy skips reapplying it.
`ansible/ninjasploitable-bake.yml` is gated on a marker
(`/var/lib/ludus/ninjasploitable_content_baked`) written **last**, so a rebuild after a
good bake is a pure no-op and an interrupted build re-does only the missing work. `apt`
`state: present` is itself idempotent. `krb5-user` is preseeded so the build never blocks
on its interactive realm prompt.
Boots the Debian 12.1.0 netinst ISO with `iso_url` + `iso_checksum` and
`iso_download_pve = true` (Proxmox verifies the local copy, skips the transfer — never
`iso_file`). The preseed is vendored in `http/`, so **no base template or extra
`source add` is required** — `ludus templates add -d templates/ninjasploitable`
builds it standalone.

```bash
ludus templates add -d templates/ninjasploitable
ludus templates build -n ninjasploitable-x64-server-template
```

`debian` / `debian`.
