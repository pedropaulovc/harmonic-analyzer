"""Offline contracts for the connecting-rod drawing."""

from __future__ import annotations

from pathlib import Path

import ch_connecting_rod_notes
import ch_connecting_rod_spec
import draw_ch_connecting_rod as drawing
import build_ch_connecting_rod as rod
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-connecting-rod.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-connecting-rod.pdf")
    assert drawing.PNG.as_posix().endswith("/png/ch-connecting-rod_drawing.png")
    assert DRAWINGS_BY_NAME["ch_connecting_rod"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert rod.DRAWING_DIMENSIONS is ch_connecting_rod_notes.DRAWING_DIMENSIONS
    marked = set().union(*ch_connecting_rod_notes.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked


def test_draw_view_math_matches_the_spec() -> None:
    assert (drawing.CENTER_DISTANCE, drawing.HEAD_TOP_Y) == (
        ch_connecting_rod_spec.CENTER_DISTANCE,
        ch_connecting_rod_spec.HEAD_TOP_Y,
    )
    assert ch_connecting_rod_spec.CENTER_DISTANCE == rod.CENTER_DISTANCE
    assert ch_connecting_rod_spec.RING_BORE_DIA == rod.RING_BORE_DIA
    assert ch_connecting_rod_spec.RING_BORE_DIA_BAND == rod.RING_BORE_DIA_BAND
    assert ch_connecting_rod_spec.SHANK_WIDTH == rod.SHANK_WIDTH
    assert ch_connecting_rod_spec.RING_THICKNESS == rod.RING_THICKNESS
    assert ch_connecting_rod_spec.SHANK_THICKNESS == rod.SHANK_THICKNESS
    assert ch_connecting_rod_spec.HEAD_WIDTH == rod.HEAD_WIDTH
    assert ch_connecting_rod_spec.HEAD_HEIGHT == rod.HEAD_HEIGHT
    assert ch_connecting_rod_spec.HEAD_CROWN_ABOVE_PIN == rod.HEAD_CROWN_ABOVE_PIN
    assert ch_connecting_rod_spec.HEAD_THICKNESS == rod.HEAD_THICKNESS


def test_rod_length_closes_the_raised_cam_to_the_level_rocker() -> None:
    import math

    import channel_frame_geom as frame
    import ch_rocker_arm_spec as rocker
    import dt_cylinder_gear_spec as cylinder

    pin = (
        frame.ROCKER_PIVOT_XY[0] - rocker.ROD_HOLE_X,
        frame.ROCKER_PIVOT_XY[1] + rocker.ROD_HOLE_Y - rocker.PIVOT_MID_Y,
    )
    phase = math.radians(frame.CYLINDER_LOCK_PHASE_DEG)
    cam = (
        frame.CAM_SHAFT_XY[0] + cylinder.ECCENTRICITY * math.sin(phase),
        frame.CAM_SHAFT_XY[1] + cylinder.ECCENTRICITY * math.cos(phase),
    )
    assert abs(rod.CENTER_DISTANCE - math.dist(pin, cam)) < 1e-9


def test_pin_hole_is_part_owned_and_drawing_geometry_is_derived() -> None:
    assert rod.PIN_HOLE_SPEC is ch_connecting_rod_spec.PIN_HOLE_SPEC
    assert drawing.PIN_HOLE_SPEC is ch_connecting_rod_spec.PIN_HOLE_SPEC
    assert drawing._PIN_HOLE_DIA == blind_cut_dia_mm(ch_connecting_rod_spec.PIN_HOLE_SPEC)
    source = Path(rod.__file__).read_text(encoding="utf-8")
    assert "HoleSpec(" not in source
    assert "\n        PIN_HOLE_SPEC," in source
    assert "expect_dia_mm=blind_cut_dia_mm(PIN_HOLE_SPEC)" in source


def test_sheet_runs_at_1_to_1_with_1_to_2_isometric() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 2)" in source  # the isometric override
    assert drawing.LEFT_CENTER == (0.080, 0.171)
    assert (
        'add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.070)'
        in source
    )
    assert ch_connecting_rod_notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_are_functional_and_not_title_block_duplicates() -> None:
    notes = ch_connecting_rod_notes.DRAWING_NOTES
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
    assert "Ra " not in notes  # the title-block surface row is never restated
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
    assert 'label="strap bore axis",' in source
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
    assert ch_connecting_rod_spec.RING_BORE_DIA_BAND == (0.10, 0.00)
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

    spec = _config.parts("ch-connecting-rod")
    assert spec["material_specification"] == "LOW-CARBON STEEL OR GRAY IRON"
    assert spec["finish"] == (
        "BLACK ENAMEL; MASK STRAP BORE + PIN HOLE; OIL BARE MACHINED SURFACES"
    )
    assert int(spec["quantity"]) == 20
