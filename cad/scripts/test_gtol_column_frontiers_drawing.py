"""Pure replay of the half-scale lever's measured native column routes.

Source: datum-policy-9v0ujds_/pilot.json, SHA256
7b5146812d689d104fadc644f64926026b19f1088895e7389a5e88bd8426d5ae,
recipe42ccf5a6. Two horizontal chains and four rejected vertical offsets were
captured. For the prediction ONLY, both shoulder endpoints move by dy and each
model endpoint stays fixed. Native acceptance must re-read the actual routes;
this fixture contains only the four cells reported across the six failures,
not the complete sheet, native GTol bodies, or final packing measurements.
"""

from types import SimpleNamespace

import pytest

import _drawing_native_gtol as policy
from _drawing_annotation_bounds import LeaderGeometry, Segment
from _drawing_leader_clearance import crossing_records, vertical_candidates
from _drawing_view_packing import Rect


def half_scale_lever_fixture(side="right"):
    # Exact native shoulder start/elbow X, shoulder Y, and fixed attachment XY.
    coordinates = (
        (
            "DetailItem350",
            0.22571249995300008,
            0.21936249995300008,
            -0.013138348769214818,
            -0.006788348769214818,
            0.15387500001249999,
            0.18955000002099995,
            0.1573750000125,
        ),
        (
            "DetailItem354",
            0.22593119077101065,
            0.21958119077101065,
            -0.020854546077532822,
            -0.014504546077532822,
            0.14487500001249998,
            0.1066749999725,
            0.155,
        ),
        (
            "DetailItem356",
            0.22590097023215938,
            0.2195509702321594,
            -0.01012712782629819,
            -0.0037771278262981895,
            0.13587500001249997,
            0.169048474984,
            0.155,
        ),
        (
            "DetailItem357",
            0.22578279628602355,
            0.21943279628602355,
            -0.010245301772434025,
            -0.003895301772434025,
            0.12687500001249996,
            0.194959649984,
            0.155,
        ),
    )
    arrows = (
        Rect(
            0.18591327347092776,
            0.1537382734624278,
            0.19318672657107214,
            0.16101172656257218,
        ),
        Rect(
            0.10303827342242781,
            0.1513632734499278,
            0.11031172652257219,
            0.1586367265500722,
        ),
        Rect(
            0.1654117484339278,
            0.1513632734499278,
            0.17268520153407219,
            0.1586367265500722,
        ),
        Rect(
            0.19132292343392782,
            0.1513632734499278,
            0.1985963765340722,
            0.1586367265500722,
        ),
    )
    geometry = {}
    for index, (name, rx, re, lx, le, y, ax, ay) in enumerate(coordinates):
        x, elbow = (rx, re) if side == "right" else (lx, le)
        decorations = (arrows[index],)
        if index == 0:
            decorations = (
                Rect(elbow - 0.00175, y - 0.00175, elbow + 0.00175, y + 0.00175),
                *decorations,
            )
        geometry[name] = LeaderGeometry(
            (Segment((x, y), (elbow, y)), Segment((elbow, y), (ax, ay))), decorations
        )
    cells = {}
    for name, kind, text, bounds in (
        (
            "RD3",
            4,
            "9.50",
            (
                0.209361874956129,
                0.14181999982002955,
                0.218432874956129,
                0.14739986648669623,
            ),
        ),
        (
            "RD1",
            4,
            "127.00",
            (
                0.1296781941436046,
                0.14032312485905918,
                0.14392172747693793,
                0.14590299152572586,
            ),
        ),
        (
            "DetailItem348",
            2,
            "B",
            (
                -0.005976363768177645,
                0.14258876170500057,
                -0.0032767637681776454,
                0.14816862837166725,
            ),
        ),
        (
            "NoseRadius",
            4,
            "R4.75",
            (
                0.07238270765139358,
                0.16521187479884736,
                0.08428590765139357,
                0.17079174146551404,
            ),
        ),
    ):
        cells[name] = SimpleNamespace(
            kind=kind,
            text_boxes=(Rect(*bounds),),
            text_runs=(SimpleNamespace(value=text),),
        )
    return geometry, cells


def predict_routes(geometry, dy):
    """Test-only three-point hypothesis; never used as native acceptance data."""
    result = {}
    for name, row in geometry.items():
        first, diagonal = row.segments
        start = (first.start[0], first.start[1] + dy)
        elbow = (first.end[0], first.end[1] + dy)
        decorations = row.decorations
        if name == "DetailItem350":
            decorations = (decorations[0].translated((0, dy)), *decorations[1:])
        result[name] = LeaderGeometry(
            (Segment(start, elbow), Segment(elbow, diagonal.end)), decorations
        )
    return result


def crossings(geometry, cells):
    return crossing_records(
        {name: row.segments for name, row in geometry.items()},
        cells,
        {name: row.decorations for name, row in geometry.items()},
    )


@pytest.mark.parametrize(
    "side,dy,expected",
    [
        ("right", 0, {("DetailItem354", "RD3")}),
        ("left", 0, {("DetailItem354", "DetailItem348"), ("DetailItem357", "RD1")}),
        (
            "left",
            0.0200279915132259,
            {("DetailItem350", "NoseRadius"), ("DetailItem357", "DetailItem348")},
        ),
        (
            "left",
            -0.0032862383074994117,
            {("DetailItem354", "DetailItem348"), ("DetailItem357", "RD1")},
        ),
        ("right", 0.003524866474196253, {("DetailItem356", "RD3")}),
        ("right", -0.0040550001924704315, {("DetailItem354", "RD3")}),
    ],
)
def test_replay_all_six_captured_crossing_sets(side, dy, expected):
    geometry, cells = half_scale_lever_fixture(side)
    hits = crossings(predict_routes(geometry, dy), cells)
    assert {
        (hit["leader_annotation"], hit["target_annotation"]) for hit in hits
    } == expected


def test_whole_bank_frontier_clears_known_cells_after_old_lift_hits_next_row():
    geometry, cells = half_scale_lever_fixture()
    initial_hits = crossings(geometry, cells)
    old_up, _ = vertical_candidates(
        initial_hits,
        {name: row.segments for name, row in geometry.items()},
        {name: row.decorations for name, row in geometry.items()},
    )
    assert old_up.dy_m == pytest.approx(0.003524866474196253)
    assert (
        crossings(predict_routes(geometry, old_up.dy_m), cells)[0]["leader_annotation"]
        == "DetailItem356"
    )
    up, down = policy.column_vertical_candidates(initial_hits, geometry, cells)
    assert up.dy_m == pytest.approx(0.02152486647419627)
    assert up.dy_m > old_up.dy_m and down.dy_m < 0
    assert crossings(predict_routes(geometry, up.dy_m), cells) == []
    for name, row in geometry.items():
        assert (
            predict_routes(geometry, up.dy_m)[name].segments[1].end
            == row.segments[1].end
        )


def test_cell_outside_every_native_route_x_range_cannot_drive_vertical_frontier():
    geometry, cells = half_scale_lever_fixture()
    hits = crossings(geometry, cells)
    baseline = policy.column_vertical_candidates(hits, geometry, cells)
    cells["distant"] = SimpleNamespace(kind=4, text_boxes=(Rect(2, 3, 4, 5),))
    assert policy.column_vertical_candidates(hits, geometry, cells) == baseline


def test_moving_gtol_body_is_not_mistaken_for_a_stationary_text_obstacle():
    geometry, cells = half_scale_lever_fixture()
    hits = crossings(geometry, cells)
    baseline = policy.column_vertical_candidates(hits, geometry, cells)
    cells["DetailItem350"] = SimpleNamespace(kind=5, text_boxes=(Rect(0.2, 3, 0.3, 5),))
    assert policy.column_vertical_candidates(hits, geometry, cells) == baseline


def test_previously_unhit_upper_cell_must_not_force_bank_above_a_clear_gap():
    geometry, cells = half_scale_lever_fixture()
    hits = crossings(geometry, cells)
    cells["higher-dimension"] = SimpleNamespace(
        kind=4, text_boxes=(Rect(0.21, 0.18, 0.218, 0.185),)
    )
    up, _ = policy.column_vertical_candidates(hits, geometry, cells)
    # The old maximum-frontier contract was deliberately superseded by the
    # measured ten-cell failure: both upper and lower obstacles bound a gap.
    assert up.dy_m == pytest.approx(0.02152486647419627)
    assert crossings(predict_routes(geometry, up.dy_m), cells) == []


def test_noninitial_row_width_and_decoration_are_not_dropped():
    geometry, cells = half_scale_lever_fixture()
    hits = crossings(geometry, cells)
    row = geometry["DetailItem357"]
    geometry["DetailItem357"] = LeaderGeometry(
        tuple(Segment(line.start, line.end, 0.0004) for line in row.segments),
        row.decorations,
    )
    up, _ = policy.column_vertical_candidates(hits, geometry, cells)
    assert up.dy_m == pytest.approx(0.02152486647419627 + 0.0002)
    geometry["DetailItem357"] = LeaderGeometry(
        row.segments, (*row.decorations, Rect(0.21, 0.120, 0.218, 0.122))
    )
    # An unassociated synthetic box is not evidence that a decoration follows
    # the shoulder. The new prediction must reject this unsupported shape.
    with pytest.raises(ValueError, match="decoration"):
        policy.column_vertical_candidates(hits, geometry, cells)


@pytest.mark.parametrize("fault", ["shape", "disconnected", "nan", "negative_width"])
def test_unsupported_noninitial_row_is_not_guessed_as_a_bent_route(fault):
    geometry, cells = half_scale_lever_fixture()
    hits = crossings(geometry, cells)
    first, second = geometry["DetailItem357"].segments
    if fault == "shape":
        lines = (first,)
    elif fault == "disconnected":
        lines = (first, Segment((0.0, 0.0), second.end))
    elif fault == "nan":
        lines = (Segment((float("nan"), first.start[1]), first.end), second)
    else:
        lines = (Segment(first.start, first.end, -1), second)
    geometry["DetailItem357"] = LeaderGeometry(lines, ())
    with pytest.raises(ValueError, match="whole-bank frontier"):
        policy.column_vertical_candidates(hits, geometry, cells)


@pytest.mark.parametrize("clearance", [-1, float("inf"), float("nan")])
def test_frontier_rejects_invalid_clearance(clearance):
    geometry, cells = half_scale_lever_fixture()
    with pytest.raises(ValueError, match="clearance"):
        policy.column_vertical_candidates(
            crossings(geometry, cells), geometry, cells, clearance_m=clearance
        )
