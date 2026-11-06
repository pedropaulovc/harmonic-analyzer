"""Offline contracts for the held bandsaw-before-jig route; no COM imports."""

from __future__ import annotations

import math
import tomllib
from pathlib import Path

import pytest

import ch_rocker_arm_tl_oblique_blank_spec as blank
import ch_rocker_arm_tl_oblique_trammel_spec as trammel


def test_circle_anchors_and_clipped_purchased_stock() -> None:
    assert blank.INNER_STATIONS == (0.0, 75.0, 148.0)
    assert blank.OUTER_STATIONS == (20.0, 60.0, 100.0, 140.0)
    for anchors, radius in ((blank.INNER_ANCHORS, trammel.R_C1), (blank.OUTER_ANCHORS, trammel.R_C2)):
        for x, y in anchors:
            assert math.hypot(x, y + trammel.H1) == pytest.approx(radius)
    assert trammel.BLANK_LENGTH == 350.0
    assert trammel.BLANK_WIDTH == 38.1
    for x, y in blank.BLANK_OUTLINE:
        assert -175.0 <= x <= 175.0
        assert blank.RAW_Y_MIN - 1e-9 <= y <= blank.RAW_Y_MAX + 1e-9
    assert min(x for x, _ in blank.BLANK_OUTLINE) == -175.0
    assert max(x for x, _ in blank.BLANK_OUTLINE) == 175.0
    # Complete circles to the ends need >45 mm, so treating the unclipped
    # virtual anchors as physical stock would silently invent material.
    assert trammel.R_C2 - math.sqrt(trammel.R_C1**2 - 175.0**2) > trammel.BLANK_WIDTH


def test_continuous_radial_allowance_and_sliver_margin() -> None:
    for name, evidence in blank.proof().items():
        assert evidence.accepted_sliver_margin >= blank.SLIVER_MARGIN_MIN
        assert evidence.accepted_finish_stock >= blank.FINISH_STOCK_MIN
        low, high = evidence.swept_radius_bounds
        radius, cutter = trammel.PASS_RADIUS[name], trammel.PART_CUTTER_DIA / 2.0
        # Both sides of the pre-sawn edge stay inside the full swept annulus.
        assert radius - cutter < low - blank.SAW_EDGE_TOLERANCE
        assert high + blank.SAW_EDGE_TOLERANCE < radius + cutter
    inner, outer = blank.proof()["inner"], blank.proof()["outer"]
    assert inner.finished_radius_bounds == pytest.approx((794.350861016, 795.522918577), abs=1e-8)
    assert inner.accepted_sliver_margin == pytest.approx(3.375861016, abs=1e-8)
    assert inner.accepted_finish_stock == pytest.approx(4.2625, abs=1e-8)
    assert outer.accepted_sliver_margin == pytest.approx(3.648211261, abs=1e-8)
    assert outer.accepted_finish_stock == pytest.approx(4.013460462, abs=1e-8)


def test_cut_counts_and_no_redundant_interior_anchor() -> None:
    # Counts are full-edge straight cuts; rolled stock portions are NOT cuts.
    assert len(blank.INNER_ANCHORS) - 1 == 4
    assert len(blank.OUTER_ANCHORS) - 1 == 7
    assert blank.SAW_EDGE_TOLERANCE == 0.5
    for name, anchors in (("inner", blank.INNER_ANCHORS), ("outer", blank.OUTER_ANCHORS)):
        for index in range(1, len(anchors) - 1):
            pruned = blank._extend(anchors[:index] + anchors[index + 1:])
            low, high = blank._radial_bounds(pruned, trammel.TIP_ANGLE)
            if name == "inner":
                margin = low - (trammel.R_C1 - trammel.PART_CUTTER_DIA / 2.0) - 0.5
                assert margin < blank.SLIVER_MARGIN_MIN
            else:
                assert low - trammel.R_OUTER - 0.5 < blank.FINISH_STOCK_MIN


def test_exact_extremum_finds_between_station_minimum() -> None:
    # Endpoints both radius 10, interior radius 8: endpoint-only or sparse
    # station checking cannot be the implementation of the radial proof.
    chain = ((-6.0, 8.0 - trammel.H1), (6.0, 8.0 - trammel.H1))
    assert blank._radial_bounds(chain, math.pi / 4.0) == pytest.approx((8.0, 10.0))
    # Tight wedge must clip the segment at rays rather than keep its endpoints.
    assert blank._radial_bounds(chain, math.atan(0.25)) == pytest.approx((8.0, math.sqrt(68.0)))


@pytest.mark.parametrize("centre, expected", [((0.0, 0.0), math.pi), ((5.0, 0.0), 0.0), ((2.0, 0.0), math.pi / 2.0)])
def test_exact_disk_polygon_area_controls(centre, expected) -> None:
    square = ((-2.0, -2.0), (2.0, -2.0), (2.0, 2.0), (-2.0, 2.0))
    assert blank.disk_material_area(centre, 1.0, square) == pytest.approx(expected, abs=1e-10)


def test_entry_is_side_engagement_at_either_stop() -> None:
    evidence = blank.proof()
    for name, expected in (("inner", 0.7257136568), ("outer", 0.4212195013)):
        assert evidence[name].entry_air_fraction == pytest.approx((expected, expected), abs=1e-8)
        # A 0.5 mm normal corridor can change disk occupancy by at most
        # a 2r-wide strip plus end caps; still comfortably >30% open at entry.
        cutter = trammel.PART_CUTTER_DIA / 2.0
        error_area = 2.0 * cutter * blank.SAW_EDGE_TOLERANCE + math.pi * blank.SAW_EDGE_TOLERANCE**2
        assert min(evidence[name].entry_air_fraction) - error_area / (math.pi * cutter**2) > 0.3


def test_locator_and_hold_down_bearing_are_actual_stock() -> None:
    import ch_rocker_arm_tl_vn_oblique_clamp_screw_spec as cr_screw
    import ch_rocker_arm_tl_vn_oblique_left_clamp_screw_spec as left_screw

    # CR stays as bought; LEFT uses its supplier head, HUB its 11 mm brass
    # washer. CL remains a separate 1/4 locator. Not a clearance certificate.
    footprints = (
        (trammel.LEFT_CLAMP, left_screw.DIMS.head_dia / 2.0),
        (trammel.CR, cr_screw.DIMS.head_dia / 2.0),
        (trammel.HUB, 11.0 / 2.0),
        (trammel.CL, 3.175),
    )
    for point, radius in footprints:
        assert blank.disk_material_area(point, radius) == pytest.approx(math.pi * radius**2, abs=1e-8)
    assert trammel.LEFT_CLAMP[0] == -169.5
    assert trammel.LEFT_CLAMP != trammel.CL
    x, y = trammel.LEFT_CLAMP
    head_radius = left_screw.DIMS.head_dia / 2.0
    left, bottom = trammel.RISER_BLANK_ORIGIN
    assert left <= x - head_radius < x + head_radius <= left + trammel.RISER_BLANK_LENGTH
    assert bottom <= y - head_radius < y + head_radius <= bottom + trammel.RISER_BLANK_WIDTH
    # sin(theta) is monotone throughout each +/-11 degree pass, so its stop
    # is the exact maximum X of the riser's self-cut swept disk. The entire
    # LEFT bearing pad is outboard of both sweeps, on uncut riser stock.
    self_cut_x_max = max(
        radius * math.sin(trammel.SWEEP[name]) + trammel.RISER_CUTTER_DIA / 2.0
        for name, radius in trammel.PASS_RADIUS.items()
    )
    assert abs(x) - head_radius > self_cut_x_max


def test_held_process_layout_matches_geometry_without_chain_drilling() -> None:
    path = Path(__file__).resolve().parents[1] / "process" / "ch_rocker_arm" / "plan.toml"
    text = path.read_text(encoding="utf-8")
    plan = tomllib.loads(text)
    assert text.startswith("# HELD REFERENCE ROUTE")
    assert plan["construction"] == "built_up"
    assert plan["stock"]["length_mm"] == trammel.BLANK_LENGTH
    assert plan["stock"]["section_mm"] == [trammel.BLANK_WIDTH, 3.175]
    assert plan["stock"]["origin_mm"] == pytest.approx((-175.0, blank.RAW_Y_MIN, 0.0))
    layout = plan["bandsaw_preform"]
    assert layout["retained_edge_normal_error_max_mm"] == blank.SAW_EDGE_TOLERANCE
    for key, anchors in (("inner_anchors_mm", blank.INNER_ANCHORS), ("outer_anchors_mm", blank.OUTER_ANCHORS)):
        assert len(layout[key]) == len(anchors)
        for actual, expected in zip(layout[key], anchors):
            assert actual == pytest.approx(expected)
    assert layout["raw_y_limits_mm"] == pytest.approx((blank.RAW_Y_MIN, blank.RAW_Y_MAX))
    assert all(op.get("contour", {}).get("method") != "chain_drill" for setup in plan["setups"] for op in setup["ops"])
    assert [setup["id"] for setup in plan["setups"]] == ["S0", "S1", "S2", "S3", "S4", "S5"]
    setup = next(setup for setup in plan["setups"] if setup["id"] == "S2")
    holes = next(op["note"] for op in setup["ops"] if op["op"] == 20)
    assert "Ø.206 in (5.2324 mm) THRU" in holes
    assert "(-169.5,27.557592509)" in holes
    assert "pointed #10-24 transfer screw" in holes
    assert "retained CL dowel" in holes
    assert "lift the work off before drilling" in holes
    assert "Remove the transfer screw" in holes
