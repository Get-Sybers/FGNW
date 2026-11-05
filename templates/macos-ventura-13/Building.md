# Building the macOS templates unattended

These notes capture the build mechanism and the end-to-end validation recorded in
[FGNW#19](https://github.com/Get-Sybers/FGNW/pull/19) -- *Build the macOS templates
unattended (console-driven install, local build storage)* -- which took
`get_sybers.templates` to 0.2.0. They apply to the shared `macos_template` role
that every `templates/macos-*` directory builds with; the validation below was run
against macOS Monterey 12.7.1.

## Summary

`ludus templates build -n macos-*-template` now produces the macOS template in
**one unattended run** - no console interaction, no second build, no root step on
Intel hosts. `get_sybers.templates` goes to 0.2.0.

### What was blocking it, and what this changes

- **The installer ISO is invisible to UEFI/OpenCore** (it is an Apple Partition Map
  image). PREPARE now extracts `BaseSystem.dmg` (macOS Recovery, a GPT disk
  OpenCore boots fine) out of the ISO with `7z`, converts it with `qemu-img`,
  uploads it to the ISO storage as `import` content (curl, headers from a 0600
  file) and attaches it as `sata1` via `import-from`. No `args`, no `qm`, no root.
- **The "APFS sealing hang" at "Less than a minute remaining" is storage latency,
  not macOS.** Measured on the build host: the installer's last phase is a stream
  of small synchronous writes - on Ceph RBD ~20 ms each, ~100-200 writes/s, and the
  VM sat at that screen for >50 minutes still crawling (QMP `query-blockstats`:
  35,000 s of cumulative write wait). On a local zvol the identical install (same
  ISO, same OpenCore v0.7, same VM shape) completed to Setup Assistant in 15-17
  minutes, three times out of three. The role therefore installs on the local
  storage with the most free space whenever the template pool is a network type,
  and FINALIZE moves the finished disk (+ EFI vars) to the pool. `build_storage_pool`
  / `macos_template_build_storage` overrides it. The OpenCore kext/driver set (Lilu,
  VirtualSMC, WhateverGreen, VoodooPS2, AppleMCEReporterDisabler;
  OpenRuntime/OpenHfsPlus, APFS jumpstart) was checked against the ISO's
  `config.plist` and is the intended LongQT set for Monterey; it is not the cause.
- **Console driver** (`roles/macos_template/files/console/`, stdlib-only Python):
  opens the VM console through the Proxmox API (`vncproxy` + `vncwebsocket`, exactly
  what noVNC does - needs only `VM.Console`, so it works as the Ludus build user),
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
- **Provision-play bugs found by the first real end-to-end run** (the play had never
  been exercised): macOS TCC blocks reading the removable OpenCore CD over SSH, so
  the EFI folder is now extracted on the build host and pushed as a tarball (`cp`
  onto the FAT32 ESP also choked on xattrs); the "first APFS disk" heuristic picked
  the Recovery disk instead of the system disk; `async` on `raw` is unsupported and
  failed every FINALIZE (now `shutdown -h +1`); the guest-agent install was not
  idempotent on re-runs.

### Validation (Proxmox VE 9.2.9, Ludus 2.3.10, Intel host, Ceph RBD pool, local-zfs build storage)

- Three fresh Monterey 12.7.1 installs on local-zfs reached Setup Assistant
  unattended (two driven entirely by the driver's `install` stage); the inject stage
  booted Base System from the picker and injected the daemon; the first boot created
  `localuser` (admin, `com.apple.access_ssh`), SSH worked, `/var/db/.AppleSetupDone`
  present, daemon self-removed.
- The provision play ran clean against that guest (CLT/python3, guest agent,
  hostname, EFI embed, scheduled shutdown): `ok=19 changed=9 failed=0 rescued=0`.
- The FINALIZE API sequence (detach media, `move_disk` sata0 + efidisk0 to
  `ludus-ceph` with delete, cache mode) was exercised with the same parameters; the
  VM then booted from the embedded OpenCore on Ceph with no ISO attached and was
  SSH-reachable in 30 s.
- `yamllint --strict`, `ansible-lint --profile production` (collection + templates
  copy) and every `scripts/check-*.py` gate pass.
- Not exercised in this PR: the `vncwebsocket` transport under a real Ludus token
  (the driver was driven over the VNC unix socket in the dev harness; the websocket
  client follows noVNC's handshake and uses the token in the `Authorization` header
  like every other API call).

### Operator notes

- Node prerequisites: `7z` (`apt install 7zip`), and the ISO storage must allow
  `import` content (`pvesm set local --content ...,import`). Both are asserted with a
  remedy message.
- Credentials must be printable ASCII (they are typed through the console).
- The Tahoe/Sequoia/Sonoma/Ventura templates share the role and media layout but
  were not re-run here; their READMEs say so.
