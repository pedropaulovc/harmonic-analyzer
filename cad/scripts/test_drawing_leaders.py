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


def test_distance_to_point_clamps_to_the_segment() -> None:
    assert leaders.distance_to_point(((0, 0), (2, 0)), (1, 1)) == pytest.approx(1.0)
    assert leaders.distance_to_point(((0, 0), (2, 0)), (3, 0)) == pytest.approx(1.0)
    assert leaders.distance_to_point(((1, 1), (1, 1)), (1, 2)) == pytest.approx(1.0)


def test_assert_leaders_clear_names_crossings_intrusions_and_missing_ink() -> None:
    through = [((-1.0, 1.0), (1.0, -1.0))]
    radius = [((-2.0, 0.5), (0.4, -0.1))]
    near = [((-0.3, 1.0), (-0.1, 0.4))]
    with pytest.raises(RuntimeError, match=r"crossings \[\('A', 'B'\)\]"):
        leaders.assert_leaders_clear(
            {"A": through, "B": radius}, centre=(0.0, 0.0), keep_out={}, label="t"
        )
    with pytest.raises(RuntimeError, match="inside the keep-out"):
        leaders.assert_leaders_clear(
            {"A": through}, centre=(0.0, 0.0), keep_out={"A": 0.2}, label="t"
        )
    with pytest.raises(RuntimeError, match=r"no ink read for \['B'\]"):
        leaders.assert_leaders_clear(
            {"A": near, "B": []}, centre=(0.0, 0.0), keep_out={}, label="t"
        )
    # A leader that only ENDS at the centre (R12.7 does) is caught by the
    # keep-out, not as a crossing: the endpoint touch is not proper.
    assert not leaders.segments_cross(through[0], ((-2.0, 0.5), (0.0, 0.0)))
    leaders.assert_leaders_clear(
        {"A": near, "B": radius}, centre=(0.0, 0.0), keep_out={"A": 0.2}, label="t"
    )
