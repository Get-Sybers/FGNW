"""Shared fixtures: load the linter from scripts/ and build throwaway sources.

The mutation tests edit a copy of the vendored golden Ludus source under
``tests/fixtures/ludus-source`` (a single clean Debian template + an example
blueprint), so the linter's own regression tests never depend on FGNW's real,
evolving template library. ``test_fgnw_source_is_clean`` lints the actual
repository separately.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "ludus_source_lint.py"
FIXTURE = REPO / "tests" / "fixtures" / "ludus-source"


@pytest.fixture(scope="session")
def lint_module():
    spec = importlib.util.spec_from_file_location("ludus_source_lint", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ludus_source_lint"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def reference(lint_module):
    return lint_module.Reference(REPO / "ludus-reference")


@pytest.fixture
def source(tmp_path):
    """A writable copy of the vendored golden Ludus source (tests/fixtures/)."""
    root = tmp_path / "source"
    root.mkdir()
    for name in ("source.yml", "README.md", ".ludus-lint.yml"):
        shutil.copy(FIXTURE / name, root / name)
    for name in ("templates", "blueprints", "ansible"):
        shutil.copytree(FIXTURE / name, root / name)
    # The reference data lives at the repo root; copy it in so that invoking the
    # linter's main() with just --root (as test_cli_exit_codes does) resolves the
    # default <root>/ludus-reference.
    shutil.copytree(REPO / "ludus-reference", root / "ludus-reference")
    return root


@pytest.fixture
def lint(lint_module, reference):
    def _run(root: Path, config: dict | None = None):
        linter = lint_module.Linter(root, reference, config or {})
        findings = linter.run()
        by_rule: dict[str, list] = {}
        for f in findings:
            by_rule.setdefault(f.rule, []).append(f)
        return findings, by_rule

    return _run


def edit(path: Path, old: str, new: str, count: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not found in {path}"
    path.write_text(text.replace(old, new, count), encoding="utf-8")
