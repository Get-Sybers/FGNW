The **workstation** counterpart to `win2022-server-x64-appxfix`. FGNW
workstations run **Windows 10**; this is the image they use.
Derived from `templates/win10-22h2-x64-enterprise` in the **Bad Sector Labs**
Ludus source ([`badsectorlabs/ludus-source-bsl`](https://github.com/badsectorlabs/ludus-source-bsl),
AGPL-3.0-or-later), which is registered on this server as source
`5yioto0c3emh3cn`. Upstream ships it already self-contained (`icon.png`,
`Autounattend.xml`, `scripts/`, `iso/`), so this copy is upstream's files plus
the changes listed below. It keeps a **distinct** `vm_name` rather than
shadowing upstream's — same reasoning as the server derivative.

1. **`scripts/remove-appx-sysprep-blockers.ps1`**, added as the **final**
   provisioner. This is the point of the template.
2. **`iso_download_pve = true`.** Upstream omits it; the Ludus stock templates
   set it. With it, Proxmox verifies the copy it already holds against
   `iso_checksum` and skips a 5.5 GB download. Repo rule 9 prescribes exactly
   this, and explicitly forbids the alternative of swapping to `iso_file`
   (which would discard verification). `iso_url` + `iso_checksum` are unchanged.
3. `vm_name` → `win10-22h2-x64-enterprise-appxfix-template`; description
   updated to say what it is.
Nothing else is touched — no structural rewrite (rule 9).
The server derivative targets **Edge by name**, because a Server 2022 image
ships essentially one Store-signed AppX package and Edge is it.
A desktop image is the opposite. Windows 10 ships dozens of provisioned Store
apps, and **any** of them can end up "installed for a user, but not provisioned
for all users" — the exact condition sysprep's cleanup providers hard-fail on
(deploy symptom: `Timeout when waiting for <ip>:5986 to stop`). A per-user copy
being updated past the provisioned version is enough to cause it.
So an Edge-only script here would remove Edge, verify "no Edge blocker
remains", pass its own check — and still ship a template that fails sysprep at
deploy time on some other package. That is a false green of precisely the kind
this repo exists to prevent.
This script therefore matches the **condition**, not a package name:

- enumerate every non-framework, removable package installed for any user whose
  name is absent from the provisioned list;
- remove the per-user installs;
- **re-evaluate the condition** and **fail the build** if any blocker survives.
The server script already anticipated this — it logs non-Edge packages in the
same state as "potential future sysprep blocker" (non-fatal). Here they are the
primary target, and they are fatal.
⚠️ **Cutover warning:** do **not** repoint range configs at
`win10-22h2-x64-enterprise-appxfix-template` until `ludus templates list` shows
it built. Repointing first makes deploys fail at VM creation.

```bash
ludus templates add -d templates/win10-22h2-x64-enterprise-appxfix
ludus templates build -n win10-22h2-x64-enterprise-appxfix-template
ludus templates logs -f
ludus templates list
```

In the build log look for the `=== remove-appx-sysprep-blockers ===` transcript:
it lists every blocker found and removed, and **fails the build** if any
remains.
`iso_checksum` `sha256:ef7312733a9f…` is registered in `get_sybers.cluster`
`meta/iso-inventory.yml` (rule 9: the checksum is the identity), and the file is
present on this cluster.
