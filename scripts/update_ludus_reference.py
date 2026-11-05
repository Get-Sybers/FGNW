#!/usr/bin/env python3
"""Regenerate ludus-reference/ from the upstream Ludus repositories.

Fetches badsectorlabs/ludus (sparse, blob-less) and badsectorlabs/ludus-source-bsl
at the requested refs, extracts the facts the linter and the Packer smoke test
rely on, and writes them to ludus-reference/:

  versions.json            Packer / plugin versions the Ludus server installs
  packer-variables.json    the -var set, PKR_VAR_ variables and environment of `packer build`
  proxmox-bindings.json    curated binding rules (kept here so they are reproducible)
  credentials.json         per-OS credentials from range-management/group_vars
  templates.json           builtin + Bad Sector Labs template names
  range-config.jsonschema  verbatim copy of the range config schema

With --check nothing is written: the files are regenerated into a temporary
directory and compared with the committed copies (provenance commit/date
ignored); exit status 1 means upstream drifted and the rules need review.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

LUDUS_REPO = "https://github.com/badsectorlabs/ludus"
BSL_REPO = "https://github.com/badsectorlabs/ludus-source-bsl"

LUDUS_PATHS = [
    "ludus-api/api_template_management.go",
    "ludus-server/dependency_updates.go",
    "docs/docs/using-ludus/templates.md",
    "ludus-server/ansible/range-management/group_vars/*",
    "ludus-server/ansible/user-files/range-config.jsonschema",
    "ludus-server/packer/*/*.pkr.hcl",
    "ludus-server/packer/README.md",
]

# Human text for the variables Ludus passes. New upstream variables get a generic
# description until someone documents them here.
VARIABLE_DOCS = {
    "proxmox_url": ("https://<proxmox>:8006/api2/json", "Proxmox API URL (server config proxmox_url + /api2/json)"),
    "proxmox_host": ("ludus", "Proxmox node name to build on (server config proxmox_node)"),
    "proxmox_skip_tls_verify": ("true", "Whether to accept the Proxmox API certificate without verification (server config proxmox_invalid_cert)"),
    "proxmox_pool": ("SHARED", "Always SHARED: templates must live in the SHARED pool to be usable by every Ludus user"),
    "proxmox_storage_pool": ("local", "VM disk storage pool (server config proxmox_vm_storage_pool)"),
    "proxmox_storage_format": ("qcow2", "VM disk format for the storage pool (server config proxmox_vm_storage_format)"),
    "iso_storage_pool": ("local", "Storage pool ISOs are downloaded to (server config proxmox_iso_storage_pool)"),
    "ansible_home": ("/opt/ludus/users/<user>/.ansible", "Writable ANSIBLE_HOME for the building user; everything outside the install dir is read-only"),
    "ludus_nat_interface": ("vmbr1000", "Bridge templates are built on (server config ludus_nat_interface)"),
    "proxmox_username": ("", "Declared by the documented required block; Ludus sets it to an empty string so the Proxmox plugin falls back to the PROXMOX_USERNAME environment variable (the user's API token id). Never give it a default."),
    "proxmox_password": ("", "Declared by the documented required block; Ludus sets it to an empty string so the Proxmox plugin falls back to the PROXMOX_TOKEN environment variable. Must be sensitive and never have a default."),
}

ENVIRONMENT_DOCS = {
    "PACKER_PLUGIN_PATH": "/opt/ludus/resources/packer/plugins (plugins are pre-installed; templates must not rely on `packer init`)",
    "PROXMOX_USERNAME": "<user API token id> (read by the Proxmox plugin when `username` is empty)",
    "PROXMOX_TOKEN": "<user API token secret> (read by the Proxmox plugin when `password`/`token` are empty)",
    "PACKER_CONFIG_DIR": "/opt/ludus/users/<user>/packer",
    "PACKER_CACHE_DIR": "/opt/ludus/users/<user>/packer/packer_cache",
    "ANSIBLE_ROLES_PATH": "user roles dir, then the instance-wide global roles dir (inherited by Ansible provisioners; do not override)",
    "ANSIBLE_COLLECTIONS_PATH": "user collections dir, then the instance-wide global collections dir (inherited by Ansible provisioners; do not override)",
    "CHECKPOINT_DISABLE": "1",
    "PACKER_LOG": "1",
    "PACKER_LOG_PATH": "/opt/ludus/users/<user>/packer/log-history/<template>-<timestamp>.log",
    "TMPDIR": "/opt/ludus/users/<user>/packer/tmp",
}

# Curated: which builder attributes must be driven by the Ludus variables. Derived
# from the builtin templates, the Bad Sector Labs templates and the templates doc.
PROXMOX_BINDINGS = {
    "_comment": "Which proxmox-iso builder attributes must be driven by the Ludus build-time variables rather than hard-coded. Derived from the builtin templates in ludus-server/packer/, the Bad Sector Labs source templates, and docs/docs/using-ludus/templates.md. Regenerate with `make update-reference`.",
    "builder_types": ["proxmox-iso", "proxmox-clone"],
    "required_bindings": [
        {"attribute": "proxmox_url", "variable": "proxmox_url", "required": True, "why": "API endpoint of the Ludus Proxmox server"},
        {"attribute": "node", "variable": "proxmox_host", "required": True, "why": "Build on the node Ludus is configured for"},
        {"attribute": "insecure_skip_tls_verify", "variable": "proxmox_skip_tls_verify", "required": True, "why": "Follow the server's certificate policy"},
        {"attribute": "pool", "variable": "proxmox_pool", "required": True, "why": "Templates must land in the SHARED pool to be usable by all users"},
        {"attribute": "disks[].storage_pool", "variable": "proxmox_storage_pool", "required": True, "why": "Use the server's VM storage pool (ZFS/LVM/local differ per install)"},
        {"attribute": "disks[].format", "variable": "proxmox_storage_format", "required": True, "why": "Disk format must match what the storage pool supports"},
        {"attribute": "network_adapters[].bridge", "variable": "ludus_nat_interface", "required": True, "why": "Build on the Ludus NAT bridge so the installer gets DHCP + internet"},
        {"attribute": "boot_iso.iso_storage_pool", "variable": "iso_storage_pool", "required": "one_of_iso_storage", "why": "Download the installer ISO to the configured ISO storage"},
        {"attribute": "iso_storage_pool", "variable": "iso_storage_pool", "required": "one_of_iso_storage", "why": "Deprecated top-level form of boot_iso.iso_storage_pool"},
        {"attribute": "additional_iso_files[].iso_storage_pool", "variable": "iso_storage_pool", "required": False, "why": "Extra ISOs (virtio drivers, provisioning CD) go to the same ISO storage"},
        {"attribute": "efi_config.efi_storage_pool", "variable": "proxmox_storage_pool", "required": False, "why": "EFI vars disk lives with the VM disks"},
        {"attribute": "tpm_config.tpm_storage_pool", "variable": "proxmox_storage_pool", "required": False, "why": "vTPM state disk lives with the VM disks"},
        {"attribute": "cloud_init_storage_pool", "variable": "proxmox_storage_pool", "required": False, "why": "cloud-init drive lives with the VM disks"},
        {"attribute": "username", "variable": "proxmox_username", "required": False, "why": "Must be empty at build time so the plugin uses PROXMOX_USERNAME from the environment"},
        {"attribute": "password", "variable": "proxmox_password", "required": False, "why": "Must be empty at build time so the plugin uses PROXMOX_TOKEN from the environment"},
        {"attribute": "token", "variable": "proxmox_password", "required": False, "why": "Never hard-code an API token in a template"},
    ],
    "forbidden_attributes": [
        {"attribute": "vm_id", "why": "Ludus/Proxmox allocate the next free VMID; a fixed id collides on shared servers"},
        {"attribute": "skip_convert_to_template", "when_equals": True, "why": "Ludus needs the build to end as a Proxmox template"},
    ],
    "template_name_rules": {
        "resolved_from": "vm_name in a source block (variable and local references resolved from variable defaults), falling back to variable \"vm_name\"",
        "must_end_with": "-template",
        "dns_name_regex": "^(?:(?:(?:[a-zA-Z0-9](?:[a-zA-Z0-9\\-]*[a-zA-Z0-9])?)\\.)*(?:[A-Za-z0-9](?:[A-Za-z0-9\\-]*[A-Za-z0-9])?))$",
        "template_name_attribute": "must be absent or equal to vm_name: Ludus looks the built template up by vm_name",
    },
    "proxmox_os_types": ["wxp", "w2k", "w2k3", "w2k8", "wvista", "win7", "win8", "win10", "win11", "l24", "l26", "solaris", "other"],
    "ludus_os_detection": "Ludus reads the literal default of variable \"os\" (regex over the file) and maps win*/w2k*/wxp/wvista -> windows, l2* -> linux, anything else -> other; with no such variable it guesses from the template name",
    "communicators": ["ssh", "winrm"],
    "ansible_provisioner": {
        "required_env": ["ANSIBLE_HOME=${var.ansible_home}"],
        "recommended_env_ssh": ["ANSIBLE_LOCAL_TEMP=${var.ansible_home}/tmp", "ANSIBLE_PERSISTENT_CONTROL_PATH_DIR=${var.ansible_home}/pc", "ANSIBLE_SSH_CONTROL_PATH_DIR=${var.ansible_home}/cp"],
        "must_not_set_env": ["ANSIBLE_ROLES_PATH", "ANSIBLE_COLLECTIONS_PATH"],
        "required_attributes": {"skip_version_check": True},
        "recommended_attributes": {"use_proxy": False},
        "source": "ludus-server/packer/README.md",
    },
    "performance_recommendations": {
        "scsi_controller": "virtio-scsi-single",
        "disks[].type": "virtio",
        "disks[].discard": True,
        "disks[].io_thread": True,
        "network_adapters[].model": "virtio",
        "cpu_type": "host",
        "source": "docs/docs/using-ludus/templates.md#performance-options",
    },
}


def run(cmd: list[str], cwd: Path | None = None) -> str:
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def fetch_repo(url: str, ref: str, dest: Path, sparse_paths: list[str] | None) -> dict:
    """Shallow clone of a single ref (branch, tag or commit), optionally sparse."""
    run(["git", "init", "-q", str(dest)])
    run(["git", "remote", "add", "origin", url], cwd=dest)
    if sparse_paths:
        run(["git", "config", "core.sparseCheckout", "true"], cwd=dest)
        (dest / ".git" / "info").mkdir(parents=True, exist_ok=True)
        (dest / ".git" / "info" / "sparse-checkout").write_text("\n".join(sparse_paths) + "\n")
        run(["git", "fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", ref], cwd=dest)
    else:
        run(["git", "fetch", "-q", "--depth", "1", "origin", ref], cwd=dest)
    run(["git", "-c", "advice.detachedHead=false", "checkout", "-q", "--detach", "FETCH_HEAD"], cwd=dest)
    return {
        "repo": url,
        "ref": ref,
        "commit": run(["git", "rev-parse", "HEAD"], cwd=dest),
        "commit_date": run(["git", "log", "-1", "--format=%cI"], cwd=dest),
    }


def grab(pattern: str, text: str, flags: int = 0) -> str:
    m = re.search(pattern, text, flags)
    if not m:
        raise SystemExit(f"update_ludus_reference: pattern {pattern!r} not found upstream; the rule needs attention")
    return m.group(1)


def derive_versions(ludus: Path, prov: dict) -> dict:
    go = (ludus / "ludus-server" / "dependency_updates.go").read_text(encoding="utf-8")
    packer = grab(r'minPackerVersion\s*=\s*"([^"]+)"', go)
    proxmox_ver = grab(r'minPackerProxmoxPluginVersion\s*=\s*"([^"]+)"', go)
    ansible_ver = grab(r'minPackerAnsiblePluginVersion\s*=\s*"([^"]+)"', go)
    proxmox_src = grab(r'packer plugins install (github\.com/[\w.-]+/proxmox) v', go)
    ansible_src = grab(r'packer plugins install (github\.com/[\w.-]+/ansible) v', go)
    literal_versions = [v for v in re.findall(r"proxmox v(\d+\.\d+\.\d+)\"", go) if v != proxmox_ver]
    proxmox = {
        "source": proxmox_src,
        "version": proxmox_ver,
    }
    if literal_versions:
        proxmox["fallback_version_for_proxmox_below_9_1"] = literal_versions[0]
    proxmox["note"] = f"Ludus installs the Bad Sector Labs fork, not github.com/hashicorp/proxmox (ludus-server/dependency_updates.go)." if "badsectorlabs" in proxmox_src else "Plugin source as installed by ludus-server/dependency_updates.go."
    return {
        "_comment": "Tool versions the Ludus server pins for template builds. Source: ludus-server/dependency_updates.go and ludus-server/ansible/proxmox-install/stage-3.yml in badsectorlabs/ludus. Regenerate with `make update-reference`.",
        "provenance": prov,
        "packer": {
            "min_version": packer,
            "source": "ludus-server/dependency_updates.go (minPackerVersion)",
            "download": "https://releases.hashicorp.com/packer/{version}/packer_{version}_linux_amd64.zip",
        },
        "plugins": {"proxmox": proxmox, "ansible": {"source": ansible_src, "version": ansible_ver}},
    }


def derive_packer_variables(ludus: Path) -> dict:
    go = (ludus / "ludus-api" / "api_template_management.go").read_text(encoding="utf-8")
    start = go.index("tmplStr := ")
    end = go.index("{{.PackerFile}}", start)
    tmpl = go[start:end]
    cli_names = re.findall(r"-var '([a-z_]+)=", tmpl)
    env_names = re.findall(r'PKR_VAR_([a-z_]+)=""', tmpl)
    env_keys = re.findall(r"`([A-Z_]+)=", tmpl)
    env_keys = [k for k in env_keys if not k.startswith("PKR_VAR_")]
    for extra in re.findall(r"\s([A-Z_]+)=(?:\{\{|1)", tmpl):
        if extra not in env_keys and extra not in ("PKR_VAR_proxmox_password", "PKR_VAR_proxmox_username"):
            env_keys.append(extra)
    flags = re.findall(r"packer build ((?:-[a-z-]+=\S+\s*)+)", tmpl)
    build_flags = flags[0].strip() if flags else ""

    docs = (ludus / "docs" / "docs" / "using-ludus" / "templates.md").read_text(encoding="utf-8")
    block_start = docs.index("# This block has to be in each file")
    block_end = docs.index("####", block_start)
    block = docs[block_start:block_end]
    documented: dict[str, dict] = {}
    for m in re.finditer(r'variable\s+"(\w+)"\s*\{([^}]*)\}', block):
        body = m.group(2)
        documented[m.group(1)] = {
            "type": grab(r"type\s*=\s*(\w+)", body),
            "sensitive": bool(re.search(r"sensitive\s*=\s*true", body)),
        }

    def spec(name: str, set_by: str, optional: bool) -> dict:
        doc = documented.get(name, {"type": "string", "sensitive": False})
        example, text = VARIABLE_DOCS.get(name, ("", "New upstream variable; document it in scripts/update_ludus_reference.py"))
        out = {"name": name, "type": doc["type"]}
        if doc["sensitive"]:
            out["sensitive"] = True
        if example:
            out["example"] = example
        out["set_by"] = set_by
        if optional:
            out["optional"] = True
        out["description"] = text
        return out

    return {
        "_comment": "How the Ludus server invokes Packer for a template build. Derived from buildVMFromTemplateWithPacker() in ludus-api/api_template_management.go and the 'Creating Your Own Templates' section of docs/docs/using-ludus/templates.md. Regenerate with `make update-reference`.",
        "command": f"packer build {build_flags} <template.pkr.hcl>".replace("  ", " "),
        "working_directory": "the directory that contains the template's .pkr.hcl file (relative paths in the template resolve from here)",
        "cli_variables": [spec(n, "-var", False) for n in cli_names],
        "environment_variables": [spec(n, f'PKR_VAR_{n}=""', True) for n in env_names],
        "process_environment": {k: ENVIRONMENT_DOCS.get(k, "(set by the Ludus server)") for k in env_keys},
        "documented_required_block": list(documented),
    }


def derive_credentials(ludus: Path) -> dict:
    import yaml

    groups: dict[str, dict] = {}
    gv = ludus / "ludus-server" / "ansible" / "range-management" / "group_vars"
    for path in sorted(gv.glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if "ludus_template_user" not in data:
            continue
        conn = str(data.get("ansible_connection", "ssh"))
        if "winrm" in conn:
            port = data.get("ludus_windows_control_port", "")
            conn = "winrm (HTTPS, port 5986)" if "5986" in str(port) else "winrm (HTTPS)"
        groups[path.stem] = {
            "user": str(data["ludus_template_user"]),
            "password": str(data.get("ludus_template_password", "")),
            "connection": conn,
        }
    return {
        "_comment": "Credentials Ludus uses to reach a deployed VM, keyed by the OS id the QEMU guest agent reports (os-release ID; mswindows -> windows). A template whose baked-in account differs cannot be configured by `ludus range deploy`. Source: ludus-server/ansible/range-management/group_vars/*.yml. Regenerate with `make update-reference`.",
        "groups": groups,
        "convention": "localuser:password unless the OS has a reason not to (docs/docs/using-ludus/templates.md)",
    }


VM_NAME_RE = re.compile(r'variable\s+"vm_name"\s*\{[^}]*default\s*=\s*"([^"]+)"', re.S)


def template_names(paths: list[Path]) -> list[str]:
    names = set()
    for p in paths:
        m = VM_NAME_RE.search(p.read_text(encoding="utf-8", errors="replace"))
        if m:
            names.add(m.group(1))
    return sorted(names)


def derive_templates(ludus: Path, bsl: Path) -> dict:
    return {
        "_comment": "Template names that already exist on every Ludus server: the builtins compiled into ludus-server (ludus-server/packer/*) and the Bad Sector Labs source Ludus auto-registers at startup. A source template must not reuse a builtin name (rejected) and should not reuse a BSL name (skipped as already installed). Regenerate with `make update-reference`.",
        "builtin": template_names(sorted((ludus / "ludus-server" / "packer").glob("*/*.pkr.hcl"))),
        "ludus_source_bsl": template_names(sorted((bsl / "templates").glob("*/*.pkr.hcl"))),
    }


def generate(out: Path, ludus_ref: str, bsl_ref: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ludus-reference-") as tmp:
        tmp_path = Path(tmp)
        ludus = tmp_path / "ludus"
        bsl = tmp_path / "bsl"
        print(f"fetching {LUDUS_REPO}@{ludus_ref} (sparse)", file=sys.stderr)
        ludus_prov = fetch_repo(LUDUS_REPO, ludus_ref, ludus, LUDUS_PATHS)
        print(f"fetching {BSL_REPO}@{bsl_ref}", file=sys.stderr)
        bsl_prov = fetch_repo(BSL_REPO, bsl_ref, bsl, ["templates/*/*.pkr.hcl"])
        prov = {"ludus": ludus_prov, "ludus_source_bsl": bsl_prov}

        files = {
            "versions.json": derive_versions(ludus, prov),
            "packer-variables.json": derive_packer_variables(ludus),
            "proxmox-bindings.json": PROXMOX_BINDINGS,
            "credentials.json": derive_credentials(ludus),
            "templates.json": derive_templates(ludus, bsl),
        }
        for name, data in files.items():
            (out / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        schema_path = out / "range-config.jsonschema"
        shutil.copyfile(ludus / "ludus-server" / "ansible" / "user-files" / "range-config.jsonschema", schema_path)
        schema = schema_path.read_text(encoding="utf-8")
        json.loads(schema)  # must be valid JSON
        # Normalise to the repo's editorconfig / pre-commit rules (no trailing
        # whitespace, exactly one final newline) so the committed copy is
        # hook-clean by construction and round-trips through --check and the
        # weekly drift job; upstream ships it with trailing whitespace and no
        # final newline, which the pre-commit hooks would otherwise rewrite.
        schema_path.write_text("\n".join(line.rstrip() for line in schema.split("\n")).rstrip("\n") + "\n", encoding="utf-8")


def normalise(name: str, text: str) -> str:
    if name == "versions.json":
        data = json.loads(text)
        data.pop("provenance", None)
        return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    return text


def check(current: Path, ludus_ref: str, bsl_ref: str) -> int:
    with tempfile.TemporaryDirectory(prefix="ludus-reference-check-") as tmp:
        fresh = Path(tmp) / "ludus-reference"
        generate(fresh, ludus_ref, bsl_ref)
        drift = 0
        for path in sorted(fresh.iterdir()):
            old = current / path.name
            new_text = normalise(path.name, path.read_text(encoding="utf-8"))
            old_text = normalise(path.name, old.read_text(encoding="utf-8")) if old.exists() else ""
            if new_text != old_text:
                drift += 1
                print(f"::warning file=ludus-reference/{path.name}::upstream Ludus changed something this file records")
                sys.stdout.writelines(difflib.unified_diff(old_text.splitlines(True), new_text.splitlines(True), f"ludus-reference/{path.name} (committed)", f"ludus-reference/{path.name} (upstream {ludus_ref})"))
        if drift:
            print(f"\nupdate_ludus_reference: {drift} file(s) drifted from upstream; run `make update-reference`, review the linter rules, and commit")
            return 1
        print("update_ludus_reference: ludus-reference/ matches upstream")
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "ludus-reference"), help="directory to (re)generate (default: <repo>/ludus-reference)")
    parser.add_argument("--ref", default="main", help="badsectorlabs/ludus branch, tag or commit (default: main)")
    parser.add_argument("--bsl-ref", default="main", help="badsectorlabs/ludus-source-bsl branch, tag or commit (default: main)")
    parser.add_argument("--check", action="store_true", help="compare upstream with the committed files instead of writing; exit 1 on drift")
    args = parser.parse_args(argv)
    out = Path(args.out)
    if args.check:
        return check(out, args.ref, args.bsl_ref)
    generate(out, args.ref, args.bsl_ref)
    print(f"update_ludus_reference: wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
