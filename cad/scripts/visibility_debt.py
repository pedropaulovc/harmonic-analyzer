"""The reference sketches parts still save shown: a debt the release refuses.

Every part save runs ``_visibility.assert_reference_geometry_hidden``, which
fails on any shown sketch the part's builder does not list in its module-level
``SHOWN_SKETCH_ALLOWANCES`` (name -> "<owner>: <reason>").  Each allowance lives
with its part, so deleting one re-keys only that part.  This module reads them
back WITHOUT importing any builder (the dicts are literals, parsed with
``ast``), so the release can refuse to start while any part still lists one,
before a single leaf is dispatched.
"""

from __future__ import annotations

import ast
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
ALLOWANCES_NAME = "SHOWN_SKETCH_ALLOWANCES"


def _module_literal(path: Path, name: str) -> dict[str, str] | None:
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        targets = (
            [node.target]
            if isinstance(node, ast.AnnAssign)
            else getattr(node, "targets", [])
        )
        if any(isinstance(t, ast.Name) and t.id == name for t in targets):
            return ast.literal_eval(node.value)
    return None


def _part_name(path: Path) -> str:
    part = _module_literal(path, "PART_NAME")
    if not isinstance(part, str):
        raise ValueError(f"{path.name} lists {ALLOWANCES_NAME} but no PART_NAME literal")
    return part


def shown_sketch_allowances(scripts_dir: Path = SCRIPTS_DIR) -> dict[str, dict[str, str]]:
    """part name -> its builder's ``SHOWN_SKETCH_ALLOWANCES``, for every builder
    that declares one (an empty dict included, so a stale declaration shows)."""
    found: dict[str, dict[str, str]] = {}
    for path in sorted(scripts_dir.glob("build_*.py")):
        if ALLOWANCES_NAME not in path.read_text(encoding="utf-8"):
            continue
        allowances = _module_literal(path, ALLOWANCES_NAME)
        if allowances is None:
            continue
        found[_part_name(path)] = dict(allowances)
    return found


def assert_no_visibility_debt(scripts_dir: Path = SCRIPTS_DIR) -> None:
    """Release gate: no part may ship a reference sketch shown."""
    debt = [
        f"{part}: {', '.join(sorted(entries))}"
        for part, entries in sorted(shown_sketch_allowances(scripts_dir).items())
        if entries
    ]
    if debt:
        raise RuntimeError(
            "release blocked: parts still save reference sketches shown "
            f"({ALLOWANCES_NAME}): {'; '.join(debt)}"
        )
