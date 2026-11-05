# Building the macOS template unattended

One `ludus templates build -n macos-sequoia-15-template` produces the registered
macOS template in a single unattended run: no console interaction, no second build,
no root step on an Intel host. The build is the shared `macos_template` role in the
`get_sybers.templates` collection, run by Packer's `null` source. This page explains
why the build is shaped the way it is and what is verified about it.

## Why the build looks like this

- **The installer ISO is invisible to UEFI/OpenCore** (it is an Apple Partition Map
  image). PREPARE extracts `BaseSystem.dmg` (macOS Recovery, a GPT disk OpenCore
  boots) out of the ISO with `7z`, converts it with `qemu-img`, uploads it to the ISO
  storage as `import` content (curl, headers from a 0600 file) and attaches it as
  `sata1` via `import-from`. No `args`, no `qm`, no root.
- **The "APFS sealing hang" at "Less than a minute remaining" is storage latency,
  not macOS.** The installer's last phase is a stream of small synchronous writes:
  on Ceph RBD ~20 ms each, ~100-200 writes/s, and the VM sits at that screen for
  well over 50 minutes still crawling (QMP `query-blockstats`: 35,000 s of
  cumulative write wait). On local storage the identical install (same ISO, same
  OpenCore v0.7, same VM shape) reaches Setup Assistant in 15-17 minutes. The role
  therefore installs on local storage whenever the template pool is a network type,
  and FINALIZE moves the finished disk (+ EFI vars) to the pool. `build_storage_pool`
  / `macos_template_build_storage` overrides the choice. The OpenCore kext/driver set
  (Lilu, VirtualSMC, WhateverGreen, VoodooPS2, AppleMCEReporterDisabler;
  OpenRuntime/OpenHfsPlus, APFS jumpstart) is the intended LongQT set and is not a
  factor.
- **Console driver** (`roles/macos_template/files/console/`, stdlib-only Python):
  opens the VM console through the Proxmox API (`vncproxy` + `vncwebsocket`, exactly
  what noVNC does; it needs only `VM.Console`, so it runs as the Ludus build user),
  recognises screens by pixel probes, and types into the Recovery Terminal: find the
  blank target disk, `diskutil eraseDisk APFS "Macintosh HD"`, `startosinstall
  --agreetolicense --nointeraction`, wait the installer out (black-screen reboot ->
  bright Setup Assistant). It then resets the VM, picks **macOS Base System** in the
  OpenCore picker (identified by the rendered label's column projection; the entry
  order flips after the install), and from Recovery writes the first-boot
  LaunchDaemon onto the installed Data volume as plain heredocs (Recovery has no
  base64/python) with an md5 check, plus `.AppleSetupDone`. Every shell step prints a
  green/red marker row the driver watches; every state change is logged with a PNG
  under the build's work dir.
- **First boot** (`files/firstboot/`): a LaunchDaemon creates the admin user
  (`localuser`/`password`, substituted at build time), enables Remote Login,
  suppresses Setup Assistant for that user, and removes itself. FINALIZE runs in the
  same build from there.
- **Provisioning details that exist for a reason:** the OpenCore EFI folder is
  extracted on the build host and pushed as a tarball, because macOS TCC blocks
  reading the removable OpenCore CD over SSH and `cp` onto the FAT32 ESP chokes on
  xattrs; the system disk is the APFS container holding "Macintosh HD", not the
  first APFS disk (that is the Recovery disk); the final power-off is
  `shutdown -h +1`, because `async` is unsupported on `raw`; the guest-agent install
  is idempotent, so FINALIZE can be re-run on an existing VM.

## What is verified

- **macOS Sequoia 15.4 builds end-to-end on a stock Ludus node** (Proxmox VE 9.2,
  Ludus 2.3, Intel host, Ceph RBD template pool, `local` dir build storage): one
  `ludus templates build` runs PREPARE, the console-driven install, first boot and
  FINALIZE unattended in about 25 minutes and registers the template `BUILT` in pool
  `SHARED`, with the system and EFI disks on the pool, OpenCore embedded and no ISO
  attached. The console driver works over the API's `vncwebsocket` transport with
  the Ludus build token.
- **The template deploys the way Ludus expects.** A linked clone boots from the
  pool, reports its IPv4 through the guest agent within about two minutes, accepts
  SSH as `localuser`/`password`, has a working `/usr/bin/python3`, and sudo prompts
  for the password - what Ludus's `group_vars/macos.yml` assumes.
- **The same role installs macOS Monterey 12.7.1** the same way (it is the version
  the console driver was developed against): the install reaches Setup Assistant
  unattended, the first boot creates `localuser` (admin, `com.apple.access_ssh`)
  and SSH works, the provision play runs clean, and the finished VM boots from the
  embedded OpenCore on Ceph with no ISO attached. Ventura, Sonoma and Tahoe are not
  part of this source.
- `yamllint --strict`, `ansible-lint --profile production` (collection + templates
  copy), the Ludus-source linter and every `scripts/check-*.py` gate pass.

## Operator notes

- Node prerequisites: `7z` (`apt install 7zip`), and the ISO storage must allow
  `import` content (`pvesm set local --content ...,import`). Both are asserted with a
  remedy message.
- Credentials must be printable ASCII (they are typed through the console).
- The build storage must be one the Ludus build token can allocate on. Ludus
  grants its users `Datastore.AllocateSpace` on its own VM and ISO storages only,
  so the role checks each local candidate's effective privileges
  (`/access/permissions`) and skips the ones it cannot use instead of failing at
  VM creation; on a stock Ludus node that selects the `local` dir storage over a
  bare `local-zfs`. The template's collection dependency is pinned to a commit, not
  `main`, so a build is reproducible.
