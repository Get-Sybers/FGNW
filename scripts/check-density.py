#!/usr/bin/env python3
"""Conditional density + main.yml shape. One walker, used for every tree."""
import collections, glob, os, re, sys, yaml
INCLUDE = {'include_tasks', 'import_tasks', 'include_role', 'import_role',
           'ansible.builtin.include_tasks', 'ansible.builtin.import_tasks',
           'ansible.builtin.include_role', 'ansible.builtin.import_role'}
META = {'name', 'when', 'register', 'loop', 'with_items', 'with_dict', 'loop_control',
        'tags', 'vars', 'become', 'become_user', 'changed_when', 'failed_when',
        'ignore_errors', 'delegate_to', 'run_once', 'no_log', 'notify', 'until',
        'retries', 'delay', 'args', 'check_mode', 'environment', 'block', 'rescue',
        'always', 'listen'}
API = re.compile(r'ansible\.builtin\.uri|community\.general\.proxmox|proxmox_|pvesh|'
                 r'pvesm|\bpct\b|\bqm\b|\bludus\b|api_|_api|\bcurl\b')
def classify(t):
    mods = [k for k in t if k not in META]
    m = mods[0] if mods else '(none)'
    if m in INCLUDE:
        return 'include'
    if m.endswith('assert'):
        return 'assert'
    if m.endswith(('set_fact', 'setup', 'package_facts', 'service_facts')):
        return 'fact'
    return 'action'
def walk(tasks, out):
    for t in tasks or []:
        if not isinstance(t, dict):
            continue
        if any(k in t for k in ('block', 'rescue', 'always')):
            for k in ('block', 'rescue', 'always'):
                walk(t.get(k), out)
            continue
        out.append((classify(t), 'when' in t))
def density(files):
    c, w = collections.Counter(), collections.Counter()
    skipped = []
    for f in files:
        o = []
        try:
            walk(yaml.safe_load(open(f)), o)
        except (yaml.YAMLError, OSError, UnicodeDecodeError) as exc:
            skipped.append(f"{f}: {type(exc).__name__}")
            continue
        for k, hw in o:
            c[k] += 1
            if hw:
                w[k] += 1
    for s in skipped:
        print(f"  WARN unparseable, not counted: {s}", file=sys.stderr)
    return c, w
def shape(role_dir):
    mp = os.path.join(role_dir, 'tasks', 'main.yml')
    if not os.path.exists(mp):
        return None
    o = []
    try:
        walk(yaml.safe_load(open(mp)), o)
    except (yaml.YAMLError, OSError, UnicodeDecodeError) as exc:
        print(f"  WARN unparseable main.yml, shape unknown: {mp}: "
              f"{type(exc).__name__}", file=sys.stderr)
        return None
    inc = sum(1 for k, _ in o if k == 'include')
    act = len(o) - inc
    return 'dispatch' if inc and act <= 2 else ('mixed' if inc else 'action list')
def report(label, files):
    c, w = density(files)
    pct = w['action'] * 100 // max(c['action'], 1)
    ratio = c['action'] / c['include'] if c['include'] else float('inf')
    print(f"  {label:<32}{c['action']:>7}{w['action']:>9}{pct:>5}%{c['include']:>9}{ratio:>8.1f}")
    return pct
print(f"  {'tree':<32}{'action':>7}{'when':>9}{'':>6}{'include':>9}{'act:inc':>8}")
report('tracked collections (all 3)',
       glob.glob('ansible/collections/get_sybers.*/roles/*/tasks/*.yml'))
for coll in sorted(glob.glob('ansible/collections/get_sybers.*')):
    report('  ' + os.path.basename(coll), glob.glob(f'{coll}/roles/*/tasks/*.yml'))
report('tracked task-roles', glob.glob('ansible/roles/*/tasks/*.yml'))
_staged_globs = ('.dev/ansible/lib/get-sybers/*/tasks/*.yml',
                 '.Non-Distribute/dev/ansible/lib/get-sybers/*/tasks/*.yml')
_staged = [f for g in _staged_globs for f in glob.glob(g)]
if _staged:
    report('staged dev/ansible/lib/get-sybers', _staged)
elif any(os.path.isdir(g.split('/')[0]) for g in _staged_globs):
    print(f"  {'staged dev/ansible/lib/get-sybers':<32}"
          f"{'MISSING — no files matched ' + ' or '.join(_staged_globs):>39}")
print(f"\n  main.yml shape x API, per collection")
for coll in sorted(glob.glob('ansible/collections/get_sybers.*')):
    sh, api = collections.Counter(), collections.Counter()
    n_roles = 0
    for rd in sorted(glob.glob(f'{coll}/roles/*')):
        s = shape(rd)
        if not s:
            continue
        n_roles += 1
        body = ''.join(open(f).read() for f in glob.glob(f'{rd}/tasks/*.yml'))
        sh[s] += 1
        if API.search(body):
            api[s] += 1
    parts = ', '.join(f"{s} {sh[s]}({api[s]} API)" for s in ('dispatch', 'mixed', 'action list') if sh[s])
    print(f"  {os.path.basename(coll):<26} {n_roles:>2} roles with tasks/main.yml — {parts}")
