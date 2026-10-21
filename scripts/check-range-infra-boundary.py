#!/usr/bin/env python3
"""check-range-infra-boundary.py — no range surface may drive the infra LXC
build chain. (Operator ruling, issues
Why this exists: a blueprint play (campaign/ansible/ghost9-template.yml, now
removed) baked a RANGE asset — the Ghosts LXC — through the get_sybers.infra
build machinery: infra_bridge -> infra_firewall -> infra_lxc_template ->
infra_provision_window. That path hands a range build the infra tier's
host-side powers (bridges, firewall chains, PVE operations), and in practice
it drove an unauthorized PVE privilege-escalation attempt. The ruling: a range
LXC is built on a plain Debian base template with NO infra roles and NO PVE
API credentials. A rule with no detector is a suggestion, so this is the
detector.
What fails: any non-comment reference to an infra build-chain identifier —
    infra_lxc_template   infra_bridge   infra_firewall   infra_provision_window
(and anything derived from them: their variables, their host group
infra_lxc_template_build) — inside a RANGE surface:
    blueprints/                                  every blueprint, all files
    ansible/roles/                               the shared task-roles
    ansible/collections/get_sybers.range/        the range galaxy
    templates/                                   packer templates
The infra galaxy itself (ansible/collections/get_sybers.infra/) is the ONLY
legitimate home of those roles and is not scanned. Markdown is not scanned:
docs may record the history of the ban, and a guard that fires on its own
documentation teaches people to delete the documentation.
The scan is line-based so every hit is reported file:line. Whole-line comments
(`
execute a role, and the ban itself must be citable in-line. Scanning ZERO
files, or an unreadable file, is a FAILURE, not a pass: a gate that could not
look must say so (the lesson of issue
Exit 0: no range surface references the infra build chain.
Exit 1: at least one hit, or the scan could not actually scan.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent
def _gates(section: str) -> dict:
    """This repo's scope for the mirrored checkers, from scripts/gates.yml.
    The scripts/*.py family is byte-identical across the source repos; the
    per-repo piece is gates.yml alone. Missing file or section means the
    script's built-in defaults apply.
    """
    p = Path(__file__).resolve().parent / "gates.yml"
    if not p.is_file():
        return {}
    try:
        import yaml
    except ImportError:
        sys.exit("FAIL: PyYAML is required to read scripts/gates.yml "
                 "(python3 -m pip install pyyaml)")
    try:
        return (yaml.safe_load(p.read_text()) or {}).get(section) or {}
    except Exception as exc:
        sys.exit(f"FAIL: unreadable scripts/gates.yml: {exc}")
GATES = _gates("boundary")
PATTERN = re.compile(r"\binfra_(?:lxc_template|bridge|firewall|provision_window)\w*")
SCAN_TREES = tuple(GATES.get("scan_trees") or (
    "blueprints",
    "ansible/roles",
    "ansible/collections/get_sybers.range",
    "templates",
))
SCAN_SUFFIXES = {".yml", ".yaml", ".j2", ".cfg", ".ini", ".sh", ".py", ".hcl", ".json"}
TRAILING_COMMENT = re.compile(r"\s#.*$")
def scannable(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SCAN_SUFFIXES
def strip_comment(line: str) -> str:
    if line.lstrip().startswith("#"):
        return ""
    return TRAILING_COMMENT.sub("", line)
def main() -> int:
    if GATES.get("applicable") is False:
        print("NOT-APPLICABLE (scripts/gates.yml): "
              f"{GATES.get('reason', 'no reason recorded')}")
        return 0
    hits: list[tuple[str, int, str]] = []
    unreadable: list[str] = []
    scanned = 0
    for tree in SCAN_TREES:
        root = REPO_ROOT / tree
        if not root.is_dir():
            print(f"SKIP: scan tree not in this repo: {tree}/")
            continue
        for path in sorted(p for p in root.rglob("*") if scannable(p)):
            rel = path.relative_to(REPO_ROOT)
            try:
                text = path.read_text(encoding="utf-8", errors="strict")
            except (OSError, UnicodeDecodeError) as exc:
                unreadable.append(f"{rel}: {exc}")
                continue
            scanned += 1
            for lineno, line in enumerate(text.splitlines(), 1):
                m = PATTERN.search(strip_comment(line))
                if m:
                    hits.append((str(rel), lineno, m.group(0)))
    print(f"range/infra boundary: scanned {scanned} file(s) under "
          f"{', '.join(t + '/' for t in SCAN_TREES)}")
    if scanned == 0:
        print("FAIL: scanned nothing — a gate that could not look must not pass")
        return 1
    if unreadable:
        print(f"\nFAIL: {len(unreadable)} file(s) could not be read — not checked is not passed:")
        for u in unreadable:
            print(f"  {u}")
        return 1
    if hits:
        print(f"\nFAIL: {len(hits)} reference(s) to the infra LXC build chain in range surfaces.")
        print("A range asset is never built through get_sybers.infra (issues #219/#234):\n")
        for rel, lineno, ident in hits:
            print(f"  {rel}:{lineno}   {ident}")
        print("\nBuild range LXCs on a plain Debian base with no infra roles and no PVE")
        print("API credentials. If this is genuinely infra-tier work, it belongs in")
        print("ansible/collections/get_sybers.infra/, not here.")
        return 1
    print("OK: no range surface references the infra build chain.")
    return 0
if __name__ == "__main__":
    sys.exit(main())
