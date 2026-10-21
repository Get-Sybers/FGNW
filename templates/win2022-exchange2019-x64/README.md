Windows Server 2022 with the **Exchange 2019 CU15 prerequisites and media baked in
at build time**, derived from
[`win2022-server-x64-appxfix`](../win2022-server-x64-appxfix/) (which itself removes the
Edge AppX sysprep blocker). Built for the FGNW `*-owa` hosts so
that a range deploy only has to run the **AD-bound** half of the Exchange install.
Everything the deploy-time `aleemladha.ludus_exchange` role would otherwise download and
install that does **not** need Active Directory, done once in the image:

- The full Exchange 2019 **Windows feature set** (`Install-WindowsFeature …`: `Web-*`,
  `RSAT-Clustering*`, `RPC-over-HTTP-proxy`, `Windows-Identity-Foundation`, `RSAT-ADDS`,
  `ADLDS`, …) plus the IIS6-management-compat optional features.
- The prerequisite runtimes: **.NET 4.8**, **VC++ 2013 x64**, the **IIS URL Rewrite**
  module, and the **UCMA 4.0 Runtime** (the exact installers the role pulls at deploy).
- The **Exchange 2019 CU15 media** staged at `C:\ludus\ExchangeServer2019-x64-cu15.iso`
  (sha256 `07c3fc16…629ae`, verified on download), where the role looks for it.
- A completion marker at `C:\ludus\exchange_prereqs_complete.txt`.
`/PrepareSchema`, `/PrepareAD`, `/Mode:Install /Role:Mailbox`, and mailbox/send-connector
creation — all of which require the host to be domain-joined. `aleemladha.ludus_exchange`
sees the marker + staged media and **skips its prereq + download blocks**, running only
these AD-bound steps.
The bake (`ansible/exchange-bake.yml`) is gated on the **same marker file the deploy role
checks**, so re-running the Packer build after a successful bake is a pure no-op, and the
deploy-time prereq block short-circuits on the same signal. Every step is independently
idempotent as well — `win_feature`/`win_optional_feature` converge on `state: present`,
`win_package` keys on the product code / `product_id`, `win_get_url` skips an unchanged
destination. The marker is written **last** (only once prereqs *and* media are present),
so a build interrupted mid-bake re-does the missing work instead of being falsely marked
complete.
The **boot** ISO (Server 2022 eval) uses `iso_url` + `iso_checksum` with
`iso_download_pve = true`, so Proxmox verifies the local copy and skips the transfer —
never `iso_file`. The Exchange CU15 media is **application content fetched during
provisioning** (via `win_get_url` inside the guest), not a Proxmox boot ISO — so it lives
in `iso-inventory.yml`'s model awkwardly (that registry is keyed by Proxmox volid + node).
Its identity is instead pinned where it is consumed: `checksum: "sha256:07c3fc16…629ae"`
on the bake play's download, verified before use. sha256 recorded here + in the play.

```bash
ludus templates add -d templates/win2022-exchange2019-x64
ludus templates build -n win2022-exchange2019-x64-template
```

`localuser` / `password`. The ~6 GB CU15 download makes this a long build; run it once.
