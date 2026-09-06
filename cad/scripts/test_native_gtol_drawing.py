"""Measured GTol column planning and exact native-mutation witness controls."""

import ast
from dataclasses import replace
import math
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import _drawing_native_gtol as layout
from _drawing_view_packing import Rect


@pytest.mark.parametrize(
    ("column", "expected"),
    [
        (Rect(0.4, 0.3, 0.5, 0.4), (-0.302, 0)),
        (Rect(0.7, 0.3, 0.75, 0.4), (0.102, 0)),
        (Rect(0.05, 0.3, 0.1, 0.4), (0, 0)),
    ],
)
def test_outboard_minimum_horizontal_displacement(column, expected):
    assert layout.column_outboard_translation(
        column, Rect(0.2, 0.2, 0.8, 0.8)
    ) == pytest.approx(expected)


def test_obstacle_changes_preferred_side_without_changing_height():
    column = Rect(0.4, 0.3, 0.5, 0.4)
    obstacle = Rect(-0.1, 0.25, 0.2, 0.45)
    delta = layout.column_outboard_translation(
        column, Rect(0.2, 0.2, 0.8, 0.8), [obstacle]
    )
    assert delta == pytest.approx((0.402, 0))


def test_obstacle_boundary_is_a_candidate_not_just_two_view_sides():
    column = Rect(0.7, 0.3, 0.75, 0.4)
    obstacle = Rect(0.8, 0.25, 0.9, 0.45)
    delta = layout.column_outboard_translation(
        column, Rect(0.2, 0.2, 0.8, 0.8), [obstacle]
    )
    assert delta == pytest.approx((0.202, 0))


def test_nonoverlapping_height_does_not_block_horizontal_lane():
    assert layout.column_outboard_translation(
        Rect(0.7, 0.3, 0.75, 0.4), Rect(0.2, 0.2, 0.8, 0.8), [Rect(0.8, 0.5, 1.0, 0.6)]
    ) == pytest.approx((0.102, 0))


@pytest.mark.parametrize("gap", [-0.1, math.nan, math.inf])
def test_invalid_clearance_rejected(gap):
    with pytest.raises(ValueError):
        layout.column_outboard_translation(
            Rect(0, 0, 1, 1), Rect(0, 0, 1, 1), gap_m=gap
        )
    with pytest.raises(ValueError):
        layout.column_clearance_translations({}, (), gap_m=gap)


def test_clearance_single_pass_preserves_native_order_and_sufficient_gaps():
    bodies = {
        "first": Rect(0, 0.08, 0.02, 0.1),
        "quantity": Rect(0, 0.05, 0.08, 0.08),
        "third": Rect(0, 0.04, 0.02, 0.06),
        "far": Rect(0, 0.001, 0.02, 0.02),
    }
    result = layout.column_clearance_translations(bodies, tuple(bodies), gap_m=0.002)
    assert result["first"] == (0, 0)
    assert result["quantity"] == pytest.approx((0, -0.002))
    assert result["third"] == pytest.approx((0, -0.014))
    assert result["far"] == (0, 0)
    arranged = {name: body.translated(result[name]) for name, body in bodies.items()}
    for first, second in zip(tuple(arranged.values()), tuple(arranged.values())[1:]):
        assert first.ymin - second.ymax >= 0.002 - 1e-12


@pytest.mark.parametrize("order", [("a", "a"), (), ("unknown",)])
def test_clearance_order_requires_every_body_once(order):
    with pytest.raises(ValueError, match="exactly once"):
        layout.column_clearance_translations({"a": Rect(0, 0, 1, 1)}, order)


def native_context(monkeypatch, count=2):
    monkeypatch.setattr(layout, "_early_bound", lambda item, name: item)
    monkeypatch.setattr(
        layout,
        "annotation_leader_geometry",
        lambda annotation: layout.LeaderGeometry((), ()),
    )
    app, model, view = Mock(), Mock(), Mock()
    adapter = SimpleNamespace(swApp=app, currentModel=model)
    app.IsSame.side_effect = lambda first, second: int(first is second)
    model.GetType.return_value = 3
    model.GetViews.return_value = [(Mock(), view)]
    view.GetName2.return_value = "native-view"
    view.GetOutline.return_value = (0.2, 0.2, 0.8, 0.9)
    rows, selected = [], []
    model.ClearSelection2.side_effect = lambda clear: selected.clear()
    for index in range(count):
        item = Mock()
        item.position = [0.4 + index * 0.1, 0.8, -0.002]
        item.size = (0.1 + index * 0.2, 0.1 + index * 0.1)
        item.GetPosition.side_effect = lambda item=item: tuple(item.position)
        item.GetType.return_value = 5
        item.GetName.return_value = f"GTol{index}"
        item.Visible, item.OwnerType, item.Owner = 1, 0, view
        item.IsDangling.return_value = False
        item.GetAttachedEntities3.return_value = (object(),)
        item.GetAttachedEntityTypes.return_value = (2,)
        gtol = item.GetSpecificAnnotation.return_value
        gtol.GetAnnotation.return_value = item
        gtol.GetFrameCount.return_value = 1
        gtol.GetFrame.return_value.GetSymbolXml.return_value = (
            '<frame tolerance="0.05"/>'
        )
        gtol.GetTextCount.return_value = 2
        gtol.GetTextAtIndex.side_effect = lambda index: ("0.05", "DATUM B SIDE")[index]

        def select(append, mark, item=item):
            selected.append(item)
            return True

        def move(x, y, z, item=item):
            item.position[:] = (x, y, z)
            return True

        item.Select2.side_effect = select
        item.SetPosition2.side_effect = move
        rows.append(item)
    view.GetAnnotationsByType.side_effect = lambda kind: rows if kind == 5 else ()
    selection = model.SelectionManager
    selection.GetSelectedObjectCount2.side_effect = lambda mark: len(selected)
    selection.GetSelectedObjectType3.return_value = 13
    selection.GetSelectedObjectsDrawingView2.return_value = view
    selection.GetSelectedObject6.side_effect = lambda index, mark: selected[
        index - 1
    ].GetSpecificAnnotation()
    app.IsCommandEnabled.return_value = True

    def command(command, title):
        if command == 317:
            for index, item in enumerate(selected):
                item.position[1] -= index * 0.1
        if command == 307:
            for item in selected:
                item.position[0] = selected[0].position[0]
        return True

    app.RunCommand.side_effect = command

    def measure(adapter, annotation):
        x, y, _ = annotation.position
        width, height = annotation.size
        return SimpleNamespace(
            kind=5,
            body=Rect(x, y - height, x + width, y),
            anchor=(x, y),
            format_signature=("Century Gothic", 0.0035),
            text_boxes=(),
            text_runs=(),
            native_leader_segments=(),
            leader_segments=(),
            leader_decorations=(),
        )

    return adapter, view, rows, measure


def arrange(adapter, view, measure):
    return layout.arrange_native_gtol_columns(
        adapter, views={"front": view}, measure_annotation=measure
    )


def test_native_commands_clearance_and_outboard_shift_keep_exact_entities(monkeypatch):
    adapter, view, rows, measure = native_context(monkeypatch, count=3)
    result = arrange(adapter, view, measure)["front"]
    assert [call.args[0] for call in adapter.swApp.RunCommand.call_args_list] == [
        317,
        307,
    ]
    assert [entry["command"] for entry in result["commands"]] == [317, 307]
    assert result["clearance_translations_m"]["GTol0"] == (0, 0)
    assert result["clearance_translations_m"]["GTol1"] == pytest.approx((0, -0.002))
    assert result["translation_m"] == pytest.approx((0.402, 0))
    assert rows[0].position == pytest.approx((0.802, 0.8, -0.002))
    assert rows[1].position == pytest.approx((0.802, 0.698, -0.002))
    assert rows[0].SetPosition2.call_count == 1
    assert rows[1].SetPosition2.call_count == 2
    assert result["body_after"][0] == pytest.approx(0.802)


@pytest.mark.parametrize(
    "count,commands", [(0, []), (1, []), (2, [307]), (3, [317, 307])]
)
def test_native_spacing_uses_the_observed_minimum_bank_cardinality(
    monkeypatch, count, commands
):
    adapter, view, rows, measure = native_context(monkeypatch, count=count)
    adapter.swApp.IsCommandEnabled.side_effect = lambda command: (
        command != 317 or count >= 3
    )
    arrange(adapter, view, measure)
    assert [
        call.args[0] for call in adapter.swApp.RunCommand.call_args_list
    ] == commands


@pytest.mark.parametrize("count", [0, 1])
def test_empty_or_singleton_bank_never_calls_disabled_multiselect_commands(
    monkeypatch, count
):
    adapter, view, rows, measure = native_context(monkeypatch, count=count)
    adapter.swApp.IsCommandEnabled.return_value = False
    result = arrange(adapter, view, measure)["front"]
    assert result["count"] == count
    adapter.swApp.RunCommand.assert_not_called()
    if count:
        rows[0].SetPosition2.assert_called_once()


@pytest.mark.parametrize(
    "failure",
    [
        "disabled",
        "selection_count",
        "selection_type",
        "selection_view",
        "selection_identity",
        "selection_rejected",
        "activate",
    ],
)
def test_wrong_native_selection_or_disabled_command_fails_before_mutation(
    monkeypatch, failure
):
    adapter, view, rows, measure = native_context(monkeypatch)
    selection = adapter.currentModel.SelectionManager
    if failure == "disabled":
        adapter.swApp.IsCommandEnabled.return_value = False
    if failure == "selection_count":
        selection.GetSelectedObjectCount2.side_effect = lambda mark: 3
    if failure == "selection_type":
        selection.GetSelectedObjectType3.return_value = 14
    if failure == "selection_view":
        selection.GetSelectedObjectsDrawingView2.return_value = Mock()
    if failure == "selection_identity":
        selection.GetSelectedObject6.side_effect = lambda index, mark: Mock()
    if failure == "selection_rejected":
        rows[0].Select2.side_effect = lambda append, mark: False
    if failure == "activate":
        adapter.currentModel.ActivateView.return_value = False
    with pytest.raises(RuntimeError):
        arrange(adapter, view, measure)
    adapter.swApp.RunCommand.assert_not_called()
    for item in rows:
        item.SetPosition2.assert_not_called()
    assert adapter.currentModel.SelectionManager.GetSelectedObjectCount2(-1) in (0, 3)


def test_rejected_native_command_has_no_manual_fallback(monkeypatch):
    adapter, view, rows, measure = native_context(monkeypatch)
    adapter.swApp.RunCommand.side_effect = lambda command, title: False
    with pytest.raises(RuntimeError, match="rejected the bank"):
        arrange(adapter, view, measure)
    adapter.swApp.RunCommand.assert_called_once()
    for item in rows:
        item.SetPosition2.assert_not_called()


def test_real_gtol_selection_with_null_manager_view_uses_exact_annotation_owner(
    monkeypatch,
):
    adapter, view, rows, measure = native_context(monkeypatch)
    adapter.currentModel.SelectionManager.GetSelectedObjectsDrawingView2.return_value = None
    report = arrange(adapter, view, measure)["front"]
    assert report["count"] == 2
    assert [call.args[0] for call in adapter.swApp.RunCommand.call_args_list] == [307]


def test_source_owned_gtol_cannot_use_null_selection_view_as_a_view_identity_witness(
    monkeypatch,
):
    adapter, view, rows, measure = native_context(monkeypatch)
    for annotation in rows:
        annotation.OwnerType, annotation.Owner = 3, view.ReferencedDocument
    adapter.currentModel.SelectionManager.GetSelectedObjectsDrawingView2.return_value = None
    with pytest.raises(RuntimeError, match="no exact drawing-view context"):
        arrange(adapter, view, measure)
    adapter.swApp.RunCommand.assert_not_called()


def test_owner_changed_during_selection_rejects_even_exact_selected_annotation(
    monkeypatch,
):
    adapter, view, rows, measure = native_context(monkeypatch)
    bank = layout._read_gtols(adapter, view, measure)
    rows[0].Owner = Mock()
    with pytest.raises(RuntimeError, match="selected GTol owner differs"):
        layout._native_command(adapter, adapter.currentModel, view, bank, 317)
    adapter.swApp.RunCommand.assert_not_called()


@pytest.mark.parametrize(
    "failure", ["coverage", "text", "frame", "entity", "dangling", "hidden", "owner"]
)
def test_native_command_semantic_drift_is_not_hidden_by_layout(monkeypatch, failure):
    adapter, view, rows, measure = native_context(monkeypatch)

    def corrupt(command, title):
        if failure == "coverage":
            rows.pop()
        if failure == "text":
            rows[0].GetSpecificAnnotation.return_value.GetTextAtIndex.side_effect = (
                lambda index: "changed"
            )
        if failure == "frame":
            rows[
                0
            ].GetSpecificAnnotation.return_value.GetFrame.return_value.GetSymbolXml.return_value = '<frame tolerance="0.50"/>'
        if failure == "entity":
            rows[0].GetAttachedEntities3.return_value = (object(),)
        if failure == "dangling":
            rows[0].IsDangling.return_value = True
        if failure == "hidden":
            rows[0].Visible = 0
        if failure == "owner":
            rows[0].Owner = Mock()
        return True

    adapter.swApp.RunCommand.side_effect = corrupt
    with pytest.raises(RuntimeError):
        arrange(adapter, view, measure)


@pytest.mark.parametrize("failure", ["reject", "clamp", "body", "attachment"])
def test_translation_requires_native_target_body_and_attachment_readback(
    monkeypatch, failure
):
    adapter, view, rows, measure = native_context(monkeypatch, count=1)
    item = rows[0]
    original_move = item.SetPosition2.side_effect

    def broken_move(x, y, z):
        if failure == "reject":
            return False
        if failure == "clamp":
            return True
        original_move(x, y, z)
        if failure == "body":
            item.size = (0.2, 0.1)
        if failure == "attachment":
            item.GetAttachedEntities3.return_value = (object(),)
        return True

    item.SetPosition2.side_effect = broken_move
    with pytest.raises(RuntimeError):
        arrange(adapter, view, measure)


def test_unprovable_attachment_is_rejected_before_native_commands(monkeypatch):
    adapter, view, rows, measure = native_context(monkeypatch)
    rows[0].GetAttachedEntities3.return_value = (None,)
    with pytest.raises(RuntimeError, match="cannot be proven exactly"):
        arrange(adapter, view, measure)
    adapter.swApp.RunCommand.assert_not_called()


def test_unknown_active_drawing_view_is_rejected_before_measurement(monkeypatch):
    adapter, view, rows, measure = native_context(monkeypatch)
    adapter.currentModel.GetViews.return_value = [(Mock(), Mock())]
    with pytest.raises(ValueError, match="active drawing"):
        arrange(adapter, view, measure)
    view.GetAnnotationsByType.assert_not_called()


def test_semantic_witness_covers_all_frames_and_attachment_types(monkeypatch):
    adapter, view, rows, measure = native_context(monkeypatch, count=1)
    before = layout._read_gtols(adapter, view, measure)
    old = before["GTol0"]
    for changed in (
        replace(old, frames=(old.frames[0], "<other/>")),
        replace(old, entity_types=(1,)),
        replace(old, entities=()),
    ):
        with pytest.raises(RuntimeError):
            layout._unchanged(adapter.swApp, before, {"GTol0": changed}, "mutation")


@pytest.mark.parametrize("count", [0, 2])
def test_unreadable_stored_frame_is_not_silently_excluded(monkeypatch, count):
    adapter, view, rows, measure = native_context(monkeypatch, count=1)
    gtol = rows[0].GetSpecificAnnotation.return_value
    frame = gtol.GetFrame.return_value
    gtol.GetFrameCount.return_value = count
    gtol.GetFrame.side_effect = lambda index: frame if index == 1 else None
    with pytest.raises(RuntimeError, match="frames|readable XML"):
        arrange(adapter, view, measure)
    rows[0].SetPosition2.assert_not_called()


def test_measured_surface_finish_body_changes_outboard_choice(monkeypatch):
    adapter, view, rows, measure = native_context(monkeypatch, count=1)
    obstacle = Mock()
    obstacle.position = [0.0, 0.85, 0]
    obstacle.size = (0.2, 0.1)
    view.GetAnnotationsByType.side_effect = lambda kind: {5: rows, 7: [obstacle]}.get(
        kind, ()
    )
    result = arrange(adapter, view, measure)["front"]
    assert result["translation_m"] == pytest.approx((0.402, 0))
    assert result["obstacle_count"] == 1
    obstacle.SetPosition2.assert_not_called()


def test_production_helper_never_recreates_annotations_or_selects_geometry():
    tree = ast.parse(Path(layout.__file__).read_text())
    methods = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not methods & {
        "SelectByID2",
        "SelectEntity",
        "SelectByRay",
        "SetAttachedEntities",
        "InsertGtol",
        "SetSymbolXml",
    }
    assert {
        "RunCommand",
        "IsCommandEnabled",
        "SetPosition2",
        "GetPosition",
        "GetOutline",
        "GetSelectedObjectsDrawingView2",
    } <= methods


def test_full_native_witness_is_read_only_before_and_after_final_bank(monkeypatch):
    adapter, view, rows, measure = native_context(monkeypatch)
    measured = Mock(side_effect=measure)
    result = arrange(adapter, view, measured)["front"]
    assert measured.call_count == 2 * len(rows)
    for annotation in rows:
        assert (
            annotation.GetSpecificAnnotation.return_value.GetFrameCount.call_count == 2
        )
        assert annotation.GetAttachedEntities3.call_count == 2
    assert all(
        call["body_union_source"] == "derived_translation"
        for call in result["commands"]
    )
    assert result["body_before_source"] == "derived_translation"
    assert result["body_after_source"] == "native_measurement"


def test_intermediate_shape_change_cannot_become_the_new_accepted_body(monkeypatch):
    adapter, view, rows, measure = native_context(monkeypatch, count=3)
    native_command = adapter.swApp.RunCommand.side_effect

    def change_shape(command, title):
        native_command(command, title)
        if command == 317:
            rows[0].size = (0.15, 0.1)
        return True

    adapter.swApp.RunCommand.side_effect = change_shape
    with pytest.raises(RuntimeError, match="body did not translate rigidly"):
        arrange(adapter, view, measure)


@pytest.mark.parametrize("field", ["quantity", "frame", "entity"])
def test_intermediate_content_drift_is_rejected_by_the_final_full_witness(
    monkeypatch, field
):
    adapter, view, rows, measure = native_context(monkeypatch, count=3)
    measured = Mock(side_effect=measure)
    native_command = adapter.swApp.RunCommand.side_effect

    def corrupt(command, title):
        native_command(command, title)
        if command == 317:
            gtol = rows[0].GetSpecificAnnotation.return_value
            if field == "quantity":
                gtol.GetTextAtIndex.side_effect = lambda index: ("0.05", "WRONG SIDE")[
                    index
                ]
            if field == "frame":
                gtol.GetFrame.return_value.GetSymbolXml.return_value = (
                    '<frame tolerance="0.50"/>'
                )
            if field == "entity":
                rows[0].GetAttachedEntities3.return_value = (object(),)
        return True

    adapter.swApp.RunCommand.side_effect = corrupt
    with pytest.raises(RuntimeError, match="final native witness"):
        arrange(adapter, view, measured)
    assert measured.call_count == 2 * len(rows)
    assert adapter.swApp.RunCommand.call_count == 2
    assert any(annotation.SetPosition2.call_count for annotation in rows)
