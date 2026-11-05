The Windows 11 desktop derivative. **FGNW does not use this** — its workstations
are Windows 10, see
`../win10-22h2-x64-enterprise-appxfix`. This one is built alongside so a Win11
image with a working sysprep exists when something wants it.
A **Tier C** local derivative of the stock Ludus `packer/win11-22h2-x64-enterprise`
template. The stock directory is Tier A: `ludus-server --update` overwrites it,
so it cannot carry a local fix without joining the fragile post-update re-apply
list. This copy lives outside the `--update` blast radius and survives upgrades.
Like the server derivative, the shared `../common`, `../scripts` and `../ansible`
files are **vendored** into `iso/`, `scripts/` and `ansible/` so
`ludus templates add -d` works on this directory alone.

1. **`scripts/remove-appx-sysprep-blockers.ps1`**, added as the **final**
   provisioner — the point of the template.
2. `description` and `icon_path` variables added: Ludus stock templates carry no
   catalog metadata, and `ludus source add` reads these when the template is
   browsed in the picker.
3. `vm_name` → `win11-22h2-x64-enterprise-appxfix-template` (distinct from
   stock — the CLI refuses to unregister a built-in, so shadowing the stock name
   is not reachable; see the server derivative's README for the full history).
4. Vendored file paths (`../common/…` → `iso/…`, `../scripts/…` → `scripts/…`,
   `../ansible/…` → `ansible/…`).
`iso_url`, `iso_checksum` and `iso_download_pve = true` are stock's own —
unchanged (rule 9).
Identical reasoning to the Win10 derivative, and it applies *more* strongly
here: Windows 11 ships even more provisioned Store apps than Windows 10, and any
one of them left "installed for a user, but not provisioned for all users" makes
deploy-time sysprep hard-fail (symptom: `Timeout when waiting for <ip>:5986 to
stop`).
The server derivative targets Edge by name because Server 2022 ships essentially
one Store-signed AppX. On a desktop image that approach would pass its own
verification and still ship a template that fails sysprep on a different
package — a false green. This script enumerates the blocker **condition**,
removes what meets it, then re-evaluates and **fails the build** if anything
survives.
⚠️ **Cutover warning:** do not repoint any range config at
`win11-22h2-x64-enterprise-appxfix-template` until `ludus templates list` shows
it built.

```bash
ludus templates add -d templates/win11-22h2-x64-enterprise-appxfix
ludus templates build -n win11-22h2-x64-enterprise-appxfix-template
ludus templates logs -f
ludus templates list
```

Look for the `=== remove-appx-sysprep-blockers ===` transcript in the build log.
`iso_checksum` `sha256:ebbc7910…` (Windows 11 Enterprise Evaluation 22621.525)
is registered in `get_sybers.cluster` `meta/iso-inventory.yml` and present on
this cluster.
