"""Offline contracts for the channel-lever drawing."""

from __future__ import annotations

from pathlib import Path

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


def test_sheet_runs_at_1_to_1_with_1_to_4_isometric() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 4)" in source  # the isometric override
    assert channel_lever_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:4"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


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
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_native_gdt_and_finish_present() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'bar_height = add_edge_dimension(' in source
    assert 'set_basic_dimension(adapter, bar_height, label="bar height from datum C")' in source
    assert source.count("add_datum_feature(") == 3
    assert (
        'label="fulcrum bore axis",\n        position_tolerance_m=0.001'
        in source
    )
    assert source.count("position_tolerance_m=0.001") == 1
    assert source.count("_force_dimension_black(") == 3
    assert source.count("annotation.Color = 0") == 1
    assert "annotation.LayerOverride" in source
    assert "InsertCenterMark3(2, False, False)" in source
    assert "referenced_model_circular_edge(" in source
    assert "2.0 * TIP_RADIUS" in source
    assert "view.SelectEntity(tip_edge, False)" in source
    assert "GetVisibleEntities2" not in source
    assert source.count("add_feature_control_frame(") == 5
    assert source.count('characteristic="position"') == 2
    assert source.count('datums=("A", "B", "C")') == 3
    assert 'characteristic="profile_surface"' in source
    assert 'characteristic="perpendicularity"' in source
    assert 'characteristic="parallelism"' in source
    assert source.count('datums=("A",)') == 2
    assert "all_around=True" in source
    assert 'edge_xy=bar_pin_edge' in source
    assert 'label="bar-pin hole position"' in source
    assert 'edge_xy=spring_fcf_edge' in source
    assert 'label="spring-eye hole position"' in source
    assert "bar_pin_edge[0] - 0.045, 0.174" in source
    assert "spring_fcf_edge[0] + 0.020, 0.174" in source
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
