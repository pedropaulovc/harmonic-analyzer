"""Offline contracts for the leader geometry the crank drawings gate on."""

from __future__ import annotations

import pytest

import _drawing_leaders as leaders


def test_segments_cross_only_on_a_proper_intersection() -> None:
    assert leaders.segments_cross(((0, 0), (1, 1)), ((0, 1), (1, 0)))
    assert not leaders.segments_cross(((0, 0), (1, 0)), ((0, 1), (1, 1)))
    # A shared endpoint, or a T that stops short, is not a crossing.
    assert not leaders.segments_cross(((0, 0), (1, 0)), ((1, 0), (1, 1)))
    assert not leaders.segments_cross(((0, 0), (1, 0)), ((0.5, 0.1), (0.5, 1)))


def test_a_leader_laid_along_another_line_crosses_it() -> None:
    # Main's rider on _drawing_leaders: collinear overlap prints as one stroke.
    tol = leaders.COLLINEAR_TOLERANCE
    base = ((0.0, 0.0), (0.010, 0.0))
    assert leaders.segments_cross(base, ((0.004, 0.0), (0.020, 0.0)))
    assert leaders.segments_cross(base, ((0.002, tol / 2), (0.006, -tol / 2)))
    assert leaders.segments_cross(((0.004, 0.0), (0.006, 0.0)), base)  # contained
    # Collinear but apart, touching end to end, or parallel beyond the tolerance.
    assert not leaders.segments_cross(base, ((0.012, 0.0), (0.020, 0.0)))
    assert not leaders.segments_cross(base, ((0.010, 0.0), (0.020, 0.0)))
    assert not leaders.segments_cross(base, ((0.002, 2 * tol), (0.008, 2 * tol)))


def test_distance_to_point_clamps_to_the_segment() -> None:
    assert leaders.distance_to_point(((0, 0), (2, 0)), (1, 1)) == pytest.approx(1.0)
    assert leaders.distance_to_point(((0, 0), (2, 0)), (3, 0)) == pytest.approx(1.0)
    assert leaders.distance_to_point(((1, 1), (1, 1)), (1, 2)) == pytest.approx(1.0)


def test_assert_leaders_clear_names_crossings_intrusions_and_missing_ink() -> None:
    through = [((-1.0, 1.0), (1.0, -1.0))]
    radius = [((-2.0, 0.5), (0.4, -0.1))]
    near = [((-0.3, 1.0), (-0.1, 0.4))]
    anywhere = {"A": (0.0, 9.0), "B": (0.0, 9.0)}
    with pytest.raises(RuntimeError, match=r"crossings \[\('A', 'B'\)\]"):
        leaders.assert_leaders_clear(
            {"A": through, "B": radius}, centre=(0.0, 0.0), keep_out={},
            lands_within=anywhere, label="t",
        )
    with pytest.raises(RuntimeError, match="inside the keep-out"):
        leaders.assert_leaders_clear(
            {"A": through}, centre=(0.0, 0.0), keep_out={"A": 0.2},
            lands_within=anywhere, label="t",
        )
    with pytest.raises(RuntimeError, match=r"no ink read for \['B'\]"):
        leaders.assert_leaders_clear(
            {"A": near, "B": []}, centre=(0.0, 0.0), keep_out={},
            lands_within=anywhere, label="t",
        )
    # Segments read in the wrong space (here: shifted far off the feature)
    # land nowhere near it, so the check cannot pass vacuously.
    shifted = [((x + 5.0, y + 5.0), (u + 5.0, v + 5.0)) for (x, y), (u, v) in near]
    with pytest.raises(RuntimeError, match="landing off its feature"):
        leaders.assert_leaders_clear(
            {"A": shifted}, centre=(0.0, 0.0), keep_out={"A": 0.2},
            lands_within={"A": (0.3, 0.5)}, label="t",
        )
    with pytest.raises(ValueError, match="no landing band"):
        leaders.assert_leaders_clear(
            {"A": near}, centre=(0.0, 0.0), keep_out={}, lands_within={}, label="t"
        )
    # A leader that only ENDS at the centre (R12.7 does) is caught by the
    # keep-out, not as a crossing: the endpoint touch is not proper.
    assert not leaders.segments_cross(through[0], ((-2.0, 0.5), (0.0, 0.0)))
    leaders.assert_leaders_clear(
        {"A": near, "B": radius}, centre=(0.0, 0.0), keep_out={"A": 0.2},
        lands_within={"A": (0.3, 0.5), "B": (0.3, 0.5)}, label="t",
    )


def test_section_line_info_parses_chain_segments_and_arrow_shafts() -> None:
    # One section line, two chain segments, two arrows, two labels.
    chain = [4, 0.1, 0.1, 0.0, 0.1, 0.2, 0.0, 4, 0.1, 0.2, 0.0, 0.1, 0.3, 0.0]
    arrow1 = [0.1, 0.1, 0.0, 0.12, 0.1, 0.0, 0.002, 0.004, 1]
    arrow2 = [0.1, 0.3, 0.0, 0.12, 0.3, 0.0, 0.002, 0.004, 1]
    text = [0.13, 0.1, 0.0, 0.13, 0.3, 0.0, 0.005]
    values = [1, 0, 2, *chain, *arrow1, *arrow2, *text]
    assert leaders.parse_section_line_info(values) == [
        ((0.1, 0.1), (0.1, 0.2)),
        ((0.1, 0.2), (0.1, 0.3)),
        ((0.1, 0.1), (0.12, 0.1)),
        ((0.1, 0.3), (0.12, 0.3)),
    ]
    assert leaders.parse_section_line_info([]) == []
    with pytest.raises(RuntimeError, match="parsed"):
        leaders.parse_section_line_info([*values, 0.0])


def test_points_inside_is_strict() -> None:
    box = (0.0, 0.0, 1.0, 1.0)
    assert leaders.points_inside([(0.5, 0.5), (1.5, 0.5), (1.0, 0.5)], box) == [(0.5, 0.5)]
