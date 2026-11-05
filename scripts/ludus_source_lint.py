#!/usr/bin/env python3
"""Lint a Ludus source repository against the native Ludus conventions.

The checks mirror what the Ludus server does when a source is registered
(``ludus source add`` / ``sync``) and when a template is built, so that a
template or blueprint that passes here also works on a real Ludus server:

* repository layout: ``source.yml``, ``blueprints/``, ``templates/``,
  ``ansible/roles/``, ``ansible/collections/`` (ludus-api/source_walker.go,
  source_schema.go, source_catalog.go);
* Packer templates: the build-time variables Ludus injects, the Proxmox
  builder attributes that must be bound to them, template-name resolution,
  OS detection, ansible provisioner requirements and file references
  (ludus-api/api_template_management.go, ludus-server/packer/README.md,
  docs/docs/using-ludus/templates.md);
* blueprints: manifest rules, the range-config JSON schema and the offline
  checks ``range config set`` / ``blueprint apply`` perform
  (ludus-api/yaml_validate.go), dependency declarations.

Everything Ludus-specific is read from ``ludus-reference/`` so the rules track
upstream instead of a hand-written list (see ``make update-reference``).

Exit status: 1 when any error is reported (or any warning with ``--strict``).
"""

from __future__ import annotations

import argparse
import dataclasses
import fnmatch
import glob
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError:  # pragma: no cover - dependency error surfaced to the user
    sys.exit("ludus_source_lint: PyYAML is required (pip install -r requirements-ci.txt)")

# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

LEVELS = ("error", "warning", "info", "off")
LEVEL_RANK = {"error": 0, "warning": 1, "info": 2}

RULES: dict[str, tuple[str, str]] = {
    # Source layout
    "S001": ("error", "the source must ship at least one blueprint, template, role or collection"),
    "S002": ("warning", "source.yml should exist and carry name, description, authors and homepage"),
    "S003": ("error", "source.yml must be valid (manifest_version <= 1, string fields, authors list)"),
    "S004": ("error", "git submodules must be populated and live under an artifact directory"),
    "S005": ("warning", "README.md should exist at the repository root"),
    "S006": ("info", "unexpected entry in an artifact directory"),
    # Blueprints
    "B001": ("error", "blueprint.yml must exist and satisfy the Ludus manifest rules"),
    "B002": ("error", "range-config.yml must validate against the Ludus range-config JSON schema"),
    "B003": ("error", "range-config.yml must pass the offline checks the Ludus server runs on apply"),
    "B004": ("error", "every role referenced by range-config.yml must be declared in requirements.yml or vendored"),
    "B005": ("warning", "every template referenced by range-config.yml must be a known template"),
    "B006": ("error", "requirements.yml must use the ansible-galaxy requirements format"),
    "B007": ("warning", "a blueprint should ship a README.md and a description"),
    "B008": ("warning", "range-config conventions: {{ range_id }} in vm_name, no router block, no hard-coded 10.x addresses"),
    # Packer templates
    "T001": ("error", "a template directory must contain exactly one *.pkr.hcl or *.pkr.json file"),
    "T002": ("error", "the template must be valid HCL2"),
    "T003": ("error", "vm_name must resolve to a literal ending in -template, be a valid DNS name and be unique"),
    "T004": ("error", "the Ludus build-time variables must be declared exactly as Ludus passes them"),
    "T005": ("error", "every variable Ludus does not set must have a default"),
    "T006": ("warning", "catalog metadata: static description and icon_path variables"),
    "T007": ("error", "the template must build with the proxmox-iso (or proxmox-clone) builder"),
    "T008": ("error", "Proxmox builder attributes must be bound to the Ludus variables, not hard-coded"),
    "T009": ("error", "vm_id, template_name and skip_convert_to_template are managed by Ludus; API credentials must never be literal"),
    "T010": ("error", "communicator must be ssh or winrm and variable \"os\" must be a literal Proxmox OS type"),
    "T011": ("error", "ansible provisioners must set ANSIBLE_HOME=${var.ansible_home} and skip_version_check = true"),
    "T012": ("error", "every file the template references must exist inside the template directory"),
    "T013": ("error", "Windows templates must ship Autounattend.xml in the template root and use WinRM over HTTPS"),
    "T014": ("warning", "template credentials should match the Ludus group_vars for the guest OS"),
    "T015": ("info", "Proxmox performance options recommended by the Ludus docs"),
    "T016": ("error", "required_plugins, when present, must name the plugin sources the Ludus server installs"),
    "T017": ("warning", "ansible provisioner conventions (use_proxy = false, ANSIBLE_* temp dirs, no roles/collections path override)"),
    # Roles / collections
    "R001": ("error", "a role must have tasks/main.yml and meta/main.yml"),
    "R002": ("warning", "a role's meta/main.yml should define galaxy_info.description (shown in the catalog)"),
    "R003": ("error", "a role's meta/version.yml, when present, must define version"),
    "C001": ("error", "a collection must have galaxy.yml with namespace, name and version"),
    "C002": ("warning", "a collection's galaxy.yml should define description"),
}

ARTIFACT_DIRS = ("blueprints", "templates", "ansible/roles", "ansible/collections")
PACKER_SUFFIXES = (".pkr.hcl", ".pkr.json")
RASTER_ICON_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp")
BLUEPRINT_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_\-]*(/[A-Za-z0-9_\-]+){0,2}$")
SEMVER_RE = re.compile(r"^v?\d+(\.\d+){0,2}([-+][0-9A-Za-z.-]+)?$")
LUDUS_VM_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,62}$")
RANGE_ID_RE = re.compile(r"\{\{\s*range_id\s*\}\}")
RANGE_SECOND_OCTET_RE = re.compile(r"\{\{\s*range_second_octet\s*\}\}")
HARDCODED_10_RE = re.compile(r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
GALAXY_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
VAR_REF_RE = re.compile(r"^\$\{\s*var\.([A-Za-z_][A-Za-z0-9_]*)\s*\}$")
LOCAL_REF_RE = re.compile(r"^\$\{\s*local\.([A-Za-z_][A-Za-z0-9_]*)\s*\}$")
HCL_META_KEYS = {"__is_block__", "__comments__", "__inline_comments__", "__start_line__", "__end_line__"}

GUEST_OS_HINTS: tuple[tuple[str, str], ...] = (
    ("kali", "kali"),
    ("remnux", "ubuntu"),
    ("ubuntu", "ubuntu"),
    ("debian", "debian"),
    ("rocky", "rocky"),
    ("almalinux", "almalinux"),
    ("alma", "almalinux"),
    ("centos", "centos"),
    ("rhel", "rhel"),
    ("redhat", "rhel"),
    ("macos", "macos"),
    ("osx", "osx"),
)


@dataclasses.dataclass
class Finding:
    rule: str
    level: str
    path: str
    message: str
    line: int | None = None

    def as_text(self) -> str:
        loc = f"{self.path}:{self.line}" if self.line else self.path
        return f"{self.level.upper():7} {self.rule}  {loc}: {self.message}"

    def as_github(self) -> str:
        kind = {"error": "error", "warning": "warning", "info": "notice"}[self.level]
        loc = f"file={self.path}" + (f",line={self.line}" if self.line else "")
        msg = self.message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        return f"::{kind} {loc},title={self.rule}::{msg}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def strip_meta(obj: Any) -> Any:
    """Drop python-hcl2 metadata keys recursively."""
    if isinstance(obj, dict):
        return {k: strip_meta(v) for k, v in obj.items() if k not in HCL_META_KEYS}
    if isinstance(obj, list):
        return [strip_meta(v) for v in obj]
    return obj


def is_quoted(value: Any) -> bool:
    return isinstance(value, str) and len(value) >= 2 and value[0] == '"' and value[-1] == '"'


def inner(value: Any) -> Any:
    """Text of an HCL value: the string body for quoted literals, the expression otherwise."""
    if is_quoted(value):
        try:
            return json.loads(value)
        except ValueError:
            return value[1:-1]
    return value


def is_literal_string(value: Any) -> bool:
    return is_quoted(value) and "${" not in value.replace("$${", "")


def var_ref(value: Any) -> str | None:
    """Return NAME when value is exactly ``var.NAME`` / ``"${var.NAME}"``."""
    if not isinstance(value, str):
        return None
    text = value[1:-1] if is_quoted(value) else value
    m = VAR_REF_RE.match(text.strip())
    return m.group(1) if m else None


def local_ref(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value[1:-1] if is_quoted(value) else value
    m = LOCAL_REF_RE.match(text.strip())
    return m.group(1) if m else None


def label(key: str) -> str:
    """Block labels come back quoted (``'"name"'``)."""
    return inner(key) if is_quoted(key) else key


def blocks(body: dict, name: str) -> list[dict]:
    """Nested blocks of ``name`` inside ``body`` (python-hcl2 renders repeated blocks as a list)."""
    value = body.get(name)
    if isinstance(value, list):
        return [v for v in value if isinstance(v, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def find_line(path: Path, needle: str) -> int | None:
    try:
        for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if needle in line:
                return n
    except OSError:
        pass
    return None


def parse_gitmodules(path: Path) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if line.startswith("[submodule"):
            current = {"name": line[len("[submodule") :].strip().strip('[]" ')}
            entries.append(current)
        elif current is not None and "=" in line:
            key, _, value = line.partition("=")
            current[key.strip()] = value.strip()
    return entries


# ---------------------------------------------------------------------------
# Linter
# ---------------------------------------------------------------------------


class Reference:
    """The vendored Ludus facts in ludus-reference/."""

    def __init__(self, ref_dir: Path):
        self.dir = ref_dir
        missing = [n for n in ("packer-variables.json", "proxmox-bindings.json", "credentials.json", "templates.json", "range-config.jsonschema") if not (ref_dir / n).exists()]
        if missing:
            raise SystemExit(f"ludus_source_lint: reference files missing in {ref_dir}: {', '.join(missing)} (run `make update-reference`)")
        self.packer_vars = load_json(ref_dir / "packer-variables.json")
        self.bindings = load_json(ref_dir / "proxmox-bindings.json")
        self.credentials = load_json(ref_dir / "credentials.json")
        self.templates = load_json(ref_dir / "templates.json")
        self.range_schema = load_json(ref_dir / "range-config.jsonschema")
        self.versions = load_json(ref_dir / "versions.json") if (ref_dir / "versions.json").exists() else {}

    @property
    def cli_variables(self) -> list[dict]:
        return self.packer_vars["cli_variables"]

    @property
    def env_variables(self) -> list[dict]:
        return self.packer_vars.get("environment_variables", [])

    @property
    def ludus_variable_names(self) -> set[str]:
        return {v["name"] for v in self.cli_variables} | {v["name"] for v in self.env_variables}

    @property
    def builtin_templates(self) -> set[str]:
        return set(self.templates.get("builtin", []))

    @property
    def bsl_templates(self) -> set[str]:
        return set(self.templates.get("ludus_source_bsl", []))

    @property
    def allowed_plugin_sources(self) -> dict[str, str]:
        plugins = self.versions.get("plugins", {})
        return {p["source"]: p["version"] for p in plugins.values() if "source" in p}


class Linter:
    def __init__(self, root: Path, reference: Reference, config: dict | None = None):
        self.root = root.resolve()
        self.ref = reference
        self.config = config or {}
        self.findings: list[Finding] = []
        self.severity = dict(self.config.get("severity") or {})
        for rule, level in self.severity.items():
            if rule not in RULES:
                raise SystemExit(f"ludus_source_lint: unknown rule {rule!r} in severity overrides")
            if level not in LEVELS:
                raise SystemExit(f"ludus_source_lint: invalid level {level!r} for {rule} (use one of {', '.join(LEVELS)})")
        self.template_names: dict[str, str] = {}
        self.role_identities: set[str] = set()
        self.collection_fqcns: set[str] = set()

    # -- reporting -------------------------------------------------------

    def report(self, rule: str, path: Path | str, message: str, line: int | None = None, level: str | None = None) -> None:
        default_level = RULES[rule][0]
        effective = self.severity.get(rule, default_level)
        if effective == "off":
            return
        if level is not None and effective == default_level:
            # a sub-check may soften (never harden) the rule's default level
            effective = level if LEVEL_RANK[level] >= LEVEL_RANK[default_level] else effective
        rel_path = rel(self.root, path) if isinstance(path, Path) else path
        self.findings.append(Finding(rule, effective, rel_path, message, line))

    def counts(self) -> dict[str, int]:
        out = {"error": 0, "warning": 0, "info": 0}
        for f in self.findings:
            out[f.level] += 1
        return out

    # -- driver ------------------------------------------------------------

    def run(self) -> list[Finding]:
        self.lint_root()
        self.lint_submodules()
        self.lint_templates()
        self.lint_roles()
        self.lint_collections()
        self.lint_blueprints()
        if not (self.template_names or self.role_identities or self.collection_fqcns or self._blueprint_dirs()):
            self.report("S001", ".", "no blueprints/, templates/, ansible/roles/ or ansible/collections/ content found; a Ludus source must ship at least one artifact")
        self.findings.sort(key=lambda f: (LEVEL_RANK[f.level], f.path, f.line or 0, f.rule))
        return self.findings

    # -- source root --------------------------------------------------------

    def lint_root(self) -> None:
        manifest = self.root / "source.yml"
        if not manifest.exists():
            self.report("S002", "source.yml", "source.yml is missing; Ludus falls back to the git URL for the name and homepage, but a name, description, authors and homepage make the source readable in `ludus source list`")
        else:
            try:
                data = load_yaml(manifest)
            except yaml.YAMLError as exc:
                self.report("S003", manifest, f"source.yml is not valid YAML: {exc}")
                data = None
            if data is not None:
                if not isinstance(data, dict):
                    self.report("S003", manifest, "source.yml must be a mapping")
                else:
                    mv = data.get("manifest_version", 1)
                    if not isinstance(mv, int) or isinstance(mv, bool) or mv < 1 or mv > 1:
                        self.report("S003", manifest, f"manifest_version must be the integer 1 (Ludus supports up to 1), got {mv!r}", find_line(manifest, "manifest_version"))
                    for key in ("name", "description", "homepage", "license"):
                        if key in data and not isinstance(data[key], str):
                            self.report("S003", manifest, f"{key} must be a string", find_line(manifest, f"{key}:"))
                    if "authors" in data and (not isinstance(data["authors"], list) or not all(isinstance(a, str) for a in data["authors"])):
                        self.report("S003", manifest, "authors must be a list of strings", find_line(manifest, "authors:"))
                    unknown = set(data) - {"manifest_version", "name", "description", "authors", "homepage", "license"}
                    if unknown:
                        self.report("S003", manifest, f"unknown keys {sorted(unknown)} (Ludus reads manifest_version, name, description, authors, homepage, license)", level="warning")
                    for key in ("name", "description", "authors", "homepage"):
                        if not data.get(key):
                            self.report("S002", manifest, f"{key} is not set")
        if not (self.root / "README.md").exists():
            self.report("S005", "README.md", "add a README.md describing the source, how to add it and what it ships")

    def lint_submodules(self) -> None:
        gitmodules = self.root / ".gitmodules"
        if not gitmodules.exists():
            return
        for entry in parse_gitmodules(gitmodules):
            path = entry.get("path")
            if not path:
                self.report("S004", gitmodules, f"submodule {entry.get('name')!r} has no path")
                continue
            if not any(path == d or path.startswith(d + "/") for d in ARTIFACT_DIRS):
                self.report("S004", gitmodules, f"submodule {path!r} is outside the artifact directories ({', '.join(ARTIFACT_DIRS)}); Ludus only materialises submodules that are a blueprint, template, role or collection", find_line(gitmodules, f"path = {path}"))
            target = self.root / path
            if not target.is_dir() or not any(target.iterdir()):
                self.report("S004", path, "submodule is not initialised (empty directory); clone with --recurse-submodules or run `git submodule update --init --recursive` (CI: actions/checkout with submodules: recursive)")

    # -- templates ----------------------------------------------------------

    def _template_dirs(self) -> list[Path]:
        base = self.root / "templates"
        if not base.is_dir():
            return []
        return sorted(p for p in base.iterdir() if p.is_dir())

    def lint_templates(self) -> None:
        base = self.root / "templates"
        if not base.is_dir():
            return
        for entry in sorted(base.iterdir()):
            if entry.is_file() and entry.name not in ("README.md", "README.rst", ".gitkeep"):
                self.report("S006", entry, "stray file in templates/: each template lives in its own templates/<name>/ directory")
        for tdir in self._template_dirs():
            if (self.root / ".gitmodules").exists() and tdir.is_dir() and not any(tdir.iterdir()):
                continue  # reported by S004
            self.lint_template_dir(tdir)

    def lint_template_dir(self, tdir: Path) -> None:
        packer_files = sorted(p for p in tdir.rglob("*") if p.is_file() and p.name.endswith(PACKER_SUFFIXES))
        if not packer_files:
            self.report("T001", tdir, "no *.pkr.hcl or *.pkr.json file found (the `.pkr.` part of the name is required for Ludus to recognise the template)")
            return
        if len(packer_files) > 1:
            self.report("T001", tdir, "more than one Packer file found: " + ", ".join(rel(tdir, p) for p in packer_files) + " (Ludus rejects a template upload with more than one)")
            return
        pfile = packer_files[0]
        if pfile.parent != tdir:
            self.report("T001", pfile, "the Packer file should sit in the template directory root; Ludus uses its directory as the working directory for the build", level="warning")
        if pfile.name.endswith(".pkr.json"):
            self.report("T001", pfile, "JSON templates are accepted by Ludus but .pkr.hcl is preferred; the structural checks (T003-T017) only run on HCL", level="warning")
            return
        try:
            import hcl2  # noqa: WPS433  (optional dependency, imported lazily)
        except ImportError:
            raise SystemExit("ludus_source_lint: python-hcl2 is required to lint templates (pip install -r requirements-ci.txt)")
        try:
            with pfile.open("r", encoding="utf-8") as fh:
                doc = strip_meta(hcl2.load(fh))
        except Exception as exc:  # lark raises many exception types
            self.report("T002", pfile, f"HCL parse error: {str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__}")
            return
        tpl = TemplateContext(self, tdir, pfile, doc)
        tpl.lint()

    # -- roles ----------------------------------------------------------------

    def lint_roles(self) -> None:
        base = self.root / "ansible" / "roles"
        if not base.is_dir():
            return
        for entry in sorted(base.iterdir()):
            if entry.is_file():
                if entry.name not in ("README.md", ".gitkeep"):
                    self.report("S006", entry, "stray file in ansible/roles/: each role lives in its own directory")
                continue
            if not any(entry.iterdir()):
                continue  # empty submodule, reported by S004 (or an empty placeholder)
            self.lint_role(entry)

    def lint_role(self, rdir: Path) -> None:
        name = rdir.name
        self.role_identities.add(name)
        tasks = next((rdir / "tasks" / f for f in ("main.yml", "main.yaml") if (rdir / "tasks" / f).exists()), None)
        meta = next((rdir / "meta" / f for f in ("main.yml", "main.yaml") if (rdir / "meta" / f).exists()), None)
        if tasks is None:
            self.report("R001", rdir, "tasks/main.yml is missing; Ludus runs the role via ansible so it needs a tasks entry point")
        if meta is None:
            self.report("R001", rdir, "meta/main.yml is missing; Ludus roles must have a meta folder with a main.yml (developers/ansible-roles.md) and Ludus reads galaxy_info from it")
        else:
            try:
                data = load_yaml(meta) or {}
            except yaml.YAMLError as exc:
                self.report("R001", meta, f"meta/main.yml is not valid YAML: {exc}")
                data = {}
            galaxy = data.get("galaxy_info") if isinstance(data, dict) else None
            if not isinstance(galaxy, dict):
                self.report("R002", meta, "galaxy_info is missing; add galaxy_info.description so the role has a description in the Ludus catalog")
            else:
                if not str(galaxy.get("description") or "").strip():
                    self.report("R002", meta, "galaxy_info.description is empty; Ludus shows it in the catalog and picker")
                author = str(galaxy.get("author") or "").strip()
                role_name = str(galaxy.get("role_name") or "").strip()
                if author and role_name:
                    self.role_identities.add(f"{author}.{role_name}")
        version_file = rdir / "meta" / "version.yml"
        if version_file.exists():
            try:
                vdata = load_yaml(version_file)
            except yaml.YAMLError as exc:
                self.report("R003", version_file, f"meta/version.yml is not valid YAML: {exc}")
            else:
                if not isinstance(vdata, dict) or not str(vdata.get("version") or "").strip():
                    self.report("R003", version_file, "meta/version.yml must contain `version: <string>` (Ludus displays it instead of detecting a git tag)")

    # -- collections ------------------------------------------------------------

    def lint_collections(self) -> None:
        base = self.root / "ansible" / "collections"
        if not base.is_dir():
            return
        for entry in sorted(base.iterdir()):
            if entry.is_file():
                if entry.name not in ("README.md", ".gitkeep"):
                    self.report("S006", entry, "stray file in ansible/collections/: each collection lives in its own directory")
                continue
            if not any(entry.iterdir()):
                continue
            self.lint_collection(entry)

    def lint_collection(self, cdir: Path) -> None:
        galaxy = cdir / "galaxy.yml"
        if not galaxy.exists():
            self.report("C001", cdir, "galaxy.yml is missing; Ludus identifies a collection by the namespace.name in galaxy.yml")
            return
        try:
            data = load_yaml(galaxy) or {}
        except yaml.YAMLError as exc:
            self.report("C001", galaxy, f"galaxy.yml is not valid YAML: {exc}")
            return
        if not isinstance(data, dict):
            self.report("C001", galaxy, "galaxy.yml must be a mapping")
            return
        ns = str(data.get("namespace") or "").strip()
        name = str(data.get("name") or "").strip()
        for key, value in (("namespace", ns), ("name", name)):
            if not value:
                self.report("C001", galaxy, f"{key} is required (Ludus rejects a collection without it)")
            elif not GALAXY_NAME_RE.match(value):
                self.report("C001", galaxy, f"{key} {value!r} must match {GALAXY_NAME_RE.pattern} (ansible-galaxy naming rules)")
        if not str(data.get("version") or "").strip():
            self.report("C001", galaxy, "version is required by ansible-galaxy")
        if not str(data.get("description") or "").strip():
            self.report("C002", galaxy, "description is empty; Ludus shows it in the catalog and picker")
        if ns and name:
            fqcn = f"{ns}.{name}"
            if fqcn in self.collection_fqcns:
                self.report("C001", galaxy, f"collection {fqcn} is shipped twice in this source")
            self.collection_fqcns.add(fqcn)

    # -- blueprints ---------------------------------------------------------------

    def _blueprint_dirs(self) -> list[Path]:
        base = self.root / "blueprints"
        if not base.is_dir():
            return []
        found: list[Path] = []

        def walk(d: Path, depth: int) -> None:
            for sub in sorted(p for p in d.iterdir() if p.is_dir()):
                if (sub / "blueprint.yml").exists():
                    found.append(sub)
                elif depth < 2:
                    walk(sub, depth + 1)

        walk(base, 0)
        return found

    def lint_blueprints(self) -> None:
        base = self.root / "blueprints"
        if not base.is_dir():
            return
        for entry in sorted(base.iterdir()):
            if entry.is_file() and entry.name not in ("README.md", ".gitkeep"):
                self.report("S006", entry, "stray file in blueprints/: each blueprint lives in its own blueprints/<id>/ directory")
        bp_dirs = self._blueprint_dirs()
        # directories with files but no blueprint.yml are silently skipped by Ludus; say so
        for sub in sorted(p for p in base.rglob("*") if p.is_dir()):
            if sub in bp_dirs or any(sub.is_relative_to(b) for b in bp_dirs):
                continue
            if any(p.is_file() for p in sub.iterdir()) and not any(p.is_dir() for p in sub.iterdir()):
                self.report("B001", sub, "directory contains files but no blueprint.yml, so Ludus ignores it")
        known_templates = set(self.template_names) | self.ref.builtin_templates | self.ref.bsl_templates | set(self.config.get("known_templates") or [])
        for bdir in bp_dirs:
            self.lint_blueprint(bdir, known_templates)

    def lint_blueprint(self, bdir: Path, known_templates: set[str]) -> None:
        manifest = bdir / "blueprint.yml"
        rel_id = rel(self.root / "blueprints", bdir).replace(os.sep, "/")
        try:
            data = load_yaml(manifest)
        except yaml.YAMLError as exc:
            self.report("B001", manifest, f"blueprint.yml is not valid YAML: {exc}")
            return
        if not isinstance(data, dict):
            self.report("B001", manifest, "blueprint.yml must be a mapping")
            return
        mv = data.get("manifest_version", 1)
        if not isinstance(mv, int) or isinstance(mv, bool) or mv < 1 or mv > 1:
            self.report("B001", manifest, f"manifest_version must be 1, got {mv!r}", find_line(manifest, "manifest_version"))
        bp_id = str(data.get("id") or "")
        if not bp_id:
            self.report("B001", manifest, "id is required")
        elif not BLUEPRINT_ID_RE.match(bp_id):
            self.report("B001", manifest, f"id {bp_id!r} must match {BLUEPRINT_ID_RE.pattern}", find_line(manifest, "id:"))
        elif bp_id != rel_id:
            self.report("B001", manifest, f"id {bp_id!r} does not match the directory path {rel_id!r}; Ludus rejects the source (blueprints/<id>/blueprint.yml must have id: <id>)", find_line(manifest, "id:"))
        if not str(data.get("name") or "").strip():
            self.report("B001", manifest, "name is required")
        version = data.get("version")
        if version is None or str(version).strip() == "":
            self.report("B001", manifest, "version is required")
        elif not SEMVER_RE.match(str(version)):
            self.report("B001", manifest, f"version {version!r} must be valid semver (e.g. 1.0.0)", find_line(manifest, "version:"))
        config_rel = data.get("config")
        config_path: Path | None = None
        if not config_rel:
            self.report("B001", manifest, "config is required (path to range-config.yml, relative to blueprint.yml)")
        elif not self._relative_inside(bdir, str(config_rel)):
            self.report("B001", manifest, f"config {config_rel!r} must be a relative path inside the blueprint directory", find_line(manifest, "config:"))
        else:
            config_path = (bdir / str(config_rel)).resolve()
            if not config_path.is_file():
                self.report("B001", manifest, f"config file {config_rel!r} does not exist", find_line(manifest, "config:"))
                config_path = None
        thumb = data.get("thumbnail_path")
        if thumb:
            if not self._relative_inside(bdir, str(thumb)):
                self.report("B001", manifest, f"thumbnail_path {thumb!r} must be a relative path inside the blueprint directory", find_line(manifest, "thumbnail_path"))
            elif not (bdir / str(thumb)).is_file():
                self.report("B001", manifest, f"thumbnail_path {thumb!r} does not exist", find_line(manifest, "thumbnail_path"))
        tags = data.get("tags")
        if tags is not None and (not isinstance(tags, list) or not all(isinstance(t, str) for t in tags)):
            self.report("B001", manifest, "tags must be a list of strings", find_line(manifest, "tags"))
        mlv = data.get("min_ludus_version")
        if mlv is not None and not SEMVER_RE.match(str(mlv)):
            self.report("B001", manifest, f"min_ludus_version {mlv!r} should be a version like 2.1.2", find_line(manifest, "min_ludus_version"), level="warning")
        if not str(data.get("description") or "").strip():
            self.report("B007", manifest, "description is empty; it is the one-line summary shown in the catalog and picker")
        if not (bdir / "README.md").exists():
            self.report("B007", bdir, "README.md is missing (document the lab: diagram, VM table, credentials)")

        requirements = self.lint_requirements(bdir / "requirements.yml")
        if config_path is not None:
            self.lint_range_config(config_path, requirements, known_templates)

    @staticmethod
    def _relative_inside(base: Path, p: str) -> bool:
        if os.path.isabs(p):
            return False
        cleaned = os.path.normpath(p)
        if cleaned in (".", "") or cleaned.startswith(".."):
            return False
        try:
            (base / cleaned).resolve().relative_to(base.resolve())
        except ValueError:
            return False
        return True

    def lint_requirements(self, req: Path) -> dict[str, set[str]]:
        declared = {"roles": set(), "collections": set(), "subscription_roles": set()}
        if not req.exists():
            return declared
        try:
            data = load_yaml(req)
        except yaml.YAMLError as exc:
            self.report("B006", req, f"requirements.yml is not valid YAML: {exc}")
            return declared
        if data is None:
            return declared
        if not isinstance(data, dict):
            self.report("B006", req, "requirements.yml must be a mapping with roles:, collections: and/or subscription_roles: (the ansible-galaxy requirements format)")
            return declared
        unknown = set(data) - set(declared)
        if unknown:
            self.report("B006", req, f"unknown top-level keys {sorted(unknown)}; Ludus reads roles, collections and subscription_roles")
        for section in declared:
            entries = data.get(section)
            if entries is None:
                continue
            if not isinstance(entries, list):
                self.report("B006", req, f"{section} must be a list", find_line(req, f"{section}:"))
                continue
            for entry in entries:
                if isinstance(entry, str):
                    if section == "subscription_roles":
                        declared[section].add(entry)
                    else:
                        self.report("B006", req, f"{section} entries must be mappings with a name: key (got {entry!r})")
                    continue
                if not isinstance(entry, dict):
                    self.report("B006", req, f"invalid {section} entry {entry!r}")
                    continue
                name = str(entry.get("name") or "").strip()
                if not name:
                    self.report("B006", req, f"{section} entry without name: {entry}")
                    continue
                if section == "collections":
                    src = str(entry.get("source") or "")
                    if src.startswith(("http://", "https://", "git@", "ssh://")) and str(entry.get("type") or "") != "galaxy":
                        self.report("B006", req, f"collection {name!r}: `source:` points at an alternate Galaxy server; a git collection puts the URL in `name:` with `type: git`", find_line(req, name), level="warning")
                    if name.startswith(("http://", "https://", "git@", "ssh://")):
                        if str(entry.get("type") or "") != "git":
                            self.report("B006", req, f"collection {name!r}: a git URL in name: requires `type: git`", find_line(req, name))
                        # the installed FQCN of a git collection is only known after install; accept any FQCN reference
                        declared[section].add("*")
                        continue
                if section == "roles":
                    unknown_keys = set(entry) - {"name", "src", "scm", "version", "include"}
                    if unknown_keys:
                        self.report("B006", req, f"role {name!r}: unknown keys {sorted(unknown_keys)}", find_line(req, name), level="warning")
                declared[section].add(name)
        return declared

    def lint_range_config(self, config: Path, requirements: dict[str, set[str]], known_templates: set[str]) -> None:
        try:
            data = load_yaml(config)
        except yaml.YAMLError as exc:
            self.report("B002", config, f"range config is not valid YAML: {exc}")
            return
        if data is None:
            self.report("B002", config, "range config is empty")
            return
        try:
            import jsonschema
        except ImportError:
            raise SystemExit("ludus_source_lint: jsonschema is required to validate range configs (pip install -r requirements-ci.txt)")
        validator_cls = jsonschema.validators.validator_for(self.ref.range_schema)
        validator = validator_cls(self.ref.range_schema)
        for err in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
            where = "/".join(str(p) for p in err.absolute_path) or "<root>"
            self.report("B002", config, f"{where}: {err.message}", self._line_for_path(config, err.absolute_path))
        if not isinstance(data, dict) or not isinstance(data.get("ludus"), list):
            return

        # Offline subset of validateRangeYAML (ludus-api/yaml_validate.go)
        sample = "JD"
        seen_ip: dict[str, str] = {}
        seen_vm: set[str] = set()
        seen_host: set[str] = set()
        seen_netbios: dict[str, set[str]] = {}
        referenced_roles: list[str] = []
        for idx, vm in enumerate(data["ludus"]):
            if not isinstance(vm, dict):
                continue
            vm_name = str(vm.get("vm_name") or "")
            hostname = str(vm.get("hostname") or "")
            line = self._line_for_path(config, ["ludus", idx])
            if vm_name and not RANGE_ID_RE.search(vm_name):
                self.report("B008", config, f"vm_name {vm_name!r} does not use {{{{ range_id }}}}; names must be unique per range for a source blueprint to be portable", line)
            resolved_vm = RANGE_ID_RE.sub(sample, vm_name)
            if vm_name and not LUDUS_VM_NAME_RE.match(resolved_vm):
                self.report("B003", config, f"vm_name {vm_name!r} is invalid: must be 1-63 chars of letters, digits, '.' or '-' and start with a letter or digit", line)
            resolved_host = RANGE_ID_RE.sub(sample, hostname)
            if hostname and not LUDUS_VM_NAME_RE.match(resolved_host):
                self.report("B003", config, f"hostname {hostname!r} is invalid: must be 1-63 chars of letters, digits, '.' or '-' and start with a letter or digit", line)
            key = f"vlan {vm.get('vlan')} / ip_last_octet {vm.get('ip_last_octet')}"
            if key in seen_ip:
                self.report("B003", config, f"duplicate {key} (also used by {seen_ip[key]})", line)
            seen_ip[key] = vm_name
            if vm_name in seen_vm:
                self.report("B003", config, f"duplicate vm_name {vm_name!r}", line)
            seen_vm.add(vm_name)
            if hostname in seen_host:
                self.report("B003", config, f"duplicate hostname {hostname!r}", line)
            seen_host.add(hostname)
            domain = vm.get("domain") if isinstance(vm.get("domain"), dict) else None
            if domain and domain.get("fqdn"):
                netbios = resolved_host[:15]
                bucket = seen_netbios.setdefault(str(domain["fqdn"]), set())
                if netbios in bucket:
                    self.report("B003", config, f"duplicate Windows hostname {hostname!r}: Windows hostnames are truncated to 15 characters so the first 15 must be unique per domain", line)
                bucket.add(netbios)
                if len(resolved_host) > 15 and not isinstance(vm.get("linux"), bool):
                    self.report("B008", config, f"hostname {hostname!r} is longer than 15 characters and will be truncated for NetBIOS", line)
            template = str(vm.get("template") or "")
            if template and template not in known_templates:
                self.report("B005", config, f"template {template!r} is not shipped by this source, a Ludus builtin or the Bad Sector Labs source; add it under templates/ or list it in .ludus-lint.yml known_templates", line)
            referenced_roles.extend(self._role_names(vm.get("roles")))
            role_vars = vm.get("role_vars")
            if role_vars is not None:
                text = yaml.safe_dump(role_vars)
                if HARDCODED_10_RE.search(text) and not RANGE_SECOND_OCTET_RE.search(text):
                    self.report("B008", config, f"role_vars of {vm_name!r} contain a hard-coded 10.x.y.z address; use {{{{ range_second_octet }}}} so the blueprint works in any range", line)
        router = data.get("router")
        if isinstance(router, dict):
            self.report("B008", config, "router: block present; Ludus auto-provisions the router and source blueprints should not pin one (Bad Sector Labs contribution rule)", self._line_for_path(config, ["router"]))
            referenced_roles.extend(self._role_names(router.get("roles")))
            if router.get("vm_name") and not LUDUS_VM_NAME_RE.match(RANGE_ID_RE.sub(sample, str(router["vm_name"]))):
                self.report("B003", config, f"router.vm_name {router['vm_name']!r} is invalid", self._line_for_path(config, ["router"]))

        for role in sorted(set(referenced_roles)):
            if not self._role_satisfied(role, requirements):
                self.report("B004", config, f"role {role!r} is referenced but not declared in requirements.yml (roles:, collections: for a namespace.collection.role FQCN, or subscription_roles:) and not vendored under ansible/roles/ or ansible/collections/", find_line(config, role))

    @staticmethod
    def _role_names(roles: Any) -> list[str]:
        names: list[str] = []
        if not isinstance(roles, list):
            return names
        for role in roles:
            if isinstance(role, str):
                names.append(role)
            elif isinstance(role, dict):
                if role.get("name"):
                    names.append(str(role["name"]))
                for dep in role.get("depends_on") or []:
                    if isinstance(dep, dict) and dep.get("role"):
                        names.append(str(dep["role"]))
        return names

    def _role_satisfied(self, role: str, requirements: dict[str, set[str]]) -> bool:
        if role in requirements["roles"] or role in requirements["subscription_roles"] or role in self.role_identities:
            return True
        parts = role.split(".")
        if len(parts) == 3:
            fqcn = f"{parts[0]}.{parts[1]}"
            return fqcn in requirements["collections"] or fqcn in self.collection_fqcns or "*" in requirements["collections"]
        return False

    @staticmethod
    def _line_for_path(path: Path, json_path: Iterable[Any]) -> int | None:
        """Best-effort line lookup for a JSON path such as ['ludus', 1, 'vlan']."""
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        try:
            doc = yaml.compose(text)
        except yaml.YAMLError:
            return None
        node = doc
        for step in json_path:
            if node is None:
                return None
            if isinstance(step, int) and isinstance(node, yaml.SequenceNode):
                if step >= len(node.value):
                    return None
                node = node.value[step]
            elif isinstance(node, yaml.MappingNode):
                found = None
                for k, v in node.value:
                    if isinstance(k, yaml.ScalarNode) and k.value == str(step):
                        found = v
                        break
                if found is None:
                    return None
                node = found
            else:
                return None
        return node.start_mark.line + 1 if node is not None else None


# ---------------------------------------------------------------------------
# Packer template checks
# ---------------------------------------------------------------------------


class TemplateContext:
    def __init__(self, linter: Linter, tdir: Path, pfile: Path, doc: dict):
        self.l = linter
        self.ref = linter.ref
        self.tdir = tdir
        self.pfile = pfile
        self.doc = doc
        self.variables: dict[str, dict] = {}
        for item in doc.get("variable", []) or []:
            if isinstance(item, dict):
                for key, body in item.items():
                    self.variables[label(key)] = body if isinstance(body, dict) else {}
        self.locals: dict[str, Any] = {}
        for item in doc.get("locals", []) or []:
            if isinstance(item, dict):
                self.locals.update(item)
        self.sources: list[tuple[str, str, dict]] = []
        for item in doc.get("source", []) or []:
            if isinstance(item, dict):
                for typ, named in item.items():
                    if isinstance(named, dict):
                        for name, body in named.items():
                            self.sources.append((label(typ), label(name), body if isinstance(body, dict) else {}))
        self.builds: list[dict] = [b for b in (doc.get("build", []) or []) if isinstance(b, dict)]

    # -- helpers ------------------------------------------------------------

    def line(self, needle: str) -> int | None:
        return find_line(self.pfile, needle)

    def report(self, rule: str, message: str, needle: str | None = None, level: str | None = None) -> None:
        self.l.report(rule, self.pfile, message, self.line(needle) if needle else None, level)

    def var_default(self, name: str) -> Any:
        body = self.variables.get(name)
        if body is None or "default" not in body:
            return None
        return body["default"]

    def resolve_string(self, value: Any, _depth: int = 0) -> str | None:
        """Resolve a string the way Ludus' extractPackerTemplateName does.

        Ludus evaluates ``vm_name`` with an HCL context holding every variable
        default (literals) and every local that evaluates from those defaults,
        so literals, ``var.X`` references, ``local.Y`` references and template
        strings composed of them resolve; functions and data sources do not.
        """
        if not isinstance(value, str) or _depth > 8:
            return None
        text = inner(value) if is_quoted(value) else value

        def sub(expr: str) -> str | None:
            m = re.fullmatch(r"var\.([A-Za-z_][A-Za-z0-9_]*)", expr)
            if m:
                return self.resolve_string(self.var_default(m.group(1)), _depth + 1)
            m = re.fullmatch(r"local\.([A-Za-z_][A-Za-z0-9_]*)", expr)
            if m:
                return self.resolve_string(self.locals.get(m.group(1)), _depth + 1)
            return None

        out: list[str] = []
        pos = 0
        for match in re.finditer(r"\$\{([^{}]*)\}", text):
            if match.start() > 0 and text[match.start() - 1] == "$":
                continue  # $${ is an escaped literal
            resolved = sub(match.group(1).strip())
            if resolved is None:
                return None
            out.append(text[pos:match.start()])
            out.append(resolved)
            pos = match.end()
        out.append(text[pos:])
        return "".join(out)

    def proxmox_sources(self) -> list[tuple[str, str, dict]]:
        return [s for s in self.sources if s[0] in self.ref.bindings.get("builder_types", ["proxmox-iso", "proxmox-clone"])]

    def provisioners(self) -> list[tuple[str, dict]]:
        out: list[tuple[str, dict]] = []
        for build in self.builds:
            for item in build.get("provisioner", []) or []:
                if isinstance(item, dict):
                    for typ, body in item.items():
                        out.append((label(typ), body if isinstance(body, dict) else {}))
        return out

    # -- driver ------------------------------------------------------------

    def lint(self) -> None:
        name = self.check_template_name()
        # macOS templates cannot use Packer's proxmox-iso builder (macOS has no
        # answer-file installer and boots through OpenCore), so Ludus classifies
        # them by the "macos" substring in vm_name and builds them from a non-
        # Proxmox source (a null source driving the Proxmox REST API). The
        # Proxmox-builder rules (T007, and the variable "os" half of T010) do not
        # apply to macOS templates; every other rule still runs below.
        is_macos = bool(name) and ("macos" in name.lower() or "osx" in name.lower())
        self.check_ludus_variables()
        self.check_other_variables_have_defaults()
        self.check_catalog_metadata()
        sources = self.proxmox_sources()
        if not sources and not is_macos:
            types = sorted({s[0] for s in self.sources}) or ["none"]
            self.report("T007", f"no proxmox-iso source block found (sources: {', '.join(types)}); Ludus builds templates on Proxmox")
        communicator = None
        for typ, sname, body in sources:
            communicator = self.check_source(typ, sname, body, name)
        if not is_macos:
            self.check_os_variable(communicator)
        self.check_provisioners(communicator)
        self.check_required_plugins()
        self.check_file_references()
        if communicator == "winrm":
            self.check_windows()
        self.check_credentials(communicator)

    # -- T003 ---------------------------------------------------------------

    def check_template_name(self) -> str | None:
        resolved: str | None = None
        unresolved: list[str] = []
        for typ, sname, body in self.sources:
            if "vm_name" in body:
                resolved = self.resolve_string(body["vm_name"])
                if resolved:
                    break
                unresolved.append(f"source {typ}.{sname}: vm_name {inner(body['vm_name'])!r}")
        if not resolved:
            fallback = self.var_default("vm_name")
            resolved = inner(fallback) if is_literal_string(fallback) else None
            for item in unresolved:
                if resolved:
                    self.report("T003", f"{item} cannot be resolved from variable defaults and locals, so Ludus falls back to the default of variable \"vm_name\" ({resolved!r}); make sure the built template really gets that name", "vm_name", level="warning")
                else:
                    self.report("T003", f"{item} does not resolve to a plain string (Ludus resolves only literals, variable defaults and locals built from them)", "vm_name")
        if not resolved:
            self.report("T003", "cannot determine the template name: set vm_name in the source block (or a literal default on variable \"vm_name\") ending in -template")
            return None
        if not resolved.endswith("-template"):
            self.report("T003", f"template name {resolved!r} must end with -template (Ludus convention; the suffix is how templates are listed, built and matched in range configs)", resolved)
        dns_re = re.compile(self.ref.bindings["template_name_rules"]["dns_name_regex"])
        if not dns_re.match(resolved):
            self.report("T003", f"template name {resolved!r} is not a valid DNS name (Proxmox plugin: vm_name must be a valid DNS name)", resolved)
        if len(resolved) > 63:
            self.report("T003", f"template name {resolved!r} is longer than 63 characters", resolved, level="warning")
        if resolved in self.ref.builtin_templates:
            self.report("T003", f"template name {resolved!r} collides with a Ludus builtin template; Ludus rejects it", resolved)
        elif resolved in self.ref.bsl_templates:
            self.report("T003", f"template name {resolved!r} is already shipped by the auto-registered Bad Sector Labs source; installing this one is skipped as already present. Prefix the name with this source's slug", resolved, level="warning")
        other = self.l.template_names.get(resolved)
        if other and other != str(self.tdir):
            self.report("T003", f"template name {resolved!r} is also used by {rel(self.l.root, Path(other))}; names must be unique within a source", resolved)
        self.l.template_names[resolved] = str(self.tdir)
        return resolved

    # -- T004 / T005 ------------------------------------------------------------

    def check_ludus_variables(self) -> None:
        for spec in self.ref.cli_variables + self.ref.env_variables:
            name = spec["name"]
            optional = bool(spec.get("optional"))
            body = self.variables.get(name)
            if body is None:
                if optional:
                    continue
                self.report("T004", f"variable \"{name}\" is not declared; Ludus passes `-var {name}=...` and Packer aborts a build with an undeclared -var. Add the documented Ludus variable block")
                continue
            declared_type = str(inner(body.get("type", ""))).strip()
            if declared_type != spec["type"]:
                self.report("T004", f"variable \"{name}\" must have type = {spec['type']} (got {declared_type or 'none'!r})", f'variable "{name}"')
            if "default" in body:
                self.report("T004", f"variable \"{name}\" must not have a default: Ludus sets it at build time and a default hides a broken server configuration", f'variable "{name}"')
            if spec.get("sensitive") and body.get("sensitive") is not True:
                self.report("T004", f"variable \"{name}\" should be declared sensitive = true so its value never appears in build logs", f'variable "{name}"', level="warning")

    def check_other_variables_have_defaults(self) -> None:
        ludus_names = self.ref.ludus_variable_names
        for name, body in self.variables.items():
            if name in ludus_names:
                continue
            if "default" not in body:
                self.report("T005", f"variable \"{name}\" has no default; Ludus only sets the documented variables, so `packer build` fails with \"Unset variable\". Give it a default or derive it from a Ludus variable", f'variable "{name}"')

    # -- T006 ---------------------------------------------------------------

    def check_catalog_metadata(self) -> None:
        desc = self.var_default("description")
        if "description" not in self.variables:
            self.report("T006", "no `variable \"description\"`; add one with a literal default — it is the summary shown by `ludus source list` and the picker")
        elif not is_literal_string(desc) or not inner(desc).strip():
            self.report("T006", "variable \"description\" must have a non-empty literal string default (Ludus reads it without evaluating expressions)", 'variable "description"')
        if "icon_path" in self.variables:
            icon = self.var_default("icon_path")
            if not is_literal_string(icon):
                self.report("T006", "variable \"icon_path\" must have a literal string default (a relative path inside the template directory)", 'variable "icon_path"')
            else:
                rel_icon = inner(icon)
                if os.path.isabs(rel_icon) or ".." in Path(rel_icon).parts:
                    self.report("T006", f"icon_path {rel_icon!r} must be a relative path inside the template directory", 'variable "icon_path"')
                else:
                    icon_file = self.tdir / rel_icon
                    if not icon_file.is_file():
                        self.report("T006", f"icon_path {rel_icon!r} does not exist; Ludus falls back to an OS glyph. Add the file or remove the variable", 'variable "icon_path"')
                    else:
                        if icon_file.suffix.lower() not in RASTER_ICON_SUFFIXES:
                            self.report("T006", f"icon {rel_icon!r} must be a raster image ({', '.join(RASTER_ICON_SUFFIXES)}); SVG is not accepted", 'variable "icon_path"')
                        self._check_icon_dimensions(icon_file)

    def _check_icon_dimensions(self, icon_file: Path) -> None:
        try:
            from PIL import Image  # optional
        except ImportError:
            return
        try:
            with Image.open(icon_file) as img:
                w, h = img.size
        except Exception:
            self.l.report("T006", icon_file, "icon could not be decoded as an image")
            return
        if w != h:
            self.l.report("T006", icon_file, f"icon is {w}x{h}; a square transparent PNG (256x256 works well) renders best on template cards", level="info")
        if max(w, h) > 1024:
            self.l.report("T006", icon_file, f"icon is {w}x{h}; keep catalog icons at or below 1024px", level="info")

    # -- T008 / T009 / T010 / T015 --------------------------------------------------

    def check_source(self, typ: str, sname: str, body: dict, template_name: str | None) -> str | None:
        where = f"source {typ}.{sname}"
        bindings = self.ref.bindings["required_bindings"]
        iso_storage_seen = False
        for spec in bindings:
            attr = spec["attribute"]
            expected = spec["variable"]
            required = spec.get("required", False)
            matches = self._resolve_attribute(body, attr)
            if not matches:
                if required is True:
                    self.report("T008", f"{where}: {attr} is not set; it must be \"${{var.{expected}}}\" ({spec.get('why', '')})", sname)
                continue
            for display, value in matches:
                ref_name = var_ref(value)
                if attr in ("username", "password", "token") and ref_name is None:
                    self.report("T009", f"{where}: {display} is a literal value; Proxmox API credentials come from the build environment — use \"${{var.{expected}}}\" ({spec.get('why', '')})", display.split("[")[0].split(".")[-1])
                    continue
                if ref_name != expected:
                    self.report("T008", f"{where}: {display} = {inner(value)!r} must be \"${{var.{expected}}}\" ({spec.get('why', '')})", display.split("[")[0].split(".")[-1])
                if required == "one_of_iso_storage":
                    iso_storage_seen = True
        if typ == "proxmox-iso" and not iso_storage_seen:
            self.report("T008", f"{where}: boot_iso.iso_storage_pool (or the deprecated top-level iso_storage_pool) is not set; it must be \"${{var.iso_storage_pool}}\"", sname)

        for spec in self.ref.bindings.get("forbidden_attributes", []):
            attr = spec["attribute"]
            if attr in body:
                if "when_equals" in spec and body[attr] != spec["when_equals"]:
                    continue
                self.report("T009", f"{where}: {attr} must not be set ({spec.get('why', '')})", attr)
        if "template_name" in body:
            if template_name is None or self.resolve_string(body["template_name"]) != template_name:
                self.report("T009", f"{where}: template_name differs from vm_name; Ludus looks the built template up by vm_name, so the two must match (simplest: do not set template_name)", "template_name")

        communicator_raw = body.get("communicator")
        communicator = self.resolve_string(communicator_raw) if communicator_raw is not None else None
        if communicator_raw is None:
            self.report("T010", f"{where}: communicator is not set; Ludus templates must be reachable over ssh (Linux/macOS) or winrm (Windows) for Ansible", sname)
        elif communicator not in self.ref.bindings.get("communicators", ["ssh", "winrm"]):
            self.report("T010", f"{where}: communicator {communicator or communicator_raw!r} is not ssh or winrm; Ansible cannot configure the resulting VMs", "communicator")

        os_attr = body.get("os")
        if os_attr is not None and var_ref(os_attr) != "os" and is_literal_string(os_attr):
            os_var = self.var_default("os")
            if is_literal_string(os_var) and inner(os_var) != inner(os_attr):
                self.report("T010", f"{where}: os = {inner(os_attr)!r} differs from variable \"os\" default {inner(os_var)!r}; Ludus classifies the template from the variable", "os")
        elif os_attr is None:
            self.report("T010", f"{where}: os is not set on the builder; set os = \"${{var.os}}\" so Proxmox gets the right guest type", sname, level="warning")

        self._check_performance(where, body)
        return communicator

    def _resolve_attribute(self, body: dict, attr: str) -> list[tuple[str, Any]]:
        """Resolve 'a[].b' / 'a.b' / 'a' against a source body → [(display, value)]."""
        parts = attr.split(".")
        current: list[tuple[str, dict]] = [("", body)]
        for i, part in enumerate(parts):
            is_last = i == len(parts) - 1
            nxt: list[tuple[str, dict]] = []
            key = part[:-2] if part.endswith("[]") else part
            for prefix, node in current:
                if key not in node:
                    continue
                if is_last:
                    nxt.append((f"{prefix}{key}", node[key]))
                else:
                    for n, blk in enumerate(blocks(node, key)):
                        nxt.append((f"{prefix}{key}[{n}]." if part.endswith("[]") else f"{prefix}{key}.", blk))
            current = nxt
            if not current:
                return []
        return [(display, value) for display, value in current]

    def _check_performance(self, where: str, body: dict) -> None:
        perf = self.ref.bindings.get("performance_recommendations", {})
        checks = [
            ("scsi_controller", perf.get("scsi_controller")),
            ("cpu_type", perf.get("cpu_type")),
        ]
        for attr, wanted in checks:
            if wanted is None:
                continue
            value = self.resolve_string(body.get(attr)) if attr in body else None
            if value != wanted:
                self.report("T015", f"{where}: {attr} = {value!r}; the Ludus docs recommend {wanted!r}", attr if attr in body else None)
        for n, disk in enumerate(blocks(body, "disks")):
            if self.resolve_string(disk.get("type")) != perf.get("disks[].type", "virtio"):
                self.report("T015", f"{where}: disks[{n}].type should be \"virtio\" for best performance", "disks")
            if disk.get("discard") is not True:
                self.report("T015", f"{where}: disks[{n}].discard = true lets Proxmox reclaim space when files are deleted", "disks")
            if disk.get("io_thread") is not True:
                self.report("T015", f"{where}: disks[{n}].io_thread = true gives >15% gains with virtio-scsi-single", "disks")
        for n, nic in enumerate(blocks(body, "network_adapters")):
            if self.resolve_string(nic.get("model")) != perf.get("network_adapters[].model", "virtio"):
                self.report("T015", f"{where}: network_adapters[{n}].model should be \"virtio\" (paravirtualized, much faster than e1000)", "network_adapters")

    # -- T010 (os variable) ---------------------------------------------------------

    def check_os_variable(self, communicator: str | None) -> None:
        os_default = self.var_default("os")
        if "os" not in self.variables:
            self.report("T010", "no `variable \"os\"`: Ludus reads its literal default to classify the template as Windows or Linux (otherwise it guesses from the name). Add it with a Proxmox OS type such as l26 or win11")
            return
        if not is_literal_string(os_default):
            self.report("T010", "variable \"os\" must have a literal string default; Ludus extracts it with a regular expression", 'variable "os"')
            return
        value = inner(os_default)
        allowed = self.ref.bindings.get("proxmox_os_types", [])
        if allowed and value not in allowed:
            self.report("T010", f"variable \"os\" default {value!r} is not a Proxmox OS type ({', '.join(allowed)})", 'variable "os"')
            return
        is_windows = value.startswith(("win", "w2k")) or value in ("wxp", "wvista")
        if communicator == "winrm" and not is_windows:
            self.report("T010", f"variable \"os\" is {value!r} but the communicator is winrm; Ludus would classify the template as Linux and use ssh to configure VMs", 'variable "os"', level="warning")
        if communicator == "ssh" and is_windows:
            self.report("T010", f"variable \"os\" is {value!r} but the communicator is ssh; Ludus would classify the template as Windows and use WinRM to configure VMs", 'variable "os"', level="warning")

    # -- T011 / T017 ---------------------------------------------------------------

    def check_provisioners(self, communicator: str | None) -> None:
        rules = self.ref.bindings.get("ansible_provisioner", {})
        required_env = rules.get("required_env", ["ANSIBLE_HOME=${var.ansible_home}"])
        recommended_env = rules.get("recommended_env_ssh", [])
        forbidden_env = rules.get("must_not_set_env", [])
        for typ, body in self.provisioners():
            if typ != "ansible":
                continue
            env = [inner(e) for e in body.get("ansible_env_vars", []) or [] if isinstance(e, str)]
            env_keys = {e.split("=", 1)[0]: e.split("=", 1)[1] if "=" in e else "" for e in env}
            for item in required_env:
                key, _, wanted = item.partition("=")
                if key not in env_keys:
                    self.report("T011", f"ansible provisioner: ansible_env_vars must include \"{item}\"; everything outside the Ludus install dir is read-only for the build user", "provisioner \"ansible\"")
                elif env_keys[key].strip() != wanted:
                    self.report("T011", f"ansible provisioner: {key} must be {wanted!r} (got {env_keys[key]!r})", f"{key}=")
            if body.get("skip_version_check") is not True:
                self.report("T011", "ansible provisioner: set skip_version_check = true; the Ludus environment variables are not in place when the plugin runs its version check", "provisioner \"ansible\"")
            if body.get("use_proxy") is not False:
                self.report("T017", "ansible provisioner: set use_proxy = false (all Ludus templates do; the Packer SSH proxy adapter is not needed and breaks WinRM)", "provisioner \"ansible\"")
            if communicator == "ssh":
                for item in recommended_env:
                    key, _, wanted = item.partition("=")
                    if key not in env_keys:
                        self.report("T017", f"ansible provisioner: add \"{item}\" to ansible_env_vars so Ansible's temp and control sockets stay under the writable ansible_home", "provisioner \"ansible\"")
            for key in forbidden_env:
                if key in env_keys:
                    self.report("T017", f"ansible provisioner: do not set {key}; Ludus exports it so provisioners find the user's installed roles and collections, and an override hides them", f"{key}=")

    # -- T016 ------------------------------------------------------------------

    def check_required_plugins(self) -> None:
        allowed = self.ref.allowed_plugin_sources
        for pk in self.doc.get("packer", []) or []:
            if not isinstance(pk, dict):
                continue
            for rp in blocks(pk, "required_plugins"):
                for name, body in rp.items():
                    if not isinstance(body, dict):
                        continue
                    src = inner(body.get("source", "")) if body.get("source") is not None else ""
                    if src not in allowed:
                        self.report("T016", f"required_plugins.{label(name)}: source {src!r} is not installed on Ludus servers (PACKER_PLUGIN_PATH ships {', '.join(sorted(allowed)) or 'the Ludus plugin set'}); `packer init` is never run, so the build fails", "required_plugins", level="error")
                    else:
                        self.report("T016", f"required_plugins.{label(name)}: Ludus pre-installs {src} v{allowed[src]} and never runs `packer init`; the block is unnecessary and must stay compatible with that version", "required_plugins", level="info")

    # -- T012 ------------------------------------------------------------------

    def check_file_references(self) -> None:
        refs: list[tuple[str, Any, bool]] = []  # (display, value, allow_glob)
        for typ, sname, body in self.sources:
            if "http_directory" in body:
                refs.append((f"source {typ}.{sname}: http_directory", body["http_directory"], False))
            for key in ("floppy_files", "cd_files"):
                for v in body.get(key, []) or []:
                    refs.append((f"source {typ}.{sname}: {key}", v, True))
            for blk_name in ("additional_iso_files", "boot_iso"):
                for n, blk in enumerate(blocks(body, blk_name)):
                    for v in blk.get("cd_files", []) or []:
                        refs.append((f"source {typ}.{sname}: {blk_name}[{n}].cd_files", v, True))
        for typ, body in self.provisioners():
            if typ == "ansible":
                for key in ("playbook_file", "galaxy_file", "inventory_file"):
                    if key in body:
                        refs.append((f"provisioner ansible: {key}", body[key], False))
            elif typ in ("shell", "powershell", "windows-shell", "shell-local"):
                if "script" in body:
                    refs.append((f"provisioner {typ}: script", body["script"], False))
                for v in body.get("scripts", []) or []:
                    refs.append((f"provisioner {typ}: scripts", v, False))
            elif typ == "file":
                direction = self.resolve_string(body.get("direction")) if "direction" in body else "upload"
                if direction != "download":
                    if "source" in body:
                        refs.append((f"provisioner file: source", body["source"], True))
                    for v in body.get("sources", []) or []:
                        refs.append((f"provisioner file: sources", v, True))
        for display, value, allow_glob in refs:
            resolved = self.resolve_string(value)
            if resolved is None:
                if isinstance(value, str) and "${" in value:
                    continue  # computed path, cannot check statically
                self.report("T012", f"{display}: cannot resolve {value!r}", display.split(":")[-1].strip().split("[")[0])
                continue
            self._check_path(display, resolved, allow_glob)

    def _check_path(self, display: str, p: str, allow_glob: bool) -> None:
        needle = display.split(":")[-1].strip().split("[")[0]
        if os.path.isabs(p):
            self.report("T012", f"{display}: {p!r} is absolute; Ludus copies the template directory to the server, so paths must be relative to it", needle)
            return
        target = (self.tdir / p)
        try:
            target.resolve().relative_to(self.tdir.resolve())
        except ValueError:
            self.report("T012", f"{display}: {p!r} escapes the template directory; `ludus source add` installs each templates/<name>/ directory on its own, so ../ references break on the server", needle)
            return
        if allow_glob and any(ch in p for ch in "*?["):
            if not glob.glob(str(self.tdir / p)):
                self.report("T012", f"{display}: pattern {p!r} matches no files", needle)
            return
        if not target.exists():
            self.report("T012", f"{display}: {p!r} does not exist in the template directory", needle)

    # -- T013 ------------------------------------------------------------------

    def check_windows(self) -> None:
        if not (self.tdir / "Autounattend.xml").is_file():
            present = [p.name for p in self.tdir.iterdir() if p.name.lower() == "autounattend.xml"]
            hint = f" (found {present[0]!r}; the name is case-sensitive)" if present else ""
            self.report("T013", f"Windows template without Autounattend.xml in the template root{hint}; `ludus templates add` expects it there")
        for typ, sname, body in self.proxmox_sources():
            if body.get("winrm_use_ssl") is not True:
                self.report("T013", f"source {typ}.{sname}: set winrm_use_ssl = true (Ludus requires WinRM over HTTPS; every Ludus Windows template builds over it)", "communicator", level="warning")
            if "winrm_username" not in body or "winrm_password" not in body:
                self.report("T013", f"source {typ}.{sname}: winrm_username / winrm_password are not set", "communicator")

    # -- T014 ------------------------------------------------------------------

    def guess_guest_os(self, communicator: str | None) -> str | None:
        os_default = self.var_default("os")
        os_value = inner(os_default) if is_literal_string(os_default) else ""
        if communicator == "winrm" or os_value.startswith(("win", "w2k")) or os_value in ("wxp", "wvista"):
            return "windows"
        haystack_parts = [self.tdir.name]
        for name in ("vm_name", "iso_url", "description", "iso_file"):
            d = self.var_default(name)
            if is_literal_string(d):
                haystack_parts.append(inner(d))
        for typ, sname, body in self.sources:
            for key in ("vm_name", "iso_url", "iso_file", "template_description"):
                if is_literal_string(body.get(key)):
                    haystack_parts.append(inner(body[key]))
            for blk in blocks(body, "boot_iso"):
                for key in ("iso_url", "iso_file"):
                    if is_literal_string(blk.get(key)):
                        haystack_parts.append(inner(blk[key]))
        haystack = " ".join(haystack_parts).lower()
        for needle, group in GUEST_OS_HINTS:
            if needle in haystack:
                return group
        return None

    def check_credentials(self, communicator: str | None) -> None:
        group = self.guess_guest_os(communicator)
        if group is None:
            self.l.report("T014", self.pfile, "could not infer the guest OS family from the template name/ISO, so credentials were not checked against the Ludus group_vars; expected localuser:password unless the OS has its own convention", level="info")
            return
        expected = self.ref.credentials.get("groups", {}).get(group)
        if not expected:
            return
        user_key, pass_key = ("winrm_username", "winrm_password") if group == "windows" else ("ssh_username", "ssh_password")
        for typ, sname, body in self.proxmox_sources():
            user = self.resolve_string(body.get(user_key)) if user_key in body else None
            password = self.resolve_string(body.get(pass_key)) if pass_key in body else None
            if user is None or password is None:
                continue
            if (user, password) != (expected["user"], expected["password"]):
                self.report("T014", f"source {typ}.{sname}: credentials {user}:{password} differ from what Ludus uses for {group} guests ({expected['user']}:{expected['password']} from range-management/group_vars/{group}.yml); VMs cloned from this template cannot be configured by `ludus range deploy` unless the range uses certificate auth", user_key)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def load_config(root: Path, explicit: str | None) -> dict:
    path = Path(explicit) if explicit else root / ".ludus-lint.yml"
    if not path.exists():
        if explicit:
            raise SystemExit(f"ludus_source_lint: config {path} not found")
        return {}
    data = load_yaml(path) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"ludus_source_lint: {path} must be a mapping")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=".", help="source repository root (default: current directory)")
    parser.add_argument("--reference-dir", default=None, help="directory with the vendored Ludus reference data (default: <root>/ludus-reference)")
    parser.add_argument("--config", default=None, help="lint configuration file (default: <root>/.ludus-lint.yml when present)")
    parser.add_argument("--format", choices=("text", "github", "json"), default="text", help="output format; github adds workflow annotations")
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    parser.add_argument("--quiet", action="store_true", help="only print errors and warnings")
    parser.add_argument("--list-rules", action="store_true", help="print the rule catalogue and exit")
    args = parser.parse_args(argv)

    if args.list_rules:
        for rule, (level, text) in RULES.items():
            print(f"{rule}  {level:7}  {text}")
        return 0

    root = Path(args.root).resolve()
    if not root.is_dir():
        raise SystemExit(f"ludus_source_lint: {root} is not a directory")
    ref_dir = Path(args.reference_dir).resolve() if args.reference_dir else root / "ludus-reference"
    reference = Reference(ref_dir)
    config = load_config(root, args.config)
    linter = Linter(root, reference, config)
    findings = linter.run()

    if args.format == "json":
        print(json.dumps([dataclasses.asdict(f) for f in findings], indent=2))
    else:
        for f in findings:
            if args.quiet and f.level == "info":
                continue
            print(f.as_text())
            if args.format == "github":
                print(f.as_github())
        counts = linter.counts()
        print(f"\nludus_source_lint: {counts['error']} error(s), {counts['warning']} warning(s), {counts['info']} info in {rel(Path.cwd(), root) or '.'} "
              f"(templates: {len(linter.template_names)}, blueprints: {len(linter._blueprint_dirs())}, roles: {len([r for r in linter.role_identities if '.' not in r])}, collections: {len(linter.collection_fqcns)})")
    counts = linter.counts()
    if counts["error"] or (args.strict and counts["warning"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
