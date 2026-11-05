#!/usr/bin/env bash
# Install Packer and the Packer plugins at the versions the Ludus server pins.
#
# Versions come from ludus-reference/versions.json (derived from
# ludus-server/dependency_updates.go) and can be overridden with
# PACKER_VERSION, PROXMOX_PLUGIN_VERSION and ANSIBLE_PLUGIN_VERSION.
# Packer is fetched from releases.hashicorp.com exactly like the Ludus
# installer does, verified against the published SHA256SUMS; plugins are
# installed with `packer plugins install <source> v<version>` (the command the
# Ludus server runs), falling back to the GitHub release archive when the
# GitHub API is unreachable.
#
# Usage: scripts/install_ludus_packer.sh [tools-dir]      (default: <repo>/.tools)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REFERENCE="${LUDUS_REFERENCE_DIR:-$ROOT/ludus-reference}"
TOOLS="${1:-${LUDUS_CI_TOOLS:-$ROOT/.tools}}"
BIN="$TOOLS/bin"
PLUGINS="$TOOLS/packer-plugins"
PLUGIN_API="${PACKER_PLUGIN_API_VERSION:-x5.0}"
mkdir -p "$BIN" "$PLUGINS" "$TOOLS/downloads"

read -r REF_PACKER REF_PROXMOX_SRC REF_PROXMOX_VER REF_ANSIBLE_SRC REF_ANSIBLE_VER < <(python3 - "$REFERENCE/versions.json" <<'PY'
import json, sys
v = json.load(open(sys.argv[1]))
p = v["plugins"]
print(v["packer"]["min_version"], p["proxmox"]["source"], p["proxmox"]["version"], p["ansible"]["source"], p["ansible"]["version"])
PY
)
PACKER_VERSION="${PACKER_VERSION:-$REF_PACKER}"
PROXMOX_PLUGIN_VERSION="${PROXMOX_PLUGIN_VERSION:-$REF_PROXMOX_VER}"
ANSIBLE_PLUGIN_VERSION="${ANSIBLE_PLUGIN_VERSION:-$REF_ANSIBLE_VER}"

case "$(uname -s)" in
  Linux) OS=linux ;;
  Darwin) OS=darwin ;;
  *) echo "unsupported OS: $(uname -s)" >&2; exit 1 ;;
esac
case "$(uname -m)" in
  x86_64|amd64) ARCH=amd64 ;;
  aarch64|arm64) ARCH=arm64 ;;
  *) echo "unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac

sha256_check() { # <file> <expected>
  local actual
  if command -v sha256sum >/dev/null 2>&1; then actual="$(sha256sum "$1" | awk '{print $1}')"; else actual="$(shasum -a 256 "$1" | awk '{print $1}')"; fi
  [ "$actual" = "$2" ] || { echo "checksum mismatch for $1: $actual != $2" >&2; return 1; }
}
unzip_to() { # <zip> <dir>
  if command -v unzip >/dev/null 2>&1; then unzip -qq -o "$1" -d "$2"; else python3 -c 'import sys,zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])' "$1" "$2"; fi
}

# --- Packer -------------------------------------------------------------------
if [ -x "$BIN/packer" ] && [ "$("$BIN/packer" version 2>/dev/null | head -n1)" = "Packer v$PACKER_VERSION" ]; then
  echo "packer v$PACKER_VERSION already installed in $BIN"
else
  base="https://releases.hashicorp.com/packer/$PACKER_VERSION"
  zip="$TOOLS/downloads/packer_${PACKER_VERSION}_${OS}_${ARCH}.zip"
  echo "downloading packer v$PACKER_VERSION ($OS/$ARCH)"
  curl -fsSL -o "$zip" "$base/packer_${PACKER_VERSION}_${OS}_${ARCH}.zip"
  curl -fsSL -o "$zip.sums" "$base/packer_${PACKER_VERSION}_SHA256SUMS"
  expected="$(awk -v f="packer_${PACKER_VERSION}_${OS}_${ARCH}.zip" '$2==f {print $1}' "$zip.sums")"
  [ -n "$expected" ] || { echo "no checksum for packer_${PACKER_VERSION}_${OS}_${ARCH}.zip in SHA256SUMS" >&2; exit 1; }
  sha256_check "$zip" "$expected"
  tmp="$(mktemp -d)"
  unzip_to "$zip" "$tmp"
  install -m 0755 "$tmp/packer" "$BIN/packer"
  rm -rf "$tmp"
fi
export PATH="$BIN:$PATH"
export PACKER_PLUGIN_PATH="$PLUGINS"
export CHECKPOINT_DISABLE=1
packer version

# --- Plugins -----------------------------------------------------------------
install_plugin() { # <source like github.com/owner/name> <version>
  local source="$1" version="$2" name owner repo zip sums expected tmp binary
  name="${source##*/}"
  owner="$(basename "$(dirname "$source")")"
  repo="packer-plugin-$name"
  if packer plugins installed 2>/dev/null | grep -q "/${source}/packer-plugin-${name}_v${version}_"; then
    echo "plugin $source v$version already installed"
    return 0
  fi
  echo "installing plugin $source v$version"
  if packer plugins install "$source" "v$version"; then
    return 0
  fi
  echo "packer plugins install failed (GitHub API unreachable?); falling back to the release archive"
  binary="${repo}_v${version}_${PLUGIN_API}_${OS}_${ARCH}"
  zip="$TOOLS/downloads/${binary}.zip"
  sums="$TOOLS/downloads/${repo}_v${version}_SHA256SUMS"
  curl -fsSL -o "$zip" "https://github.com/$owner/$repo/releases/download/v$version/${binary}.zip"
  curl -fsSL -o "$sums" "https://github.com/$owner/$repo/releases/download/v$version/${repo}_v${version}_SHA256SUMS"
  expected="$(awk -v f="${binary}.zip" '$2==f {print $1}' "$sums")"
  [ -n "$expected" ] || { echo "no checksum for ${binary}.zip" >&2; return 1; }
  sha256_check "$zip" "$expected"
  tmp="$(mktemp -d)"
  unzip_to "$zip" "$tmp"
  # Place the binary in the nested plugin layout Packer >= 1.9 reads from
  # PACKER_PLUGIN_PATH (<path>/<source>/<binary> + <binary>_SHA256SUM). This is
  # the layout `packer plugins install` produces and works on Packer 1.9.4,
  # which predates `packer plugins install --path`.
  mkdir -p "$PLUGINS/$source"
  install -m 0755 "$tmp/$binary" "$PLUGINS/$source/$binary"
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$PLUGINS/$source/$binary" | awk '{print $1}' > "$PLUGINS/$source/${binary}_SHA256SUM"
  else shasum -a 256 "$PLUGINS/$source/$binary" | awk '{print $1}' > "$PLUGINS/$source/${binary}_SHA256SUM"; fi
  rm -rf "$tmp"
  packer plugins installed | grep -q "/${source}/${binary}" || { echo "plugin $source v$version is not visible to packer after manual install" >&2; return 1; }
}

install_plugin "$REF_PROXMOX_SRC" "$PROXMOX_PLUGIN_VERSION"
install_plugin "$REF_ANSIBLE_SRC" "$ANSIBLE_PLUGIN_VERSION"

echo
echo "installed plugins:"
packer plugins installed | sed 's/^/  /'
echo
echo "export PATH=\"$BIN:\$PATH\""
echo "export PACKER_PLUGIN_PATH=\"$PLUGINS\""
# Propagate to later GitHub Actions steps when running in a workflow.
if [ -n "${GITHUB_PATH:-}" ]; then echo "$BIN" >> "$GITHUB_PATH"; fi
if [ -n "${GITHUB_ENV:-}" ]; then echo "PACKER_PLUGIN_PATH=$PLUGINS" >> "$GITHUB_ENV"; fi
