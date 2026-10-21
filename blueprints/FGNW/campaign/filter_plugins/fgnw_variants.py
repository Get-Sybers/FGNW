"""fgnw_variant — turn the superset range-config into one variant's config.
`blueprints/FGNW/range-config.yml` is the ONLY range config. It holds
the xl superset plus a `ludus_extensions.variants` block, and deploy.yml renders the
variant the operator asked for into the calling user's tree before
`ludus range config set` reads it. The tracked file is never edited (
Why a plugin rather than Jinja: this is selection logic, not a substitution. It filters
the VM list, applies per-variant `target_node` and field overrides, prunes `depends_on`
entries that point at VMs the variant excludes, and fails loudly on a name that resolves
to nothing. Rule 8 puts logic here, where it can be unit-tested
(ci/variant-filter-selftest.py), instead of across a run of task lines.
The `depends_on` pruning is the subtle part.
    roles:
      - name: badsectorlabs.ludus_windows_utils.ludus_child_domain_join
        depends_on: [{vm_name: "{{ range_id }}-konoha-dc1", role: ...}]
so a variant that drops a DC would otherwise leave members waiting forever on a VM that
was never deployed.
VM identity is the `vm_name` with the leading `{{ range_id }}-` stripped; every VM in the
config uses that form, and a VM that does not is an error rather than a silent skip.
"""
from __future__ import annotations
import copy
import re
from ansible.errors import AnsibleFilterError
NAME_PREFIX_RE = re.compile(r"^\{\{ range_id \}\}-(?P<short>.+)$")
def _short(vm, where="ludus"):
    name = vm.get("vm_name")
    if not isinstance(name, str):
        raise AnsibleFilterError(f"{where}: a VM entry has no vm_name: {vm!r}")
    m = NAME_PREFIX_RE.match(name)
    if not m:
        raise AnsibleFilterError(
            f"{where}: vm_name {name!r} is not of the form '{{{{ range_id }}}}-<name>'. "
            "The variant filter identifies VMs by that suffix, so a differently-shaped "
            "name would be silently unfilterable."
        )
    return m.group("short")
def _check_known(names, known, what):
    unknown = [n for n in names if n not in known]
    if unknown:
        raise AnsibleFilterError(
            f"ludus_extensions.variants.{what} names {', '.join(sorted(unknown))}, "
            f"which are not VMs in the range config. Known VMs: {', '.join(sorted(known))}"
        )
def fgnw_variant(config, variant):
    """Return `config` reduced to `variant` ('small' | 'regular' | 'xl')."""
    if not isinstance(config, dict) or "ludus" not in config:
        raise AnsibleFilterError("fgnw_variant expects the parsed range config as a mapping")
    variants = (config.get("ludus_extensions") or {}).get("variants")
    if not variants:
        raise AnsibleFilterError(
            "range-config.yml carries no ludus_extensions.variants block, so no variant "
            "can be selected from it"
        )
    vms = config["ludus"]
    known = {_short(vm) for vm in vms}
    include = variants.get("include") or {}
    small = list(include.get("small") or [])
    xl_extra = list(include.get("xl_extra") or [])
    _check_known(small, known, "include.small")
    _check_known(xl_extra, known, "include.xl_extra")
    if variant == "small":
        keep = set(small)
    elif variant == "regular":
        keep = known - set(xl_extra)
    elif variant == "xl":
        keep = set(known)
    else:
        raise AnsibleFilterError(
            f"unknown range_variant {variant!r} — expected small, regular or xl"
        )
    target_node = (variants.get("target_node") or {}).get(variant) or {}
    overrides = (variants.get("overrides") or {}).get(variant) or {}
    _check_known([n for n in target_node if n != "*"], known, f"target_node.{variant}")
    _check_known(list(overrides), known, f"overrides.{variant}")
    out = []
    for vm in vms:
        name = _short(vm)
        if name not in keep:
            continue
        vm = copy.deepcopy(vm)
        if "*" in target_node:
            node = target_node["*"]
            vm.pop("target_node", None)
            if node is not None:
                vm["target_node"] = node
        if name in target_node:
            node = target_node[name]
            vm.pop("target_node", None)
            if node is not None:
                vm["target_node"] = node
        for key, value in (overrides.get(name) or {}).items():
            if value is None:
                vm.pop(key, None)
            else:
                vm[key] = value
        _prune_depends_on(vm, keep)
        out.append(vm)
    missing = keep - {_short(vm) for vm in out}
    if missing:
        raise AnsibleFilterError(
            f"variant {variant!r} kept {', '.join(sorted(missing))} but they are not in the "
            "rendered list — the config changed under the filter"
        )
    result = copy.deepcopy(config)
    result["ludus"] = out
    return result
def _prune_depends_on(vm, keep):
    """Drop depends_on entries naming a VM this variant does not deploy."""
    for role in vm.get("roles") or []:
        if not isinstance(role, dict) or "depends_on" not in role:
            continue
        kept = [
            dep for dep in role["depends_on"]
            if not isinstance(dep, dict)
            or "vm_name" not in dep
            or _short(dep, "depends_on") in keep
        ]
        if kept:
            role["depends_on"] = kept
        else:
            del role["depends_on"]
class FilterModule:
    def filters(self):
        return {"fgnw_variant": fgnw_variant}
