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
    assert "#47 DRILL" in notes
    assert "#21 DRILL" in notes
    assert "LINEAR +/-" not in notes
    assert "GRAY-IRON" not in notes
    assert "GREEN ENAMEL" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_native_gdt_and_finish_present() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 1
    assert source.count("add_feature_control_frame(") == 1
    assert 'characteristic="position"' in source
    assert "add_surface_finish(" in source
    assert source.count("add_native_hole_callout(") == 2


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(lever.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("channel-lever")
    assert spec["material_specification"] == "ASTM A48 Class 30 gray cast iron"
    assert spec["finish"] == "green enamel; bore + holes masked"
    assert int(spec["quantity"]) == 20
