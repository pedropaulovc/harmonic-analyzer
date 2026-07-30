"""Contract tests for GD&T values projected by drawing recipes."""

from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path


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


def _part_mapping(spec_path: Path) -> dict[str, str]:
    tree = ast.parse(spec_path.read_text(encoding="utf-8"), filename=str(spec_path))
    for node in tree.body:
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name):
            continue
        if node.target.id != TOLERANCE_MAPPING:
            continue
        assert isinstance(node.value, ast.Dict)
        raw_keys = [ast.literal_eval(key) for key in node.value.keys]
        assert all(isinstance(key, str) for key in raw_keys)
        assert len(raw_keys) == len(set(raw_keys)), (
            f"{spec_path}: duplicate {TOLERANCE_MAPPING} keys"
        )
        mapping = ast.literal_eval(node.value)
        assert isinstance(mapping, dict)
        return mapping
    raise AssertionError(f"{spec_path} lacks {TOLERANCE_MAPPING}")


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

        for call in calls:
            tolerance = _keyword(call, "tolerance")
            assert isinstance(tolerance, ast.Subscript), (
                f"{drawing}:{call.lineno}: FCF tolerance is drawing-owned"
            )
            assert isinstance(tolerance.value, ast.Name)
            assert tolerance.value.id == TOLERANCE_MAPPING
            assert all(
                key in mapping
                for key in _mapping_reference_keys(tolerance, loop_bindings)
            )
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
