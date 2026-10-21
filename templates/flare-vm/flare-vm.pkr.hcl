# Catalog metadata read by `ludus source add` when this template is browsed in the
# TUI/GUI picker. Packer requires a literal default, so this stays a static string.
variable "description" {
  type    = string
  default = "Windows malware-analysis workstation preloaded with FLARE VM tooling."
}
variable "icon_path" {
  type    = string
  default = "icon.png"
}
# Win10 22H2 Enterprise Eval (19045) — same ISO as win10-22h2-x64-enterprise-appxfix,
# already staged in the PVE ISO pool. FLARE-VM installs on Windows 10.
variable "iso_checksum" {
  type    = string
  default = "sha256:ef7312733a9f5d7d51cfa04ac497671995674ca5e1058d5164d6028f0938d668"
}
# https:
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
  default = "flare-vm-template"
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
  template_description = "Flare VM (Windows 10 22H2 64-bit Enterprise) template built ${legacy_isotime("2006-01-02 03:04:05")} username:password => localuser:password"
}
source "proxmox-iso" "flare-vm" {
  # Hit the "Press any key to boot from CD ROM"
  boot_wait = "-1s" # To set boot_wait to 0s, use a negative number, such as "-1s"
  boot_command = [  # 120 seconds of enters to cover all different speeds of disks as windows boots
    "<return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait>",
    "<return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait>",
    "<return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait>",
    "<return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait>",
    "<return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait>",
    "<return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait>",
    "<return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait>",
    "<return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait>",
    "<return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait>",
    "<return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait>",
    "<return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait>",
    "<return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait><return><wait>"
  ]
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
    iso_checksum     = "sha256:ebd48258668f7f78e026ed276c28a9d19d83e020ffa080ad69910dc86bbcbcc6"
    iso_url          = "https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/archive-virtio/virtio-win-0.1.240-1/virtio-win-0.1.240.iso"
    iso_storage_pool = "${var.iso_storage_pool}"
    unmount          = true
  }
  # UEFI (OVMF) boot — retained on the Win10 switch; Win10 boots UEFI fine and the
  # Autounattend here already lays down a GPT/EFI partition, so keep the firmware as-is.
  bios = "ovmf"
  efi_config {
    efi_storage_pool  = "${var.proxmox_storage_pool}"
    pre_enrolled_keys = true
    efi_type          = "4m"
  }
  # End UEFI boot option
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
  iso_checksum             = "${var.iso_checksum}"
  iso_url                  = "${var.iso_url}"
  # Repo rule 9 + let PVE fetch/verify the ISO into its own pool (dedup with the
  # already-staged win10 copy) instead of a slow client-side download that times
  # out — this is the fix for the 30-min "context deadline exceeded" build failure.
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
  winrm_timeout        = "60m"
  unmount_iso          = true
  task_timeout         = "20m"
}
build {
  sources = ["source.proxmox-iso.flare-vm"]
  # Disable Windows Update inline — no local .bat needed (extraction-safe).
  provisioner "powershell" {
    inline = [
      "Stop-Service -Name wuauserv -Force -ErrorAction SilentlyContinue",
      "Set-Service  -Name wuauserv -StartupType Disabled",
      "reg add 'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU' /v AUOptions /t REG_DWORD /d 2 /f | Out-Null",
      "reg add 'HKLM\\Software\\Policies\\Microsoft\\Windows\\WindowsUpdate' /v DisableWindowsUpdateAccess /t REG_DWORD /d 1 /f | Out-Null",
      "reg add 'HKLM\\Software\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU' /v NoAutoUpdate /t REG_DWORD /d 1 /f | Out-Null",
      "schtasks.exe /change /tn '\\Microsoft\\Windows\\UpdateOrchestrator\\USO_UxBroker_Display' /disable 2>$null; $true",
      "schtasks.exe /change /tn '\\Microsoft\\Windows\\UpdateOrchestrator\\MusUx_UpdateInterval' /disable 2>$null; $true",
      "schtasks.exe /change /tn '\\Microsoft\\Windows\\WindowsUpdate\\sih' /disable 2>$null; $true",
    ]
  }
  # Download W4RH4WK/Debloat-Windows-10 at pinned commit, run defender + telemetry scripts.
  # FLARE-VM requires Defender OFF; lib/ modules (New-FolderForced, take-own) must be present
  # so scripts cannot be iex'd inline — expand the archive and invoke from the tree.
  provisioner "powershell" {
    inline = [
      "$commit = '73c226b9818b9cdc9d0b165f9c4603bf78268fc5'",
      "$expectedHash = '2DDA8FE4F85E761BD34E75269AEB5A310C0C20C30AA8FB0CAC5E9E56EBF4B5EA'",
      "$zip  = \"$env:TEMP\\debloat.zip\"",
      "$dest = \"$env:TEMP\\debloat\"",
      "Remove-Item -LiteralPath $dest -Recurse -Force -ErrorAction SilentlyContinue",
      "Invoke-WebRequest -Uri \"https://github.com/W4RH4WK/Debloat-Windows-10/archive/$commit.zip\" -OutFile $zip -UseBasicParsing",
      "$actualHash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash",
      "if ($actualHash -ne $expectedHash) { throw \"Debloat-Windows-10 ZIP hash mismatch: expected $expectedHash got $actualHash\" }",
      "Expand-Archive -LiteralPath $zip -DestinationPath $dest -Force",
      "$root = Join-Path $dest \"Debloat-Windows-10-$commit\"",
      "& \"$root\\scripts\\disable-windows-defender.ps1\"",
      "& \"$root\\scripts\\block-telemetry.ps1\"",
    ]
  }
  provisioner "powershell" {
    scripts = ["scripts/disable-hibernate.ps1"]
  }
  provisioner "powershell" {
    scripts = ["scripts/install-virtio-drivers.ps1"]
  }
  provisioner "ansible" {
    playbook_file = "ansible/install-flare.yml"
    use_proxy     = false
    user          = "${var.winrm_username}"
    extra_arguments = [
      "-e", "ansible_winrm_server_cert_validation=ignore",
      "-e", "ansible_winrm_connection_timeout=300"
    ]
    ansible_env_vars   = ["ANSIBLE_HOME=${var.ansible_home}", "ANSIBLE_LOCAL_TEMP=${var.ansible_home}/tmp", "ANSIBLE_REMOTE_TEMP=${var.ansible_home}/remote_tmp", "ANSIBLE_PERSISTENT_CONTROL_PATH_DIR=${var.ansible_home}/pc", "ANSIBLE_SSH_CONTROL_PATH_DIR=${var.ansible_home}/cp"]
    skip_version_check = true # Due to https:
    timeout            = "4h"
  }
}
