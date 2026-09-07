"""Offline contracts for the channel-lever drawing."""

from __future__ import annotations

import ast
from pathlib import Path
from _drawing_test_support import linked_note_properties
import pytest

import channel_lever_spec
import draw_channel_lever as drawing
import build_channel_lever as lever
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/channel-lever.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/channel-lever.pdf")
    assert drawing.PNG.as_posix().endswith("/png/channel-lever_drawing.png")
    assert DRAWINGS_BY_NAME["channel_lever"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert lever.DRAWING_DIMENSIONS is channel_lever_spec.DRAWING_DIMENSIONS
    marked = set().union(*channel_lever_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert "TipCentreX" in marked


def test_draw_view_math_matches_the_spec() -> None:
    assert (drawing.LEVER_SPRING_X, drawing.BAR_PIN_X) == (
        channel_lever_spec.LEVER_SPRING_X,
        channel_lever_spec.BAR_PIN_X,
    )
    assert channel_lever_spec.LEVER_SPRING_X == lever.LEVER_SPRING_X
    assert channel_lever_spec.BAR_PIN_X == lever.BAR_PIN_X
    assert channel_lever_spec.PIVOT_HOLE_DIA == lever.PIVOT_HOLE_DIA


def test_sheet_runs_at_1_to_2_with_1_to_4_isometric() -> None:
    # New declared layout requirement: half-scale orthographic views leave room
    # for the measured datum/GTol envelopes; the model dimensions do not change.
    assert drawing.SHEET_SCALE == (1.0, 2.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 4)" in source  # the isometric override
    assert channel_lever_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:4"
    assert "Isometric View Note" in linked_note_properties(source)


def test_all_orthographic_views_and_final_sheet_share_declared_scale() -> None:
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    views = {
        ast.literal_eval(call.args[2]): call
        for call in calls
        if call.func.id == "place_view"
    }
    assert set(views) == {"*Front", "*Right", "*Top", "*Isometric"}
    sheet_calls = [
        call
        for call in calls
        if call.func.id in {"new_project_drawing", "finalize_drawing"}
    ]
    assert len(sheet_calls) == 2
    for call in [views["*Front"], views["*Right"], views["*Top"], *sheet_calls]:
        scale = next(
            keyword.value for keyword in call.keywords if keyword.arg == "scale"
        )
        assert isinstance(scale, ast.Name) and scale.id == "SHEET_SCALE"
    iso_scale = next(
        keyword.value
        for keyword in views["*Isometric"].keywords
        if keyword.arg == "scale"
    )
    assert ast.literal_eval(iso_scale) == (1, 4)


@pytest.mark.parametrize(
    "projection,center",
    [(drawing._sheet_xy, drawing.FRONT_CENTER), (drawing._top_xy, drawing.TOP_CENTER)],
)
def test_half_scale_text_projection_uses_model_mm_and_view_center(projection, center):
    assert projection(drawing._BBOX_CX, 0.0) == pytest.approx(center)
    assert projection(drawing._BBOX_CX + 20.0, -8.0) == pytest.approx(
        (center[0] + 0.010, center[1] - 0.004)
    )


@pytest.mark.parametrize(
    "projection,center",
    [(drawing._sheet_xy, drawing.FRONT_CENTER), (drawing._top_xy, drawing.TOP_CENTER)],
)
def test_text_projection_derives_both_axes_from_declared_scale(
    monkeypatch, projection, center
):
    monkeypatch.setattr(drawing, "SHEET_SCALE", (2.0, 5.0))
    assert projection(drawing._BBOX_CX + 20.0, -8.0) == pytest.approx(
        (center[0] + 0.008, center[1] - 0.0032)
    )


def test_linked_notes_are_functional_and_not_title_block_duplicates() -> None:
    notes = channel_lever_spec.DRAWING_NOTES
    assert "6.50 +0.03/0" in notes
    assert "DATUM C IS THE LONG TOP FACE" in notes
    assert "BASIC 4.75 BELOW C" in notes
    assert "BAR-PIN 127.00; SHOULDER 169.00" in notes
    assert "SPRING-HOLE 177.80; TIP R3 CENTRE 182.80" in notes
    assert "NOT CONCENTRIC" in notes
    assert "#47 DRILL" not in notes
    assert "#21 DRILL" not in notes
    assert "LINEAR +/-" not in notes
    assert "GRAY-IRON" not in notes
    assert "GREEN ENAMEL" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "Manufacturing Notes" in linked_note_properties(source)


def test_native_gdt_and_finish_present() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "bar_height = add_entity_dimension(" in source
    assert (
        'set_basic_dimension(adapter, bar_height, label="bar height from datum C")'
        in source
    )
    assert source.count("add_datum_feature(") == 3
    assert 'label="fulcrum bore axis"' in source
    assert "position_tolerance_m=" not in source
    assert source.count("_force_dimension_black(") == 3
    assert source.count("annotation.Color = 0") == 1
    assert "annotation.LayerOverride" in source
    assert "InsertCenterMark3(2, False, False)" in source
    assert "view.SelectEntity(tip_arc, False)" in source
    assert source.count("add_feature_control_frame(") == 5
    assert source.count('characteristic="position"') == 2
    assert source.count('datums=("A", "B", "C")') == 3
    assert 'characteristic="profile_surface"' in source
    assert 'characteristic="perpendicularity"' in source
    assert 'characteristic="parallelism"' in source
    assert source.count('datums=("A",)') == 2
    assert "all_around=True" in source
    assert 'entity=entities["bar_pin"]' in source
    assert 'label="bar-pin hole position"' in source
    assert 'entity=entities["spring"]' in source
    assert 'label="spring-eye hole position"' in source
    assert "frame_xy=" not in source
    assert "add_surface_finish(" not in source
    assert source.count("add_native_hole_callout(") == 2


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(lever.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("channel-lever")
    assert spec["material_specification"] == "ASTM A48 Class 30 gray cast iron"
    assert spec["material"] == "ASTM A48 Class 30 gray cast iron"
    assert spec["finish"] == (
        "RAL 6005 alkyd enamel, SSPC-SP3, 40-60 um DFT; mask all bores"
    )
    assert int(spec["quantity"]) == 20
