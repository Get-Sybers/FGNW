Packer templates shipped by this Ludus source. One directory per template.
Reference: <https://docs.ludus.cloud/docs/using-ludus/sources> ·
<https://docs.ludus.cloud/docs/using-ludus/templates>
`ludus source add` registers these but does **not** build them — run
`ludus templates build -n <name>` afterwards. Built images are shared
instance-wide by name, so one build makes a template usable by every range.

- The registered template name (what `build` / `rm` / `status` take via `-n`) is the template's `vm_name` default in its `.pkr.hcl`, **not** its directory name.

```bash
ludus templates add -d templates/ninjasploitable
ludus templates build -n ninjasploitable-x64-server-template
```

| Directory | Registered name | What it is |
| --- | --- | --- |
| `ninjasploitable/` | `ninjasploitable-x64-server-template` | The deliberately vulnerable Linux web target for the Fourth Great Ninja War range — range-specific, so it ships with the blueprint. |
| `win2022-server-x64-appxfix/` | `win2022-server-x64-appxfix-template` | Windows Server 2022 with ALL AppX sysprep blockers removed and EdgeUpdate disabled at build time ( |
| `win10-22h2-x64-enterprise-appxfix/` | `win10-22h2-x64-enterprise-appxfix-template` | Windows 10 22H2 Enterprise (x64) with ALL AppX sysprep blockers removed at build time ( |
| `win2022-exchange2019-x64/` | `win2022-exchange2019-x64-template` | Windows Server 2022 with Exchange 2019 CU15 prereqs and media baked in at build; derived from `win2022-server-x64-appxfix`. **Required by the FGNW blueprint** (its `*-owa` hosts). |
| `macos-sequoia-15/` | `macos-sequoia-15-template` | macOS Sequoia 15.4, OpenCore-booted ( |

Every directory here is referenced by the FGNW blueprint (`blueprints/FGNW/range-config.yml`).

Two of them are not stock Ludus templates built straight from an installer ISO:

1. **Local derivatives of stock Ludus templates.** The stock template dirs that
   ship inside a Ludus install are overwritten by `ludus-server --update`, so
   they cannot carry a local fix. When a stock build genuinely needs one, the
   copy lives here instead — see `win2022-server-x64-appxfix/`.
2. **Console-driven OpenCore installs** for guests with no answer-file installer.
   macOS ships no preseed/autounattend equivalent and boots only through an
   OpenCore bootloader (which also emulates the Apple SMC via VirtualSMC), so it
   cannot use `proxmox-iso` at all. The `macos-sequoia-15/` template uses a Packer
   `null` source that just launches **Ansible** (`build.yml` → the `macos_template`
   role), which drives Proxmox over its REST API — no shell orchestration script —
   and the VM's console over the API's VNC websocket: **PREPARE** (download +
   verify both ISOs, stage the Recovery image out of the installer ISO, create the
   VM, erase the disk and run `startosinstall` from Recovery, inject a first-boot
   daemon that creates the user and enables SSH) then **FINALIZE** (provision
   in-guest over SSH, embed OpenCore onto the disk, and convert to a template) —
   all in one unattended `ludus templates build`. See its README.

- `win2022-server-x64-appxfix/` — derivative of the stock `packer/win2022-server-x64`
  template with ALL AppX sysprep blockers removed and EdgeUpdate disabled at
  build time.
  Registered under a name distinct from the stock one, which cannot be freed via
  the CLI, so the name must be chosen explicitly.
- `macos-sequoia-15/` — macOS Sequoia 15.4, built by an unattended **Ansible**
  build (a shared `macos_template` role, run by packer's `null` source) that boots
  macOS via **OpenCore** and drives the install from the VM console. The macOS
  installer ISO is yours to pin — the OpenCore ISO and QEMU-guest-agent checksums
  ship pinned and verified — and Proxmox verifies every download (the rule-9
  guarantee for media it can't fetch through `iso_url`). Apple ships no answer-file
  installer, so the role types the install into macOS Recovery over the API's VNC
  console and a first-boot daemon creates the user; one `ludus templates build` does
  it all. FINALIZE tunes the image for `ludus range deploy` — `localuser`/`password`
  creds, a **virtio** NIC (Ludus rewrites clones to virtio), a **QEMU guest agent**
  (Ludus resolves IPs only via the agent), working `/usr/bin/python3`, and clone
  hygiene — and embeds OpenCore onto the disk so the template self-boots. The qemu
  `args` line is root-only in Proxmox but is needed **only on AMD hosts** (the
  OpenCore ISO bundles VirtualSMC, so Intel needs no root step); its README shows the
  one `qm set` for AMD. Its README links its sources (the [klabsdev guide](https://klabsdev.com/definitive-guide-to-running-macos-in-proxmox/),
  [OSX-PROXMOX](https://github.com/luchina-gabriel/OSX-PROXMOX),
  [OpenCore-ISO](https://github.com/LongQT-sea/OpenCore-ISO), and more).
