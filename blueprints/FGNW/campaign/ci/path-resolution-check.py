#!/usr/bin/env python3
"""ci/path-resolution-check.py — resolve every literal path the campaign claims,
against the SOURCE layout (issue
Why this exists: the orchestrator derives its layout (bp_dir/ad_dir/ansible_dir)
from playbook_dir, the phase files reference files through those vars, and the
standalone campaign playbooks derive their own roots the same way
(FGNW-facts-infra.yml's `__src_root: playbook_dir | dirname x4`). Three shipped
defects (F1, F5, N2) were all of one class — a path built from those vars that
resolved to NOTHING on a real `ludus source add` checkout — and nothing failed
until mid-deploy on the host. N2 specifically was a dirname-depth bug in the
fact gatherer. `ansible-playbook --syntax-check` cannot catch any of this:
include_tasks, vars_files paths and command argv resolve at RUN time.
What it checks, in four groups — each group must find at least one claim, or the
run FAILS (a gate that matched nothing is not a gate; the house standard):
  1. LAYOUT   deploy.yml derives the layout vars; this re-derives them with
              playbook_dir = the campaign dir and asserts every one of them
              renders to a literal. Every standalone
              playbook under campaign/ansible/ additionally gets its OWN
              context: playbook_dir = campaign/ansible plus every var of its
              own that renders to a literal (dirname chains included) — that is
              what makes `{{ __src_root }}/templates/` a checkable claim and
              would have caught the N2 depth bug.
  2. INCLUDES Every `include_tasks:` value resolves next to the including file
              or under the campaign dir, the two places Ansible will look.
  3. RENDERED Every path-like chunk referencing a resolvable var is rendered.
              `{{ __v.<key> }}` is expanded over EVERY variant in __variant_map,
              so a variant-only breakage (the F5 class) fails even though no
              single deploy exercises all variants. users_dir is a server path,
              so its collection/role prefixes are translated back to this
              source tree (.ansible/collections/ansible_collections/
              get_sybers/<c>/ → ansible/collections/get_sybers.<c>/) — the
              mapping that would have caught the nexus-setup.yml repoint (F5).
              A fully-rendered path is a claim ONLY if it lands inside this
              source tree: server-runtime paths (/opt/ludus/..., harvest
              output dirs) are skipped and counted — CI has no server to stat.
              Paths naming runtime artifacts (*.bak) only need their parent
              directory to exist (the N2 dirname-depth class).
  4. BARE     A bare `<name>.yml` in a phase file or campaign playbook is a
              playbook run with chdir: {{ ansible_dir }}, a task file, a range
              config, or an AD data file. Each must exist under one of the
              campaign's known bases (or beside the referencing file). This
              includes .yml literals inside Jinja EXPRESSIONS (phase4b builds
              its list with product(['FGNW-exchange.yml', ...]) and
              facts-infra defaults with default('range-config.yml') — both
              invisible to any YAML walk of plain lists).
Anything the renderer cannot fully resolve (runtime facts, __tmp_* paths, loop
vars with no literal list) is SKIPPED AND COUNTED, and every skip is printed
with --verbose: a silent skip pile would rot into exactly the blind spot this
script exists to remove.
Exit 0 all claims resolve; exit 1 any claim fails, or any group matched nothing.
"""
from __future__ import annotations
import argparse
import os
import re
import sys
from pathlib import Path
try:
    import yaml
except ImportError:
    print("FAIL: pyyaml is not installed (pip install pyyaml)")
    sys.exit(1)
CAMPAIGN = Path(__file__).resolve().parent.parent
SRC_ROOT = CAMPAIGN.parent.parent.parent
ORCHESTRATOR = "deploy.yml"
TASK_DIR = CAMPAIGN / "deploy-tasks"
ANSIBLE_DIR = CAMPAIGN / "ansible"
LAYOUT_KEYS = ("bp_dir", "ludus_root", "ad_dir", "ansible_dir", "ludus_user", "users_dir")
TOKEN_RE = re.compile(r"\{\{ (\w+)((?: \| (?:dirname|basename))*) \}\}")
VARIANT_RE = re.compile(r"\{\{ __v\.(\w+)(?: \| (dirname|basename))? \}\}")
BARE_YML_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.ya?ml$")
QUOTED_YML_RE = re.compile(r"'([A-Za-z0-9][A-Za-z0-9._-]*\.ya?ml)'")
FILTERS = {"dirname": os.path.dirname, "basename": os.path.basename, None: lambda s: s}
RUNTIME_SUBTREES = ("facts-local",)
def apply_chain(value: str, chain: str) -> str:
    for f in re.findall(r"dirname|basename", chain or ""):
        value = FILTERS[f](value)
    return value
def render(text: str, ctx: dict) -> str:
    def sub(m):
        name, chain = m.group(1), m.group(2)
        if name in ctx and isinstance(ctx[name], str):
            return apply_chain(ctx[name], chain)
        return m.group(0)
    return TOKEN_RE.sub(sub, text)
def extract_path_chunks(s: str) -> list[str]:
    """Pull the path-like substrings out of a string that may be prose.
    Assert messages MENTION paths mid-sentence ("{{ ad_dir }}/data/config.json is
    missing. Restore it…"); treating the whole string as one path fails on the
    prose around it. Protect each `{{ … }}` token, split on whitespace, keep the
    runs that contain a token, strip sentence punctuation, and restore."""
    protected = re.sub(r"\{\{ ([^}]+?) \}\}",
                       lambda m: "\x00" + m.group(1).replace(" ", "\x01") + "\x02", s)
    chunks = []
    for run in re.findall(r"\S+", protected):
        if "\x00" not in run:
            continue
        run = run.strip("'\"()[]{},;:").rstrip(".")
        chunks.append(run.replace("\x00", "{{ ").replace("\x02", " }}").replace("\x01", " "))
    return chunks
def load(path: Path):
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)
def walk_strings(node, keypath=()):
    """Yield (keypath, string) for every scalar string in a YAML document."""
    if isinstance(node, str):
        yield keypath, node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from walk_strings(v, keypath + (str(k),))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_strings(v, keypath + (str(i),))
class Report:
    def __init__(self, verbose: bool):
        self.failures: list[str] = []
        self.checked = 0
        self.skipped: list[str] = []
        self.verbose = verbose
    def ok(self, what: str):
        self.checked += 1
        if self.verbose:
            print(f"  ok    {what}")
    def fail(self, what: str, why: str):
        self.failures.append(what)
        print(f"  FAIL  {what}\n        {why}")
    def skip(self, what: str):
        self.skipped.append(what)
        if self.verbose:
            print(f"  skip  {what}")
def collect_vars(doc) -> dict:
    """Merge the vars blocks of every play in a playbook document."""
    merged = {}
    if isinstance(doc, list):
        for play in doc:
            if isinstance(play, dict):
                merged.update(play.get("vars") or {})
    return merged
def fixpoint_ctx(vars_block: dict, seed: dict) -> dict:
    """Resolve every var that renders to a literal from the seed, to a fixpoint.
    This is what turns `__src_root: {{ playbook_dir | dirname x4 }}` into a
    checkable absolute path. Vars needing runtime facts never resolve and are
    simply absent from the context."""
    ctx = dict(seed)
    changed = True
    while changed:
        changed = False
        for key, val in vars_block.items():
            if key in ctx or not isinstance(val, str):
                continue
            rendered = render(val, ctx)
            if "{{" not in rendered:
                ctx[key] = rendered
                changed = True
    return ctx
def derive_layout(rep: Report) -> dict:
    """Group 1 — re-derive the layout from the orchestrator."""
    print("[1/4] layout vars")
    name = ORCHESTRATOR
    vars_block = collect_vars(load(CAMPAIGN / name))
    ctx = {"playbook_dir": str(CAMPAIGN)}
    for key in LAYOUT_KEYS:
        if key not in vars_block:
            rep.fail(f"{name}: {key}", "layout var missing from the orchestrator's vars")
            continue
        val = render(str(vars_block[key]), ctx)
        if "{{" in val:
            rep.fail(f"{name}: {key}", f"did not fully render: {val!r}")
            continue
        ctx[key] = val
        rep.ok(f"{key} = {val}")
    ctx["__variant_map"] = vars_block.get("__variant_map") or {}
    if not ctx["__variant_map"]:
        rep.fail("__variant_map", "empty or missing — variant expansion has nothing to expand")
    return ctx
def users_dir_to_source(path: str, layout: dict) -> str | None:
    """Map a server-side users_dir path back to this source tree, or None if it is
    runtime state with no source counterpart."""
    prefix = layout["users_dir"] + "/.ansible/collections/ansible_collections/get_sybers/"
    if path.startswith(prefix):
        coll, _, rest = path[len(prefix):].partition("/")
        coll_root = SRC_ROOT / "ansible" / "collections" / f"get_sybers.{coll}"
        if not coll_root.is_dir():
            # An external get_sybers collection (scripts/gates.yml
            # closure.external_namespaces) that the server installs from its own
            # source; it has no counterpart in this tree.
            return None
        return str(coll_root / rest)
    roles_prefix = layout["users_dir"] + "/.ansible/roles"
    if path == roles_prefix or path.startswith(roles_prefix + "/"):
        return str(SRC_ROOT / "ansible" / "roles") + path[len(roles_prefix):]
    return None
def in_source_tree(path: str) -> bool:
    try:
        Path(path).resolve().relative_to(SRC_ROOT.resolve())
        return True
    except ValueError:
        return False
def check_includes(files: dict[Path, dict], rep: Report):
    """Group 2 — include_tasks targets."""
    print("\n[2/4] include_tasks targets")
    found = 0
    for path, entry in files.items():
        for keypath, s in walk_strings(entry["doc"]):
            if not keypath or "include_tasks" not in keypath[-1]:
                continue
            found += 1
            if "{{" in s:
                rep.skip(f"{path.name}: include_tasks {s!r} (templated)")
                continue
            candidates = [path.parent / s, CAMPAIGN / s]
            if any(c.is_file() for c in candidates):
                rep.ok(f"{path.name}: include_tasks {s}")
            else:
                rep.fail(f"{path.name}: include_tasks {s}",
                         "not found next to the including file nor under the campaign dir: "
                         + ", ".join(str(c) for c in candidates))
    if not found:
        rep.fail("include_tasks sweep", "matched no include_tasks at all — the check is broken")
def expand_variants(chunk: str, variant_map: dict) -> list[tuple[str, str]]:
    if not VARIANT_RE.search(chunk) or not variant_map:
        return [("", chunk)]
    out = []
    for vn, vv in variant_map.items():
        out.append((f" [{vn}]", VARIANT_RE.sub(
            lambda m: FILTERS[m.group(2)](str(vv.get(m.group(1), m.group(0)))), chunk)))
    return out
def check_rendered(files: dict[Path, dict], layout: dict, rep: Report):
    """Group 3 — path chunks referencing resolvable vars, per-file context."""
    print("\n[3/4] derived paths (per-file context, variants expanded)")
    found = 0
    seen = set()
    for path, entry in files.items():
        ctx = entry["ctx"]
        gate = re.compile(r"\{\{ (?:%s)\b" % "|".join(re.escape(k) for k in ctx
                                                      if isinstance(ctx[k], str)))
        for _, s in walk_strings(entry["doc"]):
            if "{{" not in s or not gate.search(s):
                continue
            for chunk in extract_path_chunks(s):
                if not gate.search(chunk):
                    continue
                for tag, expanded in expand_variants(chunk, layout["__variant_map"]):
                    rendered = render(expanded, ctx)
                    claim = f"{path.name}: {chunk}{tag}"
                    if claim in seen:
                        continue
                    seen.add(claim)
                    found += 1
                    if "{{" in rendered:
                        rep.skip(f"{claim} -> {rendered!r} (runtime vars remain)")
                        continue
                    if not rendered.startswith("/"):
                        rep.skip(f"{claim} (renders to a non-path value)")
                        continue
                    target = os.path.normpath(rendered)
                    if any(target.startswith(str(CAMPAIGN / d) + "/") or
                           target == str(CAMPAIGN / d) for d in RUNTIME_SUBTREES):
                        rep.skip(f"{claim} (runtime harvest output, created by the play)")
                        continue
                    if rendered.startswith(layout["users_dir"]):
                        mapped = users_dir_to_source(rendered, layout)
                        if mapped is None:
                            rep.skip(f"{claim} (runtime state under users_dir)")
                            continue
                        target = mapped
                    if not in_source_tree(target):
                        rep.skip(f"{claim} -> {target} (outside the source tree — server runtime)")
                        continue
                    if rendered.endswith(".bak"):
                        if Path(target).parent.is_dir():
                            rep.ok(f"{claim} (parent dir of runtime artifact)")
                        else:
                            rep.fail(claim, f"parent directory missing: {Path(target).parent}")
                        continue
                    if Path(target).exists():
                        rep.ok(f"{claim} -> {target}")
                    else:
                        rep.fail(claim, f"resolved to a nonexistent path: {target}")
    if not found:
        rep.fail("derived-path sweep", "matched no derived paths at all — the check is broken")
def check_bare(files: dict[Path, dict], layout: dict, rep: Report):
    """Group 4 — bare *.yml names, including literals inside Jinja expressions."""
    print("\n[4/4] bare playbook/task-file names")
    bases = [Path(layout["ansible_dir"]), TASK_DIR, Path(layout["bp_dir"]),
             Path(layout["ad_dir"]) / "data", Path(layout["ad_dir"]) / "providers" / "ludus"]
    found = 0
    seen = set()
    for path, entry in files.items():
        names = set()
        for keypath, s in walk_strings(entry["doc"]):
            if keypath and "include_tasks" in keypath[-1]:
                continue
            if keypath and keypath[-1] == "tasks_from":
                continue
            if BARE_YML_RE.match(s):
                names.add(s)
            elif "{{" in s:
                names.update(QUOTED_YML_RE.findall(s))
        for name in sorted(names):
            if name == ORCHESTRATOR:
                continue
            claim = f"{path.name}: {name}"
            if claim in seen:
                continue
            seen.add(claim)
            found += 1
            search = bases + [path.parent]
            hits = [b / name for b in search if (b / name).is_file()]
            if hits:
                rep.ok(f"{claim} -> {hits[0]}")
            else:
                rep.fail(claim, "not found under any known base: "
                         + ", ".join(str(b) for b in search))
    if not found:
        rep.fail("bare-name sweep", "matched no bare .yml names at all — the check is broken")
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--verbose", action="store_true", help="print every ok/skip, not just failures")
    args = ap.parse_args()
    rep = Report(args.verbose)
    if not (SRC_ROOT / "source.yml").is_file():
        print(f"FAIL: {SRC_ROOT} does not look like the source root (no source.yml) — "
              "this script must live at <src>/blueprints/<bp>/campaign/ci/")
        return 1
    print(f"path-resolution-check: campaign={CAMPAIGN}")
    layout = derive_layout(rep)
    if rep.failures:
        print(f"\nRESULT: FAILED ({len(rep.failures)} failure(s) deriving the layout)")
        return 1
    files: dict[Path, dict] = {}
    files[CAMPAIGN / ORCHESTRATOR] = {"doc": load(CAMPAIGN / ORCHESTRATOR), "ctx": layout}
    task_files = sorted(TASK_DIR.glob("*.yml"))
    if not task_files:
        print(f"FAIL: no task files under {TASK_DIR} — the phase files are the point")
        return 1
    for f in task_files:
        files[f] = {"doc": load(f), "ctx": layout}
    campaign_playbooks = sorted(ANSIBLE_DIR.glob("*.yml"))
    if not campaign_playbooks:
        print(f"FAIL: no playbooks under {ANSIBLE_DIR} — the campaign plays are in scope")
        return 1
    for f in campaign_playbooks:
        try:
            doc = load(f)
        except yaml.YAMLError as exc:
            rep.fail(str(f.relative_to(CAMPAIGN)), f"does not parse: {exc}")
            continue
        seed = {"playbook_dir": str(ANSIBLE_DIR)}
        files[f] = {"doc": doc, "ctx": fixpoint_ctx(collect_vars(doc), seed)}
    check_includes(files, rep)
    check_rendered(files, layout, rep)
    check_bare(files, layout, rep)
    print("\n" + "-" * 70)
    print(f"{rep.checked} path claim(s) verified, {len(rep.skipped)} skipped "
          f"(runtime-only), {len(rep.failures)} failed, "
          f"{len(files)} file(s) swept.")
    if rep.skipped and not args.verbose:
        print("(re-run with --verbose to see every verified and skipped claim)")
    if rep.failures:
        print("RESULT: FAILED")
        return 1
    print("RESULT: PASSED")
    return 0
if __name__ == "__main__":
    sys.exit(main())
