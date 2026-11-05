Ludus template for **Metasploitable2**, Rapid7's intentionally-vulnerable Ubuntu 8.04
target VM.
Most other Ludus templates in this repo build from an installer ISO via Packer's
`proxmox-iso` builder + a preseed/autounattend file (`metasploitable-3` shares
this template's import model). Metasploitable2 was never
released with installer media - it only ever shipped as a pre-built VMware disk
image (`.vmdk`) - so there's nothing for `proxmox-iso` to boot and install.
Instead this template uses a Packer `null` source and does the real work in
`scripts/import.sh`, driven entirely through the Proxmox REST API (the same auth
model the other builders use, since the `ludus` build user has no local root/`qm`
access on the node):

1. Download `metasploitable-linux-2.0.0.zip` and extract the `.vmdk` inside it.
2. Ensure the target storage (`proxmox_storage_pool`) has PVE's `import` content
   type enabled (added automatically the first time, via `PUT /storage/<pool>`).
3. Upload the vmdk to that storage with `content=import` and wait for the task.
4. Create a new VM whose `ide0` disk is `import-from=<uploaded volume>` (PVE 8.1+
   feature - this host runs PVE 9.1.4) on `ludus_nat_interface` (`vmbr1000`, the
   same build network every other template installs over), using `e1000`/`ide`/
   `kvm64` rather than the usual `virtio`/`host` - Metasploitable2 runs Linux
   2.6.24, which predates virtio driver support entirely (confirmed live: with
   virtio hardware the VM boots but never brings up a NIC).
5. Start it, poll `/var/lib/misc/dnsmasq.leases` for the DHCP lease matching the
   NIC's MAC (this image has no qemu-guest-agent, so that's the only way to learn
   its IP), then SSH in with `msfadmin`/`msfadmin` (with legacy
   HostKeyAlgorithms/KexAlgorithms/Ciphers re-enabled - this era's OpenSSH 4.7
   predates rsa-sha2, which modern OpenSSH clients require by default).
6. Run `ansible/provision.yml` over SSH via `ansible.builtin.raw` (Metasploitable2
   ships Python 2.4, which can't run modern Ansible's module wrapper at all -
   confirmed live: `SyntaxError` on `with open(...)` - so `raw`, which needs no
   Python on the target, is used for every task): regenerate SSH host keys one
   type at a time (`ssh-keygen -A` postdates this sshd), clear `/etc/machine-id`
   if present, best-effort install `qemu-guest-agent` (its apt mirrors are long
   dead, confirmed live - this reliably no-ops, bounded to a fast failure since
   this image predates coreutils `timeout`).
7. Hard-stop the VM (`status/stop`, not a graceful `status/shutdown` - confirmed
   live that ACPI powerdown just times out on this guest) and convert it to a
   Proxmox template (`POST .../template`) - the same end state `proxmox-iso`
   leaves you in, so `ludus templates build` still applies.

```bash
ludus templates add -d templates/metasploitable-2
ludus templates build -n metasploitable-2-x64-server-template
```

(The registered template name is `metasploitable-2-x64-server-template` - the
`vm_name` variable's default - not the directory name `metasploitable-2`; same
for `build`/`rm`/`status` and anywhere else you reference this template by name.)
Watch progress with `ludus templates status` / `ludus templates logs`. The build
downloads an ~865MB zip and uploads/copies a multi-GB disk image twice
(upload -> storage, then storage -> VM disk via `import-from`), so budget more
time than a typical ISO install and don't be surprised if it's disk-I/O bound.
`msfadmin` / `msfadmin` (also root via `su`/sudo on the box itself). Intentionally
weak - do not expose this VM outside an isolated range.

- The SourceForge URL is Rapid7's current official distribution point as of this
  writing. If it moves, you'll need to override `source_url` (and
  `source_archive_type`/`source_disk_glob` if the archive layout changes) - but
  `ludus templates build` has **no flag to pass extra `-var`s** (confirmed via
  `ludus templates build --help`), and Packer's `*.auto.pkrvars.hcl` auto-loading
  only applies when packer is pointed at a directory, not a specific `.pkr.hcl`
  file (confirmed live) - which is how the Ludus server always invokes it. So the
  only way to override any variable here is editing its `default` directly in
  `metasploitable-2.pkr.hcl` before `ludus templates add`.
- `agent=0` is set on the VM because Metasploitable2 doesn't ship qemu-guest-agent
  and its package mirrors are dead, so IP reporting in `ludus range list` for
  ranges using this template will rely on DHCP/ARP like any other agent-less VM.
- **Build evidence:** the `null`-source build is confirmed a Ludus template by
  Proxmox's own task log showing `qmtemplate OK` and `ludus templates list`
  showing `TRUE`, not by packer's "Build complete!" text alone (which is
  insufficient evidence — see below). Build time is a few minutes past the
  ~865MB download.
- Getting here took 5 real bugs, fixed and left as comments/notes in
  `scripts/import.sh` and `ansible/provision.yml` for future maintainers: the
  storage-content PUT needing `Datastore.Allocate` (fails silently as
  `range-admin@pam` without it - script now checks and errors clearly instead of
  discovering it later at upload time), `virtio` NIC/disk being invisible to this
  guest's kernel, modern OpenSSH refusing this era's host keys/KEX, Ansible's
  module system being unusable against Python 2.4, and graceful ACPI shutdown
  timing out (plus one where the script itself swallowed a Proxmox API error and
  reported success while the VM was still sitting there un-templated - the same
  "check the response, don't just check `<something> >/dev/null`" lesson applied
  to every `api ... POST` call after that).
