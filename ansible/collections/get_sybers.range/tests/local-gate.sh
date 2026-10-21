#!/usr/bin/env bash
set -euo pipefail
COLLECTION_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ANSIBLE_COLLECTIONS_PATH="$(cd "$COLLECTION_ROOT/../../.." && pwd):/root/.ansible/collections"
export ANSIBLE_COLLECTIONS_PATH
cd "$COLLECTION_ROOT"
if [[ $# -gt 0 ]]; then
  tests=()
  for t in "$@"; do tests+=("tests/${t#tests/}"); done
else
  mapfile -t tests < <(ls tests/test-*.yml 2> /dev/null)
fi
[[ ${#tests[@]} -gt 0 ]] || {
  echo "no tests found"
  exit 1
}
mkdir -p tests/output
fail=0
check_recap() {
  local log="$1" require_changed0="$2" bad=0
  while IFS= read -r line; do
    if ! grep -qE 'failed=0' <<< "$line" || ! grep -qE 'unreachable=0' <<< "$line"; then
      echo "  RECAP FAILURE: $line"
      bad=1
    fi
    if [[ $require_changed0 == yes ]] && ! grep -qE 'changed=0' <<< "$line"; then
      echo "  NOT IDEMPOTENT: $line"
      bad=1
    fi
  done < <(grep -E '^\S+\s+: ok=' "$log" || true)
  grep -qE '^\S+\s+: ok=' "$log" || {
    echo "  NO RECAP in $log"
    bad=1
  }
  # record the verdict in the gate's own flag; the caller keeps going to the next test
  [[ $bad -eq 0 ]] || fail=1
}
for t in "${tests[@]}"; do
  name="$(basename "$t" .yml)"
  echo "=== $name : syntax-check ==="
  ansible-playbook --syntax-check "$t"
  echo "=== $name : run 1 ==="
  log1="tests/output/${name}.run1.log"
  ansible-playbook "$t" > "$log1" 2>&1 || {
    echo "  RUN 1 EXITED NONZERO"
    tail -40 "$log1"
    fail=1
    continue
  }
  check_recap "$log1" no
  echo "=== $name : run 2 (must be changed=0) ==="
  log2="tests/output/${name}.run2.log"
  ansible-playbook "$t" > "$log2" 2>&1 || {
    echo "  RUN 2 EXITED NONZERO"
    tail -40 "$log2"
    fail=1
    continue
  }
  check_recap "$log2" yes
done
if [[ $fail -ne 0 ]]; then
  echo "GATE: FAILED (logs in tests/output/)"
  exit 1
fi
echo "GATE: PASSED (${#tests[@]} test play(s): syntax OK, runs clean, second run changed=0)"
