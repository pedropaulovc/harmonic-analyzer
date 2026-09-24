"""Offline release contracts for MHA-139, the crank handle pivot screw (U33)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_crank_handle_pivot_screw as part
import crank_handle_pivot_screw_spec as spec
import crank_handle_spec as handle
import crank_hub_geometry as geometry
import draw_crank_handle_pivot_screw as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from _hole_spec import THREAD_MAJOR_MM
from _surface_finish import MACHINED_UM


def test_registry_paths_and_part_name() -> None:
    registered = DRAWINGS_BY_NAME["crank_handle_pivot_screw"]
    assert registered.script == Path(drawing.__file__).resolve()
    assert registered.layout is DrawingLayout.LANDSCAPE
    assert registered.source.as_posix().endswith("/sldprt/crank-handle-pivot-screw.SLDPRT")
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-handle-pivot-screw.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crank-handle-pivot-screw.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crank-handle-pivot-screw_drawing.png")
    assert part.PART_NAME == registered.artifact_stem


def test_part_registry_row_is_the_made_screw() -> None:
    row = _config.parts("crank-handle-pivot-screw")
    assert row["number"] == "MHA-139"
    assert row["material"] == row["material_specification"]
    assert "1018" in row["material_specification"]
    assert "12L14" in row["material_specification"]
    assert int(row["quantity"]) == 1
    assert row["fit_class"] == "shaft_in_bushing"
    assert row["process"] != "purchased"


def test_spec_is_the_single_source_of_marked_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.SIDE_KEEP) | set(drawing.END_KEEP) == marked
    assert not set(drawing.SIDE_KEEP) & set(drawing.END_KEEP)
    # The threaded section is defined by its callout, not a Ø4.826 dimension.
    assert "ThreadDia" not in marked
    # The slot width is only true-size in the head-end view.
    assert set(drawing.END_KEEP) == {"SlotWidth"}


def test_model_owns_places_and_bands() -> None:
    assert "draw_crank_handle_pivot_screw.py" in PRECISION_MIGRATED_DRAWINGS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    # The running fit, and the relief width that holds the U33b floor.
    running_fit = {"ShoulderDia", "ShoulderLength", "ReliefWidth"}
    for name, places in spec.DRAWING_PRECISION_BY_NAME.items():
        assert places == (2 if name in running_fit else 1), name
    assert spec.REFERENCE_DIMENSIONS == {"OverallLength"}
    # Every band comes from a named spec constant, never a typed number.
    assert model_toleranced_dimensions(part) == {
        ("ScrewProfile", "ShoulderDia"): "*deviations(SHOULDER_DIA_BAND)",
        ("ScrewProfile", "ShoulderLength"): "SHOULDER_LENGTH_TOL",
        ("ScrewProfile", "ThreadLength"): "*deviations(THREAD_LENGTH_BAND)",
    }
    assert spec.SHOULDER_DIA == 6.00
    assert spec.SHOULDER_DIA_BAND == (-0.03, -0.08)
    assert spec.SHOULDER_LENGTH == 58.50
    assert spec.SHOULDER_LENGTH_TOL == 0.25
    assert spec.THREAD_LENGTH == 9.0
    assert spec.THREAD_LENGTH_BAND == (0.0, -0.5)


def test_policy_sheet_carries_no_gdt_or_render_time_precision() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_feature_control_frame",
        "add_datum_feature",
        "set_basic_dimension",
        "set_dimension_precision",
        "SetPrecision3",
    ):
        assert helper not in source
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")


def test_geometry_matches_the_u33_ruling() -> None:
    assert spec.HEAD_DIA == 8.0
    assert spec.HEAD_LENGTH == 3.0
    assert spec.SLOT_WIDTH == 1.0
    assert spec.SLOT_DEPTH == 1.0
    assert spec.HEAD_LENGTH - spec.SLOT_DEPTH == pytest.approx(2.0)
    assert spec.THREAD_MODEL_DIA == THREAD_MAJOR_MM["#10-24"] == 4.826
    assert spec.SEAT_STATION == pytest.approx(61.5)
    assert spec.OVERALL_LENGTH == pytest.approx(70.5)
    assert spec.TIP_CHAMFER == 0.5
    # The tip chamfer stays within the 0.65 thread depth (17/24 H).
    assert spec.TIP_CHAMFER <= 0.61343 * 25.4 / 24.0
    assert spec.HEAD_DIA < spec.STOCK_DIA == pytest.approx(9.525)


def test_u33_running_fit_end_play_and_engagement() -> None:
    # Handle numbers come from its own spec, the arm thickness from the shared
    # crank interface geometry.
    assert handle.HANDLE_LENGTH == 58.0
    assert handle.HANDLE_LENGTH_BAND == (0.0, -0.25)
    assert handle.PIVOT_BORE_DIA + handle.PIVOT_BORE_BAND[1] == pytest.approx(6.10)
    assert handle.PIVOT_BORE_DIA + handle.PIVOT_BORE_BAND[0] == pytest.approx(6.15)
    assert geometry.ARM_THICKNESS == 8.0

    # Shoulder 58.25..58.75 against wood 57.75..58.00.
    assert spec.END_PLAY_MIN == pytest.approx(0.25)
    assert spec.END_PLAY_MAX == pytest.approx(1.00)
    # Bore 6.10..6.15 over shoulder 5.92..5.97, on diameter.
    assert (spec.SHOULDER_DIA_MIN, spec.SHOULDER_DIA_MAX) == pytest.approx((5.92, 5.97))
    assert spec.DIAMETRAL_CLEARANCE_MIN == pytest.approx(0.13)
    assert spec.DIAMETRAL_CLEARANCE_MAX == pytest.approx(0.23)
    # The threaded section is 8.5..9.0 and always spans the 7.94 stock arm.
    assert (spec.THREAD_LENGTH_MIN, spec.THREAD_LENGTH_MAX) == pytest.approx((8.5, 9.0))
    assert spec.THREAD_LENGTH_MIN >= spec.ARM_STOCK_THICKNESS
    # The head retains the handle.
    assert spec.HEAD_DIA > spec.HANDLE_BORE_MAX


def test_thread_relief_sits_below_the_minor_with_a_45_degree_lead() -> None:
    assert spec.RELIEF_DIA == 3.4
    assert spec.RELIEF_WIDTH == 1.5
    assert spec.RELIEF_LEAD == 0.5
    assert spec.RELIEF_END_STATION == pytest.approx(spec.SEAT_STATION + 1.5)
    # At or below the #10-24 external minor: the P/8-flat UN root (the McMaster
    # 91829A560 vendor model's Ø3.451) and the UNR-2A reference max (Ø3.503).
    assert spec.THREAD_MINOR_BASIC_ROOT == pytest.approx(3.4512, abs=1e-4)
    assert spec.THREAD_MINOR_UNR_2A_MAX == pytest.approx(3.5022, abs=1e-4)
    assert spec.RELIEF_DIA <= spec.THREAD_MINOR_BASIC_ROOT
    # The lead tops out at Ø4.4, inside the thread major, leaving a flat seat.
    assert spec.SEAT_FLAT_INNER_DIA == pytest.approx(4.4)
    assert spec.SEAT_FLAT_INNER_DIA < spec.THREAD_MODEL_DIA
    assert spec.SEAT_FLAT_ANNULUS_AREA == pytest.approx(math.pi / 4.0 * (36.0 - 4.4**2))
    assert 0.0 < spec.SEAT_FLAT_ANNULUS_AREA_MIN < spec.SEAT_FLAT_ANNULUS_AREA
    assert spec.CHAMFER_CALLOUT == "X 45 DEG"
    assert drawing.CHAMFER_CALLOUT is spec.CHAMFER_CALLOUT
    # The neck is ~80 percent of the #10-24 tensile stress area.
    assert spec.NECK_AREA == pytest.approx(math.pi / 4.0 * 3.4**2)
    assert spec.TENSILE_STRESS_AREA == pytest.approx(11.29, abs=0.01)
    assert spec.NECK_TO_STRESS_AREA == pytest.approx(0.804, abs=0.001)
    # The relief sizes are routine .X under the title block, not model bands.
    toleranced = {name for _, name in model_toleranced_dimensions(part)}
    assert not toleranced & {"ReliefDia", "ReliefWidth", "ReliefLead", "TipChamfer"}


def test_u33b_engagement_exception_is_governed_by_the_stock_arm() -> None:
    # U33b: the user accepted ~1.2 D steel-in-steel; the floor is 1.15 D.
    assert spec.ENGAGEMENT_EXCEPTION_FLOOR_D == 1.15
    source = Path(spec.__file__).read_text(encoding="utf-8")
    assert "U33b (2026-09-23): user accepted ~1.2D steel-in-steel for MHA-139" in source
    assert "exception to the 1.5D rule" in source
    assert spec.ENGAGEMENT_FLOOR == pytest.approx(1.15 * 4.826)
    # The chamfer's partial threads are excluded: full thread reaches 8.5 - 0.5
    # = 8.0 from the seat face at the shortest thread section.
    assert spec.FULL_THREAD_REACH_MIN == pytest.approx(8.0)
    # Nominal: min(9.0 - 0.5, arm 8.0) - 1.5 = 6.5 of full thread, 1.35 D.
    assert spec.FULL_THREAD_NOMINAL == pytest.approx(6.5)
    assert spec.FULL_THREAD_NOMINAL_DIAMETERS == pytest.approx(6.5 / 4.826)
    # Stock 5/16-in arm: min(8.0, 7.9375 - the 0.25 exit break) - (1.5 + the
    # .XX band 0.51) = 5.68, 1.18 D.  The arm governs.
    assert geometry.GENERAL_2PL_TOL_MM == pytest.approx(0.51)
    assert spec.TAP_EXIT_BREAK == pytest.approx(0.25)
    assert spec.ARM_STOCK_THICKNESS == pytest.approx(7.9375)
    assert spec.RELIEF_WIDTH_MAX == pytest.approx(2.01)
    assert spec.FULL_THREAD_WORST == pytest.approx(5.6775)
    assert spec.FULL_THREAD_WORST_DIAMETERS == pytest.approx(1.176, abs=1e-3)
    assert spec.ENGAGEMENT_GOVERNED_BY == "arm"
    # Arm at its printed maximum 8.8: min(8.0, 8.8 - 0.25) - 2.01 = 5.99,
    # 1.24 D; the screw governs there.
    assert spec.ARM_PRINTED_THICKNESS_MAX == pytest.approx(8.8)
    assert spec.FULL_THREAD_WORST_PRINTED_ARM == pytest.approx(5.99)
    assert spec.FULL_THREAD_WORST_PRINTED_ARM_DIAMETERS == pytest.approx(1.241, abs=1e-3)
    for engaged in (spec.FULL_THREAD_WORST, spec.FULL_THREAD_WORST_PRINTED_ARM):
        assert engaged >= spec.ENGAGEMENT_FLOOR
    # The 1.5 D rule itself is not met; that is the accepted exception.
    assert spec.FULL_THREAD_WORST < 1.5 * 4.826
    # The price: the tip may stand up to 9.0 - 7.9375 past the inboard face.
    assert spec.PROUD_INBOARD_MAX == pytest.approx(1.0625)


def test_u33b_note_is_the_only_manufacturing_note() -> None:
    # The sheet states the worst case its named-exception row records.
    assert "NAMED EXCEPTION TO RULE 12" in spec.DRAWING_NOTES
    worst = f"{spec.FULL_THREAD_WORST_DIAMETERS:.2f}D"
    assert spec.DRAWING_NOTES.startswith(f"THREAD ENGAGEMENT {worst} MIN")
    policy = (Path(spec.__file__).parents[1] / "docs" / "drawing-simplicity-policy.md")
    row = next(
        line
        for line in policy.read_text(encoding="utf-8").splitlines()
        if line.startswith("| MHA-139")
    )
    assert f"{worst} at the printed worst case" in row
    # The ruling ID stays in the spec source; the sheet reader never sees it.
    assert "U33b" not in spec.DRAWING_NOTES
    assert len(spec.DRAWING_NOTES.splitlines()) == 1
    assert len(spec.DRAWING_NOTES) <= 72
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert part.DRAWING_NOTES is spec.DRAWING_NOTES


def test_thread_callout_names_the_size_but_not_the_title_block_class() -> None:
    assert spec.THREAD_CALLOUT == "#10-24 UNC"
    assert "2A" not in spec.THREAD_CALLOUT
    assert drawing.THREAD_CALLOUT is spec.THREAD_CALLOUT


def test_running_shoulder_carries_the_only_finish_symbol() -> None:
    assert len(spec.SURFACE_FINISHES) == 1
    control = spec.SURFACE_FINISHES[0]
    assert control.key == "pivot_shoulder"
    assert control.roughness_um == MACHINED_UM
    assert control.face.diameter_mm == spec.SHOULDER_DIA
    assert (
        spec.HEAD_LENGTH < control.face.contains_z_mm < spec.SEAT_STATION
    )


def test_notes_stay_within_rule_six() -> None:
    assert len(spec.DRAWING_NOTES.splitlines()) <= 4
    assert spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW\nSCALE 1:1"
    assert len(spec.ISOMETRIC_VIEW_NOTE.splitlines()) <= 4


def test_modelled_volume_is_the_turned_body_less_the_slot() -> None:
    head = math.pi * 4.0**2 * 3.0
    shoulder = math.pi * 3.0**2 * 58.5
    relief = math.pi * (3.4 / 2.0) ** 2 * 1.5
    thread = math.pi * (4.826 / 2.0) ** 2 * 7.5
    # Pappus: the lead's 0.5 x 0.5 corner triangle, centroid 1.7 + 0.5/3 out,
    # stays; the tip chamfer's, centroid 2.413 - 0.5/3 out, goes.
    lead = 2.0 * math.pi * (1.7 + 0.5 / 3.0) * (0.5 * 0.5 / 2.0)
    tip = 2.0 * math.pi * (4.826 / 2.0 - 0.5 / 3.0) * (0.5 * 0.5 / 2.0)
    assert part.V_LEAD == pytest.approx(lead)
    assert part.V_TIP_CHAMFER == pytest.approx(tip)
    assert part.V_BODY == pytest.approx(head + shoulder + relief + thread + lead - tip)
    assert part.V_RELIEF + part.V_TIP_CHAMFER == pytest.approx(part.V_TURNED - part.V_BODY)
    # A 1.0 strip across a Ø8 circle: integrate the chord 2*sqrt(r^2 - y^2)
    # over |y| <= 0.5 independently of the closed form.
    steps = 10_000
    dy = 1.0 / steps
    chords = sum(
        2.0 * math.sqrt(16.0 - (-0.5 + (i + 0.5) * dy) ** 2) for i in range(steps)
    )
    assert part.slot_strip_area(4.0, 1.0) == pytest.approx(chords * dy, abs=1e-6)
    assert part.slot_strip_area(4.0, 1.0) < 1.0 * 8.0
    assert part.V_FINAL == pytest.approx(part.V_BODY - part.V_SLOT)


def test_side_view_stations_follow_the_model() -> None:
    scale = drawing.SHEET_SCALE[0]
    assert drawing.HEAD_FACE_X - drawing.TIP_X == pytest.approx(
        spec.OVERALL_LENGTH * scale / 1000.0
    )
    assert drawing.HEAD_FACE_X - drawing.UNDERHEAD_X == pytest.approx(
        spec.HEAD_LENGTH * scale / 1000.0
    )
    assert drawing.UNDERHEAD_X - drawing.SEAT_X == pytest.approx(
        spec.SHOULDER_LENGTH * scale / 1000.0
    )
    assert drawing.SEAT_X - drawing.RELIEF_END_X == pytest.approx(
        spec.RELIEF_WIDTH * scale / 1000.0
    )
    # Model +Z runs paper-left in *Right: tip left, head right.
    assert (
        drawing.TIP_X
        < drawing.RELIEF_END_X
        < drawing.SEAT_X
        < drawing.UNDERHEAD_X
        < drawing.HEAD_FACE_X
    )


def test_head_end_view_is_the_third_angle_right_view() -> None:
    assert drawing.END_CENTER[1] == drawing.SIDE_CENTER[1]
    head_radius = spec.HEAD_DIA * drawing.SHEET_SCALE[0] / 2000.0
    head_dia_text_x = drawing.SIDE_KEEP["HeadDia"][0]
    assert drawing.HEAD_FACE_X < head_dia_text_x < drawing.END_CENTER[0] - head_radius - 0.010


def test_sheet_placements_stay_inside_the_border() -> None:
    inner = (0.0127, 0.0127, 0.4191, 0.2667)  # ASME B landscape inner border
    title_block = (0.218, 0.065)  # x >= and y <=
    points = [
        drawing.SIDE_CENTER,
        drawing.END_CENTER,
        drawing.ISO_CENTER,
        drawing.THREAD_NOTE_XY,
        drawing.FINISH_SYMBOL,
        drawing.ISO_NOTE_XY,
        (drawing.TIP_X, drawing.SIDE_CENTER[1]),
        *drawing.SIDE_KEEP.values(),
        *drawing.END_KEEP.values(),
    ]
    for x, y in points:
        assert inner[0] < x < inner[2] and inner[1] < y < inner[3]
        assert not (x >= title_block[0] and y <= title_block[1])
    # Picks land on the features they annotate.  The thread callout's leader
    # tip lands on the full-thread portion, never on the relief groove.
    assert drawing.THREAD_PICK[0] == drawing.THREAD_START_X
    assert drawing.THREAD_START_X - drawing.TIP_X == pytest.approx(
        spec.TIP_CHAMFER * drawing.SHEET_SCALE[0] / 1000.0
    )
    assert not drawing.RELIEF_END_X <= drawing.THREAD_PICK[0] <= drawing.SEAT_X
    assert drawing.THREAD_PICK[0] < drawing.RELIEF_END_X
    # The relief dimensions sit on the groove, the Ø below the profile and the
    # width above it, both above the first baseline row.
    for name in ("ReliefDia", "ReliefWidth"):
        assert drawing.RELIEF_END_X < drawing.SIDE_KEEP[name][0] < drawing.SEAT_X
    # The Ø stands on the floor, clear of the lead.
    lead_foot_x = drawing.SEAT_X - spec.RELIEF_LEAD * drawing.SHEET_SCALE[0] / 1000.0
    assert drawing.RELIEF_END_X < drawing.SIDE_KEEP["ReliefDia"][0] < lead_foot_x
    # The 45-degree lead rides the Ø callout; only the width stands above.
    assert "ReliefLead" not in drawing.SIDE_KEEP
    assert spec.RELIEF_CALLOUT == "0.5 X 45 DEG LEAD"
    assert drawing.SIDE_KEEP["ReliefWidth"][1] > drawing.RELIEF_TOP_Y
    # The thread note stands up and right of its pick, so the leader slants.
    note_x, note_y = drawing.THREAD_NOTE_XY
    assert note_x - drawing.THREAD_PICK[0] > 0.010
    assert note_y - drawing.SIDE_KEEP["ReliefWidth"][1] > 0.015
    # The slot value stands clear of its 3-mm-apart extension lines.
    assert drawing.END_KEEP["SlotWidth"][1] - drawing.END_CENTER[1] > 0.005
    assert (
        drawing.SIDE_KEEP["ThreadLength"][1] + 0.010
        < drawing.SIDE_KEEP["ReliefDia"][1]
        < 2.0 * drawing.SIDE_CENTER[1] - drawing.THREAD_TOP_Y  # below the thread
    )
    thread_half = spec.THREAD_MODEL_DIA * drawing.SHEET_SCALE[0] / 2000.0
    assert abs(drawing.THREAD_PICK[1] - drawing.SIDE_CENTER[1]) < thread_half
    assert drawing.SEAT_X < drawing.FINISH_PICK[0] < drawing.UNDERHEAD_X
    assert drawing.SEAT_X < drawing.CENTERLINE_PICK[0] < drawing.UNDERHEAD_X
    shoulder_dim_x = drawing.SIDE_KEEP["ShoulderDia"][0]
    assert drawing.SEAT_X < shoulder_dim_x < drawing.UNDERHEAD_X
    assert abs(drawing.CENTERLINE_PICK[0] - shoulder_dim_x) > 0.010
    assert abs(drawing.FINISH_PICK[0] - shoulder_dim_x) > 0.010
