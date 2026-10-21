A local derivative of the stock `packer/win2022-server-x64` template. The
stock directory ships inside the Ludus install: it is overwritten by
`ludus-server --update`, so it cannot carry a local fix without joining the
fragile post-update re-apply list. This copy lives outside the `--update` blast
radius and survives upgrades.
**The only functional change from stock** is one added provisioner, run as the
final build step: `scripts/remove-appx-sysprep-blockers.ps1`, which (a) removes
**every** AppX package meeting the installed-but-not-provisioned blocker
condition (not just Edge, by name) and (b) disables the EdgeUpdate service pair
(`edgeupdate` / `edgeupdatem`) and sets `UpdateDefault=0` policy so the updater
cannot re-register a per-user Edge AppX between clone and sysprep. Everything
else is the stock build with the shared `../common`, `../scripts` and
`../ansible` files vendored into `iso/`, `scripts/` and `ansible/` so the
directory is self-contained for `ludus templates add -d`.
Deploy-time sysprep (`Sysprep Windows VMs` play in
`ansible/range-management/ludus.yml`) fails **without rebooting** when an AppX
package is "installed for a user, but not provisioned for all users". The
deploy symptom is `Timeout when waiting for <ip>:5986 to stop`. A deploy-time
rescue removes the package and retries sysprep, but this burns the full 600 s
`Wait for WinRM to stop` timeout per wave.
The original fix stripped the provisioned packages at bake
time, but the blocker **re-arises at runtime**: Edge's Win32 updater can
re-register a per-user Edge AppX on a running clone between the end of wave N
and the start of wave N+1 — and since the bake stripped the *provisioned*
Edge copy, any later per-user install is by construction "installed but not
provisioned". The win10 appxfix template avoids this by matching the blocker
*condition* (any non-framework, non-NonRemovable package installed-but-not-
provisioned) rather than a package name — and by not having an active Edge
updater post-clone. This template now matches that approach. See issue
`vm_name` is `win2022-server-x64-appxfix-template` — a distinct name from the
stock `win2022-server-x64-template`. This is the only workable approach: the
Ludus CLI refuses to remove the registration of a built-in template
(`templates rm` prints *"is a ludus server included template and cannot be
deleted"*), so shadowing the stock name from a user template is not reachable
from the client. All range configs that need the blocker-free image must
reference `win2022-server-x64-appxfix-template` explicitly — see
`users/range-admin/range-config.yml` and variants for the repoint.
⚠️ **Cutover warning:** do **not** repoint range configs to
`win2022-server-x64-appxfix-template` until `ludus templates list` on the target
server shows it as built/available. If you repoint first, deploys fail at VM
creation.

```bash
ludus templates add -d templates/win2022-server-x64-appxfix
ludus templates build -n win2022-server-x64-appxfix-template
ludus templates logs -f
ludus templates logs -t 50
ludus templates status
ludus templates list
```

In the build log, look for the `=== remove-appx-sysprep-blockers ===`
transcript sections: the first lists the EdgeUpdate service disable and policy
key, the second lists any packages found and removed, and **fails the build** if
any blocker remains installed-but-not-provisioned.
A full range deploy from the rebuilt template where the sysprep **rescue tasks
are skipped** — `Remove AppX packages reported by the failed Sysprep attempt`
and `Retry Sysprep ...` never run — not merely a deploy that succeeds after
retries (that was the pre-
2-OSD Ceph I/O constraint (ERR-22) is independent of the AppX blocker.
After any `ludus-server --update`, diff this directory against the refreshed
stock tree and fold in upstream changes:

```bash
diff -r packer/win2022-server-x64 templates/win2022-server-x64-appxfix \
  --exclude README.md --exclude iso --exclude scripts --exclude ansible
diff packer/common templates/win2022-server-x64-appxfix/iso
diff packer/scripts templates/win2022-server-x64-appxfix/scripts
diff packer/ansible/ngen.yml templates/win2022-server-x64-appxfix/ansible/ngen.yml
```

This is a drift check, not a re-apply: an upgrade cannot delete or revert this
directory, it can only make it stale.
