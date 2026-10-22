# fgnw_mac_ghosts_client

Installs the **GHOSTS v9 Universal client** (the cross-platform client of cmu-sei/GHOSTS) on the
Hidden Sand macOS workstation and runs it as a launchd daemon that reports to the range's ghost9
GHOSTS server. It is the macOS counterpart of what `jasonmull.ludus_ghosts_client` installs on
the Windows workstations. The outcome is a `com.cmu.sei.ghosts` LaunchDaemon that starts at boot,
is kept alive, logs under `/var/log/ghosts/` and drives the Gaara persona's timeline from the
ghost9 API.

The role is called twice per deploy, selected by `fgnw_mac_ghosts_client_phase`, because Phase 2
containment seals internet egress between the two halves:

| Phase | Play | `fgnw_mac_ghosts_client_phase` | Why there |
| --- | --- | --- | --- |
| 1c (pre-containment) | [`FGNW-mac-prestage.yml`](../../FGNW-mac-prestage.yml) | `prestage` | github.com is only reachable before containment |
| 4d (post-containment) | [`FGNW-mac-services.yml`](../../FGNW-mac-services.yml) | `service` | AD is up and the client can start reporting |

Both plays limit the include to `suna-ws1` with a `when` on `inventory_hostname`.

## What it does

`tasks/prestage.yml` (`prestage` or `all`):

1. Creates the install, config and log directories (`0755`).
2. Fetches the release tarball (`fgnw_mac_ghosts_client_tarball_url`) to `/tmp/ghosts-client.tar.gz`.
3. Extracts it into `fgnw_mac_ghosts_client_install_dir`.
4. Rewrites `ApiRootUrl` in `<install_dir>/config/application.json` to `fgnw_mac_ghosts_client_api_url`.

`tasks/service.yml` (`service` or `all`):

1. Writes `/Library/LaunchDaemons/<label>.plist` (root:wheel, `0644`): runs `<install_dir>/ghosts`
   from the install dir, `RunAtLoad` and `KeepAlive` true, stdout and stderr under the log dir.
2. Runs `launchctl bootstrap system <plist>`; a "service already loaded" answer counts as success.

## Inputs

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `fgnw_mac_ghosts_client_version` | no | `v9.0.0` | GHOSTS release tag the tarball URL is built from. |
| `fgnw_mac_ghosts_client_tarball_url` | no | derived from the version (see `defaults/main.yml`) | URL of the `ghosts-client-universal-osx-x64-<version>.tar.gz` release asset. |
| `fgnw_mac_ghosts_client_install_dir` | no | `/usr/local/ghosts` | Extraction target; the daemon runs `<install_dir>/ghosts`. |
| `fgnw_mac_ghosts_client_config_dir` | no | `/etc/ghosts` | Config directory created alongside the install. |
| `fgnw_mac_ghosts_client_log_dir` | no | `/var/log/ghosts` | Where the daemon's `stdout.log` and `stderr.log` go. |
| `fgnw_mac_ghosts_client_daemon_label` | no | `com.cmu.sei.ghosts` | launchd label and plist basename. |
| `fgnw_mac_ghosts_client_api_url` | no | `http://10.{{ ansible_host.split('.')[1] }}.99.51:5000/api` | `ApiRootUrl` written into `application.json`; the second octet comes from `ansible_host`. |
| `fgnw_mac_ghosts_client_phase` | no | `all` | `prestage`, `service` or `all`. |

The default of `fgnw_mac_ghosts_client_api_url` is rendered when the argument spec is validated,
at every include and in both phases, so `ansible_host` must be a dotted IPv4 address whenever the
role is included; the materialised infra inventory guarantees that (RANGENUMBER is substituted
into the second octet). `__fgnw_mac_ghosts_client_bootstrap` is an internal registered result,
not an input.

## Privilege and platforms

- Every task runs with `become: true` (sudo via the inventory's `ansible_become_pass`): the install
  directories, `/Library/LaunchDaemons` and `launchctl bootstrap system` all need root.
- Platform: macOS on x86_64 (the osx-x64 release asset).
- `prestage` needs internet egress to github.com; `service` needs a completed prestage on the same host.

## Idempotence

Yes. `get_url` downloads only when `/tmp/ghosts-client.tar.gz` is absent, `unarchive` reports a
change only when the archive's contents differ from what is on disk, the `ApiRootUrl` rewrite is a
no-op once in place, the plist converges, and a `launchctl bootstrap` that answers "service already
loaded" is reported `ok`. A second run of either phase therefore changes nothing.

## Failure and rollback

A failed download or extraction stops the role; the directories already created stay, nothing is
rolled back, and a re-run resumes from the failed step. The bootstrap task fails on any `launchctl`
error other than "service already loaded". The role never unloads or removes the daemon; undoing it
is `launchctl bootout system/<label>` plus deleting the plist by hand.

## Example invocation

From `FGNW-mac-services.yml` (Phase 4d):

```yaml
- name: Hidden Sand Village — GHOSTS Universal client (workstation only)
  hosts: macos_dev
  tasks:
    - name: "Mac-ghosts: start the GHOSTS Universal client (service only; prestage ran in Phase 1c)"
      ansible.builtin.include_role:
        name: fgnw_mac_ghosts_client
      vars:
        fgnw_mac_ghosts_client_phase: service
      when: inventory_hostname == 'suna-ws1'
```

`FGNW-mac-prestage.yml` (Phase 1c) is the same include with `fgnw_mac_ghosts_client_phase: prestage`.
