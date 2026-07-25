"""Fleet-wide contract for part drawing view placement and default visuals."""

from __future__ import annotations

import ast
import inspect
from types import SimpleNamespace

import pytest

import _drawing_common as drawing_common
from _drawing_registry import DRAWINGS, DrawingSpec


PART_DRAWINGS = tuple(spec for spec in DRAWINGS if spec.source_kind == "part")
FORBIDDEN_PLACEMENT_KEYWORDS = {"char_height", "leader_attach_xy"}
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


def _top_level_assignments(tree: ast.Module) -> dict[str, ast.expr]:
    assignments: dict[str, ast.expr] = {}
    for statement in tree.body:
        if isinstance(statement, ast.AnnAssign) and isinstance(
            statement.target, ast.Name
        ):
            if statement.value is not None:
                assignments[statement.target.id] = statement.value
            continue
        if not isinstance(statement, ast.Assign):
            continue
        for target in statement.targets:
            if isinstance(target, ast.Name):
                assignments[target.id] = statement.value
    return assignments


def _dimension_names(
    expression: ast.expr, assignments: dict[str, ast.expr]
) -> tuple[str, ...]:
    if isinstance(expression, ast.Name):
        assert expression.id in assignments, f"unresolved keep collection {expression.id}"
        return _dimension_names(assignments[expression.id], assignments)
    if isinstance(expression, (ast.Set, ast.List, ast.Tuple)):
        assert all(
            isinstance(element, ast.Constant) and isinstance(element.value, str)
            for element in expression.elts
        ), "dimension keep collections may contain names only"
        return tuple(str(element.value) for element in expression.elts)
    if isinstance(expression, ast.Call) and isinstance(expression.func, ast.Name):
        assert expression.func.id in {"frozenset", "set", "tuple", "list"}
        if not expression.args:
            assert not expression.keywords
            return ()
        assert len(expression.args) == 1 and not expression.keywords
        return _dimension_names(expression.args[0], assignments)
    raise AssertionError(
        "dimension keep must be a literal name collection, not a coordinate mapping: "
        f"{ast.dump(expression, include_attributes=False)}"
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


@pytest.mark.parametrize("spec", PART_DRAWINGS, ids=lambda spec: spec.name)
def test_dimension_curation_keeps_names_without_coordinate_maps(
    spec: DrawingSpec,
) -> None:
    tree = ast.parse(spec.script.read_text(encoding="utf-8"), filename=str(spec.script))
    assignments = _top_level_assignments(tree)
    for call in (
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _call_name(node) == "curate_view_dimensions"
    ):
        keep = next(keyword.value for keyword in call.keywords if keyword.arg == "keep")
        names = _dimension_names(keep, assignments)
        assert len(names) == len(set(names)), f"{spec.name} repeats a dimension name"


@pytest.mark.parametrize("spec", DRAWINGS, ids=lambda spec: spec.name)
def test_drawing_recipes_do_not_restore_removed_visual_override_arguments(
    spec: DrawingSpec,
) -> None:
    tree = ast.parse(spec.script.read_text(encoding="utf-8"), filename=str(spec.script))
    forbidden = {
        keyword.arg
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg in FORBIDDEN_PLACEMENT_KEYWORDS
    }
    assert not forbidden, (
        f"{spec.name} restores drawing visual overrides: {sorted(forbidden)}"
    )


def test_curate_view_dimensions_deletes_only_and_never_repositions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keep = SimpleNamespace(name="Keep")
    drop = SimpleNamespace(name="Drop")
    curate_calls: list[tuple[str, ...]] = []

    monkeypatch.setattr(
        drawing_common, "_prepare_view_for_annotation_authoring", lambda *_args: None
    )
    monkeypatch.setattr(
        drawing_common,
        "insert_marked_dimensions",
        lambda *_args: [keep, drop],
    )
    monkeypatch.setattr(
        drawing_common,
        "delete_unnamed_imports",
        lambda _adapter, annotations: annotations,
    )
    monkeypatch.setattr(
        drawing_common,
        "dimension_name",
        lambda _adapter, annotation: annotation.name,
    )

    def curate(_adapter, annotations, *, delete):
        curate_calls.append(delete)
        return [annotation for annotation in annotations if annotation.name not in delete]

    monkeypatch.setattr(drawing_common, "curate_dimensions", curate)

    curated = drawing_common.curate_view_dimensions(
        object(), object(), keep={"Keep"}, view_label="front"
    )

    assert curated == [keep]
    assert curate_calls == [("Drop",)]
    assert "reposition" not in inspect.getsource(drawing_common.curate_view_dimensions)


def test_curate_view_dimensions_still_rejects_missing_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        drawing_common, "_prepare_view_for_annotation_authoring", lambda *_args: None
    )
    monkeypatch.setattr(drawing_common, "insert_marked_dimensions", lambda *_args: [])
    monkeypatch.setattr(
        drawing_common,
        "delete_unnamed_imports",
        lambda _adapter, annotations: annotations,
    )
    monkeypatch.setattr(drawing_common, "curate_dimensions", lambda *_args, **_kwargs: [])

    with pytest.raises(RuntimeError, match=r"missing model dimensions: \['Required'\]"):
        drawing_common.curate_view_dimensions(
            object(), object(), keep={"Required"}, view_label="front"
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


def test_datum_auto_layout_is_observed_without_rejecting_solidworks_choice() -> None:
    source = inspect.getsource(drawing_common.add_datum_feature)
    assert '"drawing.annotation_auto_layout"' in source
    assert "position did not persist" not in source


@pytest.mark.parametrize(
    ("helper", "forbidden"),
    (
        (
            drawing_common.add_feature_control_frame,
            {"leader_attach_xy", "SetLeaderAttachmentPointAtIndex", "GetLeaderPointsAtIndex"},
        ),
        (
            drawing_common.add_surface_finish,
            {
                "leader_attach_xy",
                "SetLeaderAttachmentPointAtIndex",
                "GetLeaderPointsAtIndex",
                "SetPosition2",
            },
        ),
        (drawing_common.add_native_hole_callout, {"SetPosition2"}),
        (
            drawing_common.add_property_linked_note,
            {"char_height", "SetTextFormat"},
        ),
    ),
)
def test_shared_annotation_helpers_keep_solidworks_default_visuals(
    helper: object,
    forbidden: set[str],
) -> None:
    source = inspect.getsource(helper)
    restored = {token for token in forbidden if token in source}
    assert not restored, (
        f"{getattr(helper, '__name__', helper)!s} restores visual overrides: "
        f"{sorted(restored)}"
    )


def test_dormant_layout_override_helpers_stay_deleted() -> None:
    assert not hasattr(drawing_common, "offset_dimension_text")
    assert not hasattr(drawing_common, "isolate_drawing_view_components")
