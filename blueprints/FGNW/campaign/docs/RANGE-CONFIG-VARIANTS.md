**Decision record. Refs
`blueprints/FGNW/range-config.yml` is the only range config this blueprint has.
It holds the **superset**: all 23 VMs, including `modern-infra`. Every variant is cut out of it at
deploy time by a flag — no variant has a file of its own.

```bash
ansible-playbook deploy.yml -e range_variant=small
ansible-playbook deploy.yml
ansible-playbook deploy.yml -e range_variant=xl
```

`-e range_variant=full` is an alias of `regular`. Anything else fails the preflight assert.
Setting the config by hand (`ludus range config set -f range-config.yml`) deploys the superset as
written — the `xl` set. The variant flag is the supported path.
There used to be three: the canonical config plus a standalone small one and a standalone xl one,
each a full copy of the VM list. Copies drift, and these had. By the time they were merged, both
side files were **pre-
`badsectorlabs.ludus_windows_utils` role, so a small or xl deploy came up with **no working Active
Directory at all** while the canonical config had been building AD natively for weeks. Nobody had
edited them in lockstep because nothing forced anyone to.
That is the whole argument. A variant is a *selection* over one VM list, and expressing it as a
second copy of the list means every change to the range has to be made three times, correctly, by
hand, forever. Deriving the variants from the superset makes the AD model, the role placements,
the `testing:` blocks and the templates structurally impossible to have in one variant and not
another.
`ludus_extensions` is the **one top-level key Ludus's schema tolerates unknown content under**
(`range-config.jsonschema`). Ludus validates it, ignores it, and hands it through to Ansible as the
`ludus_extensions` var. That is what lets the variant map live inside the config it describes
instead of in a separate sidecar that could go stale against it — the same carrier the `ghost9` CT
placement contract uses (`ludus_extensions.ghost9`: VLAN, address, sizing, and the digest-pinned
`get_sybers.lxc` ghost9 template image the CT is created from).
VMs are named by their `vm_name` with the leading `{{ range_id }}-` stripped.

```yaml
ludus_extensions:
  variants:
    include:
      small:    [fire-dc1, konoha-dc1, konoha-mail, ...]
      xl_extra: [modern-infra]
    target_node:
      small: {"*": null}
      xl:
        dark-mail: pi-02
    overrides:
      small:
        fire-dc1: {ram_gb: 8, cpus: 4}
```

Three maps, three jobs:

- **`include`** — membership. `small` is listed outright; `xl_extra` names the VMs that exist only
  in `xl`, and `regular` is the superset minus those.
- **`target_node`** — placement. `"*": null` is what makes `small` single-node: it strips
  `target_node` from every VM so they all fall back to `defaults.target_node`.
- **`overrides`** — everything else, per VM. `small` is **not** a same-size subset of `regular`:
  it runs alone on one node, so eight of its nine VMs are deliberately given more RAM and/or vCPU
  than the distributed variants. A general field map covers that; a membership list could not.
`campaign/filter_plugins/fgnw_variants.py` provides the `fgnw_variant` filter. `deploy.yml`'s
preflight calls it and writes the result into the **calling user's** tree:

```yaml
content: "{{ lookup('file', __cfg_blueprint) | from_yaml | fgnw_variant(__variant_norm) | to_nice_yaml(...) }}"
dest:    "{{ users_dir }}/range-config.yml"
```

The tracked file is never edited. The rendered copy is a per-deploy runtime artifact — comments and
key order are lost, which is fine for something regenerated on every run. Ludus's own templating
(`{{ range_id }}`, `{{ range_second_octet }}`) survives the round trip, because Ansible does not
re-template the output of a template.
The filter, in order: keep the VMs the variant includes; apply `target_node`; apply `overrides`;
**prune `depends_on`** entries that name a VM this variant does not deploy. That last step is the
subtle one —
waiting forever on a DC that was never provisioned.
Anything that resolves to nothing is a hard error, not a silent skip: a typo in `include.small`, an
unknown variant name, a `vm_name` not shaped `{{ range_id }}-<name>`. A dropped host has to fail the
deploy, not shrink the range quietly.
This is selection logic, not substitution, which is why it is a plugin rather than a run of Jinja in
task lines — Rule 8, and it means it can be tested. `campaign/ci/variant-filter-selftest.py` renders
all three variants **from the tracked config** (not a fixture, so it fails when the config drifts)
and checks membership, placement, overrides, override leakage, `depends_on` pruning and the error
paths. It runs as check `[5/5]` of `ci/syntax-check.sh` and needs no Ansible install.

1. Add the VM to `ludus:` in `range-config.yml`, with `vm_name: "{{ range_id }}-<name>"`.
2. Decide its variants:
   - **every variant** → nothing else to do; it is in the superset, so it is in all three.
   - **`xl` only** → add `<name>` to `include.xl_extra`.
   - **also in `small`** → add `<name>` to `include.small`.
3. If it needs a different node or size in some variant, add it to that variant's `target_node` or
   `overrides` map. Do not copy the VM.
4. If it is in `small`, keep the AD lockstep in step: `ad/NARUTO/data/inventory-small`,
   `ad/NARUTO/providers/ludus/inventory-small.yml`, `config-small.json`.
5. Run `ci/syntax-check.sh`. The self-test reads the real config, so a name that does not resolve
   fails there rather than mid-deploy.
The three current names are hardcoded in the filter, deliberately — `regular` is defined as "the
superset minus `xl_extra`", which is a rule, not a list, and `small` is an explicit roster. A fourth
variant needs:
6. A branch in `fgnw_variant()` computing its `keep` set.
7. Its entry in `__variant_map` in `deploy.yml` — that map no longer selects a config file; it still
   selects the **AD data model** (`ad_config`, `ad_data`, `ad_prov`, `infra`, `modern_infra`), which
   is the thing that genuinely still differs per variant.
8. `include` / `target_node` / `overrides` entries in `range-config.yml` as needed.
9. Coverage in `ci/variant-filter-selftest.py`.
Prefer reaching for `overrides` before adding a variant. Most "we need a slightly different range"
asks are a size or placement delta on an existing one.
