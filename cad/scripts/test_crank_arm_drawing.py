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
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm, drill_process


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
    assert "HANDLE PIVOT" not in notes
    assert "HANDLE PIVOT CENTRED" not in notes
    # The three coaxial features share the drawn arm centreline; the note
    # backs it in words without restating the width it is centred across.
    assert "ON THE ARM CENTRELINE." in notes
    assert "DIMPLE" in notes and "PIVOT HOLE" in notes
    assert not any(character.isdigit() for character in notes)
    # drawing-simplicity-policy rule 6: at most four short lines, and never a
    # dimension or a tolerance among them.
    assert len(notes.splitlines()) <= 4
    assert "+/-" not in notes and "DEEP" not in notes
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
    assert callouts["DimpleDia"] == "FIDUCIAL FLAT-BOTTOM 0.5 DEEP"
    assert blind_cut_dia_mm(crank_arm_spec.PIN_HOLE_SPEC) == 4.623
    assert blind_cut_dia_mm(crank_arm_spec.HANDLE_PIVOT_HOLE_SPEC) == 5.953
    assert drill_process(crank_arm_spec.PIN_HOLE_SPEC) == "#14 DRILL"
    assert drill_process(crank_arm_spec.HANDLE_PIVOT_HOLE_SPEC) == "15/64 DRILL"
    source = _source()
    assert source.count("add_native_hole_callout(") == 3
    assert 'label="crank-arm cross-hole"' in source
    assert 'label="handle pivot hole"' in source
    assert 'label="anchor tap"' in source
    assert source.count("process=drill_process(") == 3


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


def test_the_part_owns_every_printed_decimal_place() -> None:
    """Policy rule 2: places are the tolerance, so the .SLDPRT carries them.

    The bore's three places are the ONE exception: 9.525 is the exact 3/8 in
    conversion its callout cites.  Every other feature on this arm is
    noncritical, so it prints one place and takes the title block's .X row
    rather than the tighter .XX default (cad/docs/tolerance-policy.md).
    """
    by_name = crank_arm_spec.DRAWING_PRECISION_BY_NAME
    assert {name for name, places in by_name.items() if places != 1} == {"ShaftBoreDia"}
    assert by_name["ShaftBoreDia"] == 3
    assert crank_arm_spec.DRAWING_REFERENCE_PRECISION == {"overall length reference": 1}
    build_source = Path(arm.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in build_source
    source = _source()
    # The sheet reads the places back and never rewrites them.
    assert "set_dimension_precision" not in source
    assert "_set_primary_precision" not in source
    assert "assert_imported_precision(" in source
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS
    # No per-part band survives on this part: a pinned lever has no running fit
    # and nothing here traces to a named fit class (tolerance-policy rule 11).
    assert not hasattr(crank_arm_spec, "SHAFT_BORE_BAND")
    assert model_toleranced_dimensions(arm) == {}


def test_every_location_is_a_model_dimension_from_a_feature() -> None:
    """Rule 7 (one feature origin per view) meets rule 2 (the model owns it).

    The pivot and anchor stations read from the shaft-bore axis, the anchor's
    offset from the top long edge, the stock width and the cross-hole's
    station from the broad face are all values no feature dimension carries,
    so the part's reference sketches own them and the print imports them --
    nothing on the sheet is built from view picks except the parenthesised
    overall.
    """
    stations = crank_arm_spec.DRAWING_DIMENSIONS["StationReference"]
    assert stations == {"PivotStation", "AnchorStation", "AnchorOffset", "Width"}
    assert crank_arm_spec.DRAWING_DIMENSIONS["PinStationReference"] == {"PinStation"}
    assert stations <= set(drawing.FRONT_KEEP)
    assert set(drawing.TOP_KEEP) == {"PinStation"}
    # The baseline chain below the view stacks smallest span nearest the arm.
    chain = [
        drawing.FRONT_KEEP[name][1]
        for name in ("AnchorStation", "DimpleX", "PivotStation", "ArmEndX")
    ]
    assert chain == sorted(chain, reverse=True)
    assert crank_arm_spec.HALF_WIDTH - crank_arm_spec.ANCHOR_SCREW_Y == 3.5
    source = _source()
    assert source.count("add_edge_dimension(") == 1
    assert 'label="overall length reference"' in source


def test_hidden_lines_are_kept_only_where_they_show_something() -> None:
    source = _source()
    # Front (blind floors) and top (cross-drill meeting the bore) keep them;
    # the 16 x 8 side view would only repeat already-called-out holes.
    assert "for view in (front, top):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, right)" in source
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


def test_coaxial_features_share_a_drawn_centreline() -> None:
    # Machinist blocker: the dimple and pivot hole had no cross-width location.
    # They sit on the arm's mid-width axis, so the print draws that axis
    # between the two long edges and the note backs it.
    source = _source()
    assert "_add_arm_centerline(adapter, front)" in source
    assert "InsertCenterLine2()" in source
    assert crank_arm_spec.ARM_THICKNESS / 2.0 == 4.0
    assert crank_arm_spec.DIMPLE_X == 30.0


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
        screw.SHANK_DIA
        < insertion
        <= crank_arm_spec.ANCHOR_HOLE_SPEC.overrides_mm["ThreadDepth"]
    )
    assert crank_arm_spec.ANCHOR_HOLE_SPEC.kind == "tapped_bottoming"
    assert crank_arm_spec.ANCHOR_HOLE_SPEC.size == screw.THREAD
    assert crank_arm_spec.ANCHOR_HOLE_SPEC.depth_mm - insertion == pytest.approx(1.17)
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
