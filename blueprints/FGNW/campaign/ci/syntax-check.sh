#!/usr/bin/env bash
set -uo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root" || exit 1
ORCHESTRATORS=(deploy.yml)
TASK_DIR=deploy-tasks
failures=0
fail() {
  printf '  FAIL  %s\n' "$1"
  failures=$((failures + 1))
}
pass() { printf '  ok    %s\n' "$1"; }
echo "syntax-check: $repo_root"
echo
echo "[1/5] ansible-playbook --syntax-check (orchestrators)"
if command -v ansible-playbook > /dev/null 2>&1; then
  for pb in "${ORCHESTRATORS[@]}"; do
    if [[ ! -f $pb ]]; then
      fail "$pb (missing)"
      continue
    fi
    if out="$(ansible-playbook --syntax-check "$pb" 2>&1)"; then
      pass "$pb"
    else
      fail "$pb"
      printf '%s\n' "$out" | sed 's/^/        /'
    fi
  done
else
  if [[ ${SYNTAX_CHECK_REQUIRE_ANSIBLE:-0} == "1" ]]; then
    fail "ansible-playbook not on PATH (SYNTAX_CHECK_REQUIRE_ANSIBLE=1)"
  else
    echo "  SKIPPED — ansible-playbook is not on PATH."
    echo "  No syntax check was performed on the orchestrators. Only the YAML"
    echo "  parse below ran. Set SYNTAX_CHECK_REQUIRE_ANSIBLE=1 to make this fatal."
    ansible_skipped=1
  fi
fi
echo
echo "[2/5] YAML parse (orchestrators + $TASK_DIR/)"
if ! python3 - "$TASK_DIR" "${ORCHESTRATORS[@]}" << 'PY'
import glob
import os
import sys
try:
    import yaml
except ImportError:
    print("  FAIL  pyyaml is not installed (pip install pyyaml)")
    sys.exit(1)
task_dir, orchestrators = sys.argv[1], sys.argv[2:]
failures = 0
def fail(name, msg):
    global failures
    print("  FAIL  %s\n        %s" % (name, msg))
    failures += 1
def load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)
for path in orchestrators:
    if not os.path.isfile(path):
        fail(path, "missing")
        continue
    try:
        doc = load(path)
    except yaml.YAMLError as exc:
        fail(path, str(exc).replace("\n", "\n        "))
        continue
    if not isinstance(doc, list) or not doc:
        fail(path, "expected a non-empty list of plays, got %s" % type(doc).__name__)
        continue
    if not all(isinstance(play, dict) for play in doc):
        fail(path, "every play must be a mapping")
        continue
    print("  ok    %s (%d play%s)" % (path, len(doc), "" if len(doc) == 1 else "s"))
task_files = sorted(glob.glob(os.path.join(task_dir, "*.yml")))
if not task_files:
    fail(task_dir, "no .yml files found — the phase files are the point of this check")
for path in task_files:
    try:
        doc = load(path)
    except yaml.YAMLError as exc:
        fail(path, str(exc).replace("\n", "\n        "))
        continue
    if not isinstance(doc, list) or not doc:
        fail(path, "expected a non-empty list of tasks, got %s" % type(doc).__name__)
        continue
    bad = [i for i, task in enumerate(doc) if not isinstance(task, dict)]
    if bad:
        fail(path, "entries %s are not task mappings" % bad)
        continue
    unnamed = [i for i, task in enumerate(doc) if "name" not in task]
    if unnamed:
        fail(path, "tasks %s have no name (every task in a phase file must be named)" % unnamed)
        continue
    if any("hosts" in task or "tasks" in task for task in doc):
        fail(path, "looks like a playbook, not a task file (found hosts:/tasks:)")
        continue
    print("  ok    %s (%d task%s)" % (path, len(doc), "" if len(doc) == 1 else "s"))
sys.exit(1 if failures else 0)
PY
then
  failures=$((failures + 1))
fi
echo
echo "[3/5] path resolution (ci/path-resolution-check.py)"
if python3 "$repo_root/ci/path-resolution-check.py"; then
  pass "path resolution"
else
  fail "path resolution"
fi
echo
echo "[4/5] ludus_progress callback self-test (ci/progress-callback-selftest.py)"
if command -v ansible-playbook > /dev/null 2>&1; then
  if python3 "$repo_root/ci/progress-callback-selftest.py"; then
    pass "ludus_progress self-test"
  else
    fail "ludus_progress self-test"
  fi
else
  if [[ ${SYNTAX_CHECK_REQUIRE_ANSIBLE:-0} == "1" ]]; then
    fail "ansible-core not on PATH — cannot run ludus_progress self-test (SYNTAX_CHECK_REQUIRE_ANSIBLE=1)"
  else
    echo "  SKIPPED — ansible-core is not on PATH; the plugin import needs it."
    ansible_skipped=1
  fi
fi
echo
echo "----------------------------------------------------------------------"
echo
echo "[5/5] variant filter self-test (ci/variant-filter-selftest.py)"
if python3 "$repo_root/ci/variant-filter-selftest.py"; then
  pass "variant filter self-test"
else
  fail "variant filter self-test"
fi
if [[ $failures -ne 0 ]]; then
  echo "RESULT: FAILED ($failures check group(s) failed)"
  exit 1
fi
if [[ ${ansible_skipped:-0} == "1" ]]; then
  echo "RESULT: PASSED (DEGRADED — YAML parse + path resolution only, no ansible syntax check)"
else
  echo "RESULT: PASSED (ansible syntax check + YAML parse + path resolution)"
fi
exit 0
