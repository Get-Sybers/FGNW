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
| `win11-22h2-x64-enterprise-appxfix/` | `win11-22h2-x64-enterprise-appxfix-template` | Windows 11 22H2 Enterprise, same AppX sysprep fix — a Win11 sysprep-capable image; no blueprint references it today. |
| `flare-vm/` | `flare-vm-template` | Windows malware-analysis workstation with FLARE VM tooling. |
| `metasploitable-2/` | `metasploitable-2-x64-server-template` | Metasploitable2 (Ubuntu 8.04) vulnerable target. |
| `metasploitable-3/` | `metasploitable-3-ub1404-x64-server-template` | Metasploitable3, Ubuntu 14.04 flavor. |
| `macos-tahoe-26/` | `macos-tahoe-26-template` | macOS Tahoe 26.0 (beta), OpenCore-booted ( |
| `macos-sequoia-15/` | `macos-sequoia-15-template` | macOS Sequoia 15.4, OpenCore-booted ( |
| `macos-sonoma-14/` | `macos-sonoma-14-template` | macOS Sonoma 14.1.1, OpenCore-booted ( |
| `macos-ventura-13/` | `macos-ventura-13-template` | macOS Ventura 13.6.3, OpenCore-booted ( |
| `macos-monterey-12/` | `macos-monterey-12-template` | macOS Monterey 12.7.1, OpenCore-booted ( |

1. **Pre-built disk image imports** that don't fit the stock pattern (Packer
   `proxmox-iso` builder + preseed/autounattend against an installer ISO).
   Metasploitable1/2/3 were never released with installer media, so these use a
   Packer `null` source and a `scripts/import.sh` that imports the vendor's own
   disk image into Proxmox via the API, provisions it once over SSH, and converts
   it to a template.
2. **Local derivatives of stock Ludus templates.** The stock template dirs that
   ship inside a Ludus install are overwritten by `ludus-server --update`, so
   they cannot carry a local fix. When a stock build genuinely needs one, the
   copy lives here instead — see `win2022-server-x64-appxfix/`.
3. **Interactive OpenCore installs** for guests with no unattended installer.
   macOS ships no preseed/autounattend equivalent and boots only through an
   OpenCore bootloader (which also emulates the Apple SMC via VirtualSMC), so it
   cannot use `proxmox-iso` at all. The `macos-*/` templates use a Packer `null`
   source that just launches **Ansible** (`build.yml` → the `macos_template`
   role), which drives Proxmox over its REST API — no shell orchestration script —
   in two phases: **PREPARE** (download + verify both ISOs, create and configure
   the VM, boot it for a one-time interactive macOS install) then **FINALIZE**
   (provision in-guest over SSH, embed OpenCore onto the disk, and convert to a
   template). `ludus templates build` is run twice; the phase is auto-detected
   from VM state. See each dir's README.

- `win2022-server-x64-appxfix/` — derivative of the stock `packer/win2022-server-x64`
  template with ALL AppX sysprep blockers removed and EdgeUpdate disabled at
  build time.
  Registered under a name distinct from the stock one, which cannot be freed via
  the CLI, so the name must be chosen explicitly.
- `flare-vm/` — requires `badsectorlabs.ludus_flarevm` to be added by the
  building user.
- `metasploitable-2/` — default `source_url` points at Rapid7's official
  SourceForge distribution; see its README's Caveats for the bugs that surfaced
  during bring-up (all fixed).
- `metasploitable-3/` — default `source_url` points at Rapid7's published
  Vagrant Cloud box.
- `macos-*/` — five macOS versions (Tahoe 26, Sequoia 15, Sonoma 14, Ventura 13,
  Monterey 12), all built the same way: a two-phase **Ansible** build (a shared
  `macos_template` role, run by packer's `null` source) that boots macOS via
  **OpenCore**. The macOS installer ISO
  is yours to pin — the OpenCore ISO and QEMU-guest-agent checksums ship pinned and
  verified — and Proxmox verifies every download (the rule-9 guarantee for media it
  can't fetch through `iso_url`). The macOS install itself is a one-time interactive
  console step, because Apple ships no unattended installer, so
  `ludus templates build` is run twice (PREPARE, then FINALIZE). FINALIZE tunes the
  image for `ludus range deploy` — `localuser`/`password` creds, a **virtio** NIC
  (Ludus rewrites clones to virtio), a **QEMU guest agent** (Ludus resolves IPs only
  via the agent), working `/usr/bin/python3`, and clone hygiene — and embeds OpenCore
  onto the disk so the template self-boots. The qemu `args` line is root-only in
  Proxmox but is needed **only on AMD hosts** (the OpenCore ISO bundles VirtualSMC,
  so Intel needs no root step); each README shows the one `qm set` for AMD. Each
  dir's README links its sources (the [klabsdev guide](https://klabsdev.com/definitive-guide-to-running-macos-in-proxmox/),
  [OSX-PROXMOX](https://github.com/luchina-gabriel/OSX-PROXMOX),
  [OpenCore-ISO](https://github.com/LongQT-sea/OpenCore-ISO), and more).
