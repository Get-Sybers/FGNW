#!/usr/bin/env bash
# Smoke-test every Packer template the way the Ludus server builds it.
#
# For each templates/<name>/ directory this runs, from inside that directory
# (Ludus uses the template's directory as the working directory):
#
#   packer fmt -check -diff <template>.pkr.hcl
#   packer validate [-evaluate-datasources] -var <ludus vars...> <template>.pkr.hcl
#
# with the same -var set, PKR_VAR_* variables and PROXMOX_* environment that
# buildVMFromTemplateWithPacker() (ludus-api/api_template_management.go)
# passes, and with the Packer plugin set the Ludus server installs
# (scripts/install_ludus_packer.sh). A template that validates here validates
# on a Ludus server; unknown builder attributes, undeclared -vars, unset
# variables and missing files all fail natively.
#
# Usage: scripts/packer_smoke.sh [--no-fmt] [--inspect] [templates-dir]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REFERENCE="${LUDUS_REFERENCE_DIR:-$ROOT/ludus-reference}"
TOOLS="${LUDUS_CI_TOOLS:-$ROOT/.tools}"
TEMPLATES_DIR="$ROOT/templates"
RUN_FMT=1
RUN_INSPECT=0

while [ $# -gt 0 ]; do
  case "$1" in
    --no-fmt) RUN_FMT=0 ;;
    --inspect) RUN_INSPECT=1 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) TEMPLATES_DIR="$1" ;;
  esac
  shift
done

if [ -x "$TOOLS/bin/packer" ] && ! command -v packer >/dev/null 2>&1; then
  export PATH="$TOOLS/bin:$PATH"
fi
command -v packer >/dev/null 2>&1 || { echo "packer not found; run scripts/install_ludus_packer.sh" >&2; exit 2; }

# --- Environment the Ludus server sets for packer build --------------------
export PACKER_PLUGIN_PATH="${PACKER_PLUGIN_PATH:-$TOOLS/packer-plugins}"
export PACKER_CONFIG_DIR="${PACKER_CONFIG_DIR:-$TOOLS/packer-config}"
export PACKER_CACHE_DIR="${PACKER_CACHE_DIR:-$TOOLS/packer-cache}"
export CHECKPOINT_DISABLE=1
# The Proxmox plugin reads these when username/password are empty (Ludus sets the
# user's API token here); the PKR_VAR_ pair is passed as empty strings by Ludus.
export PROXMOX_USERNAME="${PROXMOX_USERNAME:-ludus-ci@pam!ci}"
export PROXMOX_TOKEN="${PROXMOX_TOKEN:-00000000-0000-0000-0000-000000000000}"
export PKR_VAR_proxmox_password=""
export PKR_VAR_proxmox_username=""
mkdir -p "$PACKER_CONFIG_DIR" "$PACKER_CACHE_DIR"

# --- The -var set, read from the vendored Ludus reference -------------------
mapfile -t LUDUS_VARS < <(python3 - "$REFERENCE/packer-variables.json" <<'PY'
import json, sys
spec = json.load(open(sys.argv[1]))
for v in spec["cli_variables"]:
    print(f"{v['name']}={v['example']}")
PY
)
VAR_ARGS=()
for kv in "${LUDUS_VARS[@]}"; do VAR_ARGS+=(-var "$kv"); done

# --- Plugin sanity: the badsectorlabs/proxmox + hashicorp/ansible pair -------
installed="$(packer plugins installed 2>/dev/null || true)"
for required in $(python3 - "$REFERENCE/versions.json" <<'PY'
import json, sys
spec = json.load(open(sys.argv[1]))
for p in spec["plugins"].values():
    print(p["source"])
PY
); do
  if ! grep -q "$required" <<<"$installed"; then
    echo "::error::packer plugin $required is not installed in PACKER_PLUGIN_PATH=$PACKER_PLUGIN_PATH; run scripts/install_ludus_packer.sh" >&2
    exit 2
  fi
done

echo "packer: $(packer version | head -n1)"
echo "plugins:"; while IFS= read -r line; do echo "  $line"; done <<<"$installed"
echo "ludus vars: ${LUDUS_VARS[*]}"
echo

failures=0
count=0
shopt -s nullglob
for tdir in "$TEMPLATES_DIR"/*/; do
  tdir="${tdir%/}"
  files=("$tdir"/*.pkr.hcl "$tdir"/*.pkr.json)
  if [ ${#files[@]} -eq 0 ]; then
    # nested packer files are reported by the structural linter; nothing to validate here
    continue
  fi
  if [ ${#files[@]} -gt 1 ]; then
    echo "::error file=${tdir#"$ROOT"/}::more than one Packer file in $(basename "$tdir")"
    failures=$((failures + 1)); continue
  fi
  pfile="${files[0]}"
  relfile="${pfile#"$ROOT"/}"
  count=$((count + 1))
  echo "=== $relfile"
  (
    cd "$tdir"
    status=0
    if [ "$RUN_FMT" -eq 1 ] && [[ "$pfile" == *.pkr.hcl ]]; then
      if ! packer fmt -check -diff "$(basename "$pfile")"; then
        echo "::error file=$relfile::packer fmt -check failed (run: packer fmt $relfile)"
        status=1
      fi
    fi
    extra=()
    # data blocks (e.g. data "http") are only resolved with -evaluate-datasources;
    # without it their values are unknown and the plugin's checksum validation fails.
    if grep -qE '^[[:space:]]*data[[:space:]]+"' "$(basename "$pfile")"; then
      extra+=(-evaluate-datasources)
    fi
    if ! packer validate "${extra[@]}" "${VAR_ARGS[@]}" "$(basename "$pfile")"; then
      echo "::error file=$relfile::packer validate failed with the Ludus variable set"
      status=1
    fi
    if [ "$RUN_INSPECT" -eq 1 ]; then
      packer inspect "$(basename "$pfile")" || true
    fi
    exit $status
  ) || failures=$((failures + 1))
  echo
done

if [ "$count" -eq 0 ]; then
  echo "no templates found under $TEMPLATES_DIR"
fi
echo "packer_smoke: $count template(s) checked, $failures failure(s)"
[ "$failures" -eq 0 ]
