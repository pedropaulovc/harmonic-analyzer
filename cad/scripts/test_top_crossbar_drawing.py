"""Offline contracts for the top-crossbar drawing."""

from __future__ import annotations

from pathlib import Path

import pytest

import build_top_crossbar as part
import draw_top_crossbar as drawing
import top_crossbar_spec
from _drawing_registry import DRAWINGS_BY_NAME
from cone_pivot_post_installation import (
    FRAME_COLUMN_Z_CENTER,
    FRAME_FRONT_COLUMN_Z,
    FRAME_REAR_COLUMN_Z,
    SUMMING_Z,
)


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/top-crossbar.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/top-crossbar.pdf")
    assert drawing.PNG.as_posix().endswith("/png/top-crossbar_drawing.png")
    assert DRAWINGS_BY_NAME["top_crossbar"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is top_crossbar_spec.DRAWING_DIMENSIONS
    marked = set().union(*top_crossbar_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.TOP_KEEP) | set(drawing.FRONT_KEEP)
    assert kept == marked
    assert (drawing.BAR_WIDTH, drawing.BAR_HEIGHT) == (
        top_crossbar_spec.BAR_WIDTH,
        top_crossbar_spec.BAR_HEIGHT,
    )
    assert drawing.STUD_HOLE_Z == top_crossbar_spec.STUD_HOLE_Z
    assert top_crossbar_spec.BAR_FRONT_Z == -101.0
    assert top_crossbar_spec.BAR_REAR_Z == 136.415


def test_asymmetric_frame_span_and_off_centre_stud_contract() -> None:
    """The bar follows the frame while its stud stays on the summing axis."""
    assert FRAME_FRONT_COLUMN_Z == -112.0
    assert FRAME_REAR_COLUMN_Z == 147.415
    assert top_crossbar_spec.BAR_FRONT_Z == -101.0
    assert top_crossbar_spec.BAR_REAR_Z == 136.415
    assert top_crossbar_spec.BAR_CENTER_Z == FRAME_COLUMN_Z_CENTER
    assert top_crossbar_spec.BAR_CENTER_Z == pytest.approx(17.7075)
    assert top_crossbar_spec.BAR_HALF_Z == pytest.approx(118.7075)
    assert top_crossbar_spec.BAR_LENGTH == pytest.approx(237.415)
    assert top_crossbar_spec.BAR_CENTER_Z - top_crossbar_spec.BAR_HALF_Z == pytest.approx(-101.0)
    assert top_crossbar_spec.BAR_CENTER_Z + top_crossbar_spec.BAR_HALF_Z == pytest.approx(136.415)

    assert top_crossbar_spec.STUD_HOLE_Z == pytest.approx(17.7075)
    assert top_crossbar_spec.BAR_CENTER_Z + top_crossbar_spec.STUD_HOLE_Z == pytest.approx(SUMMING_Z)


def test_part_and_drawing_apply_the_same_local_stud_offset() -> None:
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'set_global(adapter, "StudHoleZ", f"{STUD_HOLE_Z}mm")' in part_source
    assert '[[0.0, 0.0, STUD_HOLE_Z]]' in part_source
    assert 'hole_center_y = TOP_CENTER[1] + STUD_HOLE_Z / 2000.0' in drawing_source


def test_linked_notes_define_remaining_casting_requirements() -> None:
    notes = top_crossbar_spec.DRAWING_NOTES
    assert "GRAY-IRON CASTING" in notes
    assert "NO DRAFT MODELLED" in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "add_native_hole_callout(" in source
    assert "def _manufacturing_notes" not in source


def test_native_gdt_controls_crossbar_end_seats_and_hole() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 3
    assert source.count("add_feature_control_frame(") == 3
    assert "characteristic=\"position\"" in source
    assert "characteristic=\"perpendicularity\"" in source
    assert "characteristic=\"parallelism\"" in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(1, 1)") == 1
    assert source.count("scale=(1, 2)") == 2
    assert top_crossbar_spec.TOP_VIEW_NOTE == "TOP VIEW SCALE 1:2"
    assert top_crossbar_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
    assert 'add_property_linked_note(adapter, "Top View Note"' in source
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("top-crossbar")
    assert "gray cast iron" in str(config["material_specification"]).lower()
    assert "green enamel" in str(config["finish"]).lower()
    assert int(config["quantity"]) == 1
