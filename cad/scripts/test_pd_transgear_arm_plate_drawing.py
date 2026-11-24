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
import pd_transgear_knob_bush_geometry as bush
import transgear_hanger_joints as joints
import pd_transgear_knob_shaft_spec as knob_shaft
from _buildgraph import module_deps_of
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _fit_deviations import deviations
from _printed_tolerance import edge_break_chamfer_mm, edge_break_radius_mm, printed_deviations


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
    views = (drawing.PLAN_KEEP, drawing.BACK_KEEP, drawing.SIDE_KEEP)
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
def test_plate_outline_and_holes_follow_the_physical_bore_source(
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
    for name in ("REAR_FACE_Z", "PRESS_HOLE_DIA"):
        assert fresh[name] == getattr(geometry, name)
    assert all(worst >= geometry.WALL_TARGET for _, worst in fresh["WALLS"].values())


def test_the_explicit_bands_are_the_press_hole_and_the_hole_positions() -> None:
    """Fit audit 2026-11-23: the press hole and the locating holes print
    their set reamer's size and no band; each is accepted with its mate."""
    assert model_toleranced_dimensions(part) == {}
    # ANALYSIS: what the .4385 set reamer is modelled to cut, +.0005/0
    # (pd_transgear_knob_bush_geometry); the walls are judged at it.
    lower, upper = deviations(spec.PRESS_HOLE_BAND)
    assert (lower, upper) == geometry.PRESS_HOLE_LIMITS
    assert (upper, lower) == bush.PRESS_HOLE_BAND
    assert (lower, upper) == pytest.approx((0.0, 0.0005 * 25.4))
    assert geometry.PRESS_HOLE_DIA == bush.PRESS_HOLE_DIA == pytest.approx(0.4385 * 25.4)
    assert geometry.LOCATOR_HOLE_DIA_MM == pytest.approx(0.1260 * 25.4)


def test_every_printed_band_is_no_wider_than_the_arithmetic_assumed() -> None:
    """The walls and the screw engagement were judged at the geometry
    module's bands; the title-block row each printed place count invokes must
    not be wider."""
    for places, band in spec.BAND_BY_PLACES.items():
        assert band >= _band(places)
    precision = spec.DRAWING_PRECISION_BY_NAME
    for name, judged in (
        ("ThicknessOverArm", geometry.THICKNESS_OVER_ARM_BAND),
        ("CskDia", geometry.CSK_DIA_BAND),
    ):
        assert judged >= _band(precision[name]), name
    # The explicitly banded dimensions print enough places to show their band.
    for name, places in (
        ("PressHoleDia", 4), ("ScrewHoleX1", 4), ("ScrewHoleX2", 4), ("ScrewHoleY", 4),
    ):
        assert precision[name] == places, name


def test_the_worst_case_walls_hold_at_the_printed_bands() -> None:
    """Recompute the thinnest walls from the printed title-block rows, with
    each exposed edge's 0.254 (R.010) break and the drill run-off (full worst case)."""
    drill = geometry.DRILL_GROWTH
    brk = geometry.OUTLINE_EDGE_BREAK_MAX_MM
    assert brk == pytest.approx(0.254) and arm.DRILL_RUN_OFF_DEG == 0.3
    press_r_max = (geometry.PRESS_HOLE_DIA + geometry.PRESS_HOLE_LIMITS[1]) / 2.0
    # The face-A mouth's .015 X 45° lead-in at its .XXX upper limit (.020)
    # governs that mouth over the title block's .010 break.
    chamfer_max = bush.PRESS_HOLE_MOUTH_CHAMFER_MAX
    assert max(geometry.PRESS_HOLE_CHAMFER_LIMITS) == chamfer_max > brk
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
        reach = max(
            # rear face: the countersink's rim and the press hole's mouth
            geometry.CSK_DIA_LIMITS_MM[1] / 2.0 + 2.0 * brk,
            # face A: the drilled hole's mouth and the press hole's chamfer
            (geometry.SCREW_HOLE_DIA + drill) / 2.0 + brk + chamfer_max,
        )
        hole_walls.append(centre_gap - press_r_max - reach - 2.0 * deepest * run_off)
    assert min(hole_walls) == pytest.approx(geometry.WALLS["press hole to countersinks"][1])
    assert min(hole_walls) >= geometry.WALL_TARGET
    # The ligament to the R.49 end round, at face A where the chamfer and the
    # outline's break meet it.
    end_round = (
        geometry.END_R - geometry.OUTLINE_BAND - press_r_max - chamfer_max - brk
        - deepest * run_off
    )
    assert geometry.WALLS["press hole to end round"][1] == pytest.approx(end_round)
    assert end_round >= geometry.WALL_TARGET
    for index, (x, y) in enumerate(geometry.LOCATOR_SITES_MM, 1):
        locator = (
            math.hypot(x, y) - geometry.LOCATOR_MOUTH_POSITION_RADIUS_MM
            - max(geometry.LOCATING_PIN.SLIP_HOLE_LIMITS_MM) / 2.0 - press_r_max
            - geometry.LOCATOR_MOUTH_BREAK_MAX_MM - chamfer_max - 2.0 * deepest * run_off
        )
        assert geometry.WALLS[f"locator {index} to press hole"][1] == pytest.approx(locator)
    for name, (_nominal, worst) in geometry.WALLS.items():
        assert worst >= geometry.WALL_TARGET, name
    # The locator to the outline: the plate's 0.25 break and the run-off
    # through the deepest printed plate, on top of the hole's mouth break.
    deepest = geometry.THICKNESS_OVER_ARM + geometry.THICKNESS_OVER_ARM_BAND
    assert geometry.HOLE_RUN_OFF_MM == pytest.approx(deepest * run_off)
    for index in (1, 2):
        nominal, worst = geometry.WALLS[f"locator {index} to plate edge"]
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
        for wall in ("to plate edge", "to countersink", "to press hole"):
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


def test_the_three_place_thickness_names_its_function() -> None:
    """Rule 3: a three-place size states its function."""
    # The callout names the mate whose screw reach the size sets; its wording
    # is free (Codjiflo, #2148).
    callout = drawing.SIDE_CALLOUTS["ThicknessOverArm"]
    assert _config.parts("pd-transgear-arm")["number"] in callout
    # The value-and-callout block, centred on its text point, stands clear
    # right of the side view's rear face, in the open sheet.
    half = _half_width_model("X" * max(map(len, callout.splitlines())))
    assert drawing.SIDE_KEEP["ThicknessOverArm"][2] - half - geometry.REAR_FACE_Z >= 5.0
    assert spec.DRAWING_PRECISION_BY_NAME["ThicknessOverArm"] == 3


def test_the_plate_screws_engage_the_arm_one_and_a_half_diameters() -> None:
    assert joints.PLATE_SCREW_ENGAGEMENT_WORST_D >= joints.ENGAGEMENT_TARGET_D


def test_the_flat_plate_needs_no_section() -> None:
    """Rule 9: the press hole, the reams and the screw holes are standard
    holes their callouts define; the side view shows the thickness and face A
    edge-on, so the sheet cuts no section."""
    assert not hasattr(drawing, "KNOB_SECTION_LINE_MODEL")
    assert not hasattr(drawing, "SCREW_SECTION_LINE_MODEL")
    assert not hasattr(drawing, "_caption_without_scale")
    assert set(spec.DRAWING_DIMENSIONS) == {
        "PlateOutline", "Plate", "PressHoleProfile", "ScrewHoleProfile",
        "CountersinkReference", "LocatorProfile",
    }


def test_the_press_hole_chamfer_is_the_bushs_and_is_modelled_and_printed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The face-A mouth's .015 X 45° lead-in (#2425): sized by the bush
    geometry, cut natively on the part (its volume in the build's and the
    mass oracle's), and printed in the press hole's callout."""
    assert geometry.PRESS_HOLE_CHAMFER == bush.PRESS_HOLE_MOUTH_CHAMFER == pytest.approx(0.381)
    assert geometry.PRESS_HOLE_CHAMFER_PLACES == bush.PRESS_HOLE_MOUTH_CHAMFER_PLACES == 3
    c, r = geometry.PRESS_HOLE_CHAMFER, geometry.PRESS_HOLE_DIA / 2.0
    # Pappus: the c x c triangle's area about K at its centroid's radius.
    assert geometry.PRESS_HOLE_CHAMFER_VOLUME_MM3 == pytest.approx(math.pi * c * c * (r + c / 3.0))
    assert part.PRESS_HOLE_CHAMFER_VOLUME_MM3 is geometry.PRESS_HOLE_CHAMFER_VOLUME_MM3
    assert ".015 X 45\u00b0 AT FACE A" in drawing.PLAN_CALLOUTS["PressHoleDia"].splitlines()
    chamfered = geometry.nominal_material_properties()["volume_mm3"]
    monkeypatch.setattr(geometry, "PRESS_HOLE_CHAMFER_VOLUME_MM3", 0.0)
    plain = geometry.nominal_material_properties()["volume_mm3"]
    assert plain - chamfered == pytest.approx(math.pi * c * c * (r + c / 3.0))


def test_registry_row_is_the_made_steel_mha_165() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-PD-19"
    assert int(row["quantity"]) == 1
    # #2425: faced to .197 from 1/4 x 1-1/2 flat bar (the bar's width is the
    # outline's).
    assert row["material_specification"] == "1/4 x 1-1/2 1018 CF flat bar"
    assert geometry.WIDTH == pytest.approx(1.5 * 25.4)
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


def test_the_plate_has_no_notch_hub_or_boss() -> None:
    """#2425: the flat plate carries none of the old knob bearing's names;
    the MHA-PD-28 bush owns them."""
    for name in (
        "NOTCH_DEPTH", "THICKNESS_BELOW_ARM", "NOTCH_RELIEF", "notch_face_y", "NOTCH_LEFT",
        "NOTCH_RIGHT", "NOTCH_PLACES", "NOTCH_BAND", "BORE_DIA", "BORE_DIA_LIMITS", "HUB_DIA",
        "HUB_FACE_TO_MOUNTING", "HUB_LENGTH", "HUB_STATION_PLACES",
        "HUB_FACE_TO_MOUNTING_BAND", "BOSS_DIA", "HUB_TO_BOSS", "HUB_TO_BOSS_BAND",
        "BOSS_FACE_Z", "BOSS_HEIGHT", "HUB_FACE_Z", "FRONT_FACE_Z", "BORE_RUN_OFF_MM",
    ):
        assert not hasattr(geometry, name), name
    assert not hasattr(spec, "SURFACE_FINISHES")
    # One body, THICKNESS_OVER_ARM thick, less the press hole and its chamfer.
    mass = geometry.nominal_material_properties()
    assert mass["centre_of_mass_local_mm"][2] == pytest.approx(
        geometry.THICKNESS_OVER_ARM / 2.0, abs=0.01
    )


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
    # K's tilt is the MHA-PD-28 bush bore's frame (RV-02 moved with it).
    assert {control.characteristic for control in controls.values()} == {"position"}
    assert "knob_axis" not in spec.GEOMETRIC_TOLERANCES_IN
    assert 2.0 * math.hypot(0.005, 0.005) >= 0.014


# Measured on the run 20261001T110844152Z render (2:1 sheet): about 2.65 mm
# of sheet per character of dimension or note text (an upper bound); the
# section caption sits more than 6 model mm under the view (the 7.94 row at
# 5 cleared it, the 29.037 row at 11 did not).
_CHAR_MM = 2.65
_LINE_MODEL = 2.75  # a note line's pitch, model mm at 2:1 (5.5 mm on the sheet)
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


_PROCESS_LINE_HEADS = ("REAM THRU", "DRILL THRU")


def _word_lines(text: str) -> list[str]:
    """A callout's lines of words: not its size and process lines (the
    hole's REAM / DRILL THRU line, the countersink's and the chamfer's
    forms)."""
    return [
        line for line in text.splitlines()
        if not line.startswith(_PROCESS_LINE_HEADS) and "<HOLE-SINK>" not in line
        and " X 45\u00b0" not in line
    ]


def test_no_callout_prints_more_than_two_lines_of_words() -> None:
    """Rule 7: a callout carries at most two lines of words (machinist
    review, run 20261112T153723793Z: the .197 callout printed three).  The
    spec holds them as printed (#2657)."""
    for name, text in drawing.DIMENSION_CALLOUTS.items():
        assert 1 <= len(_word_lines(text)) <= 2, name


def test_the_hole_height_text_stands_right_of_the_edge() -> None:
    centre = drawing.PLAN_KEEP["ScrewHoleY"][0]
    text = f"[{_printed(geometry.SCREW_HOLES[0][1], 'ScrewHoleY')}]"
    assert geometry.EDGE_PLUS_X < centre - _half_width_model(text)
    assert "TopRightY" in drawing.BACK_KEEP


def _side_sheet_x(z: float) -> float:
    """Sheet x of the side view's model z (``*Left``: +Z reads to the right;
    the view centred on the plate's z extent)."""
    mid = geometry.THICKNESS_OVER_ARM / 2.0
    return drawing.SIDE_CENTER[0] + (z - mid) * drawing.SHEET_SCALE[0] / 1000.0


def _view_sheet_x(centre_x: float, model_x: float, mirrored: bool) -> float:
    """Sheet x of a plan-frame x in the plan (or, mirrored, the back view:
    it looks at the mounting face, so model +X reads to the left)."""
    mid = (geometry.EDGE_MINUS_X + geometry.EDGE_PLUS_X) / 2.0
    offset = (mid - model_x) if mirrored else (model_x - mid)
    return centre_x + offset * drawing.SHEET_SCALE[0] / 1000.0


def _text_half_width_sheet(text: str) -> float:
    return len(text) * _CHAR_MM / 2.0 / 1000.0


def test_the_views_texts_clear_their_neighbours_and_the_border() -> None:
    # Sheet 2: the face-A view's -X-side heights, then datum A's tag left of
    # the side view, the side view, and its thickness block.
    back = drawing.BACK_CENTER[0]
    back_right = _view_sheet_x(
        back, drawing.BACK_KEEP["LocatorY1"][0], mirrored=True
    ) + _text_half_width_sheet(_printed(geometry.LOCATOR_SITES_MM[0][1], "LocatorY1"))
    datum_a = _side_sheet_x(drawing.DATUM_A_MODEL[2])
    assert datum_a - 0.004 - back_right >= _GAP  # the tag's box, about 8 mm
    assert _side_sheet_x(0.0) - datum_a >= 0.010
    callout = drawing.SIDE_CALLOUTS["ThicknessOverArm"]
    block_right = _side_sheet_x(
        drawing.SIDE_KEEP["ThicknessOverArm"][2]
        + _half_width_model("X" * max(map(len, callout.splitlines())))
    )
    assert _INNER_BORDER_X - block_right >= 0.002
    # The side view stands under the face-A view's frame rows.
    side_top = drawing.SIDE_CENTER[1] + (drawing._TOP - drawing._BOTTOM) / 2.0 * 0.002
    assert min(xy[1] for xy in drawing.FRAME_XY.values()) - 0.007 - side_top >= _GAP
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
    assert x >= label_right + _GAP
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
            ("BUSH_NUMBER", "pd-transgear-knob-bush"),
            ("ARM_NUMBER", "pd-transgear-arm"),
            ("DOWEL_NUMBER", "pd-vn-transgear-arm-plate-locating-pin"),
        )
    }
    for name, number in numbers.items():
        assert getattr(spec, name) == number, name

    def flat(text: str) -> str:
        return " ".join(text.split())

    press = drawing.PLAN_CALLOUTS["PressHoleDia"]
    assert press is notes.PRESS_HOLE_CALLOUT
    assert press.splitlines()[0] == "REAM THRU, BONDED FIT"
    # Reamed with the set reamer: no band, no interference range; the fit
    # rides on the process line and the two lines of words give the
    # three-place chamfer its function (rule 3) and say the mate is turned
    # to this bore, in rule 4's words (its acceptance prints once, on
    # MHA-PD-28).  No necessity reason is printed: it is in the register.
    assert press.splitlines()[2:] == [
        f"CLEARS {numbers['BUSH_NUMBER']} SHOULDER ROOT",
        f"{numbers['BUSH_NUMBER']} IS BONDED IN THIS BORE",
    ]
    for word in ("HOLDS", "KEEPS", "SETS", "FASTENER"):
        assert word not in press, word
    # The chamfer's window: over the bush's root radius, under the leg that
    # still leaves a shoulder land; no two-place value fits inside it.
    low = bush.SHOULDER_ROOT_R_MAX_MM / 25.4
    high = (
        (bush.HUB_DIA / 25.4 - 0.01) - (bush.PRESS_HOLE_DIA + max(bush.PRESS_HOLE_BAND)) / 25.4
    ) / 2.0 - 0.010
    assert low == pytest.approx(0.005) and high == pytest.approx(0.0255, abs=1e-4)
    for nominal in (0.01, 0.02):
        assert not (low <= nominal - 0.01 and nominal + 0.01 <= high), nominal
    assert low <= 0.015 - 0.005 and 0.015 + 0.005 <= high
    assert max(map(len, press.splitlines())) <= 33
    assert "INTERFERENCE" not in press and not re.search(r"\.\d{4}", press)
    locator = flat(drawing.LOCATOR_CALLOUT)
    assert drawing.CALLOUTS_ABOVE["LocatorDia1"] == f"{len(geometry.LOCATOR_SITES_MM)}X"
    assert locator.startswith(f"REAM THRU, SEE NOTE {notes.LOCATOR_NOTE_NUMBER}")
    # Rule 7: under the size and process, at most two lines of words.
    assert len(drawing.LOCATOR_CALLOUT.splitlines()) == 3
    assert f"SLIP ON {numbers['DOWEL_NUMBER']}" in locator
    assert "SLIDES IN, NO SHAKE" in locator
    note = flat(drawing.LOCATOR_NOTE)
    # No clearance range is printed: the dowel is the gauge, named once, on
    # the callout.  The note prints no reason (necessity register N-02).
    assert "CLEARANCE" not in flat(locator + " " + note)
    assert not re.search(r"\.\d{4}", locator + note)
    assert "KEEPS" not in note and "MESH" not in note
    # One scheme: sheet 2's frame says where the holes stand, the note only
    # when they are made; no order of work, no "match-drill".
    assert "DRILL AND REAM AT ASSEMBLY ON ARM" in note
    for word in ("MATCH", "THROUGH", "CLAMPED", "FIRST", "THEN"):
        assert word not in note, word
    locator_frames = [
        c for c in spec.GEOMETRIC_CONTROLS if c.key.startswith("plate_locator_")
    ]
    assert len(locator_frames) == len(geometry.LOCATOR_SITES_MM)
    assert numbers["DOWEL_NUMBER"] not in note
    assert min(dowel.SLIP_DIAMETRAL_CLEARANCE_MM) > 0.0
    assert note.startswith(f"{notes.LOCATOR_NOTE_NUMBER}. ")
    for required in (numbers["ARM_NUMBER"], steps.knob_setting_ref()):
        assert required in note, required
    # The S-K setting's value is DETAIL K's native dimension, not sheet text.
    for text in (locator, note):
        assert f"{disc.CENTRE_DISTANCE:.3f}" not in text
    assert drawing.DIMENSION_CALLOUTS["LocatorDia1"] == drawing.LOCATOR_CALLOUT
    # The locating and screw-hole callouts' widths are bounded by their
    # border and witness-line tests instead.
    widths = [
        text for name, text in drawing.DIMENSION_CALLOUTS.items()
        if name not in ("LocatorDia1", "ScrewHoleDia", "PressHoleDia")
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
    assert drawing.BACK_CENTER[0] < drawing.SIDE_CENTER[0]


def test_the_side_view_projects_level_with_the_face_a_view() -> None:
    # Run 20261103T155747207Z machinist review: a view standing 4.2 mm under
    # the face-A view did not trace across.  Both views centre the same
    # _BOTTOM.._TOP outline, so equal centre heights keep K level.
    assert drawing.SIDE_CENTER[1] == drawing.BACK_CENTER[1]
    scale = drawing.SHEET_SCALE[0] / 1000.0
    view_k = drawing.BACK_CENTER[1] - (drawing._TOP + drawing._BOTTOM) / 2.0 * scale
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
    # The plate carries no frame on its press hole (K's tilt is the bush's).
    assert all(control.characteristic == "position" for control in spec.GEOMETRIC_CONTROLS)
    # Each count stands above its shown frame (a 3.5 mm line on a 1 mm
    # gap): the locator's inside the upper border, the hole's under the
    # locator frame (6.9 mm tall).
    count_height = 0.0045
    locator_top = drawing.FRAME_XY["plate_locator_1_position"][1]
    hole_top = drawing.FRAME_XY["plate_hole_1_position"][1]
    assert locator_top + count_height <= 0.2667 - 0.002
    assert hole_top + count_height <= locator_top - 0.0069 - 0.002


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
    for (x, y, z), (top, kink) in zip(
        drawing.OVERALL_WIDTH_EDGES_MODEL,
        ((geometry.TOP_RIGHT, geometry.KINK_RIGHT), (geometry.TOP_LEFT, geometry.KINK)),
    ):
        assert x == top[0] == kink[0] and kink[1] < y < top[1] and z == 0.0
    assert drawing.OVERALL_HEIGHT_CORNER_MODEL == (
        geometry.EDGE_MINUS_X, geometry.TOP_LEFT[1], geometry.REAR_FACE_Z,
    )
    assert drawing.OVERALL_HEIGHT_ROUND_MODEL == ((0.0, 0.0, geometry.REAR_FACE_Z), geometry.END_R)


def _plan_sheet_x(model_x: float) -> float:
    return _view_sheet_x(drawing.PLAN_CENTER[0], model_x, mirrored=False)


def test_the_overall_references_stand_clear() -> None:
    """The height's text stands left of the top corner's height inside the
    left border; its lower witness line (the end round's extreme, run out
    left) passes over the press-hole callout's block.  The width stands a row
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
    press_lines = len(drawing.PLAN_CALLOUTS["PressHoleDia"].splitlines()) + 1
    press_top = drawing.PLAN_KEEP["PressHoleDia"][1] + 0.9 + press_lines * _LINE_MODEL / 2.0
    assert -geometry.END_R - press_top >= 2.0 / drawing.SHEET_SCALE[0]
    # Its widest line stands inside the left border and its foot above the
    # REAR VIEW label's top.
    widest = max(map(len, drawing.PLAN_CALLOUTS["PressHoleDia"].splitlines()))
    press_x = drawing.PLAN_KEEP["PressHoleDia"][0]
    assert _plan_sheet_x(press_x) - widest * _CHAR_MM / 2.0 / 1000.0 >= 0.0125 + 0.002
    press_foot = drawing.PLAN_CENTER[1] + (
        drawing.PLAN_KEEP["PressHoleDia"][1] - 0.9 - press_lines * _LINE_MODEL / 2.0 - _PLAN_MID_Y
    ) * drawing.SHEET_SCALE[0] / 1000.0
    assert press_foot - (drawing.REAR_LABEL_XY[1] + _CAPTION_HEIGHT) >= 0.0
    # The width: 12 mm (sheet) under the side widths' row, the label under
    # its text, the label's line above the lower border.
    scale = drawing.SHEET_SCALE[0] / 1000.0
    widths_y = drawing._BACK_K[1] + drawing.BACK_KEEP["EdgeLeftX"][1] * scale
    width_y = drawing.OVERALL_WIDTH_TEXT_XY[1]
    assert widths_y - width_y >= 0.010
    assert width_y - 0.002 - drawing.FRONT_LABEL_XY[1] >= 0.004
    assert drawing.FRONT_LABEL_XY[1] - 0.004 >= 0.0125 + 0.002
    assert drawing.OVERALL_WIDTH_TEXT_XY[0] == pytest.approx(drawing._BACK_K[0])


def test_the_plate_declares_one_owner_per_face() -> None:
    import export_features
    from _gtol_face import FaceGeometry

    def plane(normal: tuple[float, float, float], offset_mm: float) -> FaceGeometry:
        point = tuple(value * offset_mm / 1000 for value in normal)
        return FaceGeometry(None, 4001, (*normal, *point), normal, (-1.0, -1.0, -1.0, 1.0, 1.0, 1.0))

    def bore(dia: float, x: float, y: float) -> FaceGeometry:
        r, t = dia / 2, geometry.THICKNESS_OVER_ARM
        box = tuple(v / 1000 for v in (x - r, y - r, 0.0, x + r, y + r, t))
        return FaceGeometry(None, 4002, (x / 1000, y / 1000, 0.0, 0.0, 0.0, 1.0, r / 1000), None, box)

    def cone(half_angle_deg: float, x: float, y: float, r: float) -> FaceGeometry:
        box = tuple(v / 1000 for v in (x - r, y - r, 0.0, x + r, y + r, geometry.THICKNESS_OVER_ARM))
        return FaceGeometry(
            None, 4003, (x / 1000, y / 1000, 0.0, 0.0, 0.0, 1.0, r / 1000, math.radians(half_angle_deg)), None, box
        )

    t = geometry.THICKNESS_OVER_ARM
    faces = {
        "face_a": plane((0.0, 0.0, -1.0), 0.0),
        "rear_face": plane((0.0, 0.0, 1.0), t),
        "outline": plane(drawing._TOP_NORMAL, drawing._TOP_NORMAL[0] * geometry.TOP_LEFT[0] + drawing._TOP_NORMAL[1] * geometry.TOP_LEFT[1]),
        "press_hole": bore(geometry.PRESS_HOLE_DIA, 0.0, 0.0),
    }
    selectors = export_features.feature_selectors("pd_transgear_arm_plate")
    checks = list(faces.items())
    checks += [("outline", plane(drawing._LEFT_TAPER_NORMAL, geometry.END_R))]
    checks += [("outline", bore(2 * geometry.END_R, 0.0, 0.0))]
    checks += [("press_hole", cone(45.0, 0.0, 0.0, 6.0))]
    for index, (x, y) in enumerate(geometry.SCREW_HOLES, 1):
        checks += [(f"screw_hole_{index}", bore(geometry.SCREW_HOLE_DIA, x, y))]
        checks += [(f"screw_hole_{index}", cone(geometry.CSK_ANGLE_DEG / 2, x, y, 4.0))]
    for index, (x, y) in enumerate(geometry.LOCATOR_SITES_MM, 1):
        checks += [(f"locator_{index}", bore(geometry.LOCATOR_HOLE_DIA_MM, x, y))]
    for name, face in checks:
        owners = [
            owner
            for owner, specs in selectors.items()
            if any(selector.matches(face) for selector in specs)
        ]
        assert owners == [name], name


def test_the_plate_feature_bands_are_the_printed_ones() -> None:
    import export_features

    def _in(value: float) -> float:
        return value * 25.4

    f = export_features.requirement_manifest("pd_transgear_arm_plate")["features"]
    assert f["rear_face"]["thickness"] == pytest.approx([_in(0.192), _in(0.202)], abs=1e-3)
    assert f["press_hole"]["dia"] == pytest.approx([_in(0.4385), _in(0.4390)], abs=1e-4)
    assert f["press_hole"]["chamfer_leg"] == pytest.approx([_in(0.010), _in(0.020)])
    assert f["press_hole"]["chamfer_at"] == "face_a" and f["press_hole"]["thru"] is True
    assert f["outline"]["end_r"] == pytest.approx([_in(0.48), _in(0.50)], abs=1e-3)
    assert f["outline"]["edge_left_x"] == pytest.approx([_in(0.74), _in(0.76)], abs=1e-3)
    assert f["outline"]["top_left_y"] == pytest.approx([_in(1.66), _in(1.68)], abs=1e-3)
    assert f["outline"]["top_right_y"] == pytest.approx([_in(1.60), _in(1.62)], abs=1e-3)
    assert f["outline"]["kink_y"] == pytest.approx([_in(0.41), _in(0.43)], abs=1e-3)
    for index in (1, 2):
        hole = f[f"screw_hole_{index}"]
        assert hole["dia"] == pytest.approx([_in(0.228), _in(0.232)], abs=1e-3)
        assert hole["csk_dia"] == pytest.approx([_in(0.307), _in(0.317)], abs=1e-3)
        assert hole["csk_angle_deg"] == [81.0, 83.0] and hole["csk_at"] == "rear_face"
        assert hole["position_dia"] == pytest.approx(_in(0.014))
        locator = f[f"locator_{index}"]
        assert locator["made_at"] == "assembly"
        assert locator["dia"] == pytest.approx([_in(0.1260), _in(0.1265)], abs=1e-4)
        assert locator["position_dia"] == pytest.approx(_in(0.004))
