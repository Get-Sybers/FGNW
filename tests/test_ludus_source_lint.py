"""Self-tests for scripts/ludus_source_lint.py against mutated copies of this source."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from conftest import REPO, edit

TEMPLATE = Path("templates/ludusplusplus-debian-13/ludusplusplus-debian-13.pkr.hcl")
RANGE = Path("blueprints/example/range-config.yml")
BLUEPRINT = Path("blueprints/example/blueprint.yml")

WINDOWS_TEMPLATE = textwrap.dedent(
    '''
    variable "description" {
      type    = string
      default = "Windows test template."
    }
    variable "os" {
      type    = string
      default = "win11"
    }
    variable "vm_name" {
      type    = string
      default = "ludusplusplus-win-test-template"
    }
    variable "winrm_username" {
      type    = string
      default = "localuser"
    }
    variable "winrm_password" {
      type    = string
      default = "password"
    }
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

    source "proxmox-iso" "win" {
      boot_iso {
        type             = "ide"
        iso_url          = "https://example.invalid/win.iso"
        iso_checksum     = "none"
        iso_storage_pool = "${var.iso_storage_pool}"
        unmount          = true
      }
      communicator             = "winrm"
      cpu_type                 = "host"
      scsi_controller          = "virtio-scsi-single"
      disks {
        disk_size    = "60G"
        format       = "${var.proxmox_storage_format}"
        storage_pool = "${var.proxmox_storage_pool}"
        type         = "virtio"
        discard      = true
        io_thread    = true
      }
      network_adapters {
        bridge = "${var.ludus_nat_interface}"
        model  = "virtio"
      }
      pool                     = "${var.proxmox_pool}"
      insecure_skip_tls_verify = "${var.proxmox_skip_tls_verify}"
      node                     = "${var.proxmox_host}"
      os                       = "${var.os}"
      password                 = "${var.proxmox_password}"
      proxmox_url              = "${var.proxmox_url}"
      username                 = "${var.proxmox_username}"
      vm_name                  = "${var.vm_name}"
      winrm_insecure           = true
      winrm_password           = "${var.winrm_password}"
      winrm_use_ssl            = true
      winrm_username           = "${var.winrm_username}"
    }

    build {
      sources = ["source.proxmox-iso.win"]
    }
    '''
)


def add_windows_template(root: Path, with_autounattend: bool = True) -> Path:
    tdir = root / "templates" / "win-test"
    tdir.mkdir()
    (tdir / "win-test.pkr.hcl").write_text(WINDOWS_TEMPLATE, encoding="utf-8")
    if with_autounattend:
        (tdir / "Autounattend.xml").write_text("<unattend/>", encoding="utf-8")
    return tdir


# --- baseline -----------------------------------------------------------------


def test_fixture_source_is_clean(lint, source):
    # The golden fixture the mutation tests start from must itself lint clean.
    findings, _ = lint(source)
    assert not [f for f in findings if f.level in ("error", "warning")], [f.as_text() for f in findings]


def test_fgnw_source_is_clean(lint):
    # FGNW's real template library and blueprint must lint clean too (the same
    # check the CI `ludus-source` job runs over the repository root).
    findings, _ = lint(REPO)
    assert not [f for f in findings if f.level in ("error", "warning")], [f.as_text() for f in findings]


def test_rule_catalogue_levels_are_valid(lint_module):
    for rule, (level, text) in lint_module.RULES.items():
        assert level in ("error", "warning", "info"), rule
        assert text


# --- templates ----------------------------------------------------------------


def test_missing_ludus_variable_is_an_error(lint, source):
    edit(source / TEMPLATE, 'variable "proxmox_storage_pool" {\n  type = string\n}\n', "")
    _, by_rule = lint(source)
    assert any("proxmox_storage_pool" in f.message and f.level == "error" for f in by_rule.get("T004", []))


def test_ludus_variable_with_default_is_an_error(lint, source):
    edit(source / TEMPLATE, 'variable "proxmox_pool" {\n  type = string\n}', 'variable "proxmox_pool" {\n  type    = string\n  default = "SHARED"\n}')
    _, by_rule = lint(source)
    assert any("proxmox_pool" in f.message and "default" in f.message for f in by_rule.get("T004", []))


def test_wrong_variable_type_is_an_error(lint, source):
    edit(source / TEMPLATE, 'variable "proxmox_skip_tls_verify" {\n  type = bool\n}', 'variable "proxmox_skip_tls_verify" {\n  type = string\n}')
    _, by_rule = lint(source)
    assert any("proxmox_skip_tls_verify" in f.message and "type = bool" in f.message for f in by_rule.get("T004", []))


def test_made_up_variable_without_default_is_an_error(lint, source):
    edit(source / TEMPLATE, 'variable "vm_memory" {', 'variable "made_up" {\n  type = string\n}\n\nvariable "vm_memory" {')
    _, by_rule = lint(source)
    assert any("made_up" in f.message for f in by_rule.get("T005", []))


def test_hardcoded_storage_pool_is_an_error(lint, source):
    edit(source / TEMPLATE, 'storage_pool = "${var.proxmox_storage_pool}"', 'storage_pool = "local-zfs"')
    _, by_rule = lint(source)
    assert any("disks[0].storage_pool" in f.message for f in by_rule.get("T008", []))


def test_wrong_variable_binding_is_an_error(lint, source):
    edit(source / TEMPLATE, 'bridge = "${var.ludus_nat_interface}"', 'bridge = "${var.proxmox_host}"')
    _, by_rule = lint(source)
    assert any("network_adapters[0].bridge" in f.message for f in by_rule.get("T008", []))


def test_missing_required_binding_is_an_error(lint, source):
    edit(source / TEMPLATE, '  pool                     = "${var.proxmox_pool}"\n', "")
    _, by_rule = lint(source)
    assert any("pool is not set" in f.message for f in by_rule.get("T008", []))


def test_literal_api_credentials_are_an_error(lint, source):
    edit(source / TEMPLATE, 'password                 = "${var.proxmox_password}"', 'password                 = "hunter2"')
    _, by_rule = lint(source)
    assert any("password" in f.message and "literal" in f.message for f in by_rule.get("T009", []))


def test_vm_id_is_an_error(lint, source):
    edit(source / TEMPLATE, '  vm_name                  = "${var.vm_name}"\n', '  vm_name                  = "${var.vm_name}"\n  vm_id                    = 9001\n')
    _, by_rule = lint(source)
    assert any("vm_id" in f.message for f in by_rule.get("T009", []))


def test_template_name_must_end_with_template_suffix(lint, source):
    edit(source / TEMPLATE, 'default = "ludusplusplus-debian-13-x64-server-template"', 'default = "ludusplusplus-debian-13"')
    _, by_rule = lint(source)
    assert any("-template" in f.message for f in by_rule.get("T003", []))


def test_builtin_template_name_collision_is_an_error(lint, source):
    edit(source / TEMPLATE, 'default = "ludusplusplus-debian-13-x64-server-template"', 'default = "debian-13-x64-server-template"')
    _, by_rule = lint(source)
    assert any("builtin" in f.message and f.level == "error" for f in by_rule.get("T003", []))


def test_bsl_template_name_collision_is_a_warning(lint, source):
    edit(source / TEMPLATE, 'default = "ludusplusplus-debian-13-x64-server-template"', 'default = "debian-11-x64-server-template"')
    _, by_rule = lint(source)
    assert any("Bad Sector Labs" in f.message and f.level == "warning" for f in by_rule.get("T003", []))


def test_vm_name_resolves_through_locals_like_ludus(lint, source):
    edit(source / TEMPLATE, 'locals {\n  template_description', 'locals {\n  name_prefix = "${var.vm_name}"\n  template_description')
    edit(source / TEMPLATE, 'vm_name                  = "${var.vm_name}"', 'vm_name                  = "${local.name_prefix}"')
    _, by_rule = lint(source)
    assert "T003" not in by_rule


def test_missing_ansible_home_is_an_error(lint, source):
    edit(source / TEMPLATE, '"ANSIBLE_HOME=${var.ansible_home}", ', "")
    _, by_rule = lint(source)
    assert any("ANSIBLE_HOME" in f.message for f in by_rule.get("T011", []))


def test_skip_version_check_false_is_an_error(lint, source):
    edit(source / TEMPLATE, "skip_version_check = true", "skip_version_check = false")
    _, by_rule = lint(source)
    assert any("skip_version_check" in f.message for f in by_rule.get("T011", []))


def test_missing_playbook_is_an_error(lint, source):
    edit(source / TEMPLATE, 'playbook_file      = "ansible/customize.yml"', 'playbook_file      = "ansible/nope.yml"')
    _, by_rule = lint(source)
    assert any("does not exist" in f.message for f in by_rule.get("T012", []))


def test_path_escaping_template_dir_is_an_error(lint, source):
    edit(source / TEMPLATE, 'playbook_file      = "ansible/customize.yml"', 'playbook_file      = "../shared/customize.yml"')
    _, by_rule = lint(source)
    assert any("escapes" in f.message for f in by_rule.get("T012", []))


def test_missing_os_variable_is_an_error(lint, source):
    edit(source / TEMPLATE, 'variable "os" {\n  type    = string\n  default = "l26"\n}', "")
    edit(source / TEMPLATE, '  os                       = "${var.os}"\n', "")
    _, by_rule = lint(source)
    assert any('variable "os"' in f.message for f in by_rule.get("T010", []))


def test_windows_template_needs_autounattend(lint, source):
    add_windows_template(source, with_autounattend=False)
    _, by_rule = lint(source)
    assert any("Autounattend.xml" in f.message for f in by_rule.get("T013", []))


def test_windows_template_with_autounattend_is_clean(lint, source):
    add_windows_template(source, with_autounattend=True)
    findings, by_rule = lint(source)
    assert not [f for f in findings if f.level == "error"], [f.as_text() for f in findings]


def test_windows_credentials_mismatch_is_a_warning(lint, source):
    tdir = add_windows_template(source)
    edit(tdir / "win-test.pkr.hcl", 'default = "localuser"', 'default = "Administrator"')
    _, by_rule = lint(source)
    assert any("Administrator" in f.message and "windows" in f.message for f in by_rule.get("T014", []))


def test_debian_credentials_mismatch_is_a_warning(lint, source):
    edit(source / TEMPLATE, 'variable "ssh_username" {\n  type    = string\n  default = "debian"', 'variable "ssh_username" {\n  type    = string\n  default = "localuser"')
    _, by_rule = lint(source)
    assert any("debian:debian" in f.message for f in by_rule.get("T014", []))


def test_two_packer_files_is_an_error(lint, source):
    (source / TEMPLATE.parent / "extra.pkr.hcl").write_text("", encoding="utf-8")
    _, by_rule = lint(source)
    assert any("more than one" in f.message for f in by_rule.get("T001", []))


def test_required_plugins_from_hashicorp_is_an_error(lint, source):
    edit(source / TEMPLATE, "locals {", 'packer {\n  required_plugins {\n    proxmox = {\n      source  = "github.com/hashicorp/proxmox"\n      version = ">= 1.2.0"\n    }\n  }\n}\n\nlocals {')
    _, by_rule = lint(source)
    assert any("hashicorp/proxmox" in f.message and f.level == "error" for f in by_rule.get("T016", []))


def test_invalid_hcl_is_an_error(lint, source):
    (source / TEMPLATE).write_text('variable "x" {\n', encoding="utf-8")
    _, by_rule = lint(source)
    assert "T002" in by_rule


# --- blueprints ---------------------------------------------------------------


def test_blueprint_id_must_match_directory(lint, source):
    edit(source / BLUEPRINT, "id: example", "id: other")
    _, by_rule = lint(source)
    assert any("does not match the directory" in f.message for f in by_rule.get("B001", []))


def test_blueprint_version_must_be_semver(lint, source):
    edit(source / BLUEPRINT, "version: 0.1.0", "version: latest")
    _, by_rule = lint(source)
    assert any("semver" in f.message for f in by_rule.get("B001", []))


def test_range_config_schema_violation(lint, source):
    edit(source / RANGE, "vlan: 10", "vlan: 1000")
    _, by_rule = lint(source)
    assert any("vlan" in f.message for f in by_rule.get("B002", []))


def test_range_config_unknown_key_is_rejected(lint, source):
    edit(source / RANGE, "    linux: true", "    linux: true\n    made_up: true")
    _, by_rule = lint(source)
    assert any("made_up" in f.message for f in by_rule.get("B002", []))


def test_duplicate_ip_is_an_error(lint, source):
    (source / RANGE).write_text(
        textwrap.dedent(
            """
            ludus:
              - vm_name: "{{ range_id }}-a"
                hostname: "a"
                template: ludusplusplus-debian-13-x64-server-template
                vlan: 10
                ip_last_octet: 10
                ram_gb: 2
                cpus: 2
                linux: true
              - vm_name: "{{ range_id }}-b"
                hostname: "b"
                template: ludusplusplus-debian-13-x64-server-template
                vlan: 10
                ip_last_octet: 10
                ram_gb: 2
                cpus: 2
                linux: true
            """
        ),
        encoding="utf-8",
    )
    _, by_rule = lint(source)
    assert any("duplicate vlan 10 / ip_last_octet 10" in f.message for f in by_rule.get("B003", []))


def test_vm_name_without_range_id_is_a_warning(lint, source):
    edit(source / RANGE, 'vm_name: "{{ range_id }}-lpp-debian13"', 'vm_name: "lpp-debian13"')
    _, by_rule = lint(source)
    assert any("range_id" in f.message for f in by_rule.get("B008", []))


def test_undeclared_role_is_an_error(lint, source):
    edit(source / RANGE, "    linux: true", "    linux: true\n    roles:\n      - badsectorlabs.ludus_adcs")
    _, by_rule = lint(source)
    assert any("badsectorlabs.ludus_adcs" in f.message for f in by_rule.get("B004", []))


def test_declared_role_is_accepted(lint, source):
    edit(source / RANGE, "    linux: true", "    linux: true\n    roles:\n      - badsectorlabs.ludus_adcs")
    (source / "blueprints/example/requirements.yml").write_text("roles:\n  - name: badsectorlabs.ludus_adcs\n    src: https://github.com/badsectorlabs/ludus_adcs\n", encoding="utf-8")
    _, by_rule = lint(source)
    assert "B004" not in by_rule


def test_vendored_role_satisfies_reference(lint, source):
    role = source / "ansible/roles/my_role"
    (role / "tasks").mkdir(parents=True)
    (role / "meta").mkdir()
    (role / "tasks/main.yml").write_text("- name: hi\n  ansible.builtin.debug:\n    msg: hi\n", encoding="utf-8")
    (role / "meta/main.yml").write_text("galaxy_info:\n  author: acme\n  role_name: my_role\n  description: test\n", encoding="utf-8")
    edit(source / RANGE, "    linux: true", "    linux: true\n    roles:\n      - acme.my_role")
    _, by_rule = lint(source)
    assert "B004" not in by_rule and "R001" not in by_rule


def test_fqcn_role_needs_collection(lint, source):
    edit(source / RANGE, "    linux: true", "    linux: true\n    roles:\n      - community.crypto.openssl_certificate")
    _, by_rule = lint(source)
    assert any("community.crypto.openssl_certificate" in f.message for f in by_rule.get("B004", []))
    (source / "blueprints/example/requirements.yml").write_text("collections:\n  - name: community.crypto\n", encoding="utf-8")
    _, by_rule = lint(source)
    assert "B004" not in by_rule


def test_unknown_template_is_a_warning_unless_allowlisted(lint, source):
    edit(source / RANGE, "template: ludusplusplus-debian-13-x64-server-template", "template: someone-elses-template")
    _, by_rule = lint(source)
    assert any("someone-elses-template" in f.message for f in by_rule.get("B005", []))
    _, by_rule = lint(source, {"known_templates": ["someone-elses-template"]})
    assert "B005" not in by_rule


def test_builtin_and_bsl_templates_are_known(lint, source):
    edit(source / RANGE, "template: ludusplusplus-debian-13-x64-server-template", "template: win2022-server-x64-template")
    _, by_rule = lint(source)
    assert "B005" not in by_rule


def test_router_block_is_a_warning(lint, source):
    edit(source / RANGE, "ludus:", 'router:\n  vm_name: "{{ range_id }}-router"\nludus:')
    _, by_rule = lint(source)
    assert any("router" in f.message for f in by_rule.get("B008", []))


# --- roles / collections / source --------------------------------------------


def test_role_without_meta_is_an_error(lint, source):
    role = source / "ansible/roles/broken"
    (role / "tasks").mkdir(parents=True)
    (role / "tasks/main.yml").write_text("[]\n", encoding="utf-8")
    _, by_rule = lint(source)
    assert any("meta/main.yml" in f.message for f in by_rule.get("R001", []))


def test_collection_without_namespace_is_an_error(lint, source):
    col = source / "ansible/collections/thing"
    col.mkdir(parents=True)
    (col / "galaxy.yml").write_text("name: thing\nversion: 1.0.0\n", encoding="utf-8")
    _, by_rule = lint(source)
    assert any("namespace" in f.message for f in by_rule.get("C001", []))


def test_source_manifest_version_is_checked(lint, source):
    edit(source / "source.yml", "manifest_version: 1", "manifest_version: 2")
    _, by_rule = lint(source)
    assert "S003" in by_rule


def test_uninitialised_submodule_is_an_error(lint, source):
    (source / ".gitmodules").write_text('[submodule "ansible/roles/vendored"]\n\tpath = ansible/roles/vendored\n\turl = https://example.invalid/vendored.git\n', encoding="utf-8")
    (source / "ansible/roles/vendored").mkdir()
    _, by_rule = lint(source)
    assert any("not initialised" in f.message for f in by_rule.get("S004", []))


def test_empty_source_is_an_error(lint, tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    (root / "source.yml").write_text("manifest_version: 1\n", encoding="utf-8")
    _, by_rule = lint(root)
    assert "S001" in by_rule


def test_severity_override_can_silence_a_rule(lint, source):
    edit(source / RANGE, 'vm_name: "{{ range_id }}-lpp-debian13"', 'vm_name: "lpp-debian13"')
    _, by_rule = lint(source, {"severity": {"B008": "off"}})
    assert "B008" not in by_rule


# --- CLI ----------------------------------------------------------------------


def test_cli_exit_codes(lint_module, source, capsys):
    assert lint_module.main(["--root", str(source)]) == 0
    edit(source / RANGE, 'vm_name: "{{ range_id }}-lpp-debian13"', 'vm_name: "lpp-debian13"')
    assert lint_module.main(["--root", str(source)]) == 0  # warning only
    assert lint_module.main(["--root", str(source), "--strict"]) == 1
    edit(source / TEMPLATE, 'storage_pool = "${var.proxmox_storage_pool}"', 'storage_pool = "local-zfs"')
    assert lint_module.main(["--root", str(source), "--format", "github"]) == 1
    out = capsys.readouterr().out
    assert "::error file=" in out and "T008" in out
