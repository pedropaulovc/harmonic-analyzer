"""Offline contracts for the pinion cam-follower-pin drawing."""

from __future__ import annotations

from pathlib import Path

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
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
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
    assert '"*Top", *RIGHT_CENTER, scale=(8, 1)' in source
    assert '"*Isometric", *ISO_CENTER, scale=(4, 1)' in source
    # The crown radius belongs to a sketch on the Top plane.  The equivalent
    # axisymmetric side elevation must face that plane to import CapR natively.
    assert '"*Right", *RIGHT_CENTER' not in source
    assert pinion_cam_pin_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 4:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source
    assert "End View Note" not in source


def test_elevation_fits_the_sheet_and_clears_the_title_block() -> None:
    half = drawing.OVERALL / 2.0 * drawing._S
    top = drawing.RIGHT_CENTER[1] + half
    bottom = drawing.RIGHT_CENTER[1] - half
    assert top < 0.262  # inner border ~0.267
    assert bottom > 0.068  # title block top ~0.065
    # The two lengths sit left of the elevation, the crown leaders right.
    left_edge = drawing.RIGHT_CENTER[0] - drawing.PIN_DIA / 2.0 * drawing._S
    right_edge = drawing.RIGHT_CENTER[0] + drawing.PIN_DIA / 2.0 * drawing._S
    assert drawing.OVERALL_TEXT_XY[0] < drawing.RIGHT_KEEP["Depth"][0] < left_edge
    assert drawing.RIGHT_KEEP["CapR"][0] > right_edge


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
    notes = pinion_cam_pin_spec.DRAWING_NOTES
    assert "BOND INTO MHA-056 FOLLOWER SEAT WITH LOCTITE 638" in notes
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
        ("Pin", "Depth"): "PIN_LENGTH_TOLERANCE_MM",
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


def test_pin_diameter_callout_names_the_title_block_stock() -> None:
    """Codex P2 on #814: the PinDia callout said drill rod while the title
    block said AISI 1018 rod.  Both now read the registry row, and the h9
    bonded slip fit assumes the drill rod it names."""
    import _config

    row = _config.parts("pinion-cam-pin")
    callout = drawing.DIMENSION_CALLOUTS["PinDia"]
    assert callout is pinion_cam_pin_spec.PIN_DIA_CALLOUT
    stock, fit = callout.split(";\n")
    assert stock == row["material_specification"].upper()
    assert "drill rod" in row["material_specification"].lower()
    assert fit == f"SLIP FIT IN {pinion_cam_pin_spec.SEAT_NUMBER} FOLLOWER SEAT"
    assert "drill rod" in row["process"]


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
