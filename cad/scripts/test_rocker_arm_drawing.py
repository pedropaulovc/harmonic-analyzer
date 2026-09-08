"""Offline contracts for the rocker-arm drawing."""

from __future__ import annotations

import math
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from _drawing_test_support import linked_note_properties

import rocker_arm_notes
import rocker_arm_spec
import draw_rocker_arm as drawing
import build_rocker_arm as arm
from _drawing_registry import DRAWINGS_BY_NAME
from cone_pivot_post_installation import MECHANISM_X_SHIFT


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/rocker-arm.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/rocker-arm.pdf")
    assert drawing.PNG.as_posix().endswith("/png/rocker-arm_drawing.png")
    assert DRAWINGS_BY_NAME["rocker_arm"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: build marks exactly the spec's map, the drawing keeps
    # exactly its union across the per-view keep-maps.
    assert arm.DRAWING_DIMENSIONS is rocker_arm_notes.DRAWING_DIMENSIONS
    marked = set().union(*rocker_arm_notes.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept | drawing.NOTE_ONLY_DIMENSIONS == marked


def test_draw_view_math_matches_the_spec() -> None:
    # The drawing's view math reads the spec's nominal spans, not a divergent
    # copy; the spec's geometry must match the part the build actually builds.
    assert (drawing.ROD_HOLE_X, drawing.TOP_END_Y) == (
        rocker_arm_spec.ROD_HOLE_X,
        rocker_arm_spec.TOP_END_Y,
    )
    assert rocker_arm_spec.CURVE_RADIUS == arm.CURVE_RADIUS
    assert rocker_arm_spec.ARM_DEPTH == arm.ARM_DEPTH
    assert rocker_arm_spec.ARM_THICKNESS == arm.ARM_THICKNESS
    assert rocker_arm_spec.TOP_ARC_LEN == arm.TOP_ARC_LEN
    assert rocker_arm_spec.BOT_ARC_LEN == arm.BOT_ARC_LEN
    assert rocker_arm_spec.TIP_FACE == arm.TIP_FACE
    assert rocker_arm_spec.ROD_HOLE_X == arm.ROD_HOLE_X


def test_rod_pin_follows_the_recentered_cam_and_recloses_neutral_y() -> None:
    assert math.isclose(
        rocker_arm_spec.ROD_HOLE_X,
        127.3738 - MECHANISM_X_SHIFT,
        abs_tol=1e-12,
    )
    assert math.isclose(rocker_arm_spec.ROD_HOLE_Y, 16.456064115939025, abs_tol=1e-12)
    assert rocker_arm_spec.ROD_HOLE_ABOVE_BOTTOM == arm.ROD_HOLE_ABOVE_BOTTOM
    assert rocker_arm_spec.ROD_HOLE_Y == arm.ROD_HOLE_Y


def test_sheet_runs_at_1_to_2() -> None:
    assert drawing.SHEET_SCALE == (1.0, 2.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 2)" in source
    assert rocker_arm_notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:4"
    assert "Isometric View Note" in linked_note_properties(source)


def test_linked_notes_are_functional_metric_and_not_title_block_duplicates() -> None:
    notes = rocker_arm_notes.DRAWING_NOTES
    assert "R800" in notes
    assert "R816" in notes
    # The rod hole rides its native Ø1.99 THRU ALL callout; the notes state
    # count and process only, never a second copy of a sheet dimension.
    assert "(1X)" in notes
    assert "#47" not in notes
    assert "REAM +0.03/0" in notes
    assert "16.00 REF" in notes
    assert "11.5 IN" not in notes
    assert "0.22 IN" not in notes
    # General tolerances live in the title block ONLY.
    assert "LINEAR +/-" not in notes
    assert "BA" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "Manufacturing Notes" in linked_note_properties(source)


def test_native_gdt_and_finish_present() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # A = pivot bore axis, B = broad face (right end view), C = rod-side tip
    # face; the rod-pin position frame references all three.
    assert source.count("add_datum_feature(") == 3
    assert "position_tolerance_m=" not in source
    assert 'entity=entities["pivot"]' in source
    assert 'label="pivot bore cylindrical datum feature"' in source
    assert source.count("shoulder=True") == 1
    assert source.count("add_feature_control_frame(") == 1
    assert 'datums=("A", "B", "C")' in source
    assert 'characteristic="position"' in source
    assert "add_surface_finish(" in source
    assert "add_native_hole_callout(" in source
    assert 'edge=entities["rod"]' in source
    assert 'entity=entities["rod"]' in source


def test_large_radius_values_are_note_only() -> None:
    assert drawing.NOTE_ONLY_DIMENSIONS == {"TopRadius", "BottomRadius"}
    assert "R800" in rocker_arm_notes.DRAWING_NOTES
    assert "R816" in rocker_arm_notes.DRAWING_NOTES


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(arm.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("rocker-arm")
    assert spec["material_specification"] == "AISI 1018 cold-rolled steel strap"
    assert spec["finish"] == "matte black oxide"
    assert int(spec["quantity"]) == 20


def test_surface_finish_is_part_owned_authored_and_consumed() -> None:
    (control,) = rocker_arm_spec.SURFACE_FINISHES
    assert control.key == "pivot_bore"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == rocker_arm_spec.PIVOT_HOLE_DIA
    assert arm.PIVOT_HOLE_DIA == rocker_arm_spec.PIVOT_HOLE_DIA
    part_source = "".join(Path(arm.__file__).read_text(encoding="utf-8").split())
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    sheet_source = "".join(Path(drawing.__file__).read_text(encoding="utf-8").split())
    assert (
        'control=surface_finish_by_key(SURFACE_FINISHES,"pivot_bore")' in sheet_source
    )
    assert "roughness_ra=" not in sheet_source


def _right_inventory_context(tmp_path, monkeypatch, inventory, *, introduced_at):
    """Run the actual recipe; replace only its external CAD/layout operations."""
    source = tmp_path / "rocker-arm.SLDPRT"
    source.write_bytes(b"COM-free recipe fixture; never opened by SolidWorks")
    monkeypatch.setattr(drawing, "SOURCE", source)
    events = []
    state = {"inventory": inventory if introduced_at == "creation" else ()}

    def read_right(kind):
        assert kind == 4
        events.append("read-right")
        if isinstance(state["inventory"], BaseException):
            raise state["inventory"]
        return state["inventory"]

    front = SimpleNamespace(ReferencedDocument=object())
    right = SimpleNamespace(GetAnnotationsByType=Mock(side_effect=read_right))
    iso = object()
    adapter = SimpleNamespace(
        currentModel=object(),
        open_model=AsyncMock(return_value=SimpleNamespace(is_success=True, data=None)),
    )
    factory = Mock(return_value=(adapter.currentModel, object()))
    monkeypatch.setattr(drawing, "place_view", Mock(side_effect=(front, right, iso)))
    for name in (
        "read_required_properties",
        "stamp_drawing_summary",
        "set_hidden_lines_removed",
        "set_hidden_lines_visible",
        "add_native_hole_callout",
        "add_entity_dimension",
        "set_basic_dimension",
        "add_datum_feature",
        "add_surface_finish",
        "add_feature_control_frame",
        "auto_arrange_view_dimensions",
    ):
        monkeypatch.setattr(drawing, name, Mock())
    monkeypatch.setattr(drawing, "auto_center_marks", Mock(return_value=True))
    monkeypatch.setattr(
        drawing,
        "add_property_linked_note",
        Mock(
            side_effect=lambda *_: SimpleNamespace(
                GetAnnotation=Mock(return_value=object())
            )
        ),
    )
    monkeypatch.setattr(
        drawing,
        "ModelEntities",
        lambda _: SimpleNamespace(
            resolve=lambda roles: {key: object() for key in roles}
        ),
    )
    retain = Mock()
    monkeypatch.setattr(drawing, "retain_view_dimensions", retain)

    def layout(current, **kwargs):
        assert current is adapter
        assert kwargs["views"] == {"front": front, "right": right, "iso": iso}
        events.append("layout")
        if introduced_at == "layout":
            state["inventory"] = inventory

    monkeypatch.setattr(
        drawing, "repair_project_drawing_layout", Mock(side_effect=layout)
    )

    async def finalize(*_args, **_kwargs):
        events.append("finalize")
        return {"drawing": "COM-free result"}

    finalizer = AsyncMock(side_effect=finalize)
    monkeypatch.setattr(drawing, "finalize_drawing", finalizer)
    return SimpleNamespace(
        adapter=adapter,
        factory=factory,
        right=right,
        front=front,
        iso=iso,
        state=state,
        events=events,
        retain=retain,
        finalizer=finalizer,
    )


@pytest.mark.parametrize("introduced_at", ["creation", "layout"])
@pytest.mark.parametrize("kind", ["visible", "hidden", "unnamed", "duplicate", "null"])
def test_final_right_inventory_rejects_any_entry_before_finalize(
    tmp_path, monkeypatch, introduced_at, kind
):
    dimension = SimpleNamespace(name="Unexpected", Visible=1)
    inventory = [dimension]
    if kind == "hidden":
        dimension.Visible = 3
    if kind == "unnamed":
        dimension.name = ""
    if kind == "duplicate":
        inventory.append(dimension)
    if kind == "null":
        inventory = [None]
    context = _right_inventory_context(
        tmp_path, monkeypatch, inventory, introduced_at=introduced_at
    )
    with pytest.raises(
        RuntimeError, match="rocker right view must contain no display dimensions"
    ):
        asyncio.run(drawing.build(context.adapter, drawing_factory=context.factory))
    context.finalizer.assert_not_awaited()
    context.retain.assert_called_once_with(
        context.adapter, context.front, keep=drawing.FRONT_KEEP, view_label="front"
    )
    context.right.GetAnnotationsByType.assert_called_once_with(4)
    assert context.events == ["layout", "read-right"]
    assert context.state["inventory"] is inventory
    assert inventory == (
        [None] if kind == "null" else [dimension] * (2 if kind == "duplicate" else 1)
    )


@pytest.mark.parametrize("inventory", [None, (), []])
def test_final_right_inventory_native_empty_result_preserves_normal_finalize(
    tmp_path, monkeypatch, inventory
):
    context = _right_inventory_context(
        tmp_path, monkeypatch, inventory, introduced_at="creation"
    )
    assert asyncio.run(
        drawing.build(context.adapter, drawing_factory=context.factory)
    ) == {"drawing": "COM-free result"}
    context.finalizer.assert_awaited_once_with(
        context.adapter,
        drawing.OUTPUTS,
        pdf_title="Rocker Arm Manufacturing Drawing",
        scale=drawing.SHEET_SCALE,
    )
    context.retain.assert_called_once_with(
        context.adapter, context.front, keep=drawing.FRONT_KEEP, view_label="front"
    )
    drawing.auto_arrange_view_dimensions.assert_called_once_with(
        context.adapter, (context.front, context.right, context.iso)
    )
    context.right.GetAnnotationsByType.assert_called_once_with(4)
    assert context.events == ["layout", "read-right", "finalize"]


def test_final_right_inventory_preserves_native_getter_error(tmp_path, monkeypatch):
    native_error = RuntimeError("native right annotation inventory failed")
    context = _right_inventory_context(
        tmp_path, monkeypatch, native_error, introduced_at="creation"
    )
    with pytest.raises(
        RuntimeError, match="native right annotation inventory failed"
    ) as caught:
        asyncio.run(drawing.build(context.adapter, drawing_factory=context.factory))
    assert caught.value is native_error
    context.finalizer.assert_not_awaited()
    context.right.GetAnnotationsByType.assert_called_once_with(4)
    assert context.events == ["layout", "read-right"]


def test_right_inventory_contract_cannot_silently_become_nonempty(
    tmp_path, monkeypatch
):
    context = _right_inventory_context(
        tmp_path, monkeypatch, (), introduced_at="creation"
    )
    monkeypatch.setattr(drawing, "RIGHT_KEEP", ("Unexpected",))
    with pytest.raises(
        ValueError, match="rocker right view requires an empty dimension contract"
    ):
        asyncio.run(drawing.build(context.adapter, drawing_factory=context.factory))
    context.adapter.open_model.assert_not_awaited()
    context.factory.assert_not_called()
    context.finalizer.assert_not_awaited()
    context.right.GetAnnotationsByType.assert_not_called()
