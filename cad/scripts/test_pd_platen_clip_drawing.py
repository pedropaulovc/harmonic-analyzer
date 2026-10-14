"""Offline contract checks for the platen-clip manufacturing drawing (MHA-PD-003)."""

from __future__ import annotations

import math

import pytest

import build_pd_platen_clip as clip
import draw_pd_platen_clip as draw
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from _hole_spec import THREAD_MAJOR_MM
from _printed_tolerance import printed_band_mm

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
    assert set(draw.DIMENSION_PREFIXES) <= set(names)
    assert set(clip.DRAWING_PRECISION_BY_NAME) == set(names)


def test_hole_stations_and_ligament_widths_print_three_places():
    places = clip.DRAWING_PRECISION_BY_NAME
    for name in ("LeftX", "RightX", "LeftZ", "RailWidth", "StartOffset", "SheetDepth"):
        assert places[name] == 3, name
    assert places["Length"] == 1
    assert clip.HOLE_CALLOUT_PRECISION == {"hw-diam": 3}


def test_far_end_ligament_spends_the_length_band():
    band = printed_band_mm(3)
    far_edge = clip.CLIP_LENGTH - printed_band_mm(1)
    hole_far_max = clip.CLIP_LENGTH - clip.HOLE_INSET + band
    expected = far_edge - hole_far_max - clip.HOLE_DIA_MAX / 2.0
    assert clip.FAR_END_LIGAMENT_MIN == pytest.approx(expected)
    assert clip.FAR_END_LIGAMENT_MIN >= clip.LIGAMENT_FLOOR


def test_slit_stays_open_at_the_printed_worst_case():
    band = printed_band_mm(3)
    assert (clip.SPRING_RAIL_Y0 - band) - (clip.SCREW_RAIL_WIDTH + band) > 0.0


def test_clip_screw_engages_one_and_a_half_diameters_worst_case():
    shortest = clip.SHANK_LEN - 0.03 * 25.4
    thickest_sheet = clip.SHEET_T + printed_band_mm(3)
    engaged = shortest - thickest_sheet - clip.PITCH - 0.25
    assert clip.CLIP_SCREW_ENGAGEMENT_MIN == pytest.approx(engaged)
    assert engaged / THREAD_MAJOR_MM[clip.THREAD] >= 1.5


def test_annotations_stay_in_the_field():
    points = [
        *draw.FRONT_KEEP.values(),
        *draw.TOP_KEEP.values(),
        draw.ISO_CENTER,
        draw.ISO_NOTE_XY,
        draw.HOLE_CALLOUT_XY,
    ]
    for xy in points:
        assert _inside(xy, BORDER), xy
        assert not _inside(xy, TITLE_BLOCK), xy
    assert BORDER[0] < draw.LEFT_EDGE_X and draw.RIGHT_EDGE_X < BORDER[2]


def test_plan_rows_stack_smallest_nearest():
    below = [draw.FRONT_KEEP["LeftX"][1], draw.FRONT_KEEP["RightX"][1]]
    assert draw.BOTTOM_EDGE_Y > below[0] > below[1]
    above = [draw.FRONT_KEEP["BridgeX0"][1], draw.FRONT_KEEP["Length"][1]]
    assert draw.TOP_EDGE_Y < above[0] < above[1]
    assert draw.FRONT_KEEP["BridgeLength"][1] == above[0]
    # Left of the plan, from the outer edge: hole row, screw rail, spring rail.
    columns = [
        draw.FRONT_KEEP[name][0] for name in ("LeftZ", "RailWidth", "StartOffset")
    ]
    assert draw.LEFT_EDGE_X > columns[0] > columns[1] > columns[2]


def test_callout_pick_lies_on_the_far_hole_rim():
    centre = (
        draw._plan_x(clip.CLIP_LENGTH - clip.HOLE_INSET),
        draw._plan_y(clip.HOLE_Y),
    )
    assert math.dist(draw.HOLE_EDGE_XY, centre) == pytest.approx(draw.HOLE_R_SHEET)
    assert draw.HOLE_CALLOUT_XY[0] > draw.RIGHT_EDGE_X
