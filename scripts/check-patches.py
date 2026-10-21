#!/usr/bin/env python3
"""Replay the cluster_ludus_patches manifest against pinned upstream Ludus.
`get_sybers.cluster.cluster_ludus_patches` re-applies our local edits to stock
Ludus files after `ludus-server --update` reverts them. Every patch is an exact
string swap, which means the manifest can rot in ways that are invisible until a
real server update: upstream renames a task and the `stock` text stops matching,
or two patches to one file collide. This replays the whole manifest, in order,
against the `badsectorlabs/ludus` submodule — no Ludus server needed.
Five failure modes are checked, and the last three are the ones that hurt:
  1. `stock` not present in the pinned upstream file. `apply_one.yml` asserts on
     this at run time, so the role aborts — and because patches share files and
     run in order, an early miss means NONE of the later ones apply either.
  2. `stock` present more than once. `replace()` takes no occurrence limit, so
     the patch silently edits every match.
  3. A marker already present in pristine upstream — the patch would always
     report "already applied" and never run.
  4. A marker that another, earlier patch's `patched` text introduces. The
     second patch then no-ops, and the role's own final verification still
     passes, because the marker IS on disk — put there by the wrong patch. This
     is the "green but never executed" shape the role exists to prevent, and it
     had gone undetected in the manifest for two patches.
  5. A patch whose `stock` is destroyed by an earlier patch to the same file.
Exits non-zero on any of them.
    python3 scripts/check-patches.py
    python3 scripts/check-patches.py -v
The pinned upstream tree it replays against comes from scripts/gates.yml
(patches.upstream — a local clone of gitlab.com/badsectorlabs/ludus checked
out at the recorded pin).
"""
from __future__ import annotations
import argparse
import pathlib
import re
import sys
try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: python3 -m pip install pyyaml")
REPO = pathlib.Path(__file__).resolve().parents[1]
ROLE = REPO / "ansible/collections/get_sybers.cluster/roles/cluster_ludus_patches"
VARS = ROLE / "vars/main.yml"
def _gates(section: str) -> dict:
    """This repo's scope for the mirrored checkers, from scripts/gates.yml.
    The scripts/*.py family is byte-identical across the source repos; the
    per-repo piece is gates.yml alone. Missing file or section means the
    script's built-in defaults apply.
    """
    p = pathlib.Path(__file__).resolve().parent / "gates.yml"
    if not p.is_file():
        return {}
    try:
        return (yaml.safe_load(p.read_text()) or {}).get(section) or {}
    except Exception as exc:
        sys.exit(f"FAIL: unreadable scripts/gates.yml: {exc}")
GATES = _gates("patches")
UPSTREAM = (
    (REPO / GATES["upstream"]) if GATES.get("upstream") else next(
        (c for c in (REPO / ".dev/ansible/lib/ludus/ludus-server",
                     REPO / ".Non-Distribute/dev/ansible/lib/ludus/ludus-server")
         if c.is_dir()),
        REPO / ".dev/ansible/lib/ludus/ludus-server",
    )
)
class ManifestLoader(yaml.SafeLoader):
    """The manifest tags every payload !unsafe so Ansible does not template it."""
ManifestLoader.add_constructor(
    "!unsafe", lambda loader, node: loader.construct_scalar(node)
)
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    if GATES.get("applicable") is False:
        print("NOT-APPLICABLE (scripts/gates.yml): "
              f"{GATES.get('reason', 'no reason recorded')}")
        return 0
    if not UPSTREAM.exists():
        sys.exit(
            f"pinned upstream tree not found at {UPSTREAM}\n"
            "  (set patches.upstream in scripts/gates.yml to a local clone of "
            "gitlab.com/badsectorlabs/ludus at the recorded pin)"
        )
    manifest = yaml.load(VARS.read_text(), Loader=ManifestLoader)
    patches = manifest["ludus_patches"]
    reorder = manifest["ludus_patch_reorder"]
    working: dict[str, str] = {}
    pristine: dict[str, str] = {}
    marker_owner: dict[str, str] = {}
    problems: list[str] = []
    def load(rel: str) -> str | None:
        if rel not in working:
            path = UPSTREAM / rel
            if not path.exists():
                return None
            pristine[rel] = working[rel] = path.read_text()
        return working[rel]
    print(f"upstream: {UPSTREAM}")
    print(f"manifest: {VARS.relative_to(REPO)}\n")
    for patch in patches:
        pid, rel = patch["id"], patch["file"]
        content = load(rel)
        label = f"  {pid:<30} {rel:<52}"
        if content is None:
            print(f"{label} MISSING upstream file")
            problems.append(f"{pid}: {rel} does not exist in the pinned upstream")
            continue
        marker, stock, patched = patch["marker"], patch["stock"], patch["patched"]
        if marker in content:
            owner = marker_owner.get(marker)
            if owner:
                print(f"{label} MARKER COLLISION with {owner}")
                problems.append(
                    f"{pid}: its marker is already written by {owner}, so this patch "
                    f"would report 'already applied' and never run — while the role's "
                    f"final verification still passes on {owner}'s text"
                )
            else:
                print(f"{label} marker present in pristine upstream")
                problems.append(
                    f"{pid}: marker {marker!r} is already in stock upstream, so the "
                    f"patch can never apply"
                )
            continue
        occurrences = content.count(stock)
        if occurrences == 0:
            in_pristine = pristine[rel].count(stock)
            print(f"{label} STOCK NOT FOUND")
            problems.append(
                f"{pid}: `stock` does not appear in {rel}. "
                + (
                    "It was present before the earlier patches to this file ran, so an "
                    "earlier patch destroyed it — reorder or re-derive."
                    if in_pristine
                    else "Upstream text has changed; re-derive this patch against the "
                    "pinned tree rather than forcing it."
                )
            )
            continue
        if occurrences > 1:
            print(f"{label} STOCK MATCHES {occurrences}x")
            problems.append(
                f"{pid}: `stock` occurs {occurrences} times in {rel}; replace() has no "
                f"occurrence limit, so the patch would edit all of them. Widen the "
                f"match until it is unique."
            )
            continue
        new = content.replace(stock, patched)
        if new == content:
            print(f"{label} REPLACE WAS A NO-OP")
            problems.append(f"{pid}: `stock` and `patched` are identical.")
            continue
        if marker not in new:
            print(f"{label} MARKER ABSENT AFTER PATCH")
            problems.append(
                f"{pid}: after substituting, marker {marker!r} is still not in the "
                f"file — the patch would apply and then fail its own verification."
            )
            continue
        working[rel] = new
        marker_owner[marker] = pid
        delta = f" +{len(new) - len(content)}B" if args.verbose else ""
        print(f"{label} ok{delta}")
    rel = reorder["file"]
    content = load(rel)
    print()
    label = f"  {reorder['id']:<30} {rel:<52}"
    if content is None:
        print(f"{label} MISSING upstream file")
        problems.append(f"{reorder['id']}: {rel} does not exist upstream")
    else:
        start = content.find(reorder["section_start"])
        end = content.find(reorder["section_end"])
        anchor = content.find(reorder["anchor"])
        if min(start, end, anchor) < 0:
            print(f"{label} LANDMARK MISSING")
            problems.append(
                f"{reorder['id']}: landmark missing (start={start}, end={end}, "
                f"anchor={anchor}). Re-derive against the current stock file."
            )
        elif start < anchor:
            print(f"{label} already ordered — no-op")
        else:
            section = content[start:end]
            if end <= start or reorder["anchor"] in section:
                print(f"{label} SLICE SWALLOWS THE ANCHOR")
                problems.append(
                    f"{reorder['id']}: the slice [{start}:{end}] contains the anchor. "
                    f"The role refuses this, but it means the landmarks no longer "
                    f"bound the section — re-derive them."
                )
            else:
                out = (content[:start] + content[end:]).replace(
                    reorder["anchor"], section + "\n" + reorder["anchor"]
                )
                if len(out) < len(content):
                    print(f"{label} REORDER SHRANK THE FILE")
                    problems.append(
                        f"{reorder['id']}: reorder lost "
                        f"{len(content) - len(out)} bytes."
                    )
                else:
                    delta = (
                        f" {len(content)}B -> {len(out)}B" if args.verbose else ""
                    )
                    print(f"{label} ok{delta}")
    print()
    for task_file in sorted((ROLE / "tasks").glob("*.yml")):
        text = task_file.read_text()
        label = f"  {'jinja-escape':<30} {task_file.name:<52}"
        offenders = [
            expr for expr in re.findall(r"\{\{.*?\}\}", text, re.DOTALL)
            if "\\n" in expr
        ]
        if offenders:
            print(f"{label} LITERAL \\n INSIDE A JINJA EXPRESSION")
            problems.append(
                f"{task_file.name}: a Jinja expression contains a literal "
                f"backslash-n, which Jinja emits verbatim rather than as a "
                f"newline. Resolve the newline in YAML instead "
                f"(e.g. set_fact: _lp_nl: \"\\n\"). Offending expression: "
                f"{offenders[0].strip()[:80]}"
            )
        else:
            print(f"{label} ok")
    print()
    for rel, content in sorted(working.items()):
        if rel.endswith(".j2"):
            print(f"  {'parse':<30} {rel:<52} jinja — n/a")
            continue
        try:
            doc = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            print(f"  {'parse':<30} {rel:<52} INVALID YAML")
            problems.append(f"{rel}: patched result does not parse — {exc}")
            continue
        count = len(doc) if isinstance(doc, list) else 1
        print(f"  {'parse':<30} {rel:<52} ok ({count} top-level)")
    files = sorted({p["file"] for p in patches} | {reorder["file"]})
    print(
        f"\n  {len(patches)} text patches + 1 reorder across {len(files)} stock files"
    )
    if problems:
        print(f"\nFAIL — {len(problems)} problem(s)\n")
        for n, text in enumerate(problems, 1):
            print(f"  {n}. {text}")
        return 1
    print("\nPASS — every patch matches pinned upstream exactly once, every marker")
    print("       is unique to its own patch, and the reorder is well-formed")
    return 0
if __name__ == "__main__":
    sys.exit(main())
