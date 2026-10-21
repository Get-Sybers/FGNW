import importlib.util
import json
import os
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
CAMPAIGN = os.path.dirname(HERE)
PLUGIN = os.path.join(CAMPAIGN, "callback_plugins", "ludus_progress.py")
def load_plugin():
    spec = importlib.util.spec_from_file_location("ludus_progress", PLUGIN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
class FakeTask(object):
    def __init__(self, name):
        self._name = name
    def get_name(self):
        return self._name
class FakeResult(object):
    def __init__(self, changed=False):
        self._result = {"changed": changed}
class Collector(object):
    """Stands in for Ansible's Display; captures the marker lines."""
    def __init__(self):
        self.lines = []
    def display(self, msg, *args, **kwargs):
        self.lines.append(msg)
def build_callback(mod):
    cb = mod.CallbackModule()
    import re
    cb._stage_re = re.compile(r"^(Phase\s|Cleanup\b)")
    cb._per_task = True
    cb._display = Collector()
    return cb
def drive(cb):
    cb.v2_playbook_on_task_start(FakeTask("preflight | announce"), False)
    cb.v2_runner_on_ok(FakeResult(changed=False))
    cb.v2_playbook_on_task_start(
        FakeTask("Phase 2 (Containment — isolation start)"), False
    )
    cb.v2_playbook_on_task_start(FakeTask("phase2 | snapshot"), False)
    cb.v2_runner_on_ok(FakeResult(changed=True))
    cb.v2_playbook_on_task_start(FakeTask("phase2 | seal"), False)
    cb.v2_runner_on_skipped(FakeResult())
    cb.v2_playbook_on_task_start(FakeTask("Phase 3 (AD build)"), False)
    cb.v2_playbook_on_task_start(FakeTask("phase3 | provision forest"), False)
    cb.v2_runner_on_failed(FakeResult(), ignore_errors=False)
    cb.v2_playbook_on_stats(object())
def last_marker(cb, mod):
    marks = [ln for ln in cb._display.lines if ln.startswith(mod.MARKER)]
    assert marks, "no LUDUS_PROGRESS markers were emitted"
    return json.loads(marks[-1][len(mod.MARKER):])
def main():
    if not os.path.isfile(PLUGIN):
        print("  FAIL  plugin not found at %s" % PLUGIN)
        return 1
    try:
        mod = load_plugin()
    except Exception as exc:
        print("  FAIL  could not import plugin (ansible-core present?): %s" % exc)
        return 1
    cb = build_callback(mod)
    drive(cb)
    payload = last_marker(cb, mod)
    failures = []
    def check(cond, msg):
        if not cond:
            failures.append(msg)
    check(payload.get("schema") == "ludus-progress/1", "schema mismatch")
    stages = {s["name"]: s for s in payload["stages"]}
    order = [s["name"] for s in payload["stages"]]
    check(
        order
        == [
            "Preflight",
            "Phase 2 (Containment — isolation start)",
            "Phase 3 (AD build)",
        ],
        "stage order wrong: %s" % order,
    )
    pf = stages.get("Preflight", {})
    check(pf.get("tasks") == 1 and pf.get("ok") == 1 and pf.get("finished") == 1,
          "Preflight counts wrong: %s" % pf)
    p2 = stages.get("Phase 2 (Containment — isolation start)", {})
    check(
        p2.get("tasks") == 2
        and p2.get("changed") == 1
        and p2.get("skipped") == 1
        and p2.get("finished") == 2,
        "Phase 2 counts wrong: %s" % p2,
    )
    p3 = stages.get("Phase 3 (AD build)", {})
    check(
        p3.get("tasks") == 1 and p3.get("failed") == 1 and p3.get("finished") == 1,
        "Phase 3 attribution/counts wrong (nested task opened its own stage?): %s" % p3,
    )
    totals = payload.get("totals", {})
    check(totals.get("stages") == 3, "totals.stages wrong: %s" % totals)
    check(totals.get("failed") == 1, "totals.failed wrong: %s" % totals)
    if failures:
        print("  FAIL  ludus_progress self-test")
        for f in failures:
            print("        - %s" % f)
        return 1
    print("  ok    ludus_progress self-test (3 stages, attribution + counts)")
    return 0
if __name__ == "__main__":
    sys.exit(main())
