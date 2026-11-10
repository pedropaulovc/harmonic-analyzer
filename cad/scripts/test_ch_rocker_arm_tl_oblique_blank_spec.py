"""Pure contracts for the R4 raw-edge-referenced preform and full envelopes."""
from __future__ import annotations

import math

import pytest

import ch_rocker_arm_tl_oblique_blank_spec as blank
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_tl_oblique_riser_spec as riser
from _mcmaster_91251a197 import DIMS as common_screw


def test_roughing_bias_preserves_product_and_real_stock() -> None:
    assert blank.INNER_STATIONS == (30.0, 90.0, 150.0)
    assert blank.OUTER_STATIONS == (0.0, 160.0)
    assert blank.INNER_ANCHOR_RADIUS == 795.080
    assert blank.OUTER_ANCHOR_RADIUS == 821.210
    assert trammel.R_C1 == 795.2375
    assert trammel.R_C2 == 820.7625
    for anchors, radius in ((blank.INNER_ANCHORS, blank.INNER_ANCHOR_RADIUS),
                            (blank.OUTER_ANCHORS, blank.OUTER_ANCHOR_RADIUS)):
        for x, y in anchors:
            assert math.hypot(x, y + trammel.H1) == pytest.approx(radius)
    assert trammel.BLANK_LENGTH == 350.0
    assert blank.BLANK_WIDTH == 38.1
    assert (blank.RAW_Y_MIN, blank.RAW_Y_MAX) == pytest.approx((19.5791335401, 57.6791335401))
    assert blank.RAW_Y_MAX - trammel.STRAP_SPAN_Y[1] == pytest.approx(4.4026799405)
    for x, y in blank.BLANK_OUTLINE:
        assert -175.0 <= x <= 175.0
        assert blank.RAW_Y_MIN - 1e-9 <= y <= blank.RAW_Y_MAX + 1e-9
    assert min(x for x, _ in blank.BLANK_OUTLINE) == -175.0
    assert max(x for x, _ in blank.BLANK_OUTLINE) == 175.0


def test_layout_uses_raw_edge_and_end_midpoint_not_hub() -> None:
    assert blank.LAYOUT_DATUM == (0.0, blank.RAW_Y_MIN)
    assert blank.SAW_EDGE_TOLERANCE == 0.5  # total layout + saw, not separate .5 errors
    assert blank.LAYOUT_ROUNDING_ERROR == pytest.approx(math.sqrt(2.0) * 0.0127)
    assert blank.ACCEPTED_EDGE_CORRIDOR == pytest.approx(0.5 + math.sqrt(2.0) * 0.0127)
    for name, anchors in (("inner", blank.INNER_ANCHORS), ("outer", blank.OUTER_ANCHORS)):
        for mark, (x, y) in zip(blank.LAYOUT_MARKS[name], anchors, strict=True):
            assert math.dist(mark, (x, y - blank.RAW_Y_MIN)) <= blank.LAYOUT_ROUNDING_ERROR + 1e-9
            for coordinate in mark:
                assert coordinate / 25.4 == pytest.approx(round(coordinate / 25.4, 3))


def test_continuous_directional_allowances_include_yaw_and_rounding() -> None:
    assert blank.LONGITUDINAL_SETUP_ERROR == 0.5
    assert 0.57 < blank.LONGITUDINAL_ERROR < 0.59
    assert blank.REGISTRATION_Y_ERROR[0] < riser.STOP_RAW_Y_LIMITS[0] - blank.RAW_Y_MIN
    assert blank.REGISTRATION_Y_ERROR[1] > riser.STOP_RAW_Y_LIMITS[1] - blank.RAW_Y_MIN
    evidence = blank.proof()
    for name, result in evidence.items():
        assert result.accepted_sliver_margin >= blank.SLIVER_MARGIN_MIN == 3.0
        assert result.accepted_finish_stock > blank.FINISH_STOCK_MIN_BY_PASS[name]
    assert 4.03 < evidence["inner"].accepted_finish_stock < 4.05
    assert 0.30 < evidence["outer"].accepted_finish_stock < 0.32
    assert 3.49 < evidence["outer"].accepted_sliver_margin < 3.52


def test_each_chord_is_required_by_the_accepted_envelope() -> None:
    for name, anchors in (("inner", blank.INNER_ANCHORS), ("outer", blank.OUTER_ANCHORS)):
        assert len(anchors) - 1 == {"inner": 5, "outer": 2}[name]
        for index in range(1, len(anchors) - 1):
            pruned = blank._extend(anchors[:index] + anchors[index + 1:])
            low, high = blank.directional_radial_bounds(pruned, trammel.TIP_ANGLE)
            if name == "inner":
                margin = low - (trammel.R_C1 - trammel.PART_CUTTER_DIA / 2.0) - blank.ACCEPTED_EDGE_CORRIDOR
                assert margin < blank.SLIVER_MARGIN_MIN
            else:
                assert low - trammel.R_OUTER - blank.ACCEPTED_EDGE_CORRIDOR < 0.0


def test_directional_extrema_contain_every_translated_segment_sample() -> None:
    chain = blank.INNER_VERTICES
    low, high = blank.directional_radial_bounds(chain, trammel.TIP_ANGLE)
    for a, b in zip(chain, chain[1:]):
        for dx in (-blank.LONGITUDINAL_ERROR, 0.0, blank.LONGITUDINAL_ERROR):
            for dy in (*blank.REGISTRATION_Y_ERROR, sum(blank.REGISTRATION_Y_ERROR) / 2.0):
                for i in range(21):
                    t = i / 20.0
                    x, y = a[0] + t * (b[0] - a[0]) + dx, a[1] + t * (b[1] - a[1]) + dy
                    if abs(math.atan2(x, y + trammel.H1)) <= trammel.TIP_ANGLE:
                        assert low - 1e-9 <= math.hypot(x, y + trammel.H1) <= high + 1e-9


def test_exact_extremum_finds_between_station_minimum() -> None:
    chain = ((-6.0, 8.0 - trammel.H1), (6.0, 8.0 - trammel.H1))
    assert blank._radial_bounds(chain, math.pi / 4.0) == pytest.approx((8.0, 10.0))
    assert blank._radial_bounds(chain, math.atan(0.25)) == pytest.approx((8.0, math.sqrt(68.0)))


@pytest.mark.parametrize("centre, expected", [((0.0, 0.0), math.pi), ((5.0, 0.0), 0.0), ((2.0, 0.0), math.pi / 2.0)])
def test_exact_disk_polygon_area_controls(centre, expected) -> None:
    square = ((-2.0, -2.0), (2.0, -2.0), (2.0, 2.0), (-2.0, 2.0))
    assert blank.disk_material_area(centre, 1.0, square) == pytest.approx(expected, abs=1e-10)


def test_entry_fraction_is_nominal_side_engagement_not_a_false_accepted_percentage() -> None:
    for result in blank.proof().values():
        left, right = result.entry_air_fraction
        assert 0.0 < left < 1.0
        assert left == pytest.approx(right)
    # Accepted side entry is certified by the scrap-side overlap, not the
    # retired R3 >30% statement which omitted registration and longitudinal error.
    assert min(p.accepted_sliver_margin for p in blank.proof().values()) >= 3.0


def test_two_common_heads_and_hub_washer_have_real_stock_under_them() -> None:
    import ch_rocker_arm_tl_oblique_hub_washer_spec as washer

    for point, radius in ((trammel.CL, common_screw.head_dia / 2.0),
                          (trammel.CR, common_screw.head_dia / 2.0),
                          (trammel.HUB, washer.OD / 2.0)):
        assert blank.disk_material_area(point, radius) == pytest.approx(math.pi * radius**2, abs=1e-8)
