"""Fleet-wide contract for part drawing view placement and default visuals."""

from __future__ import annotations

import ast
from types import SimpleNamespace

import pytest

import _drawing_common as drawing_common
from _drawing_registry import DRAWINGS, DrawingSpec


PART_DRAWINGS = tuple(spec for spec in DRAWINGS if spec.source_kind == "part")
VISUAL_OVERRIDE_CALLS = {
    "SetDisplayMode4",
    "SetDisplayTangentEdges2",
    "UpdateViewDisplayGeometry",
    "set_hidden_lines_removed",
    "set_hidden_lines_visible",
}


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
def test_part_drawing_keeps_explicit_placements_and_default_visuals(
    spec: DrawingSpec,
) -> None:
    tree = ast.parse(spec.script.read_text(encoding="utf-8"), filename=str(spec.script))
    calls = {
        name
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and (name := _call_name(node))
    }

    assert _has_precomputed_placements(tree), (
        f"{spec.name} lost its precomputed view placements"
    )
    assert calls.isdisjoint(VISUAL_OVERRIDE_CALLS), (
        f"{spec.name} overrides SolidWorks drawing visuals: "
        f"{sorted(calls & VISUAL_OVERRIDE_CALLS)}"
    )


def test_hidden_edges_are_temporary_authoring_input_not_saved_visuals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeView:
        def __init__(self) -> None:
            self.mode = 2
            self.calls: list[tuple[bool, int, bool, bool, bool]] = []

        def GetUseParentDisplayMode(self) -> bool:
            return True

        def GetDisplayMode2(self) -> int:
            return self.mode

        def GetFacettedHlrDisplay(self) -> bool:
            return False

        def GetDisplayEdgesInShadedMode(self) -> bool:
            return True

        def GetCThreadQuality(self) -> bool:
            return True

        def SetDisplayMode4(
            self,
            use_parent: bool,
            mode: int,
            faceted: bool,
            edges: bool,
            cosmetic_threads_high_quality: bool,
        ) -> bool:
            self.calls.append(
                (
                    use_parent,
                    mode,
                    faceted,
                    edges,
                    cosmetic_threads_high_quality,
                )
            )
            self.mode = mode
            return True

    view = FakeView()
    monkeypatch.setattr(drawing_common, "_early_bound", lambda value, _name: value)
    monkeypatch.setattr(drawing_common, "view_name", lambda _adapter, _view: "Front")
    drawing_common._AUTHORING_VIEW_DISPLAYS.clear()

    drawing_common._prepare_view_for_annotation_authoring(
        SimpleNamespace(), view
    )
    drawing_common._prepare_view_for_annotation_authoring(
        SimpleNamespace(), view
    )
    assert view.calls == [(False, 1, False, True, True)]

    drawing_common._restore_default_view_displays()
    assert view.calls[-1] == (True, 2, False, True, True)
    assert view.mode == 2
    assert not drawing_common._AUTHORING_VIEW_DISPLAYS
