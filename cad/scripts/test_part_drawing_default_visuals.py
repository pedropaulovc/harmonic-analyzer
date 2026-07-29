"""Fleet-wide contract for part drawing view placement."""

from __future__ import annotations

import ast

import pytest

from _drawing_registry import DRAWINGS, DrawingSpec


PART_DRAWINGS = tuple(spec for spec in DRAWINGS if spec.source_kind == "part")



def _call_name(node: ast.Call) -> str:
    function = node.func
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        return function.attr
    return ""


def _has_precomputed_placements(tree: ast.AST) -> bool:
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    if any(_call_name(node) == "place_view" for node in calls):
        return True
    required_recipe_fields = {"side_center", "end_center", "iso_center"}
    return any(
        _call_name(node) == "FastenerSheet"
        and required_recipe_fields <= {keyword.arg for keyword in node.keywords}
        for node in calls
    )


@pytest.mark.parametrize("spec", PART_DRAWINGS, ids=lambda spec: spec.name)
def test_part_drawing_keeps_explicit_placements(spec: DrawingSpec) -> None:
    # Per-view display control (hidden lines, tangent edges) is a LAYOUT concern
    # a recipe may own: several sheets attach datums and callouts to hidden
    # edges, which are only selectable when the view displays them.
    tree = ast.parse(spec.script.read_text(encoding="utf-8"), filename=str(spec.script))
    assert _has_precomputed_placements(tree), (
        f"{spec.name} lost its precomputed view placements"
    )
