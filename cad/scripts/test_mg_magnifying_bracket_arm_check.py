"""Offline physical load/compliance checks for the current threaded L bracket."""

from __future__ import annotations

import itertools
import math

import pytest

import error_budget
import magnifying_bracket_joint_layout as joint
import mg_lever_thread_joint as thread
import mg_magnifying_bracket_arm_check as arm
import mg_magnifying_lever_geom as lever
import mg_magnifying_bracket_spec as bracket_spec
import sh_vn_music_wire_lever_geom as wire
import spring_force_model

from mg_magnifying_wheel_geom import WIRE_RATIO


def _spring_compliance_along_wire() -> float:
    nom = error_budget.nominal()
    channel = spring_force_model.channel_response(nom.sum_hole_x, nom.spring_rate, nom.spring_initial_tension)
    stiffness = error_budget.N_ELEMENTS * channel.stiffness_n_mm_per_rad + spring_force_model.counter_stiffness(nom.counter_rate, nom.counter_initial_tension)
    moment_arm = error_budget.wire_moment_arm(nom, lever.KNIFE_LOCAL_X - lever.CLAMP_LOCAL_X)
    return moment_arm**2 / stiffness


def test_neck_load_uses_current_mounting_seat_and_wire_plane() -> None:
    assert arm.NECK == joint.BRACKET_ORIGIN
    assert arm.ARM_SPAN == pytest.approx(97.965)
    assert arm.ARM_SPAN > joint.SIDE_PLATE_Z[0]
    assert arm.ARM_B == thread.NECK_THICKNESS - thread.NECK_THICKNESS_TOL == 11.7
    assert arm.ARM_H == 2.0 * (thread.NOSE_R - thread.NOSE_R_TOL) == 10.9
    assert arm.NECK[2] == wire.HOOK_Z == wire.DRUM_END_Z
    assert arm.HOOK == (wire.HOOK_X, wire.HOOK_Y, wire.HOOK_Z)


def test_arm_section_and_span_bound_every_accepted_size_corner() -> None:
    for width, radius, seat, grip, nose_location in itertools.product(
        (11.7, 13.3), (5.45, 5.55), (99.89, 100.91),
        (3.045, 3.305), (-0.10, 0.10),
    ):
        height = 2.0 * radius
        assert arm.I_VERTICAL <= width * height**3 / 12.0 + 1e-9
        assert arm.I_LATERAL <= height * width**3 / 12.0 + 1e-9
        assert arm.ARM_SPAN >= seat - grip + nose_location - 1e-9
    assert bracket_spec.DRAWING_PRECISION["Neck"]["NeckThickness"] == 1
    assert arm.AXIS_TO_SEAT_MAX == pytest.approx(101.01)


def test_loads_follow_actual_force_direction_and_scale_linearly() -> None:
    assert arm.WIRE1_TENSION_MAX_N == pytest.approx(WIRE_RATIO * arm.PEN_LOAD_MAX_N)
    fx, fy, mz = arm.joint_load(1.0, 0.0)
    assert (fx, fy) == pytest.approx(arm.WIRE_DIR[:2])
    assert mz == pytest.approx(arm.HOOK_DX * fy - arm.HOOK_DY * fx)
    assert arm.joint_load(2.0, 3.0) == pytest.approx(tuple(2.0 * a + 3.0 * b for a, b in zip(arm.joint_load(1.0, 0.0), arm.joint_load(0.0, 1.0))))


def test_gravity_moment_bounds_every_accepted_free_tip_in_the_fitted_frame() -> None:
    free_tip_offsets = [
        length - thickness / 2.0 - projection
        for length, thickness, projection in itertools.product(
            (thread.ROD_LENGTH - thread.ROD_LENGTH_TOL, thread.ROD_LENGTH + thread.ROD_LENGTH_TOL),
            (thread.NECK_THICKNESS - thread.NECK_THICKNESS_TOL, thread.NECK_THICKNESS + thread.NECK_THICKNESS_TOL),
            (lever.THREAD_PROJECTION - lever.THREAD_PROJECTION_TOL, lever.THREAD_PROJECTION + lever.THREAD_PROJECTION_TOL),
        )
    ]
    farthest_tip = max(free_tip_offsets)
    assert farthest_tip == pytest.approx(161.710)
    assert arm.LEVER_GROUP_ARM_X == pytest.approx(farthest_tip)
    # The former fixed-tip arm misses an accepted fitted rod by 1.710 mm.
    assert farthest_tip > thread.ROD_LENGTH - thread.NECK_THICKNESS / 2.0 - lever.THREAD_PROJECTION
    assert arm.joint_load(0.0, 1.0) == pytest.approx((0.0, -1.0, -farthest_tip))


def test_relocated_row_changes_joint_reference_not_neck_hook_or_body_pose() -> None:
    assert arm.NECK == (40.0, 979.7, -173.51)
    assert arm.HOOK == pytest.approx((150.0 - math.hypot(8.95, 4.5), 919.7, -173.51))
    assert joint.SIDE_PLATE_MACHINE_X == (-8.0, 46.25)
    assert joint.SIDE_PLATE_Y == (-5.5, 5.5)
    assert joint.SIDE_PLATE_FRONT_Z == pytest.approx(
        joint.SEAT_PLANE_Z - 3.175,
    )
    assert (lever.KNIFE_LOCAL_X, lever.KNIFE_LOCAL_Y) == (215.0, 5.134)
    assert arm.JOINT == pytest.approx((
        sum(point[0] for point in joint.SCREW_POSITIONS) / len(joint.SCREW_POSITIONS),
        979.7 - 0.71,
        joint.SEAT_PLANE_Z,
    ))
    assert arm.JOINT[1] == pytest.approx(
        sum(point[1] for point in joint.SCREW_POSITIONS) / len(joint.SCREW_POSITIONS),
    )
    fx, fy, mz = arm.joint_load(arm.WIRE1_TENSION_MAX_N, arm.LEVER_GROUP_N)
    centered_row_mz = mz + (arm.NECK[0] - arm.JOINT[0]) * fy
    assert arm.JOINT_MZ == pytest.approx(centered_row_mz - 0.71 * fx)
    assert arm.JOINT_MZ != pytest.approx(centered_row_mz)


@pytest.mark.parametrize("case", ["peak", "minimum_tension", "wire_only"])
def test_joint_moments_use_actual_force_stations_about_the_moved_row(case) -> None:
    tension, weight, actual_mz = {
        "peak": (arm.WIRE1_TENSION_MAX_N, arm.LEVER_GROUP_N, arm.JOINT_MZ),
        "minimum_tension": (
            WIRE_RATIO * arm.PEN_SIDE_G * arm.G * (1.0 - arm.GUIDE_FRICTION_FRACTION),
            arm.LEVER_GROUP_N,
            arm.JOINT_MZ_MIN_TENSION,
        ),
        "wire_only": (arm.WIRE1_TENSION_MAX_N, 0.0, arm.JOINT_MZ_NO_GROUP),
    }[case]
    wire_fx, wire_fy = (tension * component for component in arm.WIRE_DIR[:2])
    expected_mz = (
        (arm.HOOK[0] - arm.JOINT[0]) * wire_fy
        - (arm.HOOK[1] - arm.JOINT[1]) * wire_fx
        - (arm.NECK[0] + arm.LEVER_GROUP_ARM_X - arm.JOINT[0]) * weight
    )
    assert actual_mz == pytest.approx(expected_mz)
    assert actual_mz < 0.0
    if case == "peak":
        assert arm.AXIS_TO_SEAT_MAX > abs(arm.NECK[2] - arm.JOINT[2])
        assert arm.JOINT_MX == pytest.approx(arm.AXIS_TO_SEAT_MAX * (wire_fy - weight))
        assert arm.JOINT_MY == pytest.approx(-arm.AXIS_TO_SEAT_MAX * wire_fx)


def test_shifted_row_uses_nearer_flange_edge_for_prying_and_actual_torque_for_shear() -> None:
    lower, upper = (
        joint.BRACKET_ORIGIN[1] + edge for edge in joint.SIDE_PLATE_Y
    )
    nominal_edge = min(arm.JOINT[1] - lower, upper - arm.JOINT[1])
    assert nominal_edge == pytest.approx(4.79)
    row_from_lower = arm.JOINT[1] - lower
    nearest_edge = min(
        row_from_lower - joint.POSITION_BAND,
        joint.SIDE_PLATE_HEIGHT + joint.SIDE_PLATE_HEIGHT_DEVIATIONS[0]
        - row_from_lower - joint.POSITION_BAND,
    )
    assert nearest_edge == pytest.approx(4.7392)
    assert arm.JOINT_PRYING_ARM_Y == pytest.approx(nearest_edge)
    expected_tension = (
        abs(arm.JOINT_MX) / (2.0 * nearest_edge)
        + abs(arm.JOINT_MY) / arm.SCREW_PITCH_X
    )
    centered_tension = (
        abs(arm.JOINT_MX) / joint.SIDE_PLATE_HEIGHT
        + abs(arm.JOINT_MY) / arm.SCREW_PITCH_X
    )
    assert arm.JOINT_TENSION_INCREMENT_N == pytest.approx(expected_tension)
    assert expected_tension > centered_tension
    fx, fy, _mz = arm.joint_load(arm.WIRE1_TENSION_MAX_N, arm.LEVER_GROUP_N)
    expected_shear = math.hypot(fx, fy) / 2.0 + abs(arm.JOINT_MZ) / arm.SCREW_PITCH_X
    assert arm.JOINT_SHEAR_DEMAND_N == pytest.approx(expected_shear)
    assert arm.SCREW_SHEAR_STRESS == pytest.approx(
        expected_shear / (math.pi / 4.0 * arm.SCREW_MINOR_DIA**2),
    )
    assert arm.JOINT_PRELOAD_MARGIN == pytest.approx(
        arm.SCREW_PRELOAD_N / expected_tension,
    )


def test_prying_demand_bounds_every_accepted_foot_width_and_row_corner() -> None:
    # The lower-edge ordinate and overall .X width are independent controls.
    # Width variation is not a symmetric displacement of both nominal edges.
    corner_arms = [
        min(row_from_lower, width - row_from_lower)
        for width, row_from_lower in itertools.product(
            (10.2, 11.8), (4.7392, 4.8408),
        )
    ]
    assert (min(corner_arms), max(corner_arms)) == pytest.approx((4.7392, 4.8408))
    corner_tensions = [
        abs(arm.JOINT_MX) / (2.0 * edge_arm)
        + abs(arm.JOINT_MY) / 13.7
        for edge_arm in corner_arms
    ]
    assert arm.JOINT_PRYING_ARM_Y == pytest.approx(min(corner_arms))
    assert arm.JOINT_TENSION_INCREMENT_N == pytest.approx(max(corner_tensions))
    assert all(
        demand <= arm.JOINT_TENSION_INCREMENT_N + 1e-9
        for demand in corner_tensions
    )
    assert max(corner_tensions) < arm.SCREW_PRELOAD_N
    # A stale 12.70 mm foot arm would underpredict the new tension demand.
    old_foot_tension = abs(arm.JOINT_MX) / (2.0 * 5.59) + abs(arm.JOINT_MY) / 13.7
    assert arm.JOINT_TENSION_INCREMENT_N > old_foot_tension


def test_deflection_grows_with_span_and_respects_superposition() -> None:
    short = arm.hook_deflection_along_wire(arm.ARM_SPAN / 2.0, 1.0, 0.0)
    long = arm.hook_deflection_along_wire(arm.ARM_SPAN, 1.0, 0.0)
    assert 0.0 < abs(short) < abs(long)
    assert arm.ARM_COMPLIANCE_MM_PER_N == pytest.approx(abs(long))
    combined = arm.hook_deflection_along_wire(arm.ARM_SPAN, 2.0, 3.0)
    assert combined == pytest.approx(2.0 * long + 3.0 * arm.hook_deflection_along_wire(arm.ARM_SPAN, 0.0, 1.0))


def test_arm_adds_under_one_percent_to_the_actual_spring_compliance() -> None:
    spring = _spring_compliance_along_wire()
    assert spring > 0.0
    assert arm.ARM_COMPLIANCE_MM_PER_N / spring <= arm.ARM_SHARE_OF_SPRING_COMPLIANCE_MAX


def test_flange_joint_retains_screw_margins() -> None:
    assert arm.JOINT_PRELOAD_MARGIN > 1.0
    assert arm.SCREW_SHEAR_STRESS < arm.SCREW_SHEAR_ALLOWABLE
    assert arm.JOINT_TENSION_INCREMENT_N < arm.SCREW_PRELOAD_N
    assert joint.ENGAGEMENT_MIN >= 1.5 * joint.SCREW_MAJOR_DIA


def test_reported_material_demand_combines_bending_and_torsion_without_certifying_generic_steel() -> None:
    report = arm.material_demand_report()
    bending_alone = 3.0 * report["bending_stress_MPa"]
    torsion_alone = 3.0 * 3.0**0.5 * report["torsion_stress_MPa"]
    required = report["required_yield_for_factor_three_MPa"]
    # Simultaneous nonzero loads demand more than either isolated-load check,
    # while the sum is a conservative bound. This catches the former max-only
    # calculation without reproducing the implementation's von Mises formula.
    assert max(bending_alone, torsion_alone) < required < bending_alone + torsion_alone
    assert report["verified_yield_MPa"] is None
    assert report["verified_yield_safety_factor"] is None
