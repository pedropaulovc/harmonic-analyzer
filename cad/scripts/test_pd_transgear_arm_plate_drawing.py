"""Offline contracts for the transgear arm plate (MHA-PD-19) drawing."""

from __future__ import annotations

import math
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
import pd_cluster_air as cluster_air
import transgear_cluster_fit as cluster_fit
import transgear_hanger_joints as joints
import pd_transgear_knob_shaft_spec as knob_shaft
from _buildgraph import module_deps_of
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _fit_deviations import deviations
from _printed_tolerance import printed_deviations
from pd_cluster_stack_band import PRINTED_LENGTH_BAND


def _band(places: int) -> float:
    return _config.title_block(f"linear_{places}pl")["value_in"] * 25.4


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-transgear-arm-plate.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-transgear-arm-plate.pdf")
    row = DRAWINGS_BY_NAME["pd_transgear_arm_plate"]
    assert row.script == Path(drawing.__file__).resolve()
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_has_one_view() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
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
    # band and names the collar air it sets (rule 4).
    assert geometry.HUB_FACE_TO_MOUNTING_BAND == PRINTED_LENGTH_BAND
    assert "COLLAR AIR" in " ".join(drawing.SECTION_CALLOUTS["HubFaceToMounting"].split())
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
        ("ThicknessOverArm", geometry.BAND_XX),
        ("HubDia", geometry.BAND_XX),
        ("NotchLeftY", geometry.NOTCH_BAND),
        ("NotchRightY", geometry.NOTCH_BAND),
        ("CskDia", geometry.CSK_DIA_BAND),
        ("HubFaceToMounting", geometry.BAND_XXX),
    ):
        assert judged >= _band(precision[name]), name
    # The explicitly banded dimensions print enough places to show their band.
    for name in ("BoreDia", "HubToBoss", "ScrewHoleX1", "ScrewHoleX2", "ScrewHoleY"):
        assert precision[name] == 3, name


def test_the_worst_case_walls_hold_at_the_printed_bands() -> None:
    """Recompute the thinnest walls from the printed title-block rows, with
    each exposed edge's 0.254 (R.010) break and the drill run-off (full worst case)."""
    drill = _config.title_block("drilled_hole")["plus_mm"]
    brk = geometry.OUTLINE_EDGE_BREAK_MAX_MM
    assert brk == pytest.approx(0.254) and arm.DRILL_RUN_OFF_DEG == 0.3
    bore_r_max = (geometry.BORE_DIA + geometry.BORE_DIA_LIMITS[1]) / 2.0
    hub_wall = (
        geometry.HUB_DIA - _band(spec.DRAWING_PRECISION_BY_NAME["HubDia"])
    ) / 2.0 - bore_r_max - 2.0 * brk
    assert hub_wall >= geometry.WALL_TARGET
    # The P 7.0 zones run from face A into the arm: inside the plate each
    # hole's axis is extrapolated over the deepest stock.
    deepest = geometry.THICKNESS_OVER_ARM + geometry.THICKNESS_OVER_ARM_BAND
    position = spec.REDUCER_POSITION_RADIUS + deepest * (
        2.0 * spec.REDUCER_POSITION_RADIUS / geometry.CLAMP_PLATE_PROJECTED_HEIGHT_MM
    )
    run_off = math.tan(math.radians(arm.DRILL_RUN_OFF_DEG))
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
    # The budget charges the arm's 0.8 for the .X side edge, no less than
    # the title block's printed .X row.
    assert geometry.BAND_X >= _band(1)
    side_wall = (
        to_edge - geometry.CSK_DIA_LIMITS_MM[1] / 2.0 - geometry.BAND_X - position
        - deepest * run_off - 2.0 * brk
    )
    assert geometry.WALLS["countersinks to the side edges"][1] == pytest.approx(side_wall)
    assert side_wall >= geometry.WALL_TARGET


def test_the_countersink_callout_names_no_hole_size() -> None:
    """The callout is fixed text on the countersink's native dimension: a
    hole size typed into it would not follow the drill's native value."""
    assert spec.CSK_CALLOUT.splitlines() == ["82\u00b0 CSK", "COAXIAL WITH", "DRILLED HOLE"]
    assert not any(character.isdigit() for character in spec.CSK_CALLOUT.splitlines()[-1])


def test_the_plate_screws_engage_the_arm_one_and_a_half_diameters() -> None:
    assert joints.PLATE_SCREW_ENGAGEMENT_WORST_D >= joints.ENGAGEMENT_TARGET_D


def test_the_sections_cut_the_whole_plate_on_the_bore_and_hole_axes() -> None:
    (x0, y0, _), (x1, y1, _) = drawing.KNOB_SECTION_LINE_MODEL
    assert x0 == x1 == 0.0
    assert min(y0, y1) < -geometry.END_R
    assert max(y0, y1) > geometry.arm_upper_edge_y(0.0)
    (x0, y0, _), (x1, y1, _) = drawing.SCREW_SECTION_LINE_MODEL
    assert y0 == y1 == geometry.SCREW_HOLES[0][1] == geometry.SCREW_HOLES[1][1]
    assert min(x0, x1) < geometry.EDGE_MINUS_X and max(x0, x1) > geometry.EDGE_PLUS_X


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
    (or there is none): the print asks for no more than the part needs."""
    return holds(places) and (places == 1 or not holds(places - 1))


_CONE = math.tan(math.radians(geometry.CSK_ANGLE_DEG / 2.0))


def _screw_seat(csk_places: int, thickness_places: int) -> tuple[float, float]:
    """Actual rounded print rows: published stock bound and true cone floor."""
    _csk_low, csk_high = printed_deviations(geometry.CSK_DIA, csk_places)
    thick_low, thick_high = printed_deviations(geometry.THICKNESS_OVER_ARM, thickness_places)
    angle = joints.PLATE_SCREW_AXIS_TILT_MAX_RAD
    proud = (
        (screw.STOCK_OVERALL_LENGTH_MIN_MM - screw.HEAD_WHOLE_METAL_HEIGHT_MAX_MM) * math.cos(angle)
        - (screw.HEAD_RADIUS_FROM_THREAD_AXIS_MAX_MM + screw.THREAD_MAJOR / 2.0
           + screw.STOCK_BODY_STRAIGHTNESS_MAX_MM) * math.sin(angle)
        - (geometry.THICKNESS_OVER_ARM + thick_high) - arm.THICKNESS - arm.THICKNESS_BAND
        - joints.PLATE_SCREW_SEAT_HEIGHT_DEBIT_MM
    )
    cone_radius = (geometry.CSK_DIA + csk_high) / 2.0
    alpha = math.atan(geometry.REDUCER_POSITION_DIAMETER / geometry.CLAMP_PLATE_PROJECTED_HEIGHT_MM)
    # The zone runs into the arm: each axis is extrapolated to the rear face.
    axis = geometry.REDUCER_POSITION_RADIUS + (geometry.THICKNESS_OVER_ARM + thick_high) * math.tan(alpha)
    depth = ((cone_radius - geometry.SCREW_HOLE_DIA / 2.0 + 2.0 * axis)
             / math.tan(geometry.CSK_HALF_ANGLE_LIMITS_RAD[0] - alpha)
             + cone_radius * math.sin(alpha))
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


def test_the_countersink_and_the_thickness_print_the_loosest_seat_rows() -> None:
    """Loosest rows retain the actual cone floor and published stock cut.
    No incoming crown/length acceptance or cone-centering premise."""
    csk = spec.DRAWING_PRECISION_BY_NAME["CskDia"]
    thickness = spec.DRAWING_PRECISION_BY_NAME["ThicknessOverArm"]
    assert _loosest_row(csk, lambda places: _seat_holds(places, thickness))
    # The seat alone would accept .X thickness, but the locator dowels'
    # full-cylinder span (LOCATOR_FULL_CYLINDER_SPAN_MIN_MM, hence the S-K
    # mouth position radius) is judged at the .XX band, so the seat only
    # has to hold at the printed row.
    assert _seat_holds(csk, thickness)


def test_floor_pays_independent_extrapolated_cone_and_hole_axes_and_actual_rim_tilt() -> None:
    """The P 7.0 zone runs from face A into the arm, so inside the plate each
    axis (cone and hole, no coaxial credit) is the zone's straight extension:
    the zone radius plus its full tilt over the deepest stock."""
    alpha = math.atan(geometry.REDUCER_POSITION_DIAMETER / geometry.CLAMP_PLATE_PROJECTED_HEIGHT_MM)
    rear_face_max = geometry.THICKNESS_OVER_ARM + geometry.THICKNESS_OVER_ARM_BAND
    axis = geometry.REDUCER_POSITION_RADIUS + rear_face_max * math.tan(alpha)
    assert geometry.SCREW_AXIS_RADIUS_IN_PLATE_MM == pytest.approx(axis)
    assert geometry.screw_axis_radius_mm(0.0) == geometry.REDUCER_POSITION_RADIUS
    with pytest.raises(ValueError):
        geometry.screw_axis_radius_mm(-1.0)
    radius = geometry.CSK_DIA_LIMITS_MM[1] / 2.0
    depth = ((radius - geometry.SCREW_HOLE_DIA / 2.0 + 2.0 * axis)
             / math.tan(geometry.CSK_HALF_ANGLE_LIMITS_RAD[0] - alpha) + radius * math.sin(alpha))
    floor = (
        geometry.THICKNESS_OVER_ARM - geometry.THICKNESS_OVER_ARM_BAND - depth
        - geometry.OUTLINE_EDGE_BREAK_MAX_MM  # the hole's exit mouth at face A
    )
    assert geometry.WALLS["under the countersinks"][1] == pytest.approx(floor)
    assert floor > geometry.WALL_TARGET
    assert spec.DRAWING_PRECISION_BY_NAME["ThicknessOverArm"] == 2
    assert spec.DRAWING_PRECISION_BY_NAME["CskDia"] == 1
    # With the source fillet-clearance drill, the ordinary CSK row now
    # retains the true floor. The old smaller hole required needless precision.
    old_hole_floor = (geometry.THICKNESS_OVER_ARM - geometry.THICKNESS_OVER_ARM_BAND
                      - ((2.0 * radius - 4.5) / 2.0 + geometry.REDUCER_POSITION_DIAMETER)
                      / math.tan(geometry.CSK_HALF_ANGLE_LIMITS_RAD[0] - alpha)
                      - radius * math.sin(alpha))
    assert old_hole_floor < geometry.WALL_TARGET


def _notch_air(places: int) -> float:
    """Worst air between the notch face and the arm's lower edge with the
    corner heights at the deviations their printed values allow."""
    rise = max(
        printed_deviations(corner[1], places)[1]
        for corner in (geometry.NOTCH_LEFT, geometry.NOTCH_RIGHT)
    )
    return (
        (geometry.NOTCH_RELIEF - rise) * math.cos(arm.EDGE_LEAN)
        - arm.BAND_X
    )


def test_the_notch_corner_heights_print_the_loosest_row_that_clears_the_arm() -> None:
    for name in ("NotchLeftY", "NotchRightY"):
        places = spec.DRAWING_PRECISION_BY_NAME[name]
        assert _loosest_row(places, lambda p: _notch_air(p) > 0.0), name


def test_the_notch_depth_prints_the_loosest_row_the_lock_sweep_clears(
    monkeypatch,
) -> None:
    """The lower section's front face stands proud of the arm by the deepest
    notch; the guide-lock screw heads sweep past it as the platen feeds."""

    def holds(places: int) -> bool:
        monkeypatch.setattr(
            assembly,
            "_NOTCH_DEPTH_DEV",
            printed_deviations(geometry.NOTCH_DEPTH, places),
        )
        try:
            assembly._assert_lock_station_sweep()
        except AssertionError:
            return False
        return True

    assert _loosest_row(spec.DRAWING_PRECISION_BY_NAME["NotchDepth"], holds)


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
    assert all(control.tolerance == f"{spec.REDUCER_POSITION_DIAMETER:.3f}"
               for control in spec.GEOMETRIC_CONTROLS if control.characteristic == "position")


def test_the_drill_and_countersink_leaders_lead_to_different_holes() -> None:
    """The drill callout (left) leads to the -X hole, the countersink callout
    (right) to the +X hole: the leaders span disjoint x and cannot cross."""
    drill_hole_x = geometry.SCREW_HOLES[0][0]  # ScrewHoleDia's circle
    csk_hole_x = geometry.SCREW_HOLES[part.CSK_REFERENCE_HOLE][0]
    drill_text_x = drawing.PLAN_KEEP["ScrewHoleDia"][0]
    csk_text_x = drawing.PLAN_KEEP["CskDia"][0]
    assert drill_text_x < drill_hole_x and csk_hole_x < csk_text_x
    drill_reach = drill_hole_x + geometry.SCREW_HOLE_DIA / 2.0
    csk_reach = csk_hole_x - geometry.CSK_DIA / 2.0
    assert drill_reach < csk_reach


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
# The locator callout's leader leaves its text block's lower right, this far
# (model mm) from the kept text point (measured on the r18 sheet, run
# 20261027T192628995Z: the shelf's right end).
_LOCATOR_LEADER_START_MODEL = (16.8, -11.0)


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
        width = max(map(len, spec.FINISH_CAPTIONS[key].splitlines()))
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
    lines = len(spec.FINISH_CAPTIONS["boss_face"].splitlines())
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
        caption = spec.FINISH_CAPTIONS[key]
        assert caption.startswith("THRUST FACE"), key
        assert caption.endswith(_config.parts(mate)["number"]), key


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
    # The knob zone's chain line ends short of the hub Ø's dimension line.
    assert drawing.KNOB_ZONE[1][2] - drawing.SECTION_KEEP["HubDia"][2] >= 2.0
    # The section's boss Ø ends inside the border.
    boss_text = "\u00d8" + _printed(geometry.BOSS_DIA, "BossDia")
    boss_right = _section_sheet_x(
        drawing.SECTION_KEEP["BossDia"][2] + _half_width_model(boss_text)
    )
    assert _INNER_BORDER_X - boss_right >= 0.002
    # The face-A view's frames: the knob bore's stays inside the border.
    assert drawing.FRAME_XY["knob_projected_axis"][0] > 0.0125 + 0.004
    # Sheet 1: the plan's right-hand height, then section D-D and the
    # isometric, which stand clear of the title block and the border.
    plan_right = _view_sheet_x(
        drawing.PLAN_CENTER[0], drawing.PLAN_KEEP["ScrewHoleY"][0], mirrored=False
    ) + _text_half_width_sheet(f"[{_printed(geometry.SCREW_HOLES[0][1], 'ScrewHoleY')}]")
    section_half = (geometry.EDGE_PLUS_X - geometry.EDGE_MINUS_X) / 1000.0
    assert drawing.SCREW_SECTION_CENTER[0] - section_half - plan_right >= _GAP
    assert drawing.SCREW_SECTION_CENTER[0] + section_half <= _INNER_BORDER_X - _GAP
    assert drawing.SCREW_SECTION_CENTER[1] - 0.03 > 0.066
    iso_left = drawing.ISO_CENTER[0] - _ISO_HALF_WIDTH_SHEET
    assert iso_left - plan_right >= _GAP
    assert drawing.ISO_CENTER[0] + _ISO_HALF_WIDTH_SHEET <= _INNER_BORDER_X - _GAP
    iso_bottom = drawing.ISO_CENTER[1] - _ISO_HALF_HEIGHT_SHEET
    assert iso_bottom - drawing.SCREW_SECTION_CENTER[1] >= 0.03
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
    widest = max(map(len, drawing._locator_callout().splitlines()))
    text_x = _view_sheet_x(
        drawing.PLAN_CENTER[0], drawing.PLAN_KEEP["LocatorDia1"][0], mirrored=False
    )
    assert text_x - _text_half_width_sheet("X" * widest) >= 0.0125 + 0.002


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
    text_x, text_y, _ = drawing.PLAN_KEEP["LocatorDia1"]
    start_x = text_x + _LOCATOR_LEADER_START_MODEL[0]
    start_y = text_y + _LOCATOR_LEADER_START_MODEL[1]
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
    nothing stands below the view, over its caption."""
    keep = drawing.SECTION_KEEP
    stations = {
        "ThicknessOverArm": geometry.REAR_FACE_Z,
        "NotchDepth": geometry.FRONT_FACE_Z,
        "HubFaceToMounting": geometry.HUB_FACE_Z,
    }
    for name, station in stations.items():
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
    """The tight bands name their mates; the locating holes point at the
    MHA-PD-00 view whose native S-K dimension sets the matched pair (no
    sheet notes, no centre distance on this sheet)."""
    import pd_paper_drive_assembly_steps as steps

    numbers = {
        name: _config.parts(key)["number"]
        for name, key in (
            ("KNOB_SHAFT_NUMBER", "pd-transgear-knob-shaft"),
            ("THRUST_RING_NUMBER", "pd-transgear-knob-thrust-ring"),
            ("KNOB_CUP_NUMBER", "pd-transgear-knob-cup"),
            ("ARM_NUMBER", "pd-transgear-arm"),
            ("DOWEL_NUMBER", "pd-vn-transgear-arm-plate-locating-pin"),
        )
    }
    for name, number in numbers.items():
        assert getattr(spec, name) == number, name

    def flat(text: str) -> str:
        return " ".join(text.split())

    bore = flat(spec.BORE_CALLOUT)
    assert "REAM" in bore and "RUNNING FIT" in bore
    assert numbers["KNOB_SHAFT_NUMBER"] in bore
    locator = flat(drawing._locator_callout())
    assert locator.startswith("2X REAM THRU") and "SLIP FIT" in locator
    for required in (
        numbers["DOWEL_NUMBER"],
        numbers["ARM_NUMBER"],
        steps.knob_setting_ref(),
        "0.05 MAX",
    ):
        assert required in locator, required
    # The S-K setting's value is VIEW K's native dimension, not callout text.
    assert f"{disc.CENTRE_DISTANCE:.3f}" not in locator
    assert drawing.DIMENSION_CALLOUTS["LocatorDia1"] == drawing._locator_callout()
    assert numbers["KNOB_SHAFT_NUMBER"] in spec.HUB_STATION_CALLOUT
    assert numbers["KNOB_CUP_NUMBER"] in spec.HUB_TO_BOSS_CALLOUT
    assert drawing.DIMENSION_CALLOUTS["HubFaceToMounting"] == spec.HUB_STATION_CALLOUT
    assert drawing.DIMENSION_CALLOUTS["HubToBoss"] == spec.HUB_TO_BOSS_CALLOUT
    for text in (*drawing.DIMENSION_CALLOUTS.values(), *drawing.CALLOUTS_ABOVE.values()):
        assert all(len(line) <= 23 for line in text.splitlines()), text
    assert not hasattr(drawing, "NOTES_TEXT")


def test_each_projected_zone_is_a_chain_line_from_face_a() -> None:
    """ASME Y14.5-2018 §6.4.7: each zone drawn from face A along its
    feature's axis for its frame's height: the knob bore's toward the hub
    (-Z), just off the axis; each screw hole's on its axis, out of face A
    into the mating arm (-Z), outside the plate and clear of its hatching,
    the axis's centre line continuing it through the plate."""
    heights = {
        control.key: control.projected_zone_height_mm
        for control in spec.GEOMETRIC_CONTROLS
        if control.projected_zone_height_mm is not None
    }
    assert heights == {
        "plate_hole_1_position": spec.SCREW_ZONE_HEIGHT,
        "plate_hole_2_position": spec.SCREW_ZONE_HEIGHT,
        "knob_projected_axis": spec.KNOB_ZONE_HEIGHT,
    }
    start, end, text = drawing.KNOB_ZONE
    assert start == (0.0, drawing.CHAIN_LINE_OFFSET_MM, 0.0)
    assert end[:2] == start[:2] and end[2] == -spec.KNOB_ZONE_HEIGHT
    assert end[2] < text[2] < geometry.HUB_FACE_Z
    assert drawing.CHAIN_LINE_OFFSET_MM < text[1] < geometry.HUB_DIA / 2.0 - 1.5
    assert drawing.CHAIN_LINE_OFFSET_MM < geometry.BORE_DIA / 2.0
    for (start, end, text), axis, (x, y) in zip(
        drawing.SCREW_ZONES, drawing.SCREW_AXES, geometry.SCREW_HOLES, strict=True
    ):
        assert start == (x, y, 0.0)
        assert end == (x, y, -spec.SCREW_ZONE_HEIGHT)
        assert text[2] < end[2] and abs(text[0] - x) < geometry.SCREW_HOLE_DIA / 2.0
        assert axis == ((x, y, 0.0), (x, y, geometry.REAR_FACE_Z + 1.5))
    # D-D's arrows point down the plan: face A stands up in the section, so
    # the zones rise away from the view's caption.
    first, last = drawing.SCREW_SECTION_LINE_MODEL
    assert first[0] < geometry.EDGE_MINUS_X < geometry.EDGE_PLUS_X < last[0]
    assert spec.DRAWING_REFERENCE_PRECISION == {"KnobZone": 1, "ScrewZone": 1}
    # The chain plane's lower limit narrows with the disc cluster's ±0.02
    # stack terms (#2038), so K's projected height is 40.3, not 40.6.
    assert f"{spec.KNOB_ZONE_HEIGHT:.1f}" == "40.3"
    assert f"{spec.SCREW_ZONE_HEIGHT:.1f}" == "7.0"


def test_two_sheets_label_each_face_view() -> None:
    assert spec.SHEET_NAMES == ("REAR FACE", "FACE A")
    assert spec.REAR_VIEW_LABEL == "REAR VIEW"
    assert "FACE A" in spec.FRONT_VIEW_LABEL
    # The countersinks are cut from the rear face, which *Front looks at;
    # *Back looks at face A.
    assert geometry.REAR_FACE_Z > 0.0
    assert drawing.BACK_CENTER[0] < drawing.KNOB_SECTION_CENTER[0]
