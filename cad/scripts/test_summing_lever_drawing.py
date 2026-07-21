"""Offline contracts for the summing-lever drawing."""

from __future__ import annotations

from pathlib import Path

import summing_lever_spec
import draw_summing_lever as drawing
import build_summing_lever as lever
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/summing-lever.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/summing-lever.pdf")
    assert drawing.PNG.as_posix().endswith("/png/summing-lever_drawing.png")
    assert DRAWINGS_BY_NAME["summing_lever"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert lever.DRAWING_DIMENSIONS is summing_lever_spec.DRAWING_DIMENSIONS
    marked = set().union(*summing_lever_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked


def test_draw_view_math_matches_the_spec() -> None:
    assert (drawing.PLATE_W, drawing.TIP_X) == (
        summing_lever_spec.PLATE_W,
        summing_lever_spec.TIP_X,
    )
    assert summing_lever_spec.CYL_R == lever.CYL_R
    assert summing_lever_spec.ANCHOR_R == lever.ANCHOR_R
    assert summing_lever_spec.PLATE_W == lever.PLATE_W
    assert summing_lever_spec.PLATE_T == lever.PLATE_T
    assert summing_lever_spec.HEX_W == lever.HEX_W
    assert summing_lever_spec.HEX_H == lever.HEX_H
    assert summing_lever_spec.HEX_DEPTH == lever.HEX_DEPTH
    assert summing_lever_spec.HOLE_X == lever.HOLE_X
    assert summing_lever_spec.HOLE_COUNT == lever.HOLE_COUNT
    assert summing_lever_spec.CHANNEL_PITCH == lever.CHANNEL_PITCH


def test_sheet_runs_at_1_to_2_with_1_to_4_isometric() -> None:
    assert drawing.SHEET_SCALE == (1.0, 2.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 4)" in source  # the isometric override
    assert summing_lever_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:4"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_describe_the_hung_lever() -> None:
    notes = summing_lever_spec.DRAWING_NOTES
    assert "KNIFE EDGE" in notes
    assert "#47" in notes
    assert "7.0565 PITCH" in notes
    assert "4.60 FROM FREE PLATE EDGE" in notes
    assert "END OFFSETS 9.90 AND 8.43" in notes
    assert "76.20 FROM PIVOT AXIS" in notes
    assert "3.00 BORE" in notes
    assert "19.05 THICK" in notes
    assert "8.65 W x 10.27 HIGH" in notes
    assert "21.72 LONG EACH END" in notes
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
    assert source.count("add_native_hole_callout(") == 1
    assert "knife_edge = _top_xy" in source
    assert 'label="knife-edge ridge finish"' in source


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(lever.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("summing-lever")
    assert spec["material_specification"] == "ASTM A48 Class 30 gray cast iron"
    assert spec["finish"] == "green enamel; knife edges + anchor bore machined"
    assert int(spec["quantity"]) == 1
