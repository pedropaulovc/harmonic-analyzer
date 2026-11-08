"""Offline contracts for the oblique-trammel jig's 6061 riser (MHA-CH-06-TL-24)."""

from __future__ import annotations

import inspect
import math
import re

import pytest

import _config
import build_ch_rocker_arm_tl_oblique_riser as part
import ch_rocker_arm_tl_oblique_carrier_spec as carrier_spec
import ch_rocker_arm_tl_oblique_riser_spec as spec
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_strap_spec as strap
import draw_ch_rocker_arm_tl_oblique_riser as drawing
import export_features
from _drawing_contract import model_toleranced_dimensions
from _hole_spec import THREAD_MAJOR_MM
from _inch_wall_limits import WALL_TARGET_MM

STEM = "ch_rocker_arm_tl_oblique_riser"
INCH = 25.4
_STOP_STATIONS = {"Stop1X", "Stop2X", "StopY"}


def _on_inch_grid(value_mm: float, places: int) -> bool:
    inches = value_mm / INCH
    return abs(inches - round(inches, places)) < 1e-9


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def _carrier(xy: tuple[float, float]) -> tuple[float, float]:
    return (xy[0] + spec.BLANK_ORIGIN[0], xy[1] + spec.BLANK_ORIGIN[1])


def _close(a: tuple[float, float], b: tuple[float, float], tol: float) -> bool:
    return math.dist(a, b) <= tol


def test_hole_positions_map_back_to_the_calculator() -> None:
    # Presentation precision must not move the carrier-located model axes.
    tol = 1e-9
    assert len(spec.SCREW_HOLES) == len(trammel.RISER_SCREWS) == 4
    for riser, carrier in zip(spec.SCREW_HOLES, trammel.RISER_SCREWS, strict=True):
        assert _close(_carrier(riser), carrier, tol)
    assert _close(_carrier(spec.HUB_HOLE), trammel.HUB, tol)
    assert _close(_carrier(spec.CL_HOLE), trammel.CL, tol)
    assert _close(_carrier(spec.CR_HOLE), trammel.CR, tol)
    for riser, carrier in zip(
        spec.STOP_PIN_HOLES, spec.STOP_PIN_CARRIER_POINTS, strict=True
    ):
        assert _close(_carrier(riser), carrier, tol)
    features = _features()
    for name, carrier, y_field in (
        *(
            (f"screw_hole_{i}", xy, "width_nominal")
            for i, xy in enumerate(trammel.RISER_SCREWS, start=1)
        ),
        ("hub_hole", trammel.HUB, "width_nominal"),
        ("cl_hole", trammel.CL, "width_nominal"),
        ("cr_hole", trammel.CR, "width_nominal"),
        *(
            (f"stop_hole_{i}", xy, "height_nominal")
            for i, xy in enumerate(spec.STOP_PIN_CARRIER_POINTS, start=1)
        ),
    ):
        feature = features[name]
        exported = (feature["station_nominal"], feature[y_field])
        assert _close(_carrier(exported), carrier, tol), name
        assert feature["thru"] is True


def test_the_model_globals_are_the_spec_stations() -> None:
    g = spec.GLOBALS
    xs = [g[f"Screw{i}X"] for i in range(1, 5)]
    ys = [g["ScrewInnerY"]] * 2 + [g["ScrewOuterY"]] * 2
    assert list(zip(xs, ys, strict=True)) == list(spec.SCREW_HOLES)
    assert (g["HubX"], g["HubY"]) == spec.HUB_HOLE
    assert (g["ClX"], g["ClampY"]) == spec.CL_HOLE
    assert (g["CrX"], g["ClampY"]) == spec.CR_HOLE
    assert [(g["Stop1X"], g["StopY"]), (g["Stop2X"], g["StopY"])] == list(
        spec.STOP_PIN_HOLES
    )
    # The plain sketch circles are the carrier-spotted HUB, CL and CR only:
    # the stop holes are a native #30 wizard feature (actual cut).
    assert [xy for xy, _dia, _n, _d in spec.CIRCLES] == [
        spec.HUB_HOLE,
        spec.CL_HOLE,
        spec.CR_HOLE,
    ]
    assert [dia for _xy, dia, _n, _d in spec.CIRCLES] == [
        spec.HUB_DIA,
        spec.CLAMP_DIA,
        spec.CLAMP_DIA,
    ]


def test_blank_and_holes_are_the_part_sheet() -> None:
    assert spec.THICKNESS == trammel.RISER_THICK
    for name, value in (
        ("BlankLength", spec.BLANK_LENGTH),
        ("BlankWidth", spec.BLANK_WIDTH),
        ("BlankThick", spec.THICKNESS),
        ("ClampDia", spec.CLAMP_DIA),
        ("StopDia", spec.STOP_HOLE_DIA),
        ("Stop1X", spec.STOP_PIN_HOLES[0][0]),
        ("Stop2X", spec.STOP_PIN_HOLES[1][0]),
        ("StopY", spec.STOP_PIN_HOLES[0][1]),
    ):
        assert _on_inch_grid(value, spec.DRAWING_PRECISION_BY_NAME[name]), name
    assert spec.SCREW_SPEC.kind == "clearance" and spec.SCREW_SPEC.size == "#4"
    assert trammel.RISER_SCREW == "#4-40"
    # The literal metric HUB relief passes the in-place product-hole reamer.
    assert spec.HUB_DIA == 12.0
    assert spec.HUB_DIA > strap.HOLE_DIA
    assert part.MATERIAL == "6061 Alloy"


def test_hub_relief_cuts_the_12_mm_drill_and_prints_its_design_nominal() -> None:
    """The owner's literal 12 mm relief stays the model's cut (its reamer
    clearance is the drill's); the inch sheet prints the floored three-place
    design nominal .472 from a blanked reference circle, as the #30 holes do,
    so the DRILLED HOLES +.004/0 band contains the actual drill and every
    exported endpoint is a printed value."""
    assert spec.HUB_DIA_PRINTED == pytest.approx(0.472 * INCH)
    assert _on_inch_grid(spec.HUB_DIA_PRINTED, spec.HUB_PLACES)
    assert spec.DRAWING_PRECISION_BY_NAME["HubDia"] == spec.HUB_PLACES == 3
    assert spec.GLOBALS["HubDia"] == spec.HUB_DIA_PRINTED
    assert spec.GLOBALS["HubCutDia"] == spec.HUB_DIA
    assert spec.CIRCLES[0][2][2] == "HubCutDia" and spec.CIRCLES[0][3][2] == '"HubCutDia"'
    assert spec.DRAWING_DIMENSIONS["HubHoleReference"] == {"HubDia"}
    assert "HubDia" not in spec.DRAWING_DIMENSIONS["HoleProfile"]
    assert "HubCutDia" not in set().union(*spec.DRAWING_DIMENSIONS.values())
    rows = {row[0]: row for row in part._REFERENCE_CIRCLES}
    _sketch, centre, dia, names, drives = rows["HubHoleReference"]
    assert (centre, dia) == (spec.HUB_HOLE, spec.HUB_DIA_PRINTED)
    assert names[2] == "HubDia" and drives == ('"HubX"', '"HubY"', '"HubDia"')
    feature = _features()["hub_hole"]
    lo, hi = feature["dia"]
    assert (lo, hi) == pytest.approx((0.472 * INCH, 0.476 * INCH))
    assert lo <= spec.HUB_DIA <= hi
    assert feature["dia_nominal"] == spec.HUB_DIA_PRINTED
    assert lo > strap.HOLE_DIA
    assert spec.CALLOUTS_BELOW["HubDia"].split("\n")[0] == "12 MM DRILL THRU"


def test_blank_sizes_are_finished_native_dimensions_not_stock() -> None:
    dimensions = {"BlankLength", "BlankWidth", "BlankThick"}
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert dimensions <= marked
    assert not dimensions & spec.REFERENCE_DIMENSIONS
    assert not dimensions & set(spec.CALLOUTS_BELOW)
    for name in dimensions:
        assert spec.DRAWING_PRECISION_BY_NAME[name] in (
            spec.BLANK_PLACES,
            spec.THICKNESS_PLACES,
        ), name
    assert not {
        (feature, name)
        for feature, name in model_toleranced_dimensions(part)
        if name in dimensions
    }


def test_flat_head_sinks_and_countersink_stays_in_the_blank() -> None:
    csk = _features()["screw_hole_1_countersink"]
    assert csk["angle_deg"] == 82.0
    assert csk["dia"][0] >= spec.SCREW_HEAD_DIA_MAX
    assert spec.CSK_DEPTH_MAX < spec.THICKNESS - spec.THICKNESS_BAND
    assert _features()["screw_hole_1"]["dia"][0] > spec.SCREW_BODY_DIA


def test_the_screw_hole_has_one_callout_naming_its_countersink() -> None:
    """Three-place design nominal, actual #30 cutter and unchanged countersink."""
    assert _on_inch_grid(spec.SCREW_DIA_PRINTED, spec.SCREW_DIA_PLACES)
    assert spec.SCREW_DIA_PLACES == spec.DRAWING_PRECISION_BY_NAME["ScrewDia"] == 3
    assert spec.SCREW_DIA_PRINTED == pytest.approx(0.128 * INCH)
    assert spec.SCREW_DRILL == "#30"
    assert spec.SCREW_DRILL_DIA == pytest.approx(0.1285 * INCH)
    assert spec.SCREW_DIA == round(spec.SCREW_DRILL_DIA, 3)
    assert spec.GLOBALS["ScrewDia"] == spec.SCREW_DIA_PRINTED
    lo, hi = _features()["screw_hole_1"]["dia"]
    assert lo <= spec.SCREW_DIA <= hi
    assert (lo, hi) == pytest.approx((0.128 * INCH, 0.132 * INCH))
    assert round(spec.SCREW_DIA / INCH, 3) * INCH > spec.SCREW_DIA
    assert spec.CALLOUTS_ABOVE["ScrewDia"] == "4X"
    rows = spec.CALLOUTS_BELOW["ScrewDia"].split("\n")
    assert rows[0] == "#30 DRILL THRU" and rows[1] == spec.CSK_CALLOUT
    assert "CskDia" not in set().union(*spec.DRAWING_DIMENSIONS.values())


def test_native_cut_readback_requires_both_design_limits() -> None:
    for printed in (spec.SCREW_DIA_PRINTED, spec.STOP_HOLE_DIA):
        lo, hi = printed, printed + spec.DRILLED_BAND[0]
        for diameter in (lo, spec.SCREW_DRILL_DIA, spec.SCREW_DIA, hi):
            part._require_cut_in_printed_band(diameter, printed, "holes")
        for diameter in (lo - 0.001, hi + 0.001):
            with pytest.raises(RuntimeError, match="outside the printed"):
                part._require_cut_in_printed_band(diameter, printed, "holes")


def test_stop_holes_cut_the_actual_30_drill_and_print_the_design_nominal() -> None:
    """The two loose end-stop pin holes follow the screw holes' prior fix: the
    native wizard cuts the actual #30 (.1285); a blanked reference circle on
    stop 2 prints the .128 design nominal under DRILLED HOLES +.004/0."""
    assert spec.STOP_DRILL == spec.SCREW_DRILL == "#30"
    assert spec.STOP_SPEC == spec.SCREW_SPEC
    assert spec.STOP_DIA == spec.SCREW_DIA
    assert spec.STOP_HOLE_DIA == pytest.approx(0.128 * INCH)
    assert spec.GLOBALS["StopDia"] == spec.STOP_HOLE_DIA
    assert spec.DRAWING_PRECISION_BY_NAME["StopDia"] == 3
    assert spec.DRAWING_DIMENSIONS["StopHoles"] == _STOP_STATIONS
    assert spec.DRAWING_DIMENSIONS["StopHoleReference"] == {"StopDia"}
    assert part.REFERENCE_SKETCHES == (
        "ScrewHoleReference",
        "HubHoleReference",
        "StopHoleReference",
    )
    rows = {row[0]: row for row in part._REFERENCE_CIRCLES}
    _sketch, centre, dia, names, drives = rows["StopHoleReference"]
    assert (centre, dia) == (spec.STOP_PIN_HOLES[1], spec.STOP_HOLE_DIA)
    assert names[2] == "StopDia" and drives == ('"Stop2X"', '"StopY"', '"StopDia"')
    for index in (1, 2):
        feature = _features()[f"stop_hole_{index}"]
        lo, hi = feature["dia"]
        assert (lo, hi) == pytest.approx((0.128 * INCH, 0.132 * INCH))
        assert lo <= spec.STOP_DIA <= hi
        assert lo <= spec.SCREW_DRILL_DIA <= hi
        # Loose: the largest supplier pin slips in the smallest hole.
        assert lo > spec.STOP_PIN_DIA_LIMITS[1]
    source = inspect.getsource(part.build)
    assert 'name="StopHoles"' in source and "STOP_SPEC" in source
    assert "SharedCoordinate(0)" in source[source.index('name="StopHoles"') :]
    assert spec.CALLOUTS_ABOVE["StopDia"] == "2X"
    assert spec.CALLOUTS_BELOW["StopDia"].split("\n")[0] == "#30 DRILL THRU"
    assert spec.WALLS_MM["stop 1 to edges"] >= WALL_TARGET_MM
    assert spec.WALLS_MM["stop 2 to edges"] >= WALL_TARGET_MM


def test_hole_locations_are_reference_values_from_the_carrier() -> None:
    """TrammelJig ruling: the carrier-located holes are spotted from TL-21 at
    assembly, so their stations print as parenthesised 2-place references and
    each such callout ends in the location rows (review r7: not a general
    note). The end-stop holes are drilled at ordinary .XX stations that keep
    the title block's band, and their callout names the pins instead."""
    stations = set().union(*spec.DRAWING_DIMENSIONS.values()) - {
        "BlankLength",
        "BlankWidth",
        "BlankThick",
        *spec.HOLE_CALLOUTS,
        *_STOP_STATIONS,
    }
    assert spec.REFERENCE_DIMENSIONS == stations
    assert not _STOP_STATIONS & spec.REFERENCE_DIMENSIONS
    assert all(spec.DRAWING_PRECISION_BY_NAME[n] == 2 for n in stations)
    carrier_number = _config.parts("ch-rocker-arm-tl-oblique-carrier")["number"]
    rows = [f"LOCATE FROM {carrier_number}", "AT ASSEMBLY"]
    assert set(spec.HOLE_CALLOUTS) == {"ScrewDia", "HubDia", "ClampDia", "StopDia"}
    for name in set(spec.HOLE_CALLOUTS) - {"StopDia"}:
        assert spec.CALLOUTS_BELOW[name].split("\n")[-2:] == rows, name
    assert "LOCATE" not in spec.CALLOUTS_BELOW["StopDia"]
    assert spec.DRAWING_NOTES == ""
    assert not any("Location" in p for p in part._SAVED_DRAWING_PROPERTIES)
    for name, feature in _features().items():
        if name.startswith("stop_hole_"):
            assert {"station", "height"} <= set(feature["requirements"]), name
        elif name.endswith("_hole") or re.fullmatch(r"screw_hole_\d", name):
            assert "station" not in feature and "width" not in feature, name


def test_clamp_holes_pass_their_mates_and_meet_the_band_wall_target() -> None:
    """R4: the #9 CL/CR clearances, spotted through TL-21's ordinary #8-32
    taps, keep the .080 target to both self-cut edges with the carrier
    stations' error about the cut's centre. The owner Option B RV-01
    exception (.071 MIN, 2026-11-06) belonged to the retired .257 holes and
    is not carried: no below-target statement or exception remains."""
    lo, _hi = _features()["cl_hole"]["dia"]
    assert lo > THREAD_MAJOR_MM[carrier_spec.CLAMP_THREAD]
    centre = trammel.ARC_CENTRE
    radius = math.dist(trammel.CL, centre)
    hole_r = (spec.CLAMP_DIA + spec.DRILLED_BAND[0]) / 2.0
    error = spec.CLAMP_STATION_ERROR
    inner, outer = spec.CLAMP_BAND_WALLS
    assert inner == pytest.approx(radius - hole_r - error - trammel.RISER_INNER_RADIUS)
    assert outer == pytest.approx(trammel.RISER_OUTER_RADIUS - radius - hole_r - error)
    assert min(inner, outer) >= WALL_TARGET_MM
    assert not any("WALL" in row for row in spec.CALLOUTS_BELOW["ClampDia"].split("\n"))
    riser = _config.parts("ch-rocker-arm-tl-oblique-riser")
    assert not riser.get("machinist_exceptions")
    # The self-cut stays the approved 9/16 cutter on the strap cutter's centres.
    assert trammel.RISER_CUTTER_IN == "9/16"


def test_each_row_count_matches_the_holes_on_that_row() -> None:
    """Review r5: a 2X row height names exactly the two holes on its row, and
    its dimension stands right of the view so the extension line from the
    dimensioned left hole runs through its partner."""
    rows = {
        "ScrewInnerY": [
            xy for xy in spec.SCREW_HOLES if xy[1] == spec.GLOBALS["ScrewInnerY"]
        ],
        "ScrewOuterY": [
            xy for xy in spec.SCREW_HOLES if xy[1] == spec.GLOBALS["ScrewOuterY"]
        ],
        "ClampY": [spec.CL_HOLE, spec.CR_HOLE],
        "StopY": list(spec.STOP_PIN_HOLES),
    }
    all_holes = [
        *spec.SCREW_HOLES,
        spec.HUB_HOLE,
        spec.CL_HOLE,
        spec.CR_HOLE,
        *spec.STOP_PIN_HOLES,
    ]
    assert set(rows) == set(spec.ROW_COUNTS)
    for name, holes in rows.items():
        on_row = [xy for xy in all_holes if xy[1] == spec.GLOBALS[name]]
        assert on_row == holes and len(holes) == 2, name
        assert spec.ROW_COUNTS[name] == "2X"
        assert drawing.PLAN_KEEP[name][0] > spec.BLANK_LENGTH
    assert [xy for xy in all_holes if xy[1] == spec.GLOBALS["HubY"]] == [spec.HUB_HOLE]
    assert "HubY" not in spec.ROW_COUNTS
    assert not set(spec.ROW_COUNTS) & set(spec.CALLOUTS_ABOVE)
    # The ordinary stop row is counted in the drawing, not parenthesised.
    assert "StopY" not in spec.REFERENCE_DIMENSIONS


# Sheet text at the template's height: about 2.05 mm a character, 4.5 mm tall
# (jig-r6 layout audit); the audit wants 2.26 mm of air between texts.
_CHAR_MM, _TEXT_MM, _AIR_MM = 2.05, 4.5, 2.26
_PLAN_SCALE = drawing.VIEW_SCALE[0] / drawing.VIEW_SCALE[1]


def test_row_heights_stand_a_text_width_apart() -> None:
    """jig-r6: the right-hand row heights overprinted each other. Each one-line
    "2X (dd.dd)" clears its neighbour's, and the first clears the outline."""
    names = ["ClampY", "ScrewOuterY", "ScrewInnerY"]
    xs = [drawing.PLAN_KEEP[n][0] * _PLAN_SCALE for n in names]
    assert xs == sorted(xs)
    half = len("2X (00.00)") * _CHAR_MM / 2.0
    assert xs[0] - half - spec.BLANK_LENGTH * _PLAN_SCALE >= _AIR_MM
    assert all(b - a >= 2.0 * half + _AIR_MM for a, b in zip(xs, xs[1:]))
    width_x = drawing.PLAN_KEEP["BlankWidth"][0] * _PLAN_SCALE
    width_text = f"{spec.BLANK_WIDTH:.{spec.DRAWING_PRECISION_BY_NAME['BlankWidth']}f}"
    assert width_x - xs[-1] >= half + len(width_text) * _CHAR_MM / 2.0 + _AIR_MM
    # Each count's text fits between its own extension lines.
    for name in names:
        assert spec.GLOBALS[name] * _PLAN_SCALE > _TEXT_MM + 1.0, name


# Native run 26bb's right-end ink (PDF/PNG crop, paper mm at 1:2): an
# outside row-height text starts 1.5 mm right of its dimension line and its
# shelf ends 15.6 mm right of it; an extension line overshoots its dimension
# line by 1.0 mm; an outside arrow's tail reaches 6.3 mm past the edge it
# points at. The (.64) text sat centred on its own line.
_OUTSIDE_TEXT_LEAD_MM = 1.5
_OUTSIDE_SHELF_END_MM = 15.6
_EXTENSION_OVERSHOOT_MM = 1.0
_ARROW_TAIL_MM = 6.3


def _right_of_outline(name: str) -> float:
    """A right-hand row height's dimension line, paper mm off the outline."""
    return (drawing.PLAN_KEEP[name][0] - spec.BLANK_LENGTH) * _PLAN_SCALE


def test_stop_and_clamp_row_heights_do_not_strike_each_other() -> None:
    """Machinist review of native run 26bb (FIX): the .19 dimension line and
    its stop extension line ran through "2X (.64)", and the (.64) lower arrow
    ran down through "2X .19". The stops' row stands nearest the outline with
    its text on a shelf below the edge; the CL/CR row stands clear of that
    shelf, its centred text clear of the stops' lines."""
    stop_x = _right_of_outline("StopY")
    clamp_x = _right_of_outline("ClampY")
    stop_text = f"2X .{round(spec.GLOBALS['StopY'] / INCH * 100):02d}"
    assert stop_text == "2X .19"
    # The span is too short for the text: it stands outside, below the edge.
    assert spec.GLOBALS["StopY"] * _PLAN_SCALE < _TEXT_MM
    _x, y, _ = drawing.PLAN_KEEP["StopY"]
    assert y * _PLAN_SCALE + _TEXT_MM / 2.0 <= -_AIR_MM
    # Its text clears the right end's extension line (the length's).
    assert stop_x + _OUTSIDE_TEXT_LEAD_MM >= _AIR_MM
    # The CL/CR row's lower arrow tail drops right of the stops' shelf.
    assert clamp_x - (stop_x + _OUTSIDE_SHELF_END_MM) >= _AIR_MM
    # The stops' dimension and extension lines end left of "2X (.64)".
    clamp_half = len("2X (.64)") * _CHAR_MM / 2.0
    assert (clamp_x - clamp_half) - (stop_x + _EXTENSION_OVERSHOOT_MM) >= _AIR_MM
    # The stops' upper arrow tail rises past the stop row into the band of
    # the CL/CR text; it must stand left of that text too (same check), and
    # the CL/CR lower arrow tail stays above the stop callout block.
    stop_block_top = drawing.PLAN_KEEP["StopDia"][1] * _PLAN_SCALE + 2.0 * _TEXT_MM
    assert -_ARROW_TAIL_MM - stop_block_top >= _AIR_MM


def test_stock_width_stands_clear_of_section_a_a() -> None:
    """Shifting the row heights outboard keeps the stock width's text left of
    section A-A, which shows the thickness across at 2:1."""
    plan_left = drawing.PLAN_CENTER[0] * 1000.0 - spec.BLANK_LENGTH * _PLAN_SCALE / 2.0
    width_x = plan_left + drawing.PLAN_KEEP["BlankWidth"][0] * _PLAN_SCALE
    width_text = f"{spec.BLANK_WIDTH / INCH:.2f}".lstrip("0")
    section_scale = drawing.SECTION_SCALE[0] / drawing.SECTION_SCALE[1]
    section_left = drawing.SECTION_CENTER[0] * 1000.0 - spec.THICKNESS * section_scale / 2.0
    assert section_left - (width_x + len(width_text) * _CHAR_MM / 2.0) >= _AIR_MM


# Native run 26bb: the stop block's widest row and shelf spanned 48.7 mm,
# centred on its requested X (237.2-285.9 on paper, only 1.6 mm right of the
# right end's extension line at 237.6).
_STOP_BLOCK_HALF_MM = 24.4


def test_stop_callout_block_stands_below_right_of_stop_two() -> None:
    """The stop holes' block hangs off stop 2 (the reference circle's hole),
    right of every X-stack extension line and left of section A-A, under the
    stops' row-height shelf."""
    x, y, _ = drawing.PLAN_KEEP["StopDia"]
    stop_x, stop_y = spec.STOP_PIN_HOLES[1]
    assert x > spec.BLANK_LENGTH > stop_x and y < drawing.PLAN_KEEP["StopY"][1]
    block_left = (x - spec.BLANK_LENGTH) * _PLAN_SCALE - _STOP_BLOCK_HALF_MM
    block_right = (x - spec.BLANK_LENGTH) * _PLAN_SCALE + _STOP_BLOCK_HALF_MM
    assert block_left >= _AIR_MM + 2.0  # off the length's extension line
    plan_right = drawing.PLAN_CENTER[0] * 1000.0 + spec.BLANK_LENGTH * _PLAN_SCALE / 2.0
    section_scale = drawing.SECTION_SCALE[0] / drawing.SECTION_SCALE[1]
    section_left = drawing.SECTION_CENTER[0] * 1000.0 - spec.THICKNESS * section_scale / 2.0
    assert section_left - (plan_right + block_right) >= _AIR_MM
    assert stop_y > 0.0


def test_x_stack_rows_leave_air_and_the_section_letters_clear() -> None:
    """jig-r6: the X stack's texts stood 0.48 mm apart, CL's text sat on the
    baseline extension, and the section letter sat on HubX's extension."""
    order = (
        "Stop1X",
        "ClX",
        "Screw3X",
        "Screw1X",
        "HubX",
        "Screw2X",
        "Screw4X",
        "CrX",
        "Stop2X",
        "BlankLength",
    )
    rows = [drawing.PLAN_KEEP[n][1] * _PLAN_SCALE for n in order]
    assert all(a - b - _TEXT_MM >= 4.52 for a, b in zip(rows, rows[1:]))
    # Nearest the part first, length last.
    lengths = [spec.GLOBALS[n] for n in order]
    assert lengths == sorted(lengths)
    for name, text in (("Stop1X", ".29"), ("ClX", "(9.11)")):
        right = drawing.PLAN_KEEP[name][0] * _PLAN_SCALE + len(text) * _CHAR_MM / 2.0
        assert right <= -_AIR_MM, name
    # Review r7: the HUB row height's dimension line and arrows ran down
    # through "(9.11)"; its line and its own text stand left of CL's text.
    cl_text_left = (
        drawing.PLAN_KEEP["ClX"][0] * _PLAN_SCALE - len("(9.11)") * _CHAR_MM / 2.0
    )
    hub_x = drawing.PLAN_KEEP["HubY"][0] * _PLAN_SCALE
    assert cl_text_left - (hub_x + len("(29.53)") * _CHAR_MM / 2.0) >= _AIR_MM
    # The arrows point +X; each letter stands 14-20 mm (sheet) past the line.
    cut = drawing.CUT_X * _PLAN_SCALE
    stations = sorted(
        x * _PLAN_SCALE
        for x, _y in (
            *spec.SCREW_HOLES,
            spec.HUB_HOLE,
            spec.CL_HOLE,
            spec.CR_HOLE,
            *spec.STOP_PIN_HOLES,
        )
    )
    assert not [s for s in stations if cut + 12.0 < s < cut + 22.0]
    assert -drawing.CUT_Y[0] * _PLAN_SCALE >= 6.0
    assert (drawing.CUT_Y[1] - spec.BLANK_WIDTH) * _PLAN_SCALE >= 6.0


def test_walls_hold_rule_17_at_worst_case() -> None:
    assert min(spec.WALLS_MM.values()) >= WALL_TARGET_MM
    assert min(trammel.RISER_SCREW_WALLS) >= WALL_TARGET_MM


def test_drilled_holes_carry_the_title_block_band_only() -> None:
    assert model_toleranced_dimensions(part) == {}


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.PLAN_KEEP) | set(drawing.SECTION_KEEP) == marked
    assert not set(drawing.PLAN_KEEP) & set(drawing.SECTION_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert set(spec.CALLOUTS_ABOVE) | set(spec.CALLOUTS_BELOW) <= marked


def test_sheet_carries_no_notes_and_short_callouts() -> None:
    """No general notes; callout rows stay short (the location row, naming the
    carrier's number, is the longest)."""
    assert spec.DRAWING_NOTES == ""
    for text in (*spec.CALLOUTS_ABOVE.values(), *spec.CALLOUTS_BELOW.values()):
        for line in text.split("\n"):
            assert len(line.replace("<MOD-DIAM>", " Ø")) <= 28, line


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-oblique-riser")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)
    assert number == "MHA-CH-06-TL-24"


def test_every_exported_band_endpoint_is_a_printed_value() -> None:
    """Each band endpoint and nominal is a value the inch sheet prints."""
    checked = 0
    for name, feature in _features().items():
        for requirement in feature["requirements"]:
            band = feature.get(requirement)
            if not (isinstance(band, list) and len(band) == 2):
                continue
            places = feature["precision"][requirement]
            for end in band:
                assert _on_inch_grid(end, places), (name, requirement)
            nominal = feature.get(f"{requirement}_nominal")
            if nominal is not None:
                assert band[0] <= nominal <= band[1], (name, requirement)
                assert _on_inch_grid(nominal, places), (name, requirement)
            checked += 1
    assert checked


# The retained 0c3 native/PDF ink below was measured on the 41.148 wide blank.
# The plan view centres on its outline, so the 42.926 blank lifts everything
# above the outline's centre by a quarter of the growth on paper at 1:2.
_RETAINED_0C3_WIDTH = 41.148
_WIDTH_LIFT = (spec.BLANK_WIDTH - _RETAINED_0C3_WIDTH) / 2.0 * _PLAN_SCALE


def test_clamp_callout_has_border_air_and_clears_the_cutting_plane() -> None:
    # Retained 0c3 native/PDF ink, in paper mm at the unchanged 1:2 scale.
    # The old shelf started at 13.0891 against the 12.7 inner border.
    # Translate the entire associative block, not only its diameter row.
    x, y, _ = drawing.PLAN_KEEP["ClampDia"]
    dx = (x - (-26.0)) * _PLAN_SCALE
    dy = (y - (drawing._CALLOUT_Y + 10.0)) * _PLAN_SCALE
    assert (dx, dy) == pytest.approx((3.0, 1.0))
    lift = dy + _WIDTH_LIFT
    assert 13.0891 + dx - 12.7 >= _AIR_MM  # shelf, farther left than the ink
    assert 266.7 - (262.7036 + lift) >= _AIR_MM  # top of the full block
    assert 104.4326 - (87.2384 + dx) >= _AIR_MM  # upper section letter A
    # Keep the leader's closest approach to the upper A-A tail clear too:
    # shifting only X would repair the border but reintroduce review r12.
    # The CL hole and the cut's tail rise with the outline's top half.
    circle = (69.55255, 201.89715 + _WIDTH_LIFT)
    elbow = (87.2384 + dx, 224.8134 + lift)
    cut_tail = (90.2203, 222.287 + _WIDTH_LIFT)
    vx, vy = elbow[0] - circle[0], elbow[1] - circle[1]
    tx, ty = cut_tail[0] - circle[0], cut_tail[1] - circle[1]
    assert 0.0 < (tx * vx + ty * vy) / (vx * vx + vy * vy) < 1.0
    assert abs(vx * ty - vy * tx) / math.hypot(vx, vy) >= _AIR_MM
    assert elbow[1] - cut_tail[1] >= _AIR_MM
    assert x < drawing.CUT_X


def test_one_sheet_and_no_left_clamp_remnants() -> None:
    """R4 omits LEFT: no second sheet, hole, dimension or spec name survives."""
    assert not hasattr(drawing, "SHEET_NAMES")
    assert not hasattr(drawing, "LEFT_CLAMP_DIMENSIONS")
    assert not [n for n in dir(spec) if n.startswith("LEFT")]
    assert not [n for n in drawing.PLAN_KEEP if n.startswith("LeftClamp")]
    assert not [n for n in _features() if n.startswith("left_clamp")]
    assert len(spec.HOLES) == 9
