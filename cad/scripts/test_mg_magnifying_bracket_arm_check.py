"""Offline pins for mg_magnifying_bracket_arm_check (#1559, A1 pose)."""

from __future__ import annotations

import pytest

import error_budget
import magnifying_bracket_joint_layout as joint
import mg_magnifying_bracket_arm_check as arm
import mg_magnifying_lever_geom as lever
import spring_force_model
import vn_lever_wire_geom
from build_mg_magnifying_bracket import ARM_Z
from mg_magnifying_wheel_geom import WIRE_RATIO


def _spring_compliance_along_wire() -> float:
    """Hook compliance along wire 1 (mm/N) the summing springs already give:
    wire moment arm^2 over error_budget's rotational stiffness (the same sum
    pen_gain_per_arm_mm divides by), at the as-built clamp station."""
    nom = error_budget.nominal()
    channel = spring_force_model.channel_response(
        nom.sum_hole_x, nom.spring_rate, nom.spring_initial_tension
    )
    stiffness = error_budget.N_ELEMENTS * channel.stiffness_n_mm_per_rad + (
        spring_force_model.counter_stiffness(
            nom.counter_rate, nom.counter_initial_tension
        )
    )
    moment_arm = error_budget.wire_moment_arm(
        nom, lever.KNIFE_LOCAL_X - lever.CLAMP_LOCAL_X
    )
    return moment_arm**2 / stiffness


def test_a1_pose_and_arm_length():
    assert joint.BRACKET_ORIGIN[2] == vn_lever_wire_geom.DRUM_END_Z == -173.51
    assert arm.COLLAR == joint.BRACKET_ORIGIN
    assert ARM_Z == (4.0, 103.51)
    assert arm.ARM_SPAN == pytest.approx(91.2226, abs=1e-3)
    assert arm.OLD_ARM_SPAN == pytest.approx(46.01)


def test_loads_from_their_sources():
    assert arm.PEN_SIDE_G == pytest.approx(145.25, abs=0.05)
    assert arm.WIRE1_TENSION_MAX_N == pytest.approx(WIRE_RATIO * arm.PEN_LOAD_MAX_N)
    assert arm.WIRE1_TENSION_MAX_N == pytest.approx(10.68, abs=0.01)
    assert arm.LEVER_GROUP_G == pytest.approx(105.6, abs=0.1)
    assert arm.HOOK == (
        vn_lever_wire_geom.HOOK_X,
        vn_lever_wire_geom.HOOK_Y,
        vn_lever_wire_geom.HOOK_Z,
    )


def test_arm_deflection_old_and_new():
    assert arm.HOOK_OFFSET_OLD == pytest.approx(0.123, abs=0.001)
    assert arm.HOOK_OFFSET_NEW == pytest.approx(0.274, abs=0.001)
    assert arm.PEN_OFFSET_NEW == pytest.approx(1.37, abs=0.01)
    assert arm.ARM_COMPLIANCE_MM_PER_N == pytest.approx(0.0227, abs=1e-4)


def test_arm_adds_under_one_percent_to_the_spring_compliance():
    spring = _spring_compliance_along_wire()
    assert spring == pytest.approx(3.19, abs=0.02)
    share = arm.ARM_COMPLIANCE_MM_PER_N / spring
    assert share == pytest.approx(0.0071, abs=2e-4)
    assert share <= arm.ARM_SHARE_OF_SPRING_COMPLIANCE_MAX


def test_flange_joint_margins():
    assert arm.JOINT_PRELOAD_MARGIN == pytest.approx(1.65, abs=0.01)
    assert arm.JOINT_PRELOAD_MARGIN > 1.0
    assert arm.SCREW_SHEAR_STRESS == pytest.approx(66.1, abs=0.2)
    assert arm.SCREW_SHEAR_STRESS < arm.SCREW_SHEAR_ALLOWABLE
    assert arm.BENDING_STRESS == pytest.approx(13.1, abs=0.1)
    assert arm.TORSION_STRESS == pytest.approx(10.6, abs=0.1)
