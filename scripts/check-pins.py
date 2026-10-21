#!/usr/bin/env python3
"""check-pins.py — §2/§13 pin discipline.
Asserts, exit non-zero on any failure:
  1. every galaxy.yml dependency has an exact pin in requirements.yml;
  2. every requirements.yml collection version is an exact X.Y.Z
     (never a range, ``:latest``, or a branch); a ``type: git`` entry is
     exact when its version is a 40-hex commit SHA (a tag or branch is not);
  3. every pin satisfies its galaxy.yml bound (>=floor,<ceiling);
  4. no version literal lives outside requirements.yml / galaxy.yml
     (scripts and CI read the pins, they do not carry their own copy).
Byte-identical across the Get-Sybers source repos; it reads galaxy.yml and
requirements.yml at the repo root, so there is no per-repo piece. A repo with
no galaxy.yml (a Ludus source shipping only standalone task-roles) has no
bounds to check: (1) and (3) are skipped and reported as such, (2) and (4)
still apply.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path
import yaml
REPO = Path(__file__).resolve().parent.parent
EXACT = re.compile(r"^\d+\.\d+\.\d+$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
BOUND = re.compile(r">=\s*(\d+\.\d+\.\d+)\s*,\s*<\s*(\d+\.\d+\.\d+)\s*$")
def _load(path: Path) -> dict:
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text()) or {}
def _ver_tuple(v: str) -> tuple[int, int, int]:
    return tuple(int(x) for x in v.split("."))
def main() -> int:
    errors: list[str] = []
    has_galaxy = (REPO / "galaxy.yml").is_file()
    galaxy = _load(REPO / "galaxy.yml")
    reqs = _load(REPO / "requirements.yml")
    deps = (galaxy.get("dependencies") or {})
    pins = {}
    git_pins = {}
    for entry in (reqs.get("collections") or []):
        if isinstance(entry, dict) and "name" in entry:
            if entry.get("type") == "git":
                git_pins[entry["name"]] = entry.get("version")
            else:
                pins[entry["name"]] = entry.get("version")
        elif isinstance(entry, str):
            errors.append(f"requirements.yml: '{entry}' has no explicit version")
    for name, ver in pins.items():
        if not isinstance(ver, str) or not EXACT.match(ver):
            errors.append(f"requirements.yml: {name} pin '{ver}' is not an exact X.Y.Z")
    # A collection installed from git has no X.Y.Z to pin: the exact pin is the
    # commit SHA. A tag or branch name moves, so it is refused. Git sources carry
    # no Galaxy name, so they take no part in the galaxy.yml bound check below.
    for name, ver in git_pins.items():
        if not isinstance(ver, str) or not GIT_SHA.match(ver):
            errors.append(f"requirements.yml: git source {name} pin '{ver}' is not a 40-hex commit SHA")
    if has_galaxy:
        for name, bound in deps.items():
            if name not in pins:
                errors.append(f"galaxy.yml dependency '{name}' has no requirements.yml pin")
                continue
            ver = pins[name]
            m = BOUND.match(str(bound))
            if not m:
                errors.append(f"galaxy.yml: '{name}' bound '{bound}' is not >=x.y.z,<next-major")
                continue
            if isinstance(ver, str) and EXACT.match(ver):
                floor, ceil = _ver_tuple(m.group(1)), _ver_tuple(m.group(2))
                if not (floor <= _ver_tuple(ver) < ceil):
                    errors.append(f"{name}: pin {ver} outside bound {bound}")
        for name in pins:
            if name not in deps:
                errors.append(f"requirements.yml: '{name}' is pinned but not a galaxy.yml dependency")
    literal = re.compile(r"(ansible\.\w+|community\.\w+|ansible-core)\s*[:=><]=?\s*\d")
    ci_files = [REPO / ".gitlab-ci.yml"]
    ci_files += sorted((REPO / ".github" / "workflows").glob("*.y*ml"))
    for f in ci_files:
        if not f.is_file():
            continue
        rel = f.relative_to(REPO).as_posix()
        for i, line in enumerate(f.read_text().splitlines(), 1):
            s = line.strip()
            if s.startswith("#"):
                continue
            if literal.search(line) and "requirements.yml" not in line:
                errors.append(f"{rel}:{i}: version literal outside requirements.yml: {s}")
    if errors:
        print("PIN CHECK: FAIL")
        for e in errors:
            print(f"  - {e}")
        return 1
    scope = f"{len(deps)} declared" if has_galaxy else "no galaxy.yml — bound check skipped"
    git_note = f", {len(git_pins)} git source(s) pinned to a commit" if git_pins else ""
    print(f"PIN CHECK: PASS ({len(pins)} pinned{git_note}, {scope})")
    return 0
if __name__ == "__main__":
    sys.exit(main())
