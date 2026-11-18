"""The measuring stick's registration on a rocker arm (#2434, option 2)."""

from __future__ import annotations

import math

import pytest

import ms_stick_registration as registration
import ms_stick_spec as stick


def test_the_stick_as_drawn_reads_a_common_offset_from_the_pivot() -> None:
    """Michelson's method with the stick as drawn: the reading for station d
    is (d + ~2.7 mm)/14.2 across the whole travel, the figure the 2026-11-15
    owner pack derived (2.74 over seven stations; issue-2434-registration.py
    on dfm-evidence/2434)."""
    assert registration.MEAN_OFFSET_MM == pytest.approx(2.72, abs=0.02)
    assert registration.OFFSET_SPREAD_MM < 0.1
    for station in (0.0, 22.0, 44.0, registration.MAX_STATION_MM):
        reading = registration.stick_reading(station)
        assert stick.DIVISION_SPACING * reading - station == pytest.approx(
            registration.MEAN_OFFSET_MM, abs=registration.OFFSET_SPREAD_MM + 1e-9
        )
    # The pack's per-station figures, reproduced from the specs.
    assert registration.stick_reading(0.0) == pytest.approx(0.1983, abs=5e-4)
    assert registration.stick_reading(88.0) == pytest.approx(6.3935, abs=5e-4)


def test_zero_is_the_stop_on_the_two_tenths_tick() -> None:
    assert registration.ZERO_TICK_TEXT == "0.2"
    assert abs(registration.ZERO_TICK_STATION_MM) < 0.05
    assert registration.station_for_reading(registration.ZERO_READING) == pytest.approx(0.0, abs=1e-6)


def test_the_registration_touches_the_surfaces_it_names() -> None:
    """The 10 end's top corner touches the bar's outboard face; the resting
    corner lies on the arm's top edge; the stop face reaches the land's
    bottom corner, square to the stick."""
    for station in (0.0, 36.0, registration.MAX_STATION_MM):
        g = registration.register(station)
        (fx, fy), (ux, uy) = g.bar_face_bottom, g.bar_face_up
        tx, ty = g.ten_end_top
        assert tx == pytest.approx(fx + (ty - fy) / uy * ux, abs=1e-6)
        ex, ey = g.ten_end_bottom
        assert ey == pytest.approx(registration.top_edge_y(ex), abs=1e-9)
        assert math.dist(g.ten_end_top, g.ten_end_bottom) == pytest.approx(stick.BODY_THICKNESS)
        assert 0.0 < g.land_depth_mm < registration.STOP_FACE_DEPTH_MM
        # The stick rests on the tip corner: its slope runs E to T.
        tip = registration.TIP_CORNER
        assert math.degrees(math.atan2(tip[1] - ey, tip[0] - ex)) == pytest.approx(g.slope_deg)
