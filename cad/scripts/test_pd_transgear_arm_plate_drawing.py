"""Offline contracts for the transgear arm plate (MHA-PD-19) drawing."""

from __future__ import annotations

import math
import re
import runpy
from pathlib import Path

import pytest

import _config
import build_pd_paper_drive_assembly as assembly
import build_pd_transgear_arm_plate as part
import draw_pd_transgear_arm_plate as drawing
import pd_transgear_arm_geometry as arm
import pd_rack_pinion_spec as disc
import pd_transgear_arm_plate_geometry as geometry
import pd_vn_transgear_arm_plate_screw_spec as screw
import pd_transgear_arm_plate_spec as spec
import pd_transgear_arm_plate_notes as notes
import pd_cluster_air as cluster_air
import transgear_cluster_fit as cluster_fit
import transgear_hanger_joints as joints
import pd_transgear_knob_shaft_spec as knob_shaft
from _buildgraph import module_deps_of
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _fit_deviations import deviations
from _printed_tolerance import edge_break_chamfer_mm, edge_break_radius_mm, printed_deviations
from pd_cluster_stack_band import FIT_LENGTH_BAND_IN


def _band(places: int) -> float:
    return _config.title_block(f"linear_{places}pl", unit="in")["band_in"] * 25.4


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-transgear-arm-plate.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-transgear-arm-plate.pdf")
    row = DRAWINGS_BY_NAME["pd_transgear_arm_plate"]
    assert row.script == Path(drawing.__file__).resolve()
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_has_one_view() -> None:
    """Each marked dimension prints in one view, save the countersink Ø: the
    screw holes' one hole callout states it, on the drill Ø (machinist
    review of the fan-out screen: two callouts for one hole)."""
    marked = set().union(*spec.DRAWING_DIMENSIONS.values()) - {"CskDia"}
    views = (drawing.PLAN_KEEP, drawing.BACK_KEEP, drawing.SECTION_KEEP)
    assert set().union(*views) == marked
    assert sum(len(view) for view in views) == len(marked)
    assert set(drawing.DIMENSION_CALLOUTS) | set(drawing.CALLOUTS_ABOVE) <= marked
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS


def test_the_plate_bore_and_printed_hole_stations_follow_the_reducer_geometry() -> None:
    theta = math.radians(disc.MESH_ANGLE_DEG) - math.radians(arm.ARM_ANGLE_DEG)
    bore_station = arm.PIN_STATION + disc.CENTRE_DISTANCE * math.cos(theta)
    bore_offset = disc.CENTRE_DISTANCE * math.sin(theta)
    assert geometry.BORE_STATION == pytest.approx(bore_station)
    assert geometry.BORE_OFFSET == pytest.approx(bore_offset)
    bore_xy = tuple(
        assembly.PIVOT_XY[axis]
        + bore_station * arm.ARM_U[axis]
        + bore_offset * arm.ARM_N[axis]
        for axis in (0, 1)
    )
    assert assembly.KNOB_SHAFT_XY == pytest.approx(bore_xy)
    assert math.dist(assembly.STUD_XY, bore_xy) == pytest.approx(disc.CENTRE_DISTANCE)
    for index, (x, y) in enumerate(geometry.SCREW_HOLES, start=1):
        # Transform the bore-origin plate coordinates back to the arm's pivot
        # origin: both holes must meet the real taps, on the arm centreline.
        assert x + bore_station == pytest.approx(arm.PLATE_TAP_STATIONS[index - 1])
        assert y + bore_offset == pytest.approx(0.0)
        assert part.SCREW_HOLES[index - 1] == pytest.approx((x, y))
    # Hole 1's text sits between its witness lines; hole 2's stands outboard
    # of its own, clear of K's witness line.
    assert drawing.PLAN_KEEP["ScrewHoleX1"][0] == pytest.approx(geometry.SCREW_HOLES[0][0] / 2.0)
    assert drawing.PLAN_KEEP["ScrewHoleX2"][0] > geometry.SCREW_HOLES[1][0] + 3.0
    assert part.SCREW_HOLE_Y == pytest.approx(-bore_offset)
    assert drawing.PLAN_KEEP["ScrewHoleY"][1] == pytest.approx(-bore_offset / 2.0)
    for corner, edge_x in (
        (geometry.TOP_LEFT, geometry.EDGE_MINUS_X),
        (geometry.TOP_RIGHT, geometry.EDGE_PLUS_X),
    ):
        assert corner[1] == pytest.approx(
            arm.edge_half_width(edge_x + bore_station) - bore_offset
        )


@pytest.mark.parametrize("centre_change", (-0.5, 0.5))
def test_plate_outline_notch_and_holes_follow_the_physical_bore_source(
    monkeypatch: pytest.MonkeyPatch, centre_change: float
) -> None:
    # Source mutation only: these deltas are not a manufacturing acceptance band.
    monkeypatch.setattr(disc, "CENTRE_DISTANCE", disc.CENTRE_DISTANCE + centre_change)
    fresh_arm = runpy.run_path(arm.__file__)
    for name in (
        "KNOB_BORE_STATION", "KNOB_BORE_OFFSET", "PLATE_SCREW_MID_STATION",
        "PLATE_TAP_STATIONS", "LOCATOR_SITES_MM",
    ):
        monkeypatch.setattr(arm, name, fresh_arm[name])
    fresh = runpy.run_path(geometry.__file__)
    assert fresh["BORE_STATION"] == fresh_arm["KNOB_BORE_STATION"]
    assert fresh["BORE_OFFSET"] == fresh_arm["KNOB_BORE_OFFSET"]
    assert fresh["SCREW_HOLES"][0][1] == pytest.approx(-fresh["BORE_OFFSET"])
    assert fresh["SCREW_HOLES"] != geometry.SCREW_HOLES
    assert fresh["TOP_LEFT"] != geometry.TOP_LEFT
    assert fresh["NOTCH_LEFT"] != geometry.NOTCH_LEFT
    for name in ("HUB_FACE_Z", "BOSS_FACE_Z", "FRONT_FACE_Z", "REAR_FACE_Z"):
        assert fresh[name] == getattr(geometry, name)
    assert all(worst >= geometry.WALL_TARGET for _, worst in fresh["WALLS"].values())


def test_the_explicit_bands_are_the_bore_the_knob_float_and_the_hole_positions() -> (
    None
):
    assert model_toleranced_dimensions(part) == {
        ("LocatorProfile", "f'LocatorDia{index}'"): "*deviations(LOCATOR_HOLE_BAND_MM)",
        ("BearingProfile", "HubToBoss"): "HUB_TO_BOSS_TOLERANCE",
        ("BearingProfile", "HubFaceToMounting"): "HUB_FACE_TO_MOUNTING_BAND",
        ("BoreProfile", "BoreDia"): "*deviations(BORE_BAND)",
    }
    # The hub station is a disc-cluster stack term: it prints the cluster's
    # band (rule 4).
    assert geometry.HUB_FACE_TO_MOUNTING_BAND == FIT_LENGTH_BAND_IN
    assert spec.DRAWING_PRECISION_BY_NAME["HubFaceToMounting"] == 3
    # The H7 bore prints its sourced limits; zero lower deviation is intentional.
    lower, upper = deviations(spec.BORE_BAND)
    assert (lower, upper) == geometry.BORE_DIA_LIMITS
    assert 0.0 <= lower < upper


def test_every_printed_band_is_no_wider_than_the_arithmetic_assumed() -> None:
    """The walls and the screw engagement were judged at the geometry
    module's bands; the title-block row each printed place count invokes must
    not be wider."""
    for places, band in spec.BAND_BY_PLACES.items():
        assert band >= _band(places)
    precision = spec.DRAWING_PRECISION_BY_NAME
    for name, judged in (
        ("ThicknessOverArm", geometry.THICKNESS_OVER_ARM_BAND),
        ("HubDia", geometry.BAND_XX),
        ("NotchLeftY", geometry.NOTCH_BAND),
        ("NotchRightY", geometry.NOTCH_BAND),
        ("CskDia", geometry.CSK_DIA_BAND),
        ("HubFaceToMounting", geometry.BAND_XXX),
    ):
        assert judged >= _band(precision[name]), name
    # The explicitly banded dimensions print enough places to show their band.
    for name, places in (
        ("BoreDia", 4), ("HubToBoss", 3), ("ScrewHoleX1", 4), ("ScrewHoleX2", 4),
        ("ScrewHoleY", 4),
    ):
        assert precision[name] == places, name


def test_the_worst_case_walls_hold_at_the_printed_bands() -> None:
    """Recompute the thinnest walls from the printed title-block rows, with
    each exposed edge's 0.254 (R.010) break and the drill run-off (full worst case)."""
    drill = geometry.DRILL_GROWTH
    brk = geometry.OUTLINE_EDGE_BREAK_MAX_MM
    assert brk == pytest.approx(0.254) and arm.DRILL_RUN_OFF_DEG == 0.3
    bore_r_max = (geometry.BORE_DIA + geometry.BORE_DIA_LIMITS[1]) / 2.0
    hub_wall = (
        geometry.HUB_DIA - _band(spec.DRAWING_PRECISION_BY_NAME["HubDia"])
    ) / 2.0 - bore_r_max - 2.0 * brk
    assert hub_wall >= geometry.WALL_TARGET
    # Each screw hole's plain Ø.014 zone holds its axis over the drilled
    # cylinder; past the cone's floor the axis runs on at the drill's
    # run-off, to the deepest stock's rear face.
    deepest = geometry.THICKNESS_OVER_ARM + geometry.THICKNESS_OVER_ARM_BAND
    run_off = math.tan(math.radians(arm.DRILL_RUN_OFF_DEG))
    assert float(spec.GEOMETRIC_TOLERANCES_IN["screw_position"]) * 25.4 == pytest.approx(
        2.0 * geometry.SCREW_HOLE_POSITION_RADIUS_MM
    )
    position = geometry.SCREW_HOLE_POSITION_RADIUS_MM + (
        deepest - geometry.SCREW_HOLE_ZONE_LENGTH_MIN_MM
    ) * run_off
    assert geometry.SCREW_AXIS_RADIUS_IN_PLATE_MM == pytest.approx(position)
    hole_walls = []
    for x, y in geometry.SCREW_HOLES:
        centre_gap = math.hypot(x, y) - position
        hole_walls.append(
            centre_gap - bore_r_max - (geometry.SCREW_HOLE_DIA + drill) / 2.0 - brk
            - (deepest + geometry.HUB_TO_BOSS + geometry.HUB_TO_BOSS_BAND) * run_off
        )
    assert min(hole_walls) == pytest.approx(geometry.WALLS["bore to screw holes"][1])
    assert min(hole_walls) >= geometry.WALL_TARGET
    for name, (_nominal, worst) in geometry.WALLS.items():
        assert worst >= geometry.WALL_TARGET, name
    # The locator to the outline: the plate's 0.25 break and the run-off
    # through the deepest printed plate, on top of the hole's mouth break.
    deepest = geometry.THICKNESS_OVER_ARM + geometry.THICKNESS_OVER_ARM_BAND
    assert geometry.HOLE_RUN_OFF_MM == pytest.approx(deepest * run_off)
    for index in (1, 2):
        nominal, worst = geometry.WALLS[f"locator {index} to plate edge/notch"]
        assert worst < nominal - brk - deepest * run_off
    # Each countersink to its side edge: the .X edge band, the cone's upper
    # Ø, the extrapolated axis, the hole's run-off to its rear exit (the cone
    # follows it; the edge was milled first) and both edge breaks.
    to_edge = min(
        geometry.SCREW_HOLES[0][0] - geometry.EDGE_MINUS_X,
        geometry.EDGE_PLUS_X - geometry.SCREW_HOLES[-1][0],
    )
    # The budget charges the outline's printed reach for the side edge, no
    # less than the title block's .XX row.
    assert geometry.OUTLINE_BAND >= _band(geometry.OUTLINE_PLACES)
    side_wall = (
        to_edge - geometry.CSK_DIA_LIMITS_MM[1] / 2.0 - geometry.OUTLINE_BAND - position
        - deepest * run_off - 2.0 * brk
    )
    assert geometry.WALLS["countersinks to the side edges"][1] == pytest.approx(side_wall)
    assert side_wall >= geometry.WALL_TARGET


def test_the_slip_hole_mouths_take_the_title_block_break() -> None:
    """Fan-out L2 (delegated ruling 2026-11-07 (Main)): the plate's dowel
    slip holes print no break of their own; every stack their mouths touch
    holds at the title block's .010 on both legs."""
    brk = max(
        edge_break_radius_mm(unit=geometry.UNIT), edge_break_chamfer_mm(unit=geometry.UNIT)
    )
    assert geometry.LOCATOR_MOUTH_BREAK_MAX_MM == pytest.approx(brk)
    span = (
        geometry.THICKNESS_OVER_ARM - geometry.THICKNESS_OVER_ARM_BAND
        - 2.0 * geometry.LOCATOR_MOUTH_BREAK_MAX_MM
    )
    assert geometry.LOCATOR_FULL_CYLINDER_SPAN_MIN_MM == pytest.approx(span)
    assert geometry.LOCATOR_MOUTH_POSITION_RADIUS_MM == pytest.approx(
        geometry.REDUCER_POSITION_RADIUS * (1.0 + 2.0 * geometry.LOCATOR_MOUTH_BREAK_MAX_MM / span)
    )
    for index in (1, 2):
        for wall in ("to plate edge/notch", "to countersink", "to running bore"):
            assert geometry.WALLS[f"locator {index} {wall}"][1] >= geometry.WALL_TARGET
    assert "BREAK" not in notes.LOCATOR_NOTE
    assert not hasattr(spec, "LOCATOR_MOUTH_BREAK")


def test_the_screw_hole_callout_states_the_model_countersink() -> None:
    """One hole callout: the drill Ø's native value, then the countersink in
    symbol form at the model's diameter (its printed places) and angle, and
    the screw whose head it seats."""
    callout = drawing.SCREW_HOLE_CALLOUT
    csk = f"{geometry.CSK_DIA / 25.4:.{spec.DRAWING_PRECISION_BY_NAME['CskDia']}f}"
    assert (
        f"<HOLE-SINK><MOD-DIAM>{csk.removeprefix('0')} X {geometry.CSK_ANGLE_DEG:.0f}\u00b0"
        in callout
    )
    assert _config.parts("pd-vn-transgear-arm-plate-screw")["number"] in callout
    assert drawing.CALLOUTS_ABOVE["ScrewHoleDia"] == f"{len(geometry.SCREW_HOLES)}X"
    assert "CskDia" not in drawing.PLAN_KEEP


def test_the_three_place_section_sizes_name_their_function() -> None:
    """Rule 3: a three-place size states its function; the notch depth only
    wraps the arm's edge and prints two places."""
    # The callout names the mate whose screw reach the size sets; its wording
    # is free (Codjiflo, #2148).
    callout = drawing.SECTION_CALLOUTS["ThicknessOverArm"]
    assert _config.parts("pd-transgear-arm")["number"] in callout
    # The value-and-callout block, centred on its text point, stands clear of
    # the hub-to-boss dimension's boss-face witness line (at +6 that line ran
    # through the text: machinist review of ae9ed661a).
    half = _half_width_model("X" * max(map(len, callout.splitlines())))
    assert drawing.SECTION_KEEP["ThicknessOverArm"][2] - half - geometry.BOSS_FACE_Z >= 5.0
    assert spec.DRAWING_PRECISION_BY_NAME["ThicknessOverArm"] == 3
    assert spec.DRAWING_PRECISION_BY_NAME["NotchDepth"] == 2
    assert round(geometry.NOTCH_DEPTH / 25.4, 2) == pytest.approx(geometry.NOTCH_DEPTH / 25.4)


def test_the_plate_screws_engage_the_arm_one_and_a_half_diameters() -> None:
    assert joints.PLATE_SCREW_ENGAGEMENT_WORST_D >= joints.ENGAGEMENT_TARGET_D


def test_the_only_section_cuts_the_plate_on_the_bore_axis() -> None:
    (x0, y0, _), (x1, y1, _) = drawing.KNOB_SECTION_LINE_MODEL
    assert x0 == x1 == 0.0
    assert min(y0, y1) < -geometry.END_R
    assert max(y0, y1) > geometry.arm_upper_edge_y(0.0)
    # D-D carried only the screw hole's projected-zone height (fan-out Q2-A).
    assert not hasattr(drawing, "SCREW_SECTION_LINE_MODEL")


@pytest.mark.parametrize(
    ("linked", "wanted"),
    [
        ("<VLNAME> <VLLABEL>\r\n<VLSCALE><VLSCALEV>", "<VLNAME> <VLLABEL>"),
        ("<VLNAME> <VLLABEL>\r\nSCALE <VLSCALE>", "<VLNAME> <VLLABEL>"),
        ("<VLNAME><VLLABEL><VLSCALEV>", "<VLNAME><VLLABEL>"),
        ("<VLNAME> <VLLABEL>", "<VLNAME> <VLLABEL>"),
    ],
)
def test_section_captions_drop_the_sheet_scale(linked: str, wanted: str) -> None:
    assert drawing.VIEW_SCALE[0] / drawing.VIEW_SCALE[1] == (
        drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1]
    )
    assert drawing._caption_without_scale(linked) == wanted


def test_registry_row_is_the_made_steel_mha_165() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-PD-19"
    assert int(row["quantity"]) == 1
    assert "1018" in row["material_specification"]
    assert str(row["finish"]).strip()
    assert row["tolerance_class"] == "machined_block"


def test_the_build_imports_no_drawing_or_assembly_module() -> None:
    deps = module_deps_of(Path(part.__file__))
    assert not [
        dep
        for dep in deps
        if Path(str(dep)).stem.startswith(("draw_", "build_"))
        and Path(str(dep)).stem != "build_pd_transgear_arm_plate"
    ]


def _loosest_row(places: int, holds) -> bool:
    """``places`` holds its stack and the next looser title-block row does not
    (or there is none: .XX is the inch sheet's loosest): the print asks for no
    more than the part needs."""
    return holds(places) and (places == 2 or not holds(places - 1))


_CONE = math.tan(math.radians(geometry.CSK_ANGLE_DEG / 2.0))


def _screw_seat(csk_places: int, thickness_places: int) -> tuple[float, float]:
    """Actual rounded print rows: published stock bound and true cone floor."""
    _csk_low, csk_high = printed_deviations(geometry.CSK_DIA, csk_places, unit=geometry.UNIT)
    thick_low, thick_high = printed_deviations(
        geometry.THICKNESS_OVER_ARM, thickness_places, unit=geometry.UNIT
    )
    angle = joints.PLATE_SCREW_AXIS_TILT_MAX_RAD
    proud = (
        (screw.STOCK_OVERALL_LENGTH_MIN_MM - screw.HEAD_WHOLE_METAL_HEIGHT_MAX_MM) * math.cos(angle)
        - (screw.HEAD_RADIUS_FROM_THREAD_AXIS_MAX_MM + screw.THREAD_MAJOR / 2.0
           + screw.STOCK_BODY_STRAIGHTNESS_MAX_MM) * math.sin(angle)
        - (geometry.THICKNESS_OVER_ARM + thick_high) - arm.THICKNESS - arm.THICKNESS_BAND
        - joints.PLATE_SCREW_SEAT_HEIGHT_DEBIT_MM
    )
    cone_radius = (geometry.CSK_DIA + csk_high) / 2.0
    alpha = math.radians(arm.DRILL_RUN_OFF_DEG)
    # The plain zone holds each axis over the drilled cylinder (the thinnest
    # stock less the deepest cone); past it the axis runs on at the drill's
    # run-off to the deepest stock's rear face.  The cone and the cylinder
    # it leaves settle together.
    length = geometry.THICKNESS_OVER_ARM + thick_low
    for _ in range(50):
        axis = geometry.SCREW_HOLE_POSITION_RADIUS_MM + max(
            0.0, geometry.THICKNESS_OVER_ARM + thick_high - length
        ) * math.tan(alpha)
        depth = ((cone_radius - geometry.SCREW_HOLE_DIA / 2.0 + 2.0 * axis)
                 / math.tan(geometry.CSK_HALF_ANGLE_LIMITS_RAD[0] - alpha)
                 + cone_radius * math.sin(alpha))
        length = geometry.THICKNESS_OVER_ARM + thick_low - depth
    land = (
        geometry.THICKNESS_OVER_ARM + thick_low - depth
        - geometry.OUTLINE_EDGE_BREAK_MAX_MM  # the hole's exit mouth at face A
    )
    return proud, land


def _seat_holds(csk_places: int, thickness_places: int) -> bool:
    proud, land = _screw_seat(csk_places, thickness_places)
    return (
        proud >= joints.PLATE_SCREW_CUT_PROUD_MAX + screw.POINT_CHAMFER_LENGTH_MAX_MM
        and land >= geometry.WALL_TARGET
    )


def test_the_countersink_and_the_thickness_hold_the_seat_at_their_rows() -> None:
    """The printed rows retain the actual cone floor and published stock cut.
    No incoming crown/length acceptance or cone-centering premise. On the
    inch sheet each nominal's own digits fix its row (.312 head seat, .197
    stock over the arm), so the seat only has to hold at the printed row."""
    csk = spec.DRAWING_PRECISION_BY_NAME["CskDia"]
    thickness = spec.DRAWING_PRECISION_BY_NAME["ThicknessOverArm"]
    assert _seat_holds(csk, thickness)


def test_floor_pays_independent_cone_and_hole_axes_and_actual_rim_tilt() -> None:
    """The plain Ø.014 zone holds each axis (cone and hole, no coaxial
    credit) over the drilled cylinder, face A to the deepest cone's floor
    on the thinnest stock; past it the axis runs on at the drill's run-off
    to the deepest stock's rear face."""
    alpha = math.radians(arm.DRILL_RUN_OFF_DEG)
    rear_face_max = geometry.THICKNESS_OVER_ARM + geometry.THICKNESS_OVER_ARM_BAND
    thinnest = geometry.THICKNESS_OVER_ARM - geometry.THICKNESS_OVER_ARM_BAND
    length = geometry.SCREW_HOLE_ZONE_LENGTH_MIN_MM
    axis = geometry.SCREW_HOLE_POSITION_RADIUS_MM + (rear_face_max - length) * math.tan(alpha)
    assert geometry.SCREW_AXIS_RADIUS_IN_PLATE_MM == pytest.approx(axis)
    assert geometry.screw_axis_radius_mm(0.0) == geometry.SCREW_HOLE_POSITION_RADIUS_MM
    assert geometry.screw_axis_radius_mm(length) == geometry.SCREW_HOLE_POSITION_RADIUS_MM
    with pytest.raises(ValueError):
        geometry.screw_axis_radius_mm(-1.0)
    radius = geometry.CSK_DIA_LIMITS_MM[1] / 2.0
    depth = ((radius - geometry.SCREW_HOLE_DIA / 2.0 + 2.0 * axis)
             / math.tan(geometry.CSK_HALF_ANGLE_LIMITS_RAD[0] - alpha) + radius * math.sin(alpha))
    # The zone's cylinder is what that deepest cone leaves of the thinnest stock.
    assert length == pytest.approx(thinnest - depth)
    floor = (
        geometry.THICKNESS_OVER_ARM - geometry.THICKNESS_OVER_ARM_BAND - depth
        - geometry.OUTLINE_EDGE_BREAK_MAX_MM  # the hole's exit mouth at face A
    )
    assert geometry.WALLS["under the countersinks"][1] == pytest.approx(floor)
    assert floor > geometry.WALL_TARGET
    assert spec.DRAWING_PRECISION_BY_NAME["ThicknessOverArm"] == 3
    assert spec.DRAWING_PRECISION_BY_NAME["CskDia"] == 3


def _notch_air(places: int) -> float:
    """Worst air between the notch face and the arm's lower edge with the
    corner heights at the deviations their printed values allow."""
    rise = max(
        printed_deviations(corner[1], places, unit=geometry.UNIT)[1]
        for corner in (geometry.NOTCH_LEFT, geometry.NOTCH_RIGHT)
    )
    return (
        (geometry.NOTCH_RELIEF - rise) * math.cos(arm.EDGE_LEAN)
        - arm.OUTLINE_BAND
    )


def test_the_notch_corner_heights_print_the_loosest_row_that_clears_the_arm() -> None:
    for name in ("NotchLeftY", "NotchRightY"):
        places = spec.DRAWING_PRECISION_BY_NAME[name]
        assert _loosest_row(places, lambda p: _notch_air(p) > 0.0), name


def test_the_notch_depth_row_holds_the_lock_sweep(
    monkeypatch,
) -> None:
    """The lower section's front face stands proud of the arm by the deepest
    notch; the guide-lock screw heads sweep past it as the platen feeds."""

    def holds(places: int) -> bool:
        monkeypatch.setattr(
            assembly,
            "_NOTCH_DEPTH_DEV",
            printed_deviations(geometry.NOTCH_DEPTH, places, unit=geometry.UNIT),
        )
        try:
            assembly._assert_lock_station_sweep()
        except AssertionError:
            return False
        return True

    assert holds(spec.DRAWING_PRECISION_BY_NAME["NotchDepth"])


def test_the_hub_station_band_holds_the_governing_air_it_closes() -> None:
    """The hub station prints an explicit band, not a title-block row, so no
    row judges it.  It is a term of the collar-to-disc air, not of the
    disc-to-platen air, and that air holds by the governing method at the
    printed band."""
    label, _, band = cluster_fit.PH
    assert band == geometry.HUB_FACE_TO_MOUNTING_BAND
    assert cluster_air.COLLAR_AIR.terms[label] == band
    assert label not in assembly.PLATEN_AIR.terms
    method = assembly.CLUSTER_AIRS["method"]
    assert cluster_air.COLLAR_AIR.air_mm(method) >= cluster_air.COLLAR_AIR_MIN


def test_clamp_availability_is_paid_after_dowel_location() -> None:
    """Reference datum-pose clearance only; actual critical setting is inspected."""
    assert joints.PLATE_SCREW_REFERENCE_ENTRY_MARGIN_MM > 0.0
    assert joints.PLATE_SCREW_STOCK_LEAD_MARGIN_MM > 0.0
    assert knob_shaft.END_FLOAT - knob_shaft.END_FLOAT_SET_TOL > 0.0
    positions = {
        control.key: float(control.tolerance) * 25.4
        for control in spec.GEOMETRIC_CONTROLS if control.characteristic == "position"
    }
    # The dowel reams sit inside K's setting circle; the screw holes, the
    # master the arm's taps are spotted through, at the drilled-hole row.
    for key, zone in positions.items():
        bound = (
            geometry.SCREW_HOLE_POSITION_DIAMETER_MM if key.startswith("plate_hole_")
            else spec.REDUCER_POSITION_DIAMETER
        )
        assert zone <= bound, key


def test_frames_are_plain_at_the_ruled_rows() -> None:
    """Fan-out Q2-A/L1 (delegated ruling 2026-11-07 (Main), no precedent;
    owner review #2144; pending owner confirmation): no projected zone; the
    dowel reams at the reamed-pattern row Ø.004, the screw holes at the
    drilled-hole row Ø.014 (±.005 from the datums), K ⊥ Ø.002 to A."""
    controls = {control.key: control for control in spec.GEOMETRIC_CONTROLS}
    assert all(control.projected_zone_height_mm is None for control in controls.values())
    for index in (1, 2):
        assert controls[f"plate_locator_{index}_position"].tolerance == ".004"
        assert controls[f"plate_hole_{index}_position"].tolerance == ".014"
    knob = controls["knob_axis_perpendicularity"]
    assert (knob.characteristic, knob.tolerance, knob.datums) == ("perpendicularity", ".002", ("A",))
    assert 2.0 * math.hypot(0.005, 0.005) >= 0.014
    # K's tilt over its shortest bore, carried to its projected height, stays
    # inside the reducer axes' tilt budget the air stacks charge.
    bore = geometry.HUB_TO_BOSS - geometry.HUB_TO_BOSS_BAND - 2.0 * geometry.OUTLINE_EDGE_BREAK_MAX_MM
    zone = 0.002 * 25.4 * spec.REGISTRATION.K_PROJECTED_HEIGHT_MM / bore
    assert zone == pytest.approx(spec.KNOB_AXIS_ZONE_AT_PROJECTED_HEIGHT_MM)
    assert zone <= spec.REGISTRATION.AXIS_PROJECTED_ZONE_DIAMETER_MM
    # No tighter than the shop row: .001 per inch of bore, never under .001.
    assert 0.002 >= max(0.001, 0.001 * bore / 25.4)


# Measured on the run 20261001T110844152Z render (2:1 sheet): about 2.65 mm
# of sheet per character of dimension or note text (an upper bound); the
# section caption sits more than 6 model mm under the view (the 7.94 row at
# 5 cleared it, the 29.037 row at 11 did not).
_CHAR_MM = 2.65
_LINE_MODEL = 2.75  # a note line's pitch, model mm at 2:1 (5.5 mm on the sheet)
_CAPTION_CLEAR_MODEL = 6.0
_INNER_BORDER_X = 0.4191  # ASME B landscape inner border, right
_CAPTION_HEIGHT = 0.0035
# The 1:1 isometric's half extents, sheet m: 44 x 52 measured on the r3
# sheet for the 31.75 bar, plus its widening to 38.1 foreshortened (cos 30
# across, sin 30 up).
_ISO_HALF_WIDTH_SHEET = (44.0 + 6.35 * math.cos(math.radians(30.0))) / 2.0 / 1000.0
_ISO_HALF_HEIGHT_SHEET = (52.0 + 6.35 * 0.5) / 2.0 / 1000.0
# The plan and back views centre on the plate's model y extent.
_PLAN_MID_Y = (geometry.TOP_LEFT[1] - geometry.END_R) / 2.0
_GAP = 0.004  # sheet m between neighbouring texts
# The locator callout's shelf runs under its whole text block; the leader
# leaves its right end.  Measured on the round 1 sheet (41ad5cf, layout
# audit): with its text point at x -27.05, the 27-character block's shelf
# ran from model x -45.6 to -7.7 (1.404 model mm a character, centred 0.4
# right of the text point) at 6.45 under the text point with the value and
# three lines under it.  The count line above the value lowers the block's
# foot by half a line pitch (3.22): about 8.06 [estimate until the next
# render].
_SHELF_CHAR_MODEL = (45.6 - 7.7) / 27
_SHELF_CENTRE_OFFSET_MODEL = 0.4
_SHELF_DROP_MODEL = 6.45 + 3.22 / 2.0
# The value with its stacked band reads about 13 characters wide.
_LOCATOR_VALUE_CHARS = 13


def _locator_widest() -> int:
    return max(
        _LOCATOR_VALUE_CHARS,
        len(drawing.PLAN_CALLOUTS_ABOVE["LocatorDia1"]),
        *map(len, drawing.LOCATOR_CALLOUT.splitlines()),
    )


def _locator_shelf_model() -> tuple[float, float, float]:
    """Left end x, right end x and y of the locator callout's shelf, model mm."""
    text_x, text_y, _ = drawing.PLAN_KEEP["LocatorDia1"]
    centre = text_x + _SHELF_CENTRE_OFFSET_MODEL
    half = _locator_widest() * _SHELF_CHAR_MODEL / 2.0
    return centre - half, centre + half, text_y - _SHELF_DROP_MODEL


def _half_width_model(text: str) -> float:
    """Half a text's width in model mm on the 2:1 views."""
    return len(text) * _CHAR_MM / 2.0 / drawing.SHEET_SCALE[0]


def _printed(value: float, name: str) -> str:
    return f"{value:.{spec.DRAWING_PRECISION_BY_NAME[name]}f}"


def test_the_thrust_face_finishes_and_captions_clear_their_face_and_the_diameters() -> None:
    """Outward from each face: its symbol and caption, then its diameter's
    text; the hub's stand outside the hub diameter's witness lines, the
    boss's inside the boss diameter's."""
    for key, face_z, name, value, outward in (
        ("hub_face", geometry.HUB_FACE_Z, "HubDia", geometry.HUB_DIA, -1.0),
        ("boss_face", geometry.BOSS_FACE_Z, "BossDia", geometry.BOSS_DIA, 1.0),
    ):
        _pick, symbol, caption = drawing.FACE_FINISHES[key]
        width = max(map(len, drawing.FACE_FINISH_CAPTIONS[key].splitlines()))
        caption_near = outward * (caption[2] - face_z)
        if outward < 0.0:
            caption_near -= 2.0 * _half_width_model("X" * width)
        caption_far = caption_near + 2.0 * _half_width_model("X" * width)
        assert outward * (symbol[2] - face_z) > 1.0, key
        assert caption_near > 0.5, key
        text = "\u00d8" + _printed(value, name)
        text_near = outward * (drawing.SECTION_KEEP[name][2] - face_z)
        text_near -= _half_width_model(text)
        assert text_near > caption_far, key
    hub_pick, hub_symbol, hub_caption = drawing.FACE_FINISHES["hub_face"]
    assert hub_symbol[1] == hub_pick[1]
    assert hub_caption[1] < -geometry.HUB_DIA / 2.0
    boss_caption = drawing.FACE_FINISHES["boss_face"][2]
    lines = len(drawing.FACE_FINISH_CAPTIONS["boss_face"].splitlines())
    assert boss_caption[1] < geometry.BOSS_DIA / 2.0
    assert boss_caption[1] - lines * _LINE_MODEL > drawing.FACE_FINISHES["boss_face"][1][1]


def test_each_thrust_face_finish_lands_on_its_own_face_annulus() -> None:
    """Each leader meets its face between the bore and the face's diameter,
    so it reads as the face's; each caption names what runs on the face."""
    for key, face_z, face_dia, mate in (
        ("hub_face", geometry.HUB_FACE_Z, geometry.HUB_DIA, "pd-transgear-knob-thrust-ring"),
        ("boss_face", geometry.BOSS_FACE_Z, geometry.BOSS_DIA, "pd-transgear-knob-cup"),
    ):
        pick = drawing.FACE_FINISHES[key][0]
        assert pick[2] == face_z, key
        assert geometry.BORE_DIA / 2.0 + 0.5 < abs(pick[1]) < face_dia / 2.0 - 0.5, key
        caption = drawing.FACE_FINISH_CAPTIONS[key]
        assert caption.startswith("THRUST FACE"), key
        assert caption.endswith(_config.parts(mate)["number"]), key


_PROCESS_LINE_HEADS = ("REAM THRU", "DRILL THRU")


def _word_lines(text: str) -> list[str]:
    """A callout's lines of words: not its size and process lines (the
    hole's REAM / DRILL THRU line, the countersink's form)."""
    return [
        line for line in text.splitlines()
        if not line.startswith(_PROCESS_LINE_HEADS) and "<HOLE-SINK>" not in line
    ]


def test_no_callout_or_caption_prints_more_than_two_lines_of_words() -> None:
    """Rule 7: a callout carries at most two lines of words (machinist
    review, run 20261112T153723793Z: the .197 callout and both thrust-face
    captions printed three).  The spec's three-line strings print re-wrapped,
    every word and drawing number kept in order."""
    printed = {
        **drawing.DIMENSION_CALLOUTS,
        **{f"{key} caption": text for key, text in drawing.FACE_FINISH_CAPTIONS.items()},
    }
    for name, text in printed.items():
        assert 1 <= len(_word_lines(text)) <= 2, name
    sources = {
        drawing.SECTION_CALLOUTS["ThicknessOverArm"]: spec.THICKNESS_CALLOUT,
        **{drawing.FACE_FINISH_CAPTIONS[key]: text for key, text in spec.FINISH_CAPTIONS.items()},
    }
    for wrapped, source in sources.items():
        assert wrapped.split() == source.split(), source


def test_the_hole_height_text_stands_right_of_the_edge() -> None:
    centre = drawing.PLAN_KEEP["ScrewHoleY"][0]
    text = f"[{_printed(geometry.SCREW_HOLES[0][1], 'ScrewHoleY')}]"
    assert geometry.EDGE_PLUS_X < centre - _half_width_model(text)
    assert "TopRightY" in drawing.BACK_KEEP


def _section_sheet_x(z: float) -> float:
    """Sheet x of section A-A's model z (the view centred on its z extent)."""
    mid = (geometry.HUB_FACE_Z + geometry.BOSS_FACE_Z) / 2.0
    return drawing.KNOB_SECTION_CENTER[0] + (z - mid) * drawing.SHEET_SCALE[0] / 1000.0


def _view_sheet_x(centre_x: float, model_x: float, mirrored: bool) -> float:
    """Sheet x of a plan-frame x in the plan (or, mirrored, the back view:
    it looks at the mounting face, so model +X reads to the left)."""
    mid = (geometry.EDGE_MINUS_X + geometry.EDGE_PLUS_X) / 2.0
    offset = (mid - model_x) if mirrored else (model_x - mid)
    return centre_x + offset * drawing.SHEET_SCALE[0] / 1000.0


def _text_half_width_sheet(text: str) -> float:
    return len(text) * _CHAR_MM / 2.0 / 1000.0


def test_the_views_texts_clear_their_neighbours_and_the_border() -> None:
    # Sheet 2: the face-A view's -X-side heights, then section A-A's hub Ø.
    back = drawing.BACK_CENTER[0]
    back_right = max(
        _view_sheet_x(back, drawing.BACK_KEEP[name][0], mirrored=True)
        + _text_half_width_sheet(_printed(value, name))
        for name, value in (
            ("NotchLeftY", geometry.NOTCH_LEFT[1]),
            ("LocatorY1", geometry.LOCATOR_SITES_MM[0][1]),
        )
    )
    hub_text = "\u00d8" + _printed(geometry.HUB_DIA, "HubDia")
    hub_left = _section_sheet_x(
        drawing.SECTION_KEEP["HubDia"][2] - _half_width_model(hub_text)
    )
    assert hub_left - back_right >= _GAP
    # The section's boss Ø ends inside the border.
    boss_text = "\u00d8" + _printed(geometry.BOSS_DIA, "BossDia")
    boss_right = _section_sheet_x(
        drawing.SECTION_KEEP["BossDia"][2] + _half_width_model(boss_text)
    )
    assert _INNER_BORDER_X - boss_right >= 0.002
    # The face-A view's frames: the knob bore's stays inside the border.
    assert drawing.FRAME_XY["knob_axis_perpendicularity"][0] > 0.0125 + 0.004
    # Sheet 1: the plan's right-hand height, then the isometric, which
    # stands clear of the border.
    plan_right = _view_sheet_x(
        drawing.PLAN_CENTER[0], drawing.PLAN_KEEP["ScrewHoleY"][0], mirrored=False
    ) + _text_half_width_sheet(f"[{_printed(geometry.SCREW_HOLES[0][1], 'ScrewHoleY')}]")
    iso_left = drawing.ISO_CENTER[0] - _ISO_HALF_WIDTH_SHEET
    assert iso_left - plan_right >= _GAP
    assert drawing.ISO_CENTER[0] + _ISO_HALF_WIDTH_SHEET <= _INNER_BORDER_X - _GAP
    caption_y = drawing.ISO_NOTE_XY[1]
    assert caption_y - _CAPTION_HEIGHT - (drawing.ISO_CENTER[1] + _ISO_HALF_HEIGHT_SHEET) >= 0.0
    assert caption_y <= 0.266 - 0.004


def test_the_locator_callout_stays_inside_the_border() -> None:
    """Its lines stand under the size, the size under the top border."""
    text_y = (
        drawing.PLAN_CENTER[1]
        + (drawing.PLAN_KEEP["LocatorDia1"][1] - _PLAN_MID_Y) * drawing.SHEET_SCALE[0] / 1000.0
    )
    assert text_y + 0.006 <= 0.266 - 0.002
    left, _right, _y = _locator_shelf_model()
    left_sheet = drawing.PLAN_CENTER[0] + left * drawing.SHEET_SCALE[0] / 1000.0
    assert left_sheet >= 0.0125 + 0.002


def test_the_locator_shelf_ends_left_of_hole_1_witness_line() -> None:
    """Round 1 layout audit (41ad5cf, shoulder-crosses-line): the 27-character
    block's shelf ran right across hole 1's witness line (the .4281's, x
    83.2 mm on the sheet, rising to the row above the shelf).  The shelf now
    ends 2 mm (sheet) short of it."""
    _left, right, shelf_y = _locator_shelf_model()
    witness_x = geometry.SCREW_HOLES[0][0]
    assert witness_x - right >= 2.0 / drawing.SHEET_SCALE[0]
    # The witness line runs up to the -X hole's row, above the shelf.
    assert drawing.PLAN_KEEP["ScrewHoleX1"][1] > shelf_y
    assert max(map(len, drawing.LOCATOR_CALLOUT.splitlines())) <= 21


def test_the_screw_hole_callout_ends_left_of_hole_1_witness_line() -> None:
    """Fan-out round 2 (run 20261107T121559938Z): the .4281's witness line
    rose from hole 1 through the 2X Ø.228 callout's '82°' and screw number.
    Its block (count, value, three lines: the locator block's build, so its
    measured shelf) ends 2 mm (sheet) short of that line, inside the left
    border, its shelf above the -X top corner (the overall height's upper
    witness line) and under the locator callout's shelf."""
    text_x, text_y, _ = drawing.PLAN_KEEP["ScrewHoleDia"]
    printed = drawing.SCREW_HOLE_CALLOUT.replace("<HOLE-SINK>", "V").replace("<MOD-DIAM>", "D")
    widest = max(_LOCATOR_VALUE_CHARS, *map(len, printed.splitlines()))
    half = widest * _SHELF_CHAR_MODEL / 2.0
    left = text_x + _SHELF_CENTRE_OFFSET_MODEL - half
    right = text_x + _SHELF_CENTRE_OFFSET_MODEL + half
    assert geometry.SCREW_HOLES[0][0] - right >= 2.0 / drawing.SHEET_SCALE[0]
    assert drawing.PLAN_CENTER[0] + left * drawing.SHEET_SCALE[0] / 1000.0 >= 0.0125 + 0.002
    assert len(printed.splitlines()) == len(drawing.LOCATOR_CALLOUT.splitlines())
    shelf_y = text_y - _SHELF_DROP_MODEL
    assert shelf_y - geometry.TOP_LEFT[1] >= 2.0 / drawing.SHEET_SCALE[0]
    _locator_left, _locator_right, locator_shelf_y = _locator_shelf_model()
    assert locator_shelf_y - (text_y + _SHELF_DROP_MODEL) >= 2.0 / drawing.SHEET_SCALE[0]
    # The witness line rises past the block to the .4281's row.
    assert drawing.PLAN_KEEP["ScrewHoleX1"][1] > text_y + _SHELF_DROP_MODEL


def test_the_locating_hole_note_stands_under_the_plan_right_of_its_label() -> None:
    """The numbered note's block (top-left at its xy) stands right of the
    REAR VIEW label and the bore's finish symbol (about 12 mm wide), left of
    the title block (x > 0.216 below y 0.066), above the lower border."""
    x, y = drawing.LOCATOR_NOTE_XY
    lines = drawing.LOCATOR_NOTE.splitlines()
    assert max(map(len, lines)) <= notes.LOCATOR_NOTE_WIDTH
    # Rule 7: a note prints at most four lines.
    assert len(lines) <= 4
    width = max(map(len, lines)) * _CHAR_MM / 1000.0
    label_right = drawing.REAR_LABEL_XY[0] + len(spec.REAR_VIEW_LABEL) * _CHAR_MM / 1000.0
    finish_x = drawing.PLAN_CENTER[0] + drawing.BORE_FINISH_MODEL[0] * drawing.SHEET_SCALE[0] / 1000.0
    assert x >= max(label_right + _GAP, finish_x + 0.012)
    assert x + width <= 0.216 - 0.002
    assert y - len(lines) * _LINE_MODEL * drawing.SHEET_SCALE[0] / 1000.0 >= 0.0125 + 0.002
    assert y <= 0.066 - _GAP


def test_the_reamed_hole_leader_crosses_no_plan_dimension_line() -> None:
    """The locator callout's leader runs from its text to locator 1 without
    crossing a location or size dimension line standing above the plan; the
    -X hole's position stands above the leader's start, out of its way and
    off the plate (rule 14)."""
    spans = {
        "ScrewHoleX1": (geometry.SCREW_HOLES[0][0], 0.0),
        "ScrewHoleX2": (geometry.SCREW_HOLES[1][0], 0.0),
        "LocatorX1": (geometry.LOCATOR_SITES_MM[0][0], 0.0),
        "EdgeLeftX": (geometry.EDGE_MINUS_X, 0.0),
        "EdgeRightX": (0.0, geometry.EDGE_PLUS_X),
    }
    _left, start_x, start_y = _locator_shelf_model()
    site_x, site_y = geometry.LOCATOR_SITES_MM[0]
    # Its text (1.8 mm half height) clears the leader's start by a row.
    assert drawing.PLAN_KEEP["ScrewHoleX1"][1] > start_y + 4.0
    checked = 0
    for name, (x0, x1) in spans.items():
        if name not in drawing.PLAN_KEEP:
            continue
        row = drawing.PLAN_KEEP[name][1]
        assert row > geometry.TOP_LEFT[1], name
        assert site_y < row, name
        if row >= start_y:
            continue
        leader_x = start_x + (site_x - start_x) * (start_y - row) / (start_y - site_y)
        assert not min(x0, x1) <= leader_x <= max(x0, x1), name
        checked += 1
    assert checked


def test_section_stations_are_a_baseline_from_the_mounting_face() -> None:
    """Every shoulder station stands above the plate measured from the
    mounting face (z = 0), shortest nearest so no extension line crosses a
    dimension line; the hub-to-boss length stands above them all, and
    nothing stands below the view, over its caption.  The over-arm
    thickness's value and callout stand right of the boss face's witness."""
    keep = drawing.SECTION_KEEP
    stations = {
        "ThicknessOverArm": geometry.REAR_FACE_Z,
        "NotchDepth": geometry.FRONT_FACE_Z,
        "HubFaceToMounting": geometry.HUB_FACE_Z,
    }
    for name, station in stations.items():
        if name == "ThicknessOverArm":
            assert keep[name][2] >= geometry.BOSS_FACE_Z + 12.0, name
        else:
            assert keep[name][2] == pytest.approx(station / 2.0), name
        assert keep[name][1] > geometry.arm_upper_edge_y(0.0), name
    rows = sorted(stations, key=lambda name: keep[name][1])
    assert rows == sorted(stations, key=lambda name: abs(stations[name]))
    assert keep["HubToBoss"][1] > max(keep[name][1] for name in stations)
    assert keep["HubToBoss"][2] == pytest.approx((geometry.HUB_FACE_Z + geometry.BOSS_FACE_Z) / 2.0)
    assert not [name for name, point in keep.items() if point[1] < -geometry.END_R]


def test_each_stacked_callout_fits_its_rows_and_witness_lines() -> None:
    """A callout's lines stand under its value, above the next row's text,
    and between the dimension's own witness lines.  SOLIDWORKS centres the
    value-and-callout block on its position (run 20261028T111221004Z: a third
    callout line raised the hub station's value into the hub-to-boss line)."""
    keep = drawing.SECTION_KEEP

    def half_height(name: str) -> float:
        lines = len(drawing.SECTION_CALLOUTS.get(name, "").splitlines())
        return 0.9 + lines * _LINE_MODEL / 2.0

    for name, below, (left, right) in (
        ("HubFaceToMounting", "NotchDepth", (geometry.HUB_FACE_Z, 0.0)),
        ("HubToBoss", "HubFaceToMounting", (geometry.HUB_FACE_Z, geometry.BOSS_FACE_Z)),
    ):
        text = drawing.SECTION_CALLOUTS[name]
        bottom = keep[name][1] - half_height(name)
        assert bottom - (keep[below][1] + half_height(below)) >= 0.5, name
        half = _half_width_model("X" * max(map(len, text.splitlines())))
        assert left + 0.5 < keep[name][2] - half, name
        assert keep[name][2] + half < right - 0.5, name


def test_the_callouts_name_each_fit_and_the_matched_pair() -> None:
    """The tight bands name their mates with a standard fit; the locating
    holes' callout points at the numbered note that sends their match-drill
    to the MHA-PD-00 view whose native S-K dimension sets the pair (no
    centre distance on this sheet)."""
    import pd_paper_drive_assembly_steps as steps
    import pd_vn_transgear_arm_plate_locating_pin_spec as dowel

    numbers = {
        name: _config.parts(key)["number"]
        for name, key in (
            ("KNOB_SHAFT_NUMBER", "pd-transgear-knob-shaft"),
            ("THRUST_RING_NUMBER", "pd-transgear-knob-thrust-ring"),
            ("KNOB_CUP_NUMBER", "pd-transgear-knob-cup"),
            ("ARM_NUMBER", "pd-transgear-arm"),
            ("DOWEL_NUMBER", "pd-vn-transgear-arm-plate-locating-pin"),
            ("SPROCKET_NUMBER", "pd-transgear-removable"),
        )
    }
    for name, number in numbers.items():
        assert getattr(spec, name) == number, name

    def flat(text: str) -> str:
        return " ".join(text.split())

    bore = flat(spec.BORE_CALLOUT)
    assert "REAM" in bore and "RUNNING FIT" in bore
    assert numbers["KNOB_SHAFT_NUMBER"] in bore
    locator = flat(drawing.LOCATOR_CALLOUT)
    assert drawing.CALLOUTS_ABOVE["LocatorDia1"] == f"{len(geometry.LOCATOR_SITES_MM)}X"
    assert locator.startswith(f"REAM THRU, SEE NOTE {notes.LOCATOR_NOTE_NUMBER}")
    # Rule 7: under the size and process, at most two lines of words.
    assert len(drawing.LOCATOR_CALLOUT.splitlines()) == 3
    assert "LOCATIONAL CLEARANCE FIT ON" in locator
    assert numbers["DOWEL_NUMBER"] in locator
    note = flat(drawing.LOCATOR_NOTE)
    # The REF clearance (in the note) encloses the dowel's limits in the
    # reamed hole; the dowel is named once, on the callout.
    match = re.search(r"\(CLEARANCE (\.\d{4})-(\.\d{4})\)", note)
    assert match, note
    assert numbers["DOWEL_NUMBER"] not in note
    low, high = map(float, match.groups())
    clearance_in = [value / 25.4 for value in dowel.SLIP_DIAMETRAL_CLEARANCE_MM]
    assert 0.0 < low <= clearance_in[0] < low + 1e-4
    assert high - 1e-4 < clearance_in[1] <= high
    assert note.startswith(f"{notes.LOCATOR_NOTE_NUMBER}. ")
    for required in (numbers["ARM_NUMBER"], steps.knob_setting_ref()):
        assert required in note, required
    # The S-K setting's value is DETAIL K's native dimension, not sheet text.
    for text in (locator, note):
        assert f"{disc.CENTRE_DISTANCE:.3f}" not in text
    assert drawing.DIMENSION_CALLOUTS["LocatorDia1"] == drawing.LOCATOR_CALLOUT
    # The hub station names what it sets by drawing number: the knob shaft
    # (its integral 15T) and the chain sprocket on the collar.
    for name in ("KNOB_SHAFT_NUMBER", "SPROCKET_NUMBER"):
        assert numbers[name] in drawing.HUB_STATION_CALLOUT, name
    assert numbers["KNOB_CUP_NUMBER"] in spec.HUB_TO_BOSS_CALLOUT
    assert drawing.DIMENSION_CALLOUTS["HubFaceToMounting"] == drawing.HUB_STATION_CALLOUT
    assert drawing.DIMENSION_CALLOUTS["HubToBoss"] == spec.HUB_TO_BOSS_CALLOUT
    # The locating and screw-hole callouts' widths are bounded by their
    # border and witness-line tests instead.
    widths = [
        text for name, text in drawing.DIMENSION_CALLOUTS.items()
        if name not in ("LocatorDia1", "ScrewHoleDia")
    ]
    for text in (*widths, *drawing.CALLOUTS_ABOVE.values()):
        printed = text.replace("<HOLE-SINK>", "V").replace("<MOD-DIAM>", "D")
        assert all(len(line) <= 24 for line in printed.splitlines()), text
    assert not hasattr(drawing, "NOTES_TEXT")


def test_two_sheets_label_each_face_view() -> None:
    assert spec.SHEET_NAMES == ("REAR FACE", "FACE A")
    assert spec.REAR_VIEW_LABEL == "REAR VIEW"
    assert "FACE A" in spec.FRONT_VIEW_LABEL
    # The countersinks are cut from the rear face, which *Front looks at;
    # *Back looks at face A.
    assert geometry.REAR_FACE_Z > 0.0
    assert drawing.BACK_CENTER[0] < drawing.KNOB_SECTION_CENTER[0]


def test_section_a_a_projects_level_with_the_face_a_view() -> None:
    # Run 20261103T155747207Z machinist review: the section stood 4.2 mm
    # under the view, so its bore axis did not trace across.  Each view
    # centres its own outline: the view's spans the top corner, the
    # section's the top edge at the cut (x = 0).
    scale = drawing.SHEET_SCALE[0] / 1000.0
    view_k = drawing.BACK_CENTER[1] - (drawing._TOP + drawing._BOTTOM) / 2.0 * scale
    section_k = (
        drawing.KNOB_SECTION_CENTER[1]
        - (drawing._SECTION_TOP + drawing._BOTTOM) / 2.0 * scale
    )
    assert section_k == pytest.approx(view_k, abs=1e-9)
    assert drawing._BACK_K[1] == pytest.approx(view_k)


def test_each_2x_group_prints_one_frame_with_its_count() -> None:
    """Machinist screen (clarity, fan-out round 2): one frame for the 2X
    dowel reams and one for the 2X screw holes, each member the same
    control at its own site."""
    groups = drawing.frame_groups()
    assert [(shown, hidden, count) for shown, hidden, count in groups] == [
        ("plate_locator_1_position", ("plate_locator_2_position",), "2X"),
        ("plate_hole_1_position", ("plate_hole_2_position",), "2X"),
    ]
    controls = {control.key: control for control in spec.GEOMETRIC_CONTROLS}
    for shown, hidden, _count in groups:
        for key in hidden:
            assert (controls[key].tolerance, controls[key].datums) == (
                controls[shown].tolerance, controls[shown].datums,
            )
    # The knob bore's own frame stays (RV-02 accepts it).
    assert "knob_axis_perpendicularity" not in {
        key for shown, hidden, _ in groups for key in (shown, *hidden)
    }
    # Each count stands above its shown frame (a 3.5 mm line on a 1 mm
    # gap): the locator's inside the upper border, the hole's under the
    # locator frame (6.9 mm tall).
    count_height = 0.0045
    locator_top = drawing.FRAME_XY["plate_locator_1_position"][1]
    hole_top = drawing.FRAME_XY["plate_hole_1_position"][1]
    assert locator_top + count_height <= 0.2667 - 0.002
    assert hole_top + count_height <= locator_top - 0.0069 - 0.002


class _FakeGtol:
    def __init__(self, accept: bool = True) -> None:
        self.texts: dict[int, str] = {}
        self.accept = accept

    def SetText(self, which: int, text: str) -> bool:  # noqa: N802 - COM name
        if self.accept:
            self.texts[which] = text
        return self.accept

    def GetText(self, which: int) -> str:  # noqa: N802 - COM name
        return self.texts.get(which, "")


class _FakeFrame:
    def __init__(self, gtol: _FakeGtol, *, sticky_visible: bool = False) -> None:
        self._visible = 1
        self.sticky_visible = sticky_visible
        self.gtol = gtol

    @property
    def Visible(self) -> int:  # noqa: N802 - COM name
        return self._visible

    @Visible.setter
    def Visible(self, value: int) -> None:  # noqa: N802 - COM name
        if not self.sticky_visible:
            self._visible = value

    def GetSpecificAnnotation(self) -> _FakeGtol:  # noqa: N802 - COM name
        return self.gtol


def _fake_frames(**overrides: _FakeFrame) -> dict[str, _FakeFrame]:
    keys = [control.key for control in spec.GEOMETRIC_CONTROLS]
    return {key: overrides.get(key, _FakeFrame(_FakeGtol())) for key in keys}


def _patch_com(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    rebuilds: list[str] = []
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(
        drawing, "rebuild_drawing", lambda _adapter, *, label: rebuilds.append(label)
    )
    return rebuilds


def test_one_frame_per_group_hides_repeats_and_reads_the_count_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rebuilds = _patch_com(monkeypatch)
    frames = _fake_frames()
    drawing._one_frame_per_group(object(), frames)
    assert len(rebuilds) == 1
    for shown, hidden, count in drawing.frame_groups():
        assert frames[shown].Visible == 1
        assert frames[shown].gtol.GetText(3) == count
        for key in hidden:
            assert frames[key].Visible == 3
            assert frames[key].gtol.texts == {}
    assert frames["knob_axis_perpendicularity"].Visible == 1
    assert frames["knob_axis_perpendicularity"].gtol.texts == {}


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ("plate_hole_2_position", "did not stay hidden"),
        ("plate_locator_1_position", "was refused"),
    ],
)
def test_one_frame_per_group_fails_on_a_refused_readback(
    monkeypatch: pytest.MonkeyPatch, override: str, message: str
) -> None:
    _patch_com(monkeypatch)
    frame = (
        _FakeFrame(_FakeGtol(), sticky_visible=True)
        if override == "plate_hole_2_position"
        else _FakeFrame(_FakeGtol(accept=False))
    )
    with pytest.raises(RuntimeError, match=message):
        drawing._one_frame_per_group(object(), _fake_frames(**{override: frame}))


def test_the_overall_references_restate_the_outline() -> None:
    """Fan-out round 2 (clarity): the overall width and height print as
    references at the outline's places, measured across the side edges and
    from the -X top corner to the end round's extreme."""
    width = geometry.EDGE_PLUS_X - geometry.EDGE_MINUS_X
    height = geometry.TOP_LEFT[1] + geometry.END_R
    assert spec.OVERALL_WIDTH_MM == pytest.approx(width)
    assert spec.OVERALL_HEIGHT_MM == pytest.approx(height)
    assert spec.DRAWING_REFERENCE_PRECISION == {
        "OverallWidth": geometry.OUTLINE_PLACES, "OverallHeight": geometry.OUTLINE_PLACES,
    }
    assert geometry.TOP_LEFT[1] == max(geometry.TOP_LEFT[1], geometry.TOP_RIGHT[1])
    # The picks sit on the outline the dimensions measure.
    for (x, y, z), (top, notch) in zip(
        drawing.OVERALL_WIDTH_EDGES_MODEL,
        ((geometry.TOP_RIGHT, geometry.NOTCH_RIGHT), (geometry.TOP_LEFT, geometry.NOTCH_LEFT)),
    ):
        assert x == top[0] == notch[0] and notch[1] < y < top[1] and z == 0.0
    assert drawing.OVERALL_HEIGHT_CORNER_MODEL == (
        geometry.EDGE_MINUS_X, geometry.TOP_LEFT[1], geometry.REAR_FACE_Z,
    )
    assert drawing.OVERALL_HEIGHT_ROUND_MODEL == ((0.0, 0.0, geometry.REAR_FACE_Z), geometry.END_R)


def _plan_sheet_x(model_x: float) -> float:
    return _view_sheet_x(drawing.PLAN_CENTER[0], model_x, mirrored=False)


def test_the_overall_references_stand_clear() -> None:
    """The height's text stands left of the top corner's height inside the
    left border; its lower witness line (the end round's extreme, run out
    left) passes over the bore callout's block.  The width stands a row
    under the side widths with the view's label under it, all above the
    lower border."""
    height_text = f"({spec.OVERALL_HEIGHT_MM / 25.4:.2f})"
    x, y, _ = drawing.OVERALL_HEIGHT_TEXT_MODEL
    left = _plan_sheet_x(x) - _text_half_width_sheet(height_text)
    right = _plan_sheet_x(x) + _text_half_width_sheet(height_text)
    assert left >= 0.0125 + 0.002
    top_left_text = _printed(geometry.TOP_LEFT[1], "TopLeftY")
    neighbour = _plan_sheet_x(drawing.PLAN_KEEP["TopLeftY"][0]) - _text_half_width_sheet(top_left_text)
    assert neighbour - right >= _GAP
    assert geometry.KINK[1] < y < geometry.TOP_LEFT[1]
    bore_lines = len(drawing.PLAN_CALLOUTS["BoreDia"].splitlines()) + 1
    bore_top = drawing.PLAN_KEEP["BoreDia"][1] + 0.9 + bore_lines * _LINE_MODEL / 2.0
    assert -geometry.END_R - bore_top >= 2.0 / drawing.SHEET_SCALE[0]
    # The width: 12 mm (sheet) under the side widths' row, the label under
    # its text, the label's line above the lower border.
    scale = drawing.SHEET_SCALE[0] / 1000.0
    widths_y = drawing._BACK_K[1] + drawing.BACK_KEEP["EdgeLeftX"][1] * scale
    width_y = drawing.OVERALL_WIDTH_TEXT_XY[1]
    assert widths_y - width_y >= 0.010
    assert width_y - 0.002 - drawing.FRONT_LABEL_XY[1] >= 0.004
    assert drawing.FRONT_LABEL_XY[1] - 0.004 >= 0.0125 + 0.002
    assert drawing.OVERALL_WIDTH_TEXT_XY[0] == pytest.approx(drawing._BACK_K[0])
