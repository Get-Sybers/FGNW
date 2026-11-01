#!/usr/bin/env bash
# sasori-verify.sh — build sasori and run the verify subcommand against a live range.
#
# Run from any directory; the script resolves paths from its own location.
#
# Usage:
#   bash scripts/sasori-verify.sh [--deep] [hostname1 hostname2 ...]
#
# Required env vars (set directly or source a 0600 creds file first):
#   PVE_HOST         Proxmox base URL   e.g. https://pve01:8006
#   PVE_USER         API token user     e.g. emulator@pve
#   PVE_TOKEN_ID     token ID           (the part after the !)
#   PVE_SECRET       token secret
#   RANGE_NUMBER     Ludus range number (integer)
#
# Optional env vars:
#   PVE_NODE             Proxmox node name (default: pve)
#   PVE_INSECURE         1 to skip TLS verify
#   PERSONA_TIMELINES    path to persona-timelines.yml (skip if passing hostnames)
#   PERSONA_OVERRIDES    path to persona-overrides.yml
#
# Example — source creds then check two specific VMs with deep exec test:
#   source /root/.sasori-verify.env   # chmod 0600
#   bash scripts/sasori-verify.sh --deep konoha-ws1 konoha-ws2
#
# Example — check all personas defined in the config:
#   export PERSONA_TIMELINES=/opt/ludus/sources/.../ghosts/persona-timelines.yml
#   bash scripts/sasori-verify.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SASORI_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ── Require required env vars ───────────────────────────────────────────────
missing=()
for v in PVE_HOST PVE_USER PVE_TOKEN_ID PVE_SECRET RANGE_NUMBER; do
    [[ -z "${!v:-}" ]] && missing+=("$v")
done
if [[ "${#missing[@]}" -gt 0 ]]; then
    echo "ERROR: missing required env vars: ${missing[*]}" >&2
    echo "" >&2
    echo "Set them or source a 0600 creds file:" >&2
    echo "  source /path/to/verify-creds.env && bash scripts/sasori-verify.sh" >&2
    echo "" >&2
    echo "Creds file format:" >&2
    echo "  export PVE_HOST=https://pve01:8006" >&2
    echo "  export PVE_USER=emulator@pve" >&2
    echo "  export PVE_TOKEN_ID=verify-token" >&2
    echo "  export PVE_SECRET=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" >&2
    echo "  export RANGE_NUMBER=10" >&2
    exit 1
fi

# ── Build ───────────────────────────────────────────────────────────────────
BIN="$(mktemp -t sasori-XXXXXXXX)"
trap 'rm -f "$BIN"' EXIT

echo "Building sasori from ${SASORI_DIR} ..."
cd "${SASORI_DIR}"
CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o "${BIN}" ./cmd/sasori
echo "Build OK."
echo ""

# ── Run verify ──────────────────────────────────────────────────────────────
"${BIN}" verify "$@"
