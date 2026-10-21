Ludus template for **macOS Monterey 12.7.1**, installed on Proxmox via the
[OpenCore](https://github.com/acidanthera/OpenCorePkg) bootloader and built with
Packer + Ansible.
> Registered template name: **`macos-monterey-12-template`** (the `vm_name` default) - not the
> directory name. Use it for `build` / `rm` / `status`. It **must contain `macos`** -
> Ludus keys its macOS deploy handling on that substring.
The Windows and Linux ISO templates here build with Packer's `proxmox-iso`
builder + an autounattend/preseed answer file. **macOS has no equivalent** - Apple
ships no unattended-install mechanism, so the OS install (Disk Utility format ->
Install macOS -> Setup Assistant -> create the first user) is unavoidably
**interactive**, done once at the Proxmox console/VNC. macOS also boots only
through an **OpenCore** bootloader, which `proxmox-iso` cannot drive, and it would
time out waiting for an SSH communicator that never appears.
So - like the metasploitable templates, which use a Packer `null` source because
no installer ISO fits `proxmox-iso` - this template uses a `null` source and does
the real work in **Ansible**, shipped in the `get_sybers.templates` collection each `.pkr.hcl`
installs and runs by FQCN (`ansible-playbook get_sybers.templates.build`):
[`build.yml`](../../ansible/collections/get_sybers.templates/playbooks/build.yml) runs the
[`macos_template`](../../ansible/collections/get_sybers.templates/roles/macos_template/) role, which drives Proxmox over
its REST API (no shell orchestration script). It runs in **two phases** that
`ludus templates build` steps through on successive runs (the phase is
auto-detected from VM state - Ludus can't pass extra `-var`s):

1. **PREPARE** (no VM yet): assert the ISO checksums, have Proxmox download +
   verify both ISOs (a bundled `proxmox_iso_download` module), create the VM with
   the full macOS layout, and boot it. On **Intel hosts no root step is needed** -
   the OpenCore ISO bundles VirtualSMC, so there is no `isa-applesmc`/OSK
   requirement; only **AMD hosts** need a one-time root `qm set --args` (PREPARE
   prints it). **No template exists yet** - you then do the one-time interactive
   install.
2. **FINALIZE** (VM installed + reachable over SSH): provision in-guest over SSH
   (install a guest agent + Command Line Tools, clone hygiene), embed OpenCore onto
   the disk ESP, remove the install media, and convert the VM to a Ludus template.
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
and verified**; only the macOS installer ISO is yours to pin. klabsdev publishes no digest, so record the
sha256 of the copy you fetch and set it in [`macos-monterey-12.pkr.hcl`](macos-monterey-12.pkr.hcl)
**before** `ludus templates add`:

```text
sha256sum macOS-Monterey-12.7.1.iso
```

`ludus templates build` has no flag to pass extra `-var`s, so editing the
`default`s in the `.pkr.hcl` is the only way to set these.

```bash
ludus templates add -d templates/macos-monterey-12
ludus templates build -n macos-monterey-12-template
```

PREPARE ends by printing what to do next. At the Proxmox **console/VNC** for the
new VM:

1. In the OpenCore boot picker, choose **Install macOS**.
2. **Disk Utility** -> erase the SATA disk as **APFS** (e.g. "Macintosh HD").
3. Install macOS (several automatic reboots - keep selecting the disk / "macOS
   Installer" in the OpenCore picker until it boots the installed OS).
4. In **Setup Assistant**, create the first user matching the template vars -
   **`localuser` / `password`** by default (skip Apple ID). This account needs sudo
   (Setup Assistant's first user is an admin).
5. Enable **Remote Login (SSH)** for that admin user - macOS 13+:
   *System Settings -> General -> Sharing -> Remote Login*; macOS 12:
   *System Preferences -> Sharing -> Remote Login*.
Then re-run the same command to finalize:

```bash
ludus templates build -n macos-monterey-12-template
```

Confirm success with `ludus templates list` showing this name `TRUE` - packer's
"Build complete!" for PREPARE only means the VM is ready to install, **not** that
a template exists. Watch progress with `ludus templates logs` (the Ansible output
is captured there).
> **AMD hosts only:** the qemu `args` option (forcing the CPU model) is
> `root@pam`-only in Proxmox. On AMD, PREPARE prints the exact
> `qm set <vmid> --args '...'` + `qm start <vmid>` to run once as root on the node,
> then continue at step 1. Intel hosts need none of this.
`localuser` / `password` (the `ssh_username` / `ssh_password` vars) - created by you
in Setup Assistant, used by FINALIZE, and what Ludus's macOS deploy expects.
Intentionally weak; an isolated-range template. Change both vars **and** Ludus's
`group_vars/macos.yml` together if you harden them.

- **Not verified end-to-end.** Authored to the Ludus / Packer / Ansible / template
  standards and cross-checked against Ludus's own macOS deploy code, but without a
  live Proxmox+macOS run - treat the first build as a bring-up and watch
  `ludus templates logs`. The macOS-specific knobs (`guest_cpu`, `guest_nic_model`,
  `vga`, `qemu_args`) are overridable variables; some hosts may need tuning.
- **Guest agent is third-party.** `mav2287/mac-guest-agent` (MIT) is downloaded
  in-guest and checksum-verified before install; it is required for Ludus IP
  discovery. Set `install_guest_agent = false` to opt out (then deploys must
  resolve IPs another way).
- **OpenCore is embedded on the disk ESP** by default (`embed_opencore`), so the
  finished template self-boots with no ISO attached; if that step fails it falls
  back to keeping the OpenCore ISO attached as the boot CD.
- **Command Line Tools install** needs Apple's software-update servers reachable
  from the build network (Ludus's NAT provides this). If it fails, install them
  once in the VM's Terminal (`xcode-select --install`) and re-run FINALIZE.
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
