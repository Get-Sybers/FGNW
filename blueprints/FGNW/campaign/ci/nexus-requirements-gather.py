"""
Gather Nexus cache requirements with two methods:
  1) from blueprints/config content
  2) from live deploy logs (download/install failures)
"""
from __future__ import annotations
import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import yaml
URL_RE = re.compile(r"https?://[^\s\"'<>]+")
YAML_GLOB = ("*.yml", "*.yaml")
@dataclass
class UrlFact:
    file: str
    path: str
    url: str
def _load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)
def _walk_yaml(obj: Any, path: str = "$"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_yaml(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_yaml(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        for url in URL_RE.findall(obj):
            yield path, url
def _scan_yaml_tree(root: Path) -> list[UrlFact]:
    facts: list[UrlFact] = []
    for glob in YAML_GLOB:
        for path in sorted(root.rglob(glob)):
            try:
                doc = _load_yaml(path)
            except Exception:
                continue
            for yaml_path, url in _walk_yaml(doc):
                facts.append(
                    UrlFact(
                        file=str(path),
                        path=yaml_path,
                        url=url.rstrip(".,)"),
                    )
                )
    return facts
def gather_from_blueprint(repo_root: Path) -> dict[str, Any]:
    campaign_root = repo_root / "blueprints/FGNW/campaign"
    requirements_path = campaign_root / "ludus-requirements.yml"
    requirements_doc = _load_yaml(requirements_path)
    nexus_block = requirements_doc.get("nexus", {}) if isinstance(requirements_doc, dict) else {}
    urls = _scan_yaml_tree(campaign_root / "ansible")
    urls += _scan_yaml_tree(repo_root / "ansible/roles")
    urls += _scan_yaml_tree(repo_root / "ansible/collections/get_sybers.infra/playbooks")
    nexus_urls: list[dict[str, str]] = []
    external_urls: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for fact in urls:
        key = (fact.file, fact.path, fact.url)
        if key in seen:
            continue
        seen.add(key)
        row = {"file": fact.file, "yaml_path": fact.path, "url": fact.url}
        if "192.0.2.2:8081" in fact.url or "/repository/" in fact.url:
            nexus_urls.append(row)
        else:
            external_urls.append(row)
    repos = nexus_block.get("repos_this_blueprint_depends_on", [])
    raw_hosted = next((repo for repo in repos if isinstance(repo, dict) and repo.get("name") == "raw-hosted"), {})
    return {
        "source": str(requirements_path),
        "nexus_declared": {
            "required": bool(nexus_block.get("required", False)),
            "repos": repos,
            "artifacts": raw_hosted.get("artifacts", []),
        },
        "discovered_urls": {
            "external": external_urls,
            "nexus": nexus_urls,
        },
    }
def gather_from_live_log(log_path: Path) -> dict[str, Any]:
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    fail_markers = (
        "fatal:",
        "failed!",
        "connection refused",
        "timed out",
        "temporary failure in name resolution",
        "could not resolve",
        "unable to connect",
        "status code was",
        "404",
        "403",
    )
    download_markers = ("get_url", "win_get_url", "download", "chocolatey", "uri:")
    nexus_markers = ("192.0.2.2:8081", "nexus", "raw-hosted", "/repository/")
    findings: list[dict[str, Any]] = []
    seen: set[tuple[int, tuple[str, ...]]] = set()
    for i, line in enumerate(lines):
        ll = line.lower()
        if not any(marker in ll for marker in fail_markers):
            continue
        window = "\n".join(lines[max(0, i - 2) : i + 3])
        window_lower = window.lower()
        if not any(marker in window_lower for marker in download_markers):
            continue
        urls = sorted({u.rstrip(".,)") for u in URL_RE.findall(window)})
        key = (i, tuple(urls))
        if key in seen:
            continue
        seen.add(key)
        findings.append(
            {
                "line": i + 1,
                "nexus_related": any(marker in ll for marker in nexus_markers)
                or any(any(marker in url.lower() for marker in nexus_markers) for url in urls),
                "urls": urls,
                "context": window,
            }
        )
    return {"source": str(log_path), "failures": findings}
def main() -> int:
    parser = argparse.ArgumentParser(description="Gather Nexus requirements from blueprint facts or live deploy logs.")
    sub = parser.add_subparsers(dest="mode", required=True)
    p_blueprint = sub.add_parser("blueprint", help="Gather requirements from blueprint/config facts.")
    p_blueprint.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[4]),
        help="Repository root path (default: auto-detected).",
    )
    p_blueprint.add_argument("--format", choices=("json", "yaml"), default="json")
    p_live = sub.add_parser("live-log", help="Gather requirements from live deploy failure logs.")
    p_live.add_argument("--log-file", required=True, help="Path to deploy log file to analyze.")
    p_live.add_argument("--format", choices=("json", "yaml"), default="json")
    args = parser.parse_args()
    if args.mode == "blueprint":
        payload = gather_from_blueprint(Path(args.repo_root))
    else:
        payload = gather_from_live_log(Path(args.log_file))
    if args.format == "yaml":
        print(yaml.safe_dump(payload, sort_keys=False))
    else:
        print(json.dumps(payload, indent=2))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
