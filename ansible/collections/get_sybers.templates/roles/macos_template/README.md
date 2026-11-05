Builds a **macOS Ludus template on Proxmox** via the OpenCore bootloader,
orchestrated over the Proxmox REST API, **fully unattended**: one
`ludus templates build -n <name>` produces the registered template with no console
interaction. It is the single shared copy of this role, living only in this
collection; each `macos-*` template's `.pkr.hcl` installs the collection and runs its
`playbooks/build.yml` by its collection-qualified name (the collection name followed
by the playbook stem `build`), so the role is not duplicated per template.
The Proxmox modules moved out of `community.general` into a separate
[`community.proxmox`](https://github.com/ansible-collections/community.proxmox)
collection, which is **not guaranteed present** on every Ludus build host. To
avoid a fragile external dependency this role stays on **ansible-core only** —
`ansible.builtin.uri` for the API, the collection's own
`plugins/modules/proxmox_iso_download.py` module (called by FQCN as
`get_sybers.templates.proxmox_iso_download`) for Proxmox's `download-url` with
checksum verification and task polling, and a stdlib-only Python console driver
(`files/console/`) for the install itself. Every API task is guarded (query, then
act) so the role is **idempotent**.

## How the unattended install works

Apple ships no answer-file installer, and the installer ISO is an Apple Partition
Map image that UEFI/OpenCore cannot even see. The role works around both:

1. **PREPARE** (`tasks/prepare.yml`, no VM of that name yet): assert the ISO
   checksums and have Proxmox download + verify both ISOs; extract
   `BaseSystem.dmg` (the macOS Recovery image, a GPT disk OpenCore boots fine)
   out of the installer ISO with `7z`, convert it to raw with `qemu-img`, upload it
   to the ISO storage as `import` content and attach it as a second SATA disk
   (`import-from`); create the VM (q35/OVMF, OpenCore + installer CDs, virtio NIC,
   ISA-serial guest agent) and boot it. OpenCore auto-boots Recovery.
2. **Console driver** (`files/console/macos_unattended.py`): opens the VM's console
   through the Proxmox API (`vncproxy` + `vncwebsocket`, the path noVNC uses -
   needs only `VM.Console`, no root and no `qm`), recognises screens by pixel
   probes and types into the Recovery Terminal: find the blank target disk, erase
   it as APFS "Macintosh HD", run the full installer's
   `startosinstall --agreetolicense --nointeraction`, then wait through the
   installer's reboots until the installed OS reaches Setup Assistant. It then
   resets the VM, picks **macOS Base System** in the OpenCore picker (identified
   by its rendered label, the entry order is not stable), and from Recovery writes
   a first-boot LaunchDaemon onto the installed Data volume (typed as heredocs and
   md5-verified) plus `.AppleSetupDone`, and reboots. Each shell step prints a
   green/red marker row the driver watches for, and every state change is logged
   with a PNG under `macos_template_work_dir/console-<vmid>/`.
3. **First boot** (`files/firstboot/ludus-first-boot.sh`, run once by
   `com.ludus.firstboot`): create the admin user (`localuser` / `password` by
   default), enable Remote Login (SSH), suppress Setup Assistant for that user,
   self-destruct.
4. **FINALIZE** (`tasks/finalize_discover.yml` → provision → `finalize_convert.yml`):
   find the guest IP (DHCP lease), provision in-guest over SSH (guest agent, Command
   Line Tools / `python3`, clone hygiene, OpenCore embedded onto the disk ESP),
   detach the Recovery disk and install media, move the system disk to the template
   pool if it was installed elsewhere, and convert to a template.

Re-running the build on an existing (not yet templated) VM runs FINALIZE only;
on an existing template it is a no-op.

### Storage: why the install may run on a local disk

The installer's last phase (the APFS system snapshot + seal, "Less than a minute
remaining") is a long stream of small synchronous writes. On network storage it
crawls - on Ceph RBD, ~20 ms per write, ~100-200 writes/s - and sits at that
screen for hours; on a local zvol the same install finishes in ~15 minutes. So
when the Ludus template pool is a networked type (`macos_template_network_storage_types`)
the role installs on the local storage with the most free space
(`macos_template_local_storage_types`) **that the build token can allocate on**, and
FINALIZE moves the finished disk (and the EFI vars disk) to the template pool.
Ludus grants its users rights on its own VM and ISO storages only, so the role asks
the API for the token's effective privileges on each candidate
(`GET /access/permissions?path=/storage/<id>`) and skips any without
`Datastore.AllocateSpace` - it reports what it skipped, and falls back to the pool
(slow, with a warning) when no local storage is usable. Set
`macos_template_build_storage` to force a storage; the build then refuses to run if
the token cannot allocate on it, naming the privilege to grant. The system disk is
built with `cache=unsafe` (no flushes) and templated with
`macos_template_disk_cache_final` (`writeback`).

### Build-host requirements

- The build runs on the Proxmox node (it reads the Ludus NAT's DHCP leases and
  `/proc/cpuinfo`), as whatever user Ludus runs Packer as - nothing needs root.
- `7z` (Debian package `7zip`) and `qemu-img` (always present on a node) on the
  build host; `curl` for the upload.
- The ISO storage must allow `import` content (`pvesm set local --content ...,import`).
- The Proxmox token needs the usual VM admin rights plus `VM.Console` (in
  `PVEVMAdmin`) and `Datastore.AllocateTemplate` on the ISO storage (already
  required for the ISO downloads).
- For a fast install when the template pool is networked, the token also needs
  `Datastore.AllocateSpace` on one local storage (the `PVEDatastoreUser` role on
  `/storage/<id>` for the Ludus users group). Ludus does not grant this by
  default; without it the role still builds, on the pool, slowly.

Ludus's own macOS deploy path drove several of these — without them a built
template will not deploy with `ludus range deploy`:

- **User `localuser` / `password`** with sudo (Ludus's `group_vars/macos.yml`).
- **virtio NIC** — Ludus rewrites `net0` to virtio on every clone, so the template
  must be installed and finalized on virtio too.
- **QEMU guest agent** (`mav2287/mac-guest-agent`, MIT, ISA-serial) — Ludus resolves
  a VM's IP only via the guest agent; the VM is created with `agent=enabled=1,type=isa`.
- **Working `/usr/bin/python3`** via the Command Line Tools — Ludus's deploy uses
  real Ansible modules with `ansible_python_interpreter: /usr/bin/python3`.
- **Clone hygiene** — regenerated SSH host keys, reset network interfaces, disabled
  automatic software updates.
- The registered `vm_name` **must contain `macos`** — Ludus's inventory keys the
  macOS handling on that substring.

| Variable | Meaning |
| --- | --- |
| `macos_template_api_host` | Proxmox API base URL (`https://host:8006`) |
| `macos_template_api_user` | token id `user@realm!tokenid` (or `user@realm` for ticket auth) |
| `macos_template_api_token_secret` | API token secret (preferred auth); else `macos_template_api_password` |
| `macos_template_node` | Proxmox node name |
| `macos_template_storage_pool` / `macos_template_storage_format` | template disk storage + format |
| `macos_template_build_storage` | storage the install runs on (empty = auto, see above) |
| `macos_template_iso_storage` | storage holding the ISOs (must allow `iso` and `import` content) |
| `macos_template_pool` | Proxmox resource pool |
| `macos_template_bridge` | build network bridge (Ludus NAT, e.g. `vmbr1000`) |
| `macos_template_vm_name` | registered template name (**must contain `macos`**) |
| `macos_template_iso_url` / `macos_template_iso_checksum` / `macos_template_iso_name` | macOS installer ISO |
| `macos_template_opencore_url` / `macos_template_opencore_checksum` / `macos_template_opencore_name` | OpenCore ISO |
| `macos_template_description` | Proxmox description string |

`macos_template_guest_cpu` (`Skylake-Client-v4`), `macos_template_guest_nic_model` (`virtio`),
`macos_template_vga` (`vmware`), `macos_template_machine` (`q35`), `macos_template_bios` (`ovmf`),
`macos_template_efitype` (`4m`), `macos_template_qemu_args` (full override; AMD tuning),
`macos_template_balloon` (`0`), `macos_template_vm_memory`/`macos_template_vm_cores`/`macos_template_vm_disk_size`,
`macos_template_ssh_username`/`macos_template_ssh_password` (`localuser`/`password`, printable ASCII),
`macos_template_install_guest_agent` + `macos_template_guest_agent_url`/`macos_template_guest_agent_checksum`,
`macos_template_install_clt`, `macos_template_embed_opencore`, `macos_template_skip_provision`,
`macos_template_validate_certs`, `macos_template_task_timeout`, `macos_template_ip_retries`,
`macos_template_ssh_wait_timeout`, `macos_template_install_timeout`, `macos_template_console_boot_timeout`,
`macos_template_work_dir`, `macos_template_basesystem_name`, `macos_template_disk_cache_build`,
`macos_template_disk_cache_final`, `macos_template_network_storage_types`, `macos_template_local_storage_types`.
The Proxmox token/password and the guest SSH password arrive from the Ludus build
environment at runtime (never committed). Tasks that template a secret into a fact,
a header file or an `add_host` set `no_log: true`; the console driver receives the
token secret through its environment, not its command line; in-guest privileged
steps use `become` (the password comes from `ansible_become_pass`, never a command
line). Run the build without `-vvv` to keep the API token out of task dumps.
VM creation runs only when no VM of that name exists; the Recovery image staging,
`args`, `start`, and the ISO downloads all check current state first. If the
console driver fails, the VM is left in place with its screenshots for inspection;
destroy it (or finish the install by hand) and re-run. Provisioning flags success on
localhost; FINALIZE converts to a template **only** if provisioning succeeded (or
was explicitly skipped), so a half-configured VM is never templated — just re-run
to resume.

Builds macOS Sequoia 15.4 end-to-end on a stock Ludus 2.3 node (Proxmox VE 9.2,
Intel host, Ceph RBD template pool, `local` dir build storage) with LongQT-OpenCore
v0.7 - one unattended `ludus templates build`, template `BUILT` in pool `SHARED`, a
clone that reports its IP through the guest agent and accepts SSH as `localuser`.
The same role installs macOS Monterey 12.7.1 the same way.
The screen probes assume the 1280x800 console the `vmware` VGA gives OpenCore and
Recovery; a different `macos_template_vga` may need the coordinates in
`files/console/macos_unattended.py` adjusted.
