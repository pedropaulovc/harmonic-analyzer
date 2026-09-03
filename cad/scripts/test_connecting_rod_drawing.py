"""Offline contracts for the connecting-rod drawing."""

from __future__ import annotations

import math
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


def test_draw_view_math_matches_the_clevis_spec() -> None:
    assert (drawing.CENTER_DISTANCE, drawing.CLEVIS_TOP_Y) == (
        connecting_rod_spec.CENTER_DISTANCE,
        connecting_rod_spec.CLEVIS_TOP_Y,
    )
    assert connecting_rod_spec.CENTER_DISTANCE == rod.CENTER_DISTANCE
    assert connecting_rod_spec.RING_BORE_DIA == rod.RING_BORE_DIA
    assert connecting_rod_spec.RING_BORE_DIA_BAND == rod.RING_BORE_DIA_BAND
    assert connecting_rod_spec.SHANK_WIDTH == rod.SHANK_WIDTH
    assert connecting_rod_spec.RING_THICKNESS == rod.RING_THICKNESS
    assert connecting_rod_spec.SHANK_THICKNESS == rod.SHANK_THICKNESS
    assert connecting_rod_spec.PRONG_WIDTH_X == rod.PRONG_WIDTH_X == 8.0
    assert connecting_rod_spec.PRONG_HEIGHT == rod.PRONG_HEIGHT == 12.0
    assert connecting_rod_spec.PRONG_THICKNESS == rod.PRONG_THICKNESS == 1.0
    assert connecting_rod_spec.CLEVIS_SLOT_WIDTH == rod.CLEVIS_SLOT_WIDTH == 2.9
    assert connecting_rod_spec.CLEVIS_OUTSIDE_WIDTH == 4.9


def test_clevis_local_z_envelopes_and_connected_transition() -> None:
    spec = connecting_rod_spec
    assert math.isclose(spec.NEAR_PRONG_Z_MIN, -2.6, abs_tol=1e-12)
    assert math.isclose(spec.NEAR_PRONG_Z_MAX, -1.6, abs_tol=1e-12)
    assert math.isclose(spec.SLOT_Z_MIN, -5.5, abs_tol=1e-12)
    assert math.isclose(spec.SLOT_Z_MAX, -2.6, abs_tol=1e-12)
    assert math.isclose(spec.FAR_PRONG_Z_MIN, -6.5, abs_tol=1e-12)
    assert math.isclose(spec.FAR_PRONG_Z_MAX, -5.5, abs_tol=1e-12)
    assert math.isclose(spec.CLEVIS_CENTER_Z_LOCAL, -4.05, abs_tol=1e-12)
    assert spec.OFFSET_NECK_Z_MIN < spec.NEAR_PRONG_Z_MAX
    assert spec.OFFSET_NECK_Z_MAX > -spec.SHANK_THICKNESS / 2.0
    assert spec.CLEVIS_WEB_TOP_Y - spec.CLEVIS_ROOT_Y == 0.5
    source = Path(rod.__file__).read_text(encoding="utf-8")
    assert source.count("await add_prong(") == 2
    assert 'await add_bridge(\n        "ClevisWeb"' in source
    assert 'await add_bridge(\n        "OffsetNeck"' in source
    assert "[[0.0, CENTER_DISTANCE, NEAR_PRONG_Z_MAX]]" in source
    assert "(0.0, 0.0, 1.0)" in source


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
    assert "RING 3.00 THICK; SHANK 2.50 THICK" in notes
    assert "EXTENDS ONLY TO THE CLEVIS ROOT" in notes
    assert "0.10 MIN CLR/SIDE" in notes
    assert "RING WALL 4.50 MIN AFTER BORING" in notes
    assert "NO DRAFT REQUIRED" in notes
    assert "HANGS PLUMB" not in notes  # not an inspectable requirement
    assert "SHANK C/L" not in notes  # the 4.00 BASIC from datum B owns it
    assert "TWO D-SHAPED PRONGS, 8.00 W x 12.00 HIGH" in notes
    assert "PRONGS 1.00 THICK ABOUT A 2.90 SLOT" in notes
    assert "PIN HOLE 1X THRU BOTH PRONGS" in notes
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
