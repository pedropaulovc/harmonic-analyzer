"""Offline contract checks for the platen manufacturing drawing (MHA-PD-002)."""

from __future__ import annotations

import math
from pathlib import Path

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
from machinist_exceptions import load_exceptions, render_anchor
from vn_fillister_screw_spec import HEAD_H as FILLISTER_HEAD_H

# ASME B landscape field and title block (sheet metres).
BORDER = (0.0127, 0.0127, 0.4191, 0.2667)
TITLE_BLOCK = (0.216, 0.0127, 0.4191, 0.066)
CAD_SCRIPTS = Path(__file__).resolve().parent
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
        "section A-A": (
            draw.SECTION_CENTER[0] - spec.PLATE_THICKNESS * draw._SECTION_S / 2.0,
            draw.SECTION_CENTER[1] - draw.SECTION_SPAN * draw._SECTION_S,
            draw.SECTION_CENTER[0] + spec.PLATE_THICKNESS * draw._SECTION_S / 2.0,
            draw.SECTION_CENTER[1] + draw.SECTION_SPAN * draw._SECTION_S,
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
    keeps = (draw.FRONT_KEEP, draw.RIGHT_KEEP, draw.SECTION_KEEP_NAMES)
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
    # The thickness is spent by the disc-to-platen air and says so on the
    # sheet, naming the reducer disc by its registry number (r7 review).
    assert places["Depth"] == 3
    depth_callout = draw.DIMENSION_CALLOUTS_ABOVE["Depth"]
    assert draw.DISC_NUMBER == _config.parts("pd-rack-pinion")["number"]
    assert draw.DISC_NUMBER in depth_callout
    # An above-callout line break would not print.
    assert "\n" not in depth_callout
    # The boss prints .X and still keeps its wall round the tap at that band.
    assert places["BossH"] == places["Boss2Dia"] == 1
    assert spec.SOCKET_BOSS_WALL_MIN == pytest.approx(
        (spec.SOCKET_BOSS_DIA - printed_band_mm(1)) / 2.0 - 2.184 / 2.0
    )
    assert spec.SOCKET_BOSS_WALL_MIN >= 2.0


def test_boss_roots_print_a_single_max_limit_on_the_right_view():
    # r7 review: the 4X tap bosses' root corner was unstated.  Each takes the
    # tool-nose round up to R0.5, printed "4X R0.5 MAX": swTolMAX prints the
    # nominal, so the model carries the limit and its band runs down to sharp.
    assert spec.SOCKET_BOSS_FILLET_R == 0.5
    assert spec.SOCKET_BOSS_FILLET_BAND == (0.0, -spec.SOCKET_BOSS_FILLET_R)
    assert spec.SOCKET_BOSS_FILLET_TOL_TYPE == 6  # swTolMAX
    assert spec.DRAWING_DIMENSIONS["SocketBossFillet"] == {"BossFilletR"}
    places = spec.DRAWING_PRECISION_BY_NAME["BossFilletR"]
    assert round(spec.SOCKET_BOSS_FILLET_R, places) == spec.SOCKET_BOSS_FILLET_R
    assert draw.DIMENSION_PREFIXES["BossFilletR"] == "4X R"
    assert "BossFilletR" in draw.RIGHT_KEEP
    # The printed round is the upper boss nearest the right view's eye (+X);
    # the build rounds it alone and the other three in a second feature, both
    # on one global, each picked on its root circle at the back face.
    assert spec.SOCKET_BOSS_FILLET_PRINTED_XY == (
        max(x for x, _ in spec.SOCKET_XY),
        max(y for _, y in spec.SOCKET_XY),
    )
    source = (CAD_SCRIPTS / "build_pd_platen.py").read_text(encoding="utf-8")
    assert '("SocketBossFillet", "BossFilletR", [SOCKET_BOSS_FILLET_PRINTED_XY])' in (
        source
    )
    assert "_boss_fillet_max_limit(adapter)" in source
    assert '"SocketBossFilletR", f"{SOCKET_BOSS_FILLET_R}mm"' in source
    # The text stands up-left of the upper boss's root, left of its end face
    # (half of ~28 mm of text) and under the thickness's outside arrow.
    x, y = draw.RIGHT_KEEP["BossFilletR"]
    boss_end_x = draw._right_x(spec.PLATE_THICKNESS + spec.SOCKET_BOSS_H)
    assert x + 0.014 < boss_end_x - 0.002
    root_y = draw._right_y(max(y for _, y in spec.SOCKET_XY) + spec.SOCKET_BOSS_DIA / 2)
    assert abs(y - root_y) < 0.003
    assert y + TEXT_HALF_H < 0.2458 - 0.002
    # Nothing rides the back face there: the assembly's boss sweep grows each
    # boss by the round's foot.
    assembly_source = (CAD_SCRIPTS / "build_pd_paper_drive_assembly.py").read_text(
        encoding="utf-8"
    )
    assert "PLATEN_SOCKET_BOSS_DIA / 2.0 + PLATEN_BOSS_FILLET_R" in assembly_source


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
    offset = spec.CBORE_SECTION_HOLE_Y - spec.CBORE_FLOOR_REFERENCE_Y
    assert spec.GUIDE_HOLE_DIA / 2.0 < offset < spec.CBORE_DIA / 2.0
    assert (spec.CBORE_SECTION_X, spec.CBORE_SECTION_HOLE_Y) in spec.GUIDE_HOLE_XY
    assert spec.DRAWING_DIMENSIONS["CboreFloorReference"] == {draw.REFERENCE_DIMENSION}
    # Section A-A draws the counterbore (r4: not hidden lines in the right
    # view), and its partial cut spans the whole counterbore.
    assert draw.SECTION_KEEP_NAMES == {draw.REFERENCE_DIMENSION}
    assert draw.REFERENCE_DIMENSION not in draw.RIGHT_KEEP
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
    assert "HIDDEN" not in spec.RIGHT_VIEW_NOTE
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


def test_owner_rulings_are_declared_against_the_printed_text():
    # The sockets' .XXX stations match the clip's (owner ruling 2026-10-15,
    # option A) and the thin counterbore floor is the user's 2026-10-14
    # shortfall; each declaration anchors what the sheet prints.
    entries = {entry.id: entry for entry in load_exceptions("pd_platen")}
    assert {name: entry.kind.value for name, entry in entries.items()} == {
        "RV-01": "accept",
        "RV-02": "minor",
    }

    def rendered(id_: str) -> str:
        return "; ".join(render_anchor(a, "pd_platen") for a in entries[id_].anchors)

    sockets = entries["RV-01"]
    assert sockets.reason.endswith("(owner-accepted)")
    assert draw.SOCKET_CALLOUT_PROCESS.replace("\n", " / ") in rendered("RV-01")
    assert {f"dim:{name}@Sockets" for name in spec.DRAWING_DIMENSIONS["Sockets"]} <= {
        str(anchor) for anchor in sockets.anchors
    }
    floor = entries["RV-02"]
    assert floor.reason.endswith("(owner-ruled shortfall)")
    assert spec.CBORE_FLOOR_CALLOUT.replace("\n", " / ") in rendered("RV-02")
    assert "dim:CboreFloor@CboreFloorReference" in {str(a) for a in floor.anchors}


def test_one_centre_mark_per_hole_per_plan_view():
    assert draw.CENTER_MARKS_PER_VIEW == len(spec.SOCKET_XY) + len(spec.GUIDE_HOLE_XY)


def test_hole_callouts_name_their_mating_patterns():
    assert "MHA-PD-011" in draw.GUIDE_CALLOUT_PROCESS
    # Four callout rows at most: the Ø line, two process rows, the C'BORE row.
    assert draw.GUIDE_CALLOUT_PROCESS.count("\n") == 2
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
