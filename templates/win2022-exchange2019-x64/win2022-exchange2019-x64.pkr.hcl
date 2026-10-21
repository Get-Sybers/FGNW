# Catalog metadata read by `ludus source add` when this template is browsed in the
# TUI/GUI picker. Packer requires a literal default, so this stays a static string.
variable "description" {
  type    = string
  default = "Windows Server 2022 + Exchange 2019 CU15 prerequisites and media baked in at build (derived from win2022-server-x64-appxfix; Edge AppX sysprep blocker removed, #101). Only the AD-bound Exchange install runs at deploy (#325). Use for the FGNW *-owa hosts."
}
variable "icon_path" {
  type    = string
  default = "icon.png"
}
variable "iso_checksum" {
  type    = string
  default = "sha256:3e4fa6d8507b554856fc9ca6079cc402df11a8b79344871669f0251535255325"
}
variable "os" {
  type    = string
  default = "win11"
}
variable "iso_url" {
  type    = string
  default = "https://software-static.download.prss.microsoft.com/sg/download/888969d5-f34g-4e03-ac9d-1f9786c66749/SERVER_EVAL_x64FRE_en-us.iso"
}
variable "vm_cpu_cores" {
  type    = string
  default = "4"
}
variable "vm_disk_size" {
  type    = string
  default = "250G"
}
variable "vm_memory" {
  type    = string
  default = "8192"
}
variable "vm_name" {
  type    = string
  default = "win2022-exchange2019-x64-template"
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
# Derivative of win2022-server-x64-appxfix (itself a local derivative of the stock
# packer/win2022-server-x64 template). Self-contained per the templates/ convention:
# the shared iso/, scripts/ and ansible/ files are vendored so `ludus templates add -d`
# works on this directory alone. Two functional changes over stock:
#   1. exchange-bake.yml — bakes the Exchange 2019 CU15 prerequisites + media (#325);
#   2. remove-appx-sysprep-blockers.ps1 — the sysprep-blocker removal, kept LAST (#101/#514).
locals {
  template_description = "Windows Server 2022 + Exchange 2019 CU15 prereqs/media baked (derived from win2022-server-x64-appxfix, ALL AppX blockers removed + EdgeUpdate disabled #101/#514; only the AD-bound install runs at deploy, #325) built ${legacy_isotime("2006-01-02 03:04:05")} username:password => localuser:password"
}
source "proxmox-iso" "win2022-exchange2019-x64" {
  additional_iso_files {
    type             = "sata"
    index            = "3"
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
    type             = "sata"
    index            = "4"
    iso_checksum     = "sha256:c88a0dde34605eaee6cf889f3e2a0c2af3caeb91b5df45a125ca4f701acbbbe0"
    iso_url          = "https://virtio-win.ludus.cloud/archive-virtio/virtio-win-0.1.229-1/virtio-win-0.1.229.iso"
    iso_storage_pool = "${var.iso_storage_pool}"
    unmount          = true
    iso_download_pve = true
  }
  boot_iso {
    type              = "ide"
    iso_checksum      = "${var.iso_checksum}"
    iso_url           = "${var.iso_url}"
    iso_storage_pool  = "${var.iso_storage_pool}"
    iso_download_pve  = true
    unmount           = true
    keep_cdrom_device = true
  }
  communicator    = "winrm"
  cores           = "${var.vm_cpu_cores}"
  cpu_type        = "host"
  scsi_controller = "virtio-scsi-single"
  disks {
    disk_size    = "${var.vm_disk_size}"
    format       = "${var.proxmox_storage_format}"
    storage_pool = "${var.proxmox_storage_pool}"
    type         = "virtio"
    discard      = true
    io_thread    = true
  }
  pool                     = "${var.proxmox_pool}"
  insecure_skip_tls_verify = "${var.proxmox_skip_tls_verify}"
  memory                   = "${var.vm_memory}"
  network_adapters {
    bridge = "${var.ludus_nat_interface}"
    model  = "virtio"
  }
  node                 = "${var.proxmox_host}"
  os                   = "${var.os}"
  proxmox_url          = "${var.proxmox_url}"
  template_description = "${local.template_description}"
  vm_name              = "${var.vm_name}"
  winrm_insecure       = true
  winrm_password       = "${var.winrm_password}"
  winrm_use_ssl        = true
  winrm_username       = "${var.winrm_username}"
  winrm_timeout        = "6h"
  task_timeout         = "20m"
}
build {
  sources = ["source.proxmox-iso.win2022-exchange2019-x64"]
  provisioner "windows-shell" {
    scripts = ["scripts/disablewinupdate.bat"]
  }
  provisioner "powershell" {
    scripts = ["scripts/disable-hibernate.ps1"]
  }
  provisioner "powershell" {
    scripts = ["scripts/install-virtio-drivers.ps1"]
  }
  provisioner "powershell" {
    scripts = ["scripts/optimize-assemblies.ps1"]
  }
  provisioner "ansible" {
    playbook_file = "ansible/ngen.yml"
    galaxy_file   = "requirements.yml"
    use_proxy     = false
    user          = "${var.winrm_username}"
    extra_arguments = [
      "-e", "ansible_winrm_server_cert_validation=ignore",
      "-e", "ansible_winrm_connection_timeout=300"
    ]
    ansible_env_vars   = ["ANSIBLE_HOME=${var.ansible_home}"]
    skip_version_check = true
  }
  # #325 — bake the Exchange 2019 CU15 prerequisites (Windows features, .NET 4.8,
  # VC++ 2013, URL Rewrite, UCMA 4.0) and the CU15 media into the image. Runs after
  # ngen and BEFORE the Edge-AppX removal so the AppX step stays the final provisioner.
  # Domain-independent only; the AD-bound install (/PrepareSchema, /PrepareAD,
  # /Mode:Install, mailboxes) stays at range-deploy. Idempotent via a marker file the
  # deploy-time aleemladha.ludus_exchange role also honours (see ansible/exchange-bake.yml).
  provisioner "ansible" {
    playbook_file = "ansible/exchange-bake.yml"
    use_proxy     = false
    user          = "${var.winrm_username}"
    extra_arguments = [
      "-e", "ansible_winrm_server_cert_validation=ignore",
      "-e", "ansible_winrm_connection_timeout=300"
    ]
    ansible_env_vars   = ["ANSIBLE_HOME=${var.ansible_home}"]
    skip_version_check = true
  }
  # #101/#514 — the whole point of this derivative template.
  # Sysprep runs at range-deploy time (ansible/range-management, `Sysprep
  # Windows VMs` play) and its cleanup providers hard-fail when an AppX
  # package is "installed for a user, but not provisioned for all users".
  # This script (a) removes ALL packages meeting that condition (not just
  # Edge), and (b) disables the EdgeUpdate service pair so the updater
  # cannot re-register a per-user Edge AppX between clone and sysprep.
  # Ordering matters: this must stay the final provisioner — nothing after
  # it may install or update a Store app or re-enable EdgeUpdate before
  # capture. (This build never runs Windows Update: disablewinupdate.bat
  # above disables it.)
  provisioner "powershell" {
    scripts = ["scripts/remove-appx-sysprep-blockers.ps1"]
  }
}
