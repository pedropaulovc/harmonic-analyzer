"""Offline contracts for the feed-pinion sleeve (MHA-110) and its drawing."""

from __future__ import annotations

import itertools
import math
from pathlib import Path

import pytest

import _config
import build_transgear_feed_pinion as part
import draw_transgear_feed_pinion as drawing
import transgear_feed_pinion_spec as spec
from _drawing_contract import (
    PRECISION_MIGRATED_DRAWINGS,
    drawing_specification_violations,
    model_toleranced_dimensions,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _layout_audit import TEXT_CLEARANCE_HEIGHTS
from _layout_geometry import ARROW_TEXT_CLEARANCE_M, Box, estimate_text_box
from _printed_tolerance import printed_band_mm


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/transgear-feed-pinion.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/transgear-feed-pinion.pdf")
    assert drawing.PNG.as_posix().endswith("/png/transgear-feed-pinion_drawing.png")
    assert (
        DRAWINGS_BY_NAME["transgear_feed_pinion"].script
        == Path(drawing.__file__).resolve()
    )


def test_every_marked_dimension_is_placed_and_has_places() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked


def test_sheet_authors_no_manufacturing_value() -> None:
    # Rule 2: places and bands come from the part; the sheet reads them back.
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert not drawing_specification_violations(source, filename=drawing.__file__)


def test_bands_come_from_named_spec_constants() -> None:
    assert model_toleranced_dimensions(part) == {
        ("GearBlank", "FaceWidth"): "STATION_TOL",
        ("SleeveProfile", "SpigotFront"): "STATION_TOL",
        ("SleeveProfile", "OverallLength"): "STATION_TOL",
        ("SleeveProfile", "BoreDia"): "*BORE_DEVIATIONS",
        ("SleeveProfile", "SpigotDia"): "*SPIGOT_DIA_DEVIATIONS",
        ("SleeveProfile", "ShankDia"): "*SHANK_DIA_DEVIATIONS",
        ("SleeveProfile", "OutsideDia"): "*OUTSIDE_DIA_DEVIATIONS",
    }
    # A band tighter than its printed row needs a functional reason (rule 12):
    # the stations' ±0.05 sits inside their .XX row, the tip's +0/-0.10 inside .XXX.
    assert spec.STATION_TOL < printed_band_mm(spec.STATION_PLACES)
    assert -spec.OUTSIDE_DIA_BAND[1] < printed_band_mm(
        spec.DRAWING_PRECISION_BY_NAME["OutsideDia"]
    )


def test_root_prints_as_the_cutter_depth_floor() -> None:
    # swTolType_e.swTolMIN (offline API docs) prints the nominal then "MIN".
    assert spec.ROOT_DIA_TOL_TYPE == 5
    places = spec.DRAWING_PRECISION_BY_NAME["RootDia"]
    assert f"{spec.ROOT_DIA:.{places}f}" == f"{spec.ROOT_DIA_MIN:.{places}f}" == "8.04"
    assert spec.ROOT_DIA >= spec.ROOT_DIA_MIN
    # The model cuts the root the sheet floors: pitch radius less 1.25/P.
    pitch_r = spec.TEETH / spec.DIAMETRAL_PITCH / 2.0 * 25.4
    assert 2.0 * (
        pitch_r - spec.DEDENDUM_FACTOR / spec.DIAMETRAL_PITCH * 25.4
    ) == pytest.approx(spec.ROOT_DIA)
    lower, upper = spec.ROOT_DIA_DEVIATIONS
    assert spec.ROOT_DIA + lower == pytest.approx(spec.ROOT_DIA_MIN)
    assert upper == 0.0


def test_cluster_float_and_nose_proud_hold_worst_case() -> None:
    low, high = spec.CLUSTER_FLOAT_RANGE
    assert low == pytest.approx(0.2) and high == pytest.approx(0.4)
    assert spec.NOSE_PROUD == pytest.approx(0.70)
    assert spec.NOSE_PROUD_WORST >= 0.34 - 1e-9
    # The hub flange clamps the disc, never the spigot step.
    assert spec.SPIGOT_RECESS_WORST > 0.0
    assert spec.SPIGOT_LENGTH_MIN > 0.5 * spec.DISC_THICKNESS


def test_bore_runs_on_the_stud_journal() -> None:
    import transgear_stub_spec as stud

    assert spec.BORE_DIA == stud.JOURNAL_DIA
    j_upper, j_lower = stud.JOURNAL_DIA_BAND
    b_upper, b_lower = spec.BORE_DIA_BAND
    clearance = (b_lower - j_upper, b_upper - j_lower)
    assert clearance == pytest.approx(spec.BORE_DIAMETRAL_CLEARANCE)
    assert clearance[0] > 0.0
    # A running fit exists only when both size bands are narrower than the
    # clearance range they claim (tolerance-policy step 6b).
    span = clearance[1] - clearance[0]
    assert b_upper - b_lower < span and j_upper - j_lower < span


def test_oil_hole_lands_on_the_hub_hole_and_a_tooth_centre() -> None:
    import transgear_disc_hub_spec as hub
    from involute_gear import gear_facts

    hub_front = spec.GEAR_FACE_STATION + spec.DISC_THICKNESS + hub.HUB_LENGTH
    assert spec.OIL_HOLE_Z == pytest.approx(hub_front - hub.OIL_HOLE_STATION)
    assert spec.OIL_HOLE_DIA == hub.OIL_HOLE_DIA
    assert spec.SPIGOT_FRONT_STATION < spec.OIL_HOLE_Z < spec.OVERALL_LENGTH
    facts = gear_facts(spec.TEETH, spec.DIAMETRAL_PITCH, spec.PRESSURE_ANGLE_DEG)
    gap_centre = math.degrees((facts["ThetaL"] + facts["ThetaU"]) / 2.0)
    pitch = 360.0 / spec.TEETH
    offset = (spec.OIL_HOLE_AZIMUTH_DEG - gap_centre) % pitch
    assert offset == pytest.approx(pitch / 2.0)  # +Y is a tooth centre


def test_walls_meet_the_target_worst_case() -> None:
    for name, nominal, worst in spec.WALLS:
        assert worst >= spec.WALL_TARGET, name
        assert nominal >= worst, name


def test_sheet_text_names_the_right_parts() -> None:
    numbers = {
        "transgear-feed-pinion": spec.SLEEVE_NUMBER,
        "transgear-stub": spec.STUD_NUMBER,
        "transgear-disc-hub": spec.HUB_NUMBER,
        "rack-pinion": spec.DISC_NUMBER,
        "platen-rack": spec.RACK_NUMBER,
    }
    for stem, number in numbers.items():
        assert _config.parts(stem)["number"] == number, stem
    assert spec.OIL_HOLE_NOTE.startswith(f"MATCH DRILL AT ASSY WITH {spec.HUB_NUMBER}")
    assert f"MATE STUD {spec.STUD_NUMBER}" in spec.BORE_FIT_CALLOUT
    assert drawing.DIMENSION_CALLOUTS == {"BoreDia": spec.BORE_PROCESS_CALLOUT}


def test_part_record_and_finish() -> None:
    config = _config.parts("transgear-feed-pinion")
    assert config["material_specification"] == "SAE 1018 CF bar, ASTM A108-24"
    assert int(config["quantity"]) == 1
    (control,) = spec.SURFACE_FINISHES
    assert control.key == "bore"
    assert control.face.diameter_mm == spec.BORE_DIA


# Dimension text as the fleet's sheets print it: 3.5 mm caps, the advance and
# line pitch measured on the arbor-pedestal sheet (test_arbor_pedestal_drawing).
_CAP_M = 0.0035
_ADVANCE = 109.7 / (42 * 3.5)
_LINE_SPACING = 16.8 * 25.4 / 72.0 / 3.5
_NOMINAL = {
    "OutsideDia": spec.OUTSIDE_DIA,
    "RootDia": spec.ROOT_DIA_MIN,
    "BoreDia": spec.BORE_DIA,
    "SpigotDia": spec.SPIGOT_DIA,
    "ShankDia": spec.SHANK_DIA,
    "FaceWidth": spec.FACE_WIDTH,
    "SpigotFront": spec.SPIGOT_FRONT_STATION,
    "OverallLength": spec.OVERALL_LENGTH,
}
_DEVIATIONS = {
    "BoreDia": spec.BORE_DEVIATIONS,
    "SpigotDia": spec.SPIGOT_DIA_DEVIATIONS,
    "ShankDia": spec.SHANK_DIA_DEVIATIONS,
    "OutsideDia": spec.OUTSIDE_DIA_DEVIATIONS,
}
# The places SolidWorks printed each stacked band's deviations in (run
# 20261001T110844152Z): the upper above the lower, the lower beside the value.
_DEVIATION_PLACES = {"BoreDia": 3, "SpigotDia": 2, "ShankDia": 3, "OutsideDia": 1}


def _printed_text(name: str) -> str:
    """A kept dimension's whole text as the section prints it, padded with
    the space SolidWorks prints either side: its value, then the root's MIN,
    a station's band, or a stacked band, then any callout below."""
    value = f"{_NOMINAL[name]:.{spec.DRAWING_PRECISION_BY_NAME[name]}f}"
    if name.endswith("Dia"):
        value = f"\u00d8{value}"
    if name == "RootDia":
        rows = [f"{value} min."]
    elif name in _DEVIATIONS:
        lower, upper = _DEVIATIONS[name]
        places = _DEVIATION_PLACES[name]
        rows = [f"{upper:+.{places}f}", f"{value} {lower:+.{places}f}"]
    else:
        rows = [f"{value} \u00b1{spec.STATION_TOL:.{spec.STATION_PLACES}f}"]
    if name in drawing.DIMENSION_CALLOUTS:
        rows.append(drawing.DIMENSION_CALLOUTS[name])
    return "\n".join(f" {row} " for row in rows)


def _inline(anchor: tuple[float, float]) -> bool:
    return anchor[1] == drawing.RIGHT_CENTER[1]


def _printed_box(name: str, anchor: tuple[float, float]) -> Box:
    """The estimated box of a kept dimension's whole text.

    Text placed on the axis prints centred on its point, the dimension line
    breaking round it (the crank hub's sheet).  A shelf diameter's text hangs
    off one side of its dimension line, and SolidWorks picks the side (the
    20261001T110844152Z shelf printed both), so its box covers both."""
    box = estimate_text_box(
        _printed_text(name),
        anchor=anchor,
        height=_CAP_M,
        reference=2,
        advance_ratio=_ADVANCE,
        line_spacing=_LINE_SPACING,
    )
    assert box is not None
    if name.endswith("Dia") and not _inline(anchor):
        width = box.xmax - box.xmin
        return Box(anchor[0] - width, box.ymin, anchor[0] + width, box.ymax)
    return box


def _note_box(text: str, anchor: tuple[float, float]) -> Box:
    """A note's estimated box: SolidWorks places a note by its upper left."""
    box = estimate_text_box(
        text,
        anchor=anchor,
        height=_CAP_M,
        advance_ratio=_ADVANCE,
        line_spacing=_LINE_SPACING,
    )
    assert box is not None
    return box


def test_section_values_and_bands_print_clear_of_each_other() -> None:
    """Machinist review of run 20261001T110844152Z: the tip, spigot and shank
    stood on one shelf above the section and their stacked bands printed over
    each other.  Every value with its band and callout keeps the layout
    audit's text air from every other text, clears both views, and stays
    inside the border; the inline diameters print between their own
    extension lines and off the part."""
    s = drawing.VIEW_SCALE[0] / 1000.0
    axis_y = drawing.RIGHT_CENTER[1]
    rear_x = drawing._side_x(0.0)
    nose_x = drawing._side_x(spec.OVERALL_LENGTH)
    section = Box(rear_x, axis_y - drawing.HALF_OD, nose_x, axis_y + drawing.HALF_OD)
    end_view = Box(
        drawing.FRONT_CENTER[0] - drawing.HALF_OD,
        drawing.FRONT_CENTER[1] - drawing.HALF_OD,
        drawing.FRONT_CENTER[0] + drawing.HALF_OD,
        drawing.FRONT_CENTER[1] + drawing.HALF_OD,
    )
    boxes = {name: _printed_box(name, xy) for name, xy in drawing.RIGHT_KEEP.items()}
    boxes["oil hole note"] = _note_box(spec.OIL_HOLE_NOTE, drawing.OIL_HOLE_CALLOUT)
    boxes["bore fit note"] = _note_box(spec.BORE_FIT_CALLOUT, drawing.BORE_FIT_NOTE)
    air = TEXT_CLEARANCE_HEIGHTS * _CAP_M
    clashes = [
        (a, b, round(boxes[a].gap(boxes[b]) * 1000.0, 2))
        for a, b in itertools.combinations(sorted(boxes), 2)
        if boxes[a].gap(boxes[b]) < air
    ]
    assert clashes == []
    x0, y0, x1, y1 = drawing.SHEET_INNER_BORDER
    for name, box in boxes.items():
        assert x0 <= box.xmin and box.xmax <= x1, name
        assert y0 <= box.ymin and box.ymax <= y1, name
        assert box.gap(end_view) >= ARROW_TEXT_CLEARANCE_M, name
    inline = {
        name: anchor for name, anchor in drawing.RIGHT_KEEP.items() if _inline(anchor)
    }
    assert set(inline) == {"OutsideDia", "RootDia", "ShankDia"}
    for name in inline:
        half = _NOMINAL[name] / 2.0 * s
        assert axis_y - half < boxes[name].ymin, name
        assert boxes[name].ymax < axis_y + half, name
        assert boxes[name].gap(section) >= ARROW_TEXT_CLEARANCE_M, name
    # Beside one face the larger diameter stands farther out, so neither's
    # extension lines cross the other's dimension line.
    left = sorted(
        (n for n in inline if inline[n][0] < rear_x), key=lambda n: -inline[n][0]
    )
    assert left == ["RootDia", "OutsideDia"]
    assert [_NOMINAL[n] for n in left] == sorted(_NOMINAL[n] for n in left)
    assert inline["ShankDia"][0] > nose_x


# The finish symbol's ink from its insertion point, measured on run
# 20261001T110844152Z: the leader leaves the shoulder's right end, the "Ra"
# text's lower right corner stands up and right of the root, and the V's
# left arm reaches left of it.
_FINISH_SHOULDER_DX = 0.0064
_FINISH_TEXT_CORNER = (0.0147, 0.0042)
_FINISH_LEFT_DX = -0.0021


def test_finish_leader_climbs_clear_of_its_own_text() -> None:
    """Run 20261001T110844152Z's finish leader climbed through its own "Ra
    1.6" (leader-through-own-text); it now passes right of the text, and the
    symbol stands clear of the end view and inside the border."""
    sx, sy = drawing.FINISH_SYMBOL
    start = (sx + _FINISH_SHOULDER_DX, sy)
    end = drawing.FINISH_ATTACH
    text_right = sx + _FINISH_TEXT_CORNER[0]
    text_bottom = sy + _FINISH_TEXT_CORNER[1]
    assert end[0] > start[0] and end[1] > text_bottom
    rise = (text_bottom - start[1]) / (end[1] - start[1])
    leader_x = start[0] + (end[0] - start[0]) * rise
    assert leader_x - text_right >= ARROW_TEXT_CLEARANCE_M
    end_view_left = drawing.FRONT_CENTER[0] - drawing.HALF_OD
    assert end_view_left - text_right >= ARROW_TEXT_CLEARANCE_M
    assert sx + _FINISH_LEFT_DX > drawing.SHEET_INNER_BORDER[0]
