"""ci/variant-filter-selftest.py — prove the variant filter against the real config.
`range-config.yml` is the only range config (
with the fgnw_variant filter, so a bug here silently deploys the wrong set of VMs — the
exact failure the three-file split existed to avoid. This asserts the filter's contract
against the tracked superset rather than a fixture, so it fails when the config drifts.
Checked:
  * membership per variant, including that small is a strict subset and xl is everything
  * per-variant target_node (small has none at all — it is deliberately single-node)
  * per-variant field overrides land, and only on the named VMs
  * depends_on entries pointing at excluded VMs are pruned, so no member of a filtered
    variant waits forever on a DC that was never deployed
  * a name that resolves to no VM is a hard error, not a silent no-op
Exit 0 pass, 1 fail.
"""
from __future__ import annotations
import copy
import pathlib
import sys
import types
CAMPAIGN = pathlib.Path(__file__).resolve().parent.parent
BLUEPRINT = CAMPAIGN.parent
try:
    import yaml
except ImportError:
    print("FAIL: pyyaml is not installed (pip install pyyaml)")
    sys.exit(1)
if "ansible.errors" not in sys.modules:
    sys.modules.setdefault("ansible", types.ModuleType("ansible"))
    errors = types.ModuleType("ansible.errors")
    class AnsibleFilterError(Exception):
        pass
    errors.AnsibleFilterError = AnsibleFilterError
    sys.modules["ansible.errors"] = errors
sys.path.insert(0, str(CAMPAIGN / "filter_plugins"))
from fgnw_variants import fgnw_variant
from ansible.errors import AnsibleFilterError
FAILURES: list[str] = []
def check(what, cond, detail=""):
    if cond:
        print(f"  ok    {what}")
    else:
        FAILURES.append(what)
        print(f"  FAIL  {what}\n        {detail}")
def short(vm):
    return vm["vm_name"].replace("{{ range_id }}-", "")
def main() -> int:
    cfg = yaml.safe_load((BLUEPRINT / "range-config.yml").read_text())
    variants = cfg["ludus_extensions"]["variants"]
    everything = {short(v) for v in cfg["ludus"]}
    rendered = {v: fgnw_variant(cfg, v) for v in ("small", "regular", "xl")}
    names = {v: {short(x) for x in r["ludus"]} for v, r in rendered.items()}
    check("small membership matches include.small",
          names["small"] == set(variants["include"]["small"]),
          f"{sorted(names['small'] ^ set(variants['include']['small']))}")
    check("xl is the whole superset", names["xl"] == everything)
    check("regular is the superset minus xl_extra",
          names["regular"] == everything - set(variants["include"]["xl_extra"]))
    check("small is a strict subset of regular", names["small"] < names["regular"])
    check("small pins no VM to a node (single-node by construction)",
          all("target_node" not in v for v in rendered["small"]["ludus"]),
          str([short(v) for v in rendered["small"]["ludus"] if "target_node" in v]))
    xl_nodes = {short(v): v.get("target_node") for v in rendered["xl"]["ludus"]}
    for name, node in (variants["target_node"].get("xl") or {}).items():
        check(f"xl places {name} on {node}", xl_nodes.get(name) == node, str(xl_nodes.get(name)))
    small_by = {short(v): v for v in rendered["small"]["ludus"]}
    for name, fields in (variants["overrides"].get("small") or {}).items():
        for key, want in fields.items():
            check(f"small overrides {name}.{key}={want}",
                  small_by[name].get(key) == want, str(small_by[name].get(key)))
    reg_by = {short(v): v for v in rendered["regular"]["ludus"]}
    leaked = [
        f"{n}.{k}" for n, f in (variants["overrides"].get("small") or {}).items()
        for k, want in f.items() if n in reg_by and reg_by[n].get(k) == want
        and _superset_value(cfg, n, k) != want
    ]
    check("small's overrides do not leak into regular", not leaked, str(leaked))
    dangling = [
        f"{short(vm)} -> {dep['vm_name']}"
        for vm in rendered["small"]["ludus"]
        for role in (vm.get("roles") or [])
        if isinstance(role, dict)
        for dep in (role.get("depends_on") or [])
        if isinstance(dep, dict) and "vm_name" in dep
        and short(dep) not in names["small"]
    ]
    check("small has no depends_on pointing at an excluded VM", not dangling, str(dangling))
    bad = copy.deepcopy(cfg)
    bad["ludus_extensions"]["variants"]["include"]["small"].append("no-such-vm")
    try:
        fgnw_variant(bad, "small")
        check("a variant naming a VM that does not exist is a hard error", False,
              "it was accepted, so a typo would silently drop a host from the range")
    except AnsibleFilterError:
        check("a variant naming a VM that does not exist is a hard error", True)
    try:
        fgnw_variant(cfg, "enormous")
        check("an unrecognised range_variant is a hard error", False, "it was accepted")
    except AnsibleFilterError:
        check("an unrecognised range_variant is a hard error", True)
    print()
    if FAILURES:
        print(f"RESULT: FAILED ({len(FAILURES)} check(s))")
        return 1
    print("RESULT: PASSED (variant filter)")
    return 0
def _superset_value(cfg, name, key):
    for vm in cfg["ludus"]:
        if short(vm) == name:
            return vm.get(key)
    return None
if __name__ == "__main__":
    sys.exit(main())
