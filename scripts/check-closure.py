#!/usr/bin/env python3
"""Dependency closure: does every role/collection reference in the tracked tree resolve?
A file being a byte-identical duplicate of something elsewhere does NOT make it
removable — the galaxy still has to be able to FIND it at runtime. This walks
every reference and says where it resolves, or that it does not.
"""
import os
import re
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT)
def _gates(section):
    """This repo's scope for the mirrored checkers, from scripts/gates.yml.
    The scripts/*.py family is byte-identical across the source repos; the
    per-repo piece is gates.yml alone. Missing file or section means the
    script's built-in defaults apply.
    """
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gates.yml")
    if not os.path.isfile(p):
        return {}
    try:
        import yaml
    except ImportError:
        raise SystemExit("FAIL: PyYAML is required to read scripts/gates.yml "
                         "(python3 -m pip install pyyaml)")
    try:
        with open(p) as fh:
            return (yaml.safe_load(fh) or {}).get(section) or {}
    except Exception as exc:
        raise SystemExit(f"FAIL: unreadable scripts/gates.yml: {exc}")
GATES = _gates("closure")
EXTERNAL_NS = set(GATES.get("external_namespaces") or [])
task_roles = ({d for d in os.listdir("ansible/roles")
               if os.path.isdir(f"ansible/roles/{d}")}
              if os.path.isdir("ansible/roles") else set())
coll_roles = {}
coll_dirs = {}
for d in (sorted(os.listdir("ansible/collections"))
          if os.path.isdir("ansible/collections") else []):
    p = f"ansible/collections/{d}"
    if not os.path.isdir(p):
        continue
    gy = open(f"{p}/galaxy.yml").read()
    ns = re.search(r"^namespace:\s*(\S+)", gy, re.M).group(1)
    nm = re.search(r"^name:\s*(\S+)", gy, re.M).group(1)
    coll_dirs[d] = f"{ns}.{nm}"
    rp = f"{p}/roles"
    if os.path.isdir(rp):
        for r in os.listdir(rp):
            if os.path.isdir(f"{rp}/{r}"):
                coll_roles[f"{ns}.{nm}.{r}"] = f"{rp}/{r}"
                coll_roles.setdefault(f"{d}.{r}", f"{rp}/{r}")
    plugins_root = f"{p}/plugins"
    kinds = sorted(os.listdir(plugins_root)) if os.path.isdir(plugins_root) else []
    for kind in kinds:
        pp = f"{plugins_root}/{kind}"
        if not os.path.isdir(pp) or kind == "__pycache__":
            continue
        for f in os.listdir(pp):
            if f.endswith(".py") and not f.startswith("_"):
                stem = f[:-3]
                coll_roles[f"{ns}.{nm}.{stem}"] = f"{pp}/{f}"
                coll_roles.setdefault(f"{d}.{stem}", f"{pp}/{f}")
refs = {}
FQCN = re.compile(r"\bget_sybers\.[a-z_]+\.[a-z_0-9]+\b")
FQCN_USES = re.compile(
    r"^(?!\s*#)\s*(?:-\s*)?(?:name:\s*|role:\s*)?(get_sybers\.[a-z_]+\.[a-z_0-9]+)\s*:?\s*$",
    re.M,
)
for base in ("ansible", "blueprints"):
    for dirpath, _dirs, files in os.walk(base):
        if "/.git" in dirpath:
            continue
        for f in files:
            if not f.endswith((".yml", ".yaml", ".j2", ".md", ".cfg")):
                continue
            fp = os.path.join(dirpath, f)
            try:
                txt = open(fp, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            for m in FQCN.findall(txt):
                refs.setdefault(m, set()).add(fp)
cfg_roles = {}
for cfg in ("range-config.yml",):
    p = f"blueprints/FGNW/{cfg}"
    if not os.path.exists(p):
        continue
    inside = False
    for line in open(p):
        if re.match(r"^\s*roles:\s*$", line):
            inside = True
            continue
        if inside:
            m = re.match(r"^\s*-\s*([A-Za-z0-9_.\-]+)\s*$", line)
            if m:
                cfg_roles.setdefault(m.group(1), set()).add(cfg)
            elif line.strip() and not line.lstrip().startswith("#"):
                inside = False
print("=" * 78)
print("COLLECTION DIRECTORY vs DECLARED FQCN")
print("=" * 78)
for d, fqcn in coll_dirs.items():
    flag = "" if d == fqcn else "   <-- MISMATCH: installs as %s" % fqcn
    print(f"  dir {d:<26} galaxy.yml -> {fqcn}{flag}")
print()
print("=" * 78)
print("FQCN ROLE REFERENCES — do they resolve?")
print("=" * 78)
bad = []
for fqcn in sorted(refs):
    parts = fqcn.split(".")
    if len(parts) != 3:
        continue
    ns, coll, role = parts
    declared = f"{ns}.{coll}"
    if fqcn in coll_roles:
        real = coll_dirs.get(f"{ns}.{coll}")
        if real and real != f"{ns}.{coll}":
            status = f"DIR-ONLY (installs as {real}.{role})"
            bad.append((fqcn, status))
        else:
            status = "ok"
    elif declared in EXTERNAL_NS:
        status = "EXTERNAL (declared)"
    else:
        status = "UNRESOLVED"
        bad.append((fqcn, status))
    if status != "ok":
        print(f"  {status:<40} {fqcn}")
        for f in sorted(refs[fqcn])[:3]:
            print(f"      referenced by {f}")
if not bad:
    print("  all references resolve")
print()
print("=" * 78)
print("CROSS-COLLECTION USE vs DECLARED dependencies")
print("=" * 78)
for d, fqcn in coll_dirs.items():
    gy = open(f"ansible/collections/{d}/galaxy.yml").read()
    dep_blk = re.search(r"^dependencies:\n((?:\s+.*\n)*)", gy, re.M)
    declared = set(re.findall(r'"?([a-z_]+\.[a-z_]+)"?\s*:', dep_blk.group(1))) if dep_blk else set()
    used = set()
    for dirpath, _x, files in os.walk(f"ansible/collections/{d}"):
        for f in files:
            if not f.endswith((".yml", ".yaml")):
                continue
            txt = open(os.path.join(dirpath, f), encoding="utf-8", errors="replace").read()
            for m in FQCN_USES.findall(txt):
                other = ".".join(m.split(".")[:2])
                if other != fqcn and other != d:
                    used.add(other)
    missing = used - declared
    print(f"  {d}")
    print(f"      declared : {sorted(declared) or '(none)'}")
    print(f"      uses     : {sorted(used) or '(none)'}")
    if missing:
        print(f"      *** UNDECLARED RUNTIME DEPENDENCY: {sorted(missing)}")
print()
print("=" * 78)
print("RANGE-CONFIG `roles:` — vendored, Galaxy-declared, or missing?")
print("=" * 78)
req = ""
rp = "blueprints/FGNW/requirements.yml"
if os.path.exists(rp):
    req = open(rp).read()
for r in sorted(cfg_roles):
    if r in task_roles:
        where = f"vendored  ansible/roles/{r}"
    elif r in req:
        where = "declared in requirements.yml (pulled from Galaxy)"
    else:
        where = "*** NOT VENDORED AND NOT DECLARED ***"
    print(f"  {r:<44} {where}")
print()
print("=" * 78)
broken = len(bad)
missing_dep = 0
for d, fqcn in coll_dirs.items():
    gy = open(f"ansible/collections/{d}/galaxy.yml").read()
    dep_blk = re.search(r"^dependencies:\n((?:\s+.*\n)*)", gy, re.M)
    declared = set(re.findall(r'"?([a-z_]+\.[a-z_]+)"?\s*:', dep_blk.group(1))) if dep_blk else set()
    used = set()
    for dirpath, _x, files in os.walk(f"ansible/collections/{d}"):
        for f in files:
            if f.endswith((".yml", ".yaml")):
                txt = open(os.path.join(dirpath, f), encoding="utf-8", errors="replace").read()
                for m in FQCN_USES.findall(txt):
                    o = ".".join(m.split(".")[:2])
                    if o not in (fqcn, d):
                        used.add(o)
    missing_dep += len(used - declared)
if broken or missing_dep:
    print(f"FAIL — {broken} unresolved/mis-namespaced reference(s), "
          f"{missing_dep} undeclared cross-collection dependency(ies)")
    raise SystemExit(1)
print("PASS — every reference resolves and every cross-collection dependency is declared")
