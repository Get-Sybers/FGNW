# =============================================================================
# LudusPlusPlus — Debian 13 (Trixie) minimal x64 server template
#
# Adapted from the Bad Sector Labs Packer starter
# (https://github.com/badsectorlabs/ludus_packer_template, MIT) and the Ludus
# builtin debian13 template. Everything Ludus needs is here:
#
#   * the required Ludus variable block (set by the Ludus server at build time),
#   * a `description` (and optional `icon_path`) variable for the source catalog,
#   * a `vm_name` ending in `-template`, which is the name range configs use,
#   * credentials that match Ludus' Debian group_vars (debian:debian), so
#     `ludus range deploy` can reach VMs cloned from this template.
#
# Build it with: ludus templates build -n ludusplusplus-debian-13-x64-server-template
# =============================================================================

# --- Template knobs ----------------------------------------------------------

variable "vm_name" {
  type    = string
  default = "ludusplusplus-debian-13-x64-server-template" # keep the -template suffix; prefix with the source slug to stay unique across sources
}

variable "description" {
  type    = string
  default = "Debian 13 (Trixie) minimal x64 server — LudusPlusPlus base image."
}

variable "icon_path" {
  type    = string
  default = "icon.png"
}

variable "iso_url" {
  type    = string
  default = "https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-13.7.0-amd64-netinst.iso"
}

variable "iso_checksum" {
  type    = string
  default = "sha512:ef04d0276850d70e4aaec0b55003628660e9631b26e35215a70ab3c8c707294a4b12731bc73c75a932902f703a7c278310ca99df28d6b36fb06d5618d8d0f678"
}

variable "vm_cpu_cores" {
  type    = string
  default = "2"
}

variable "vm_disk_size" {
  type    = string
  default = "60G"
}

variable "vm_memory" {
  type    = string
  default = "4096"
}

# Credentials created by http/preseed.cfg. Ludus connects to Debian guests as
# debian:debian (ludus-server/ansible/range-management/group_vars/debian.yml),
# so change these only together with the preseed AND a deliberate reason.
variable "ssh_username" {
  type    = string
  default = "debian"
}

variable "ssh_password" {
  type    = string
  default = "debian"
}

# Proxmox guest OS type. Ludus reads this literal to classify the template
# (l24/l26 = Linux, win*/w2k* = Windows). Use win10/win11 etc. for Windows.
variable "os" {
  type    = string
  default = "l26"
}

# --- Required Ludus block — do not remove or give defaults -------------------
# The Ludus server passes these with `packer build -var ...` (or, for the
# username/password pair, as empty PKR_VAR_ environment variables so the
# Proxmox plugin falls back to the building user's API token). Packer refuses
# a -var that is not declared, so every template must declare all of them.
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
  template_description = "${var.description} Built ${legacy_isotime("2006-01-02 03:04:05")}. username:password => ${var.ssh_username}:${var.ssh_password}"
}

source "proxmox-iso" "ludusplusplus-debian-13" {
  # Boots the Debian installer and points it at http/preseed.cfg for a fully
  # automated install.
  boot_command = [
    "<down><tab>", # non-graphical install
    "preseed/url=http://{{ .HTTPIP }}:{{ .HTTPPort }}/preseed.cfg ",
    "language=en locale=en_US.UTF-8 ",
    "country=US keymap=us ",
    "hostname=debian13 domain=local ",
    "<enter><wait>",
  ]
  boot_key_interval = "100ms"
  http_directory    = "./http"

  boot_iso {
    type              = "ide"
    iso_checksum      = "${var.iso_checksum}"
    iso_url           = "${var.iso_url}"
    iso_storage_pool  = "${var.iso_storage_pool}"
    iso_download_pve  = true
    unmount           = true
    keep_cdrom_device = false
  }

  communicator = "ssh"
  cores        = "${var.vm_cpu_cores}"
  cpu_type     = "host" # pass through the host CPU for maximum performance

  # virtio-scsi-single + io_thread + discard is the Ludus-recommended disk
  # setup for Proxmox guests (see docs/templates/ludus-packer.md).
  scsi_controller = "virtio-scsi-single"
  disks {
    disk_size    = "${var.vm_disk_size}"
    format       = "${var.proxmox_storage_format}"
    storage_pool = "${var.proxmox_storage_pool}"
    type         = "virtio"
    discard      = true
    io_thread    = true
  }

  # virtio is paravirtualized and much faster than the emulated e1000.
  network_adapters {
    bridge = "${var.ludus_nat_interface}"
    model  = "virtio"
  }

  pool                     = "${var.proxmox_pool}"
  insecure_skip_tls_verify = "${var.proxmox_skip_tls_verify}"
  memory                   = "${var.vm_memory}"
  node                     = "${var.proxmox_host}"
  os                       = "${var.os}"
  password                 = "${var.proxmox_password}"
  proxmox_url              = "${var.proxmox_url}"
  template_description     = "${local.template_description}"
  username                 = "${var.proxmox_username}"
  vm_name                  = "${var.vm_name}"
  ssh_password             = "${var.ssh_password}"
  ssh_username             = "${var.ssh_username}"
  ssh_wait_timeout         = "30m"
  task_timeout             = "20m" // On slow disks the imgcopy operation takes > 1m
}

build {
  sources = ["source.proxmox-iso.ludusplusplus-debian-13"]

  # Runs once at template build time — everything it installs is baked into
  # the image and inherited by every VM cloned from it.
  provisioner "ansible" {
    playbook_file      = "ansible/customize.yml"
    use_proxy          = false
    user               = "${var.ssh_username}"
    extra_arguments    = ["--extra-vars", "{ansible_python_interpreter: /usr/bin/python3, ansible_password: ${var.ssh_password}, ansible_sudo_pass: ${var.ssh_password}}"]
    ansible_env_vars   = ["ANSIBLE_HOME=${var.ansible_home}", "ANSIBLE_LOCAL_TEMP=${var.ansible_home}/tmp", "ANSIBLE_PERSISTENT_CONTROL_PATH_DIR=${var.ansible_home}/pc", "ANSIBLE_SSH_CONTROL_PATH_DIR=${var.ansible_home}/cp"]
    skip_version_check = true
  }
}
