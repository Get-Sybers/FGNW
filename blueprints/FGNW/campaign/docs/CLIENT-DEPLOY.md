> **Scope: this builds the fully-instrumented range — everything except GHOSTS emulation and the
> attack plays.** One `ludus range deploy` (token `1`) stands up the VMs, native AD and everything
> `range-config.yml` lists: **AD content** — OUs, groups, users, memberships
> (`get_sybers.range_password_policy` + `get_sybers.range_ad_mgmt`,
> sysmon + ACSC event logging on the Windows VMs, and **real
> Exchange 2019** on the three Windows `-mail` servers) are applied by `range deploy` itself rather than by
> `campaign/deploy.yml`, so what **doesn't** happen is the emulation/attack tail: the Nexus cache
> seed (0), the ghost9 GHOSTS server CT (1b — a `get_sybers.lxc` container created on the PVE
> node from the published ghost9 template), content seeding (4), threat artefacts (4c), and
> GHOSTS emulation and verification (5).
>
> A range built this way is domain-joined, directory-populated, instrumented, and serving mail —
> but has no GHOSTS activity or attack plays on it. Completing the scenario means running
> `campaign/deploy.yml` **on the Ludus host** — see [`DEPLOY.md`](DEPLOY.md). That tail cannot be
> driven from a client: it SSH/WinRMs into range VMs at `10.<N>.x.x`, and a client has no route
> into the range networks. (The range-config roles above are not an exception — they run during
> `range deploy`, WinRM'd from the Ludus controller, not the client.)
From the ludus-client repo:

```bash
scripts/preflight.sh
source scripts/ludus-ra.sh
```

The RA range does not exist until you make it. Auth alone gets you a RA user with no RA range. Until `ludus range create` runs, every range/blueprint command that infers a target dies with `Range RA not found for user RA` — that's not a bug, it's the missing object. Don't chase it with `--url`; see the gotchas at the bottom.

```bash
ludus source sync RA-get-sybers-fgnw
ludus source add  RA-get-sybers-fgnw --all --force
ludus source list RA-get-sybers-fgnw --catalog
ludus blueprint list
```

> **Every role the blueprint names ships from this source.** `get_sybers.{sysmon,acsc_event_logging}`
> are listed in the blueprint's `range-config.yml` `roles:` and live under `ansible/roles/`
> beside the Exchange roles (`get_sybers.range_exchange` + `get_sybers.range_exchange_seed`);
> the source-add step above installs all of them into the per-user roles path `range deploy`
> resolves from, so run it before §3's deploy.
A source add is a collection-install event — the server then runs the CVE gate (`playbooks/pct-cve-check.yml -e pct_fix=true`, CVE-2026-16658). That's server-side; confirm it happened.
The range's VMs clone from built template images. A `source add --force` re-extracts the template
*definitions* but does not build the *images* — so a deploy against un-built or stale templates is a
common failure. The definitions come from two places: `ninjasploitable` and the generic Windows
appxfix/Exchange images from this source (`templates/`), and
`debian-12`/`kali` from stock Ludus — the full name-by-name list is `campaign/ludus-requirements.yml`
`templates.required`. Build them before creating the range:

```bash
ludus templates build -n all
ludus templates status
ludus templates list
```

`build` skips templates that are already built, so it is safe to run before every deploy. Templates
build on the server via packer; from here you only drive and watch them over the API. Do not run
`range create` / `range deploy` until `templates list` shows the FGNW templates built.
If `ludus range errors` later shows `Timeout when waiting for <ip>:5986 to stop` together with
`SYSPRP MRTGeneralize:98 - ERROR: Failed ConnectServer`, you are almost certainly reusing a stale
Windows image that predates the AppX fix. Remove the built image that matches the failing host
(`win2022-exchange2019-x64-template` for `*-mail`, `win2022-server-x64-appxfix-template` for DCs /
other servers, `win10-22h2-x64-enterprise-appxfix-template` for workstations), rebuild it, then
re-run the deploy.
The FGNW blueprint lives server-side and is applied to a range — it is not a local config file. On a fresh RA there is no range yet, so range create is the bootstrap: it makes the RA range object and seeds it from the blueprint in one shot. (blueprint apply on its own can't do this — it needs a range that already exists, so on a fresh RA it just returns `Range RA not found`.)

```bash
ludus range create -r RA --name "Fourth Great Ninja War" \
  --from-blueprint RA-get-sybers-fgnw/FGNW
ludus range default set RA
ludus range deploy
ludus range list
ludus range errors
```

Exchange is **real Exchange 2019** (`get_sybers.range_exchange` + `get_sybers.range_exchange_seed`)
on the three Windows `-mail` servers (`konoha-mail`, `oto-mail`, `dark-mail`; the Sand forest's
`suna-mail` is macOS Postfix/Dovecot), and it runs **last** — ordered after the DCs' AD-content
roles via `depends_on`, since it needs the directory in place.
To (re)apply just the **AD content** on an already-built range — without a full redeploy — limit
the run to the two AD roles at the user-defined-roles stage:

```bash
ludus range deploy --only-roles get_sybers.range_password_policy,get_sybers.range_ad_mgmt -t user-defined-roles
```

Sysmon and ACSC event logging are blueprint roles — `ludus range deploy` already installs
them on the Windows VMs, so there is nothing to add client-side. To re-run just those agents
on an already-built range — without a full redeploy — limit the run the same way as the
AD-content re-run above:

```bash
ludus range deploy --only-roles get_sybers.sysmon,get_sybers.acsc_event_logging -t user-defined-roles
ludus range list
```

The same `--only-roles … -t user-defined-roles` pattern re-runs any role the range config lists.
`testing start` snapshots the current fully-built state (VMs + native AD + AD content +
sysmon + ACSC + Exchange) as the **revert-to baseline**, then seals the range completely. Run
it *after* §3's deploy so everything is captured; a later `testing stop` reverts *to* this
populated state.

```bash
ludus testing start
ludus testing status
```

```bash
ludus range list
ludus range logs -f
ludus range errors
```

Destroying the range is a direct client CLI command (`ludus range rm`). Reclaiming the orphaned Ceph
disks it leaves behind is **client-driven through the `ludus` CLI too, in two moves**: *deliver* the
cluster role with `ludus source add`, then *run* it — via `ludus range deploy --only-roles` when the
range is built (the role's tasks delegate to the deploy's controller, pi-01), or via the wrapper
playbook on the server for the 0-VM teardown window. The storage step is the part that is easy to
get wrong, so it has its own subsection below.

```bash
ludus range rm
```

To rebuild templates from scratch, remove the old images first — `ludus templates build` **skips
already-built templates and has no --force flag**, so a stale image is never refreshed until it is
removed:

```bash
ludus templates rm -n <template-name>
```

`templates rm` will **not** remove Ludus's built-in template directories, only source-provided ones.
A range teardown does not always reclaim its Ceph RBD disks: PVE `qmdestroy` serialises through one
cluster-wide `cfs-lock 'storage-ludus-ceph'`, and under the ~20 concurrent destroys of a teardown the
losers time out, delete the VM config, and **leave the disk orphaned** (ERR-20, issue
pin their base template — so `ludus templates rm` of that base fails with *"base volume … is still in
use by linked cloned"* — and waste pool space.
The remediation is a **cluster role** (`get_sybers.cluster.cluster_ceph_orphan_sweep`), and on a
built range you drive it end-to-end from the client with the `ludus` CLI. First deliver it, then run
it via `range deploy`:

```bash
ludus source sync RA-get-sybers-proxmaxxing
ludus source add  RA-get-sybers-proxmaxxing --all --force
ludus range deploy --only-roles get_sybers.cluster.cluster_ceph_orphan_sweep -t user-defined-roles
```

**Why this works — three moving parts, all required:**

- **Config membership.** `--only-roles` *filters* the roles already named in the range config's
  per-VM `roles:` lists (stock Ludus resolves the run order from the config and gates each role
  with `when: role_name in only_roles` — it cannot inject a role that isn't listed). So the sweep
  role must first be **added** to a carrier VM's `roles:` list — the **`attacker`** VM is a natural
  choice (present in all three variants) — via `ludus range config get`/`set`. Without that entry,
  `--only-roles` has no candidate and silently runs nothing.
- **Delegation, not play targeting.** Stock Ludus applies user-defined roles **on the range VM**
  (the generated play is `hosts: <vm_name>`). The sweep works anyway because **every host-touching
  task in the role delegates to `localhost` — the deploy's ansible controller, which is pi-01**,
  where `rbd`/`pvesh`/`ceph` live (`ceph_orphan_sweep_delegate_to`, default `localhost`; the
  included `cluster_preflight` is delegated to the same host, so the root/PVE-node gates admit the
  host that acts). The carrier VM is only the vehicle; nothing executes on it.
- **A built range.** The user-defined-roles stage iterates the config's role-bearing VMs and stops
  at stock Ludus's *"\<vm\> is not in the Ansible inventory … need to do a full deploy?"* gate at
  the **first unbuilt one** — before any role runs, and regardless of `--only-roles`. So this path
  needs the range deployed; for the teardown window with no VMs, run the wrapper playbook on the
  server instead:

  ```bash
  cd /opt/ludus/users/range-admin/.ansible/collections/ansible_collections/get_sybers/cluster
  ansible-playbook -i inventories/cluster playbooks/cluster-ceph-orphan-sweep.yml
  ansible-playbook -i inventories/cluster playbooks/cluster-ceph-orphan-sweep.yml -e ceph_orphan_sweep_preview_only=false
  ```

**Preview vs apply.** The sweep previews by default and never auto-runs
(`ceph_orphan_sweep_preview_only: true`) — a `range deploy` run *reports* the orphans and touches
nothing. `ludus range deploy` has no `-e`; the apply toggle rides the range config: stock Ludus
`set_fact`s the config's `role_vars` / `global_role_vars` onto the VM's host context at the
user-defined-roles stage, where the role reads them. The deliberate apply is a three-step:

```bash
ludus range config get > /tmp/rc.yml
ludus range config set -f /tmp/rc.yml
ludus range deploy --only-roles get_sybers.cluster.cluster_ceph_orphan_sweep -t user-defined-roles
```

Two standing consequences of the carrier entry: a **full** deploy now also runs the sweep — in
preview that is a harmless read-only orphan report at the user-defined-roles stage, but the sweep's
preflight failing (e.g. `ceph` CLI unreachable) would fail that deploy; and **only `add --force`
makes a role change live** — a plain `source sync` refreshes the tree but leaves the installed
collection untouched.
**Do NOT reach for the Proxmox API to delete RBD volumes by hand.** Direct storage-content deletes go
through the very `cfs-lock` that stranded the disk, and bypass the sweep's gates:

1. the name must be exactly a per-VM disk (`^vm-<id>-disk-<n>`, never a `base-*` template,
   and never a snapshot `-state-`/cloudinit/fleece volume);
2. **no live guest config references it** — a QEMU VM *or* an LXC container. This catches both a dead
   VMID and a **VMID re-adopted by a later template build** (the case where a range disk orphaned by a
   timed-out destroy keeps its VMID and a new template grabs that VMID). Fail-closed: any incomplete
   read of the live-guest set aborts the sweep rather than mint a false orphan.
3. zero RBD watchers — a *runtime* backstop, not the logic gate.

- `cluster-ceph-diagnose.yml` — read-only Ceph health/orphan report; run this first.
- `cluster-ceph-orphan-sweep.yml` — the ERR-20 orphan reaper above.
- `post-update-reconcile.yml` — re-applies the local Ludus patches (incl. the ERR-13 empty-stdout
  guard) and the CVE fix after a `ludus-server --update` or a `source add --force` reverts them.
All three are `get_sybers.cluster` playbooks, delivered from the client with `ludus source sync` +
`ludus source add --all --force`. **Only the orphan sweep is `range deploy`-drivable** — it alone
delegates its tasks to the controller and sits in the range config as a carrier role. The other two
run the delivered collection against its bundled `inventories/cluster` inventory on the server.
