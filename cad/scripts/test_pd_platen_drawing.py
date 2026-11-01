"""Offline contract checks for the platen manufacturing drawing (MHA-PD-02)."""

from __future__ import annotations

import math
import re

import pytest

import _config
import build_pd_platen as build
import draw_pd_platen as draw
import pd_platen_spec as spec
from _hole_spec import THREAD_MAJOR_MM, blind_cut_dia_mm
from _holes import SharedCoordinate
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import printed_deviations
from sh_vn_brass_fillister_screw_spec import HEAD_H as FILLISTER_HEAD_H

# ASME B landscape field and title block (sheet metres).
BORDER = (0.0127, 0.0127, 0.4191, 0.2667)
TITLE_BLOCK = (0.216, 0.0127, 0.4191, 0.066)
# Half extent of one printed dimension value (about 2.5 mm a character).
TEXT_HALF_H = 0.002


def _limits(nominal: float, places: int) -> tuple[float, float]:
    """The least and greatest part the inch sheet accepts for a model value."""
    lower, upper = printed_deviations(nominal, places, unit=spec.UNIT)
    return nominal + lower, nominal + upper


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
        "section A-A": (
            draw.SECTION_CENTER[0] - spec.PLATE_THICKNESS * draw._SECTION_S / 2.0,
            draw.SECTION_CENTER[1] - draw.SECTION_SPAN * draw._SECTION_S,
            draw.SECTION_CENTER[0] + spec.PLATE_THICKNESS * draw._SECTION_S / 2.0,
            draw.SECTION_CENTER[1] + draw.SECTION_SPAN * draw._SECTION_S,
        ),
    }


def test_printed_guide_and_screw_numbers_resolve_to_the_registered_parts() -> None:
    registered = {row["number"] for row in _config.parts().values()}
    printed = set(
        re.findall(
            r"\bMHA-[A-Z0-9]+(?:-[A-Z0-9]+)+\b", draw.GUIDE_CALLOUT_PROCESS
        )
    )
    assert printed <= registered, printed - registered
    for mate in ("pd-platen-guide", "sh-vn-brass-fillister-screw"):
        assert _config.parts(mate)["number"] in printed


def test_boss_walls_survive_the_printed_band():
    assert spec.UNIT == "in"
    smallest_boss = _limits(spec.SOCKET_BOSS_DIA, spec.DRAWING_PRECISION_BY_NAME["Boss2Dia"])[0]
    major = THREAD_MAJOR_MM[spec.SOCKET_SPEC.size]
    assert spec.SOCKET_BOSS_WALL_MIN == pytest.approx(smallest_boss / 2.0 - major / 2.0)
    assert spec.SOCKET_BOSS_WALL_MIN >= WALL_TARGET_MM


def test_boss_roots_stay_inside_the_title_block_inside_corner_limit():
    # Machinist review round 2: nothing seats on the boss roots, so the title
    # block's inside-corner limit governs them unprinted; the modelled round
    # lies inside it and the assembly sweep grows each boss by the limit.
    from _printed_tolerance import inside_corner_radius_mm

    limit = inside_corner_radius_mm(unit=spec.UNIT)
    assert spec.SOCKET_BOSS_ROOT_R_MAX == limit == pytest.approx(0.040 * 25.4)
    assert 0.0 < spec.SOCKET_BOSS_FILLET_R <= limit
    printed = {n for names in spec.DRAWING_DIMENSIONS.values() for n in names}
    assert not any("Fillet" in name for name in printed)


def test_counterbore_floor_holds_the_user_accepted_worst_case():
    # User ruling 2026-10-14 (pd-platen RV-02): the thin floor is accepted at
    # its 0.67 worst case and printed as a reference; nothing may thin it.
    depth_places = spec.DRAWING_PRECISION_BY_NAME["Depth"]
    cbore_places = spec.GUIDE_CALLOUT_PRECISION["hw-cbdepth"]
    worst = (
        _limits(spec.PLATE_THICKNESS, depth_places)[0]
        - _limits(spec.CBORE_DEPTH, cbore_places)[1]
    )
    assert worst == pytest.approx(spec.CBORE_FLOOR_MIN)
    assert worst == pytest.approx(0.027 * 25.4)
    assert worst >= 0.67
    assert spec.CBORE_FLOOR == pytest.approx(spec.PLATE_THICKNESS - spec.CBORE_DEPTH)
    # The reference line crosses the floor's annulus, clear of the through hole
    # and inside the counterbore, so it measures metal.
    offset = spec.CBORE_SECTION_HOLE_Y - spec.CBORE_FLOOR_REFERENCE_Y
    assert spec.GUIDE_HOLE_DIA / 2.0 < offset < spec.CBORE_DIA / 2.0
    assert (spec.CBORE_SECTION_X, spec.CBORE_SECTION_HOLE_Y) in spec.GUIDE_HOLE_XY
    # Section A-A draws the counterbore (r4: not hidden lines in the right
    # view), and its partial cut spans the whole counterbore.
    assert draw.SECTION_SPAN > spec.CBORE_DIA / 2.0
    assert {point[:2] for point in draw.SECTION_LINE_MODEL_MM} == {
        (spec.CBORE_SECTION_X, spec.CBORE_SECTION_HOLE_Y - draw.SECTION_SPAN),
        (spec.CBORE_SECTION_X, spec.CBORE_SECTION_HOLE_Y + draw.SECTION_SPAN),
    }
    # The value hangs below the cut, wholly left of both extension lines (r5:
    # centred on them, they struck its text).
    _, text_y, text_z = draw.SECTION_TEXT_MODEL_MM[draw.REFERENCE_DIMENSION]
    assert text_y < spec.CBORE_SECTION_HOLE_Y - draw.SECTION_SPAN
    text_right = (
        draw.SECTION_CENTER[0]
        + (text_z - spec.PLATE_THICKNESS / 2.0) * draw._SECTION_S
        + draw._SECTION_TEXT_HALF_WIDTH
    )
    assert text_right == pytest.approx(draw.SECTION_TEXT_RIGHT)
    near_extension = (
        draw.SECTION_CENTER[0]
        + (spec.CBORE_DEPTH - spec.PLATE_THICKNESS / 2.0) * draw._SECTION_S
    )
    assert near_extension - text_right >= 0.002


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
    _placed_coordinates(spec.GUIDE_HOLE_XY, build.GUIDE_PLACEMENT, drives)
    assert sorted(map(tuple, sockets)) == sorted(spec.SOCKET_XY)


def test_shallowest_printed_counterbore_still_sinks_the_head():
    places = spec.GUIDE_CALLOUT_PRECISION["hw-cbdepth"]
    shallowest = _limits(spec.CBORE_DEPTH, places)[0]
    assert shallowest - FILLISTER_HEAD_H == pytest.approx(spec.HEAD_RECESS_MIN)
    assert spec.HEAD_RECESS_MIN > 0.0
    # The counterbore Ø prints .XX: the head still clears its smallest Ø.
    assert _limits(spec.CBORE_DIA, spec.GUIDE_CALLOUT_PRECISION["hw-cbdia"])[0] > 4.6482


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
        draw.SECTION_CAPTION_XY,
        # The floor value's text, both ends, below the cut.
        *(
            (
                x,
                draw.SECTION_CENTER[1]
                + (
                    draw.SECTION_TEXT_MODEL_MM[draw.REFERENCE_DIMENSION][1]
                    - spec.CBORE_SECTION_HOLE_Y
                )
                * draw._SECTION_S,
            )
            for x in (
                draw.SECTION_TEXT_RIGHT - 2.0 * draw._SECTION_TEXT_HALF_WIDTH,
                draw.SECTION_TEXT_RIGHT,
            )
        ),
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
