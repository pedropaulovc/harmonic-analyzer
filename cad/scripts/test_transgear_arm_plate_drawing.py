"""Offline contracts for the transgear arm plate (MHA-165) drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_paper_drive_assembly as assembly
import build_transgear_arm_plate as part
import draw_transgear_arm_plate as drawing
import transgear_arm_geometry as arm
import transgear_arm_plate_geometry as geometry
import transgear_arm_plate_screw_spec as screw
import transgear_arm_plate_spec as spec
import transgear_hanger_joints as joints
import transgear_knob_shaft_spec as knob_shaft
import transgear_knob_thrust_ring_spec as ring
from _buildgraph import module_deps_of
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _fit_limits import deviations
from _printed_tolerance import printed_deviations


def _band(places: int) -> float:
    return _config.title_block(f"linear_{places}pl")["value_in"] * 25.4


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/transgear-arm-plate.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/transgear-arm-plate.pdf")
    row = DRAWINGS_BY_NAME["transgear_arm_plate"]
    assert row.script == Path(drawing.__file__).resolve()
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_has_one_view() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    views = (drawing.PLAN_KEEP, drawing.BACK_KEEP, drawing.SECTION_KEEP)
    assert set().union(*views) == marked
    assert sum(len(view) for view in views) == len(marked)
    assert set(drawing.DIMENSION_CALLOUTS) | set(drawing.CALLOUTS_ABOVE) <= marked
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS


def test_the_explicit_bands_are_the_bore_the_knob_float_and_the_hole_positions() -> (
    None
):
    assert model_toleranced_dimensions(part) == {
        ("ScrewHoleProfile", "ScrewHoleX1"): "HOLE_POSITION_TOLERANCE",
        ("ScrewHoleProfile", "ScrewHoleX2"): "HOLE_POSITION_TOLERANCE",
        ("ScrewHoleProfile", "ScrewHoleY"): "HOLE_POSITION_TOLERANCE",
        ("BearingProfile", "HubToBoss"): "HUB_TO_BOSS_TOLERANCE",
        ("BoreProfile", "BoreDia"): "*deviations(BORE_BAND)",
    }
    # The running bore prints the geometry's clearance limits over Ø8.5.
    lower, upper = deviations(spec.BORE_BAND)
    assert (lower, upper) == geometry.BORE_DIA_LIMITS
    assert 0.0 < lower < upper


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
    position = spec.HOLE_POSITION_TOLERANCE * math.sqrt(2.0)
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
    assert row["number"] == "MHA-165"
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
        and Path(str(dep)).stem != "build_transgear_arm_plate"
    ]


def _loosest_row(places: int, holds) -> bool:
    """``places`` holds its stack and the next looser title-block row does not
    (or there is none): the print asks for no more than the part needs."""
    return holds(places) and (places == 1 or not holds(places - 1))


_CONE = math.tan(math.radians(geometry.CSK_ANGLE_DEG / 2.0))


def _screw_seat(csk_places: int, thickness_places: int) -> tuple[float, float]:
    """(shortest stock screw's stand past the arm, land under the cone) with
    the countersink Ø and the thickness over the arm at the deviations their
    printed (rounded) values allow, the head riding its eccentric seat."""
    csk_low, csk_high = printed_deviations(geometry.CSK_DIA, csk_places)
    thick_low, thick_high = printed_deviations(
        geometry.THICKNESS_OVER_ARM, thickness_places
    )
    proud = (
        screw.STOCK_LENGTH
        - screw.STOCK_LENGTH_BAND[1]
        - (geometry.THICKNESS_OVER_ARM + thick_high)
        - (-csk_low) / 2.0 / _CONE  # a small seat holds the head proud
        - joints.PLATE_SCREW_ECCENTRIC_LIFT
        - (arm.THICKNESS + arm.THICKNESS_BAND)
    )
    land = (
        geometry.THICKNESS_OVER_ARM
        + thick_low
        - (geometry.CSK_DIA + csk_high - geometry.SCREW_HOLE_DIA) / 2.0 / _CONE
    )
    return proud, land


def _seat_holds(csk_places: int, thickness_places: int) -> bool:
    proud, land = _screw_seat(csk_places, thickness_places)
    return (
        proud >= joints.PLATE_SCREW_CUT_PROUD_MAX + screw.FIRST_THREAD_LOSS
        and land >= geometry.WALL_TARGET
    )


def test_the_countersink_and_the_thickness_print_the_loosest_seat_rows() -> None:
    """The cut-to-fit oval head: a small countersink or a thick plate holds it
    proud (the shortest stock screw must still stand past its cut), a large
    countersink on a thin plate leaves too little land under the cone."""
    csk = spec.DRAWING_PRECISION_BY_NAME["CskDia"]
    thickness = spec.DRAWING_PRECISION_BY_NAME["ThicknessOverArm"]
    assert _loosest_row(csk, lambda places: _seat_holds(places, thickness))
    assert _loosest_row(thickness, lambda places: _seat_holds(csk, places))


def _notch_air(places: int) -> float:
    """Worst air between the notch face and the arm's lower edge with the
    corner heights at the deviations their printed values allow."""
    rise = max(
        printed_deviations(corner[1], places)[1]
        for corner in (geometry.NOTCH_LEFT, geometry.NOTCH_RIGHT)
    )
    return (
        geometry.NOTCH_RELIEF
        - rise
        - geometry.HOLE_POSITION_BAND
        - joints._NOTCH_LEVER * joints._NOTCH_FLOAT
    ) * math.cos(arm.EDGE_LEAN) - arm.BAND_X


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
    judged = _band(spec.HUB_STATION_PLACES)

    def holds(places: int) -> bool:
        return assembly.DISC_PLATEN_AIR_WORST - (_band(places) - judged) >= 0.0

    assert _loosest_row(printed, holds)


def test_the_explicit_bands_are_tighter_only_where_the_title_block_row_fails() -> None:
    """The hub-to-boss band keeps the knob's end float open; the hole
    positions keep the two shanks inside their float over the arm's taps."""
    row = _band(3)

    def end_float_min(band: float) -> float:
        return knob_shaft.END_FLOAT - (
            knob_shaft.JOURNAL_LENGTH_TOL + ring.LENGTH_TOL + band
        )

    assert end_float_min(spec.HUB_TO_BOSS_TOLERANCE) > 0.0
    assert end_float_min(row) <= 0.0

    def pitch_margin(band: float) -> float:
        mismatch = 2.0 * arm.HOLE_POSITION_BAND + 2.0 * band
        return joints.PLATE_SCREW_PITCH_FLOAT - mismatch

    assert pitch_margin(spec.HOLE_POSITION_TOLERANCE) > 0.0
    assert pitch_margin(row) <= 0.0


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
_GAP = 0.004  # sheet m between neighbouring texts


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


def test_the_hole_height_text_stands_between_the_edge_and_the_corner_height() -> None:
    centre = drawing.PLAN_KEEP["ScrewHoleY"][0]
    tol = spec.HOLE_POSITION_TOLERANCE
    text = f"{_printed(geometry.SCREW_HOLES[0][1], 'ScrewHoleY')} \u00b1{tol:.3f}"
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
    # The caption starts right of the over-arm wall and ends inside the border.
    caption_left = drawing.ISO_NOTE_XY[0]
    caption_right = caption_left + len(spec.ISOMETRIC_VIEW_NOTE) * _CHAR_MM / 1000.0
    assert caption_left - _section_sheet_x(geometry.REAR_FACE_Z) >= _GAP
    assert _INNER_BORDER_X - caption_right >= 0.002


def test_the_first_plan_row_clears_the_cutting_line_arrow() -> None:
    arrow_top = (
        geometry.arm_upper_edge_y(0.0)
        + drawing.SECTION_LINE_OVERRUN_MM
        + _SECTION_LABEL_MODEL
    )
    nearest_row = min(
        drawing.PLAN_KEEP[name][1] for name in ("ScrewHoleX1", "ScrewHoleX2", "Width")
    )
    assert nearest_row - _TEXT_BELOW_KEEP_MODEL - arrow_top >= 1.0


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
