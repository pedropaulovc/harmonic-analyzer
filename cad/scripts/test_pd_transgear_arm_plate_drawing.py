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
import transgear_hanger_joints as joints
import pd_transgear_knob_shaft_spec as knob_shaft
from _buildgraph import module_deps_of
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _fit_deviations import deviations
from _printed_tolerance import printed_deviations


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
        assert drawing.PLAN_KEEP[f"ScrewHoleX{index}"][0] == pytest.approx(x / 2.0)
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
        ("BoreProfile", "BoreDia"): "*deviations(BORE_BAND)",
    }
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
    """Recompute the thinnest walls from the printed title-block rows."""
    drill = _config.title_block("drilled_hole")["plus_mm"]
    bore_r_max = (geometry.BORE_DIA + geometry.BORE_DIA_LIMITS[1]) / 2.0
    hub_wall = (
        geometry.HUB_DIA - _band(spec.DRAWING_PRECISION_BY_NAME["HubDia"])
    ) / 2.0 - bore_r_max
    assert hub_wall >= geometry.WALL_TARGET
    position = spec.REDUCER_POSITION_RADIUS
    for x, y in geometry.SCREW_HOLES:
        centre_gap = math.hypot(x, y) - position
        hole_wall = centre_gap - bore_r_max - (geometry.SCREW_HOLE_DIA + drill) / 2.0
        assert hole_wall >= geometry.WALL_TARGET
    for name, (_nominal, worst) in geometry.WALLS.items():
        assert worst >= geometry.WALL_TARGET, name


def test_the_plate_screws_engage_the_arm_one_and_a_half_diameters() -> None:
    assert joints.PLATE_SCREW_ENGAGEMENT_WORST_D >= joints.ENGAGEMENT_TARGET_D


def test_the_section_cuts_the_whole_plate_on_the_bore_axis() -> None:
    (x0, y0, _), (x1, y1, _) = drawing.SECTION_LINE_MODEL
    assert x0 == x1 == 0.0
    assert min(y0, y1) < -geometry.END_R
    assert max(y0, y1) > geometry.arm_upper_edge_y(0.0)


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
    depth = ((cone_radius - geometry.SCREW_HOLE_DIA / 2.0 + geometry.REDUCER_POSITION_DIAMETER)
             / math.tan(geometry.CSK_HALF_ANGLE_LIMITS_RAD[0] - alpha)
             + cone_radius * math.sin(alpha))
    land = geometry.THICKNESS_OVER_ARM + thick_low - depth
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


def test_floor_pays_independent_projected_cone_and_hole_axes_and_actual_rim_tilt() -> None:
    alpha = math.atan(geometry.REDUCER_POSITION_DIAMETER / geometry.CLAMP_PLATE_PROJECTED_HEIGHT_MM)
    radius = geometry.CSK_DIA_LIMITS_MM[1] / 2.0
    depth = ((radius - geometry.SCREW_HOLE_DIA / 2.0 + geometry.REDUCER_POSITION_DIAMETER)
             / math.tan(geometry.CSK_HALF_ANGLE_LIMITS_RAD[0] - alpha) + radius * math.sin(alpha))
    floor = geometry.THICKNESS_OVER_ARM - geometry.THICKNESS_OVER_ARM_BAND - depth
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


def test_the_hub_station_prints_the_loosest_row_the_disc_platen_air_holds() -> None:
    """The disc-to-platen air was judged at HUB_STATION_PLACES' row."""
    printed = spec.DRAWING_PRECISION_BY_NAME["HubFaceToMounting"]
    judged = _band(geometry.HUB_STATION_PLACES)

    def holds(places: int) -> bool:
        return assembly.DISC_PLATEN_AIR_WORST - (_band(places) - judged) >= 0.0

    assert _loosest_row(printed, holds)


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
# of sheet per character of dimension or note text (an upper bound); a
# horizontal dimension's text reaches 1.6 model mm under its text point; the
# cutting line's arrow and letter reach 2.1 model mm past the line's end; the
# section caption sits more than 6 model mm under the view (the 7.94 row at
# 5 cleared it, the 29.037 row at 11 did not).
_CHAR_MM = 2.65
_TEXT_BELOW_KEEP_MODEL = 1.6
_SECTION_LABEL_MODEL = 2.1
_CAPTION_CLEAR_MODEL = 6.0
_INNER_BORDER_X = 0.4191  # ASME B landscape inner border, right
_TITLE_BLOCK_LEFT_X = 0.216  # the title block's left edge, below y 0.066
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
# (model mm) from the kept text point (measured on the r3 sheet).
_LOCATOR_LEADER_START_MODEL = (7.0, -5.5)


def _half_width_model(text: str) -> float:
    """Half a text's width in model mm on the 2:1 views."""
    return len(text) * _CHAR_MM / 2.0 / drawing.SHEET_SCALE[0]


def _printed(value: float, name: str) -> str:
    return f"{value:.{spec.DRAWING_PRECISION_BY_NAME[name]}f}"


def test_the_thrust_face_finishes_clear_their_face_and_the_diameters() -> None:
    """Face, then the finish symbol, then the Ø text, outward on each side."""
    left, right = drawing.FINISH_SYMBOL_REACH
    for key, face_z, name, value, outward in (
        ("hub_face", geometry.HUB_FACE_Z, "HubDia", geometry.HUB_DIA, -1.0),
        ("boss_face", geometry.BOSS_FACE_Z, "BossDia", geometry.BOSS_DIA, 1.0),
    ):
        _pick, symbol = drawing.FACE_FINISHES[key]
        near, far = sorted(
            (
                outward * (symbol[2] - left - face_z),
                outward * (symbol[2] + right - face_z),
            )
        )
        text = "\u00d8" + _printed(value, name)
        text_near = outward * (drawing.SECTION_KEEP[name][2] - face_z)
        text_near -= _half_width_model(text)
        assert near > 0.0, key
        assert text_near > far, key


def test_each_thrust_face_finish_lands_on_its_own_face_annulus() -> None:
    """Each leader meets its face between the bore and the face's diameter,
    with the symbol level with that point, so it reads as the face's."""
    for key, face_z, face_dia in (
        ("hub_face", geometry.HUB_FACE_Z, geometry.HUB_DIA),
        ("boss_face", geometry.BOSS_FACE_Z, geometry.BOSS_DIA),
    ):
        pick, symbol = drawing.FACE_FINISHES[key]
        assert pick[2] == face_z, key
        assert geometry.BORE_DIA / 2.0 + 0.5 < abs(pick[1]) < face_dia / 2.0 - 0.5, key
        assert symbol[1] == pick[1], key


def test_the_hole_height_text_stands_between_the_edge_and_the_corner_height() -> None:
    centre = drawing.PLAN_KEEP["ScrewHoleY"][0]
    text = f"[{_printed(geometry.SCREW_HOLES[0][1], 'ScrewHoleY')}]"
    half = _half_width_model(text)
    assert geometry.EDGE_PLUS_X < centre - half
    assert centre + half < drawing.PLAN_KEEP["TopRightY"][0]


def _section_sheet_x(z: float) -> float:
    """Sheet x of section A-A's model z (the view centred on its z extent)."""
    mid = (geometry.HUB_FACE_Z + geometry.BOSS_FACE_Z) / 2.0
    return drawing.SECTION_CENTER[0] + (z - mid) * drawing.SHEET_SCALE[0] / 1000.0


def _view_sheet_x(centre_x: float, model_x: float, mirrored: bool) -> float:
    """Sheet x of a plan-frame x in the plan (or, mirrored, the back view:
    it looks at the mounting face, so model +X reads to the left)."""
    mid = (geometry.EDGE_MINUS_X + geometry.EDGE_PLUS_X) / 2.0
    offset = (mid - model_x) if mirrored else (model_x - mid)
    return centre_x + offset * drawing.SHEET_SCALE[0] / 1000.0


def _text_half_width_sheet(text: str) -> float:
    return len(text) * _CHAR_MM / 2.0 / 1000.0


def test_the_views_texts_clear_their_neighbours_and_the_border() -> None:
    back = drawing.BACK_CENTER[0]
    # Plan's right-hand height, then the back view's -X-side notch height.
    top_right = drawing.PLAN_KEEP["TopRightY"][0]
    plan_right = _view_sheet_x(
        drawing.PLAN_CENTER[0], top_right, mirrored=False
    ) + _text_half_width_sheet(_printed(geometry.TOP_RIGHT[1], "TopRightY"))
    notch_right = drawing.BACK_KEEP["NotchRightY"][0]
    back_left = _view_sheet_x(back, notch_right, mirrored=True) - (
        _text_half_width_sheet(_printed(geometry.NOTCH_RIGHT[1], "NotchRightY"))
    )
    assert back_left - plan_right >= _GAP
    # The back view's other notch height, then the section's hub Ø.
    notch_left = drawing.BACK_KEEP["NotchLeftY"][0]
    back_right = _view_sheet_x(back, notch_left, mirrored=True) + (
        _text_half_width_sheet(_printed(geometry.NOTCH_LEFT[1], "NotchLeftY"))
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
    # The matched locator note now lives on sheet 2. The isometric still
    # clears the title block and its caption stays under the edge dimensions.
    assert _TITLE_BLOCK_LEFT_X - (drawing.ISO_CENTER[0] + _ISO_HALF_WIDTH_SHEET) >= _GAP
    edge_text_bottom = (
        drawing.PLAN_CENTER[1]
        + (drawing.BACK_KEEP["EdgeLeftX"][1] - _PLAN_MID_Y) * drawing.SHEET_SCALE[0] / 1000.0
        - _TEXT_BELOW_KEEP_MODEL * drawing.SHEET_SCALE[0] / 1000.0
    )
    caption_y = drawing.ISO_NOTE_XY[1]
    assert edge_text_bottom - caption_y >= 0.002
    assert caption_y - _CAPTION_HEIGHT - (drawing.ISO_CENTER[1] + _ISO_HALF_HEIGHT_SHEET) >= 0.0


def test_the_first_plan_row_clears_the_cutting_line_arrow() -> None:
    arrow_top = (
        geometry.arm_upper_edge_y(0.0)
        + drawing.SECTION_LINE_OVERRUN_MM
        + _SECTION_LABEL_MODEL
    )
    nearest_row = min(
        drawing.PLAN_KEEP[name][1]
        for name in ("ScrewHoleX1", "ScrewHoleX2", "LocatorX1")
    )
    assert nearest_row - _TEXT_BELOW_KEEP_MODEL - arrow_top >= 1.0


def test_the_reamed_hole_leader_crosses_no_plan_dimension_line() -> None:
    """The locator callout's leader runs from its text to locator 1 without
    crossing a location or size dimension line standing above the plan."""
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
    checked = 0
    for name, (x0, x1) in spans.items():
        if name not in drawing.PLAN_KEEP:
            continue
        row = drawing.PLAN_KEEP[name][1]
        assert site_y < row < start_y, name
        leader_x = start_x + (site_x - start_x) * (start_y - row) / (start_y - site_y)
        assert not min(x0, x1) <= leader_x <= max(x0, x1), name
        checked += 1
    assert checked


def test_section_stations_are_a_baseline_from_the_mounting_face() -> None:
    """Every shoulder station stands above the plate measured from the
    mounting face (z = 0), shortest nearest so no extension line crosses a
    dimension line; the overall alone stands below."""
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
    below = [name for name, point in keep.items() if point[1] < -geometry.END_R]
    assert below == ["HubToBoss"]
    assert -geometry.END_R - keep["HubToBoss"][1] < _CAPTION_CLEAR_MODEL



@pytest.mark.parametrize(
    "fault",
    (None, "overlap", "border", "title block", "extent", "attachment",
     "leader", "dangling", "text", "missing note", "view", "section letter",
     "section arrow"),
)
def test_settled_projection_notes_use_native_ink_and_attached_state(
    monkeypatch, fault: str | None,
) -> None:
    """A later rebuild cannot silently overlap or detach the acceptance text."""
    from types import SimpleNamespace

    from _drawing_layout_check import DrawableRegion

    class Note:
        def __init__(self, text, box):
            self.text = text
            self.extent = (box[0], box[1], 0.0, box[2], box[3], 0.0)
            self.attached = 1
            self.leaders = 1
            self.dangling = False

        def GetExtent(self):
            return self.extent

        def GetText(self):
            return self.text

        def GetAnnotation(self):
            return self

        def GetAttachedEntityCount3(self):
            return self.attached

        def GetLeaderCount(self):
            return self.leaders

        def IsDangling(self):
            return self.dangling

    active_sheets = []
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(
            ActivateSheet=lambda name: active_sheets.append(name) or True,
        ),
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(
        drawing, "sheet_region",
        lambda _adapter: DrawableRegion(0.0127, 0.0127, 0.4191, 0.2667),
    )
    sections = tuple(
        SimpleNamespace(
            GetLabel=lambda letter=letter: letter,
            GetTextInfo=lambda y=y: (0.350, y, 0.0, 0.365, y, 0.0),
            GetTextFormat=lambda: SimpleNamespace(
                CharHeight=0.0035, IsHeightSpecifiedInPts=lambda: False,
            ),
        )
        for letter, y in (("B", 0.250), ("C", 0.230))
    )
    native_view = SimpleNamespace(
        GetOutline=lambda: (0.260, 0.160, 0.340, 0.250),
        GetSectionLines=lambda: sections,
    )
    monkeypatch.setattr(drawing, "iter_views", lambda _adapter: (native_view,))
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, _view: "section")
    monkeypatch.setattr(
        drawing, "section_line_segments",
        lambda _adapter, _view: [((0.350, 0.185), (0.365, 0.185))],
    )
    notes = {
        "screw zone": Note(
            spec.SCREW_PROJECTED_ZONE_CALLOUT, (0.014, 0.030, 0.110, 0.060),
        ),
        "knob zone": Note(
            spec.KNOB_PROJECTED_ZONE_CALLOUT, (0.014, 0.110, 0.140, 0.135),
        ),
        "matched pair": Note(
            drawing.LOCATOR_MATCH_TEXT, (0.014, 0.174, 0.150, 0.216),
        ),
        "caption": Note(
            drawing.PROJECTION_CAPTION, (0.014, 0.255, 0.120, 0.263),
        ),
    }
    if fault == "overlap":
        notes["knob zone"].extent = (0.020, 0.180, 0.0, 0.145, 0.210, 0.0)
    elif fault == "border":
        notes["caption"].extent = (0.014, 0.260, 0.0, 0.120, 0.275, 0.0)
    elif fault == "title block":
        notes["screw zone"].extent = (0.225, 0.030, 0.0, 0.350, 0.060, 0.0)
    elif fault == "extent":
        notes["knob zone"].extent = ()
    elif fault == "attachment":
        notes["screw zone"].attached = 0
    elif fault == "leader":
        notes["screw zone"].leaders = 2
    elif fault == "dangling":
        notes["screw zone"].dangling = True
    elif fault == "text":
        notes["matched pair"].text = "native text lost its matched-set acceptance"
    elif fault == "missing note":
        del notes["knob zone"]
    elif fault == "view":
        notes["knob zone"].extent = (0.270, 0.200, 0.0, 0.330, 0.240, 0.0)
    elif fault == "section letter":
        notes["knob zone"].extent = (0.350, 0.244, 0.0, 0.360, 0.251, 0.0)
    elif fault == "section arrow":
        notes["knob zone"].extent = (0.350, 0.180, 0.0, 0.365, 0.190, 0.0)

    if fault is None:
        drawing._assert_projection_notes_clear(adapter, notes)
        assert active_sheets == [drawing.SHEET_NAMES[1]]
    else:
        with pytest.raises(RuntimeError):
            drawing._assert_projection_notes_clear(adapter, notes)


@pytest.mark.parametrize(
    "name, xy_mm, direction",
    [
        (f"plate_hole_{index}_position", xy, 1.0)
        for index, xy in enumerate(geometry.SCREW_HOLES, 1)
    ] + [("knob_projected_axis", (0.0, 0.0), -1.0)],
)
def test_projected_axis_runs_the_real_control_and_projection_path(
    monkeypatch, name: str, xy_mm: tuple[float, float], direction: float,
) -> None:
    """Exercise real control lookup and mm-to-sheet math, not native ink."""
    from types import SimpleNamespace

    import _drawing_projection as projection

    scale = drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1]
    model_to_sheet = lambda xyz: (0.200 + xyz[0] * scale,
                                  0.100 + xyz[2] * scale, 0.0)
    sheet_to_sketch = lambda xyz: (xyz[0] - 0.030, xyz[1] + 0.020, xyz[2])

    class MathPoint:
        def __init__(self, coordinates):
            # double_array supplies a typed pywin32 VARIANT on Windows;
            # its SAFEARRAY payload is .value, not the wrapper itself.
            self.ArrayData = tuple(getattr(coordinates, "value", coordinates))

        def MultiplyTransform(self, transform):
            return MathPoint(transform.apply(self.ArrayData))

    utility = SimpleNamespace(CreatePoint=MathPoint)
    lines = []

    def create_line(*coordinates):
        start = SimpleNamespace(**dict(zip("XYZ", coordinates[:3])))
        end = SimpleNamespace(**dict(zip("XYZ", coordinates[3:])))
        line = SimpleNamespace(
            GetStartPoint2=lambda: start, GetEndPoint2=lambda: end, Color=-1,
        )
        lines.append((tuple(coordinates), line))
        return line

    manager = SimpleNamespace(AddToDB=False, CreateCenterLine=create_line)
    activated, rebuilt = [], []
    adapter = SimpleNamespace(
        swApp=SimpleNamespace(GetMathUtility=lambda: utility),
        currentModel=SimpleNamespace(
            ActivateView=lambda label: activated.append(label) or True,
            ClearSelection2=lambda _all: None, SketchManager=manager,
        ),
        _get_attr_or_call=lambda obj, member: (
            getattr(obj, member)() if callable(getattr(obj, member))
            else getattr(obj, member)
        ),
    )
    view = SimpleNamespace(
        GetSketch=lambda: SimpleNamespace(
            ModelToSketchTransform=SimpleNamespace(apply=sheet_to_sketch),
        ),
        ModelToViewTransform=SimpleNamespace(apply=model_to_sheet),
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, _view: "side-on section")
    monkeypatch.setattr(
        drawing, "rebuild_drawing",
        lambda _adapter, *, label: rebuilt.append(label),
    )
    monkeypatch.setattr(
        projection, "_com_invoke",
        lambda obj, _interface, member, *args: (
            getattr(obj, member)(*args) if callable(getattr(obj, member))
            else getattr(obj, member)
        ),
    )

    drawing._projected_axis_graphic(
        adapter, view, name=name, xy_mm=xy_mm, direction=direction,
    )

    control = next(control for control in spec.GEOMETRIC_CONTROLS if control.key == name)
    assert control.projected_zone_height_mm is not None
    expected = tuple(
        coordinate
        for z_mm in (0.0, direction * control.projected_zone_height_mm)
        for coordinate in sheet_to_sketch(model_to_sheet(
            (xy_mm[0] / 1000.0, xy_mm[1] / 1000.0, z_mm / 1000.0),
        ))
    )
    assert len(lines) == 1
    assert lines[0][0] == pytest.approx(expected)
    assert lines[0][1].Color == 0
    assert manager.AddToDB is False
    assert activated == ["side-on section"]
    assert rebuilt == [f"plate {name} projected axis"]
