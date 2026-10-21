"""scripts/check-one-action.py — enforce README rule 8 on the owned Ansible layer.
Rule 8 (README.md): "A task does one action and contains no logic. The logic lives in
the playbook." The three-layer table is explicit — a **Task** contains *exactly one
action* and NEVER `when:`, branching, or detection-plus-action. This is the whole reason
for the FGNW AD-layer uplift (epic
`$Ansible.Changed`, folded several cmdlets into one `win_shell`, and buried an
`if ($requireDc)` inside a monolithic readiness probe. This is the detector that makes
"one task, one action" enforceable rather than aspirational — check-density (rule 8's old,
removed detector) measured `when:` density and proved little; this checks the actual bar.
Two detectors:
  A. `when:` on an ACTION task inside a role. `when:` belongs on the playbook's
     include_tasks / include_role / import_* (or a block) that DECIDES — not on the task
     that ACTS. Includes, imports, group_by and blocks are the decision layer and are
     exempt. Applied to role task files only; a playbook's own `when:` on an include or
     group_by is correct and is not flagged.
  B. An inline shell-body task (win_shell / shell / raw / win_powershell) that does MORE
     THAN ONE action — two or more statements, or a control-flow keyword
     (if/elseif/else/foreach/for/while/switch/try/…). A prologue of error-handling / setup
     lines ($ErrorActionPreference, Set-StrictMode, [CmdletBinding()], param(…), comments)
     is not an action. command/win_command are single-executable by nature; they are only
     flagged when they chain with && / || / ;.
SCOPE grows with the rebuild. It is seeded with the FGNW owned AD layer — the clean-room
roles epic
A gate that matches nothing is not a gate (the house standard), so the run FAILS if the
scope resolves to zero files.
Usage:
  scripts/check-one-action.py            gate the owned layer (CI); exit 1 on any violation
  scripts/check-one-action.py --audit    survey the WHOLE blueprint and print a refactor
                                         backlog grouped by provenance bucket (exit 0)
EXIT 0 every task in scope does one action (or --audit, always); 1 any violation, or scope empty.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path
try:
    import yaml
except ImportError:
    print("FAIL: pyyaml is not installed (pip install pyyaml)")
    sys.exit(1)
REPO = Path(__file__).resolve().parent.parent
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
        return (yaml.safe_load(p.read_text()) or {}).get(section) or {}
    except Exception as exc:
        sys.exit(f"FAIL: unreadable scripts/gates.yml: {exc}")
GATES = _gates("one_action")
CAMPAIGN_ANSIBLE = REPO / GATES.get(
    "scope_root", "blueprints/FGNW/campaign/ansible")
SCOPE_GLOBS = GATES.get("scope_globs") or [
    "roles/fgnw_ad_mgmt/tasks/**/*.yml",
    "FGNW-campaign-setup.yml",
    "FGNW-ninjasploitable-join.yml",
]
class LineLoader(yaml.SafeLoader):
    """SafeLoader that records the 1-based source line of every mapping as __line__."""
def _mapping_with_line(loader, node):
    mapping = yaml.SafeLoader.construct_mapping(loader, node, deep=True)
    mapping["__line__"] = node.start_mark.line + 1
    return mapping
LineLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping_with_line)
DIRECTIVES = {
    "name", "when", "register", "loop", "with_items", "with_dict", "with_first_found",
    "with_fileglob", "with_together", "until", "retries", "delay", "changed_when",
    "failed_when", "no_log", "tags", "vars", "environment", "loop_control", "become",
    "become_user", "become_method", "become_password", "become_flags", "delegate_to",
    "delegate_facts", "run_once", "ignore_errors", "notify", "listen", "args", "check_mode",
    "diff", "throttle", "any_errors_fatal", "connection", "remote_user", "timeout", "poll",
    "async", "collections", "module_defaults", "action", "local_action", "__line__",
}
INCLUDE_MODULES = {
    "include_tasks", "include_role", "import_tasks", "import_role", "include",
    "import_playbook", "group_by",
    "ansible.builtin.include_tasks", "ansible.builtin.include_role",
    "ansible.builtin.import_tasks", "ansible.builtin.import_role",
    "ansible.builtin.import_playbook", "ansible.builtin.group_by",
    "ansible.legacy.include_tasks", "ansible.legacy.include_role",
}
SHELL_BODY_MODULES = {
    "shell", "raw", "win_shell", "win_powershell",
    "ansible.builtin.shell", "ansible.builtin.raw",
    "ansible.windows.win_shell", "ansible.windows.win_powershell",
}
CMD_MODULES = {
    "command", "win_command",
    "ansible.builtin.command", "ansible.windows.win_command",
}
CONTROL_FLOW = re.compile(r"^(if|elseif|else|foreach|for|while|switch|try|catch|finally|do)\b", re.I)
PROLOGUE = re.compile(
    r"^(\$ErrorActionPreference\b|Set-StrictMode\b|\[CmdletBinding|param\s*\(|\)\s*$|set\s+[-+])",
    re.I,
)
def module_of(task: dict):
    keys = [k for k in task if k not in DIRECTIVES]
    if not keys:
        return None
    for k in keys:
        if k in INCLUDE_MODULES or k in SHELL_BODY_MODULES or k in CMD_MODULES:
            return k
    return keys[0]
def body_of(task: dict, mod: str):
    val = task.get(mod)
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        for k in ("script", "cmd", "_raw_params"):
            if isinstance(val.get(k), str):
                return val[k]
    args = task.get("args") or {}
    for k in ("cmd", "_raw_params"):
        if isinstance(args.get(k), str):
            return args[k]
    return None
def action_statements(body: str):
    """Non-prologue lines, and the count of top-level statements among them."""
    lines = []
    for raw in body.splitlines():
        s = raw.strip()
        if not s or s.startswith("#") or PROLOGUE.match(s):
            continue
        lines.append(s)
    stmts = []
    for line in lines:
        stmts.extend(p for p in line.split(";") if p.strip())
    return lines, stmts
def iter_tasks(nodes):
    for t in nodes:
        if not isinstance(t, dict):
            continue
        if any(k in t for k in ("block", "rescue", "always")):
            for bk in ("block", "rescue", "always"):
                if isinstance(t.get(bk), list):
                    yield from iter_tasks(t[bk])
            continue
        yield t
def tasks_in(doc, is_playbook):
    if is_playbook:
        for play in doc:
            if not isinstance(play, dict):
                continue
            for section in ("pre_tasks", "tasks", "post_tasks", "handlers"):
                if isinstance(play.get(section), list):
                    yield from iter_tasks(play[section])
    elif isinstance(doc, list):
        yield from iter_tasks(doc)
A_ROLES = {
    "ad", "adcs", "child_dns", "child_domain", "common", "commonwkstn",
    "dc_dns_conditional_forwarder", "dns_conditional_forwarder", "dnsforwarder",
    "domain_controller", "fakespooler", "laps", "member_server", "move_to_ou",
    "password_policy", "powershell_logging", "privileged_user_task", "security", "settings",
    "trusts",
}
B_ROLES = {"aleemladha.ludus_exchange", "geerlingguy.docker", "wireshark"}
C_ROLES = {
    "fgnw_browser_defaults", "fgnw_browser_extensions", "fgnw_decoy_files",
    "fgnw_exchange_seed_mail", "fgnw_modern_infra", "fgnw_owa_inboxes", "fgnw_themed_sites",
    "ludus_tool_cache",
    "fgnw_ad_mgmt",
}
A_PLAYBOOKS = {
    "build.yml", "data.yml", "main.yml", "ad-child_domain.yml", "ad-data.yml", "ad-members.yml",
    "ad-parent_domain.yml", "ad-servers.yml", "ad-trusts.yml", "adcs.yml", "dnsforwarder.yml",
    "lat.yml", "reboot.yml", "security.yml", "tgtdelegation.yml",
}
BUCKET_LABEL = {
    "A": "legacy upstream-derived — REPLACE, not refactor-in-place",
    "B": "third-party — LEAVE (upstream identity; refactoring breaks provenance)",
    "C": "owned (Get-Sybers) — REFACTOR IN PLACE to rule 8",
    "?": "unclassified — check provenance",
}
ANSIBLE_CHANGED = re.compile(r"\$Ansible\.Changed")
OUT_OF_SCOPE_EXACT: set[str] = set()
OUT_OF_SCOPE_PREFIXES = ("FGNW-facts-", "FGNW-verify-")
def out_of_scope(name: str) -> bool:
    return name in OUT_OF_SCOPE_EXACT or name.startswith(OUT_OF_SCOPE_PREFIXES)
def bucket_of(path: Path):
    parts = path.parts
    if "roles" in parts:
        name = parts[parts.index("roles") + 1]
        if name in A_ROLES:
            return "A"
        if name in B_ROLES:
            return "B"
        if name in C_ROLES:
            return "C"
        return "?"
    stem = path.name
    if stem.startswith("FGNW-") or stem.startswith("ghost9-"):
        return "C"
    if "deploy-tasks" in parts:
        return "C"
    if stem in A_PLAYBOOKS:
        return "A"
    return "?"
def scan_file(f: Path):
    """Return a list of (line, name, ftype, why) rule-8 findings for one file."""
    try:
        doc = yaml.load(f.read_text(encoding="utf-8"), Loader=LineLoader)
    except yaml.YAMLError as exc:
        return [("?", "<file>", "yaml", f"YAML error: {exc}")]
    if doc is None:
        return []
    is_playbook = isinstance(doc, list) and any(
        isinstance(p, dict) and ("hosts" in p or "import_playbook" in p) for p in doc
    )
    is_role_taskfile = "/roles/" in str(f) and "/tasks/" in str(f)
    found = []
    for task in tasks_in(doc, is_playbook):
        mod = module_of(task)
        if mod is None:
            continue
        line, name = task.get("__line__", "?"), task.get("name", "<unnamed>")
        if is_role_taskfile and "when" in task and mod not in INCLUDE_MODULES and mod != "block":
            found.append((line, name, "when", f"`when:` on an action task ({mod}) — the decision "
                          f"belongs on an include/import, not the task that acts"))
        body = body_of(task, mod) if (mod in SHELL_BODY_MODULES or mod in CMD_MODULES) else None
        if mod in SHELL_BODY_MODULES and body:
            lines, stmts = action_statements(body)
            branch = next((l for l in lines if CONTROL_FLOW.match(l)), None)
            if branch:
                found.append((line, name, "branch", f"inline {mod} contains control flow "
                              f"('{branch.split()[0]} …') — logic belongs in the playbook"))
            elif len(stmts) > 1:
                found.append((line, name, "multi", f"inline {mod} runs {len(stmts)} statements — "
                              f"a task does one action"))
        if mod in CMD_MODULES and body and re.search(r"&&|\|\||;", body):
            found.append((line, name, "chain", f"{mod} chains multiple commands — one action"))
        if body and ANSIBLE_CHANGED.search(body):
            found.append((line, name, "changed", f"{mod} sets $Ansible.Changed — hand-rolled "
                          f"idempotence; use module semantics or a two-task check→act"))
    return found
def gate():
    files = []
    for glob in SCOPE_GLOBS:
        files += sorted(CAMPAIGN_ANSIBLE.glob(glob))
    files = [f for f in files if f.is_file()]
    if not files:
        print("FAIL: scope matched no files — a gate that matches nothing is not a gate.")
        return 1
    violations = [(f, *v) for f in files for v in scan_file(f)]
    if violations:
        print("FAIL — rule 8, a task does one action:\n")
        for f, line, name, ftype, why in violations:
            print(f"  {f.relative_to(REPO)}:{line}\n      task: {name}\n      {why}\n")
        print(f"{len(violations)} violation(s).")
        return 1
    print(f"OK — {len(files)} file(s) in the owned AD layer; every task does one action.")
    for f in files:
        print(f"  swept  {f.relative_to(REPO)}")
    return 0
def audit():
    """Survey the whole blueprint's task-level PowerShell; report a refactor backlog by bucket."""
    seen = {}
    for f in sorted(set(CAMPAIGN_ANSIBLE.glob("roles/**/*.yml")) | set(CAMPAIGN_ANSIBLE.glob("*.yml"))
                    | set((CAMPAIGN_ANSIBLE.parent / "deploy-tasks").glob("*.yml"))):
        if not f.is_file() or out_of_scope(f.name):
            continue
        found = scan_file(f)
        if found:
            seen[f] = found
    by_bucket = {"A": [], "B": [], "C": [], "?": []}
    for f, found in seen.items():
        by_bucket[bucket_of(f)].append((f, found))
    PS_TYPES = {"multi", "branch", "changed", "chain"}
    def split(found):
        ps = sum(1 for _, _, t, _ in found if t in PS_TYPES)
        return ps, len(found) - ps
    total_ps = sum(split(v)[0] for v in seen.values())
    total_when = sum(split(v)[1] for v in seen.values())
    print(f"PowerShell / rule-8 audit — {total_ps} chunky-PowerShell finding(s) "
          f"(multi-statement / branching / $Ansible.Changed) and {total_when} when:-on-action "
          f"finding(s), across {len(seen)} file(s).\n")
    replaced = {"domain_controller", "child_domain"}
    for code in ("A", "B", "C", "?"):
        rows = sorted(by_bucket[code], key=lambda x: (-split(x[1])[0], -len(x[1])))
        if not rows:
            continue
        bps = sum(split(fnd)[0] for _, fnd in rows)
        bwhen = sum(split(fnd)[1] for _, fnd in rows)
        print(f"── Bucket {code}: {BUCKET_LABEL[code]}")
        print(f"   {bps} chunky-PS + {bwhen} when: across {len(rows)} file(s)")
        for f, found in rows:
            tallies = {}
            for _, _, ftype, _ in found:
                tallies[ftype] = tallies.get(ftype, 0) + 1
            brk = ", ".join(f"{tallies[k]} {k}" for k in ("multi", "branch", "changed", "chain", "when")
                            if k in tallies)
            note = "   [→ replaced by fgnw_ad_* in #401]" if (
                code == "A" and any(r in f.parts for r in replaced)) else ""
            print(f"    {split(found)[0]:>2} PS  {f.relative_to(CAMPAIGN_ANSIBLE.parent)}   ({brk}){note}")
        print()
    print("Out of scope (not runtime range-config, so rule 8 does not apply):")
    print("  · FGNW-facts-*.yml / FGNW-verify-*.yml — read-only diagnostic/verification "
          "harvesters (snapshot the range into JSON; mutate nothing).")
    print("  · blueprints/…/campaign/ad/NARUTO/scripts/*.ps1 — standalone attack artifacts "
          "(programs run on targets, not Ansible tasks).")
    print("Disposition: A → replaced by the rebuild · B → leave (provenance) · "
          "C → refactor in place to rule 8 (the PowerShell surface beyond the AD layer).")
    return 0
def main(argv):
    if GATES.get("applicable") is False:
        print("NOT-APPLICABLE (scripts/gates.yml): "
              f"{GATES.get('reason', 'no reason recorded')}")
        return 0
    if "--audit" in argv:
        return audit()
    return gate()
if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
