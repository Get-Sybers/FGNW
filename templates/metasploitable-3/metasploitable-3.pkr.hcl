# Catalog metadata read by `ludus source add` when this template is browsed in the
# TUI/GUI picker. Packer requires a literal default, so this stays a static string.
variable "description" {
  type    = string
  default = "Metasploitable3 (Ubuntu 14.04) vulnerable target, imported from Rapid7's published Vagrant Cloud box."
}
variable "icon_path" {
  type    = string
  default = "icon.png"
}
# Metasploitable3 has no installer ISO either - Rapid7's own build process
# (Vagrant + Packer + Chef, see github.com/rapid7/metasploitable3) produces a
# Vagrant box, not something a proxmox-iso/-clone builder can consume directly.
# Re-running that whole Vagrant/Packer/Chef pipeline nested inside this Proxmox
# host would need its own hypervisor (VirtualBox/VMware) for Vagrant to drive,
# which isn't set up here - so instead this template takes Rapid7's own published
# build output (their Vagrant Cloud box, which *is* the artifact that pipeline
# produces) and imports it the same way metasploitable-2 imports its vmdk.
# This is the Ubuntu 14.04 flavor (`metasploitable3-ub1404`); Rapid7 also
# publishes a Windows Server 2008 flavor under the same account if that's wanted
# later - it would need its own template following this same pattern.
variable "source_url" {
  type        = string
  default     = "https://vagrantcloud.com/rapid7/boxes/metasploitable3-ub1404/versions/0.1.12-weekly/providers/virtualbox/unknown/vagrant.box"
  description = "Rapid7's published metasploitable3-ub1404 Vagrant box (virtualbox provider). Confirm this is still the current version at https://app.vagrantup.com/rapid7/boxes/metasploitable3-ub1404 before relying on the default."
}
variable "source_checksum" {
  type        = string
  default     = "sha256:2a3e1708e4ff25ebf43be31ed243aea56d73503f1b63f9f34a9b80482f18e4c3"
  description = "REQUIRED: \"<algo>:<hex>\" digest of the downloaded source archive (what import.sh actually verifies, before extracting the disk it boots as the root disk). The import refuses to run without it. Default is the sha256 of Rapid7's metasploitable3-ub1404 0.1.12-weekly virtualbox vagrant.box (Vagrant Cloud publishes no checksum), verified by download."
}
variable "source_archive_type" {
  type    = string
  default = "vagrant-box"
}
variable "source_disk_glob" {
  type    = string
  default = "*.vmdk"
}
variable "vm_cpu_cores" {
  type    = string
  default = "2"
}
variable "vm_memory" {
  type    = string
  default = "2048"
}
variable "vm_name" {
  type    = string
  default = "metasploitable-3-ub1404-x64-server-template"
}
variable "ssh_password" {
  type    = string
  default = "vagrant"
}
variable "ssh_username" {
  type    = string
  default = "vagrant"
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
  template_description = "Metasploitable3 (ub1404) template imported ${legacy_isotime("2006-01-02 03:04:05")} username:password => vagrant:vagrant"
}
source "null" "metasploitable-3" {
  communicator = "none"
}
build {
  sources = ["source.null.metasploitable-3"]
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
      "ANSIBLE_HOME=${var.ansible_home}",
      "ANSIBLE_COLLECTIONS_PATH=${path.root}/collections",
      "ANSIBLE_REQUIREMENTS=${path.root}/requirements.yml",
      "ANSIBLE_PLAYBOOK=get_sybers.templates.provision",
    ]
    inline = ["bash \"${path.root}/scripts/import.sh\""]
  }
}
