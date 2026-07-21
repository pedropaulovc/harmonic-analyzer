"""Offline contracts for the connecting-rod drawing."""

from __future__ import annotations

from pathlib import Path

import connecting_rod_spec
import draw_connecting_rod as drawing
import build_connecting_rod as rod
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/connecting-rod.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/connecting-rod.pdf")
    assert drawing.PNG.as_posix().endswith("/png/connecting-rod_drawing.png")
    assert DRAWINGS_BY_NAME["connecting_rod"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert rod.DRAWING_DIMENSIONS is connecting_rod_spec.DRAWING_DIMENSIONS
    marked = set().union(*connecting_rod_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked


def test_draw_view_math_matches_the_spec() -> None:
    assert (drawing.CENTER_DISTANCE, drawing.HEAD_TOP_Y) == (
        connecting_rod_spec.CENTER_DISTANCE,
        connecting_rod_spec.HEAD_TOP_Y,
    )
    assert connecting_rod_spec.CENTER_DISTANCE == rod.CENTER_DISTANCE
    assert connecting_rod_spec.RING_BORE_DIA == rod.RING_BORE_DIA
    assert connecting_rod_spec.SHANK_WIDTH == rod.SHANK_WIDTH
    assert connecting_rod_spec.RING_THICKNESS == rod.RING_THICKNESS
    assert connecting_rod_spec.SHANK_THICKNESS == rod.SHANK_THICKNESS
    assert connecting_rod_spec.HEAD_WIDTH == rod.HEAD_WIDTH
    assert connecting_rod_spec.HEAD_HEIGHT == rod.HEAD_HEIGHT
    assert connecting_rod_spec.HEAD_CROWN_ABOVE_PIN == rod.HEAD_CROWN_ABOVE_PIN
    assert connecting_rod_spec.HEAD_THICKNESS == rod.HEAD_THICKNESS


def test_sheet_runs_at_1_to_1_with_1_to_2_isometric() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 2)" in source  # the isometric override
    assert connecting_rod_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_are_functional_and_not_title_block_duplicates() -> None:
    notes = connecting_rod_spec.DRAWING_NOTES
    assert "#47 DRILL" in notes
    assert "RING 3.0 THICK" in notes
    assert "SHANK AND HEAD\n   2.5 THICK" in notes
    assert "HEAD 10.0 W x 10.5 HIGH, R5.0" in notes
    assert "PIN C/L 2.40 BELOW CROWN" in notes
    assert "LINEAR +/-" not in notes
    assert "BA" not in notes
    assert "GRAY-IRON" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_native_gdt_and_finish_present() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 1
    assert source.count("add_feature_control_frame(") == 1
    assert 'characteristic="position"' in source
    assert "add_surface_finish(" in source
    assert "add_native_hole_callout(" in source


def test_bore_finish_is_routed_clear_of_the_lower_dimension_stack() -> None:
    edge_x, edge_y = drawing.BORE_FINISH_EDGE
    symbol_x, symbol_y = drawing.BORE_FINISH_SYMBOL
    assert symbol_x > edge_x
    assert symbol_y > edge_y
    assert symbol_y > drawing.FRONT_KEEP["StrapBoreDia"][1] + 0.010
    assert symbol_x < 0.250


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(rod.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("connecting-rod")
    assert spec["material_specification"] == "ASTM A48 Class 30 gray cast iron"
    assert spec["finish"] == "black rough cast; bore machined"
    assert int(spec["quantity"]) == 20
