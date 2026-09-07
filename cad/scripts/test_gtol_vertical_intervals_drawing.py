"""Pure ten-cell replay; native acceptance is still required after prediction.

datum-policy-p6dj_zsa/pilot.json SHA256
0f9a2502b7cd5a96a463aa9d412b521255358db55e96904afa2933aa9708602b.
The native 62.94347762865551 mm RIGHT-UP moved the shoulder/all-around circle
while leaving attachment endpoints/arrows fixed, exactly as the three-point
model predicts. It crossed RD4 for 2.814143/6.820318 mm inside measured cells.
All ten reported cells are retained here; this is not the complete sheet.
"""

from types import SimpleNamespace

import pytest

import _drawing_native_gtol as policy
from _drawing_annotation_bounds import LeaderGeometry, Segment
from _drawing_leader_clearance import intersects_cell
from _drawing_view_packing import Rect
from test_gtol_column_frontiers_drawing import (
    half_scale_lever_fixture,
    predict_routes,
    crossings,
)


def ten_cell_lever_fixture():
    geometry, cells = half_scale_lever_fixture()
    for name, text, boxes in (
        (
            "FulcrumDia",
            "<MOD-DIAM>6.50",
            (
                (
                    0.044774062129357896,
                    0.17360057094760695,
                    0.0460862621293579,
                    0.17918043761427363,
                ),
                (
                    0.046077117726119304,
                    0.1735470987709471,
                    0.05135555524090871,
                    0.17918043761427363,
                ),
                (
                    0.051345555240908704,
                    0.17360057094760695,
                    0.06170875524090871,
                    0.17918043761427363,
                ),
            ),
        ),
        (
            "BarLength",
            "169.00",
            (
                (
                    0.14017819416210459,
                    0.1343231248590592,
                    0.15442172749543792,
                    0.13990299152572588,
                ),
            ),
        ),
        (
            "RD4",
            "<MOD-DIAM> 1.99 THRU ALL",
            (
                (
                    0.205899999953,
                    0.18318513879782894,
                    0.2111784373513741,
                    0.18881847764115547,
                ),
                (
                    0.21116843735137408,
                    0.1832386109744888,
                    0.2429418373513741,
                    0.18881847764115547,
                ),
            ),
        ),
    ):
        cells[name] = SimpleNamespace(
            kind=4,
            text_boxes=tuple(Rect(*box) for box in boxes),
            text_runs=(SimpleNamespace(value=text),),
        )
    return geometry, cells


def test_ten_cells_require_middle_interval_not_above_all_obstacles():
    geometry, cells = ten_cell_lever_fixture()
    assert sum(len(row.text_boxes) for row in cells.values()) == 10
    extreme_hits = crossings(predict_routes(geometry, 0.06294347762865551), cells)
    assert {
        (hit["leader_annotation"], hit["target_annotation"]) for hit in extreme_hits
    } == {("DetailItem356", "RD4"), ("DetailItem357", "RD4")}
    candidates = policy.column_vertical_candidates(
        crossings(geometry, cells), geometry, cells
    )
    up = next(row for row in candidates if row.direction.value == "up")
    assert up.dy_m == pytest.approx(0.02152486647419627)
    assert crossings(predict_routes(geometry, up.dy_m), cells) == []


@pytest.mark.parametrize(
    "motion", [(1, 1), (-1, -1), (1, 0), (0, 1), (-1, 0), (0, -1), (0, 0)]
)
@pytest.mark.parametrize(
    "cell",
    [
        Rect(0.19, 0.18, 0.25, 0.24),
        Rect(0.1, 0.1, 0.2, 0.16),
        Rect(0.3, 0.22, 0.31, 0.32),
        Rect(1, 1, 2, 2),
    ],
)
@pytest.mark.parametrize(
    "line",
    [
        Segment((0.1, 0.16), (0.3, 0.22)),
        Segment((0.3, 0.22), (0.1, 0.16)),
        Segment((0.2, 0.1), (0.2, 0.3)),
        Segment((0.2, 0.2), (0.2, 0.2)),
        Segment((0.1, 0.3), (0.3, 0.3), 0.00018),
    ],
)
def test_analytic_forbidden_interval_matches_existing_segment_clipper(
    motion, cell, line
):
    clearance = 0.001
    expanded = Rect(
        cell.xmin - clearance,
        cell.ymin - clearance,
        cell.xmax + clearance,
        cell.ymax + clearance,
    )
    interval = policy._line_vertical_interval(line, cell, motion, clearance)
    for index in range(-100, 101):
        dy = index * 0.00317
        shifted = Segment(
            (line.start[0], line.start[1] + motion[0] * dy),
            (line.end[0], line.end[1] + motion[1] * dy),
            line.width_m,
        )
        predicted = interval is not None and interval[0] <= dy <= interval[1]
        assert predicted == intersects_cell(shifted, expanded), (
            motion,
            line,
            dy,
            interval,
        )


def test_native_decoration_vertex_association_distinguishes_elbow_and_arrow():
    geometry, _ = ten_cell_lever_fixture()
    row = geometry["DetailItem350"]
    assert [
        policy._decoration_motion(box, row.segments) for box in row.decorations
    ] == [1, 0]


@pytest.mark.parametrize("box", [Rect(0, 0, 1, 1), Rect(0.3, 0.3, 0.4, 0.4)])
def test_ambiguous_or_unassociated_decoration_cannot_be_guessed(box):
    geometry, _ = ten_cell_lever_fixture()
    with pytest.raises(ValueError, match="decoration"):
        policy._decoration_motion(box, geometry["DetailItem350"].segments)


@pytest.mark.parametrize("motion", [-1, 0, 1])
def test_decoration_interval_tracks_fixed_arrow_and_moving_shoulder(motion):
    box, cell = Rect(0.1, 0.2, 0.3, 0.4), Rect(0.25, 0.32, 0.35, 0.42)
    interval = policy._box_vertical_interval(box, cell, motion, 0.001)
    for index in range(-100, 101):
        dy = index * 0.00317
        moved = box.translated((0, motion * dy))
        hit = moved.ymax + 0.001 >= cell.ymin and moved.ymin - 0.001 <= cell.ymax
        assert (interval is not None and interval[0] <= dy <= interval[1]) == hit


def test_interval_union_uses_nearest_gap_and_returns_at_most_two_offsets():
    intervals = [(-0.01, 0.02), (0.01, 0.03), (0.08, 0.09), (-0.05, -0.02)]
    up, down = policy._nearest_vertical_candidates(intervals)
    assert up.dy_m == pytest.approx(0.03 + policy._POSITION_EPSILON_M)
    assert down.dy_m == pytest.approx(-0.01 - policy._POSITION_EPSILON_M)
    assert policy._nearest_vertical_candidates([(-float("inf"), float("inf"))]) == ()
    assert [
        row.direction.value
        for row in policy._nearest_vertical_candidates([(-0.01, float("inf"))])
    ] == ["down"]
    assert policy._nearest_vertical_candidates([]) == ()


@pytest.mark.parametrize("interval", [(1, -1), (float("nan"), 1), (0, float("nan"))])
def test_malformed_interval_is_not_silently_dropped(interval):
    with pytest.raises(ValueError, match="invalid forbidden"):
        policy._nearest_vertical_candidates([interval])


def simple_route():
    return LeaderGeometry(
        (Segment((0.4, 0.1), (0.3, 0.1)), Segment((0.3, 0.1), (0.1, 0.05))), ()
    )


def text_cell(box):
    return SimpleNamespace(kind=4, text_boxes=(box,), text_runs=())


def test_associated_elbow_decoration_can_require_more_clearance_than_shoulder():
    route = simple_route()
    geometry = {
        "gtol": LeaderGeometry(route.segments, (Rect(0.299, 0.095, 0.301, 0.105),))
    }
    cells = {"text": text_cell(Rect(0.29, 0.09, 0.31, 0.11))}
    up, _ = policy.column_vertical_candidates(
        crossings(geometry, cells), geometry, cells
    )
    assert up.dy_m == pytest.approx(0.016 + policy._POSITION_EPSILON_M)


def test_fixed_attachment_inside_fixed_text_has_no_predicted_escape():
    geometry = {"gtol": simple_route()}
    cells = {"text": text_cell(Rect(0.099, 0.049, 0.101, 0.051))}
    assert (
        policy.column_vertical_candidates(crossings(geometry, cells), geometry, cells)
        == ()
    )


def test_other_moving_gtol_body_is_relative_not_a_stationary_cell():
    geometry = {"gtol": simple_route(), "other": LeaderGeometry((), ())}
    cells = {"other": text_cell(Rect(0.39, 0.095, 0.405, 0.105))}
    # A shoulder already crossing another co-moving body cannot escape it by
    # translating the entire bank. Treating that body as fixed invents a gap.
    assert (
        policy.column_vertical_candidates(crossings(geometry, cells), geometry, cells)
        == ()
    )
    stationary = {"gtol": geometry["gtol"]}
    assert (
        len(
            policy.column_vertical_candidates(
                crossings(stationary, cells), stationary, cells
            )
        )
        == 2
    )


def test_fixed_arrow_can_clear_a_body_that_moves_with_the_bank():
    route = simple_route()
    geometry = {
        "gtol": LeaderGeometry(route.segments, (Rect(0.099, 0.049, 0.101, 0.051),)),
        "other": LeaderGeometry((), ()),
    }
    cells = {"other": text_cell(Rect(0.099, 0.048, 0.101, 0.052))}
    assert (
        len(
            policy.column_vertical_candidates(
                crossings(geometry, cells), geometry, cells
            )
        )
        == 2
    )


def test_body_obstacle_uses_current_horizontal_body_and_existing_gap_tolerance():
    geometry = {"gtol": simple_route()}
    cells = {"text": text_cell(Rect(0.29, 0.09, 0.31, 0.11))}
    hits = crossings(geometry, cells)
    body = Rect(0.4, 0.09, 0.42, 0.1)
    obstacle = Rect(0.4, 0.109, 0.42, 0.13)
    up, _ = policy.column_vertical_candidates(
        hits, geometry, cells, bodies=(body,), obstacles=(obstacle,)
    )
    assert up.dy_m == pytest.approx(
        0.042 - policy._BODY_EPSILON_M + policy._POSITION_EPSILON_M
    )
    assert policy._separated(body.translated((0, up.dy_m)), obstacle, 0.002)
    # An exact sufficient horizontal gap stays sufficient for every DY.
    distant = Rect(0.422, 0.109, 0.43, 0.13)
    assert policy.column_vertical_candidates(
        hits, geometry, cells, bodies=(body,), obstacles=(distant,)
    ) == policy.column_vertical_candidates(hits, geometry, cells)


@pytest.mark.parametrize("motion", [(1, -1), (2, 2)])
def test_unsupported_endpoint_motion_is_rejected(motion):
    with pytest.raises(ValueError, match="unsupported"):
        policy._line_vertical_interval(
            simple_route().segments[0], Rect(0, 0, 1, 1), motion, 0.001
        )


def test_reversed_or_nonhorizontal_native_chain_cannot_be_guessed():
    route = simple_route()
    geometry = {
        "gtol": LeaderGeometry(
            tuple(Segment(line.end, line.start) for line in route.segments[::-1]), ()
        )
    }
    cells = {"text": text_cell(Rect(0.29, 0.09, 0.31, 0.11))}
    with pytest.raises(ValueError, match="three-point"):
        policy.column_vertical_candidates(crossings(geometry, cells), geometry, cells)
