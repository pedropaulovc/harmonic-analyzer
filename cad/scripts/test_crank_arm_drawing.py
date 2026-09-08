"""Offline contracts for the crank-arm drawing."""

from __future__ import annotations

import math
from pathlib import Path

import crank_arm_spec
import draw_crank_arm as drawing
import build_crank_arm as arm
from _drawing_registry import DRAWINGS_BY_NAME
from _holes import NUMBER_DRILL_MM


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-arm.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crank-arm.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crank-arm_drawing.png")
    assert DRAWINGS_BY_NAME["crank_arm"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set are BOTH
    # the shared spec's map. build re-exports the SAME object (so it marks exactly the
    # spec), and the drawing keeps exactly its union across the per-view keep-maps --
    # a rename in one script that isn't mirrored in the other fails here, offline.
    assert arm.DRAWING_DIMENSIONS is crank_arm_spec.DRAWING_DIMENSIONS
    marked = set().union(*crank_arm_spec.DRAWING_DIMENSIONS.values())
    kept = (
        set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    )
    assert kept == marked
    # A callout can only annotate a dimension the print actually shows.
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    # The drawing's view math reads the spec's nominal spans, not a divergent copy.
    assert (drawing.ARM_END_X, drawing.HALF_WIDTH) == (
        crank_arm_spec.ARM_END_X,
        crank_arm_spec.HALF_WIDTH,
    )


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    assert crank_arm_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"


def test_linked_notes_define_a_complete_individual_part() -> None:
    notes = crank_arm_spec.DRAWING_NOTES
    assert "3/8 IN" in drawing.DIMENSION_CALLOUTS["ShaftBoreDia"]
    assert "15/64 DRILL THRU" in notes
    assert "HANDLE PIVOT CENTRED" not in notes
    assert "FINISHED SIZE FOR THIS PART" in notes
    assert "MHA-026" not in notes and "MHA-024" not in notes
    assert "OUTSIDE THIS PART DRAWING" not in notes
    assert "MATCH-REAM" not in notes
    assert "NOT INDIVIDUAL PART ACCEPTANCE" not in notes
    assert "NO. 2" not in notes
    # General tolerances live in the title block ONLY -- a second general
    # tolerance in the notes would conflict with it.
    assert "LINEAR +/-" not in notes
    assert "HOLE CENTRES" not in notes
    # Pedro 2026-07-10: drawings spec the closest US-customary fastener, not
    # the period British Association series.
    assert "BA" not in notes
    assert "X.XX" not in notes


def test_hole_states_are_annotated() -> None:
    callouts = drawing.DIMENSION_CALLOUTS
    assert callouts["ShaftBoreDia"].startswith("THRU")
    assert callouts["DimpleDia"] == "0.5 DEEP"
    assert crank_arm_spec.PIN_HOLE_DIA == NUMBER_DRILL_MM["#14"]


def test_shaft_axis_datum_pick_is_radial_with_its_symbol() -> None:
    centre = (drawing._sheet_x(0.0), drawing.FRONT_CENTER[1])
    rim_vector = (
        drawing.DATUM_B_RIM[0] - centre[0],
        drawing.DATUM_B_RIM[1] - centre[1],
    )
    leader_vector = (
        drawing.DATUM_B_SYMBOL[0] - drawing.DATUM_B_RIM[0],
        drawing.DATUM_B_SYMBOL[1] - drawing.DATUM_B_RIM[1],
    )
    assert math.isclose(
        math.hypot(*rim_vector), drawing.DATUM_B_RADIUS, abs_tol=1e-12
    )
    assert math.isclose(
        rim_vector[0] * leader_vector[1] - rim_vector[1] * leader_vector[0],
        0.0,
        abs_tol=1e-12,
    )
    assert rim_vector[0] * leader_vector[0] + rim_vector[1] * leader_vector[1] > 0




def test_dimple_has_both_nominal_location_coordinates() -> None:
    assert crank_arm_spec.DIMPLE_X == 30.0
    assert crank_arm_spec.HALF_WIDTH == 8.0


def test_wizard_holes_are_not_fake_marked_dimensions() -> None:
    assert "BoreProfile" not in arm.DRAWING_DIMENSIONS
    assert "PinHoleProfile" not in arm.DRAWING_DIMENSIONS


def test_part_stamps_make_critical_drawing_properties() -> None:
    import _config

    spec = _config.parts("crank-arm")
    expected = "SAE 1018 CF bar, ASTM A108-24"
    assert spec["material"] == expected
    assert spec["material_specification"] == expected
    assert spec["finish"]
    assert int(spec["quantity"]) == 1


def test_stock_anchor_clamps_eye_without_bottoming_or_drill_breakthrough() -> None:
    import build_crank_pin_eye as eye
    import build_drive_train_assembly as drive
    import build_fillister_screw as screw
    import pytest

    # Derive the insertion from the placed under-head plane, not a duplicated
    # engagement constant: moving the head off the wire must fail this contract.
    wire_front = drive.EYE_Z - eye.WIRE_DIA / 2.0
    wire_back = drive.EYE_Z + eye.WIRE_DIA / 2.0
    assert drive.ANCHOR_HEAD_Z == pytest.approx(wire_front)
    assert drive.CRANK_ARM_Z0 - wire_back == pytest.approx(0.02)
    insertion = drive.ANCHOR_HEAD_Z + screw.SHANK_LEN - drive.CRANK_ARM_Z0
    assert insertion == pytest.approx(5.33)
    assert screw.SHANK_DIA < insertion <= arm.ANCHOR_HOLE_SPEC.overrides_mm["ThreadDepth"]
    assert arm.ANCHOR_HOLE_SPEC.kind == "tapped_bottoming"
    assert arm.ANCHOR_HOLE_SPEC.size == screw.THREAD
    assert arm.ANCHOR_HOLE_SPEC.depth_mm - insertion == pytest.approx(1.17)
    assert drive.ANCHOR_BACK_WALL == pytest.approx(0.8207, abs=0.0001)
    assert drive.ANCHOR_BACK_WALL >= 0.5

    # The eye tail ends just outside the shank, still under the head. Its
    # loop and the photographed screw station remain on the operator face.
    tail_end_y = drive.EYE_CENTER_Y + eye.LOOP_R + eye.TAIL_LEN
    shank_gap = drive.ANCHOR_SCREW_XY[1] - tail_end_y - screw.SHANK_DIA / 2.0
    assert shank_gap == pytest.approx(0.02)
    assert screw.HEAD_DIA / 2.0 - (drive.ANCHOR_SCREW_XY[1] - tail_end_y) >= eye.WIRE_DIA / 2.0
    assert drive.ANCHOR_SCREW_XY == pytest.approx(
        (drive.X_CRANK - 4.5, drive.Y_CRANK - 20.0)
    )
