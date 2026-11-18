"""The sub-plate's spec mirrors agree with the strap plan and the shop record.

``ch_rocker_strap_tl_sub_plate_spec`` never reads a TOML (it is a COM-leaf
input); every plan or shop value it mirrors is held to its source here.
"""

from __future__ import annotations

import tomllib

import pytest

import ch_rocker_strap_tl_sub_plate_spec as spec
from _paths import CAD_ROOT

PLAN = tomllib.loads(
    (CAD_ROOT / "process" / "ch_rocker_strap" / "plan.toml").read_text(encoding="utf-8")
)["parameters"]
SHOP = tomllib.loads(
    (CAD_ROOT / "config" / "shop-equipment.toml").read_text(encoding="utf-8")
)


def test_hub_and_clamp_stations_are_the_plans() -> None:
    assert spec.HUB_X == PLAN["hub_x_mm"] == spec.PLAN_HUB_X
    # The plan states the hub's distance toward the operator from Y0.
    assert -spec.HUB_Y == PLAN["hub_y_mm"] == spec.PLAN_HUB_Y
    assert spec.CLAMP_STATIONS == tuple(PLAN[f"clamp_{i}_x_mm"] for i in range(1, 5))


def test_notch_mirrors_are_the_plans_fence_notch() -> None:
    assert spec.PLAN_FENCE_NOTCH_INNER == PLAN["fence_notch_inner_mm"]
    assert spec.PLAN_FENCE_NOTCH_OUTER == PLAN["fence_notch_outer_mm"]
    assert spec.PLAN_FENCE_NOTCH_DEPTH == PLAN["fence_notch_depth_mm"]
    assert spec.NOTCH_FLOOR_Z == PLAN["fence_notch_floor_z_mm"]


def test_envelope_is_the_plans_plate() -> None:
    assert spec.LEFT_END_X == PLAN["plate_start_x_mm"]
    assert spec.PLATE_LENGTH == PLAN["plate_length_mm"]
    assert spec.PLATE_WIDTH == PLAN["plate_width_mm"]
    # The strap plan stacks Z on the plate's top height (.416 under Z0) and
    # holds the fence and end-stop tops to this plate's .074 +.005 limit.
    assert -spec.UNDERSIDE_Z == pytest.approx(PLAN["plate_top_height_mm"])
    assert spec.FENCE_HEIGHT_MAX == pytest.approx(PLAN["fence_height_mm"])
    assert spec.FENCE_HEIGHT_MAX == pytest.approx(PLAN["end_stop_height_mm"])
    assert spec.FENCE_WIDTH == PLAN["fence_width_mm"]


def test_counterbore_is_the_plans_hub_relief() -> None:
    assert PLAN["hub_relief_dia_mm"] <= spec.HUB_CBORE_DIA
    assert spec.HUB_CBORE_DEPTH == pytest.approx(PLAN["hub_relief_depth_mm"], abs=0.01)
    assert spec.PLAN_DRILL_TIP_Z == PLAN["drill_tip_z_mm"]
    assert spec.PLAN_REAM_TIP_Z == PLAN["ream_tip_z_mm"]
    assert spec.PLAN_RELIEF_FLOOR_CLEARANCE == PLAN["relief_floor_clearance_mm"]


def test_shop_record_names_this_plate_and_its_clamps_pocket() -> None:
    fixtures = SHOP["fixtures"]
    plate = fixtures["strap-sub-plate"]
    assert plate["kind"] == "fixture_plate"
    # The record's name and sizes are corrected in the strap traveler's PR.
    clamp = fixtures["edge-clamps-low-profile"]
    assert clamp["slot_depth_mm"] == spec.POCKET_DEPTH == spec.CLAMP_B
    assert clamp["slot_width_mm"] == spec.CLAMP_C
    assert clamp["slot_width_mm"] == pytest.approx(
        spec.POCKET_NEAR_WALL_Y - spec.POCKET_BACK_WALL_Y
    )
    assert clamp["screw_from_work_edge_mm"] == spec.CLAMP_A
    assert clamp["screw_from_work_edge_mm"] == pytest.approx(
        spec.BLANK_EDGE_Y - spec.CLAMP_SCREW_Y
    )
    assert clamp["min_clamp_height_mm"] == PLAN["clamp_height_mm"]
