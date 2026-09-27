"""The cone-shaft tip seats on the 94025A150 cup WALL, derived, never tuned.

A flat shaft end in a conical cup touches along the ring where its end edge
meets the cone, end-radius / tan(half-angle) short of the apex. Placing it AT
the apex buried 1.05 mm^3 of steel once the tip journal grew to 1/16 in
(run 20260923T032622366Z-79c0b168, gate.interference).
"""

from __future__ import annotations

import math

import pytest

import build_drive_train_assembly as bdt
from build_cone_tip_adjuster import CUP_DEPTH, CUP_DIA
from cone_gear_shaft_spec import ADJUSTER_EMBED, SECTIONS


def test_seat_depth_is_the_end_radius_over_the_cup_half_angle() -> None:
    end_radius = SECTIONS[-1][0] * 25.4 / 2.0
    half_angle = math.atan((CUP_DIA / 2.0) / CUP_DEPTH)
    assert bdt.ADJ_CUP_HALF_ANGLE == pytest.approx(half_angle, abs=1e-12)
    assert bdt.ADJ_SEAT_DEPTH == pytest.approx(end_radius / math.tan(half_angle), abs=1e-12)
    assert 0.0 < bdt.ADJ_SEAT_DEPTH < CUP_DEPTH


def test_the_vendor_cup_is_the_90_degree_cone_the_derivation_reads() -> None:
    # 94025A150 Sketch2: rim radius equals cup depth, a 45 deg half-angle, so a
    # 1/16 in end seats exactly one end radius (0.79375) short of the apex.
    assert math.degrees(bdt.ADJ_CUP_HALF_ANGLE) == pytest.approx(45.0, abs=1e-6)
    assert bdt.ADJ_SEAT_DEPTH == pytest.approx(25.4 / 32.0, abs=1e-9)


def test_shaft_end_meets_the_cup_wall_and_the_adjuster_backs_out_by_that_depth() -> None:
    tip_end = bdt.SHAFT_FRONT_STATION + SECTIONS[-1][1]
    apex = bdt.ADJ_HEAD_STATION - bdt.ADJ_LEN + CUP_DEPTH
    assert apex - tip_end == pytest.approx(bdt.ADJ_SEAT_DEPTH, abs=1e-9)
    assert bdt.ADJ_THREAD_ENGAGEMENT == pytest.approx(
        ADJUSTER_EMBED - bdt.ADJ_SEAT_DEPTH, abs=1e-12
    )
