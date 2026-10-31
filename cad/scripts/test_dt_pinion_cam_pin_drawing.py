"""Offline contracts for the pinion cam-follower-pin drawing."""

from __future__ import annotations

from pathlib import Path

import pytest

import dt_pinion_cam_pin_spec
import draw_dt_pinion_cam_pin as drawing
import build_dt_pinion_cam_pin as pin
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-pinion-cam-pin.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-pinion-cam-pin.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-pinion-cam-pin_drawing.png")
    assert DRAWINGS_BY_NAME["dt_pinion_cam_pin"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert pin.DRAWING_DIMENSIONS is dt_pinion_cam_pin_spec.DRAWING_DIMENSIONS
    marked = set().union(*dt_pinion_cam_pin_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert drawing.PIN_DIA == dt_pinion_cam_pin_spec.PIN_DIA
    assert drawing.PIN_DIA == pytest.approx(0.1563 * 25.4)  # 5/32 drill rod
    assert drawing.PIN_LEN == dt_pinion_cam_pin_spec.PIN_LEN


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
    assert dt_pinion_cam_pin_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 4:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source
    assert "End View Note" not in source


def test_side_view_lies_as_turned_with_the_end_view_in_projection() -> None:
    """Machinist review of 7f7fc1717: the end view sat beside a vertical
    elevation, out of projection, carrying the only diameter.  The side view
    now lies horizontal (drawing-guidelines.md rule 11 (turned parts read like the lathe), turned parts), the end view projects to its
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
    # below, the crown radius leader at the lower left of the crown.
    assert top < drawing.RIGHT_KEEP["Depth"][1] < drawing.OVERALL_TEXT_XY[1] < 0.255
    assert 0.080 < drawing.RIGHT_KEEP["PinDia"][1] < bottom
    assert drawing.RIGHT_KEEP["PinDia"][0] > drawing.RIGHT_CENTER[0]
    x, y = drawing.RIGHT_KEEP["CapR"]
    assert end_view_right < x < crown_apex_x
    assert 0.080 < y < drawing.RIGHT_CENTER[1]


def test_sheet_has_no_general_notes() -> None:
    """Machinist review r1 of #1009: the sharp-crown-root note argued with the
    title block and named no reason; the crown root takes the title block's
    edge break like every other edge, and the bond is the fit-up step."""
    assert not hasattr(dt_pinion_cam_pin_spec, "DRAWING_NOTES")
    for module in (drawing, pin):
        assert "Manufacturing Notes" not in Path(module.__file__).read_text(
            encoding="utf-8"
        )


def test_end_view_keeps_the_templates_one_center_mark(monkeypatch) -> None:
    """Layout audit r1-r2 of #1009: the template's centre mark and an
    unconditional auto_center_marks printed two identical marks on the end
    view.  The sheet adds one only when the template did not."""
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "if _center_mark_count(front) == 0 and not auto_center_marks(" in source
    assert "if found != 1:" in source
    assert drawing._CENTER_MARK_ANNOTATION == 13

    class _View:
        def __init__(self, marks):
            self.marks = marks

        def GetAnnotationsByType(self, kind):  # noqa: N802 - the COM member name
            assert kind == 13
            return self.marks

    monkeypatch.setattr(drawing, "_early_bound", lambda view, _iface: view)
    assert drawing._center_mark_count(_View(None)) == 0
    assert drawing._center_mark_count(_View(("mark",))) == 1


def test_bonded_slip_fit_replaces_the_press() -> None:
    """U27 (Main, 2026-09-23): stock drill rod slipped into the strap's H7 seat
    and bonded with LOCTITE 638 (the U6 drum-to-arbor precedent).  #290: 5/32
    drill rod (+/-.0005) in the .1570 seat."""
    import dt_pinion_bracket_spec

    assert dt_pinion_cam_pin_spec.PIN_DIA == pytest.approx(0.1563 * 25.4)
    assert dt_pinion_cam_pin_spec.PIN_DIA_BAND == (0.0127, -0.0127)
    assert dt_pinion_cam_pin_spec.SEAT_BAND == dt_pinion_bracket_spec.PIN_SEAT_DIA_BAND
    seat_min = dt_pinion_bracket_spec.PIN_BORE + dt_pinion_bracket_spec.PIN_SEAT_DIA_BAND[1]
    seat_max = dt_pinion_bracket_spec.PIN_BORE + dt_pinion_bracket_spec.PIN_SEAT_DIA_BAND[0]
    pin_min = dt_pinion_cam_pin_spec.PIN_DIA + dt_pinion_cam_pin_spec.PIN_DIA_BAND[1]
    pin_max = dt_pinion_cam_pin_spec.PIN_DIA + dt_pinion_cam_pin_spec.PIN_DIA_BAND[0]
    assert round(seat_min - pin_max, 6) == 0.00508
    assert round(seat_max - pin_min, 6) == 0.04318
    assert seat_max - pin_min <= dt_pinion_cam_pin_spec.RETAINING_COMPOUND_MAX_GAP_MM
    # drawing-guidelines.md rule 7 (notes: few, flagged, never a method) (Main's MHA-DT-25 eye pass): the bond is the fit-up step, not a note.
    assert dt_pinion_cam_pin_spec.ASSEMBLY_STEP == (
        "BOND 2X MHA-DT-25, ONE INTO EACH MHA-DT-14 FOLLOWER SEAT WITH LOCTITE 638."
    )
    assert "MHA-DT-14" in drawing.DIMENSION_CALLOUTS["PinDia"]
    assert "SLIP FIT" in drawing.DIMENSION_CALLOUTS["PinDia"]
    import draw_dt_pinion_bracket

    assert "MHA-DT-25" in draw_dt_pinion_bracket.DIMENSION_CALLOUTS["PinSeatDia"]


def test_the_bond_step_counts_one_pin_per_strap() -> None:
    """final877 eye pass (A03 sheet 8, step 14): the step named no count, so a
    fitter could bond one follower pin and stop.  It prints the BOM quantity,
    and that quantity is one per strap."""
    import _config

    pins = _config.parts("dt-pinion-cam-pin")["quantity"]
    straps = _config.parts("dt-pinion-bracket")
    assert straps["number"] == dt_pinion_cam_pin_spec.SEAT_NUMBER
    assert pins == straps["quantity"] == 2
    step = dt_pinion_cam_pin_spec.ASSEMBLY_STEP
    assert step.startswith(f"BOND {pins}X MHA-DT-25, ONE INTO EACH MHA-DT-14 ")


def test_no_gdt_the_shank_carries_the_finish_and_only_the_fit_is_banded() -> None:
    """drawing-simplicity-policy.md `GD&T allowlist (rule 5)`: a pin is not on
    the GD&T allowlist.  drawing-guidelines.md rule 6 (roughness symbols only
    where a surface runs, slides or locates): the cam rides the Ø4 shank, a
    cam-follower contact (Codex P2 on #1687); the crown touches nothing.
    Machinist review r1 of #1009: the length and crown radius bands named no
    mate; they take the title block's .XX."""
    from _gtol_cylinder import CylinderFace

    source = Path(drawing.__file__).read_text(encoding="utf-8")
    build_source = Path(pin.__file__).read_text(encoding="utf-8")
    assert not hasattr(dt_pinion_cam_pin_spec, "GEOMETRIC_TOLERANCES_MM")
    assert "add_datum_feature(" not in source
    assert "add_feature_control_frame(" not in source
    (control,) = dt_pinion_cam_pin_spec.SURFACE_FINISHES
    assert control.key == "shank"
    assert control.roughness_um == 1.6
    assert control.face == CylinderFace(diameter_mm=dt_pinion_cam_pin_spec.PIN_DIA)
    assert source.count("add_surface_finish(") == 1
    assert 'surface_finish_by_key(SURFACE_FINISHES, "shank")' in source
    assert "author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)" in (
        build_source
    )
    assert "add_view_centerline(" in source
    assert model_toleranced_dimensions(pin) == {
        ("PinProfile", "PinDia"): "PIN_DIA_BAND[0]",
    }
    assert "FINAL SIZE" not in drawing.DIMENSION_CALLOUTS["PinDia"]
    assert drawing.DIMENSION_CALLOUTS["Depth"] is dt_pinion_cam_pin_spec.DEPTH_CALLOUT
    assert (
        drawing.DIMENSION_CALLOUTS["CapR"] is dt_pinion_cam_pin_spec.CAP_RADIUS_CALLOUT
    )
    assert "CapR" in drawing.RIGHT_KEEP
    # The reference overall replaces the crown-height prose (drawing-guidelines.md rule 10 (dimension from a real feature)).
    assert "_overall_reference(adapter, right)" in source
    assert "set_reference_dimension(" in source
    assert "SetPrecision3(DRAWING_REFERENCE_PRECISION" in source
    assert "REF AXIAL HEIGHT" not in source
    assert drawing.OVERALL == pytest.approx(20.801, abs=5e-4)


def test_the_cam_rides_the_shank_short_of_the_crown() -> None:
    """The representative finish station lies on the exposed shank, not the
    crown.  Down/up axis projections are reachability landmarks, not the
    operating contact extent; an independent all-angle bound excludes crown."""
    import build_dt_drive_train_assembly as asm

    stations = []
    for centre, normal, ecc in (
        (asm._FPIN_C, asm._SPR_N, -asm.CAM_ECC),
        (asm._FPIN_C_ENG, asm._N_ENG, asm.CAM_ECC),
    ):
        axis = (asm.LIFT_X, asm.LIFT_Y + ecc)
        foot = -((axis[0] - centre[0]) * normal[0] + (axis[1] - centre[1]) * normal[1])
        stations.append(foot - asm._FPIN_S0)
    contact = drawing.CAM_CONTACT_FROM_SEATED_END_MM
    assert min(stations) - 0.5 < contact < max(stations) + 0.5
    assert dt_pinion_cam_pin_spec.SEAT_LEN < min(stations)
    assert max(stations) < dt_pinion_cam_pin_spec.PIN_LEN - 3.0
    # Independently exclude the crown over every nominal cam/strap angle:
    # projection on a unit pin axis cannot exceed the pivot-to-cam distance.
    # The seated root is _FPIN_S0 outboard of the pivot/strap centreline.
    from math import hypot

    furthest_contact = (
        hypot(asm.LIFT_X - asm.PIVOT_X, asm.LIFT_Y - asm.PIVOT_Y)
        + asm.CAM_ECC
        - asm._FPIN_S0
    )
    assert furthest_contact < dt_pinion_cam_pin_spec.PIN_LEN - 2.0


# The finish symbol's ink relative to its V root at 2.5 mm character height:
# the leader leaves the shelf's right end; the "Ra 1.6" text sits above the
# shelf, right of it (r5 layout audit: text 4.2-6.8 mm above the root), and
# the CAM CONTACT target prints a row above the bar, about 11.5 mm up.
_SHELF_LEFT_DX = -0.0030
_LEADER_ELBOW_DX = 0.00635
_SYMBOL_TOP_DY = 0.0115


def test_shank_finish_sits_clear_above_the_shank() -> None:
    x, y = drawing.SHANK_FINISH_SYMBOL_XY
    model_x, model_y, model_z = drawing._shank_point()
    target = (
        drawing.side_view_x(model_z * 1000.0),
        drawing.RIGHT_CENTER[1] + model_y * drawing.SHEET_SCALE[0],
    )
    assert model_x == 0.0
    assert dt_pinion_cam_pin_spec.SEAT_LEN < model_z * 1000.0 < drawing.PIN_LEN
    assert target[1] == pytest.approx(drawing.RIGHT_CENTER[1] + drawing.HALF_DIA)
    # The leader falls from the shelf end to the shank's upper edge, so it
    # passes below the text that sits above the shelf.
    assert y > target[1] + 0.004
    assert target[0] > x + _LEADER_ELBOW_DX + 0.005
    # Clear of the crown-root extension line and under the Depth block.
    assert x + _SHELF_LEFT_DX > drawing.side_view_x(drawing.PIN_LEN) + 0.005
    # r5 layout audit: the Depth dimension line runs 8 mm under its keep point.
    depth_line = drawing.RIGHT_KEEP["Depth"][1] - 0.008
    assert depth_line - (y + _SYMBOL_TOP_DY) > _SYMBOL_TOP_DY
    assert (
        dt_pinion_cam_pin_spec.SURFACE_FINISHES[0].production_method
        == dt_pinion_cam_pin_spec.SHANK_FINISH_TARGET
    )


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(pin.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    assert '"Isometric View Note": ISOMETRIC_VIEW_NOTE' in source
    import _config

    spec = _config.parts("dt-pinion-cam-pin")
    assert spec["number"] == "MHA-DT-25"
    assert "5/32" in spec["material_specification"]
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

    row = _config.parts("dt-pinion-cam-pin")
    callout = drawing.DIMENSION_CALLOUTS["PinDia"]
    assert callout is dt_pinion_cam_pin_spec.PIN_DIA_CALLOUT
    assert callout == f"SLIP FIT IN {dt_pinion_cam_pin_spec.SEAT_NUMBER} FOLLOWER SEAT"
    assert "DRILL ROD" not in callout.upper()
    assert row["material_specification"].upper() not in callout.upper()
    assert "drill rod" in row["material_specification"].lower()
    assert "drill rod" in row["process"]


def test_finish_states_the_condition_not_the_method() -> None:
    """Machinist review of 7f7fc1717: "crown turned" prescribed a method the
    crown's radius and roughness already define."""
    import _config

    finish = _config.parts("dt-pinion-cam-pin")["finish"]
    assert "turned" not in finish.lower()
    assert finish == "as-received drill rod; protect with ISO VG 32 machine-oil film"


def test_the_part_owns_the_printed_precision() -> None:
    """Codex P2 on #814: the sheet set PinDia's places itself.  The part now
    authors every marked dimension's places and the sheet only asserts them."""
    from _drawing_contract import (
        PRECISION_MIGRATED_DRAWINGS,
        drawing_specification_violations,
    )

    precision = dt_pinion_cam_pin_spec.DRAWING_PRECISION
    assert {
        feature: set(names) for feature, names in precision.items()
    } == dt_pinion_cam_pin_spec.DRAWING_DIMENSIONS
    assert dt_pinion_cam_pin_spec.DRAWING_PRECISION_BY_NAME == {
        "PinDia": 4,
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
    assert "draw_dt_pinion_cam_pin.py" in PRECISION_MIGRATED_DRAWINGS
    assert not drawing_specification_violations(draw_source, filename=drawing.__file__)
