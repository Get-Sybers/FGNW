Ludus template for **macOS Ventura 13.6.3**, installed on Proxmox via the
[OpenCore](https://github.com/acidanthera/OpenCorePkg) bootloader and built with
Packer + Ansible - **fully unattended**: one `ludus templates build` produces the
registered template with no console interaction.
> Registered template name: **`macos-ventura-13-template`** (the `vm_name` default) - not the
> directory name. Use it for `build` / `rm` / `status`. It **must contain `macos`** -
> Ludus keys its macOS deploy handling on that substring.
The Windows and Linux ISO templates here build with Packer's `proxmox-iso`
builder + an autounattend/preseed answer file. **macOS has no equivalent** - Apple
ships no answer-file installer, macOS boots only through an **OpenCore** bootloader
that `proxmox-iso` cannot drive, and the installer ISO is an Apple Partition Map
image that UEFI cannot even enumerate. So - like the metasploitable templates,
which use a Packer `null` source because no installer ISO fits `proxmox-iso` - this
template uses a `null` source and does the real work in **Ansible**, shipped in the
`get_sybers.templates` collection each `.pkr.hcl` installs and runs by FQCN
(`ansible-playbook get_sybers.templates.build`):
[`build.yml`](../../ansible/collections/get_sybers.templates/playbooks/build.yml) runs the
[`macos_template`](../../ansible/collections/get_sybers.templates/roles/macos_template/) role, which drives Proxmox over
its REST API and the VM's console over the API's VNC websocket:

1. **PREPARE**: assert the ISO checksums, have Proxmox download + verify both ISOs
   (a bundled `proxmox_iso_download` module); extract the installer's
   `BaseSystem.dmg` (macOS Recovery, a GPT disk OpenCore boots) with `7z`, convert
   it with `qemu-img`, upload it to the ISO storage as `import` content and attach
   it as a second disk; create the VM (q35/OVMF, OpenCore + installer CDs, virtio
   NIC, guest agent on ISA serial) and boot it. On **Intel hosts no root step is
   needed** - the OpenCore ISO bundles VirtualSMC; only **AMD hosts** need a
   one-time root `qm set --args` (PREPARE prints it, then re-run).
2. **Console-driven install**: the role's driver recognises screens by pixel probes
   and types into the Recovery Terminal - find the blank target disk, erase it as
   APFS "Macintosh HD", run `startosinstall --agreetolicense --nointeraction`,
   wait through the installer's reboots to Setup Assistant; then reset, pick
   **macOS Base System** in the OpenCore picker and, from Recovery, write a
   first-boot LaunchDaemon onto the installed Data volume (md5-verified) plus
   `.AppleSetupDone`. The first boot creates **`localuser` / `password`** (admin),
   enables Remote Login (SSH) and skips Setup Assistant for that user.
3. **FINALIZE** (same run): provision in-guest over SSH (install a guest agent +
   Command Line Tools, clone hygiene), embed OpenCore onto the disk ESP, remove the
   Recovery disk and install media, move the disk to the template pool if it was
   installed on local storage, and convert the VM to a Ludus template.
The role is standard Ansible (idempotent `uri` tasks, `assert` validation,
`block`/`rescue`, `no_log`/`become` for secrets) and needs no external collection;
see its [README](../../ansible/collections/get_sybers.templates/roles/macos_template/README.md).
FINALIZE bakes in what Ludus's macOS deploy path expects, so a built template
actually deploys: the first user is **`localuser` / `password`** with sudo, the NIC
is **virtio** (Ludus rewrites it to virtio on clone anyway), a **QEMU guest agent**
is installed (Ludus resolves a VM's IP only via the agent), **`/usr/bin/python3`**
is made to work via the Command Line Tools, and SSH host keys / saved network
interfaces are reset for clean cloning.
The build **refuses to run** until the macOS ISO is pinned, and Proxmox verifies
the download against it (the rule-9 guarantee `iso_url`+`iso_checksum` give the
stock templates). The OpenCore ISO and guest-agent checksums are **already pinned
and verified**; the macOS installer ISO's sha256 is pinned to the klabsdev
image. If you supply a different copy, record its sha256 and set it in
[`macos-ventura-13.pkr.hcl`](macos-ventura-13.pkr.hcl) **before** `ludus templates add`:

```text
sha256sum macOS-Ventura-13.6.3.iso
```

`ludus templates build` has no flag to pass extra `-var`s, so editing the
`default`s in the `.pkr.hcl` is the only way to set these.

## Host prerequisites

- `7z` (Debian package `7zip`) on the Proxmox node Ludus builds on; `qemu-img` and
  `curl` are always there.
- The ISO storage must allow **`import`** content as well as `iso`
  (`pvesm set local --content <existing>,import`), for the Recovery boot image.
- A local storage (ZFS/LVM-thin/dir) with ~90 GiB free when the Ludus pool is
  networked (Ceph RBD, NFS): the installer's final APFS seal is a stream of small
  synchronous writes that crawls for hours on networked storage, so the role
  installs locally and FINALIZE moves the finished disk to the pool. Set
  `build_storage_pool` to force a storage.

```bash
ludus templates add -d templates/macos-ventura-13
ludus templates build -n macos-ventura-13-template
```

Expect ~45-60 minutes on local SSD storage: ~5 min ISO staging, ~20 min install,
~10 min first boot + provisioning (the Command Line Tools download from Apple),
and the disk move to the pool. Watch `ludus templates logs`; the console driver
prints each state change (Recovery seen, Terminal opened, disk erased, installer
rebooted, install complete, Base System picked, daemon injected) and saves a PNG of
each under the build's `ANSIBLE_LOCAL_TEMP/macos-template/console-<vmid>/` on the
node. Confirm success with `ludus templates list` showing this name `TRUE`.
If the driver fails, the VM is left in place with those screenshots; `ludus
templates rm` it (or destroy the VM) and re-run.
> **AMD hosts only:** the qemu `args` option (forcing the CPU model) is
> `root@pam`-only in Proxmox. On AMD, PREPARE prints the exact
> `qm set <vmid> --args '...'` to run once as root on the node, then re-run the
> build: the role finds the VM and installs unattended. Intel hosts need none of this.
`localuser` / `password` (the `ssh_username` / `ssh_password` vars) - created by the
first-boot daemon, used by FINALIZE, and what Ludus's macOS deploy expects.
Intentionally weak; an isolated-range template. Printable ASCII only (they are
typed through the console). Change both vars **and** Ludus's `group_vars/macos.yml`
together if you harden them.

- **Not yet verified end-to-end for macOS Ventura 13.6.3.** The unattended flow was validated on
  macOS Monterey 12.7.1 (Proxmox VE 9.2 / Ludus 2.3, Intel host, Ceph RBD template pool,
  local ZFS build storage); this version uses the same role and media layout, so treat
  the first build as a bring-up and watch `ludus templates logs` / the console
  screenshots. The screen probes assume the 1280x800 console the `vmware` VGA gives
  OpenCore and Recovery.
- **Guest agent is third-party.** `mav2287/mac-guest-agent` (MIT) is downloaded
  in-guest and checksum-verified before install; it is required for Ludus IP
  discovery. Set `install_guest_agent = false` to opt out (then deploys must
  resolve IPs another way).
- **OpenCore is embedded on the disk ESP** by default (`embed_opencore`), so the
  finished template self-boots with no ISO attached; if that step fails it falls
  back to keeping the OpenCore ISO attached as the boot CD.
- **Command Line Tools install** needs Apple's software-update servers reachable
  from the build network (Ludus's NAT provides this). If it fails, re-run the
  build: FINALIZE resumes on the existing VM.
- **Licensing.** Apple's EULA restricts macOS to Apple-branded hardware; running
  it on non-Apple hosts is your compliance call. This template ships no Apple
  software, only automation around media you supply.
- **macOS ISO** - `source_url`, the klabsdev image named in the tracking issue,
  built from Apple's own installer assets (e.g. with
  [LongQT-sea/macos-iso-builder](https://github.com/LongQT-sea/macos-iso-builder)).
  Supply and verify your own copy.
- **OpenCore ISO** - [LongQT-sea/OpenCore-ISO](https://github.com/LongQT-sea/OpenCore-ISO)
  v0.7 (OpenCore is BSD-3-Clause); checksum pinned and verified.
- **Guest agent** - [mav2287/mac-guest-agent](https://github.com/mav2287/mac-guest-agent)
  v2.5.6 (MIT); checksum pinned and verified.
Sites and projects this template draws on:
- [klabsdev - The Definitive Guide to Running macOS in Proxmox](https://klabsdev.com/definitive-guide-to-running-macos-in-proxmox/) - the guide and ISO host named in the tracking issue.
- [luchina-gabriel/OSX-PROXMOX](https://github.com/luchina-gabriel/OSX-PROXMOX) - an automated macOS-on-Proxmox installer (AMD/Intel, High Sierra->Tahoe); a reference for the VM/OpenCore configuration and a good alternative if you want a fully guided root-run setup.
- [LongQT-sea/OpenCore-ISO](https://github.com/LongQT-sea/OpenCore-ISO) - the OpenCore boot ISO used here (bundles VirtualSMC; supports 10.4->26).
- [LongQT-sea/macos-iso-builder](https://github.com/LongQT-sea/macos-iso-builder) - builds macOS installer ISOs from Apple assets.
- [mav2287/mac-guest-agent](https://github.com/mav2287/mac-guest-agent) - the QEMU guest agent installed in-guest.
- [Nick Sherlock - Installing macOS on Proxmox](https://www.nicksherlock.com/2021/10/installing-macos-12-monterey-on-proxmox-7/) - the canonical write-up of the QEMU config, CPU flags, and OpenCore setup.
- [thenickdude/KVM-Opencore](https://github.com/thenickdude/KVM-Opencore) - the widely-used OpenCore images (through Ventura).
- [acidanthera/OpenCorePkg](https://github.com/acidanthera/OpenCorePkg) and the [Dortania OpenCore Install Guide](https://dortania.github.io/OpenCore-Install-Guide/) - upstream OpenCore.
- [Ludus - sources](https://docs.ludus.cloud/docs/using-ludus/sources/), [templates](https://docs.ludus.cloud/docs/using-ludus/templates/) - how this source and its templates are consumed.
- [Proxmox VE API viewer](https://pve.proxmox.com/pve-docs/api-viewer/) - the REST API the role drives.
- [ansible-collections/community.proxmox](https://github.com/ansible-collections/community.proxmox) - where the Proxmox Ansible modules now live (this role deliberately avoids depending on it; see the role README).
