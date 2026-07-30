"""Offline contracts for the connecting-rod drawing."""

from __future__ import annotations

from pathlib import Path

import connecting_rod_notes
import connecting_rod_spec
import draw_connecting_rod as drawing
import build_connecting_rod as rod
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/connecting-rod.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/connecting-rod.pdf")
    assert drawing.PNG.as_posix().endswith("/png/connecting-rod_drawing.png")
    assert DRAWINGS_BY_NAME["connecting_rod"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert rod.DRAWING_DIMENSIONS is connecting_rod_notes.DRAWING_DIMENSIONS
    marked = set().union(*connecting_rod_notes.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked


def test_draw_view_math_matches_the_spec() -> None:
    assert (drawing.CENTER_DISTANCE, drawing.HEAD_TOP_Y) == (
        connecting_rod_spec.CENTER_DISTANCE,
        connecting_rod_spec.HEAD_TOP_Y,
    )
    assert connecting_rod_spec.CENTER_DISTANCE == rod.CENTER_DISTANCE
    assert connecting_rod_spec.RING_BORE_DIA == rod.RING_BORE_DIA
    assert connecting_rod_spec.RING_BORE_DIA_BAND == rod.RING_BORE_DIA_BAND
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
    assert drawing.LEFT_CENTER == (0.080, 0.171)
    assert 'add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.070)' in source
    assert connecting_rod_notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_are_functional_and_not_title_block_duplicates() -> None:
    notes = connecting_rod_notes.DRAWING_NOTES
    # The pin hole rides its native Ø1.99 THRU ALL callout and the bore its
    # imported model tolerance; notes never repeat a sheet dimension.
    assert "#47" not in notes
    assert "1X" in notes
    assert "RING 3.00 THICK, STEP AT THE RING OD" in notes
    assert "SHANK AND HEAD 2.50" in notes
    assert "ONE MIDPLANE" in notes
    assert "0.10 MIN CLR/SIDE" in notes
    assert "RING WALL 4.50 MIN AFTER BORING" in notes
    assert "NO DRAFT REQUIRED" in notes
    assert "HANGS PLUMB" not in notes  # not an inspectable requirement
    assert "SHANK C/L" not in notes  # the 4.00 BASIC from datum B owns it
    assert "HEAD 10.00 W x 10.50 HIGH, R5.00 CROWN" in notes
    assert "PIN C/L 2.40 BELOW CROWN" in notes  # one line, with the 1X count
    assert "AS CAST" in notes
    assert "147.67" not in notes  # the BASIC sheet dimension owns it
    assert "LINEAR +/-" not in notes
    assert "BA" not in notes
    assert "GRAY-IRON" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_native_gdt_and_finish_present() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # A = strap bore axis, B = shank left flank (clocking); the pin-hole
    # position frame references both and the bore imports its model-owned fit.
    assert source.count("add_datum_feature(") == 2
    assert 'label="strap bore axis",\n        position_tolerance_m=0.000005' in source
    assert source.count("add_feature_control_frame(") == 1
    assert 'datums=("A", "B")' in source
    assert 'characteristic="position"' in source
    assert '"StrapBoreDia": "BORE"' in source
    assert "+0.10/0" not in source
    assert "add_surface_finish(" in source
    assert "add_native_hole_callout(" in source
    # The callout owns the 9-o'clock rim; the position FCF anchors the
    # opposite 3-o'clock rim so the two leaders cannot cross.
    assert source.count("edge_xy=pin_rim") == 1
    assert source.count("edge_xy=pin_fcf_rim") == 1


def test_strap_bore_tolerance_is_owned_by_the_named_model_dimension() -> None:
    assert connecting_rod_spec.RING_BORE_DIA_BAND == (0.10, 0.00)
    assert model_toleranced_dimensions(rod) == {
        ("StrapBoreProfile", "StrapBoreDia"): "*deviations(RING_BORE_DIA_BAND)"
    }


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
