"""Contract tests for GD&T values projected by drawing recipes."""

from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).parent
FCF_HELPER = "add_feature_control_frame"
TOLERANCE_MAPPING = "GEOMETRIC_TOLERANCES_MM"


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


def _literal_mapping(
    source: Path, name: str, active: frozenset[tuple[Path, str]],
) -> dict[str, str]:
    source = source.resolve()
    identity = (source, name)
    assert identity not in active, f"{source}: cyclic literal mapping {name}"
    assert source.is_file(), f"{source}: missing literal mapping source for {name}"
    active = active | {identity}
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    definitions: list[ast.expr | None] = []
    imports: list[tuple[ast.ImportFrom, str]] = []
    for node in tree.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
        ):
            definitions.append(node.value)
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == name
        ):
            definitions.append(node.value)
        elif isinstance(node, ast.ImportFrom):
            imports.extend(
                (node, alias.name)
                for alias in node.names if (alias.asname or alias.name) == name
            )
    assert len(definitions) + len(imports) == 1, (
        f"{source}: missing or ambiguous literal mapping {name}"
    )
    if imports:
        imported, exported = imports[0]
        assert imported.level == 0 and imported.module and imported.module.isidentifier(), (
            f"{source}: {name} needs a direct local-module import"
        )
        return _literal_mapping(source.parent / f"{imported.module}.py", exported, active)

    value = definitions[0]
    assert isinstance(value, ast.Dict), f"{source}: {name} must be a literal mapping"
    mapping: dict[str, str] = {}
    for key, item in zip(value.keys, value.values):
        if key is None:
            assert isinstance(item, ast.Name), f"{source}: {name} requires **Name expansions"
            entries = _literal_mapping(source, item.id, active)
        else:
            assert isinstance(key, ast.Constant) and isinstance(key.value, str), (
                f"{source}: {name} requires literal string keys"
            )
            assert isinstance(item, ast.Constant) and isinstance(item.value, str), (
                f"{source}: {name} requires literal string values"
            )
            entries = {key.value: item.value}
        assert not mapping.keys() & entries.keys(), f"{source}: duplicate {name} keys"
        mapping.update(entries)
    return mapping


def _part_mapping(spec_path: Path) -> dict[str, str]:
    return _literal_mapping(spec_path, TOLERANCE_MAPPING, frozenset())


def test_part_mapping_follows_imported_literal_changes_without_executing_them(tmp_path) -> None:
    interface = tmp_path / "interface.py"
    spec = tmp_path / "sample_spec.py"
    interface.write_text(
        "raise RuntimeError('source contracts must not execute imports')\n"
        "BASE = {'mounting position': '0.15'}\n"
        "MOUNTING = {**BASE}\n",
        encoding="utf-8",
    )
    spec.write_text(
        "from interface import MOUNTING as SEAT\n"
        "GEOMETRIC_TOLERANCES_MM: dict[str, str] = {'bore position': '0.20', **SEAT}\n",
        encoding="utf-8",
    )
    assert _part_mapping(spec) == {"bore position": "0.20", "mounting position": "0.15"}
    interface.write_text("MOUNTING = {'mounting position': '0.155'}\n", encoding="utf-8")
    assert _part_mapping(spec) == {"bore position": "0.20", "mounting position": "0.155"}


@pytest.mark.parametrize(("shared", "expression"), [
    ("MOUNTING = {'position': '0.15'}", "{'position': '0.10', 'position': '0.20'}"),
    ("MOUNTING = {'position': '0.15'}", "{'position': '0.10', **MOUNTING}"),
    ("MOUNTING = {'position': '0.15'}", "{**MOUNTING, 'position': '0.10'}"),
    ("MOUNTING = {'position': '0.15'}", "{**MOUNTING, **MOUNTING}"),
    ("MOUNTING = {'position': '0.10', 'position': '0.20'}", "{**MOUNTING}"),
])
def test_part_mapping_rejects_duplicates_including_import_expansions(
    tmp_path, shared: str, expression: str,
) -> None:
    (tmp_path / "interface.py").write_text(shared, encoding="utf-8")
    spec = tmp_path / "sample_spec.py"
    spec.write_text(
        "from interface import MOUNTING\n"
        f"GEOMETRIC_TOLERANCES_MM: dict[str, str] = {expression}\n",
        encoding="utf-8",
    )
    with pytest.raises(AssertionError, match="duplicate"):
        _part_mapping(spec)


@pytest.mark.parametrize(("shared", "source"), [
    (None, "from interface import MOUNTING\nGEOMETRIC_TOLERANCES_MM = {**MOUNTING}"),
    ("OTHER = {}", "from interface import MOUNTING\nGEOMETRIC_TOLERANCES_MM = {**MOUNTING}"),
    ("", "GEOMETRIC_TOLERANCES_MM = {**MISSING}"),
    ("", "FIRST = {**SECOND}\nSECOND = {**FIRST}\nGEOMETRIC_TOLERANCES_MM = {**FIRST}"),
    ("from sample_spec import GEOMETRIC_TOLERANCES_MM as MOUNTING",
     "from interface import MOUNTING\nGEOMETRIC_TOLERANCES_MM = {**MOUNTING}"),
    ("MOUNTING = {}", "from interface import MOUNTING\nMOUNTING = {}\n"
     "GEOMETRIC_TOLERANCES_MM = {**MOUNTING}"),
    ("", "if True:\n    MOUNTING = {}\nGEOMETRIC_TOLERANCES_MM = {**MOUNTING}"),
    ("", "def choose():\n    MOUNTING = {}\nGEOMETRIC_TOLERANCES_MM = {**MOUNTING}"),
])
def test_part_mapping_rejects_missing_ambiguous_and_cyclic_sources(tmp_path, shared, source) -> None:
    if shared is not None:
        (tmp_path / "interface.py").write_text(shared, encoding="utf-8")
    spec = tmp_path / "sample_spec.py"
    spec.write_text(source, encoding="utf-8")
    with pytest.raises(AssertionError, match="missing|ambiguous|cyclic"):
        _part_mapping(spec)


@pytest.mark.parametrize("expression", [
    "{1: '0.15'}",
    "{'position': 0.15}",
    "{'position': f'{0.15}'}",
    "{'position': VALUE}",
    "dict(position='0.15')",
    "{**{'position': '0.15'}}",
])
def test_part_mapping_requires_literal_string_entries(tmp_path, expression: str) -> None:
    spec = tmp_path / "sample_spec.py"
    spec.write_text(f"GEOMETRIC_TOLERANCES_MM = {expression}\n", encoding="utf-8")
    with pytest.raises(AssertionError):
        _part_mapping(spec)


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
    assert node.value.id == TOLERANCE_MAPPING
    if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
        return (node.slice.value,)
    if isinstance(node.slice, ast.Name) and node.slice.id in loop_bindings:
        return loop_bindings[node.slice.id]
    raise AssertionError(
        f"line {node.lineno}: cannot prove {TOLERANCE_MAPPING} key set"
    )


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
        assert mapping, f"{spec_path}: empty {TOLERANCE_MAPPING}"
        assert all(re.fullmatch(r"\d+(?:\.\d+)?", value) for value in mapping.values())
        assert all(float(value) > 0.0 for value in mapping.values())
        loop_bindings = _loop_string_bindings(tree)
        spec_tree = ast.parse(spec_path.read_text(encoding="utf-8"))

        for call in calls:
            tolerance = _keyword(call, "tolerance")
            if (
                isinstance(tolerance, ast.Subscript)
                and isinstance(tolerance.value, ast.Name)
                and tolerance.value.id == TOLERANCE_MAPPING
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
            if node.value.id != TOLERANCE_MAPPING:
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
