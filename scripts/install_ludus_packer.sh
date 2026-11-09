#!/usr/bin/env bash
# Install Packer and the Packer plugins at the versions the Ludus server pins.
#
# Versions come from ludus-reference/versions.json (derived from
# ludus-server/dependency_updates.go) and can be overridden with
# PACKER_VERSION, PROXMOX_PLUGIN_VERSION and ANSIBLE_PLUGIN_VERSION.
# Packer is fetched from releases.hashicorp.com exactly like the Ludus
# installer does, verified against the published SHA256SUMS; plugins are
# installed with `packer plugins install <source> v<version>` (the command the
# Ludus server runs), falling back to fetching the plugin through the GitHub
# release API (binary + checksum) when GitHub's asset CDN returns 504s.
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

read -r REF_PACKER REF_PROXMOX_SRC REF_PROXMOX_VER REF_ANSIBLE_SRC REF_ANSIBLE_VER < <(
  python3 - "$REFERENCE/versions.json" << 'PY'
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
  *)
    echo "unsupported OS: $(uname -s)" >&2
    exit 1
    ;;
esac
case "$(uname -m)" in
  x86_64 | amd64) ARCH=amd64 ;;
  aarch64 | arm64) ARCH=arm64 ;;
  *)
    echo "unsupported architecture: $(uname -m)" >&2
    exit 1
    ;;
esac

sha256_check() { # <file> <expected>
  local actual
  if command -v sha256sum > /dev/null 2>&1; then actual="$(sha256sum "$1" | awk '{print $1}')"; else actual="$(shasum -a 256 "$1" | awk '{print $1}')"; fi
  [[ $actual == "$2" ]] || {
    echo "checksum mismatch for $1: $actual != $2" >&2
    return 1
  }
}
# --- GitHub release assets via the API (resilient to releases/download 504s) ---
# GitHub's asset CDN (https://github.com/<owner>/<repo>/releases/download/...)
# has intermittently returned HTTP 504 for both plugin binaries and their
# SHA256SUMS files, while api.github.com and its per-asset download endpoint
# stay reachable. The plugin fallback below fetches everything through the API.
# Unauthenticated on public repos; a token in PACKER_GITHUB_API_TOKEN or
# GITHUB_TOKEN, when set, is sent only to lift the anonymous rate limit and is
# never written anywhere.
gh_release_json() { # <owner> <repo> <version> <dest-file>
  local tok="${PACKER_GITHUB_API_TOKEN:-${GITHUB_TOKEN:-}}" auth=()
  [[ -n $tok ]] && auth=(-H "Authorization: Bearer $tok")
  curl -fsSL -o "$4" -H "Accept: application/vnd.github+json" "${auth[@]}" \
    "https://api.github.com/repos/$1/$2/releases/tags/v$3"
}
gh_asset_field() { # <asset-name> <release-json> <id|digest> -> prints value or nothing
  python3 -c 'import json, sys
name, path, field = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    assets = json.load(open(path)).get("assets", [])
except Exception:
    sys.exit(0)
for a in assets:
    if a.get("name") == name:
        if field == "digest":
            d = a.get("digest") or ""
            if d.startswith("sha256:"):
                print(d.split(":", 1)[1])
        else:
            print(a.get(field, ""))
        break' "$1" "$2" "$3"
}
gh_asset_download() { # <owner> <repo> <asset-id> <dest>
  local tok="${PACKER_GITHUB_API_TOKEN:-${GITHUB_TOKEN:-}}" auth=()
  [[ -n $tok ]] && auth=(-H "Authorization: Bearer $tok")
  curl -fsSL -o "$4" -H "Accept: application/octet-stream" "${auth[@]}" \
    "https://api.github.com/repos/$1/$2/releases/assets/$3"
}

unzip_to() { # <zip> <dir>
  if command -v unzip > /dev/null 2>&1; then unzip -qq -o "$1" -d "$2"; else python3 -c 'import sys,zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])' "$1" "$2"; fi
}

# --- Packer -------------------------------------------------------------------
if [[ -x "$BIN/packer" ]] && [[ "$("$BIN/packer" version 2> /dev/null | head -n1)" == "Packer v$PACKER_VERSION" ]]; then
  echo "packer v$PACKER_VERSION already installed in $BIN"
else
  base="https://releases.hashicorp.com/packer/$PACKER_VERSION"
  zip="$TOOLS/downloads/packer_${PACKER_VERSION}_${OS}_${ARCH}.zip"
  echo "downloading packer v$PACKER_VERSION ($OS/$ARCH)"
  curl -fsSL -o "$zip" "$base/packer_${PACKER_VERSION}_${OS}_${ARCH}.zip"
  curl -fsSL -o "$zip.sums" "$base/packer_${PACKER_VERSION}_SHA256SUMS"
  expected="$(awk -v f="packer_${PACKER_VERSION}_${OS}_${ARCH}.zip" '$2==f {print $1}' "$zip.sums")"
  [[ -n $expected ]] || {
    echo "no checksum for packer_${PACKER_VERSION}_${OS}_${ARCH}.zip in SHA256SUMS" >&2
    exit 1
  }
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
  local source="$1" version="$2" name owner repo zip sums expected tmp binary rjson zip_id sums_id
  name="${source##*/}"
  owner="$(basename "$(dirname "$source")")"
  repo="packer-plugin-$name"
  if packer plugins installed 2> /dev/null | grep -q "/${source}/packer-plugin-${name}_v${version}_"; then
    echo "plugin $source v$version already installed"
    return 0
  fi
  echo "installing plugin $source v$version"
  if packer plugins install "$source" "v$version"; then
    return 0
  fi
  echo "packer plugins install failed (GitHub asset CDN unreachable?); fetching the plugin via the GitHub release API"
  binary="${repo}_v${version}_${PLUGIN_API}_${OS}_${ARCH}"
  zip="$TOOLS/downloads/${binary}.zip"
  rjson="$TOOLS/downloads/${repo}_v${version}_release.json"
  gh_release_json "$owner" "$repo" "$version" "$rjson"
  zip_id="$(gh_asset_field "${binary}.zip" "$rjson" id)"
  [[ -n $zip_id ]] || {
    echo "release v$version has no asset ${binary}.zip" >&2
    return 1
  }
  gh_asset_download "$owner" "$repo" "$zip_id" "$zip"
  # Checksum: the per-asset API digest when present, else the SHA256SUMS asset
  # (fetched through the same API endpoint, not the 504-prone asset CDN).
  expected="$(gh_asset_field "${binary}.zip" "$rjson" digest)"
  if [[ -z $expected ]]; then
    sums="$TOOLS/downloads/${repo}_v${version}_SHA256SUMS"
    sums_id="$(gh_asset_field "${repo}_v${version}_SHA256SUMS" "$rjson" id)"
    [[ -n $sums_id ]] && gh_asset_download "$owner" "$repo" "$sums_id" "$sums"
    expected="$(awk -v f="${binary}.zip" '$2==f {print $1}' "$sums" 2> /dev/null)"
  fi
  [[ -n $expected ]] || {
    echo "no checksum available for ${binary}.zip (no API digest and no SHA256SUMS)" >&2
    return 1
  }
  sha256_check "$zip" "$expected"
  tmp="$(mktemp -d)"
  unzip_to "$zip" "$tmp"
  # Place the binary in the nested plugin layout Packer >= 1.9 reads from
  # PACKER_PLUGIN_PATH (<path>/<source>/<binary> + <binary>_SHA256SUM). This is
  # the layout `packer plugins install` produces and works on Packer 1.9.4,
  # which predates `packer plugins install --path`.
  mkdir -p "$PLUGINS/$source"
  install -m 0755 "$tmp/$binary" "$PLUGINS/$source/$binary"
  if command -v sha256sum > /dev/null 2>&1; then
    sha256sum "$PLUGINS/$source/$binary" | awk '{print $1}' > "$PLUGINS/$source/${binary}_SHA256SUM"
  else shasum -a 256 "$PLUGINS/$source/$binary" | awk '{print $1}' > "$PLUGINS/$source/${binary}_SHA256SUM"; fi
  rm -rf "$tmp"
  packer plugins installed | grep -q "/${source}/${binary}" || {
    echo "plugin $source v$version is not visible to packer after manual install" >&2
    return 1
  }
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
if [[ -n ${GITHUB_PATH:-} ]]; then echo "$BIN" >> "$GITHUB_PATH"; fi
if [[ -n ${GITHUB_ENV:-} ]]; then echo "PACKER_PLUGIN_PATH=$PLUGINS" >> "$GITHUB_ENV"; fi
