"""Offline R3 holding geometry and acceptance contracts; no native execution."""
from __future__ import annotations

import math

import pytest

import ch_rocker_arm_tl_oblique_holding_spec as holding
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_riser_spec as riser
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_tl_oblique_hub_stud_spec as stud
import ch_rocker_arm_tl_oblique_hub_sleeve_spec as sleeve
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_blank_spec as blank
from _hole_spec import THREAD_MAJOR_MM


def test_hub_keeps_current_carrier_bore_and_locating_nose() -> None:
    assert carrier.HUB_HOLE_DIA == 10.16
    assert stud.DIA == 10.16
    assert stud.TIP_SET == 2.032
    assert stud.FLANGE_DIA == 18.0
    assert stud.FLANGE_THICK == 3.0
    assert 0 < carrier.HUB_SLIP_CLEARANCE_MIN <= carrier.HUB_SLIP_CLEARANCE_MAX
    assert carrier.HUB_SLIP_CLEARANCE_MAX == pytest.approx(0.0015 * 25.4)


def test_carrier_flange_seat_charges_the_studs_printed_limits() -> None:
    assert stud.FLANGE_PLACES == 2
    assert stud.FLANGE_DIA_PRINTED == pytest.approx(18.034)
    assert stud.FLANGE_THICK_PRINTED == pytest.approx(3.048)
    assert stud.FLANGE_DIA_LIMITS == pytest.approx((17.780, 18.288))
    assert stud.FLANGE_THICK_LIMITS == pytest.approx((2.794, 3.302))
    assert stud.FLANGE_DIA_LIMITS[0] <= stud.FLANGE_DIA <= stud.FLANGE_DIA_LIMITS[1]
    assert stud.FLANGE_THICK_LIMITS[0] <= stud.FLANGE_THICK <= stud.FLANGE_THICK_LIMITS[1]
    chamfer_ratio = math.tan(math.radians(45.0 - carrier.HUB_CHAMFER_ANGLE_BAND))
    seat = (
        stud.FLANGE_DIA_LIMITS[0] / 2.0
        - carrier.HUB_HOLE_LIMITS[1] / 2.0
        - carrier.HUB_CHAMFER_MAX / chamfer_ratio
    )
    assert carrier.HUB_FLANGE_SEAT_WIDTH_MIN == pytest.approx(seat)
    assert seat >= 2.032


def test_washer_complete_sweeps_include_float_and_thread_limits() -> None:
    assert holding.WASHER_GAPS == pytest.approx({"inner": 2.754, "outer": 2.246})
    assert holding.SCREW_MAJOR_MIN == pytest.approx(0.1828 * 25.4)
    assert holding.THREAD_RADIAL_PLAY == pytest.approx((0.1672 - 0.1604) * 25.4 / 2)
    assert holding.WASHER_FLOAT_MAX > 0.21  # not the basic-major optimistic .127
    assert min(holding.WASHER_GAPS_MIN.values()) >= holding.WASHER_CLEARANCE_MIN == 1.5
    assert min(holding.WASHER_GAPS_MIN.values()) < 2.0  # the owner's explicit clarification
    holding.require_clearance()


def test_clearance_guard_rejects_a_washer_below_the_actual_floor(monkeypatch) -> None:
    monkeypatch.setattr(holding, "WASHER_GAPS_MIN", {"inner": 2.0, "outer": 1.499})
    with pytest.raises(AssertionError, match="1.5 mm"):
        holding.require_clearance()


def test_round_sleeve_supports_strap_after_self_cut_without_touching_cutter() -> None:
    assert sleeve.WALL_MIN >= 2.032
    assert riser.HUB_DIA > sleeve.OD + 0.127
    assert sleeve.SHANK_CLEARANCE_MIN > 0
    assert min(holding.SLEEVE_GAPS_MIN.values()) > 0.15
    assert len(holding.SELF_CUT_REMOVED) == 6
    assert "ch-rocker-arm-tl-oblique-hub-sleeve" in holding.SELF_CUT_REMOVED
    assert "ch-rocker-arm-tl-oblique-hub-stud" in holding.SELF_CUT_REMOVED
    assert trammel.RISER_INNER_RADIUS - trammel.R_INNER == pytest.approx(2.38125)
    assert trammel.R_OUTER - trammel.RISER_OUTER_RADIUS == pytest.approx(2.38125)


def test_left_clamp_keeps_cl_dowel_and_material_in_all_three_layers() -> None:
    assert trammel.LEFT_CLAMP[0] == -169.5
    assert math.dist(trammel.LEFT_CLAMP, trammel.ARC_CENTRE) == pytest.approx(808.254)
    assert holding.LEFT_CLAMP_TO_CL == pytest.approx(8.7906813203)
    assert min(holding.LEFT_HEAD_GAPS.values()) > 11.27
    assert min(holding.LEFT_HOLE_TO_END_MIN, holding.LEFT_HOLE_TO_CL_MIN,
               holding.LEFT_BAND_WALL_MIN) >= 2.032
    radius = holding.left_screw.DIMS.head_dia / 2
    assert blank.disk_material_area(trammel.LEFT_CLAMP, radius) == pytest.approx(math.pi * radius**2)
    assert carrier.OUTLINE_X[0] < trammel.LEFT_CLAMP[0] < carrier.OUTLINE_X[1]
    assert carrier.OUTLINE_Y[0] < trammel.LEFT_CLAMP[1] < carrier.OUTLINE_Y[1]


def test_blind_receiver_retains_floor_and_full_thread_without_tip_bottoming() -> None:
    assert carrier.LEFT_CLAMP_SPEC.end == "blind"
    assert carrier.LEFT_CLAMP_SPEC.kind == "tapped_bottoming"
    assert carrier.LEFT_CLAMP_SPEC.drill_angle_deg == 180.0
    assert carrier.LEFT_CLAMP_FLOOR_MIN == pytest.approx(2.032)
    assert carrier.LEFT_CLAMP_FULL_THREAD_MIN >= 1.5 * THREAD_MAJOR_MM["#10-24"]
    insertion_lo, insertion_hi = fasteners.LEFT_CLAMP_INSERTION
    chamfer_lo, chamfer_hi = fasteners.LEFT_CLAMP_TIP_CHAMFER
    assert insertion_lo - chamfer_hi - 0.254 >= 1.5 * THREAD_MAJOR_MM["#10-24"]
    assert insertion_hi - chamfer_lo <= carrier.LEFT_CLAMP_THREAD_DEPTH
    assert carrier.LEFT_CLAMP_DRILL_DEPTH - 0.254 - insertion_hi >= 0.29
    assert fasteners.LEFT_CLAMP.cut_length_mm is not None
    assert fasteners.CR_CLAMP in fasteners.FASTENERS
    assert fasteners.HUB_CLAMP in fasteners.FASTENERS
    assert fasteners.LEFT_CLAMP in fasteners.FASTENERS


def test_flange_clears_obstacles_over_all_planar_poses() -> None:
    assert holding.FLANGE_BOTTOM_Z == pytest.approx(77.911)
    assert holding.FLANGE_BOTTOM_Z == pytest.approx(
        trammel.CARRIER_UNDERSIDE_Z - stud.FLANGE_THICK_LIMITS[1]
    )
    assert holding.FLANGE_VERTICAL_GAPS == pytest.approx({
        "pivot blocks": 13.589, "KP08 envelope": 9.573, "handwheel sweep": 0.573,
    })
    assert holding.FLANGE_HANDWHEEL_PLAN_GAP > 275
    assert min(holding.FLANGE_SUPPORT_GAPS.values()) > 210
    assert holding.FLANGE_HANDWHEEL_PLAN_GAP == pytest.approx(
        math.hypot(*holding._PLAN_SEPARATIONS) - stud.FLANGE_DIA_LIMITS[1] / 2.0
    )
    assert holding.FLANGE_SUPPORT_GAPS == pytest.approx({
        f"{name} {index}": (
            math.dist(trammel.HUB, pin)
            - stud.FLANGE_DIA_LIMITS[1] / 2.0 - holding.spacer.OD / 2.0
        )
        for name in trammel.PASS_RADIUS
        for index, pin in enumerate(trammel.pin_pair(name), 1)
    })
    for name, rc in trammel.PASS_RADIUS.items():
        for i in range(101):
            theta = trammel.SWEEP[name] * (2 * i / 100 - 1)
            centre = trammel.carrier_pose(name, theta).to_machine(trammel.HUB)
            assert centre == pytest.approx((
                -(rc + trammel.HUB_RADIUS) * math.sin(theta / 2),
                (trammel.HUB_RADIUS - rc) * math.cos(theta / 2),
            ))
    assert holding.CLAMP_TOP_Z["hub"] < holding.CLAMP_TOP_Z["CR"]
    assert holding.CLAMP_TOP_Z["left"] < holding.CLAMP_TOP_Z["CR"]
    assert holding.CLAMP_TOP_Z["CR"] == pytest.approx(107.1464)


def test_self_cut_uses_the_actual_removal_list_and_bigger_cutter() -> None:
    cutting = holding.tooling_clearance_report("strap")
    preparing = holding.tooling_clearance_report("riser_self_cut")
    assert set(cutting) - set(preparing) == set(holding.SELF_CUT_REMOVED)
    assert set(preparing) == {
        "ch-rocker-arm-tl-vn-oblique-cl-dowel",
        "ch-rocker-arm-tl-vn-oblique-riser-screw",
    }
    assert all(gap > 0 for passes in preparing.values() for gap in passes.values())
    for stem, passes in preparing.items():
        for name, gap in passes.items():
            assert cutting[stem][name] - gap == pytest.approx(2.38125)
    with pytest.raises(ValueError, match="unknown tooling setup"):
        holding.tooling_clearance_report("unknown")


def test_left_head_has_worst_case_clearance_not_just_a_stop_pose() -> None:
    for name, nominal in holding.LEFT_HEAD_GAPS.items():
        assert holding.LEFT_HEAD_GAPS_MIN[name] == pytest.approx(
            nominal - carrier.station_sweep_error(trammel.LEFT_CLAMP, name)
            - holding.LEFT_AXIS_FLOAT_MAX - trammel.RADIUS_FROM_SHOULDER_CLEARANCE
        )
    # The design acceptance remains the original 5 mm, not the former
    # 10.6 mm numerical observation calculated with the retired pin bands.
    assert min(holding.LEFT_HEAD_GAPS_MIN.values()) >= 5.0
    assert all(holding.LEFT_HEAD_GAPS_MIN[name] < gap for name, gap in holding.LEFT_HEAD_GAPS.items())


def test_holding_gaps_include_the_new_correlated_table_errors() -> None:
    for name in ("inner", "outer"):
        assert carrier.PIN_RELATIVE_ERROR[name] > 0.0
        assert holding.LEFT_STATION_ERROR[name] == pytest.approx(
            carrier.station_cut_error(trammel.LEFT_CLAMP, name)
        )
        assert holding.WASHER_GAPS[name] - holding.WASHER_GAPS_MIN[name] >= (
            carrier.HUB_RADIAL_STACK + carrier.PIN_RELATIVE_ERROR[name]
            + holding.STUD_FLOAT + holding.WASHER_FLOAT_MAX + holding.SCREW_AXIS_FLOAT_MAX
        )
        assert holding.SLEEVE_GAPS_MIN[name] == pytest.approx(
            holding.cutter_gap(trammel.HUB, holding.SLEEVE_RADIUS_MAX, name)
            - holding.SLEEVE_FLOAT - holding.STUD_FLOAT - carrier.HUB_RADIAL_STACK
            - carrier.PIN_RELATIVE_ERROR[name]
        )
