"""The drive-train expectations in ``diagnostics/check_mirror_retirement.py``
must be the rows the assembly actually places each component with.

The diagnostic executes at import (it reads a machine-local golden pose dump),
so this reads its ``expect(DT, ...)`` calls from source and evaluates their
rows against the SolidWorks-free assembly module.  Codex P3 on #814: 485eaf434
phased MHA-DT-016 (``pinion-lift-rod``) by ``LIFT_ROD_ROWS`` but the validator
still expected IDENTITY, a false ``drow`` failure. Translations are also
cross-checked against the restored fixed crank axis.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import _transforms
import build_dt_drive_train_assembly as drive

SCRIPTS = Path(__file__).resolve().parent
DIAGNOSTIC = SCRIPTS / "diagnostics" / "check_mirror_retirement.py"
ASSEMBLY = SCRIPTS / "build_dt_drive_train_assembly.py"


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
    assert {"dt-pinion-lift-rod-1", "dt-pinion-lever-1", "dt-pinion-arbor-1"} <= covered


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
        "dt-crankshaft-1",
        "dt-crank-hub-1",
        "vn-crank-hub-pin-1",
        "dt-crank-pinion-1",
        "dt-crank-arm-1",
        "dt-crank-handle-1",
    } <= covered




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


def _shaft_helper_placements() -> dict[str, tuple[ast.expr, ast.expr]]:
    """Station and face passed when the assembly seeds an on-shaft gear."""
    placed = {}
    for call in _calls(ASSEMBLY, "_place_on_shaft"):
        part = call.args[1]
        if isinstance(part, ast.Constant) and isinstance(part.value, str):
            assert part.value not in placed, f"duplicate on-shaft seed: {part.value}"
            placed[part.value] = (call.args[2], call.args[3])
    return placed


def _shaft_diagnostic_expectations() -> dict[str, tuple[ast.expr, ast.expr]]:
    """The diagnostic's on_shaft arguments for the helper-seeded instances."""
    expected = {}
    for call in _calls(DIAGNOSTIC, "expect"):
        if not (isinstance(call.args[0], ast.Name) and call.args[0].id == "DT"):
            continue
        position = call.args[2]
        if not (
            isinstance(position, ast.Call)
            and isinstance(position.func, ast.Name)
            and position.func.id == "on_shaft"
        ):
            continue
        component_node = call.args[1]
        if not isinstance(component_node, (ast.Constant, ast.JoinedStr)):
            continue
        # The cone-gear expectation is in a j loop. Its helper-seeded T120
        # instance is j=0; the rest are copies, not _place_on_shaft calls.
        component = eval(
            compile(ast.Expression(component_node), str(DIAGNOSTIC), "eval"),
            {"j": 0},
        )
        stem = component.rsplit("-", 1)[0]
        assert stem not in expected, f"duplicate on-shaft expectation: {stem}"
        expected[stem] = (position.args[0], position.args[1])
    return expected


SHAFT_HELPER_PLACEMENTS = _shaft_helper_placements()
SHAFT_DIAGNOSTIC_EXPECTATIONS = _shaft_diagnostic_expectations()


def test_on_shaft_cross_check_covers_helper_seeded_gears() -> None:
    assert {"dt-crank-drive-gear", "dt-cone-gear"} <= SHAFT_HELPER_PLACEMENTS.keys()
    assert SHAFT_HELPER_PLACEMENTS.keys() == SHAFT_DIAGNOSTIC_EXPECTATIONS.keys()


@pytest.mark.parametrize("stem", sorted(SHAFT_HELPER_PLACEMENTS))
def test_on_shaft_expectation_matches_assembly_station_and_face(stem: str) -> None:
    expected_station, expected_face = SHAFT_DIAGNOSTIC_EXPECTATIONS[stem]
    placed_station, placed_face = SHAFT_HELPER_PLACEMENTS[stem]
    for label, expected, placed in (
        ("station", expected_station, placed_station),
        ("face", expected_face, placed_face),
    ):
        diagnostic_value = eval(
            compile(ast.Expression(expected), str(DIAGNOSTIC), "eval"),
            {"d": drive, "j": 0},
        )
        assembly_value = eval(
            compile(ast.Expression(placed), str(ASSEMBLY), "eval"),
            dict(vars(drive)),
        )
        assert abs(diagnostic_value - assembly_value) < 1e-9, (
            f"{stem}: diagnostic on_shaft {label} {ast.unparse(expected)} "
            f"differs by {diagnostic_value - assembly_value:.6f} mm "
            f"from assembly _place_on_shaft {ast.unparse(placed)}"
        )


def test_magnifying_bracket_screw_expectations_follow_live_placement() -> None:
    import build_mg_magnifier_assembly as magnifier
    import magnifying_bracket_joint_layout as joint

    assert magnifier.BRACKET_SCREW_POSITIONS is joint.SCREW_POSITIONS
    assert magnifier.BRACKET_SCREW_ROWS == _transforms.ROT_X_NEG90
    # The stock shank runs -Y, so the installed shank must run machine +Z.
    assert [-value for value in magnifier.BRACKET_SCREW_ROWS[1]] == [0.0, 0.0, 1.0]
    tree = ast.parse(DIAGNOSTIC.read_text(encoding="utf-8"))
    loops = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.For)
        and isinstance(node.iter, ast.Call)
        and ast.unparse(node.iter) == "enumerate(m.BRACKET_SCREW_POSITIONS, start=1)"
    ]
    assert len(loops) == 1
    calls = [
        node for node in ast.walk(loops[0])
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "expect"
    ]
    assert len(calls) == 1
    call = calls[0]
    assert ast.literal_eval(call.args[0]) == "mg-magnifier"
    assert ast.literal_eval(call.args[4]) == "vn-magnifying-bracket-screw"
    for index, position in enumerate(magnifier.BRACKET_SCREW_POSITIONS, start=1):
        namespace = {"m": magnifier, "index": index, "position": position}
        values = [
            eval(compile(ast.Expression(expr), str(DIAGNOSTIC), "eval"), namespace)
            for expr in call.args[1:4]
        ]
        assert values == [
            f"vn-magnifying-bracket-screw-{index}",
            list(position),
            magnifier.BRACKET_SCREW_ROWS,
        ]


def test_magnifying_bracket_screws_are_free_and_locked_to_the_bracket() -> None:
    assembly = SCRIPTS / "build_mg_magnifier_assembly.py"
    tree = ast.parse(assembly.read_text(encoding="utf-8"))
    loops = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.For)
        and isinstance(node.iter, ast.Call)
        and ast.unparse(node.iter) == "enumerate(BRACKET_SCREW_POSITIONS, start=1)"
    ]
    assert len(loops) == 1
    calls = [node for node in ast.walk(loops[0]) if isinstance(node, ast.Call)]
    placement = next(
        node for node in calls
        if getattr(node.func, "id", None) == "place_component"
    )
    assert ast.literal_eval(placement.args[1]) == "vn-magnifying-bracket-screw"
    assert ast.unparse(placement.args[2]) == "list(position)"
    assert ast.unparse(placement.args[4]) == "BRACKET_SCREW_ROWS"
    assert next(kw.value.value for kw in placement.keywords if kw.arg == "ground") is False
    mate = next(
        node for node in calls if getattr(node.func, "id", None) == "lock_mate"
    )
    assert ast.unparse(mate.args[1]) == "named_ref(f'Front Plane@{screw}', 'PLANE')"
    assert ast.unparse(mate.args[2]) == "named_ref(f'Front Plane@{bracket}', 'PLANE')"
