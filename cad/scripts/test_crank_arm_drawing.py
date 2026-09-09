"""Offline contracts for the crank-arm drawing.

The print is the fleet's reference for cad/docs/drawing-simplicity-policy.md:
a pinned hand-crank lever carries no datums, frames, roughness symbols or
basic dimensions; its notes retain only part-specific process facts.
"""

from __future__ import annotations

from pathlib import Path

import crank_arm_spec
import draw_crank_arm as drawing
import build_crank_arm as arm
from _drawing_registry import DRAWINGS_BY_NAME
from _holes import NUMBER_DRILL_MM


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-arm.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crank-arm.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crank-arm_drawing.png")
    assert DRAWINGS_BY_NAME["crank_arm"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set are BOTH
    # the shared spec's map.  A rename in one script that isn't mirrored in the
    # other fails here, offline.
    assert arm.DRAWING_DIMENSIONS is crank_arm_spec.DRAWING_DIMENSIONS
    marked = set().union(*crank_arm_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert (drawing.ARM_END_X, drawing.HALF_WIDTH) == (
        crank_arm_spec.ARM_END_X,
        crank_arm_spec.HALF_WIDTH,
    )


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = _source()
    assert "scale=(1, 1)" in source  # the isometric override
    assert crank_arm_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"


def test_notes_are_specific_and_never_repeat_the_title_block() -> None:
    notes = crank_arm_spec.DRAWING_NOTES
    assert "15/64 DRILL THRU" in notes
    assert "HANDLE PIVOT CENTRED" not in notes
    assert "FINISHED SIZE FOR THIS PART" in notes
    assert "MHA-026" not in notes and "MHA-024" not in notes
    assert "OUTSIDE THIS PART DRAWING" not in notes
    assert "MATCH-REAM" not in notes
    assert "NOT INDIVIDUAL PART ACCEPTANCE" not in notes
    assert "NO. 2" not in notes
    assert "DATUM AXIS" not in notes
    # General tolerances live in the title block ONLY -- a second general
    # tolerance in the notes would conflict with it.
    assert "LINEAR +/-" not in notes
    assert "HOLE CENTRES" not in notes
    # Pedro 2026-07-10: drawings spec the closest US-customary fastener, not
    # the period British Association series.
    assert "BA" not in notes
    assert "X.XX" not in notes
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_hole_callouts_state_size_and_process() -> None:
    callouts = drawing.DIMENSION_CALLOUTS
    assert callouts["ShaftBoreDia"].startswith("REAM THRU")
    assert "3/8 IN" in callouts["ShaftBoreDia"]
    assert callouts["DimpleDia"] == "FLAT-BOTTOM 0.50 DEEP"  # .XX -> block tol
    assert crank_arm_spec.PIN_HOLE_DIA == NUMBER_DRILL_MM["#14"]
    source = _source()
    assert source.count("add_native_hole_callout(") == 2
    assert 'label="crank-arm cross-hole"' in source
    assert 'label="handle pivot hole"' in source
    # Harvey #13: the callout says DRILL; the drill number rides as its prefix.
    assert 'process="#14 DRILL"' in source
    assert 'process="15/64 DRILL"' in source


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    # drawing-simplicity-policy.md rule 3-5: a pinned hand-crank lever is not
    # on the GD&T allowlist and nothing runs on its bore.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(crank_arm_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(crank_arm_spec, "GEOMETRIC_CONTROLS")
    assert crank_arm_spec.SURFACE_FINISHES == ()
    assert "surface_finishes=SURFACE_FINISHES" in Path(arm.__file__).read_text(
        encoding="utf-8"
    )


def test_only_the_reamed_bore_prints_three_decimals() -> None:
    source = _source()
    assert '{"ShaftBoreDia": 3}' in source
    assert crank_arm_spec.SHAFT_BORE_BAND == (0.05, 0.00)
    build_source = Path(arm.__file__).read_text(encoding="utf-8")
    assert "set_dimension_bilateral_tolerance(" in build_source


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert (
        "for view in (front, top, right):\n        set_hidden_lines_visible" in source
    )
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_dimple_is_shown_where_it_is_visible() -> None:
    # The dimple and keeper-ring anchor are cut on HandleSeat at local z=8,
    # so the principal *Front* view exposes them directly. Third-angle
    # projection keeps the matching *Top* and *Right* views unrotated.
    source = _source()
    assert 'place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER' in source
    assert 'place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER' in source
    assert "top.Angle" not in source
    assert drawing._sheet_x(10.0) > drawing._sheet_x(0.0)


def test_overall_length_is_a_conspicuous_reference() -> None:
    source = _source()
    assert 'label="overall length reference"' in source
    assert (
        'set_arc_endpoints_to_max(adapter, overall, label="overall length reference")'
        in source
    )
    assert '_early_bound(overall, "IDisplayDimension").GetAnnotation()' in source
    assert crank_arm_spec.ARM_END_X + crank_arm_spec.HALF_WIDTH == 93.0


def test_one_origin_per_view_and_the_cross_hole_station() -> None:
    source = _source()
    assert 'label="shaft-to-handle-pivot location"' in source
    assert "pin_station = add_edge_dimension(" in source
    assert 'label="cross-hole station from broad face"' in source
    assert "find_edge_near(" in source
    assert crank_arm_spec.ARM_THICKNESS / 2.0 == 4.0
    assert crank_arm_spec.DIMPLE_X == 30.0
    assert '"DimpleX":' in source


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
    assert (
        screw.SHANK_DIA < insertion <= arm.ANCHOR_HOLE_SPEC.overrides_mm["ThreadDepth"]
    )
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
    assert (
        screw.HEAD_DIA / 2.0 - (drive.ANCHOR_SCREW_XY[1] - tail_end_y)
        >= eye.WIRE_DIA / 2.0
    )
    assert drive.ANCHOR_SCREW_XY == pytest.approx(
        (drive.X_CRANK - 4.5, drive.Y_CRANK - 20.0)
    )
