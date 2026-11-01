"""Offline release contracts for MHA-DT-32, the crank handle pivot screw (U33)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_dt_crank_handle_pivot_screw as part
import dt_crank_handle_butt_cup_spec as cup
import dt_crank_handle_pivot_screw_spec as spec
import dt_crank_handle_spec as handle
import dt_crank_hub_geometry as geometry
import draw_dt_crank_handle_pivot_screw as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from _hole_spec import THREAD_MAJOR_MM
from _printed_tolerance import drilled_oversize_mm, edge_break_chamfer_mm, printed_band_mm
from _surface_finish import MACHINED_UM


def test_registry_paths_and_part_name() -> None:
    registered = DRAWINGS_BY_NAME["dt_crank_handle_pivot_screw"]
    assert registered.script == Path(drawing.__file__).resolve()
    assert registered.layout is DrawingLayout.LANDSCAPE
    assert registered.source.as_posix().endswith("/sldprt/dt-crank-handle-pivot-screw.SLDPRT")
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-crank-handle-pivot-screw.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-crank-handle-pivot-screw.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-crank-handle-pivot-screw_drawing.png")
    assert part.PART_NAME == registered.artifact_stem


def test_part_registry_row_is_the_made_screw() -> None:
    row = _config.parts("dt-crank-handle-pivot-screw")
    assert row["number"] == "MHA-DT-32"
    # The title block prints the registry title, not the slug.
    assert row["title"] == "Crank Handle Pivot Screw"
    for grade in ("1018", "12L14", "1/4 in"):
        assert grade in row["material"]
        assert grade in row["material_specification"]
    assert int(row["quantity"]) == 1
    assert row["fit_class"] == "shaft_in_bushing"
    assert row["process"] != "purchased"
    # The SLDPRT Process property comes from this row (Codex review of #921):
    # it names the thread the spec cuts.
    assert row["process"] == f"turned slotted shoulder screw; die-cut {spec.THREAD_SIZE} thread"


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
    assert "draw_dt_crank_handle_pivot_screw.py" in PRECISION_MIGRATED_DRAWINGS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    # The running fit, the head and the small features that could print as
    # nothing at two places (tip chamfer, relief Ø) at three; the stations,
    # slot and relief width at the title block's .XX.
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "HeadDia": 3,
        "HeadLength": 3,
        "ShoulderDia": 3,
        "ShoulderLength": 2,
        "ThreadLength": 2,
        "ReliefDia": 3,
        "ReliefWidth": 2,
        "TipChamfer": 3,
        "SlotWidth": 2,
        "SlotDepth": 2,
        "OverallLength": 2,
    }
    # User ruling 2026-09-29 (MHA-DT-32 review): the shoulder is turned to suit
    # the bonded handle, so its length is a reference.
    assert spec.REFERENCE_DIMENSIONS == {"OverallLength", "ShoulderLength"}
    # Every band comes from a named spec constant, never a typed number; the
    # head, slot and relief hold the title block's bands.
    assert model_toleranced_dimensions(part) == {
        ("ScrewProfile", "ShoulderDia"): "*deviations(SHOULDER_DIA_BAND)",
        ("ScrewProfile", "ThreadLength"): "*deviations(THREAD_LENGTH_BAND)",
        ("ScrewProfile", "ReliefLead"): "RELIEF_LEAD_TOL",
    }
    # The F12 running fit (#290): .156 0/-.0020 in a .161 +.0005/0 ream.
    assert spec.SHOULDER_DIA == pytest.approx(0.156 * 25.4)
    assert spec.SHOULDER_DIA_BAND == pytest.approx((0.0, -0.002 * 25.4))
    assert spec.SHOULDER_LENGTH == pytest.approx(
        spec.HANDLE_STACK_NOMINAL + spec.END_PLAY_NOMINAL
    )
    assert not hasattr(spec, "SHOULDER_LENGTH_TOL")
    assert spec.THREAD_LENGTH_BAND[0] == 0.0 > spec.THREAD_LENGTH_BAND[1]


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
    # User ruling 2026-09-30 (ch30 eight-views-4, concept v4): the photographed
    # head; #4-40 (user ruling 2026-09-30, local review of fbf82ad96).
    xx = printed_band_mm(2, unit=spec.UNIT)
    assert spec.HEAD_DIA_TOL == pytest.approx(printed_band_mm(3, unit=spec.UNIT))
    assert spec.HEAD_LENGTH_TOL == pytest.approx(printed_band_mm(3, unit=spec.UNIT))
    assert spec.SLOT_DEPTH_TOL == pytest.approx(xx)
    # The banded head under the banded slot keeps a head web at the worst
    # case, and the slot can never print as nothing (re-review).
    assert spec.SLOT_WEB_MIN == pytest.approx(
        spec.HEAD_LENGTH - spec.HEAD_LENGTH_TOL - (spec.SLOT_DEPTH + spec.SLOT_DEPTH_TOL)
    )
    assert spec.SLOT_WEB_MIN > spec.SLOT_DEPTH + spec.SLOT_DEPTH_TOL
    assert spec.SLOT_DEPTH - spec.SLOT_DEPTH_TOL > 0.0
    # The tip chamfer is a single MAX limit that never cuts past the thread
    # depth (#290 review of b28d38a16).
    assert spec.TIP_CHAMFER_MAX == spec.TIP_CHAMFER == pytest.approx(0.015 * 25.4)
    assert spec.TIP_CHAMFER_BAND == (0.0, -spec.TIP_CHAMFER)
    assert spec.THREAD_SIZE == "#4-40"
    assert spec.THREAD_MODEL_DIA == THREAD_MAJOR_MM["#4-40"] == 2.845
    assert spec.THREAD_PITCH == pytest.approx(25.4 / 40.0)
    assert spec.SEAT_STATION == pytest.approx(spec.HEAD_LENGTH + spec.SHOULDER_LENGTH)
    assert spec.OVERALL_LENGTH == pytest.approx(spec.SEAT_STATION + spec.THREAD_LENGTH)
    # The largest tip chamfer stays within the thread depth (17/24 H).
    assert spec.TIP_CHAMFER_MAX <= 0.61343 * 25.4 / 40.0
    assert spec.HEAD_DIA + spec.HEAD_DIA_TOL < spec.STOCK_DIA == pytest.approx(6.35)


def test_u33_running_fit_end_play_and_engagement() -> None:
    # Handle numbers come from its own spec, the arm thickness from the shared
    # crank interface geometry.
    assert handle.PIVOT_BORE_DIA + handle.PIVOT_BORE_BAND[1] == pytest.approx(0.161 * 25.4)
    assert handle.PIVOT_BORE_DIA + handle.PIVOT_BORE_BAND[0] == pytest.approx(0.1615 * 25.4)

    # The fitted shoulder: the cup face on the handle's basic length less the
    # pocket is the bonded handle, plus the modelled end play.
    assert spec.HANDLE_STACK_NOMINAL == pytest.approx(handle.HANDLE_LENGTH - cup.POCKET_DEPTH)
    low, high = spec.END_PLAY_RANGE
    assert low < spec.END_PLAY_NOMINAL < high
    # The ream over the shoulder, on diameter.
    assert spec.DIAMETRAL_CLEARANCE_MIN == pytest.approx(
        spec.HANDLE_BORE_MIN - spec.SHOULDER_DIA_MAX
    )
    assert spec.DIAMETRAL_CLEARANCE_MAX == pytest.approx(
        spec.HANDLE_BORE_MAX - spec.SHOULDER_DIA_MIN
    )
    assert spec.DIAMETRAL_CLEARANCE_MIN > 0.0
    # The shortest threaded section always spans the stock arm.
    assert spec.THREAD_LENGTH_MIN >= spec.ARM_STOCK_THICKNESS
    # The head retains the handle.
    assert spec.HEAD_DIA > spec.HANDLE_BORE_MAX


def test_thread_relief_sits_below_the_minor_with_a_45_degree_lead() -> None:
    # At the title block's .XXX band, the largest relief stays under the root.
    assert spec.RELIEF_DIA_MAX == pytest.approx(spec.RELIEF_DIA + 0.005 * 25.4)
    # Under the deepest die-cut root, not just the basic one (local reviews
    # of 747487c71 and 21bb244c5): 2A PD min 0.0925 in less 0.649519 P.
    assert spec.THREAD_MINOR_2A_MIN_EST == pytest.approx(
        (0.0925 - 0.649519 / 40.0) * 25.4, abs=1e-6
    )
    assert spec.THREAD_MINOR_2A_MIN_EST == pytest.approx(1.937, abs=1e-3)
    assert spec.RELIEF_DIA_MAX <= spec.THREAD_MINOR_2A_MIN_EST
    # The printed limits are the model band's (Codex P2 on #1139).
    assert spec.RELIEF_LEAD_LIMITS == pytest.approx(
        (spec.RELIEF_LEAD - spec.RELIEF_LEAD_TOL, spec.RELIEF_LEAD + spec.RELIEF_LEAD_TOL)
    )
    assert spec.RELIEF_END_STATION == pytest.approx(spec.SEAT_STATION + spec.RELIEF_WIDTH)
    # At or below the #4-40 external minor: the P/8-flat UN root
    # (2.845 - 1.299038 x 0.635 = Ø2.020) and the UNR-2A reference max
    # ((0.1114 - 1.226869 / 40) x 25.4 = Ø2.051).
    assert spec.THREAD_MINOR_BASIC_ROOT == pytest.approx(2.0201, abs=1e-4)
    assert spec.THREAD_MINOR_UNR_2A_MAX == pytest.approx(2.0505, abs=1e-4)
    assert spec.RELIEF_DIA_MAX <= spec.THREAD_MINOR_BASIC_ROOT
    # The lead tops out inside the Ø2.845 thread major, leaving a flat seat.
    assert spec.SEAT_FLAT_INNER_DIA == pytest.approx(spec.RELIEF_DIA + 2.0 * spec.RELIEF_LEAD)
    assert spec.SEAT_FLAT_INNER_DIA_MAX == pytest.approx(
        spec.RELIEF_DIA_MAX + 2.0 * spec.RELIEF_LEAD_LIMITS[1]
    )
    assert spec.SEAT_FLAT_INNER_DIA_MAX < spec.THREAD_MODEL_DIA
    # The seat on the arm face, from printed limits (local reviews of
    # 1f3067ef2, fbf82ad96, 21bb244c5 and aed772158): MHA-DT-06's tapped mouth
    # max, out to the smallest shoulder with its seat break, less the screw's
    # float off axis in the 2A/2B fit.  Under the title block's edge break on
    # both edges there would be almost none.
    assert spec.SEAT_CONTACT_INNER_DIA == spec.TAPPED_MOUTH_DIA_MAX
    assert spec.SEAT_CONTACT_OUTER_DIA_MIN == pytest.approx(
        spec.SHOULDER_DIA_MIN - 2.0 * spec.SEAT_EDGE_BREAK_MAX
    )
    assert spec.THREAD_FIT_OFFSET_MAX == pytest.approx((0.0991 - 0.0925) / 2.0 * 25.4)
    assert spec.SEAT_RADIAL_MIN == pytest.approx(
        (spec.SEAT_CONTACT_OUTER_DIA_MIN - spec.SEAT_CONTACT_INNER_DIA) / 2.0
        - spec.THREAD_FIT_OFFSET_MAX,
        abs=1e-4,
    )
    assert spec.SEAT_RADIAL_MIN >= 0.2
    title_break = edge_break_chamfer_mm(unit=spec.UNIT)
    assert (spec.SHOULDER_DIA_MIN - 2.0 * title_break) - (2.845 + 2.0 * title_break) < 0.1
    assert spec.SEAT_FLAT_ANNULUS_AREA == pytest.approx(
        math.pi / 4.0 * (spec.SHOULDER_DIA**2 - spec.TAPPED_MOUTH_DIA_MAX**2)
    )
    assert spec.SEAT_FLAT_ANNULUS_AREA_MIN == pytest.approx(
        math.pi / 4.0
        * (spec.SEAT_CONTACT_OUTER_DIA_MIN**2 - spec.SEAT_CONTACT_INNER_DIA**2)
    )
    # The one-piece screw goes in from the butt: nothing on the arm end of it
    # is larger than the bore it passes (local review of fbf82ad96).
    assert not hasattr(spec, "COLLAR_DIA")
    assert spec.SHOULDER_DIA_MAX < spec.HANDLE_BORE_MIN
    assert 0.0 < spec.SEAT_FLAT_ANNULUS_AREA_MIN < spec.SEAT_FLAT_ANNULUS_AREA
    # The neck is ~64 percent of the #4-40 tensile stress area (0.00604 in^2).
    assert spec.NECK_AREA == pytest.approx(math.pi / 4.0 * spec.RELIEF_DIA**2)
    assert spec.TENSILE_STRESS_AREA == pytest.approx(3.90, abs=0.01)
    assert spec.NECK_TO_STRESS_AREA == pytest.approx(0.64, abs=0.01)
    # The lead's band is model-owned and prints as limits in its callout, and
    # the tip chamfer carries its own band (MHA-DT-32 re-review: at .X either
    # could print as nothing).  The relief width (.XX) and diameter (.XXX)
    # are routine: the floor past the longest lead keeps 1.5 #4-40 pitches
    # (machinist review of crank-v4-16; local review of 20dac9d3f).
    toleranced = {name for _, name in model_toleranced_dimensions(part)}
    assert "ReliefLead" in toleranced
    assert not {"ReliefWidth", "ReliefDia"} & toleranced
    xx = printed_band_mm(2, unit=spec.UNIT)
    assert spec.RELIEF_WIDTH_MIN == pytest.approx(spec.RELIEF_WIDTH - xx)
    assert spec.RELIEF_FLOOR_MIN == pytest.approx(
        spec.RELIEF_WIDTH_MIN - spec.RELIEF_LEAD_LIMITS[1]
    )
    assert spec.RELIEF_FLOOR_MIN >= 1.5 * 25.4 / 40.0
    assert "ReliefLead" not in set().union(*spec.DRAWING_DIMENSIONS.values())


def test_engagement_meets_the_1_5d_rule_governed_by_the_stock_arm() -> None:
    # User ruling 2026-09-30: the #4-40 screw clears the policy's 1.5D rule at
    # the worst case, so the #8-32's U33b exception stays retired.
    assert spec.ENGAGEMENT_RULE_D == 1.5
    assert not hasattr(spec, "ENGAGEMENT_EXCEPTION_FLOOR_D")
    source = Path(spec.__file__).read_text(encoding="utf-8")
    assert "the #8-32's U33b exception (1.26D) stays" in source
    assert spec.ENGAGEMENT_FLOOR == pytest.approx(1.5 * 2.845)
    # The chamfer's partial threads are excluded: full thread reaches the
    # shortest section less the longest printed chamfer (Codex P2 on #1138).
    assert spec.FULL_THREAD_REACH_MIN == pytest.approx(
        spec.THREAD_LENGTH_MIN - spec.TIP_CHAMFER_MAX
    )
    # Nominal: the thread or the arm, whichever ends first, past the relief.
    assert spec.FULL_THREAD_NOMINAL == pytest.approx(
        min(spec.THREAD_LENGTH - spec.TIP_CHAMFER, spec.ARM_THICKNESS) - spec.RELIEF_WIDTH
    )
    # Thinnest stock 5/16-in arm (mill -0.004 in on a 1-in flat), less its
    # tapped exit break, past the widest printed relief.  The arm governs.
    assert spec.TAP_EXIT_BREAK == pytest.approx(geometry.EDGE_BREAK_MAX_MM)
    assert spec.ARM_STOCK_THICKNESS == pytest.approx(7.9375)
    assert spec.ARM_STOCK_THICKNESS_MIN == pytest.approx(7.8359)
    assert spec.FULL_THREAD_WORST == pytest.approx(
        min(spec.FULL_THREAD_REACH_MIN, spec.ARM_STOCK_THICKNESS_MIN - spec.TAP_EXIT_BREAK)
        - spec.RELIEF_WIDTH_MAX
    )
    assert spec.FULL_THREAD_WORST_DIAMETERS == pytest.approx(
        spec.FULL_THREAD_WORST / 2.845, abs=1e-4
    )
    assert spec.ENGAGEMENT_GOVERNED_BY == "arm"
    # Arm at its printed maximum: the arm still governs.
    assert spec.ARM_PRINTED_THICKNESS_MAX == pytest.approx(
        geometry.ARM_THICKNESS + geometry.GENERAL_1PL_TOL_MM
    )
    assert spec.FULL_THREAD_WORST_PRINTED_ARM == pytest.approx(
        min(spec.FULL_THREAD_REACH_MIN, spec.ARM_PRINTED_THICKNESS_MAX - spec.TAP_EXIT_BREAK)
        - spec.RELIEF_WIDTH_MAX
    )
    # The MHA-DT-32 review's own count: the shortest section less the widest
    # relief and 1.5 pitches of die run-in still spans the stock arm's
    # full-thread need.
    assert spec.THREAD_LENGTH_MIN - spec.RELIEF_WIDTH_MAX - 1.5 * spec.THREAD_PITCH >= (
        spec.FULL_THREAD_WORST
    )
    for engaged in (spec.FULL_THREAD_WORST, spec.FULL_THREAD_WORST_PRINTED_ARM):
        assert engaged >= spec.ENGAGEMENT_FLOOR
    # The 1.5 D rule itself is met, with no exception to record.
    assert spec.FULL_THREAD_WORST >= 1.5 * 2.845
    # User ruling 2026-09-29: the tip is filed flush at assembly.  Filing
    # removes the longest section less the thinnest arm at most, and even the
    # shortest full thread in the thickest stock arm still reaches the face
    # first.
    assert not hasattr(spec, "PROUD_INBOARD_MAX")
    assert spec.FILE_ALLOWANCE_MAX == pytest.approx(
        spec.THREAD_LENGTH_MAX - spec.ARM_STOCK_THICKNESS_MIN, abs=1e-4
    )
    assert spec.FILE_ALLOWANCE_MIN == pytest.approx(
        spec.FULL_THREAD_REACH_MIN - 8.0391, abs=1e-4
    )
    assert spec.FILE_ALLOWANCE_MIN > 0.0


def test_head_bearing_acceptance_accounts_for_running_offset() -> None:
    floor_hole_max = cup.FLOOR_HOLE_DIA + drilled_oversize_mm(unit=cup.UNIT)
    assert spec.HEAD_BEARING_RADIAL_CONCENTRIC_MIN == pytest.approx(
        ((spec.HEAD_DIA - spec.HEAD_DIA_TOL) - floor_hole_max) / 2.0
        - 2.0 * spec.EDGE_BREAK_MAX_MM
    )
    assert spec.HEAD_RUNNING_OFFSET_MAX == pytest.approx(
        min(cup.POCKET_CLEARANCE[1] / 2.0, (floor_hole_max - spec.SHOULDER_DIA_MIN) / 2.0)
    )
    assert spec.HEAD_BEARING_RADIAL_MIN == pytest.approx(
        spec.HEAD_BEARING_RADIAL_CONCENTRIC_MIN - spec.HEAD_RUNNING_OFFSET_MAX
    )
    assert spec.HEAD_BEARING_RADIAL_MIN > 0.0


def test_cup_wall_follows_ruling_b_without_changing_the_head_or_fit() -> None:
    # Owner ruling B on #1375 grows the cup, not any MHA-DT-32 geometry.
    assert spec.CUP_BODY_DIA == cup.BODY_DIA
    assert spec.CUP_BODY_DIA_TOL == cup.BODY_DIA_TOL
    assert spec.CUP_POCKET_CLEARANCE == cup.POCKET_CLEARANCE
    assert spec.POCKET_MAX == pytest.approx(cup.POCKET_DIA_MAX)
    assert spec.CUP_POCKET_WALL_FLOOR_MM == cup.POCKET_WALL_FLOOR_MM
    assert spec.CUP_POCKET_WALL_MIN == cup.POCKET_WALL_MIN
    assert spec.CUP_POCKET_WALL_MIN >= spec.CUP_POCKET_WALL_FLOOR_MM


def test_thread_callout_names_the_size_but_not_the_title_block_class() -> None:
    assert spec.THREAD_CALLOUT == "#4-40 UNC"
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


def test_modelled_volume_is_the_turned_body_less_the_slot() -> None:
    major_r = spec.THREAD_MODEL_DIA / 2.0
    relief_r = spec.RELIEF_DIA / 2.0
    lead, chamfer = spec.RELIEF_LEAD, spec.TIP_CHAMFER
    head = math.pi * (spec.HEAD_DIA / 2.0) ** 2 * spec.HEAD_LENGTH
    shoulder = math.pi * (spec.SHOULDER_DIA / 2.0) ** 2 * spec.SHOULDER_LENGTH
    relief = math.pi * relief_r**2 * spec.RELIEF_WIDTH

    def thread(length: float) -> float:
        return math.pi * major_r**2 * (length - spec.RELIEF_WIDTH)

    def tip(leg: float) -> float:
        return 2.0 * math.pi * (major_r - leg / 3.0) * (leg * leg / 2.0)

    # Pappus: the lead's corner triangle, centroid a third of its leg out
    # from the relief floor, stays; the tip chamfer's goes.
    lead_v = 2.0 * math.pi * (relief_r + lead / 3.0) * (lead * lead / 2.0)
    assert part.V_LEAD == pytest.approx(lead_v)
    assert part.V_BODY == pytest.approx(
        head + shoulder + relief + thread(spec.THREAD_LENGTH) + lead_v - tip(chamfer)
    )
    # Filed flush with the arm, under the tip's edge break.
    installed = spec.INSTALLED_THREAD_LENGTH, spec.INSTALLED_TIP_CHAMFER
    assert part.turned_volume(*installed) == pytest.approx(
        head + shoulder + relief + thread(installed[0]) + lead_v - tip(installed[1])
    )
    assert part.V_INSTALLED == pytest.approx(part.turned_volume(*installed) - part.V_SLOT)
    # A 1.0 strip across a Ø6 circle: integrate the chord 2*sqrt(r^2 - y^2)
    # over |y| <= 0.5 independently of the closed form.
    steps = 10_000
    dy = 1.0 / steps
    chords = sum(
        2.0 * math.sqrt(9.0 - (-0.5 + (i + 0.5) * dy) ** 2) for i in range(steps)
    )
    assert part.slot_strip_area(3.0, 1.0) == pytest.approx(chords * dy, abs=1e-6)
    assert part.slot_strip_area(3.0, 1.0) < 1.0 * 6.0
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
        drawing.SEAT_EDGE_NOTE_XY,
        (drawing.TIP_X, drawing.SIDE_CENTER[1]),
        *drawing.SIDE_KEEP.values(),
        *drawing.END_KEEP.values(),
    ]
    for x, y in points:
        assert inner[0] < x < inner[2] and inner[1] < y < inner[3]
        assert not (x >= title_block[0] and y <= title_block[1])
    # Picks land on the features they annotate.  The thread callout's leader
    # tip lands on the full-thread portion, never on the relief groove.
    assert drawing.THREAD_START_X < drawing.THREAD_PICK[0] < drawing.RELIEF_END_X
    # The relief dimensions sit on the groove, the Ø below the profile and the
    # width above it, both above the first baseline row.
    for name in ("ReliefDia", "ReliefWidth"):
        assert drawing.RELIEF_END_X < drawing.SIDE_KEEP[name][0] < drawing.SEAT_X
    # The Ø stands on the floor, clear of the lead.
    lead_foot_x = drawing.SEAT_X - spec.RELIEF_LEAD * drawing.SHEET_SCALE[0] / 1000.0
    assert drawing.RELIEF_END_X < drawing.SIDE_KEEP["ReliefDia"][0] < lead_foot_x
    # Its offset text is centred on the anchor, so judge the rendered extent
    # (render-measured width), not the anchor: the left edge stands >= 3 mm
    # right of the seat-face extension line, the right edge clear of the
    # shoulder Ø's dimension line.
    text_x, text_y = drawing.RELIEF_DIA_TEXT_XY
    half = drawing.RELIEF_DIA_TEXT_WIDTH / 2.0
    assert (text_x - half) - drawing.SEAT_X >= 0.003
    assert (text_x + half) + 0.003 <= drawing.SIDE_KEEP["ShoulderDia"][0]
    # Failing control: 0f50950a anchored at floor + 6 mm, which run 69a2f961
    # rendered with the LEAD line starting ~10 mm LEFT of the seat face.
    assert (drawing.RELIEF_FLOOR_MID_X + 0.006 - half) - drawing.SEAT_X < 0.003
    # The leader runs down-right from the dimension line on the floor to the
    # underline's left end, passing >= 2 mm under the seat-face corner.
    left = text_x - half
    end_y = text_y - drawing.RELIEF_DIA_TEXT_UNDERLINE_DROP
    start_x, start_y = drawing.RELIEF_FLOOR_MID_X, drawing.SIDE_CENTER[1]
    t = (drawing.SEAT_X - start_x) / (left - start_x)
    leader_y_at_seat = start_y + t * (end_y - start_y)
    shoulder_bottom = 2.0 * drawing.SIDE_CENTER[1] - drawing.SHOULDER_TOP_Y
    assert shoulder_bottom - leader_y_at_seat >= 0.002
    # The block stays above the fitted shoulder length's row.
    assert end_y - drawing.SIDE_KEEP["ShoulderLength"][1] >= 0.010
    # The slot value stands clear of its 3-mm-apart extension lines.
    assert drawing.END_KEEP["SlotWidth"][1] - drawing.END_CENTER[1] > 0.005
    assert (
        drawing.SIDE_KEEP["ThreadLength"][1] + 0.010
        < drawing.SIDE_KEEP["ReliefDia"][1]
        < 2.0 * drawing.SIDE_CENTER[1] - drawing.THREAD_TOP_Y  # below the thread
    )
    thread_half = spec.THREAD_MODEL_DIA * drawing.SHEET_SCALE[0] / 2000.0
    assert abs(drawing.THREAD_PICK[1] - drawing.SIDE_CENTER[1]) == pytest.approx(thread_half)
    assert drawing.SEAT_X < drawing.FINISH_PICK[0] < drawing.UNDERHEAD_X
    assert drawing.SEAT_X < drawing.CENTERLINE_PICK[0] < drawing.UNDERHEAD_X
    shoulder_dim_x = drawing.SIDE_KEEP["ShoulderDia"][0]
    assert drawing.SEAT_X < shoulder_dim_x < drawing.UNDERHEAD_X
    assert abs(drawing.CENTERLINE_PICK[0] - shoulder_dim_x) > 0.010
    assert abs(drawing.FINISH_PICK[0] - shoulder_dim_x) > 0.010
    # The seat-break note lands on the shoulder's silhouette beside the seat
    # corner, clear of the shoulder Ø's dimension line, and its leader rises
    # right of the relief width's text.
    assert drawing.SEAT_EDGE_PICK[1] == drawing.SHOULDER_TOP_Y
    assert drawing.SEAT_X < drawing.SEAT_EDGE_PICK[0] < shoulder_dim_x - 0.010
    assert drawing.SEAT_EDGE_NOTE_XY[0] > drawing.SEAT_EDGE_PICK[0]


def test_printed_material_fits_one_title_block_line() -> None:
    """Farm 3591da7a: the 51-character material wrapped into the DRAWN PER row.
    Gooseneck measured the MATERIAL cell at 36 characters; the long form stays
    in material_specification."""
    row = _config.parts("dt-crank-handle-pivot-screw")
    assert len(str(row["material"])) <= 36
    assert "cold-finished" in str(row["material_specification"])


def test_assembly_seats_the_shoulder_on_the_arm_and_files_the_tip_flush() -> None:
    """#831 P1 (Codex PRRT_kwDOPHDy386lqC_R): MHA-DT-32 is inserted in the drive
    train with ArmSeat on the arm's outboard face.  User ruling 2026-09-29
    (ch11 p.14): its tip is filed flush with the arm's inboard face, so the
    drive train places the INSTALLED configuration (the MHA-DT-30 precedent)."""
    import build_dt_drive_train_assembly as assembly

    assert assembly.HANDLE_SCREW_Z0 + spec.SEAT_STATION == pytest.approx(
        assembly.CRANK_ARM_Z0
    )
    assert assembly.HANDLE_SCREW_TIP_Z == pytest.approx(assembly.CRANK_ARM_ORIGIN_Z)
    assert spec.INSTALLED_THREAD_LENGTH == pytest.approx(geometry.ARM_THICKNESS)
    assert spec.INSTALLED_TIP_CHAMFER == pytest.approx(spec.EDGE_BREAK_MAX_MM)
    assert assembly.HANDLE_SCREW_INSTALLED_CONFIG == spec.INSTALLED_CONFIG == "INSTALLED"
    source = Path(assembly.__file__).read_text(encoding="utf-8")
    assert "configuration=HANDLE_SCREW_INSTALLED_CONFIG," in source


def test_installed_configuration_is_split_from_a_finished_default() -> None:
    import build_dt_crank_handle_pivot_screw as part

    source = Path(part.__file__).read_text(encoding="utf-8")
    split = source.index("create_configuration {INSTALLED_CONFIG}")
    for edit in (
        "await apply_material(adapter, MATERIAL)",
        "author_part_pmi(adapter",
        'blank_sketch(adapter, "StationReference")',
        "apply_drawing_precision(adapter, DRAWING_PRECISION)",
    ):
        assert source.index(edit) < split, edit
    assert "assert_saved_configurations_regenerate(adapter, PART_NAME)" in source
    assert "require_material_in_every_configuration(" in source
    assert part.V_INSTALLED < part.V_FINAL
    assert _config.parts("dt-crank-handle-pivot-screw")["description"] == "CRANK HANDLE PIVOT SCREW"


def test_quarter_inch_arm_stock_fails_the_1_5d_rule(monkeypatch) -> None:
    # The arm stock governs the worst-case engagement: 1/4-in bar would leave
    # under 1.5D of full thread past the widest relief.
    # Executed as a separate, unregistered module: reloading the real one
    # would swap its band tuples for new objects under every importer
    # (test_fit_bands tracks them by identity).
    import importlib.util
    from fractions import Fraction

    assert spec.ENGAGEMENT_RULE_D == 1.5
    monkeypatch.setattr(geometry, "ARM_STOCK_THICKNESS_IN", Fraction(1, 4))
    monkeypatch.setattr(geometry, "ARM_STOCK_THICKNESS", 0.25 * 25.4)
    monkeypatch.setattr(geometry, "ARM_STOCK_THICKNESS_MIN", 0.246 * 25.4)
    probe_spec = importlib.util.spec_from_file_location("_quarter_inch_probe", spec.__file__)
    probe = importlib.util.module_from_spec(probe_spec)
    with pytest.raises(AssertionError, match="under the 1.5D rule"):
        probe_spec.loader.exec_module(probe)
    assert probe.ARM_STOCK_THICKNESS == pytest.approx(6.35)
    assert probe.FULL_THREAD_WORST == pytest.approx(
        0.246 * 25.4 - probe.TAP_EXIT_BREAK - probe.RELIEF_WIDTH_MAX
    )
    assert probe.FULL_THREAD_WORST < 1.5 * probe.THREAD_MODEL_DIA


def test_arm_interference_allowance_follows_the_thread_size() -> None:
    # _interference_contracts names the size rather than importing this spec
    # (every assembly imports it); the allowance must still be this thread's.
    import _interference_contracts as contracts
    from _hole_spec import TAP_DRILL_MM

    pair = frozenset(("dt-crank-handle-pivot-screw-1", "dt-crank-arm-1"))
    assert contracts._DRIVE_TRAIN_ALLOWED_PAIRS[pair] == pytest.approx(
        contracts._smooth_annulus_limit_mm3(
            THREAD_MAJOR_MM[spec.THREAD_SIZE], TAP_DRILL_MM[spec.THREAD_SIZE], 7.0
        )
    )


def test_worst_engagement_clears_the_novice_margin_by_geometry() -> None:
    # Main 2026-09-25: reach >= 1.25D at the worst case by geometry; the
    # #4-40 (user ruling 2026-09-30) reaches the policy's 1.5D.
    assert spec.FULL_THREAD_WORST_DIAMETERS >= 1.5
    assert spec.RELIEF_WIDTH_MAX == pytest.approx(
        spec.RELIEF_WIDTH + printed_band_mm(2, unit=spec.UNIT)
    )



def test_station_reference_is_saved_hidden_and_imported_per_view() -> None:
    # #880: a reference sketch owns printed dimensions but no geometry, so the
    # part saves it hidden (no assembly instance renders it) and the drawing
    # shows it per view through _drawing_hidden_sketches to import them.
    build = Path(drawing.__file__).with_name("build_dt_crank_handle_pivot_screw.py").read_text(encoding="utf-8")
    blank = 'blank_sketch(adapter, "StationReference")'
    assert blank in build
    assert build.index(blank) < build.rindex("save_part_and_images(adapter, PART_NAME)")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "from _drawing_hidden_sketches import curate_view_dimensions" in source
    assert "    curate_view_dimensions,\n" not in source.replace("\r\n", "\n")
    assert "StationReference" in spec.DRAWING_DIMENSIONS
