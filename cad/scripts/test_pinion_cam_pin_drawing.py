"""Offline contracts for the pinion cam-follower-pin drawing."""

from __future__ import annotations

from pathlib import Path

import pytest

import pinion_cam_pin_spec
import draw_pinion_cam_pin as drawing
import build_pinion_cam_pin as pin
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-cam-pin.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-cam-pin.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-cam-pin_drawing.png")
    assert DRAWINGS_BY_NAME["pinion_cam_pin"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert pin.DRAWING_DIMENSIONS is pinion_cam_pin_spec.DRAWING_DIMENSIONS
    assert pin.SURFACE_FINISHES is pinion_cam_pin_spec.SURFACE_FINISHES
    assert drawing.SURFACE_FINISHES is pinion_cam_pin_spec.SURFACE_FINISHES
    marked = set().union(*pinion_cam_pin_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert drawing.PIN_DIA == pinion_cam_pin_spec.PIN_DIA
    assert drawing.PIN_DIA == 4.0
    assert drawing.PIN_LEN == pinion_cam_pin_spec.PIN_LEN


def test_sheet_runs_at_8_to_1_with_a_4_to_1_pictorial() -> None:
    # Fable review r4: at 4:1 the pin was tiny and bunched in the top half.
    assert drawing.SHEET_SCALE == (8.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '"*Front", *FRONT_CENTER, scale=(8, 1)' in source
    assert '"*Right", *RIGHT_CENTER, scale=(8, 1)' in source
    assert '"*Isometric", *ISO_CENTER, scale=(4, 1)' in source
    # Every marked dimension belongs to a sketch on the Right plane, so the
    # side view must face that plane to import them natively.
    assert '"*Top", *RIGHT_CENTER' not in source
    build_source = Path(pin.__file__).read_text(encoding="utf-8")
    assert build_source.count('create_sketch("Right")') == 2
    assert 'create_sketch("Top")' not in build_source
    assert 'create_sketch("Front")' not in build_source
    assert pinion_cam_pin_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 4:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source
    assert "End View Note" not in source


def test_side_view_lies_as_turned_with_the_end_view_in_projection() -> None:
    """Machinist review of 7f7fc1717: the end view sat beside a vertical
    elevation, out of projection, carrying the only diameter.  The side view
    now lies horizontal (rule 7, turned parts), the end view projects to its
    left on the same Y station (third angle), and the Ø prints on the side
    view beside the length."""
    assert drawing.FRONT_CENTER[1] == drawing.RIGHT_CENTER[1]
    crown_apex_x = drawing.side_view_x(drawing.OVERALL)
    seated_end_x = drawing.side_view_x(0.0)
    assert seated_end_x - crown_apex_x == pytest.approx(drawing.OVERALL * drawing._S)
    end_view_right = drawing.FRONT_CENTER[0] + drawing.HALF_DIA
    assert end_view_right + 0.050 < crown_apex_x
    assert seated_end_x < 0.325  # clear of the isometric's note column
    assert drawing.ISO_NOTE_XY[0] > seated_end_x + 0.015
    top = drawing.RIGHT_CENTER[1] + drawing.HALF_DIA
    bottom = drawing.RIGHT_CENTER[1] - drawing.HALF_DIA
    # The two lengths sit above the view (overall outermost), the diameter
    # below, the crown leaders at the lower left of the crown.
    assert top < drawing.RIGHT_KEEP["Depth"][1] < drawing.OVERALL_TEXT_XY[1] < 0.255
    assert 0.080 < drawing.RIGHT_KEEP["PinDia"][1] < bottom
    assert drawing.RIGHT_KEEP["PinDia"][0] > drawing.RIGHT_CENTER[0]
    for x, y in (drawing.RIGHT_KEEP["CapR"], drawing.CROWN_FINISH_SYMBOL_XY):
        assert end_view_right < x < crown_apex_x
        assert 0.080 < y < drawing.RIGHT_CENTER[1]


def test_linked_notes_are_functional_and_carry_no_general_tolerance() -> None:
    notes = pinion_cam_pin_spec.DRAWING_NOTES
    assert len(notes.splitlines()) <= 4
    assert "LINEAR +/-" not in notes
    assert " BA " not in f" {notes} "
    assert "X.XX" not in notes
    # Fable r4: the first line restated what the views show.
    assert "ONE SPHERICAL CROWN" not in notes
    assert "EXEMPT FROM TITLE-BLOCK EDGE-BREAK" in notes
    assert "NO CHAMFER" in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_bonded_slip_fit_replaces_the_press() -> None:
    """U27 (Main, 2026-09-23): stock drill rod slipped into the strap's H7 seat
    and bonded with LOCTITE 638 (the U6 drum-to-arbor precedent)."""
    import pinion_bracket_spec

    assert pinion_cam_pin_spec.PIN_DIA == 4.0
    assert pinion_cam_pin_spec.PIN_DIA_BAND == (0.0, -0.03)
    assert pinion_cam_pin_spec.SEAT_BAND == pinion_bracket_spec.PIN_SEAT_DIA_BAND
    assert pinion_bracket_spec.PIN_BORE == pinion_cam_pin_spec.PIN_DIA
    seat_min = pinion_bracket_spec.PIN_BORE + pinion_bracket_spec.PIN_SEAT_DIA_BAND[1]
    seat_max = pinion_bracket_spec.PIN_BORE + pinion_bracket_spec.PIN_SEAT_DIA_BAND[0]
    pin_min = pinion_cam_pin_spec.PIN_DIA + pinion_cam_pin_spec.PIN_DIA_BAND[1]
    pin_max = pinion_cam_pin_spec.PIN_DIA + pinion_cam_pin_spec.PIN_DIA_BAND[0]
    assert round(seat_min - pin_max, 6) == 0.0
    assert round(seat_max - pin_min, 6) == 0.042
    assert seat_max - pin_min <= pinion_cam_pin_spec.RETAINING_COMPOUND_MAX_GAP_MM
    # Rule 6 (Main's MHA-116 eye pass): the bond is the fit-up step, not a note.
    notes = pinion_cam_pin_spec.DRAWING_NOTES
    assert "LOCTITE" not in notes and "ON ASSEMBLY" not in notes
    assert len(notes.splitlines()) == 2
    assert pinion_cam_pin_spec.ASSEMBLY_STEP == (
        "BOND MHA-116 INTO MHA-056 FOLLOWER SEAT WITH LOCTITE 638."
    )
    assert "MHA-056" in drawing.DIMENSION_CALLOUTS["PinDia"]
    assert "SLIP FIT" in drawing.DIMENSION_CALLOUTS["PinDia"]
    import draw_pinion_bracket

    assert "MHA-116" in draw_pinion_bracket.DIMENSION_CALLOUTS["PinSeatDia"]


def test_no_gdt_and_the_crown_carries_the_finish() -> None:
    """Policy rule 3: a pin is not on the GD&T allowlist.  Rule 5: the crown
    rides the cam; the bonded shank is a static seat."""
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert not hasattr(pinion_cam_pin_spec, "GEOMETRIC_TOLERANCES_MM")
    assert "add_datum_feature(" not in source
    assert "add_feature_control_frame(" not in source
    assert "add_view_centerline(" in source
    (control,) = pinion_cam_pin_spec.SURFACE_FINISHES
    assert control.key == "crown"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == 2.0 * pinion_cam_pin_spec.CAP_RADIUS
    assert source.count("add_surface_finish(") == 1
    assert 'surface_finish_by_key(SURFACE_FINISHES, "crown")' in source
    assert "author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)" in Path(
        pin.__file__
    ).read_text(encoding="utf-8")
    assert model_toleranced_dimensions(pin) == {
        ("PinProfile", "PinDia"): "*deviations(PIN_DIA_BAND)",
        ("PinProfile", "Depth"): "PIN_LENGTH_TOLERANCE_MM",
        ("CapProfile", "CapR"): "CAP_RADIUS_TOLERANCE_MM",
    }
    assert "FINAL SIZE" not in drawing.DIMENSION_CALLOUTS["PinDia"]
    assert "SEATED FLAT END" in drawing.DIMENSION_CALLOUTS["Depth"]
    assert "CapR" in drawing.RIGHT_KEEP
    # The reference overall replaces the crown-height prose (rule 7).
    assert "_overall_reference(adapter, right)" in source
    assert "set_reference_dimension(" in source
    assert "SetPrecision3(DRAWING_REFERENCE_PRECISION" in source
    assert "REF AXIAL HEIGHT" not in source
    assert round(drawing.OVERALL, 6) == 20.8


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(pin.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    assert '"Isometric View Note": ISOMETRIC_VIEW_NOTE' in source
    import _config

    spec = _config.parts("pinion-cam-pin")
    assert spec["number"] == "MHA-116"
    assert spec["material"] == spec["material_specification"]
    assert spec["material_specification"]
    assert spec["finish"]
    assert "fit_class" not in spec
    assert int(spec["quantity"]) == 2


def test_pin_diameter_callout_leaves_the_stock_to_the_title_block() -> None:
    """Codex P2 on #814: the PinDia callout said drill rod while the title
    block said AISI 1018 rod.  Machinist review of 7f7fc1717: naming the stock
    on the callout at all repeated the Material cell.  The callout now states
    only the fit, so it cannot disagree with the title block, and the h9
    bonded slip fit still assumes the drill rod the registry row names."""
    import _config

    row = _config.parts("pinion-cam-pin")
    callout = drawing.DIMENSION_CALLOUTS["PinDia"]
    assert callout is pinion_cam_pin_spec.PIN_DIA_CALLOUT
    assert callout == f"SLIP FIT IN {pinion_cam_pin_spec.SEAT_NUMBER} FOLLOWER SEAT"
    assert "DRILL ROD" not in callout.upper()
    assert row["material_specification"].upper() not in callout.upper()
    assert "drill rod" in row["material_specification"].lower()
    assert "drill rod" in row["process"]


def test_finish_states_the_condition_not_the_method() -> None:
    """Machinist review of 7f7fc1717: "crown turned" prescribed a method the
    crown's radius and roughness already define."""
    import _config

    finish = _config.parts("pinion-cam-pin")["finish"]
    assert "turned" not in finish.lower()
    assert finish == "as-received drill rod; protect with ISO VG 32 machine-oil film"


def test_the_part_owns_the_printed_precision() -> None:
    """Codex P2 on #814: the sheet set PinDia's places itself.  The part now
    authors every marked dimension's places and the sheet only asserts them."""
    from _drawing_contract import (
        PRECISION_MIGRATED_DRAWINGS,
        drawing_specification_violations,
    )

    precision = pinion_cam_pin_spec.DRAWING_PRECISION
    assert {
        feature: set(names) for feature, names in precision.items()
    } == pinion_cam_pin_spec.DRAWING_DIMENSIONS
    assert pinion_cam_pin_spec.DRAWING_PRECISION_BY_NAME == {
        "PinDia": 2,
        "Depth": 2,
        "CapR": 2,
    }
    build_source = Path(pin.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in build_source
    draw_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert (
        "assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)"
        in draw_source
    )
    assert "draw_pinion_cam_pin.py" in PRECISION_MIGRATED_DRAWINGS
    assert not drawing_specification_violations(draw_source, filename=drawing.__file__)
