# Catalog metadata read by `ludus source add` when this template is browsed in the
# TUI/GUI picker. Packer requires a literal default, so this stays a static string.
variable "description" {
  type    = string
  default = "macOS Tahoe 26.0 (beta) for Ludus - OpenCore-booted on Proxmox. Two-phase Ansible build with a one-time interactive install; see README before building."
}
variable "icon_path" {
  type    = string
  default = "icon.png"
}
# macOS has no unattended installer (no preseed/autounattend equivalent) and boots
# only through OpenCore, so it cannot use Packer's proxmox-iso builder. Like the
# metasploitable templates it uses a "null" source; the real work is an Ansible
# role get_sybers.templates.macos_template (run by build.yml) that orchestrates Proxmox over its
# REST API. READ README.md before building - the OS install is a one-time
# interactive step, and the finished template is tuned for `ludus range deploy`
# (localuser creds, virtio NIC, a QEMU guest agent, working /usr/bin/python3).
variable "source_url" {
  type        = string
  default     = "https://cdn.klabsdev.com/MacImages/macOS-Tahoe-Beta-26.0.iso"
  description = "macOS installer ISO. Default is the klabsdev-hosted image from the issue-referenced guide. The Proxmox node must be able to reach this URL. This is beta media - re-pin source_url/source_checksum when a newer image is published."
}
variable "source_checksum" {
  type        = string
  default     = ""
  description = "REQUIRED: \"<algo>:<hex>\" digest of the macOS ISO. The build refuses to run without it, and Proxmox verifies the download against it (rule 9). No trustworthy published digest exists for this beta image, so record the sha256 of the copy you fetch: `sha256sum <file>` (or `shasum -a 256 <file>` on macOS)."
}
variable "source_iso_name" {
  type        = string
  default     = "macOS-Tahoe-Beta-26.0.iso"
  description = "Filename to store the macOS ISO under in iso_storage_pool."
}
variable "opencore_url" {
  type        = string
  default     = "https://github.com/LongQT-sea/OpenCore-ISO/releases/download/v0.7/LongQT-OpenCore-v0.7.iso"
  description = "OpenCore bootloader ISO (a separate CD/DVD macOS boots through; it bundles VirtualSMC so no isa-applesmc/OSK is needed). LongQT-sea/OpenCore-ISO supports Mac OS X 10.4 through macOS 26."
}
variable "opencore_checksum" {
  type        = string
  default     = "sha256:287328995d4198f1b05166f087d85bf7ef66bedafe150d17ad112ac8de60051d"
  description = "\"<algo>:<hex>\" digest of the OpenCore ISO, verified against the pinned LongQT-OpenCore-v0.7.iso release asset. Proxmox verifies the download against it; re-pin if you change opencore_url."
}
variable "opencore_iso_name" {
  type        = string
  default     = "LongQT-OpenCore-v0.7.iso"
  description = "Filename to store the OpenCore ISO under in iso_storage_pool."
}
variable "guest_cpu" {
  type        = string
  default     = "Skylake-Client-v4"
  description = "QEMU CPU model presented to macOS. Skylake-Client-v4 is the LongQT-recommended model for 10.11-26. On Intel hosts no qemu args are needed; on AMD hosts the role forces `-cpu <model>,vendor=GenuineIntel` via the root-only args line."
}
variable "guest_nic_model" {
  type        = string
  default     = "virtio"
  description = "NIC model. Ludus rewrites net0 to virtio on every clone at deploy, and virtio is the LongQT default for macOS 11+, so the template is installed/finalized on virtio to match."
}
variable "vga" {
  type    = string
  default = "vmware"
}
variable "vm_cpu_cores" {
  type    = string
  default = "4"
}
variable "vm_memory" {
  type    = string
  default = "8192"
}
variable "vm_disk_size" {
  type        = string
  default     = "80"
  description = "System disk size in GiB (integer). macOS needs ~30 GiB to install; this leaves lab headroom."
}
variable "vm_name" {
  type        = string
  default     = "macos-tahoe-26-template"
  description = "Registered template name. MUST contain 'macos' - Ludus keys its macOS deploy handling on that substring."
}
# QEMU guest agent baked into the guest - REQUIRED for `ludus range deploy`, which
# resolves a VM's IP only via the agent. mav2287/mac-guest-agent (MIT, ISA-serial).
variable "install_guest_agent" {
  type    = bool
  default = true
}
variable "guest_agent_url" {
  type    = string
  default = "https://github.com/mav2287/mac-guest-agent/releases/download/v2.5.6/mac-guest-agent"
}
variable "guest_agent_checksum" {
  type        = string
  default     = "sha256:fa501be5d8707b92b6b112d359007bb12163d5e95b3931f1fd7307b42afc03aa"
  description = "\"<algo>:<hex>\" digest of the guest-agent binary, self-verified against the pinned v2.5.6 release asset; checked in-guest before install."
}
# Install the Command Line Tools so /usr/bin/python3 works (Ludus deploy needs it).
variable "install_clt" {
  type    = bool
  default = true
}
# Copy OpenCore's EFI onto the disk ESP in FINALIZE so the template self-boots and
# both ISOs are removed (falls back to keeping the OpenCore ISO attached).
variable "embed_opencore" {
  type    = bool
  default = true
}
variable "balloon" {
  type    = string
  default = "0"
}
# Full override of the qemu args line (advanced / AMD tuning). Empty => the role
# sets args only on AMD hosts.
variable "qemu_args" {
  type    = string
  default = ""
}
# First-user credentials created interactively in Setup Assistant, then used by
# FINALIZE to SSH in and provision. Ludus's macOS deploy hard-codes these, so keep
# them unless you also change Ludus's group_vars. Intentionally weak - isolated range.
variable "ssh_username" {
  type    = string
  default = "localuser"
}
variable "ssh_password" {
  type    = string
  default = "password"
}
# This block has to be in each file or packer won't be able to use the variables
variable "proxmox_url" {
  type = string
}
variable "proxmox_host" {
  type = string
}
variable "proxmox_username" {
  type = string
}
variable "proxmox_password" {
  type      = string
  sensitive = true
}
# Proxmox API token - Ludus injects a token into packer's ENVIRONMENT (the
# proxmox-iso plugin logs "using token auth"); it leaves proxmox_username/password
# empty. `env()` is only valid in a variable default, so capture the token here and
# hand it to the Ansible build, which authenticates the same way the plugin does.
variable "pve_token_user" {
  type      = string
  default   = env("PROXMOX_USERNAME") # user@realm!tokenid
  sensitive = true
}
variable "pve_token_secret" {
  type      = string
  default   = env("PROXMOX_TOKEN") # the token secret
  sensitive = true
}
variable "proxmox_storage_pool" {
  type = string
}
variable "proxmox_storage_format" {
  type = string
}
variable "proxmox_skip_tls_verify" {
  type = bool
}
variable "proxmox_pool" {
  type = string
}
variable "iso_storage_pool" {
  type = string
}
variable "ansible_home" {
  type = string
}
variable "ludus_nat_interface" {
  type = string
}
####
locals {
  template_description = "macOS Tahoe 26.0 (beta) template built ${legacy_isotime("2006-01-02 03:04:05")} username:password => ${var.ssh_username}:${var.ssh_password}"
}
source "null" "macos-tahoe-26" {
  communicator = "none"
}
build {
  sources = ["source.null.macos-tahoe-26"]
  provisioner "shell-local" {
    environment_vars = [
      "PROXMOX_URL=${var.proxmox_url}",
      "PROXMOX_HOST=${var.proxmox_host}",
      "PROXMOX_USERNAME=${var.proxmox_username}",
      "PROXMOX_PASSWORD=${var.proxmox_password}",
      "PVE_TOKEN_USER=${var.pve_token_user}",
      "PVE_TOKEN_SECRET=${var.pve_token_secret}",
      "PROXMOX_INSECURE=${var.proxmox_skip_tls_verify}",
      "PROXMOX_STORAGE_POOL=${var.proxmox_storage_pool}",
      "PROXMOX_STORAGE_FORMAT=${var.proxmox_storage_format}",
      "PROXMOX_POOL=${var.proxmox_pool}",
      "ISO_STORAGE_POOL=${var.iso_storage_pool}",
      "LUDUS_NAT_INTERFACE=${var.ludus_nat_interface}",
      "VM_NAME=${var.vm_name}",
      "VM_MEMORY=${var.vm_memory}",
      "VM_CORES=${var.vm_cpu_cores}",
      "VM_DISK_SIZE=${var.vm_disk_size}",
      "BALLOON=${var.balloon}",
      "TEMPLATE_DESCRIPTION=${local.template_description}",
      "MACOS_ISO_URL=${var.source_url}",
      "MACOS_ISO_CHECKSUM=${var.source_checksum}",
      "MACOS_ISO_NAME=${var.source_iso_name}",
      "OPENCORE_ISO_URL=${var.opencore_url}",
      "OPENCORE_ISO_CHECKSUM=${var.opencore_checksum}",
      "OPENCORE_ISO_NAME=${var.opencore_iso_name}",
      "GUEST_CPU=${var.guest_cpu}",
      "GUEST_NIC_MODEL=${var.guest_nic_model}",
      "VGA=${var.vga}",
      "MACHINE=q35",
      "BIOS=ovmf",
      "EFI_TYPE=4m",
      "QEMU_ARGS=${var.qemu_args}",
      "INSTALL_GUEST_AGENT=${var.install_guest_agent}",
      "GUEST_AGENT_URL=${var.guest_agent_url}",
      "GUEST_AGENT_CHECKSUM=${var.guest_agent_checksum}",
      "INSTALL_CLT=${var.install_clt}",
      "EMBED_OPENCORE=${var.embed_opencore}",
      "SSH_USERNAME=${var.ssh_username}",
      "SSH_PASSWORD=${var.ssh_password}",
      "TASK_TIMEOUT=7200",
      "ANSIBLE_HOME=${var.ansible_home}",
      "ANSIBLE_LOCAL_TEMP=${var.ansible_home}/tmp",
      "ANSIBLE_PERSISTENT_CONTROL_PATH_DIR=${var.ansible_home}/pc",
      "ANSIBLE_SSH_CONTROL_PATH_DIR=${var.ansible_home}/cp",
      "ANSIBLE_COLLECTIONS_PATH=${path.root}/collections",
      "ANSIBLE_HOST_KEY_CHECKING=False",
      "ANSIBLE_RETRY_FILES_ENABLED=False",
      "ANSIBLE_LOCALHOST_WARNING=False",
      "ANSIBLE_DEPRECATION_WARNINGS=False",
      "ANSIBLE_PYTHON_INTERPRETER=auto_silent",
      "ANSIBLE_STDOUT_CALLBACK=default",
      "ANSIBLE_PIPELINING=True",
      "ANSIBLE_SSH_ARGS=-o ControlMaster=auto -o ControlPersist=60s -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null",
    ]
    # macOS can't use proxmox-iso; packer's null source installs the shared
    # get_sybers.templates collection (requirements.yml) and runs its build.yml
    # play by FQCN, which orchestrates Proxmox over its REST API.
    inline = [
      "ansible-galaxy collection install -r \"${path.root}/requirements.yml\" -p \"${path.root}/collections\" --no-deps --force",
      "ansible-playbook get_sybers.templates.build",
    ]
  }
}
