#!/usr/bin/env python3
"""Detect non-compliance with the house template rule: templates go through Ludus/packer.
A rule with no detector is a suggestion. This is the detector.
Five checks, each of which corresponds to a way we have actually gone wrong:
  C1  a template's structure was rewritten by us      (the LOCAL PATCH marker)
  C2  a boot ISO uses iso_file instead of iso_url     (drops checksum verification)
  C3  nested boot_iso blocks                          (invalid HCL; -syntax-only misses it)
  C4  a declared checksum is absent from the registry (ADVISORY — see below)
  C5  a registry entry is missing a required field    (an unusable record)
C1-C3 and C5 are violations and fail the run. C4 is ADVISORY and does not: a
template may legitimately pin an ISO we have never held, and failing on that
would make the gate permanently red for a state that is not a rule breach. It is
still reported, because an unregistered pin is usually a gap worth closing.
Exit 0 = compliant, 1 = violations, 2 = could not run (missing inputs).
Usage:
    scripts/check-iso-compliance.py [--templates DIR ...] [--registry PATH]
By default it checks the packer templates shipped in this repo. On a live Ludus
server, point it at the real trees:
    --templates /opt/ludus/packer --templates /opt/ludus/users
"""
from __future__ import annotations
import argparse
import glob
import os
import re
import sys
DEFAULT_REGISTRY = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "ansible/collections/get_sybers.cluster/meta/iso-inventory.yml",
)
CHECKSUM = re.compile(
    r'\biso_(?:checksum|sha1|sha256|sha512|md5)\s*=\s*'
    r'"((?:sha256|sha512|sha1|md5):[0-9a-fA-F]+)"')
REQUIRED_FIELDS = ("iso_file", "iso_checksum", "source_url", "image_class", "derived_from")
def load_registry(path):
    """Read the registry without a yaml dependency — CI images vary and this
    script must not be the reason a gate cannot run."""
    sums, entries, cur = set(), [], None
    if not os.path.exists(path):
        return None, None
    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        if re.match(r"\s*- iso_file:", line):
            if cur:
                entries.append(cur)
            cur = {}
        m = re.match(r"\s*-?\s*([a-z0-9_]+):\s*(.*)$", line)
        if m and cur is not None:
            k, v = m.group(1), m.group(2).strip()
            if k in cur:
                continue
            cur[k] = v
            if k in ("iso_checksum", "iso_sha1", "iso_sha512", "iso_md5") and v not in ("", "null"):
                sums.add(v.lower() if ":" in v else f"{k[4:]}:{v.lower()}")
    if cur:
        entries.append(cur)
    return sums, entries
def block_spans(text, name):
    """Yield (start, end) line indices of each `<name> {` block, by real brace
    depth. A naive '}' scan closes on the first nested block — that bug once made
    a blast-radius estimate report 0 when the true answer was 12."""
    lines = text.splitlines()
    depth, open_at, start_depth = 0, None, 0
    for i, ln in enumerate(lines):
        if re.search(r"\b" + name + r"\s*\{", ln) and open_at is None:
            open_at, start_depth = i, depth
        depth += ln.count("{") - ln.count("}")
        if open_at is not None and depth <= start_depth:
            yield open_at, i
            open_at = None
def boot_iso_spans(text):
    return block_spans(text, "boot_iso")
def check(template_dirs, registry_path):
    violations = []
    sums, entries = load_registry(registry_path)
    registry_present = sums is not None
    if not registry_present:
        print(f"note: no registry at {registry_path} — running structural checks "
              f"(C1-C3) only; C4/C5 skipped", file=sys.stderr)
        sums, entries = set(), []
    for e in entries:
        missing = [f for f in REQUIRED_FIELDS if f not in e]
        if missing:
            violations.append(("C5", registry_path,
                               f"entry {e.get('iso_file', '?')} missing: {', '.join(missing)}"))
        if e.get("source_url") == "null" and "source_url_note" not in e:
            violations.append(("C5", registry_path,
                               f"entry {e.get('iso_file','?')} has a null source_url with no "
                               f"source_url_note — silence reads as 'nobody looked'"))
    files = []
    for d in template_dirs:
        files += glob.glob(os.path.join(d, "**", "*.pkr.hcl"), recursive=True)
    for f in sorted(files):
        text = open(f, errors="replace").read()
        short = f.replace("/opt/ludus/", "").replace(os.getcwd() + "/", "")
        if "LOCAL PATCH (ISO-REDIRECT)" in text:
            violations.append(("C1", short,
                               "carries a LOCAL PATCH marker — template was rewritten out of band. "
                               "Revert it and use iso_download_pve instead."))
        spans = list(boot_iso_spans(text))
        for a, b in spans:
            inner = "\n".join(text.splitlines()[a + 1:b])
            if re.search(r"\bboot_iso\s*\{", inner):
                violations.append(("C3", short,
                                   f"nested boot_iso block at line {a + 1} — packer rejects this "
                                   f"('Blocks of type \"boot_iso\" are not expected here')"))
        for a, b in spans:
            block = "\n".join(text.splitlines()[a:b + 1])
            has_file = re.search(r"^\s*iso_file\s*=", block, re.M)
            has_url = re.search(r"^\s*iso_url\s*=", block, re.M)
            if has_file and not has_url:
                violations.append(("C2", short,
                                   f"boot_iso at line {a + 1} sets iso_file with no iso_url — "
                                   f"this skips Proxmox's checksum verification"))
        lines = text.splitlines()
        masked = list(lines)
        for a, b in spans:
            for i in range(a, b + 1):
                masked[i] = ""
        for a, b in block_spans(text, "additional_iso_files"):
            for i in range(a, b + 1):
                masked[i] = ""
        outer = "\n".join(masked)
        if re.search(r"^\s*iso_file\s*=", outer, re.M) and not re.search(r"^\s*iso_url\s*=", outer, re.M):
            violations.append(("C2", short,
                               "sets iso_file at the top level with no iso_url — "
                               "this skips Proxmox's checksum verification"))
        for m in (CHECKSUM.finditer(text) if registry_present else ()):
            c = m.group(1).lower()
            if c not in sums:
                violations.append(("C4", short,
                                   f"pins {c[:24]}… which is not in the ISO registry"))
    fatal = [v for v in violations if v[0] != "C4"]
    return (1 if fatal else 0), violations
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--templates", action="append", default=None)
    ap.add_argument("--registry", default=DEFAULT_REGISTRY)
    a = ap.parse_args()
    dirs = a.templates or [os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "templates")]
    dirs = [d for d in dirs if os.path.isdir(d)]
    if not dirs:
        print("no template directories to check — nothing to do")
        return 0
    rc, violations = check(dirs, a.registry)
    if rc == 2:
        return 2
    codes = {
        "C1": "template rewritten out of band",
        "C2": "iso_file without iso_url (no checksum verification)",
        "C3": "nested boot_iso (invalid HCL)",
        "C4": "checksum not in the ISO registry [ADVISORY — does not fail the run]",
        "C5": "unusable registry entry",
    }
    if not violations:
        n = sum(len(glob.glob(os.path.join(d, "**", "*.pkr.hcl"), recursive=True)) for d in dirs)
        scope = (f"against {a.registry}" if os.path.exists(a.registry)
                 else "(structural checks only — no registry on this branch)")
        print(f"ISO compliance: OK — {n} template(s) checked {scope}")
        return 0
    fatal = [v for v in violations if v[0] != "C4"]
    print("ISO COMPLIANCE — templates go through Ludus/packer"
          + ("" if fatal else "  (advisories only; nothing fails the run)") + "\n")
    for code in sorted(codes):
        hits = [v for v in violations if v[0] == code]
        if not hits:
            continue
        print(f"  [{code}] {codes[code]} — {len(hits)}")
        for _, where, why in hits:
            print(f"      {where}\n          {why}")
        print()
    return 1 if fatal else 0
if __name__ == "__main__":
    sys.exit(main())
