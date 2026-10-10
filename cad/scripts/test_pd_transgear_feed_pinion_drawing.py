"""Offline contracts for the feed-pinion sleeve (MHA-PD-010) and its drawing."""

from __future__ import annotations

import itertools
import math
from pathlib import Path

import pytest

import _config
import build_pd_transgear_feed_pinion as part
import draw_pd_transgear_feed_pinion as drawing
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
    pinion_pitch_index_deviation_mm,
    pitch_index_measurement_uncertainty_mm,
    toothspace_runout_tir_mm,
)
from _printed_tolerance import printed_band_mm
from _drawing_marks import _tolerance_places
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
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked


def test_sheet_authors_no_manufacturing_value() -> None:
    # Rule 2: places and bands come from the part; the sheet reads them back.
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert not drawing_specification_violations(source, filename=drawing.__file__)


def test_bands_come_from_named_spec_constants() -> None:
    assert model_toleranced_dimensions(part) == {
        ("FlatProfile", "FlatEnd"): "STATION_TOL",
        ("SleeveProfile", "OverallLength"): "STATION_TOL",
        ("SleeveProfile", "FullDepth"): "FULL_DEPTH_BAND",
        ("SleeveProfile", "BoreDia"): "*BORE_DEVIATIONS",
        ("SleeveProfile", "BossDia"): "*BOSS_DIA_DEVIATIONS",
        ("FlatProfile", "FlatToAxis"): "*FLAT_TO_AXIS_DEVIATIONS",
        ("SleeveProfile", "OutsideDia"): "*OUTSIDE_DIA_DEVIATIONS",
    }
    # A band tighter than its printed row needs a functional reason (rule 12):
    # stations' ±0.05, the contact-critical tip class, boss h6 and flat
    # 0/-0.015 bands have functional reasons tighter than their printed rows.
    assert spec.STATION_TOL < printed_band_mm(spec.STATION_PLACES)
    by_name = spec.DRAWING_PRECISION_BY_NAME
    for name, band in (
        ("OutsideDia", spec.OUTSIDE_DIA_BAND),
        ("BossDia", spec.BOSS_DIA_BAND),
        ("FlatToAxis", spec.FLAT_TO_AXIS_BAND),
    ):
        assert band[0] - band[1] < printed_band_mm(by_name[name]), name


def test_root_prints_as_the_cutter_depth_floor() -> None:
    # swTolType_e.swTolMIN (offline API docs) prints the nominal then "MIN".
    assert spec.ROOT_DIA_TOL_TYPE == 5
    places = spec.DRAWING_PRECISION_BY_NAME["RootDia"]
    expected_root = 2.0 * spec.STOCK_PROFILE.root_radius_min_mm
    corners = spec.manufactured_profiles()
    minimum = min(2.0 * profile.root_radius_min_mm for profile in corners)
    expected_floor = math.floor(minimum * 10**places) / 10**places
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
    assert spec.DISC_FRONT_STATION == pytest.approx(17.25)
    assert spec.DISC_FRONT_STATION_BAND == pytest.approx(
        printed_band_mm(spec.FACE_WIDTH_PLACES) + hub.SPIGOT_LENGTH_BAND
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
    assert spec.STEP_FACE_PERPENDICULARITY == 0.005
    assert spec.STEP_FACE_PERPENDICULARITY_ZONE_DIA == spec.OUTSIDE_DIA
    assert spec.GEOMETRIC_TOLERANCES_MM == {
        "step face perpendicularity to bore": "0.005"
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
    assert spec.FULL_DEPTH_MAX < spec.FACE_WIDTH - printed_band_mm(
        spec.FACE_WIDTH_PLACES
    )
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
    assert spec.RUNOUT_DISC_CLEARANCE == 0.05
    limit = spec.DISC_REAR_MIN - spec.RUNOUT_DISC_CLEARANCE
    assert spec.CUTTER_RUNOUT_END_WORST <= spec.CUTTER_RUNOUT_MAX <= limit
    # The physical cutter radius is located by deepest ground X, not the
    # nonconcentric root norm used to inspect the material's minimum wall.
    assert spec.RUNOUT_RISE_WORST == pytest.approx(
        (spec.BOSS_DIA + spec.BOSS_DIA_BAND[0]) / 2.0 - spec.ROOT_DEPTH_X_MIN
    )
    # Negative control derives an oversized cutter from the actual station
    # limit instead of pinning a formerly acceptable catalog diameter.
    length = spec.CUTTER_RUNOUT_MAX - spec.FULL_DEPTH_MAX
    rise = spec.RUNOUT_RISE_WORST
    big = 1.01 * (length * length + rise * rise) / rise
    assert (
        spec.FULL_DEPTH_MAX + spec.cutter_runout(big, spec.RUNOUT_RISE_WORST)
        > spec.CUTTER_RUNOUT_MAX
    )


def test_cutter_stations_are_native_banded_model_dimensions() -> None:
    """Codex P2 on R9-67: the full-depth window and the run-out limit print as
    the model's own dimensions, band and places on the part, not as numbers
    frozen into note text (policy rules 2 and 7)."""
    assert {"FullDepth", "CutterRunout"} <= spec.DRAWING_DIMENSIONS["SleeveProfile"]
    places = spec.DRAWING_PRECISION_BY_NAME
    assert places["FullDepth"] == spec.FULL_DEPTH_PLACES == 3
    assert places["CutterRunout"] == spec.CUTTER_RUNOUT_PLACES == 2
    # The window is the .XXX row's band; the run-out a MAX limit
    # (swTolType_e.swTolMAX) whose nominal is the limit it prints.
    assert spec.FULL_DEPTH_BAND == printed_band_mm(spec.FULL_DEPTH_PLACES)
    assert spec.CUTTER_RUNOUT_TOL_TYPE == 6
    lower, upper = spec.CUTTER_RUNOUT_DEVIATIONS
    assert upper == 0.0
    assert spec.CUTTER_RUNOUT_MAX + lower == pytest.approx(spec.FULL_DEPTH_MIN)
    # No number the model owns is retyped into the notes.
    lines = spec.DRAWING_NOTES.splitlines()
    for value in (f"{spec.FULL_DEPTH:.3f}", f"{spec.CUTTER_RUNOUT_MAX:.2f}"):
        assert value not in spec.DRAWING_NOTES, value
    # A shop note states requirements only: the cutter is method.
    assert lines == [spec.TOOTH_EDGE_NOTE, spec.FLAT_WALL_NOTE]
    assert max(len(line) for line in lines) <= 70
    # One-line names, printed before the value on its own row.
    for prefix in (spec.FULL_DEPTH_PREFIX, spec.CUTTER_RUNOUT_PREFIX):
        assert "\n" not in prefix and prefix.endswith(" ")


def test_flat_end_mill_reaches_the_end_wall_clear_of_the_hub() -> None:
    """The flat is cut by an end mill parallel to the sleeve axis, plunged
    from the nose: its flutes cover the longest flat with 0.5 to spare.  The
    wall stops nothing: the hub's flat starts a spigot length ahead of the
    step, ahead of the wall at every printed limit."""
    import pd_transgear_disc_hub_spec as hub

    assert spec.FLAT_LENGTH_MAX == pytest.approx(
        spec.FLAT_LENGTH + 2.0 * spec.STATION_TOL
    )
    assert spec.FLAT_CUTTER_FLUTE_MIN >= spec.FLAT_LENGTH_MAX + 0.5
    worst = (
        spec.FACE_WIDTH
        - printed_band_mm(spec.FACE_WIDTH_PLACES)
        + hub.SPIGOT_LENGTH_MIN
        - (spec.FLAT_END_STATION + spec.STATION_TOL)
    )
    assert hub.FLAT_END_CLEARANCE_WORST == pytest.approx(worst)
    assert hub.FLAT_END_CLEARANCE_WORST > 0.0


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
    # and the sheet prints its worst case floored at two places.
    assert spec.WALL_FLOOR <= spec.FLAT_WALL_WORST < spec.WALL_TARGET
    assert spec.FLAT_WALL_WORST <= spec.FLAT_WALL
    assert spec.FLAT_WALL_PRINTED <= spec.FLAT_WALL_WORST
    assert f"{spec.FLAT_WALL_PRINTED:.2f} MIN" in spec.FLAT_WALL_NOTE
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
    assert "\n" not in note and len(note) <= 70
    assert note.startswith(f"\u00d8{hub.OIL_HOLE_DIA:.1f} OIL HOLE")
    assert f"WITH {spec.HUB_NUMBER}" in note
    assert f"MATE PIN {spec.PIN_NUMBER}" in spec.BORE_FIT_CALLOUT
    assert drawing.DIMENSION_CALLOUTS == {"BoreDia": spec.BORE_PROCESS_CALLOUT}


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
    "OutsideDia": _tolerance_places(*spec.OUTSIDE_DIA_DEVIATIONS),
}
# The stations the R9-5 ±0.05 band governs; the other lengths print bare
# under the title block's .XXX row.
_STATIONS = {"FlatEnd", "OverallLength"}


def _printed_text(name: str) -> str:
    """A kept dimension's whole text as the section prints it, padded with
    the space SolidWorks prints either side: its value, then the root's MIN,
    a station's band, or a stacked band, then any callout below."""
    value = f"{_NOMINAL[name]:.{spec.DRAWING_PRECISION_BY_NAME[name]}f}"
    if name.endswith("Dia"):
        value = f"\u00d8{value}"
    if name == "ToothSpan":
        lower, upper = spec.SPAN_LIMITS
        rows = [
            f"{spec.SPAN_PREFIX}{upper:.{spec.SPAN_PLACES}f}",
            f"{lower:.{spec.SPAN_PLACES}f}",
        ]
    elif name == "RootDia":
        rows = [f"{value} min."]
    elif name == "CutterRunout":
        rows = [f"{spec.CUTTER_RUNOUT_PREFIX}{value} max."]
    elif name == "FullDepth":
        rows = [f"{spec.FULL_DEPTH_PREFIX}{value} \u00b1{spec.FULL_DEPTH_BAND:.2f}"]
    elif name in _DEVIATIONS:
        lower, upper = _DEVIATIONS[name]
        places = _DEVIATION_PLACES[name]
        rows = [f"{upper:+.{places}f}", f"{value} {lower:+.{places}f}"]
    elif name in _STATIONS:
        rows = [f"{value} \u00b1{spec.STATION_TOL:.{spec.STATION_PLACES}f}"]
    else:
        rows = [value]
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


def test_section_values_and_bands_print_clear_of_each_other() -> None:
    """Machinist review of run 20261001T110844152Z: the tip, spigot and shank
    stood on one shelf above the section and their stacked bands printed over
    each other.  Every value with its band and callout keeps the layout
    audit's text air from every other text, clears both views, and stays
    inside the border; the inline diameters print between their own
    extension lines and off the part, and the flat's value between the axis
    and the flat, right of the nose."""
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
    boxes = {
        name: _printed_box(name, xy)
        for name, xy in {**drawing.FRONT_KEEP, **drawing.RIGHT_KEEP}.items()
    }
    boxes["oil hole note"] = _note_box(
        drawing.OIL_HOLE_NOTE, drawing.OIL_HOLE_CALLOUT, height=drawing.NOTE_HEIGHT
    )
    boxes["bore fit note"] = _note_box(
        spec.BORE_FIT_CALLOUT, drawing.BORE_FIT_NOTE, height=drawing.BORE_FIT_CHAR_HEIGHT
    )
    boxes["toothspace callout"] = _note_box(
        spec.TOOTH_SPACE_CALLOUT, drawing.TOOTH_SPACE_CALLOUT_XY,
        height=drawing.TOOTH_SPACE_CALLOUT_CHAR_HEIGHT,
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
        assert box.gap(end_view) >= ARROW_TEXT_CLEARANCE_M, name
    inline = {
        name: anchor for name, anchor in drawing.RIGHT_KEEP.items() if _inline(anchor)
    }
    assert set(inline) == {"OutsideDia", "RootDia", "BossDia"}
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
    assert [_NOMINAL[n] for n in left] == sorted(_NOMINAL[n] for n in left)
    assert inline["BossDia"][0] > nose_x
    # The flat's value sits between its extension lines (the axis and the
    # flat) right of the nose, and its axis extension line, which runs to its
    # dimension line, stops short of the boss's inline text.
    flat = boxes["FlatToAxis"]
    flat_x = drawing.RIGHT_KEEP["FlatToAxis"][0]
    assert axis_y - spec.FLAT_TO_AXIS * s < flat.ymin and flat.ymax < axis_y
    assert flat.gap(section) >= ARROW_TEXT_CLEARANCE_M
    assert flat_x + 2.0 * ARROW_TEXT_CLEARANCE_M < boxes["BossDia"].xmin


# The native section caption, "SECTION B-B" over its scale, stands 16.5 mm
# tall and is placed by its top centre; the B sheet's title block stands up
# to 64.9 mm (test_crank_drive_gear_drawing, test_rocker_arm_support_drawing).
_CAPTION_HEIGHT = 0.0165
_TITLE_BLOCK_TOP = 0.0649


def test_baseline_lengths_stack_without_crossing_extension_lines() -> None:
    """Each length's row stands farther out than every shorter one, and its
    text crosses no outer row's extension line (the prefixed cutter texts
    stand left of the rear face); the caption hangs below them, clear of the
    title block."""
    rear_x = drawing._side_x(0.0)
    bottom = drawing.RIGHT_CENTER[1] - drawing.HALF_OD
    rows = {
        name: xy
        for name, xy in drawing.RIGHT_KEEP.items()
        if xy[1] < bottom and not name.endswith("Dia")
    }
    assert set(rows) == {
        "FullDepth",
        "FaceWidth",
        "CutterRunout",
        "FlatEnd",
        "OverallLength",
    }
    by_row = sorted(rows, key=lambda n: -rows[n][1])
    assert [_NOMINAL[n] for n in by_row] == sorted(_NOMINAL[n] for n in by_row)
    for i, name in enumerate(by_row):
        box = _printed_box(name, rows[name])
        for outer in by_row[i + 1 :]:
            x = drawing._side_x(_NOMINAL[outer])
            clear = (
                x <= box.xmin - ARROW_TEXT_CLEARANCE_M
                or x >= box.xmax + ARROW_TEXT_CLEARANCE_M
            )
            assert clear, (name, outer)
    for name in ("FullDepth", "CutterRunout"):
        assert _printed_box(name, rows[name]).xmax + ARROW_TEXT_CLEARANCE_M < rear_x
    _, cap_top = drawing.SECTION_CAPTION
    lowest = _printed_box(by_row[-1], rows[by_row[-1]])
    assert cap_top < lowest.ymin - TEXT_CLEARANCE_HEIGHTS * _CAP_M
    assert cap_top - _CAPTION_HEIGHT > _TITLE_BLOCK_TOP + 0.002


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


def test_bore_fit_leader_passes_clear_of_the_finish() -> None:
    """Run 20261002T153039266Z's bore fit leader ran through the finish's "Ra
    1.6" (leader-through-text).  The note stands above its landing, so its
    leader never dips below the landing, and the finish's whole ink stands
    several millimetres below it."""
    landing_y = drawing.BORE_FIT_ATTACH[1]
    note = _note_box(spec.BORE_FIT_CALLOUT, drawing.BORE_FIT_NOTE)
    assert note.ymin > landing_y
    _, _, _, ink_top = _finish_ink()
    assert landing_y - ink_top >= 0.005


def test_finite_gear_data_and_model_consume_one_tooth_system() -> None:
    from _gear_fit_limits import gear_tip_band_mm

    # The independent feed count/master does not follow the reducer's choice.
    source = Path(spec.__file__).read_text(encoding="utf-8")
    assert "MESH_PINION_TEETH" not in source
    assert "PROFILE_SHIFT" not in source
    assert spec.TEETH == spec.CUTTER_TEMPLATE.reference_teeth == 12
    assert spec.OUTSIDE_DIA_BAND == gear_tip_band_mm("contact_critical")
    assert part.STOCK_PROFILE is spec.STOCK_PROFILE
    assert (part.TEETH, part.DP, part.PRESSURE_ANGLE_DEG) == (
        spec.TEETH, spec.DIAMETRAL_PITCH, spec.PRESSURE_ANGLE_DEG
    )
    assert spec.PITCH_DIA == pytest.approx(spec.TEETH * spec.MODULE_MM)
    assert spec.TOOTH_THICKNESS == pytest.approx(
        spec.STOCK_PROFILE.pitch_tooth_thickness_mm
    )
    assert spec.WHOLE_DEPTH == pytest.approx(
        spec.OUTSIDE_DIA / 2.0 - spec.STOCK_PROFILE.root_radius_min_mm
    )
    for profile in spec.manufactured_profiles():
        assert profile.blank_radius_mm <= profile.support_radius_max_mm
        assert profile.tip_land_mm >= 0.25 * spec.MODULE_MM
        assert 2.0 * profile.root_radius_min_mm >= spec.ROOT_DIA_MIN
    for label, value in (
        ("NUMBER OF TEETH", f"{spec.TEETH}"),
        ("DIAMETRAL PITCH", f"{spec.DIAMETRAL_PITCH:.2f}"),
        ("PRESSURE ANGLE", f"{spec.PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("TOTAL TEMPLATE TRANSLATION s (mm, REF)", f"{spec.RADIAL_SETTING:.3f}"),
        ("CIRCULAR THICKNESS AT PD (mm, REF)", f"{spec.TOOTH_THICKNESS:.3f}"),
        ("THICKNESS INSPECTION", f"NATIVE SPAN OVER {spec.SPAN_TEETH} TEETH"),
        (
            "CUTTER TEMPLATE",
            f"#{spec.CUTTER_NUMBER}, "
            f"{spec.CUTTER_TOOTH_RANGE[0]}-{spec.CUTTER_TOOTH_RANGE[1]}T; "
            f"{spec.CUTTER_TEMPLATE.reference_teeth}T MASTER",
        ),
    ):
        assert f"{label}:  {value}" in spec.GEAR_DATA
    assert "PROFILE SHIFT" not in spec.GEAR_DATA
    assert "FINITE TRANSLATED STOCK FORM, NOT x" in spec.GEAR_DATA
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
        f"TOOTH SPACE RUNOUT {grade:.2f} TIR TO {spec.BORE_DATUM}",
        f"\u00d8{spec.TOOTHSPACE_GAUGE_DIA_IN:.4f} in PIN, ALL {spec.TEETH} SPACES",
        f"INDEX RANGE {spec.PITCH_INDEX_DEVIATION_MM:.2f} MAX",
    ]
    assert max(map(len, spec.TOOTH_SPACE_CALLOUT.splitlines())) <= 70
    assert "CANDIDATE" not in spec.TOOTH_SPACE_CALLOUT
    assert "TIR" not in spec.DRAWING_NOTES
    assert len(spec.DRAWING_NOTES.splitlines()) <= 4
    assert spec.GEAR_CONTACT_CLASS.upper() in spec.GEAR_DATA
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
    import inspect

    source = inspect.getsource(drawing.build)
    assert 'place_view(adapter, str(SOURCE), "*Back", *REAR_CENTER, scale=VIEW_SCALE)' in source
    assert "add_toothspace_callout(\n        adapter, rear," in source
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
    assert "_place_rear_caption(adapter, rear)" in source
    placer = inspect.getsource(drawing._place_rear_caption)
    assert "GetOutline" in placer and "GetExtent" in placer
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


def test_pitch_index_control_uses_quality_and_actual_reference_circle() -> None:
    grade = pinion_pitch_index_deviation_mm()
    uncertainty = pitch_index_measurement_uncertainty_mm()
    assert spec.PITCH_INDEX_DEVIATION_MM == grade
    assert spec.PITCH_INDEX_MEASUREMENT_UNCERTAINTY_MM == uncertainty
    assert spec.PITCH_INDEX_REFERENCE_RADIUS_MM == spec.PITCH_DIA / 2.0
    assert spec.PITCH_INDEX_STATIONS == tuple(range(spec.TEETH + 1))
    assert f"INDEX RANGE {grade:.2f} MAX" in spec.TOOTH_SPACE_CALLOUT
    # Uncertainty and the measuring method are internal, never printed.
    assert "U " not in spec.TOOTH_SPACE_CALLOUT and "WRAP" not in spec.TOOTH_SPACE_CALLOUT
    assert "PITCH INDEX" not in spec.DRAWING_NOTES


def test_pitch_index_receiving_pays_two_station_uncertainties() -> None:
    # Synthetic receiving inputs exercise the contract, not shop measurements.
    measured = dict.fromkeys(spec.PITCH_INDEX_STATIONS, 0.0)
    paid_uncertainty = 2.0 * spec.PITCH_INDEX_MEASUREMENT_UNCERTAINTY_MM
    headroom = spec.PITCH_INDEX_DEVIATION_MM - paid_uncertainty
    assert headroom > 0.0
    assert spec.require_pitch_index_errors_mm(measured) == pytest.approx(paid_uncertainty)
    measured[spec.TEETH // 2] = headroom / 2.0
    assert spec.require_pitch_index_errors_mm(measured) == pytest.approx(
        headroom / 2.0 + paid_uncertainty
    )
    # The wrap is an independent receiving station, not silently the first
    # space reused with an assumed perfect closure.
    measured[spec.TEETH] = spec.PITCH_INDEX_DEVIATION_MM
    with pytest.raises(ValueError, match="REJECT paid pitch/index range"):
        spec.require_pitch_index_errors_mm(measured)


@pytest.mark.parametrize("missing_station", (0, spec.TEETH // 2, spec.TEETH))
def test_pitch_index_receiving_requires_every_station_and_wrap(
    missing_station: int,
) -> None:
    measured = dict.fromkeys(spec.PITCH_INDEX_STATIONS, 0.0)
    del measured[missing_station]
    with pytest.raises(ValueError, match="every specified station exactly once"):
        spec.require_pitch_index_errors_mm(measured)


@pytest.mark.parametrize("invalid_error", (True, math.inf, -math.inf, math.nan))
def test_pitch_index_receiving_refuses_nonfinite_or_boolean_errors(
    invalid_error: float | bool,
) -> None:
    measured = dict.fromkeys(spec.PITCH_INDEX_STATIONS, 0.0)
    measured[spec.TEETH // 2] = invalid_error
    with pytest.raises(ValueError, match="finite numeric millimetres"):
        spec.require_pitch_index_errors_mm(measured)
