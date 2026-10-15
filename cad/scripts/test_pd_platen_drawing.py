"""Offline contract checks for the platen manufacturing drawing (MHA-PD-002)."""

from __future__ import annotations

import math

import pytest

import _config
import build_pd_platen as build
import draw_pd_platen as draw
import pd_platen_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from _hole_spec import blind_cut_dia_mm
from _holes import SharedCoordinate
from _printed_tolerance import printed_band_mm
from vn_fillister_screw_spec import HEAD_H as FILLISTER_HEAD_H

# ASME B landscape field and title block (sheet metres).
BORDER = (0.0127, 0.0127, 0.4191, 0.2667)
TITLE_BLOCK = (0.216, 0.0127, 0.4191, 0.066)
# Half extent of one printed dimension value (about 2.5 mm a character).
TEXT_HALF_H = 0.002


def _inside(xy, box) -> bool:
    return box[0] <= xy[0] <= box[2] and box[1] <= xy[1] <= box[3]


def _view_boxes() -> dict[str, tuple[float, float, float, float]]:
    w, h = spec.PLATE_WIDTH * draw._S / 2.0, spec.PLATE_HEIGHT * draw._S / 2.0
    depth = (spec.PLATE_THICKNESS + spec.SOCKET_BOSS_H) * draw._RIGHT_S / 2.0
    right_h = spec.PLATE_HEIGHT * draw._RIGHT_S / 2.0
    return {
        "front": (
            draw.FRONT_CENTER[0] - w,
            draw.FRONT_CENTER[1] - h,
            draw.FRONT_CENTER[0] + w,
            draw.FRONT_CENTER[1] + h,
        ),
        "right": (
            draw.RIGHT_CENTER[0] - depth,
            draw.RIGHT_CENTER[1] - right_h,
            draw.RIGHT_CENTER[0] + depth,
            draw.RIGHT_CENTER[1] + right_h,
        ),
    }


def test_registry_row_names_the_platen_sheet():
    row = DRAWINGS_BY_NAME["pd_platen"]
    assert row.part == "pd_platen"
    assert row.script_name == "draw_pd_platen.py"
    assert row.layout is DrawingLayout.LANDSCAPE
    assert draw.PART_STEM == "pd-platen"
    assert draw.OUTPUTS.pdf == row.outputs["pdf"]
    assert "draw_pd_platen.py" in PRECISION_MIGRATED_DRAWINGS


def test_views_keep_exactly_the_marked_dimensions_once():
    keeps = (draw.FRONT_KEEP, draw.RIGHT_KEEP)
    names = [name for keep in keeps for name in keep]
    assert len(names) == len(set(names))
    assert set(names) == set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(draw.DIMENSION_PREFIXES) <= set(names)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == set(names)


def test_places_follow_what_each_dimension_holds():
    places = spec.DRAWING_PRECISION_BY_NAME
    assert places["Width"] == places["Height"] == 1
    stations = (
        spec.DRAWING_DIMENSIONS["Sockets"] | spec.DRAWING_DIMENSIONS["GuideHoles"]
    )
    assert {places[name] for name in stations} == {3}
    # The thickness is spent by the disc-to-platen air and says so on the sheet.
    assert places["Depth"] == 3
    assert "Depth" in draw.DIMENSION_CALLOUTS_ABOVE
    # The boss prints .X and still keeps its wall round the tap at that band.
    assert places["BossH"] == places["Boss2Dia"] == 1
    assert spec.SOCKET_BOSS_WALL_MIN == pytest.approx(
        (spec.SOCKET_BOSS_DIA - printed_band_mm(1)) / 2.0 - 2.184 / 2.0
    )
    assert spec.SOCKET_BOSS_WALL_MIN >= 2.0


def test_counterbore_floor_holds_the_user_accepted_worst_case():
    # User ruling 2026-10-14: the thin floor is accepted at its 0.67 worst
    # case and printed as a reference; nothing may thin it further.
    depth_places = spec.DRAWING_PRECISION_BY_NAME["Depth"]
    cbore_places = spec.GUIDE_CALLOUT_PRECISION["hw-cbdepth"]
    worst = (
        round(spec.PLATE_THICKNESS, depth_places)
        - printed_band_mm(depth_places)
        - round(spec.CBORE_DEPTH, cbore_places)
        - printed_band_mm(cbore_places)
    )
    assert worst == pytest.approx(spec.CBORE_FLOOR_MIN)
    assert worst >= 0.67
    assert spec.CBORE_FLOOR == pytest.approx(spec.PLATE_THICKNESS - spec.CBORE_DEPTH)
    # The reference line crosses the floor's annulus, clear of the through hole
    # and inside the counterbore, so it measures metal.
    offset = spec.CBORE_FLOOR_REFERENCE_Y - spec.GUIDE_HOLE_Y[0]
    assert spec.GUIDE_HOLE_DIA / 2.0 < offset < spec.CBORE_DIA / 2.0
    assert spec.DRAWING_DIMENSIONS["CboreFloorReference"] == {draw.REFERENCE_DIMENSION}
    assert draw.REFERENCE_DIMENSION in draw.RIGHT_KEEP
    assert draw.REFERENCE_DIMENSION in draw.DIMENSION_CALLOUTS_BELOW
    # The sheet states the accepted shortfall at the floor, from the same
    # constant this test pins.
    assert draw.DIMENSION_CALLOUTS_BELOW[draw.REFERENCE_DIMENSION] == (
        spec.CBORE_FLOOR_CALLOUT
    )
    assert spec.CBORE_FLOOR_CALLOUT == (
        f"C'BORE FLOOR\n{spec.CBORE_FLOOR_MIN:.2f} MIN WORST CASE"
    )
    assert f"{spec.CBORE_FLOOR_MIN:.2f}" == "0.67"


def test_one_centre_mark_per_hole_per_plan_view():
    assert draw.CENTER_MARKS_PER_VIEW == len(spec.SOCKET_XY) + len(spec.GUIDE_HOLE_XY)


def test_hole_callouts_name_their_mating_patterns():
    assert "MHA-PD-011" in draw.GUIDE_CALLOUT_PROCESS
    assert "MHA-PD-003" in draw.SOCKET_CALLOUT_PROCESS
    # The counterbore depth's .XXX sinks a named screw's head.
    assert _config.parts("vn-fillister-screw")["number"] in draw.GUIDE_CALLOUT_PROCESS
    # The through hole is DRILLED at .XX; the depth keeps .XXX to sink the head.
    assert spec.GUIDE_CALLOUT_PRECISION["hw-thruholedia"] == 2
    assert spec.HEAD_RECESS_MIN > 0.0


def _placed_coordinates(points, placement, drives):
    """Each point's (x, y) as the printed drives and shared relations give it."""
    resolved: list[list[float]] = []
    for point, axes in zip(points, placement):
        coordinate = []
        for axis, dim in enumerate(axes):
            if isinstance(dim, SharedCoordinate):
                assert dim.point < len(resolved)
                coordinate.append(resolved[dim.point][axis])
            else:
                coordinate.append(drives[dim[1].strip('"')])
        assert coordinate == pytest.approx(list(point), abs=1e-9)
        resolved.append(coordinate)
    return resolved


def test_printed_stations_place_every_hole():
    xs = sorted({x for x, _ in spec.SOCKET_XY})
    ys = sorted({y for _, y in spec.SOCKET_XY})
    drives = {
        **{f"SocketX{i}": v for i, v in enumerate(xs, start=1)},
        **{f"SocketY{i}": v for i, v in enumerate(ys, start=1)},
        **{f"GuideX{i}": v for i, v in enumerate(spec.GUIDE_HOLE_X, start=1)},
        **{f"GuideY{i}": v for i, v in enumerate(spec.GUIDE_HOLE_Y, start=1)},
    }
    sockets = _placed_coordinates(build.SOCKET_ORDER, build.SOCKET_PLACEMENT, drives)
    guides = _placed_coordinates(spec.GUIDE_HOLE_XY, build.GUIDE_PLACEMENT, drives)
    assert sorted(map(tuple, sockets)) == sorted(spec.SOCKET_XY)
    assert len(guides) == 10

    def printed(placement):
        return {
            dim[0]
            for axes in placement
            for dim in axes
            if not isinstance(dim, SharedCoordinate)
        }

    assert printed(build.SOCKET_PLACEMENT) == spec.DRAWING_DIMENSIONS["Sockets"]
    assert printed(build.GUIDE_PLACEMENT) == spec.DRAWING_DIMENSIONS["GuideHoles"]


def test_shallowest_printed_counterbore_still_sinks_the_head():
    places = spec.GUIDE_CALLOUT_PRECISION["hw-cbdepth"]
    shallowest = round(spec.CBORE_DEPTH, places) - printed_band_mm(places)
    assert shallowest - FILLISTER_HEAD_H == pytest.approx(spec.HEAD_RECESS_MIN)
    assert spec.HEAD_RECESS_MIN > 0.0
    # The counterbore Ø prints .X: the head still clears its smallest Ø.
    assert spec.GUIDE_CALLOUT_PRECISION["hw-cbdia"] == 1
    assert spec.CBORE_DIA - printed_band_mm(1) > 4.6482


def test_views_and_annotations_stay_in_the_field():
    boxes = _view_boxes()
    names = list(boxes)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            box_a, box_b = boxes[a], boxes[b]
            assert (
                box_a[2] < box_b[0]
                or box_b[2] < box_a[0]
                or (box_a[3] < box_b[1] or box_b[3] < box_a[1])
            ), (a, b)
    for box in boxes.values():
        assert _inside(box[:2], BORDER) and _inside(box[2:], BORDER)
        assert box[1] > TITLE_BLOCK[3] or box[2] < TITLE_BLOCK[0]
    points = [
        *draw.FRONT_KEEP.values(),
        *draw.RIGHT_KEEP.values(),
        draw.ISO_CENTER,
        draw.ISO_NOTE_XY,
        draw.RIGHT_NOTE_XY,
        draw.GUIDE_CALLOUT_XY,
        draw.SOCKET_CALLOUT_XY,
    ]
    for xy in points:
        assert _inside(xy, BORDER), xy
        assert not _inside(xy, TITLE_BLOCK), xy


def test_x_stations_stack_smallest_nearest_below_the_front_view():
    values = {
        "Socket3X": min(x for x, _ in spec.SOCKET_XY),
        "Socket1X": max(x for x, _ in spec.SOCKET_XY),
        **{f"Guide{i}X": x for i, x in enumerate(spec.GUIDE_HOLE_X, start=1)},
        "Width": spec.PLATE_WIDTH,
    }
    rows = sorted(values, key=values.get)
    heights = [draw.FRONT_KEEP[name][1] for name in rows]
    assert heights == sorted(heights, reverse=True)
    assert heights[0] < draw.BOTTOM_EDGE_Y - TEXT_HALF_H
    assert all(a - b >= 0.006 for a, b in zip(heights, heights[1:]))


def test_callout_picks_lie_on_their_hole_rims():
    guide = (draw._front_x(spec.GUIDE_HOLE_X[0]), draw._front_y(spec.GUIDE_HOLE_Y[1]))
    assert math.dist(draw.GUIDE_EDGE_XY, guide) == pytest.approx(
        spec.GUIDE_HOLE_DIA / 2.0 * draw._S
    )
    socket = (
        draw._front_x(max(x for x, _ in spec.SOCKET_XY)),
        draw._front_y(max(y for _, y in spec.SOCKET_XY)),
    )
    assert math.dist(draw.SOCKET_EDGE_XY, socket) == pytest.approx(
        blind_cut_dia_mm(spec.SOCKET_SPEC) / 2.0 * draw._S
    )
    # Both callouts stand above the plate.
    assert draw.GUIDE_CALLOUT_XY[1] > draw.TOP_EDGE_Y
    assert draw.SOCKET_CALLOUT_XY[1] > draw.TOP_EDGE_Y
