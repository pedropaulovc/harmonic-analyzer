"""Offline contracts for the feed-pinion sleeve (MHA-PD-10) and its drawing."""

from __future__ import annotations

import itertools
import math
import re
from pathlib import Path

import pytest

import _config
import build_pd_transgear_feed_pinion as part
import draw_pd_transgear_feed_pinion as drawing
import pd_transgear_feed_pinion_callouts as callouts
import pd_transgear_feed_pinion_spec as spec
import paper_drive_stock_native as stock_native
import paper_drive_stock_drawing as stock_drawing
from _drawing_contract import (
    PRECISION_MIGRATED_DRAWINGS,
    drawing_specification_violations,
    model_toleranced_dimensions,
)
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _layout_audit import TEXT_CLEARANCE_HEIGHTS
from _layout_geometry import ARROW_TEXT_CLEARANCE_M, Box, estimate_text_box
from _gear_quality import (
    toothspace_runout_tir_mm,
)
from _printed_tolerance import (
    edge_break_chamfer_mm,
    inside_corner_radius_mm,
    printed_band_mm,
)
from pd_cluster_stack_band import PRINTED_LENGTH_BAND_IN, STACK_NAME
from paper_drive_stock_inspection import (
    span_contact_points_mm,
    toothspace_gauge_contact_mm,
)


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-transgear-feed-pinion.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-transgear-feed-pinion.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pd-transgear-feed-pinion_drawing.png")
    assert (
        DRAWINGS_BY_NAME["pd_transgear_feed_pinion"].script
        == Path(drawing.__file__).resolve()
    )


def test_every_marked_dimension_is_placed_and_has_places() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    keeps = (drawing.FRONT_KEEP, drawing.RIGHT_KEEP, drawing.LEFT_KEEP, drawing.REAR_KEEP)
    assert sum(len(keep) for keep in keeps) == len(marked)
    assert set().union(*keeps) == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked


def test_part_authors_every_callout_on_a_marked_dimension() -> None:
    """#1942: the sheet only reads text lanes back; the part writes them on
    the dimensions it marks, and every band tighter than its row names its
    mate or stack at its own callout (2026-10-24 ENFORCE review)."""
    assert part.callouts is callouts
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_dimension_callouts" not in source and ".SetText(" not in source
    for feature, by_name in callouts.authored_text().items():
        assert set(by_name) <= spec.DRAWING_DIMENSIONS[feature], feature
    below = {
        name: text
        for (_feature, name), text in callouts.CALLOUTS[callouts.CALLOUT_BELOW].items()
    }
    assert below["BoreDia"] == spec.BORE_CALLOUT
    assert spec.BORE_CALLOUT.startswith(spec.BORE_PROCESS_CALLOUT)
    assert spec.BORE_CALLOUT.endswith(spec.BORE_FIT_CALLOUT)
    for name in ("BossDia", "FlatToAxis", "FaceWidth", "FlatEnd", "OverallLength"):
        assert spec.HUB_NUMBER in below[name], name
    for name in ("OutsideDia", "ToothSpan"):
        assert spec.RACK_NUMBER in below[name], name
    assert spec.PIN_NUMBER not in below["OverallLength"]
    assert "MHA-PD-25" in below["OverallLength"]
    for name in ("FaceWidth", "OverallLength"):
        assert STACK_NAME in below[name], name
        assert "FACED" not in below[name], name
    assert callouts.CALLOUTS[callouts.TEXT_PREFIX] == {
        ("RootProfile", "RootDia"): "ROOT ENVELOPE <MOD-DIAM>"
    }


def test_sheet_authors_no_manufacturing_value() -> None:
    # drawing-simplicity-policy.md `How the repository implements the guidelines`: places and bands come from the part; the sheet reads them back.
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert not drawing_specification_violations(source, filename=drawing.__file__)


def test_bands_come_from_named_spec_constants() -> None:
    assert model_toleranced_dimensions(part) == {
        ("SleeveProfile", "OverallLength"): "OVERALL_LENGTH_BAND",
        ("GearBlank", "FaceWidth"): "FACE_WIDTH_BAND",
        ("SleeveProfile", "BoreDia"): "*BORE_DEVIATIONS",
        ("SleeveProfile", "BossDia"): "*BOSS_DIA_DEVIATIONS",
        ("FlatProfile", "FlatToAxis"): "*FLAT_TO_AXIS_DEVIATIONS",
        ("SleeveProfile", "OutsideDia"): "*OUTSIDE_DIA_DEVIATIONS",
    }
    # A band tighter than its printed row needs a functional reason (drawing-guidelines.md rule 4 (tighten only for function, and name the mate)):
    # the disc cluster stack's band, the tip class, the boss's and the flat's
    # bands print four places, where the inch title block has no row, so
    # each carries its own explicit band.
    assert spec.OVERALL_LENGTH_BAND == spec.FACE_WIDTH_BAND == PRINTED_LENGTH_BAND_IN
    by_name = spec.DRAWING_PRECISION_BY_NAME
    assert spec.STATION_PLACES == spec.FACE_WIDTH_PLACES == 4
    for name in ("OutsideDia", "BossDia", "FlatToAxis"):
        assert by_name[name] == 4, name


def test_root_prints_as_the_cutter_depth_floor() -> None:
    # swTolType_e.swTolMIN (offline API docs) prints the nominal then "MIN".
    assert spec.ROOT_DIA_TOL_TYPE == 5
    places = spec.DRAWING_PRECISION_BY_NAME["RootDia"]
    expected_root = 2.0 * spec.STOCK_PROFILE.root_radius_min_mm
    corners = spec.manufactured_profiles()
    minimum = min(2.0 * profile.root_radius_min_mm for profile in corners)
    # The MIN is floored on the printed inch grid, never rounded up.
    expected_floor = math.floor(minimum / 25.4 * 10**places) / 10**places * 25.4
    assert spec.ROOT_DIA == pytest.approx(expected_root)
    assert spec.ROOT_DIA_MIN == pytest.approx(expected_floor)
    assert spec.ROOT_DIA_MIN <= minimum <= spec.ROOT_DIA
    assert spec.ROOT_DIA_DEVIATIONS == (0.0, 0.0)
    assert spec.ROOT_DEPTH_X_MIN == pytest.approx(
        min(profile.root_point(profile.root_half_angle_rad)[0] for profile in corners)
    )


def test_disc_front_stands_a_spigot_length_ahead_of_the_step() -> None:
    """The hub's spigot seats on the 12T's step and carries the disc on its
    flange, so the disc's front face is the step plus the spigot; the disc's
    bore stands radially outside the 12T's tips, so its rear face never
    meets the teeth, and stands ahead of the step at every printed limit."""
    import pd_rack_pinion_spec as disc
    import pd_transgear_disc_hub_spec as hub

    assert spec.DISC_FRONT_STATION == pytest.approx(spec.FACE_WIDTH + hub.SPIGOT_LENGTH)
    assert spec.DISC_FRONT_STATION == pytest.approx((0.535 + 0.144) * 25.4)
    assert spec.DISC_FRONT_STATION_BAND == pytest.approx(
        spec.FACE_WIDTH_BAND + hub.SPIGOT_LENGTH_BAND
    )
    assert disc.BORE_DIA_MIN > spec.OUTSIDE_DIA + spec.OUTSIDE_DIA_BAND[0]
    assert hub.DISC_STEP_GAP_WORST > 0.0


def test_boss_and_flat_take_the_hub_bore() -> None:
    """One round size for the hub's bore and one flat for its D: the boss
    no longer carries the disc (the hub's spec checks the clearances at
    every limit pair)."""
    import pd_transgear_disc_hub_spec as hub

    assert spec.BOSS_DIA == hub.BORE_DIA
    assert spec.FLAT_TO_AXIS == hub.FLAT_TO_AXIS
    assert hub.BOSS_CLEARANCE_LIMITS[0] >= 0.0
    assert hub.FLAT_CLEARANCE[0] > 0.0


def test_step_face_is_square_to_the_bore() -> None:
    """The hub's spigot seats on the step, so the step face is held square
    to the bore (datum A) over the tip circle; the frame prints the spec's
    value."""
    assert spec.BORE_DATUM == "A"
    assert spec.STEP_FACE_PERPENDICULARITY == pytest.approx(0.0002 * 25.4)
    assert spec.STEP_FACE_PERPENDICULARITY_ZONE_DIA == spec.OUTSIDE_DIA
    assert spec.GEOMETRIC_TOLERANCES_IN == {
        "step face perpendicularity to bore": ".0002"
    }
    # The frame's leader lands on the step face's edge-on line in the
    # section, between the boss and the tip on the +Y tooth.
    s = drawing.VIEW_SCALE[0] / 1000.0
    x, y = drawing.STEP_FACE_EDGE
    assert x == pytest.approx(drawing._side_x(spec.FACE_WIDTH))
    axis_y = drawing.RIGHT_CENTER[1]
    assert axis_y + spec.BOSS_DIA / 2.0 * s < y < axis_y + spec.OUTSIDE_DIA / 2.0 * s
    assert drawing.STEP_FRAME[1] > drawing._SIDE_TOP


def test_full_depth_covers_the_racks_worst_reach() -> None:
    """R9-67: the 12T cuts full depth from the rear face over the rack's whole
    width at the printed worst case of the stack behind the platen."""
    import build_pd_paper_drive_assembly as assembly
    import pd_rack_pinion_spec as disc

    reach = assembly.RACK_FRONT_FROM_SLEEVE_REAR_WORST
    assert spec.FULL_DEPTH_MIN >= reach
    assert spec.FULL_DEPTH_MIN < spec.FACE_WIDTH - spec.FACE_WIDTH_BAND
    # The platen stands between the rack's front face and the disc's rear
    # face, so the rack never reaches within the platen's thickness of it in
    # the limit that sets its reach: the disc at its furthest forward on the
    # sleeve (the step and spigot at their longest, the disc thickest).
    disc_rear = (
        spec.DISC_FRONT_STATION + spec.DISC_FRONT_STATION_BAND - disc.FACE_WIDTH_MAX
    )
    assert reach + assembly.PLATE_THICKNESS < disc_rear


def test_cutter_run_out_ends_inside_its_limit_clear_of_the_disc() -> None:
    """The run-out at its worst, and the printed limit, stand at least
    RUNOUT_DISC_CLEARANCE behind the disc's nearest rear face: the slots end
    under the hub's spigot, which the disc stands outside radially."""
    import pd_rack_pinion_spec as disc

    assert spec.DISC_REAR_MIN == pytest.approx(
        spec.DISC_FRONT_STATION - spec.DISC_FRONT_STATION_BAND - disc.FACE_WIDTH_MAX
    )
    assert spec.RUNOUT_DISC_CLEARANCE == pytest.approx(0.002 * 25.4)
    limit = spec.DISC_REAR_MIN - spec.RUNOUT_DISC_CLEARANCE
    assert spec.CUTTER_RUNOUT_END_WORST <= spec.CUTTER_RUNOUT_MAX <= limit
    # The physical cutter radius is located by deepest ground X, not the
    # nonconcentric root norm used to inspect the material's minimum wall.
    assert spec.RUNOUT_RISE_WORST == pytest.approx(
        (spec.BOSS_DIA + spec.BOSS_DIA_BAND[0]) / 2.0 - spec.ROOT_DEPTH_X_MIN
    )
    # The largest cutter at the full-depth MIN still runs out inside the MAX.
    rise = spec.RUNOUT_RISE_WORST
    assert (
        spec.FULL_DEPTH_MIN + spec.cutter_runout(spec.CUTTER_DIA_MAX, rise)
        <= spec.CUTTER_RUNOUT_MAX
    )
    # Negative control derives an oversized cutter from the actual station
    # limit instead of pinning a formerly acceptable catalog diameter.
    length = spec.CUTTER_RUNOUT_MAX - spec.FULL_DEPTH_MIN
    big = 1.01 * (length * length + rise * rise) / rise
    assert spec.FULL_DEPTH_MIN + spec.cutter_runout(big, rise) > spec.CUTTER_RUNOUT_MAX


def test_cutter_stations_are_native_banded_model_dimensions() -> None:
    """Codex P2 on R9-67: the full-depth window and the run-out limit print as
    the model's own dimensions, band and places on the part, not as numbers
    frozen into note text (drawing-simplicity-policy.md `How the repository implements the guidelines` and drawing-guidelines.md rule 12 (hole and slot callouts say what to do))."""
    assert {"FullDepth", "CutterRunout"} <= spec.DRAWING_DIMENSIONS["SleeveProfile"]
    places = spec.DRAWING_PRECISION_BY_NAME
    assert places["FullDepth"] == spec.FULL_DEPTH_PLACES == 3
    assert places["CutterRunout"] == spec.CUTTER_RUNOUT_PLACES == 3
    # The full depth covers the rack, a one-sided need, so it prints as a
    # MIN at the modelled station (2026-10-27 review, r1, r3); the run-out
    # MAX (swTolType_e.swTolMAX) caps it.  Each nominal is the limit it
    # prints.
    assert spec.FULL_DEPTH_TOL_TYPE == 5  # swTolType_e.swTolMIN
    assert spec.FULL_DEPTH_MIN == spec.FULL_DEPTH
    assert round(spec.FULL_DEPTH / 25.4, spec.FULL_DEPTH_PLACES) * 25.4 == pytest.approx(
        spec.FULL_DEPTH
    )
    # codjiflo P2 (0247213): a smaller cutter or shallower profile runs out
    # sooner, so over every accepted part only the run-out MAX bounds the
    # full depth and the cutter's end.
    assert spec.FULL_DEPTH_MAX == spec.CUTTER_RUNOUT_MAX
    assert spec.CUTTER_RUNOUT_END_WORST == spec.CUTTER_RUNOUT_MAX
    assert spec.CUTTER_RUNOUT_TOL_TYPE == 6
    lower, upper = spec.CUTTER_RUNOUT_DEVIATIONS
    assert upper == 0.0
    assert spec.CUTTER_RUNOUT_MAX + lower == pytest.approx(spec.FULL_DEPTH_MIN)
    # No number the model owns is retyped into the notes.
    lines = spec.DRAWING_NOTES.splitlines()
    for value in (
        f"{spec.FULL_DEPTH / 25.4:.3f}".lstrip("0"),
        f"{spec.CUTTER_RUNOUT_MAX / 25.4:.3f}".lstrip("0"),
    ):
        assert value not in spec.DRAWING_NOTES, value
    # A shop note states requirements only: the cutter is method.  The
    # tooth-edge exception is flagged at the teeth by a leader (rule 7), so
    # the loose block keeps only the wall.
    assert lines == [spec.FLAT_WALL_NOTE]
    assert max(len(line) for line in lines) <= 70
    # Short names, printed under the value, so the narrow text stands left
    # of the outside view's rear face.  The full depth names its function:
    # its teeth cover the rack's reach.
    assert callouts.FULL_DEPTH_CALLOUT.split("\n") == [
        f"{spec.TEETH}T FULL DEPTH",
        f"COVERS {callouts.RACK_NUMBER} RACK",
    ]
    assert "\n" not in callouts.CUTTER_RUNOUT_CALLOUT
    # Their witnesses run along the floor of the gap facing the outside
    # view: model 195°, a gap centre (gap centres at 15° + k·30°).
    assert spec.GAP_FLOOR_WITNESS_Y == pytest.approx(
        spec.ROOT_DIA_MIN / 2.0 * math.sin(math.radians(195.0))
    )
    assert (195.0 - 180.0 / spec.TEETH) % (360.0 / spec.TEETH) == pytest.approx(0.0)


def test_flat_end_mill_reaches_the_end_wall_clear_of_the_hub() -> None:
    """The flat is cut by an end mill parallel to the sleeve axis, plunged
    from the nose: its flutes cover the longest flat with 0.5 to spare.  The
    wall stops nothing: the hub's flat starts a spigot length ahead of the
    step, ahead of the wall at every printed limit."""
    import pd_transgear_disc_hub_spec as hub

    # The end mill reaches the MAX station on the longest sleeve; a longer
    # flat toward the MIN is the shop's choice of cutter.
    assert spec.FLAT_REACH == pytest.approx(
        spec.OVERALL_LENGTH + spec.STATION_TOL - spec.FLAT_END_STATION
    )
    assert spec.FLAT_CUTTER_FLUTE_MIN >= spec.FLAT_REACH + 0.5
    # codjiflo P1 on 65a022125: the printed MIN keeps the wall off the step
    # the spigot seats on (longest tooth length plus the title block's edge
    # break) and off the cutter's run-out.
    edge_break = edge_break_chamfer_mm(unit="in")
    assert spec._TITLE_BLOCK_EDGE_BREAK == edge_break
    assert spec.FLAT_END_MIN >= (
        spec.FACE_WIDTH + spec.FACE_WIDTH_BAND + edge_break
    )
    assert spec.FLAT_END_MIN >= spec.CUTTER_RUNOUT_MAX
    assert spec.FLAT_END_TOL_TYPE == 3  # swTolType_e.swTolLIMIT
    assert spec.FLAT_END_DEVIATIONS == (
        pytest.approx(spec.FLAT_END_MIN - spec.FLAT_END_STATION), 0.0
    )
    # Looser than the title block's row at the limits' places.
    assert spec.FLAT_END_STATION - spec.FLAT_END_MIN > 2.0 * printed_band_mm(
        spec.FLAT_END_PLACES, unit="in"
    )
    worst = (
        spec.FACE_WIDTH
        - spec.FACE_WIDTH_BAND
        + hub.SPIGOT_LENGTH_MIN
        - (spec.FLAT_END_STATION + spec.STATION_TOL)
    )
    assert hub.FLAT_END_CLEARANCE_WORST == pytest.approx(worst)
    assert hub.FLAT_END_CLEARANCE_WORST > 0.0
    # codjiflo P2 on edb402b/482fbdc (#2006): the title block lets the
    # flat's floor meet the wall in an inside corner up to its ceiling.  Where
    # the hub's flat starts, that corner's blend must stay under the flats'
    # minimum clearance, or the hub cannot seat.
    corner = inside_corner_radius_mm(unit="in")
    gap = hub.FLAT_END_CLEARANCE_WORST
    rise = corner - math.sqrt(corner**2 - (corner - gap) ** 2) if gap < corner else 0.0
    assert rise < hub.FLAT_CLEARANCE[0], (gap, rise)


def test_flat_volume_is_the_boss_segment() -> None:
    radius = spec.BOSS_DIA / 2.0
    half_angle = math.acos(spec.FLAT_TO_AXIS / radius)
    segment = radius**2 * (half_angle - math.sin(half_angle) * math.cos(half_angle))
    assert part.V_FLAT == pytest.approx(
        segment * (spec.OVERALL_LENGTH - spec.FLAT_END_STATION)
    )
    # The bore stays under the flat: it never breaks through.
    assert spec.BORE_DIA / 2.0 < spec.FLAT_TO_AXIS


def test_bore_runs_on_the_pin() -> None:
    import pd_transgear_pin_spec as pin

    assert spec.BORE_DIA == pin.DIA
    p_upper, p_lower = pin.DIA_BAND
    b_upper, b_lower = spec.BORE_DIA_BAND
    clearance = (b_lower - p_upper, b_upper - p_lower)
    assert clearance == pytest.approx(spec.BORE_DIAMETRAL_CLEARANCE)
    assert clearance[0] > 0.0
    # A running fit exists only when both size bands are narrower than the
    # clearance range they claim (tolerance-policy step 6b).
    span = clearance[1] - clearance[0]
    assert b_upper - b_lower < span and p_upper - p_lower < span


def test_oil_hole_lands_on_a_tooth_centre() -> None:
    # Finite master gaps are centred at +X; the native seed rotates half a
    # physical pitch so +X, and every integer pitch from it, is a tooth.
    gap_centre = 180.0 / spec.TEETH
    pitch = 360.0 / spec.TEETH
    offset = (spec.OIL_HOLE_AZIMUTH_DEG - gap_centre) % pitch
    assert offset == pytest.approx(pitch / 2.0)  # +Y is a tooth centre


def test_walls_meet_the_target_worst_case() -> None:
    for name, nominal, worst in spec.WALLS:
        assert worst >= spec.WALL_TARGET, name
        assert nominal >= worst, name
    # The wall under the flat is the one held to the floor, not the target,
    # and the sheet prints its worst case floored on the .001 in grid.
    assert spec.WALL_FLOOR <= spec.FLAT_WALL_WORST < spec.WALL_TARGET
    assert spec.FLAT_WALL_WORST <= spec.FLAT_WALL
    assert spec.FLAT_WALL_PRINTED <= spec.FLAT_WALL_WORST
    assert spec.FLAT_WALL_WORST - spec.FLAT_WALL_PRINTED < 0.001 * 25.4
    printed = re.search(r"(\d*\.\d+) MIN", spec.FLAT_WALL_NOTE)
    assert printed is not None
    assert float(printed.group(1)) * 25.4 == pytest.approx(spec.FLAT_WALL_PRINTED)
    assert spec.FLAT_WALL_NOTE in spec.DRAWING_NOTES.splitlines()


def test_sheet_text_names_the_right_parts() -> None:
    import pd_transgear_disc_hub_spec as hub

    numbers = {
        "pd-transgear-feed-pinion": spec.SLEEVE_NUMBER,
        "pd-transgear-pin": spec.PIN_NUMBER,
        "pd-transgear-disc-hub": spec.HUB_NUMBER,
        "pd-rack-pinion": spec.DISC_NUMBER,
        "pd-platen-rack": spec.RACK_NUMBER,
    }
    for stem, number in numbers.items():
        assert _config.parts(stem)["number"] == number, stem
    note = drawing.OIL_HOLE_NOTE
    hole, drill = note.split("\n")
    printed = re.match(r"\u00d8(\d*\.\d+) OIL HOLE", hole)
    assert printed is not None
    assert float(printed.group(1)) * 25.4 == pytest.approx(hub.OIL_HOLE_DIA)
    # The leader leaves the last row's end, so that row is the longer.
    assert len(hole) < len(drill) <= 70
    assert f"WITH {spec.HUB_NUMBER}" in drill
    # The hub's sheet locates the match-drilled hole at its printed station.
    assert drill.endswith(f"POSITION SET BY {spec.HUB_NUMBER}")
    assert "OilHoleStation" in hub.DRAWING_PRECISION_BY_NAME
    assert f"MATE PIN {spec.PIN_NUMBER}" in spec.BORE_FIT_CALLOUT
    assert _config.parts("pd-transgear-front-bushing")["number"] == "MHA-PD-25"


def test_part_record_and_finish() -> None:
    config = _config.parts("pd-transgear-feed-pinion")
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
    "BossDia": spec.BOSS_DIA,
    "FlatToAxis": spec.FLAT_TO_AXIS,
    "FaceWidth": spec.FACE_WIDTH,
    "FlatEnd": spec.FLAT_END_STATION,
    "OverallLength": spec.OVERALL_LENGTH,
    "FullDepth": spec.FULL_DEPTH,
    "CutterRunout": spec.CUTTER_RUNOUT_MAX,
    "ToothSpan": spec.SPAN_NOMINAL,
}
_DEVIATIONS = {
    "BoreDia": spec.BORE_DEVIATIONS,
    "BossDia": spec.BOSS_DIA_DEVIATIONS,
    "FlatToAxis": spec.FLAT_TO_AXIS_DEVIATIONS,
    "OutsideDia": spec.OUTSIDE_DIA_DEVIATIONS,
}
# The places SolidWorks printed each stacked band's deviations in (run
# 20261001T110844152Z): the upper above the lower, the lower beside the value.
_DEVIATION_PLACES = {
    "BoreDia": spec.BORE_PLACES,
    "BossDia": spec.BOSS_DIA_PLACES,
    "FlatToAxis": spec.FLAT_TO_AXIS_PLACES,
    "OutsideDia": spec.OUTSIDE_DIA_PLACES,
}
# The disc-cluster stack terms' symmetric bands; the other lengths print bare
# under the title block's rows.
_STATIONS = {
    "OverallLength": spec.OVERALL_LENGTH_BAND,
    "FaceWidth": spec.FACE_WIDTH_BAND,
}


def _inch(value_mm: float, places: int, *, sign: bool = False) -> str:
    """``value_mm`` as the inch sheet prints it (no leading zero)."""
    text = f"{value_mm / 25.4:{'+' if sign else ''}.{places}f}"
    return text.replace("0.", ".", 1) if abs(value_mm) < 25.4 else text


def _printed_text(name: str) -> str:
    """A kept dimension's whole text as the sheet prints it, padded with the
    space SolidWorks prints either side: its part-authored prefix and value,
    then the root's MIN, a station's band, or a stacked band, then the
    part-authored callout below."""
    value = _inch(_NOMINAL[name], spec.DRAWING_PRECISION_BY_NAME[name])
    lanes = callouts.authored_by_name().get(name, {})
    if callouts.TEXT_PREFIX in lanes:
        # An authored prefix replaces SolidWorks' own diameter symbol.
        value = lanes[callouts.TEXT_PREFIX].replace("<MOD-DIAM>", "\u00d8") + value
    elif name.endswith("Dia"):
        value = f"\u00d8{value}"
    if name == "ToothSpan":
        lower, upper = spec.SPAN_LIMITS
        rows = [
            f"{spec.SPAN_PREFIX}{_inch(upper, spec.SPAN_PLACES)}",
            _inch(lower, spec.SPAN_PLACES),
        ]
    elif name in ("RootDia", "FullDepth"):
        rows = [f"{value} min."]
    elif name == "FlatEnd":
        rows = [value, _inch(spec.FLAT_END_MIN, spec.FLAT_END_PLACES)]
    elif name == "CutterRunout":
        rows = [f"{value} max."]
    elif name in _DEVIATIONS:
        lower, upper = _DEVIATIONS[name]
        places = _DEVIATION_PLACES[name]
        rows = [
            _inch(upper, places, sign=True),
            f"{value} {_inch(lower, places, sign=True)}",
        ]
    elif name in _STATIONS:
        rows = [f"{value} \u00b1{_inch(_STATIONS[name], 4)}"]
    else:
        rows = [value]
    if callouts.CALLOUT_BELOW in lanes:
        rows += lanes[callouts.CALLOUT_BELOW].split("\n")
    return "\n".join(f" {row} " for row in rows)


def _inline(anchor: tuple[float, float]) -> bool:
    return anchor[1] == drawing.RIGHT_CENTER[1]


def _printed_box(name: str, anchor: tuple[float, float]) -> Box:
    """The estimated box of a kept dimension's whole text.

    Text placed on the axis prints centred on its point, the dimension line
    breaking round it (the crank hub's sheet).  A section shelf diameter's
    text hangs off one side of its dimension line, and SolidWorks picks the
    side (the 20261001T110844152Z shelf printed both), so its box covers
    both."""
    box = estimate_text_box(
        _printed_text(name),
        anchor=anchor,
        height=_CAP_M,
        reference=2,
        advance_ratio=_ADVANCE,
        line_spacing=_LINE_SPACING,
    )
    assert box is not None
    if name == "FlatToAxis":
        # Its text prints right of its own dimension line (run
        # 20261027T032128736Z), the line at the anchor.
        width = box.xmax - box.xmin
        return Box(anchor[0], box.ymin, anchor[0] + width, box.ymax)
    if name.endswith("Dia") and name in drawing.RIGHT_KEEP and not _inline(anchor):
        width = box.xmax - box.xmin
        return Box(anchor[0] - width, box.ymin, anchor[0] + width, box.ymax)
    return box


def _note_box(text: str, anchor: tuple[float, float], *, height: float = _CAP_M) -> Box:
    """A note's estimated box: SolidWorks places a note by its upper left."""
    box = estimate_text_box(
        text,
        anchor=anchor,
        height=height,
        advance_ratio=_ADVANCE,
        line_spacing=_LINE_SPACING,
    )
    assert box is not None
    return box


def _view_box(centre: tuple[float, float], length_mm: float | None = None) -> Box:
    """A view's tip-circle box; ``length_mm`` gives a side view's length."""
    half_x = drawing.HALF_OD if length_mm is None else length_mm * drawing.VIEW_SCALE[0] / 2000.0
    return Box(
        centre[0] - half_x,
        centre[1] - drawing.HALF_OD,
        centre[0] + half_x,
        centre[1] + drawing.HALF_OD,
    )


def test_section_values_and_bands_print_clear_of_each_other() -> None:
    """Machinist review of run 20261001T110844152Z: the tip, spigot and shank
    stood on one shelf above the section and their stacked bands printed over
    each other.  Every value with its band and callout keeps the layout
    audit's text air from every other text, clears every view, and stays
    inside the border; the inline diameters print between their own
    extension lines and off the part, and the flat's value hangs below the
    section right of the nose, under the boss's lower extension line."""
    s = drawing.VIEW_SCALE[0] / 1000.0
    axis_y = drawing.RIGHT_CENTER[1]
    rear_x = drawing._side_x(0.0)
    nose_x = drawing._side_x(spec.OVERALL_LENGTH)
    section = Box(rear_x, axis_y - drawing.HALF_OD, nose_x, axis_y + drawing.HALF_OD)
    views = {
        "end": _view_box(drawing.FRONT_CENTER),
        "rear": _view_box(drawing.REAR_CENTER),
        "section": section,
        # Cropped, without an outline: its geometry ends at the fence.
        "outside": Box(
            drawing._LEFT_REAR_X,
            drawing.LEFT_CENTER[1] - drawing.HALF_OD,
            drawing.OUTSIDE_CROP_FENCE[2],
            drawing.LEFT_CENTER[1] + drawing.HALF_OD,
        ),
        # codjiflo P3 on 65a022125: the isometric's ink as run
        # 20261027T032128736Z's sheet measured it, the BossDia's extension
        # line excluded: (0.326, 0.185)-(0.409, 0.247) about ISO_CENTER
        # (0.367, 0.214) at 3:1, so in model mm from its centre (codjiflo P3
        # on 0772285: it follows the view's placement and scale).
        "isometric": Box(
            drawing.ISO_CENTER[0] - 41.0 / 3.0 * s,
            drawing.ISO_CENTER[1] - 29.0 / 3.0 * s,
            drawing.ISO_CENTER[0] + 42.0 / 3.0 * s,
            drawing.ISO_CENTER[1] + 33.0 / 3.0 * s,
        ),
    }
    keeps = {
        **drawing.FRONT_KEEP,
        **drawing.RIGHT_KEEP,
        **drawing.LEFT_KEEP,
        **drawing.REAR_KEEP,
    }
    boxes = {name: _printed_box(name, xy) for name, xy in keeps.items()}
    boxes["oil hole note"] = _note_box(
        drawing.OIL_HOLE_NOTE, drawing.OIL_HOLE_CALLOUT, height=drawing.NOTE_HEIGHT
    )
    boxes["toothspace callout"] = _note_box(
        spec.TOOTH_SPACE_CALLOUT, drawing.TOOTH_SPACE_CALLOUT_XY,
        height=drawing.TOOTH_SPACE_CALLOUT_CHAR_HEIGHT,
    )
    boxes["outside caption"] = _note_box(drawing.LEFT_CAPTION, drawing.LEFT_CAPTION_XY)
    boxes["tooth edge note"] = _note_box(
        drawing.TOOTH_EDGE_LEADER_NOTE, drawing.TOOTH_EDGE_NOTE_XY, height=0.0025
    )
    boxes["manufacturing notes"] = _note_box(
        spec.DRAWING_NOTES, drawing.NOTES_XY, height=0.0025
    )
    data_box = estimate_text_box(
        spec.GEAR_DATA,
        anchor=drawing.GEAR_DATA_XY,
        height=drawing.GEAR_DATA_CHAR_HEIGHT,
        advance_ratio=_ADVANCE,
        line_spacing=_LINE_SPACING,
    )
    assert data_box is not None
    boxes["gear data"] = data_box
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
        for view, outline in views.items():
            assert box.gap(outline) >= ARROW_TEXT_CLEARANCE_M, (name, view)
    for (a, box_a), (b, box_b) in itertools.combinations(views.items(), 2):
        assert box_a.gap(box_b) >= 0.010, (a, b)
    inline = {
        name: anchor for name, anchor in drawing.RIGHT_KEEP.items() if _inline(anchor)
    }
    assert set(inline) == {"OutsideDia", "BossDia"}
    for name in inline:
        half = _NOMINAL[name] / 2.0 * s
        assert axis_y - half < boxes[name].ymin, name
        assert boxes[name].ymax < axis_y + half, name
    assert inline["OutsideDia"][0] < rear_x
    assert inline["BossDia"][0] > nose_x
    # The flat's value and mate hang below the section right of the nose,
    # under the boss's lower extension line and left of its text; its
    # extension lines stop short of the boss's text.
    flat = boxes["FlatToAxis"]
    flat_x = drawing.RIGHT_KEEP["FlatToAxis"][0]
    assert flat.ymax + ARROW_TEXT_CLEARANCE_M < axis_y - spec.BOSS_DIA / 2.0 * s
    assert flat.xmin > nose_x + ARROW_TEXT_CLEARANCE_M
    assert flat_x + 2.0 * ARROW_TEXT_CLEARANCE_M < boxes["BossDia"].xmin


# The native section caption, "SECTION B-B" over its scale, stands 16.5 mm
# tall and is placed by its top centre; the B sheet's title block stands up
# to 64.9 mm (test_crank_drive_gear_drawing, test_rocker_arm_support_drawing).
_CAPTION_HEIGHT = 0.0165
_TITLE_BLOCK_TOP = 0.0649


def _assert_rows_stack(
    rows: dict[str, tuple[float, float]], station_x, rear_x: float, left_of_rear: set[str]
) -> list[str]:
    """Each row stands farther out than every shorter one, its text crosses
    no outer row's extension line and stands clear under the row above, and
    the named texts stand left of the rear face."""
    by_row = sorted(rows, key=lambda n: -rows[n][1])
    assert [_NOMINAL[n] for n in by_row] == sorted(_NOMINAL[n] for n in by_row)
    boxes = [_printed_box(name, rows[name]) for name in by_row]
    for i, name in enumerate(by_row):
        for outer in by_row[i + 1 :]:
            for x in (rear_x, station_x(_NOMINAL[outer])):
                clear = (
                    x <= boxes[i].xmin - ARROW_TEXT_CLEARANCE_M
                    or x >= boxes[i].xmax + ARROW_TEXT_CLEARANCE_M
                )
                assert clear, (name, outer)
        if name not in left_of_rear:
            own = (rear_x, station_x(_NOMINAL[name]))
            assert own[0] + ARROW_TEXT_CLEARANCE_M < boxes[i].xmin, name
            assert boxes[i].xmax + ARROW_TEXT_CLEARANCE_M < own[1], name
    for upper, lower in zip(boxes, boxes[1:]):
        assert lower.ymax + TEXT_CLEARANCE_HEIGHTS * _CAP_M < upper.ymin
    for name in left_of_rear:
        assert _printed_box(name, rows[name]).xmax + ARROW_TEXT_CLEARANCE_M < rear_x
    return by_row


def test_baseline_lengths_stack_without_crossing_extension_lines() -> None:
    """The section's lengths stack below it (the tooth length's and the flat
    end's texts, with their mates, left of the rear face); the caption hangs
    below them, clear of the title block."""
    rear_x = drawing._side_x(0.0)
    bottom = drawing.RIGHT_CENTER[1] - drawing.HALF_OD
    rows = {
        name: xy
        for name, xy in drawing.RIGHT_KEEP.items()
        if xy[1] < bottom and not name.endswith("Dia") and name != "FlatToAxis"
    }
    assert set(rows) == {"FaceWidth", "FlatEnd", "OverallLength"}
    by_row = _assert_rows_stack(rows, drawing._side_x, rear_x, {"FaceWidth", "FlatEnd"})
    assert _printed_box(by_row[0], rows[by_row[0]]).ymax < bottom - 0.002
    _, cap_top = drawing.SECTION_CAPTION
    lowest = _printed_box(by_row[-1], rows[by_row[-1]])
    assert cap_top < lowest.ymin - TEXT_CLEARANCE_HEIGHTS * _CAP_M
    assert cap_top - _CAPTION_HEIGHT > _TITLE_BLOCK_TOP + 0.002


def test_cutter_rows_stack_below_the_outside_view() -> None:
    """2026-10-24 ENFORCE review: the section plane passes through teeth, so
    the full-depth station and the run-out limit had no edge there.  They
    print on the outside view, which looks along the section's direction
    (*Left: rear face left), their texts left of its rear face, the lower row
    clear of the title block."""
    scale = drawing.VIEW_SCALE[0] / 1000.0
    rear_x = drawing.LEFT_CENTER[0] - spec.OVERALL_LENGTH / 2.0 * scale
    rows = dict(drawing.LEFT_KEEP)
    assert set(rows) == {"FullDepth", "CutterRunout"}
    by_row = _assert_rows_stack(
        rows, lambda z: rear_x + z * scale, rear_x, {"FullDepth", "CutterRunout"}
    )
    bottom = drawing.LEFT_CENTER[1] - drawing.HALF_OD
    assert _printed_box(by_row[0], rows[by_row[0]]).ymax < bottom - 0.002
    # The lowest row's dimension line runs just under its text.
    lowest = _printed_box(by_row[-1], rows[by_row[-1]])
    assert lowest.ymin - 0.002 > _TITLE_BLOCK_TOP
    title_left = DRAWING_TEMPLATES[DRAWINGS_BY_NAME["pd_transgear_feed_pinion"].layout].title_block_left_m
    assert rear_x > title_left
    assert drawing.TANGENT_EDGES_HIDDEN == 0  # swTangentEdgesHidden


def test_root_reads_across_two_gap_floors_on_the_rear_view() -> None:
    """The rear-face view shows the full-depth gaps; the root's text stands
    on a gap bisector, so its diameter's arrows land on two gap floors."""
    cx, cy = drawing.REAR_CENTER
    x, y = drawing.REAR_KEEP["RootDia"]
    angle = math.degrees(math.atan2(y - cy, x - cx)) % 360.0
    # *Back mirrors model x: model gaps at 15° + k·30° print at 165° - k·30°.
    pitch = 360.0 / spec.TEETH
    offset = (angle - pitch / 2.0) % pitch
    assert min(offset, pitch - offset) < 1e-9
    assert math.hypot(x - cx, y - cy) > drawing.HALF_OD + 0.015
    assert _printed_text("RootDia").strip() == (
        f"ROOT ENVELOPE \u00d8{_inch(spec.ROOT_DIA_MIN, spec.ROOT_DIA_PLACES)} min."
    )


# The finish symbol's ink from its insertion point, measured with 2.5 mm text
# on run 20261001T110844152Z: the leader leaves the shoulder's right end (the
# bent leader's fixed 6.35 mm shelf), the "Ra" text's lower right corner
# stands up and right of the root, the V's left arm reaches left of it and
# the bar over the text tops the ink.  All but the shelf scale with the text:
# run 20261002T153039266Z's 6.35 mm text printed 2.54 times as far out.
_FINISH_MEASURED_HEIGHT = 0.0025
_FINISH_SHOULDER_DX = 0.0064
_FINISH_TEXT_CORNER = (0.0147, 0.0042)
_FINISH_LEFT_DX = -0.0021
_FINISH_TOP_DY = 0.0072


def _finish_ink() -> tuple[float, float, float, float]:
    """The finish's text right, text bottom, ink left and ink top."""
    sx, sy = drawing.FINISH_SYMBOL
    k = drawing.FINISH_CHAR_HEIGHT / _FINISH_MEASURED_HEIGHT
    return (
        sx + _FINISH_TEXT_CORNER[0] * k,
        sy + _FINISH_TEXT_CORNER[1] * k,
        sx + _FINISH_LEFT_DX * k,
        sy + _FINISH_TOP_DY * k,
    )


def test_finish_leader_climbs_clear_of_its_own_text() -> None:
    """Run 20261001T110844152Z's finish leader climbed through its own "Ra
    1.6" (leader-through-own-text); it now passes right of the text, and the
    symbol stands clear of the end view and inside the border."""
    sx, sy = drawing.FINISH_SYMBOL
    text_right, text_bottom, ink_left, _ = _finish_ink()
    start = (sx + _FINISH_SHOULDER_DX, sy)
    end = drawing.FINISH_ATTACH
    assert end[0] > start[0] and end[1] > text_bottom
    rise = (text_bottom - start[1]) / (end[1] - start[1])
    leader_x = start[0] + (end[0] - start[0]) * rise
    assert leader_x - text_right >= ARROW_TEXT_CLEARANCE_M
    end_view_left = drawing.FRONT_CENTER[0] - drawing.HALF_OD
    assert end_view_left - text_right >= ARROW_TEXT_CLEARANCE_M
    assert ink_left > drawing.SHEET_INNER_BORDER[0]


def test_finish_leader_stays_above_the_span_extension_lines() -> None:
    """Stack6 review: the finish leader, landing at -135°, crossed the
    two-tooth span's upper extension line. That line runs along the lower-left
    diagonal, 2.7 mm above-left of the bore centre (stack6 render). Both
    leader ends must stand farther above-left of that diagonal."""
    cx, cy = drawing.FRONT_CENTER
    sx, sy = drawing.FINISH_SYMBOL
    for x, y in ((sx + _FINISH_SHOULDER_DX, sy), drawing.FINISH_ATTACH):
        # Signed distance above-left of the 45° line through the centre.
        assert ((y - cy) - (x - cx)) / math.sqrt(2.0) > 0.0027 + 0.001


def test_finite_gear_data_and_model_consume_one_tooth_system() -> None:
    from _gear_fit_limits import gear_tip_band_mm

    assert spec.TEETH == spec.CUTTER_TEMPLATE.reference_teeth == 12
    assert spec.OUTSIDE_DIA_BAND == gear_tip_band_mm("standard")
    assert part.STOCK_PROFILE is spec.STOCK_PROFILE
    assert (part.TEETH, part.DP, part.PRESSURE_ANGLE_DEG) == (
        spec.TEETH, spec.DIAMETRAL_PITCH, spec.PRESSURE_ANGLE_DEG
    )
    assert spec.PITCH_DIA == pytest.approx(spec.TEETH * spec.MODULE_MM)
    assert spec.WHOLE_DEPTH == pytest.approx(
        spec.OUTSIDE_DIA / 2.0 - spec.STOCK_PROFILE.root_radius_min_mm
    )
    for profile in spec.manufactured_profiles():
        assert profile.blank_radius_mm <= profile.support_radius_max_mm
        assert profile.tip_land_mm >= 0.25 * spec.MODULE_MM
        assert 2.0 * profile.root_radius_min_mm >= spec.ROOT_DIA_MIN
    lower, upper = sorted(spec.SPAN_LIMITS)
    for label, value in (
        ("NUMBER OF TEETH", f"{spec.TEETH}"),
        ("DIAMETRAL PITCH", f"{spec.DIAMETRAL_PITCH:.2f}"),
        ("PRESSURE ANGLE", f"{spec.PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (REF)", _inch(spec.PITCH_DIA, 4)),
        ("WHOLE DEPTH (REF)", _inch(spec.WHOLE_DEPTH, 4)),
        (
            "CUTTER",
            f"#{spec.CUTTER_NUMBER}, "
            f"{spec.CUTTER_TOOTH_RANGE[0]}-{spec.CUTTER_TOOTH_RANGE[1]}T",
        ),
        (
            f"SPAN OVER {spec.SPAN_TEETH} TEETH",
            f"{_inch(lower, spec.SPAN_PLACES)}-{_inch(upper, spec.SPAN_PLACES)}",
        ),
        ("MATES WITH", f"PLATEN RACK {spec.RACK_NUMBER}"),
    ):
        assert f"{label}:  {value}" in spec.GEAR_DATA
    assert len(spec.GEAR_DATA.splitlines()) == 9
    assert "PROFILE SHIFT" not in spec.GEAR_DATA
    # A form-cut tooth is a translated involute: its pitch thickness does
    # not follow the generated-involute span relation, so only the span
    # (the inspected quantity) is printed.
    assert "CIRCULAR THICKNESS" not in spec.GEAR_DATA
    assert part.GEAR_DATA == spec.GEAR_DATA


def test_tangent_span_is_real_supported_flank_inspection() -> None:
    lower, upper = spec.SPAN_LIMITS
    for profile in spec.manufactured_profiles():
        a, b = span_contact_points_mm(profile, spec.SPAN_TEETH)
        measured = math.dist(a, b)
        actual = profile.tangent_span_mm(spec.SPAN_TEETH)
        assert measured == pytest.approx(actual)
        allowance = 4.0 * profile.geometry_error_bound_mm
        assert lower - allowance <= actual <= upper + allowance
        assert max(math.hypot(*a), math.hypot(*b)) <= profile.blank_radius_mm
    assert spec.SPAN_NOMINAL == spec.STOCK_PROFILE.tangent_span_mm(spec.SPAN_TEETH)
    assert spec.SPAN_NOMINAL + spec.SPAN_BAND[1] == pytest.approx(lower)
    assert spec.SPAN_NOMINAL + spec.SPAN_BAND[0] == pytest.approx(upper)
    assert spec.SPAN_TOL_TYPE == 3
    assert "BISECTOR" not in spec.DRAWING_NOTES  # method, not requirement
    assert part.author_span is stock_native.author_span
    assert part.apply_span_limits is stock_native.apply_span_limits


def test_rack_datum_setup_uses_actual_translated_stock_form() -> None:
    alpha = math.radians(spec.PRESSURE_ANGLE_DEG)
    datum = (
        2.0 * (spec.RACK_AXIS_DISTANCE - spec.PITCH_DIA / 2.0) * math.tan(alpha)
        - 2.0 * spec.RADIAL_SETTING * math.sin(alpha + math.pi / spec.TEETH)
        / math.cos(alpha)
    )
    assert datum == pytest.approx(spec.RACK_BACKLASH)
    assert spec.RACK_BACKLASH_RANGE[0] <= datum <= spec.RACK_BACKLASH_RANGE[1]


def test_actual_partial_endcut_has_resolved_volume_and_step_material() -> None:
    lower, upper = spec.endcut_volume_bounds_mm3()
    assert 0.0 < lower <= upper
    assert upper - lower <= spec.ENDCUT_VOLUME_ERROR_MM3 + 8 * math.ulp(upper)
    assert upper < spec.STOCK_PROFILE.gap_area_mm2 * (spec.FACE_WIDTH - spec.FULL_DEPTH)
    inner = spec.BOSS_DIA / 2.0
    outer = spec.OUTSIDE_DIA / 2.0
    annulus = math.pi * (outer * outer - inner * inner)
    area_lo, area_hi = spec.step_seat_area_bounds_mm2(inner, outer)
    assert 0.0 < area_lo <= area_hi < annulus
    assert area_hi - area_lo <= spec.STEP_SEAT_AREA_ERROR_MM2 + 8 * math.ulp(area_hi)
    with pytest.raises(ValueError, match="station"):
        spec.step_seat_area_bounds_mm2(inner, outer, station_mm=spec.FULL_DEPTH - 1.0)


def test_certified_single_pin_contacts_real_finite_flanks() -> None:
    for profile in spec.manufactured_profiles():
        contact = toothspace_gauge_contact_mm(profile, spec.TOOTHSPACE_GAUGE_DIA_MM)
        assert profile.flank_parameter_min < contact.parameter < profile.flank_parameter_max
        assert contact.root_air_mm > 0.0
        assert contact.tip_air_mm > 0.0
        assert contact.center_radius_error_bound_mm >= profile.geometry_error_bound_mm
        x, y = contact.flank_point_mm
        radius = spec.TOOTHSPACE_GAUGE_DIA_MM / 2.0
        assert math.hypot(contact.center_radius_mm - x, y) == pytest.approx(radius)
        assert contact.center_radius_mm - radius > profile.root_radius_max_mm
    for invalid_diameter in (0.0, -spec.TOOTHSPACE_GAUGE_DIA_MM, math.inf, math.nan):
        with pytest.raises(ValueError):
            toothspace_gauge_contact_mm(spec.STOCK_PROFILE, invalid_diameter)
    assert "CERTIFIED" not in spec.GEAR_DATA and "STATION" not in spec.GEAR_DATA


def test_toothspace_control_is_source_owned_and_feature_local() -> None:
    grade = toothspace_runout_tir_mm()
    assert spec.TOOTH_SPACE_RUNOUT_TIR_MM == grade
    assert math.isfinite(grade) and grade > 0.0
    assert part.TOOTH_SPACE_CALLOUT is spec.TOOTH_SPACE_CALLOUT
    assert part.TOOTH_SPACE_CALLOUT_PROPERTY == spec.TOOTH_SPACE_CALLOUT_PROPERTY
    assert drawing.TOOTH_SPACE_CALLOUT_PROPERTY == spec.TOOTH_SPACE_CALLOUT_PROPERTY
    assert spec.TOOTH_SPACE_CALLOUT.splitlines() == [
        f"TOOTH SPACE RUNOUT {spec.TOOTH_SPACE_RUNOUT_TIR_TEXT} TIR TO {spec.BORE_DATUM}",
        f"\u00d8{_inch(spec.TOOTHSPACE_GAUGE_DIA_MM, 4)} PIN, ALL {spec.TEETH} SPACES",
    ]
    # The printed TIR never exceeds the grade it controls.
    assert float(spec.TOOTH_SPACE_RUNOUT_TIR_TEXT) * 25.4 <= grade
    # Indexing is held by the dividing head; no index inspection is printed.
    assert max(map(len, spec.TOOTH_SPACE_CALLOUT.splitlines())) <= 70
    assert "CANDIDATE" not in spec.TOOTH_SPACE_CALLOUT
    assert "TIR" not in spec.DRAWING_NOTES
    assert len(spec.DRAWING_NOTES.splitlines()) <= 4
    assert drawing.add_toothspace_callout is stock_drawing.add_toothspace_callout
    assert drawing.STOCK_PROFILE is spec.STOCK_PROFILE
    assert drawing.TOOTHSPACE_GAUGE_DIA_MM == spec.TOOTHSPACE_GAUGE_DIA_MM
    assert drawing.TOOTH_SPACE_INSPECTION_PHASE_RAD == spec.TOOTH_SPACE_INSPECTION_PHASE_RAD
    assert part.TOOTH_SPACE_INSPECTION_PHASE_RAD == spec.TOOTH_SPACE_INSPECTION_PHASE_RAD
    assert drawing.TOOTH_SPACE_INSPECTION_END_MM == spec.TOOTH_SPACE_INSPECTION_END_MM


def test_toothspace_callout_lands_on_the_rear_face_full_depth_flank() -> None:
    """Run 11: the end view looks at the step face, whose run-out gaps are
    partial depth, and the pick found a flank 0.23 mm off the contact. The
    straight pass is full depth at the rear face, so the callout lands on a
    *Back view of it, in free sheet below the section."""
    assert spec.TOOTH_SPACE_INSPECTION_END_MM == 0.0
    assert spec.FULL_DEPTH > spec.TOOTH_SPACE_INSPECTION_END_MM
    s = drawing.VIEW_SCALE[0] / 1000.0
    cx, cy = drawing.REAR_CENTER
    rear = Box(cx - drawing.HALF_OD, cy - drawing.HALF_OD, cx + drawing.HALF_OD, cy + drawing.HALF_OD)
    left, bottom, right, top = drawing.SHEET_INNER_BORDER
    assert rear.xmin > left and rear.ymin > bottom
    title_left = DRAWING_TEMPLATES[DRAWINGS_BY_NAME["pd_transgear_feed_pinion"].layout].title_block_left_m
    assert rear.xmax + 0.010 < title_left
    caption_bottom = drawing.SECTION_CAPTION[1] - _CAPTION_HEIGHT
    assert rear.ymax + 0.010 < caption_bottom
    # The rear-face extension lines stand right of the view and its leader.
    assert rear.xmax < drawing._side_x(0.0)
    # Run 12: the outline runs ~6 mm past the tip circle, so the caption is
    # hung below the measured outline, not at a fixed point.
    assert drawing.CAPTION_SETTLE_M >= 0.0006
    outline_bottom = cy - drawing.HALF_OD - 0.0065  # run 12's measured margin
    caption_height = 0.0047
    assert outline_bottom - drawing.REAR_CAPTION_GAP_M - caption_height - drawing.CAPTION_SETTLE_M > bottom
    # *Back mirrors model x. The chosen gap's contact sits on the view's upper
    # side, its flank facing up-left into its own gap, toward the callout.
    assert 0 <= drawing.TOOTH_SPACE_GAP_INDEX < spec.TEETH
    angle = spec.TOOTH_SPACE_INSPECTION_PHASE_RAD + drawing.TOOTH_SPACE_GAP_INDEX * 2.0 * math.pi / spec.TEETH
    contact = toothspace_gauge_contact_mm(spec.STOCK_PROFILE, spec.TOOTHSPACE_GAUGE_DIA_MM)
    x, y = stock_drawing._rotate(contact.flank_point_mm, angle)
    landing = (cx - x * s, cy + y * s)
    gap_centre = math.pi - angle
    contact_angle = math.atan2(landing[1] - cy, landing[0] - cx)
    assert contact_angle < gap_centre  # the gap opens counter-clockwise of the contact
    note = _note_box(spec.TOOTH_SPACE_CALLOUT, drawing.TOOTH_SPACE_CALLOUT_XY,
                     height=drawing.TOOTH_SPACE_CALLOUT_CHAR_HEIGHT)
    toward_note = math.atan2(note.ymin - landing[1], note.xmax - landing[0])
    assert contact_angle < toward_note < contact_angle + math.pi / 2.0


def test_end_view_is_the_sections_third_angle_left_view(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """2026-10-27 ENFORCE review (r1, r3): a nose view stood left of the
    section, whose rear face stands left.  The end view now sees the rear
    face, and its cutting line runs top to bottom so the arrows point left,
    model +X in that view: the section keeps its rear face left (codjiflo P3
    on ebde256dc: the build's own call is checked, not just the constants)."""
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from _test_stubbed_build import offline_adapter, stub_seat

    source = tmp_path / "source.SLDPRT"
    source.write_bytes(b"")
    monkeypatch.setattr(drawing, "SOURCE", source)
    seat = stub_seat(monkeypatch, drawing)
    left, bottom, right, top = drawing.SHEET_INNER_BORDER
    seat._early_bound.return_value.GetExtent.return_value = (
        left + 0.01, bottom + 0.01, 0.0, right - 0.01, top - 0.01, 0.0
    )
    seat.new_project_drawing.return_value = (MagicMock(), MagicMock())
    seat.place_view.side_effect = lambda _adapter, path, view, x, y, scale: SimpleNamespace(
        orientation=view, centre=(x, y)
    )
    asyncio.run(drawing.build(offline_adapter()))

    (section,) = seat.create_section_view.call_args_list
    parent = section.args[1]
    assert (parent.orientation, parent.centre) == ("*Back", drawing.FRONT_CENTER)
    start, end = section.kwargs["line_start"], section.kwargs["line_end"]
    assert start[0] == end[0] == drawing.FRONT_CENTER[0]
    assert start[1] > drawing.FRONT_CENTER[1] + drawing.HALF_OD > drawing.FRONT_CENTER[1]
    assert end[1] < drawing.FRONT_CENTER[1] - drawing.HALF_OD
    assert section.kwargs["view_xy"] == drawing.RIGHT_CENTER
    assert drawing.FRONT_CENTER[1] == drawing.RIGHT_CENTER[1]
    assert drawing.FRONT_CENTER[0] < drawing._side_x(0.0) < drawing._side_x(spec.OVERALL_LENGTH)


def test_outside_view_crops_past_the_run_out_limit() -> None:
    """Runs 20261027T032128736Z..054041865Z (r1, r2): uncropped, the view drew
    a tooth-space line on to the boss, past the 13.80 MAX.  It is cropped just
    past the run-out limit, so both cutter stations' witnesses stay inside and
    the boss, which the section shows, is cut away."""
    left, foot, right, head = drawing.OUTSIDE_CROP_FENCE
    s = drawing.VIEW_SCALE[0] / 1000.0
    rear = drawing._LEFT_REAR_X
    assert left < rear
    for station in (spec.FULL_DEPTH, spec.CUTTER_RUNOUT_MAX):
        assert rear + station * s < right
    assert right < rear + (spec.FACE_WIDTH + 0.5) * s
    assert foot < drawing.LEFT_CENTER[1] - drawing.HALF_OD
    assert head > drawing.LEFT_CENTER[1] + drawing.HALF_OD


def test_the_cropped_outside_view_reads_as_partial_with_a_break_on_the_boss() -> None:
    """2026-10-28 ENFORCE review (r1, r2): the cropped view had no break line
    and no PARTIAL label, and the 13.80 MAX's extension line landed past the
    drawn end.  The caption names the view PARTIAL; a long-break line on the
    crop crosses the Ø8.2 boss past both outlines, so the MAX lands on the
    boss stub between the step and the break, clear of the break's Z."""
    assert drawing.LEFT_CAPTION.splitlines()[0] == "PARTIAL"
    caption = _note_box(drawing.LEFT_CAPTION, (0.0, 0.0))
    assert caption.xmax - caption.xmin <= drawing._LEFT_CAPTION_WIDTH
    s = drawing.VIEW_SCALE[0] / 1000.0
    ys = [y for y, _z in drawing.OUTSIDE_BREAK]
    zs = [z for _y, z in drawing.OUTSIDE_BREAK]
    # Straight ends on the crop, past both boss outlines.
    for y, z in (drawing.OUTSIDE_BREAK[0], drawing.OUTSIDE_BREAK[-1]):
        assert z == drawing.OUTSIDE_CROP_Z
        assert abs(y) > spec.BOSS_DIA / 2.0
    assert drawing._outside_sheet_xy(0.0, drawing.OUTSIDE_CROP_Z)[0] == pytest.approx(
        drawing.OUTSIDE_CROP_FENCE[2]
    )
    # The Z stays ahead of the step and the MAX, on the side of the axis away
    # from the facing gap's floor, from which the MAX's extension line drops.
    assert min(zs) > spec.CUTTER_RUNOUT_MAX > spec.FACE_WIDTH
    z_ys = [y for y, z in drawing.OUTSIDE_BREAK if z != drawing.OUTSIDE_CROP_Z]
    assert spec.GAP_FLOOR_WITNESS_Y < 0.0 < min(z_ys) and max(z_ys) < spec.BOSS_DIA / 2.0
    assert sorted(ys) == ys
    # The break stands clear of the MAX's extension line on the sheet.
    assert (drawing.OUTSIDE_CROP_Z - spec.CUTTER_RUNOUT_MAX) * s >= 0.0005


def test_tooth_edge_exception_is_flagged_at_the_teeth() -> None:
    """2026-10-27 ENFORCE review (r2, r3), rule 7: the 'do not break' exception
    to the title block's edge break reaches the teeth on a leader, not as a
    loose note.  The leader leaves its longer last row and lands on the tip
    land of the gear-end view's upper-left tooth, a tooth in the mirrored
    *Back view (model 30°), outside the root's dimension."""
    rows = drawing.TOOTH_EDGE_LEADER_NOTE.split("\n")
    assert " ".join(rows) == spec.TOOTH_EDGE_NOTE
    assert len(rows) == 2 and len(rows[0]) < len(rows[1])
    assert spec.TOOTH_EDGE_NOTE not in spec.DRAWING_NOTES
    scale = drawing.VIEW_SCALE[0] / 1000.0
    dx = drawing.TOOTH_EDGE_ATTACH[0] - drawing.REAR_CENTER[0]
    dy = drawing.TOOTH_EDGE_ATTACH[1] - drawing.REAR_CENTER[1]
    radius = math.hypot(dx, dy) / scale
    assert spec.ROOT_DIA_MIN / 2.0 < spec.OUTSIDE_DIA / 2.0 - 0.1 < radius
    assert radius < spec.OUTSIDE_DIA / 2.0
    model_angle = (180.0 - math.degrees(math.atan2(dy, dx))) % 360.0
    assert model_angle % (360.0 / spec.TEETH) == pytest.approx(0.0, abs=1e-9)
    # The notes block hangs below the leader's note; the leader runs right,
    # to a tip beyond the note's end.
    note = _note_box(drawing.TOOTH_EDGE_LEADER_NOTE, drawing.TOOTH_EDGE_NOTE_XY, height=0.0025)
    assert note.xmax < drawing.TOOTH_EDGE_ATTACH[0]
    notes = _note_box(spec.DRAWING_NOTES, drawing.NOTES_XY, height=0.0025)
    assert notes.ymax < note.ymin
