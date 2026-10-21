Builds FGNW's deliberately exploitable Linux target ("Ninjasploitable") — a
Metasploitable-style box purpose-built to be broken into during range exercises.
It installs the vulnerable service stack (Apache + PHP, MariaDB, vsftpd, OpenSSH,
Samba, PostgreSQL, and best-effort telnetd), deploys intentionally vulnerable web
apps, opens up MariaDB and FTP, and creates the well-known `msfadmin` account. It
configures one VM in place, so it is a task-role (S2).
Per rule 7 the vulnerable content is meant to be **baked into the template**:
`main.yml` checks `/var/lib/ludus/ninjasploitable_content_baked` and runs the
`install` and `configure` stages only as a fallback for pre-bake templates. The
`configure_runtime` and `verify` stages always run. `verify.yml` asserts the core
services are up and the vulnerable web endpoints respond — the range §5/§6
requirement that a range role prove its vulnerability is actually present.

| `tasks_from:` | writes? | what it does |
| --- | --- | --- |
| `main.yml` | yes | bake check, then install/configure (fallback), configure_runtime, verify |
| `install.yml` | yes | apt-install the vulnerable service stack (pre-bake fallback) |
| `configure.yml` | yes | deploy the vulnerable web apps + passwordless-root MariaDB (pre-bake fallback) |
| `configure_runtime.yml` | yes | runtime-only host config: the `msfadmin` user and anonymous FTP |
| `verify.yml` | no | assert core services run and the vulnerable endpoints respond |
| name | default | purpose |

| --- | --- | --- |
| `ninjasploitable_admin_password` | `msfadmin` | Password for the `msfadmin` account — an intentionally public lab credential, not a secret. |
| `ninjasploitable_web_port` | `80` | Documents Apache's listen port (distro default 80); serving elsewhere would need extra `ports.conf`/vhost wiring, not done here. |
This role exists to weaken the host — it is the exercise target, and hardening it
would be a bug (range standard §0). The intentional vulnerabilities it
introduces:

- **SQL injection.** `/vulnerable/login.php` builds a raw SQL query by string
  interpolation of the POSTed username/password and prints the query back.
- **Unrestricted file upload.** `/vulnerable/upload.php` accepts any file with no
  type checking into `/var/www/html/uploads`, which is created **world-writable
  (`0777`)** for upload-exploitation practice.
- **Passwordless database root.** MariaDB `root@localhost` is set to an empty
  password via `mysql_native_password`, and a `vulnerable_db` is created.
- **Anonymous FTP.** vsftpd is configured with `anonymous_enable=YES`.
- **A published, well-known SSH credential.** `msfadmin` / `msfadmin` — and the
  server's own index page advertises it alongside `root` / (no password) for
  MySQL and `admin` / `admin` for the web app.
- **Cleartext remote access.** `telnetd` is installed best-effort (it may be
  absent from a given Debian release).
- **Floating, unpinned packages.** The service stack installs at `state: present`
  with no version pin — a deliberate judgement call (Debian point releases drop
  old versions, so pinning risks build breakage), left unhardened for this tier.
None of this is a defect to be fixed. The one thing the role does *not* weaken is
Ansible-output hygiene: the `msfadmin` password hash is written under `no_log`,
purely so a public-but-crackable hash does not land in task recaps.
