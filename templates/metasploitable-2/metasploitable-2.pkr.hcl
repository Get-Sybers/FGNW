# Catalog metadata read by `ludus source add` when this template is browsed in the
# TUI/GUI picker. Packer requires a literal default, so this stays a static string.
variable "description" {
  type    = string
  default = "Metasploitable2 (Ubuntu 8.04) vulnerable target, imported from Rapid7's official SourceForge disk image."
}
variable "icon_path" {
  type    = string
  default = "icon.png"
}
# Metasploitable2 has no installer ISO - Rapid7 only ever distributed it as a
# pre-built VMware disk image. There is no proxmox-iso/proxmox-clone source that
# fits, so this template uses a "null" source and does the real work (download,
# extract, import into Proxmox via the API, provision, convert to template) in
# scripts/import.sh. See README.md before building. GUEST_DISK_BUS/NIC_MODEL are
# forced to ide/e1000 below because Metasploitable2 runs Linux 2.6.24, which
# predates virtio driver support - a virtio NIC/disk would be invisible to it.
variable "source_url" {
  type        = string
  default     = "https://sourceforge.net/projects/metasploitable/files/Metasploitable2/metasploitable-linux-2.0.0.zip/download"
  description = "Official Metasploitable2 download (SourceForge). Override with a local mirror if this ever moves."
}
variable "source_checksum" {
  type        = string
  default     = "sha256:2ae8788e95273eee87bd379a250d86ec52f286fa7fe84773a3a8f6524085a1ff"
  description = "REQUIRED: \"<algo>:<hex>\" digest of the downloaded source archive (what import.sh actually verifies, before extracting the disk it boots as the root disk). The import refuses to run without it. Default is the sha256 of Rapid7's official metasploitable-linux-2.0.0.zip (SourceForge), verified by download."
}
variable "source_archive_type" {
  type    = string
  default = "zip"
}
variable "source_disk_glob" {
  type    = string
  default = "*.vmdk"
}
variable "vm_cpu_cores" {
  type    = string
  default = "1"
}
variable "vm_memory" {
  type    = string
  default = "512"
}
variable "vm_name" {
  type    = string
  default = "metasploitable-2-x64-server-template"
}
variable "ssh_password" {
  type    = string
  default = "msfadmin"
}
variable "ssh_username" {
  type    = string
  default = "msfadmin"
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
# Proxmox API token — Ludus injects a token into packer's ENVIRONMENT (the
# proxmox-iso plugin logs "using token auth"); it leaves proxmox_username/password
# empty. `env()` is only valid in a variable default, so capture the token here and
# hand it to import.sh, which authenticates the same way the plugin does.
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
  template_description = "Metasploitable2 template imported ${legacy_isotime("2006-01-02 03:04:05")} username:password => msfadmin:msfadmin"
}
source "null" "metasploitable-2" {
  communicator = "none"
}
build {
  sources = ["source.null.metasploitable-2"]
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
      "LUDUS_NAT_INTERFACE=${var.ludus_nat_interface}",
      "VM_NAME=${var.vm_name}",
      "VM_MEMORY=${var.vm_memory}",
      "VM_CORES=${var.vm_cpu_cores}",
      "TEMPLATE_DESCRIPTION=${local.template_description}",
      "SOURCE_URL=${var.source_url}",
      "SOURCE_CHECKSUM=${var.source_checksum}",
      "SOURCE_ARCHIVE_TYPE=${var.source_archive_type}",
      "SOURCE_DISK_GLOB=${var.source_disk_glob}",
      "SSH_USERNAME=${var.ssh_username}",
      "SSH_PASSWORD=${var.ssh_password}",
      "GUEST_DISK_BUS=ide",
      "GUEST_NIC_MODEL=e1000",
      "GUEST_CPU_TYPE=kvm64",
      "ANSIBLE_HOME=${var.ansible_home}",
      "ANSIBLE_COLLECTIONS_PATH=${path.root}/collections",
      "ANSIBLE_REQUIREMENTS=${path.root}/requirements.yml",
      "ANSIBLE_PLAYBOOK=get_sybers.templates.provision",
    ]
    inline = ["bash \"${path.root}/scripts/import.sh\""]
  }
}
