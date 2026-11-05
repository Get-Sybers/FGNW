variable "description" {
  type    = string
  default = "Ninjasploitable — a Naruto-themed Metasploitable2 (Debian 12) vulnerable target with vulnerable-service packages, realmd/sssd AD-join packages, and the themed vulnerable web content baked in at build time (including /reports/intake.php). Derived from the community (ludus-source-bsl) Debian template. See #365, #459, #461."
}
variable "icon_path" {
  type    = string
  default = "icon.png"
}
variable "iso_checksum" {
  type    = string
  default = "sha256:9f181ae12b25840a508786b1756c6352a0e58484998669288c4eec2ab16b8559"
}
# The operating system. Can be wxp, w2k, w2k3, w2k8, wvista, win7, win8, win10, l24 (Linux 2.4), l26 (Linux 2.6+), solaris or other. Defaults to other.
variable "os" {
  type    = string
  default = "l26"
}
variable "iso_url" {
  type    = string
  default = "https://cdimage.debian.org/cdimage/archive/12.1.0/amd64/iso-cd/debian-12.1.0-amd64-netinst.iso"
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
variable "vm_name" {
  type    = string
  default = "ninjasploitable-x64-server-template"
}
variable "ssh_password" {
  type    = string
  default = "debian"
}
variable "ssh_username" {
  type    = string
  default = "debian"
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
  template_description = "Ninjasploitable (Debian 12, Naruto-themed) — packages + vulnerable web content baked (#365, #461) built ${legacy_isotime("2006-01-02 03:04:05")} username:password => debian:debian"
}
source "proxmox-iso" "ninjasploitable-x64-server" {
  boot_command = [
    "<down><tab>", # non-graphical install
    "preseed/url=http://{{ .HTTPIP }}:{{ .HTTPPort }}/debian-12-preseed.cfg ",
    "language=en locale=en_US.UTF-8 ",
    "country=US keymap=us ",
    "hostname=metasploitable2 domain=local ",
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
  communicator    = "ssh"
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
  password             = "${var.proxmox_password}"
  proxmox_url          = "${var.proxmox_url}"
  template_description = "${local.template_description}"
  username             = "${var.proxmox_username}"
  vm_name              = "${var.vm_name}"
  ssh_password         = "${var.ssh_password}"
  ssh_username         = "${var.ssh_username}"
  ssh_wait_timeout     = "30m"
  task_timeout         = "20m"
}
build {
  sources = ["source.proxmox-iso.ninjasploitable-x64-server"]

  # #365 + #461 — bake the ninjasploitable vulnerable-service + realmd/sssd AD-join
  # packages AND the themed vulnerable web content (incl. /reports/intake.php and the
  # intentionally-vulnerable MariaDB) so a fresh clone already serves /vulnerable with
  # no deploy step. The play self-gates on /var/lib/ludus/ninjasploitable_content_baked
  # (written last), so a rebuild over a good bake is a no-op. community.general
  # (apache2_module) and ansible.mysql (mysql_user/mysql_db) install from
  # requirements.yml first.
  #
  # Not via the ansible provisioner's `galaxy_file`: the plugin runs ansible-galaxy
  # with packer's own environment, not `ansible_env_vars`, so on a Ludus server
  # (the service runs with ProtectHome=read-only) it dies creating ~/.ansible/tmp.
  # Installed here with ANSIBLE_HOME under ansible_home instead; the collections land
  # in the first entry of the ANSIBLE_COLLECTIONS_PATH Ludus exports (the user's
  # collections), where the ansible provisioner below finds them without an override.
  provisioner "shell-local" {
    environment_vars = [
      "ANSIBLE_HOME=${var.ansible_home}",
      "ANSIBLE_LOCAL_TEMP=${var.ansible_home}/tmp",
    ]
    inline = ["ansible-galaxy collection install -r \"${path.root}/requirements.yml\""]
  }
  provisioner "ansible" {
    playbook_file = "ansible/ninjasploitable-bake.yml"
    use_proxy     = false
    user          = "${var.ssh_username}"
    extra_arguments = [
      "--extra-vars", "ansible_password=${var.ssh_password} ansible_become_pass=${var.ssh_password}",
    ]
    ansible_env_vars = [
      "ANSIBLE_HOME=${var.ansible_home}",
      "ANSIBLE_LOCAL_TEMP=${var.ansible_home}/tmp",
      "ANSIBLE_PERSISTENT_CONTROL_PATH_DIR=${var.ansible_home}/pc",
      "ANSIBLE_SSH_CONTROL_PATH_DIR=${var.ansible_home}/cp",
      "ANSIBLE_HOST_KEY_CHECKING=False",
    ]
    skip_version_check = true
  }

  # Stock BSL Debian behaviour: install a first-boot oneshot that regenerates unique
  # SSH host keys on each clone and then disables itself. Kept last.
  provisioner "ansible" {
    playbook_file = "ansible/reset-ssh-host-keys.yml"
    use_proxy     = false
    user          = "${var.ssh_username}"
    extra_arguments = [
      "--extra-vars", "ansible_password=${var.ssh_password} ansible_become_pass=${var.ssh_password}",
    ]
    ansible_env_vars = [
      "ANSIBLE_HOME=${var.ansible_home}",
      "ANSIBLE_LOCAL_TEMP=${var.ansible_home}/tmp",
      "ANSIBLE_PERSISTENT_CONTROL_PATH_DIR=${var.ansible_home}/pc",
      "ANSIBLE_SSH_CONTROL_PATH_DIR=${var.ansible_home}/cp",
    ]
    skip_version_check = true
  }
}
