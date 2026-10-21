Consolidated failure runbook — the "deploy broke, now what" decision tree. Run everything as the
`range-admin` (RA) identity.

```bash
ludus range list
ludus range errors
ludus range logs
```

---
**Usually transient, not a real failure.** A VM hadn't finished booting / reported its
guest-agent IP when its `roles:` play ran, so Ansible tried an unresolvable hostname (e.g.
`ra-oto-dc1` → NameResolutionError) or "No route to host" (e.g. attacker `10.<N>.99.50:22`,
N = your range number).

- **Confirm it's transient:** `ludus range list` — if every VM now shows `On` with an IP, it was
  timing. `IP=null` on a VM means it still hasn't reported one.
- **Fix:** re-run the idempotent deploy; roles re-apply on the now-reachable VMs. `ludus range
  deploy`, or the Phase 1 range-deploy role in `deploy.yml`, handles this retry path.
- `ERROR` is a **terminal** state (not the same as `DEPLOYING`) — anything polling for
  SUCCESS/FAILED only will hang on it.
`get_sybers.{sysmon,acsc_event_logging,sysmon_linux}` ship under this source's `ansible/roles/`
and are applied by the `FGNW-sysmon.yml` / `FGNW-acsc-logging.yml` / `FGNW-sysmon-linux.yml`
campaign playbooks at Phase 4 (post-containment, Nexus-sourced); they are not listed under any
VM's `roles:`, so `ludus source add RA-get-sybers-fgnw` prints no undeclared-dependency warning.
The source-add step in CLIENT-DEPLOY.md / QUICK-DEPLOY.md installs them into the per-user roles
path the campaign playbooks resolve from.
Fix it **at the build phase, in the role/config** — never as a manual live-only command (Rule 3;
containment later removes internet and silently breaks live-only fixes). Then resume with
`ansible-playbook deploy.yml -e range_variant=<variant> -e range_from_phase=<N>`.
- **Custom `tasks/`-based role fix didn't take?** Each user has an independent copy at
  `users/<user>/.ansible/roles/<role>/` that `ludus ansible role add` does NOT refresh — `cp` the
  patched source into range-admin's copy before redeploying.
- **Nexus actually down:** `/usr/sbin/qm list | grep -i nexus` (want `ADMIN-nexus-3-oss ...
  running`). Bring it up: `ludus range deploy -t nexus` → `ansible-playbook
  /opt/ludus/users/range-admin/.ansible/collections/ansible_collections/get_sybers/infra/playbooks/nexus-setup.yml`. See the `ludus-nexus-manage` skill. Windows package installs
  go through Nexus by default — don't expect a clean fall-back to raw internet.
- **Contained and a package step needs Nexus/internet:** `ludus testing start` blocks 192.0.2.2
  too. Surgically `ludus testing allow -i 192.0.2.2` → do the work → `ludus testing deny -i
  192.0.2.2`. Do NOT `ludus testing stop` (reverts snapshots).
- **Role can't find `aleemladha.ludus_exchange`:** export
  `ANSIBLE_ROLES_PATH=/opt/ludus/users/range-admin/.ansible/roles` before a direct
  `ansible-playbook` run.
- **⚠️ Exchange ISO must be staged.** The `aleemladha.ludus_exchange` role uses an Exchange 2019
  ISO at `/opt/ludus/resources/iso/` when present; if it is absent, Phase 4b falls back to the
  role's ~6 GB live-internet fetch, which runs *after* Phase 2 containment and cannot succeed.
  Stage the ISO before Phase 4b, or deploy with `-e range_skip_exchange=true`.
- **"Copy Exchange ISO to windows host" fails on read:** once an ISO *is* staged, it must be
  readable by the `ludus` controller user. Fix: `chown ludus:ludus <iso> && chmod 664 <iso>`.
- **Duplicate mail:** `FGNW-exchange-seed-mail.yml` is NOT idempotent — it was run twice against
  a forest. Only run it once per forest. See the `ludus-exchange-seed` skill.
- **Cross-forest send-connector play errors:** you widened `--limit` past one forest before the
  earlier forest finished installing. One forest at a time.
These are fixed in committed Ansible, but the failure signatures recur on every **new** forest,
so they are here rather than in a changelog. `FGNW-exchange.yml` carries the technical detail
inline as comments.
- **Schema/AD prep fails as a child-domain admin.** Exchange prep needs Enterprise/Schema
  Admins, which by default exist only in the **forest root**. `konohagakure.fire.ninja\Administrator`
  looks like a reasonable admin and is not one. Each mail server is joined to its forest root
  (`fire.ninja` / `wind.ninja`) for this reason; `otogakure.ninja` / `akatsuki.dark` are already
  forest roots and unaffected. The same trap applies to the mail-enable-groups and
  send-connector-mesh plays, and to ADCS.
- **`Unable to relay recipient in non-accepted domain`** on every send. Direct consequence of the
  above: Setup auto-creates an Accepted Domain for the *server's own* domain (`fire.ninja`), but
  the mailboxes are `@konohagakure.fire.ninja`, which was never registered. Register the child
  domain as an accepted domain.
- **CU15 Setup rejects `/IAcceptExchangeServerLicenseTerms`.** It needs
  `/IAcceptExchangeServerLicenseTerms_DiagnosticDataOFF`. Re-check this on any CU bump or role
  revendor.
- **`New-SendConnector -SourceTransportServers` does not accept the inventory alias.** Exchange
  only knows the real Windows computer name Ludus assigns (`RA-KONOHA-MAIL`, not `konoha-mail`).
  Query `$env:COMPUTERNAME` live rather than trusting the alias — this generalises to any Exchange
  cmdlet keyed on computer identity.
- **`ansible.windows.win_shell` free-form shlex-splits before templating.** Embedded escaped
  single quotes in a `Send-MailMessage` call break the parser; move the quoting into the task's
  own `vars:`. Separately, `.NET`'s `MailMessage.Subject` rejects embedded newlines outright
  (unlike `Body`) — a multi-line quote flowing into an auto-generated subject fails.
- **The small range's AD-build data never included the `-owa` hosts** (`inventory-small`,
  `config-small.json`). `FGNW-exchange.yml` therefore domain-joins them itself rather than
  re-running the ~37-minute AD build — that play is not redundant, do not remove it.
- **Cross-forest trust can't resolve the other forest:** each host's DNS must point at its DC
  first (range router only as fallback) — a host using the range router as primary DNS makes
  trust setup fail. Re-run `dnsforwarder.yml` for cross-village DNS.
- **`'domain_name' is undefined` running `dnsforwarder.yml`:** it needs the AD-build inventories
  (`data/inventory-small` + the providers inventory), NOT the infra inventory.
The range was rebuilt and old SSH host keys are stale. Clear them:

```bash
for ip in <attacker> <ninjasploitable> <ghosts> <kali>; do ssh-keygen -f /root/.ssh/known_hosts -R $ip; done
```

Clear them manually before rerunning Phase 3.
Its `sysmonforlinux` package pulls non-Microsoft deps (libssl-dev everywhere, libjson-glib on
Debian) the Nexus apt proxies don't cover — it needs **live internet**.
**There is no pre-containment window.** Containment is Phase 2 and `FGNW-sysmon-linux.yml` runs
inside Phase 4 (`deploy-tasks/phase4-content.yml`), so this play always executes contained.
Either add the deps to the Nexus apt proxy, or `ludus testing allow` the required host for the
duration of that play and deny it afterwards. Do **not** `ludus testing stop` — that reverts
snapshots.
Windows uses **WinRM https / port 5986** (not the 5985/http default) — check `group_vars/windows.yml`.
In-range creds are per-deploy: `ludus range inventory` (`ansible_password`, `ansible_user`).

- **`Timeout when waiting for <ip>:5986 to stop` + `SYSPRP MRTGeneralize:98 - ERROR: Failed ConnectServer`:**
  This is not a bad WinRM probe in FGNW. It means Sysprep never reached its reboot because the
  built Windows image is stale or missing the AppX-fix template content. Remove and rebuild the
  built image for the failing VM class before redeploying (`win2022-exchange2019-x64-template` for
  `*-owa`, `win2022-server-x64-appxfix-template` for DCs / other servers, and
  `win10-22h2-x64-enterprise-appxfix-template` for workstations).
Often **off-shift**, not broken. Personas run on a local-clock active-hours window (default
08:00–18:00, converted to UTC, wraps midnight); a persona with `night_share=0` logs only Quartz
"0 triggers" out of hours. Check the host's `timeline.json` `UtcTimeOn/UtcTimeOff` vs the VM's
current UTC before calling it a failure. See DEPLOY.md Phase 4.
- Destroy is `ludus range rm` (range-scoped) — it never touches Nexus. Confirm afterward:
  `/usr/sbin/qm list | grep -i nexus`.

---
See also: `DEPLOY.md` (phase sequence), `deploy-verification-checklist.md` (post-deploy checks),
and the `ludus-*` skills.
