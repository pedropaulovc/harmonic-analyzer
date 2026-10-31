"""Offline contract checks for the platen-clip manufacturing drawing (MHA-PD-03)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import build_pd_platen_clip as clip
import draw_pd_platen_clip as draw
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from _hole_spec import THREAD_MAJOR_MM
from _printed_tolerance import printed_band_mm
from machinist_exceptions import load_exceptions

CONFIG_ROOT = Path(__file__).resolve().parents[1] / "config"

BORDER = (0.0127, 0.0127, 0.4191, 0.2667)
TITLE_BLOCK = (0.216, 0.0127, 0.4191, 0.066)


def _inside(xy, box) -> bool:
    return box[0] <= xy[0] <= box[2] and box[1] <= xy[1] <= box[3]


def test_registry_row_names_the_clip_sheet():
    row = DRAWINGS_BY_NAME["pd_platen_clip"]
    assert row.part == "pd_platen_clip"
    assert row.script_name == "draw_pd_platen_clip.py"
    assert row.layout is DrawingLayout.LANDSCAPE
    assert draw.PART_STEM == "pd-platen-clip"
    assert draw.OUTPUTS.pdf == row.outputs["pdf"]
    assert "draw_pd_platen_clip.py" in PRECISION_MIGRATED_DRAWINGS


def test_views_keep_exactly_the_marked_dimensions_once():
    names = [*draw.FRONT_KEEP, *draw.TOP_KEEP]
    assert len(names) == len(set(names))
    assert set(names) == set().union(*clip.DRAWING_DIMENSIONS.values())
    assert set(draw.DIMENSION_AFFIXES) <= set(names)
    assert set(draw.DIMENSION_CALLOUTS) <= set(names)
    assert set(draw.OFFSET_TEXT) <= set(names)
    assert set(clip.DRAWING_PRECISION_BY_NAME) == set(names)


def test_references_print_parenthesised_with_counts_outside():
    for name in clip.REFERENCE_DIMENSIONS:
        prefix, suffix = draw.DIMENSION_AFFIXES[name]
        assert "(" in prefix and suffix == ")", name
    assert draw.DIMENSION_AFFIXES["BendR5"] == ("6X (R", ")")
    assert draw.DIMENSION_AFFIXES["FlatFinger"] == ("2X (", ")")
    assert draw.DIMENSION_AFFIXES["EndR1"] == ("2X R", "")
    # Controlling sizes print bare.
    for name in ("Length", "RailWidth", "OverallWidth", "SlitWidth", "CrestRise"):
        assert ")" not in draw.DIMENSION_AFFIXES.get(name, ("", ""))[1], name


def test_hole_pattern_prints_three_places_and_widths_two():
    places = clip.DRAWING_PRECISION_BY_NAME
    for name in ("LeftX", "RightX", "LeftZ"):
        assert places[name] == 3, name
    # Owner ruling 2026-10-15 (default D), adjusted per rule 21: the screw
    # rail's width drops to .XX; the hole row stays .XXX for pattern float.
    for name in ("RailWidth", "OverallWidth", "SlitWidth"):
        assert places[name] == 2, name
    # The bow stations that coincide with the hole stations spell them alike.
    assert places["TangentX1"] == places["LeftX"]
    assert places["TangentX8"] == places["RightX"]
    assert places["TangentX4"] == places["BridgeX0"]
    assert places["TangentX5"] == places["BridgeX1"]


def test_far_end_ligament_spends_the_length_band():
    band = printed_band_mm(3, unit=clip.UNIT)
    far_edge = clip.CLIP_LENGTH - printed_band_mm(clip.LENGTH_PLACES, unit=clip.UNIT)
    hole_far_max = clip.CLIP_LENGTH - clip.HOLE_INSET + band
    expected = far_edge - hole_far_max - clip.HOLE_DIA_MAX / 2.0
    assert clip.FAR_END_LIGAMENT_MIN == pytest.approx(expected)
    assert clip.FAR_END_LIGAMENT_MIN >= clip.LIGAMENT_FLOOR


def test_slit_keeps_the_photographed_gap_at_the_printed_worst_case():
    narrowest = clip.NOTCH_WIDTH - printed_band_mm(clip.SLIT_PLACES, unit=clip.UNIT)
    assert clip.SLIT_WIDTH_MIN == pytest.approx(narrowest)
    assert narrowest >= clip.PHOTO_SLIT_WIDTH - 1e-9
    # The lanes close to the overall width; the spring rail is what the .30
    # screw rail and the .04 slit leave of it.
    assert clip.SCREW_RAIL_WIDTH + clip.NOTCH_WIDTH + clip.SPRING_RAIL_WIDTH == (
        pytest.approx(clip.CLIP_WIDTH)
    )
    assert clip.NOTCH_WIDTH == pytest.approx(0.04 * 25.4)
    assert clip.SPRING_RAIL_WIDTH == pytest.approx(0.130 * 25.4)


def test_clip_screw_engages_one_and_a_half_diameters_worst_case():
    shortest = clip.SHANK_LEN - 0.03 * 25.4
    engaged = shortest - clip.SHEET_T_MAX - clip.PITCH - 0.010 * 25.4
    assert clip.CLIP_SCREW_ENGAGEMENT_MIN == pytest.approx(engaged)
    assert engaged / THREAD_MAJOR_MM[clip.THREAD] >= 1.5


def test_annotations_stay_in_the_field():
    points = [
        *draw.FRONT_KEEP.values(),
        *draw.TOP_KEEP.values(),
        *draw.OFFSET_TEXT.values(),
        draw.ISO_CENTER,
        draw.ISO_NOTE_XY,
        draw.HOLE_CALLOUT_XY,
    ]
    for xy in points:
        assert _inside(xy, BORDER), xy
        assert not _inside(xy, TITLE_BLOCK), xy
    assert BORDER[0] < draw.LEFT_EDGE_X and draw.RIGHT_EDGE_X < BORDER[2]
    assert draw.PROFILE_TOP_Y < max(xy[1] for xy in draw.TOP_KEEP.values())
    assert max(xy[1] for xy in draw.TOP_KEEP.values()) < BORDER[3]


def test_plan_rows_stack_smallest_nearest():
    below = [draw.FRONT_KEEP["LeftX"][1], draw.FRONT_KEEP["RightX"][1]]
    assert draw.BOTTOM_EDGE_Y > below[0] > below[1]
    above = [draw.FRONT_KEEP[name][1] for name in ("BridgeX0", "BridgeX1", "Length")]
    assert draw.TOP_EDGE_Y < draw.OFFSET_TEXT["SlitWidth"][1] < above[0]
    assert above == sorted(above)
    # Left of the plan, from the outer edge: hole row, screw rail, overall.
    columns = [
        draw.FRONT_KEEP[name][0] for name in ("LeftZ", "RailWidth", "OverallWidth")
    ]
    assert draw.LEFT_EDGE_X > columns[0] > columns[1] > columns[2]
    # Each text stands past its own span's end, so no other span's dimension
    # line runs through it: the hole row's and the screw rail's below the
    # plan, the screw rail's lower; the spring rail's and the overall
    # width's above it, the spring rail's in its own column inside the
    # overall width's.
    assert draw.FRONT_KEEP["RailWidth"][1] < draw.FRONT_KEEP["LeftZ"][1]
    assert draw.FRONT_KEEP["LeftZ"][1] < draw.BOTTOM_EDGE_Y
    for name in ("SpringRailWidth", "OverallWidth"):
        assert draw.FRONT_KEEP[name][1] > draw.TOP_EDGE_Y, name
    assert columns[2] < draw.FRONT_KEEP["SpringRailWidth"][0] < draw.LEFT_EDGE_X


# A printed text line's pitch (r7: the four-line screw-rail block stood
# 19.8 mm tall) and width per character ("2X 3.300": 18.1 mm).
_LINE_PITCH = 0.005
_CHAR_WIDTH = 0.00226


def _block(name: str) -> tuple[float, float, float]:
    """(top, bottom, widest line) of a front-view text block, in metres."""
    places = clip.DRAWING_PRECISION_BY_NAME[name]
    value = f"{draw.DIMENSION_AFFIXES.get(name, ('', ''))[0]}{0:.{places}f}"
    lines = [value, *draw.DIMENSION_CALLOUTS.get(name, "").splitlines()]
    y = draw.FRONT_KEEP[name][1]
    half = len(lines) * _LINE_PITCH / 2.0
    return y + half, y - half, max(len(line) for line in lines) * _CHAR_WIDTH


def test_hole_row_text_clears_the_near_hole_station_line():
    # r7 audit: the near hole station's dimension line (2.8 mm under its
    # text, its outside arrow running left of the plan's near end) crossed
    # the hole row's text by 2.7 mm; r8a: its arrow (0.4 mm lower) stood
    # 1.6 mm off the text, under the audit's 2.0.
    arrow_y = draw.FRONT_KEEP["LeftX"][1] - 0.0028 - 0.0004
    top, _bottom, _width = _block("LeftZ")
    assert top < arrow_y - 0.002


def test_near_hole_station_arrows_stand_inside_its_span():
    # reviewfix-r3 machinist review: the near station's outside arrow tail ran
    # left of the plan's near end, across the hole row's dimension line, which
    # stands left of that end.  Inside, the span holds the value and an arrow
    # (about 3 mm) each side of it.
    assert draw.ARROWS_INSIDE == ("LeftX",)
    assert draw.FRONT_KEEP["LeftZ"][0] < draw.LEFT_EDGE_X
    span = draw._plan_x(clip.HOLE_INSET) - draw.LEFT_EDGE_X
    assert span - len(".283") * _CHAR_WIDTH > 2 * 0.004


def test_length_line_clears_the_bridge_end_texts():
    # r8a audit: the length's FORMED line above its value pushed its
    # dimension line through the far bridge end's text.
    length_line_y = draw.FRONT_KEEP["Length"][1] - 0.0056
    bridge_text_top = draw.FRONT_KEEP["BridgeX1"][1] + 0.00175
    assert length_line_y > bridge_text_top + 0.002


def test_hole_row_names_the_tap_pattern_and_clears_the_rail_line():
    # The .XXX hole row holds the pattern float with the platen's taps; it
    # says so, and its widest line stays right of the screw rail's line.
    assert "MHA-PD-02" in draw.DIMENSION_CALLOUTS["LeftZ"]
    assert "MHA-PD-02" in draw.HOLE_CALLOUT_PROCESS
    _top, _bottom, width = _block("LeftZ")
    hole_row_left = draw.FRONT_KEEP["LeftZ"][0] - 0.0014 - width
    assert hole_row_left > draw.FRONT_KEEP["RailWidth"][0] + 0.003


def test_hole_pattern_three_places_are_a_declared_acceptance():
    # Owner ruling 2026-10-15, option A: the hole row and stations stay .XXX
    # for pattern float (transfer-drilling rejected).
    (entry,) = load_exceptions(CONFIG_ROOT, "pd_platen_clip", "part")
    assert (entry.id, entry.kind) == ("RV-01", "accept")
    assert clip.HOLE_FLOAT_MIN >= 2.0 * clip.PATTERN_POSITION_ZONE


def test_plan_length_says_formed_without_numbers():
    # r7 review: the plan's length and outline are the formed clip, not the
    # blank; the blank's fingers are the profile's developed length.
    assert set(draw.DIMENSION_CALLOUTS_ABOVE) == {"Length"}
    text = draw.DIMENSION_CALLOUTS_ABOVE["Length"]
    assert text.startswith("FORMED")
    assert not any(char.isdigit() for char in text)
    assert "DEVELOPED" in draw.DIMENSION_CALLOUTS["FlatFinger"]


def test_profile_station_rows_stack_smallest_nearest_between_the_views():
    rows = [draw.TOP_KEEP[name][1] for name, _x, _d in clip.DRAWN_TANGENT_STATIONS]
    xs = [x for _name, x, _d in clip.DRAWN_TANGENT_STATIONS]
    assert xs == sorted(xs)
    # Only where the bows leave and rejoin the flat: the hole and bridge
    # stations (r4 read the quarter-run joins as body-line crossings).
    assert xs == pytest.approx(
        [
            clip.HOLE_INSET,
            clip.BRIDGE_X0,
            clip.BRIDGE_X1,
            clip.CLIP_LENGTH - clip.HOLE_INSET,
        ]
    )
    assert draw.PROFILE_BOTTOM_Y > rows[0]
    assert rows == sorted(rows, reverse=True)
    assert rows[-1] > draw.FRONT_KEEP["Length"][1]


def test_slit_dimension_stands_inside_the_slit():
    x, y = draw.FRONT_KEEP["SlitWidth"]
    assert draw._plan_x(clip.HOLE_INSET) < x < draw._plan_x(clip.BRIDGE_X0)
    assert draw._plan_y(clip.SCREW_RAIL_WIDTH) < y < draw._plan_y(clip.SPRING_RAIL_Y0)


def test_callout_pick_lies_on_the_far_hole_rim():
    centre = (
        draw._plan_x(clip.CLIP_LENGTH - clip.HOLE_INSET),
        draw._plan_y(clip.HOLE_Y),
    )
    assert math.dist(draw.HOLE_EDGE_XY, centre) == pytest.approx(draw.HOLE_R_SHEET)
    assert draw.HOLE_CALLOUT_XY[0] > draw.RIGHT_EDGE_X
    assert draw.HOLE_CALLOUT_PROCESS.endswith("DRILL")
