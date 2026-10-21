> **Use this from the Ludus _Client_, not the Ludus Server.** This is the fast, client-driven
> path — the `ludus` CLI over the v2 API — to stand up the Fourth Great Ninja War range from
> `main`. Some scripts referenced here live in the **ludus-client** repo, e.g.
> `scripts/ludus-ra.sh` and `scripts/preflight.sh`.
>
> The heavy **server-side** deploy — the full `ansible-playbook deploy.yml` phase orchestration
> (content, Exchange, threat, emulation, verify) and its resume/variant machinery — is **not** a
> client path. It runs on the Ludus host; see [`DEPLOY.md`](DEPLOY.md).
> **AD is native now.** The six domains and the
> fire↔otogakure forest trust are built by `ludus range deploy` itself (native `domain:` blocks +
> `badsectorlabs.ludus_windows_utils` roles). AD _content_
> (OUs/groups/users/memberships) is client-drivable too:
> `get_sybers.range_password_policy` + `get_sybers.range_ad_mgmt`, wired onto all 6 DCs, so it runs
> during `ludus range deploy` at the user-defined-roles stage — no server-side Phase-3 tail needed.
From the ludus-client repo:

```bash
scripts/preflight.sh
source scripts/ludus-ra.sh
```

```bash
ludus source sync RA-get-sybers-fgnw
ludus source add  RA-get-sybers-fgnw --all --force
ludus source list RA-get-sybers-fgnw --catalog
ludus templates build -n all
ludus templates list
```

> **The telemetry roles are applied by the campaign plays.** `get_sybers.{sysmon,acsc_event_logging,
> sysmon_linux}` ship under this source's `ansible/roles/` and are applied by campaign playbooks at
> phase 4 (FGNW-sysmon.yml / FGNW-acsc-logging.yml / FGNW-sysmon-linux.yml) — NOT listed under
> any VM's `range-config.yml` `roles:`. The source-add step above installs them into the per-user
> roles path the playbooks resolve from at deploy.
A `source add` is a collection-install event — the server then runs the CVE gate
(`playbooks/pct-cve-check.yml -e pct_fix=true`, CVE-2026-16658). That's server-side; confirm it happened.
If a later `ludus range errors` shows `Timeout when waiting for <ip>:5986 to stop` plus
`SYSPRP MRTGeneralize:98 - ERROR: Failed ConnectServer`, the failing Windows template image is
stale. Remove the built image (`ludus templates rm -n <template-name>`), rebuild it, and only then
retry `ludus range deploy`.

```bash
ludus range config set -f range-config.yml
ludus range deploy
ludus range list
ludus range errors
```

To (re)apply just the **AD content** on an already-built range — without a full redeploy — limit
the run to the two AD roles at the user-defined-roles stage:

```bash
ludus range deploy --only-roles get_sybers.range_password_policy,get_sybers.range_ad_mgmt -t user-defined-roles
```

`range-config.yml` is the 23-VM superset, so setting it by hand deploys the `xl` set. Variants are
a flag on the server-side orchestrator, not a different file — `ansible-playbook deploy.yml
-e range_variant=small` (9 VMs) or `=xl` (23), no flag for the regular 22. See
[`RANGE-CONFIG-VARIANTS.md`](RANGE-CONFIG-VARIANTS.md).
> **`-f` uploads a LOCAL file** — it does not read the server's source tree. Run it from a checkout
> at the same commit you refreshed in Step 1 (or let the server-side `deploy.yml` set it from its own
> source tree), so you deploy the source-of-truth and not a drifted local copy.

```bash
ludus testing start
```

SSH onto the Ludus host and resume `deploy.yml` at `range_from_phase=3` (post-containment,
starts at AD build):

```bash
cd /opt/ludus/sources/<sourceID>/blueprints/FGNW/campaign
export LUDUS_API_KEY=<range-admin API key>
ansible-playbook deploy.yml -e range_from_phase=3
```

See [`DEPLOY.md`](DEPLOY.md) for phase tokens, resume flags, and variant handling.

```bash
ludus range list
ludus range logs -f
ludus range errors
```
