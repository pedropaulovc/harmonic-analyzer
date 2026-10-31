"""Contract tests for GD&T values projected by drawing recipes."""

from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).parent
FCF_HELPER = "add_feature_control_frame"
# A converted (#290) spec authors GEOMETRIC_TOLERANCES_IN as its literal
# source and derives GEOMETRIC_TOLERANCES_MM from it; an unconverted spec
# authors the MM table. Drawings may subscript either.
TOLERANCE_MAPPINGS = ("GEOMETRIC_TOLERANCES_IN", "GEOMETRIC_TOLERANCES_MM")


def _fcf_calls(tree: ast.AST) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == FCF_HELPER
    ]


def _keyword(call: ast.Call, name: str) -> ast.AST:
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    raise AssertionError(f"{FCF_HELPER} call on line {call.lineno} lacks {name}=")


def _part_mapping(spec_path: Path) -> dict[str, str]:
    tree = ast.parse(spec_path.read_text(encoding="utf-8"), filename=str(spec_path))
    for name in TOLERANCE_MAPPINGS:
        for node in tree.body:
            if not isinstance(node, ast.AnnAssign):
                continue
            if not isinstance(node.target, ast.Name) or node.target.id != name:
                continue
            if not isinstance(node.value, ast.Dict):
                continue
            raw_keys = [ast.literal_eval(key) for key in node.value.keys]
            assert all(isinstance(key, str) for key in raw_keys)
            assert len(raw_keys) == len(set(raw_keys)), (
                f"{spec_path}: duplicate {name} keys"
            )
            mapping = ast.literal_eval(node.value)
            assert isinstance(mapping, dict)
            return mapping
    raise AssertionError(
        f"{spec_path} lacks a literal {' or '.join(TOLERANCE_MAPPINGS)}"
    )


def _loop_string_bindings(tree: ast.AST) -> dict[str, tuple[str, ...]]:
    """Resolve tuple-loop variables whose every row binds a static string."""
    bindings: dict[str, tuple[str, ...]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.For) or not isinstance(node.target, ast.Tuple):
            continue
        if not isinstance(node.iter, (ast.Tuple, ast.List)):
            continue
        rows = node.iter.elts
        if not rows or not all(isinstance(row, (ast.Tuple, ast.List)) for row in rows):
            continue
        for index, target in enumerate(node.target.elts):
            if not isinstance(target, ast.Name):
                continue
            values: list[str] = []
            for row in rows:
                assert isinstance(row, (ast.Tuple, ast.List))
                if index >= len(row.elts):
                    values = []
                    break
                value = row.elts[index]
                if not isinstance(value, ast.Constant) or not isinstance(
                    value.value, str
                ):
                    values = []
                    break
                values.append(value.value)
            if values:
                bindings[target.id] = tuple(values)
    return bindings


def _mapping_reference_keys(
    node: ast.Subscript, loop_bindings: dict[str, tuple[str, ...]]
) -> tuple[str, ...]:
    assert isinstance(node.value, ast.Name)
    assert node.value.id in TOLERANCE_MAPPINGS
    if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
        return (node.slice.value,)
    if isinstance(node.slice, ast.Name) and node.slice.id in loop_bindings:
        return loop_bindings[node.slice.id]
    raise AssertionError(f"line {node.lineno}: cannot prove {node.value.id} key set")


def _require_part_band_profile(
    tree: ast.Module, call: ast.Call, spec_tree: ast.Module, spec_module: str,
) -> None:
    """Allow a profile zone projected from a part's positive one-sided band."""
    characteristic = _keyword(call, "characteristic")
    assert isinstance(characteristic, ast.Constant)
    assert characteristic.value == "profile_surface"
    tolerance = _keyword(call, "tolerance")
    seen: set[str] = set()
    while isinstance(tolerance, ast.Name):
        name = tolerance.id
        assert name not in seen, "cyclic profile tolerance assignment"
        seen.add(name)
        definitions = [
            node.value for node in tree.body
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == name
            ) or (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == name
            )
        ]
        assert len(definitions) == 1, "profile tolerance needs one module assignment"
        stores = [
            node for node in ast.walk(tree)
            if (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id == name)
            or (isinstance(node, ast.arg) and node.arg == name)
        ]
        assert len(stores) == 1, "profile tolerance assignment is shadowed"
        tolerance = definitions[0]
    assert isinstance(tolerance, ast.JoinedStr) and len(tolerance.values) == 1
    formatted = tolerance.values[0]
    assert isinstance(formatted, ast.FormattedValue) and formatted.conversion == -1
    assert isinstance(formatted.format_spec, ast.JoinedStr)
    assert len(formatted.format_spec.values) == 1
    format_value = formatted.format_spec.values[0]
    assert isinstance(format_value, ast.Constant) and format_value.value == "g"
    band = formatted.value
    assert isinstance(band, ast.Subscript) and isinstance(band.value, ast.Name)
    assert isinstance(band.slice, ast.Constant) and type(band.slice.value) is int
    assert band.slice.value == 0, "profile total zone must use the upper endpoint"
    local_name = band.value.id
    imports = [
        (node, alias) for node in tree.body if isinstance(node, ast.ImportFrom)
        for alias in node.names if (alias.asname or alias.name) == local_name
    ]
    assert len(imports) == 1, "profile band needs one direct part-spec import"
    imported, alias = imports[0]
    assert imported.level == 0 and imported.module == spec_module
    assert alias.name.endswith("_BAND")
    assert not any(
        (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id == local_name)
        or (isinstance(node, ast.arg) and node.arg == local_name)
        for node in ast.walk(tree)
    ), "part band import is shadowed"
    definitions = [
        node.value for node in spec_tree.body
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == alias.name
        ) or (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == alias.name
        )
    ]
    assert len(definitions) == 1
    value = definitions[0]
    assert isinstance(value, ast.Tuple) and len(value.elts) == 2
    assert all(isinstance(endpoint, ast.Constant) for endpoint in value.elts)
    upper, lower = (endpoint.value for endpoint in value.elts)
    assert type(upper) in (int, float) and type(lower) in (int, float)
    assert upper > 0 and lower == 0



def test_all_drawing_fcf_values_come_from_part_specs() -> None:
    projected = 0
    for drawing in sorted(SCRIPTS.glob("draw_*.py")):
        source = drawing.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(drawing))
        calls = _fcf_calls(tree)
        if not calls:
            continue

        spec_path = SCRIPTS / f"{drawing.stem.removeprefix('draw_')}_spec.py"
        mapping = _part_mapping(spec_path)
        assert mapping, f"{spec_path}: empty geometric tolerance mapping"
        assert all(
            re.fullmatch(r"\d+(?:\.\d+)?|\.\d+", value) for value in mapping.values()
        )
        assert all(float(value) > 0.0 for value in mapping.values())
        loop_bindings = _loop_string_bindings(tree)
        spec_tree = ast.parse(spec_path.read_text(encoding="utf-8"))

        for call in calls:
            tolerance = _keyword(call, "tolerance")
            if (
                isinstance(tolerance, ast.Subscript)
                and isinstance(tolerance.value, ast.Name)
                and tolerance.value.id in TOLERANCE_MAPPINGS
            ):
                assert all(
                    key in mapping
                    for key in _mapping_reference_keys(tolerance, loop_bindings)
                )
            else:
                _require_part_band_profile(tree, call, spec_tree, spec_path.stem)
            projected += 1

        references: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Subscript):
                continue
            if not isinstance(node.value, ast.Name):
                continue
            if node.value.id not in TOLERANCE_MAPPINGS:
                continue
            references.extend(_mapping_reference_keys(node, loop_bindings))
        assert Counter(references) == Counter(mapping.keys()), (
            f"{drawing}: spec/reference key mismatch: "
            f"spec={Counter(mapping.keys())!r}, references={Counter(references)!r}"
        )

    assert projected > 0


@pytest.mark.parametrize("assignment", [
    "ZONE = f'{HEIGHT_BAND[0]:g}'",
    "BASE = f'{HEIGHT_BAND[0]:g}'\nZONE = BASE",
    "BASE: str = f'{HEIGHT_BAND[0]:g}'\nZONE: str = BASE",
])
def test_profile_zone_accepts_only_part_band_projection(assignment: str) -> None:
    tree = ast.parse(
        "from sample_spec import HEIGHT_BAND\n" + assignment
        + "\nadd_feature_control_frame(characteristic='profile_surface', tolerance=ZONE)"
    )
    _require_part_band_profile(
        tree, _fcf_calls(tree)[0], ast.parse("HEIGHT_BAND = (0.5, 0.0)"), "sample_spec",
    )


@pytest.mark.parametrize(("source", "spec"), [
    ("ZONE = '0.5'", "HEIGHT_BAND = (0.5, 0.0)"),
    ("ZONE = f'{0.5:g}'", "HEIGHT_BAND = (0.5, 0.0)"),
    ("HEIGHT_BAND = (0.5, 0.0)\nZONE = f'{HEIGHT_BAND[0]:g}'", "HEIGHT_BAND = (0.5, 0.0)"),
    ("from notes import HEIGHT_BAND\nZONE = f'{HEIGHT_BAND[0]:g}'", "HEIGHT_BAND = (0.5, 0.0)"),
    ("from sample_spec import HEIGHT_BAND\nZONE = f'{HEIGHT_BAND[1]:g}'", "HEIGHT_BAND = (0.5, 0.0)"),
    ("from sample_spec import HEIGHT_BAND\nZONE = f'{HEIGHT_BAND[0]:.1f}'", "HEIGHT_BAND = (0.5, 0.0)"),
    ("from sample_spec import HEIGHT_BAND\nZONE = f'zone {HEIGHT_BAND[0]:g}'", "HEIGHT_BAND = (0.5, 0.0)"),
    ("from sample_spec import HEIGHT_BAND\nZONE = f'{HEIGHT_BAND[0]:g}'", ""),
    ("from sample_spec import HEIGHT_BAND\nZONE = f'{HEIGHT_BAND[0]:g}'", "HEIGHT_BAND = (0.5, -0.1)"),
    ("from sample_spec import HEIGHT_BAND\nZONE = f'{HEIGHT_BAND[0]:g}'", "HEIGHT_BAND = (0.0, 0.0)"),
    ("from sample_spec import HEIGHT_BAND\nZONE = f'{HEIGHT_BAND[0]:g}'", "HEIGHT_BAND = OTHER"),
    ("from sample_spec import HEIGHT_BAND\nZONE = f'{HEIGHT_BAND[0]:g}'\nZONE = '0.5'", "HEIGHT_BAND = (0.5, 0.0)"),
    ("from sample_spec import HEIGHT_BAND\nZONE = f'{HEIGHT_BAND[0]:g}'\ndef local(HEIGHT_BAND): pass", "HEIGHT_BAND = (0.5, 0.0)"),
    ("ZONE = OTHER\nOTHER = ZONE", "HEIGHT_BAND = (0.5, 0.0)"),
])
def test_profile_zone_rejects_unproven_or_invalid_band_sources(source: str, spec: str) -> None:
    tree = ast.parse(
        source + "\nadd_feature_control_frame(characteristic='profile_surface', tolerance=ZONE)"
    )
    with pytest.raises(AssertionError):
        _require_part_band_profile(tree, _fcf_calls(tree)[0], ast.parse(spec), "sample_spec")


@pytest.mark.parametrize("characteristic", ["position", "profile_line", "flatness"])
def test_part_band_projection_cannot_supply_other_characteristics(characteristic: str) -> None:
    tree = ast.parse(
        "from sample_spec import HEIGHT_BAND\nZONE = f'{HEIGHT_BAND[0]:g}'\n"
        f"add_feature_control_frame(characteristic={characteristic!r}, tolerance=ZONE)"
    )
    with pytest.raises(AssertionError):
        _require_part_band_profile(
            tree, _fcf_calls(tree)[0], ast.parse("HEIGHT_BAND = (0.5, 0.0)"), "sample_spec",
        )


def test_inch_source_mapping_is_the_spec_table(tmp_path: Path) -> None:
    spec = tmp_path / "sample_spec.py"
    spec.write_text(
        'GEOMETRIC_TOLERANCES_IN: dict[str, str] = {"bore position": ".008"}\n'
        "GEOMETRIC_TOLERANCES_MM: dict[str, float] = {\n"
        "    k: float(v) * 25.4 for k, v in GEOMETRIC_TOLERANCES_IN.items()\n"
        "}\n",
        encoding="utf-8",
    )
    assert _part_mapping(spec) == {"bore position": ".008"}
    reference = ast.parse('GEOMETRIC_TOLERANCES_IN["bore position"]').body[0]
    assert isinstance(reference, ast.Expr) and isinstance(reference.value, ast.Subscript)
    assert _mapping_reference_keys(reference.value, {}) == ("bore position",)


def test_within_limits_are_not_literal_drawing_values() -> None:
    violations: list[str] = []
    for drawing in sorted(SCRIPTS.glob("draw_*.py")):
        tree = ast.parse(drawing.read_text(encoding="utf-8"), filename=str(drawing))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if re.search(r"\bWITHIN\s+\d", node.value, re.IGNORECASE):
                violations.append(f"{drawing}:{node.lineno}: {node.value!r}")
    assert not violations, "drawing-owned WITHIN limits:\n" + "\n".join(violations)
