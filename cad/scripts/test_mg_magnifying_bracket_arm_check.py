"""Offline physical load/compliance checks for the current threaded L bracket."""

from __future__ import annotations

import math

import pytest

import error_budget
import magnifying_bracket_joint_layout as joint
import mg_lever_thread_joint as thread
import mg_magnifying_bracket_arm_check as arm
import mg_magnifying_lever_geom as lever
import mg_vn_lever_wire_geom as wire
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
    assert arm.ARM_SPAN == joint.SIDE_PLATE_Z[0]
    assert arm.ARM_B == thread.NECK_THICKNESS
    assert arm.ARM_H == 2.0 * thread.NOSE_R
    assert arm.NECK[2] == wire.HOOK_Z == wire.DRUM_END_Z
    assert arm.HOOK == (wire.HOOK_X, wire.HOOK_Y, wire.HOOK_Z)


def test_loads_follow_actual_force_direction_and_scale_linearly() -> None:
    assert arm.WIRE1_TENSION_MAX_N == pytest.approx(WIRE_RATIO * arm.PEN_LOAD_MAX_N)
    fx, fy, mz = arm.joint_load(1.0, 0.0)
    assert (fx, fy) == pytest.approx(arm.WIRE_DIR[:2])
    assert mz == pytest.approx(arm.HOOK_DX * fy - arm.HOOK_DY * fx)
    assert arm.joint_load(2.0, 3.0) == pytest.approx(tuple(2.0 * a + 3.0 * b for a, b in zip(arm.joint_load(1.0, 0.0), arm.joint_load(0.0, 1.0))))


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


def test_flange_joint_retains_steel_strength_and_screw_margins() -> None:
    assert arm.JOINT_PRELOAD_MARGIN > 1.0
    assert arm.SCREW_SHEAR_STRESS < arm.SCREW_SHEAR_ALLOWABLE
    assert max(arm.BENDING_STRESS, arm.TORSION_STRESS * math.sqrt(3.0)) < arm.STEEL_YIELD / 3.0
    assert arm.JOINT_TENSION_INCREMENT_N < arm.SCREW_PRELOAD_N
    assert joint.ENGAGEMENT_MIN >= 1.5 * joint.SCREW_MAJOR_DIA
