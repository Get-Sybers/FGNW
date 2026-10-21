variable "description" {
  type    = string
  default = "Windows 10 22H2 Enterprise (x64) with ALL AppX sysprep blockers removed at build time (#101). Use this name, not the stock win10-22h2-x64-enterprise-template, for workstation VMs that sysprep."
}
variable "icon_path" {
  type    = string
  default = "icon.png"
}
variable "iso_checksum" {
  type    = string
  default = "sha256:ef7312733a9f5d7d51cfa04ac497671995674ca5e1058d5164d6028f0938d668"
}
variable "os" {
  type    = string
  default = "win10"
}
variable "iso_url" {
  type    = string
  default = "https://software-static.download.prss.microsoft.com/dbazure/988969d5-f34g-4e03-ac9d-1f9786c66750/19045.2006.220908-0225.22h2_release_svc_refresh_CLIENTENTERPRISEEVAL_OEMRET_x64FRE_en-us.iso"
}
variable "vm_cpu_cores" {
  type    = string
  default = "2"
}
variable "vm_disk_size" {
  type    = string
  default = "250G"
}
variable "vm_memory" {
  type    = string
  default = "4096"
}
variable "vm_name" {
  type    = string
  default = "win10-22h2-x64-enterprise-appxfix-template"
}
variable "winrm_password" {
  type    = string
  default = "password"
}
variable "winrm_username" {
  type    = string
  default = "localuser"
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
  template_description = "Windows 10 22H2 Enterprise 64-bit template built ${legacy_isotime("2006-01-02 03:04:05")} username:password => localuser:password"
}
source "proxmox-iso" "win10-22h2-x64-enterprise" {
  additional_iso_files {
    device           = "sata3"
    iso_storage_pool = "${var.iso_storage_pool}"
    unmount          = true
    cd_label         = "PROVISION"
    cd_files = [
      "iso/setup-for-ansible.ps1",
      "iso/win-updates.ps1",
      "iso/windows-common-setup.ps1",
      "Autounattend.xml",
    ]
  }
  additional_iso_files {
    device           = "sata4"
    iso_checksum     = "sha256:c88a0dde34605eaee6cf889f3e2a0c2af3caeb91b5df45a125ca4f701acbbbe0"
    iso_url          = "https://virtio-win.ludus.cloud/archive-virtio/virtio-win-0.1.229-1/virtio-win-0.1.229.iso"
    iso_storage_pool = "${var.iso_storage_pool}"
    unmount          = true
  }
  communicator    = "winrm"
  cores           = "${var.vm_cpu_cores}"
  cpu_type        = "host"
  scsi_controller = "virtio-scsi-single"
  disks {
    disk_size         = "${var.vm_disk_size}"
    format            = "${var.proxmox_storage_format}"
    storage_pool      = "${var.proxmox_storage_pool}"
    type              = "virtio"
    discard           = true
    io_thread         = true
  }
  pool                     = "${var.proxmox_pool}"
  insecure_skip_tls_verify = "${var.proxmox_skip_tls_verify}"
  iso_checksum             = "${var.iso_checksum}"
  iso_url                  = "${var.iso_url}"
  # Repo rule 9: keep iso_url + iso_checksum (NEVER swap to iso_file, which
  # discards verification) and let Proxmox verify the copy it already holds and
  # skip the 5.5 GB transfer. The upstream BSL template omits this; the Ludus
  # stock templates set it. This is a supported packer option, not a rewrite.
  iso_download_pve         = true
  iso_storage_pool         = "${var.iso_storage_pool}"
  memory                   = "${var.vm_memory}"
  network_adapters {
    bridge = "${var.ludus_nat_interface}"
    model  = "virtio"
  }
  node                 = "${var.proxmox_host}"
  os                   = "${var.os}"
  password             = "${var.proxmox_password}"
  proxmox_url          = "${var.proxmox_url}"
  template_description = "${local.template_description}"
  username             = "${var.proxmox_username}"
  vm_name              = "${var.vm_name}"
  winrm_insecure       = true
  winrm_password       = "${var.winrm_password}"
  winrm_use_ssl        = true
  winrm_username       = "${var.winrm_username}"
  unmount_iso          = true
  winrm_timeout        = "6h"
  task_timeout         = "20m"
}
build {
  sources = ["source.proxmox-iso.win10-22h2-x64-enterprise"]
  provisioner "windows-shell" {
    scripts = ["scripts/disablewinupdate.bat"]
  }
  provisioner "powershell" {
    scripts = ["scripts/disable-hibernate.ps1"]
  }
  provisioner "powershell" {
    scripts = ["scripts/install-virtio-drivers.ps1"]
  }
  # #101 — the whole point of this derivative template.
  # Sysprep runs at range-deploy time and its cleanup providers hard-fail when
  # an AppX package is "installed for a user, but not provisioned for all
  # users". On a DESKTOP image any of the dozens of provisioned Store apps can
  # be in that state, so this script matches the condition rather than a package
  # name and fails the build if any blocker survives. See the README.
  # Ordering matters: this must stay the FINAL provisioner — nothing after it
  # may install or update a Store app before capture. (This build never runs
  # Windows Update: disablewinupdate.bat above disables it.)
  provisioner "powershell" {
    scripts = ["scripts/remove-appx-sysprep-blockers.ps1"]
  }
}
