"""The drive-train expectations in ``diagnostics/check_mirror_retirement.py``
must be the rows the assembly actually places each component with.

The diagnostic executes at import (it reads a machine-local golden pose dump),
so this reads its ``expect(DT, ...)`` calls from source and evaluates their
rows against the SolidWorks-free assembly module.  Codex P3 on #814: 485eaf434
phased MHA-059 (``pinion-lift-rod``) by ``LIFT_ROD_ROWS`` but the validator
still expected IDENTITY, a false ``drow`` failure.  Codex on #960 (T_mz5):
R1 moved the crank family onto ``X_CRANK_FIT``/``Y_CRANK_FIT`` but the
validator still expected ``X_CRANK``/``Y_CRANK``, a false ``dpos`` failure
for five components -- so translations are cross-checked too.
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


def _placement_positions() -> dict[str, list[float]]:
    """Translation of every stem the assembly places from exactly one call
    site whose position evaluates against module-level symbols (positions
    built from loop or function locals are left out)."""
    by_stem: dict[str, list[ast.expr]] = {}
    for call in _calls(ASSEMBLY, "place_component"):
        stem = call.args[1]
        if isinstance(stem, ast.Constant) and len(call.args) >= 3:
            by_stem.setdefault(stem.value, []).append(call.args[2])
    placed = {}
    for stem, positions in by_stem.items():
        if len(positions) != 1:
            continue
        code = compile(ast.Expression(positions[0]), str(ASSEMBLY), "eval")
        try:
            placed[stem] = eval(code, dict(vars(drive)))
        except NameError:
            continue
    return placed


def _drive_train_expect_calls() -> list[tuple[str, ast.Call]]:
    found = []
    for call in _calls(DIAGNOSTIC, "expect"):
        asm, comp = call.args[0], call.args[1]
        if (
            isinstance(asm, ast.Name)
            and asm.id == "DT"
            and isinstance(comp, ast.Constant)
        ):
            found.append((comp.value, call))
    return found


def _drive_train_expectations() -> list[tuple[str, ast.expr]]:
    return [(comp, call.args[3]) for comp, call in _drive_train_expect_calls()]


def _diagnostic_eval(expr: ast.expr):
    namespace = {**vars(_transforms), "d": drive}
    return eval(compile(ast.Expression(expr), str(DIAGNOSTIC), "eval"), namespace)


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


def _position_expectations() -> list[tuple[str, ast.expr]]:
    """Diagnostic translations that evaluate against the assembly module alone
    (helpers such as ``on_shaft`` are diagnostic locals and are left out)."""
    found = []
    for component, call in _drive_train_expect_calls():
        if component.rsplit("-", 1)[0] not in PLACED_AT:
            continue
        try:
            _diagnostic_eval(call.args[2])
        except NameError:
            continue
        found.append((component, call.args[2]))
    return found


PLACED_AT = _placement_positions()
POSITIONED = _position_expectations()


def test_the_cross_check_covers_the_crank_family_translations() -> None:
    covered = {component for component, _ in POSITIONED}
    assert {
        "crankshaft-1",
        "crank-hub-1",
        "crank-hub-pin-1",
        "crank-pinion-1",
        "crank-arm-1",
        "crank-handle-1",
    } <= covered


def test_a_pre_fit_up_crank_translation_is_caught() -> None:
    # Positive control: the pre-R1 expectation, the frame crank axis, sits off
    # the fit-up axis the assembly places the crankshaft on.
    stale = ast.parse("[d.X_CRANK, d.Y_CRANK, d.CRANKSHAFT_Z0]", mode="eval").body
    delta = max(
        abs(a - b)
        for a, b in zip(_diagnostic_eval(stale), PLACED_AT["crankshaft"], strict=True)
    )
    assert delta > 1e-3


@pytest.mark.parametrize(
    ("component", "position"), POSITIONED, ids=[c for c, _ in POSITIONED]
)
def test_expected_translation_is_the_placement_translation(
    component: str, position: ast.expr
) -> None:
    stem = component.rsplit("-", 1)[0]
    expected = _diagnostic_eval(position)
    placed = PLACED_AT[stem]
    delta = max(abs(a - b) for a, b in zip(expected, placed, strict=True))
    assert delta < 1e-9, (
        f"{component}: check_mirror_retirement expects {ast.unparse(position)}, "
        f"{delta:.6f} mm off where the assembly places {stem}"
    )


@pytest.mark.parametrize(("component", "rows"), CHECKED, ids=[c for c, _ in CHECKED])
def test_expected_rows_are_the_placement_rows(component: str, rows: ast.expr) -> None:
    expected = _diagnostic_eval(rows)
    placed = getattr(drive, PLACED[component.rsplit("-", 1)[0]].id)
    assert _max_delta(expected, placed) < 1e-9, (
        f"{component}: check_mirror_retirement expects {ast.unparse(rows)}, "
        f"the assembly places it with {PLACED[component.rsplit('-', 1)[0]].id}"
    )
