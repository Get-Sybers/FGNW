A notification (aggregate-type) Ansible callback that watches the FGNW campaign
deploy (`deploy.yml`) and reports, **per stage**, how many
tasks the stage has run and how many have completed. It rides alongside the normal
stdout output and only *adds* one-line markers — it does not replace the stdout
callback.
The plugin emits a compact marker before each task (a near-live snapshot) and a
full one at the end of the run:

```text
LUDUS_PROGRESS | {"schema":"ludus-progress/1","event":"task","current_stage":"Phase 3 (AD build)","totals":{...},"stages":[...]}
```

A Ludus **client** (no server filesystem access) reads the latest snapshot straight
out of the deploy log:

```bash
ludus range logs | grep 'LUDUS_PROGRESS |' | tail -1
```

Pretty-print the stage table:

```bash
ludus range logs | grep 'LUDUS_PROGRESS |' | tail -1 \
  | sed 's/^LUDUS_PROGRESS | //' \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); \
print(f"stage: {d[\"current_stage\"]}"); \
[print(f"  {s[\"state\"]:7} {s[\"finished\"]}/{s[\"tasks\"]:<3} {s[\"name\"]}  (ok={s[\"ok\"]} chg={s[\"changed\"]} skip={s[\"skipped\"]} fail={s[\"failed\"]})") for s in d["stages"]]'
```

Each stage object carries: `name`, `state` (`running`|`done`), `tasks` (units of
work started), `finished`, and `ok` / `changed` / `skipped` / `failed` /
`unreachable`. `totals` rolls those up across stages.
Attribution keys on the human wrapper-task **name**, never the file path:

- A task whose name matches `stage_regex` (default `^(Phase\s|Cleanup\b)`) opens a
  new stage.
- Every task until the next such task counts under it.
- Runs start in a `Preflight` stage.
- Nested includes inside a phase file are named `"<token> | …"` (e.g. `"phase1b |
  …"`), which do **not** match the boundary regex, so they stay attributed to their
  enclosing Phase.
The name is the only workable key because each phase boundary has to be **one
include task**. Ansible fires `v2_playbook_on_task_start` exactly *once* for a
looped `include_tasks`, with the task name templated before `item` exists — so
folding the phases into a single looped include would emit one boundary for the
whole deploy and collapse every stage into one. `deploy.yml` keeps every phase as
its own named task; that contract is what this callback reads.
Reports the **campaign composition stages** driven by `deploy.yml` (Phases 0–5 +
Cleanup). Ludus's base `range deploy` (VM clone + OS/AD config) is a **separate**
Ansible process run by Ludus core and is not visible to this callback — that phase
is already legible in `ludus range logs` on its own.
Enabled in `campaign/ansible.cfg` (the config used for a `deploy.yml` run):

```ini
callback_plugins = ./callback_plugins
callbacks_enabled = ludus_progress
```

Options (env or `ansible.cfg` `[callback_ludus_progress]`):

| option | env | default | meaning |
| --- | --- | --- | --- |
| `stage_regex` | `LUDUS_PROGRESS_STAGE_RE` | see below | task-name pattern that opens a stage |
| `per_task` | `LUDUS_PROGRESS_PER_TASK` | `true` | emit a snapshot before every task (near-live) vs only at stage boundaries + final |

`stage_regex` default (the ` | ` is regex alternation, not a table separator):

```text

^(Phase\s|Cleanup\b)

```

`campaign/ci/progress-callback-selftest.py` drives the plugin with synthetic
events and asserts stage attribution + counts. It runs as Check 4 of
`ci/syntax-check.sh` when ansible-core is present.
"How many tasks a stage has, and how many are complete" is runtime state spanning
the whole run. A role runs as one task and cannot observe the others; only a
callback receives the per-task lifecycle events needed to count them.
