"""The drive-train expectations in ``diagnostics/check_mirror_retirement.py``
must be the rows the assembly actually places each component with.

The diagnostic executes at import (it reads a machine-local golden pose dump),
so this reads its ``expect(DT, ...)`` calls from source and evaluates their
rows against the SolidWorks-free assembly module.  Codex P3 on #814: 485eaf434
phased MHA-059 (``pinion-lift-rod``) by ``LIFT_ROD_ROWS`` but the validator
still expected IDENTITY, a false ``drow`` failure.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import _transforms
import build_drive_train_assembly as drive

SCRIPTS = Path(__file__).resolve().parent
DIAGNOSTIC = SCRIPTS / "diagnostics" / "check_mirror_retirement.py"
ASSEMBLY = SCRIPTS / "build_drive_train_assembly.py"


def _calls(path: Path, name: str) -> list[ast.Call]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == name
    ]


def _placement_rows() -> dict[str, ast.expr]:
    """Rows argument of every stem the assembly places from exactly one call
    site with a module-level rows symbol (loop-local rows are left out)."""
    by_stem: dict[str, list[ast.expr]] = {}
    for call in _calls(ASSEMBLY, "place_component"):
        stem = call.args[1]
        if isinstance(stem, ast.Constant) and len(call.args) >= 5:
            by_stem.setdefault(stem.value, []).append(call.args[4])
    return {
        stem: rows[0]
        for stem, rows in by_stem.items()
        if len(rows) == 1
        and isinstance(rows[0], ast.Name)
        and hasattr(drive, rows[0].id)
    }


def _drive_train_expectations() -> list[tuple[str, ast.expr]]:
    found = []
    for call in _calls(DIAGNOSTIC, "expect"):
        asm, comp = call.args[0], call.args[1]
        if (
            isinstance(asm, ast.Name)
            and asm.id == "DT"
            and isinstance(comp, ast.Constant)
        ):
            found.append((comp.value, call.args[3]))
    return found


def _max_delta(a, b) -> float:
    return max(
        abs(x - y)
        for ra, rb in zip(a, b, strict=True)
        for x, y in zip(ra, rb, strict=True)
    )


PLACED = _placement_rows()
CHECKED = [
    (component, rows)
    for component, rows in _drive_train_expectations()
    if component.rsplit("-", 1)[0] in PLACED
]


def test_the_cross_check_covers_the_pinion_rig() -> None:
    covered = {component for component, _ in CHECKED}
    assert {"pinion-lift-rod-1", "pinion-lever-1", "pinion-arbor-1"} <= covered


@pytest.mark.parametrize(("component", "rows"), CHECKED, ids=[c for c, _ in CHECKED])
def test_expected_rows_are_the_placement_rows(component: str, rows: ast.expr) -> None:
    namespace = {**vars(_transforms), "d": drive}
    expected = eval(compile(ast.Expression(rows), str(DIAGNOSTIC), "eval"), namespace)
    placed = getattr(drive, PLACED[component.rsplit("-", 1)[0]].id)
    assert _max_delta(expected, placed) < 1e-9, (
        f"{component}: check_mirror_retirement expects {ast.unparse(rows)}, "
        f"the assembly places it with {PLACED[component.rsplit('-', 1)[0]].id}"
    )
