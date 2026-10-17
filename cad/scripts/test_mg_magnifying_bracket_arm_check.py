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
    # The arm starts buried in the collar's wall (r4: at Z 4.0 its +Y corner
    # stepped the collar root); only its end, 103.51 from the axis, prints.
    assert ARM_Z == (3.5, 103.51)
    assert arm.ARM_SPAN == pytest.approx(91.2226, abs=1e-3)
    assert arm.OLD_ARM_SPAN == pytest.approx(46.01)


def test_loads_from_their_sources():
    assert arm.PEN_SIDE_G == pytest.approx(145.25, abs=0.05)
    assert arm.WIRE1_TENSION_MAX_N == pytest.approx(WIRE_RATIO * arm.PEN_LOAD_MAX_N)
    assert arm.WIRE1_TENSION_MAX_N == pytest.approx(10.68, abs=0.01)
    assert arm.LEVER_GROUP_G == pytest.approx(110.2, abs=0.1)
    assert arm.HOOK == (
        vn_lever_wire_geom.HOOK_X,
        vn_lever_wire_geom.HOOK_Y,
        vn_lever_wire_geom.HOOK_Z,
    )


def test_arm_deflection_old_and_new():
    assert arm.HOOK_OFFSET_OLD == pytest.approx(0.123, abs=0.001)
    assert arm.HOOK_OFFSET_NEW == pytest.approx(0.276, abs=0.001)
    assert arm.PEN_OFFSET_NEW == pytest.approx(1.38, abs=0.01)
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
    assert arm.SCREW_SHEAR_STRESS == pytest.approx(66.5, abs=0.2)
    assert arm.SCREW_SHEAR_STRESS < arm.SCREW_SHEAR_ALLOWABLE
    assert arm.BENDING_STRESS == pytest.approx(13.1, abs=0.1)
    assert arm.TORSION_STRESS == pytest.approx(10.6, abs=0.1)


def _lame_pressure(interference: float, collar_od: float) -> float:
    # Restated plane-stress Lamé, brass rod in a 1018 collar (MPa, mm).
    k = (collar_od**2 + 36.0) / (collar_od**2 - 36.0)
    return interference / (6.0 * ((1.0 - 0.34) / 97000.0 + (k + 0.29) / 200000.0))


def test_press_alone_holds_the_lever_at_its_loosest_corner():
    # #1570: 0.007 minimum less DIN 7190:1988 smoothing 0.8 (Rz 3.2 + Rz 3.2).
    effective = 0.007 - 0.8 * (4.0 * 0.8 + 4.0 * 0.8) / 1000.0
    assert effective == pytest.approx(0.00188, abs=1e-12)
    pressure = _lame_pressure(effective, 12.0 - 0.51)
    length = 10.0 - 0.05 - 6.0 / 2.0  # shortest collar less the largest dome radius
    axial = 0.10 * pressure * 3.141592653589793 * 6.0 * length
    hold = arm.PRESS_HOLDING
    assert hold["contact_pressure_min_mpa"] == pytest.approx(pressure, rel=1e-12)
    assert hold["length_min"] == pytest.approx(6.95, abs=1e-12)
    assert hold["axial_hold_n"] == pytest.approx(axial, rel=1e-12)
    assert hold["axial_hold_n"] == pytest.approx(241.41, abs=0.01)
    assert hold["torque_hold_nmm"] == pytest.approx(724.24, abs=0.01)
    # Demands: the lever's axial load at the collar; wire 1 plus the group's
    # weight one lever diameter out of the A1 plane for twist.
    assert abs(arm._FX) == pytest.approx(2.91, abs=0.05)
    assert arm.COLLAR_TORQUE_DEMAND_NMM == pytest.approx(
        (arm.WIRE1_TENSION_MAX_N + arm.LEVER_GROUP_N) * 6.0, rel=1e-12
    )
    assert arm.COLLAR_TORQUE_DEMAND_NMM == pytest.approx(70.5, abs=1.0)
    assert hold["axial_margin"] > 75.0
    assert hold["torque_margin"] > 10.0
    assert (
        min(hold["axial_margin"], hold["torque_margin"]) >= arm.PRESS_HOLDING_MARGIN_MIN
    )


def test_collar_edge_bending_is_the_accepted_local_yield():
    edge = arm.COLLAR_EDGE_BENDING
    moment = abs(arm._MZ)
    assert moment == pytest.approx(1374.5, abs=5.0)
    assert edge["edge_bearing_mpa"] == pytest.approx(
        6.0 * moment / (6.0 * 6.95**2), rel=1e-12
    )
    # One edge unloads at the loosest corner past 890 N mm; the linear field's
    # positive part keeps the friction's normal force (the holds stand).
    loose = _lame_pressure(0.00188, 11.49)
    assert edge["opening_moment_loose_nmm"] == pytest.approx(
        loose * 6.0 * 6.95**2 / 6.0
    )
    assert edge["opening_moment_loose_nmm"] == pytest.approx(890.1, abs=0.1)
    # Tightest, thinnest wall: 330.8 MPa uniform (< 333) plus the edge bearing.
    tight = _lame_pressure(0.014, 11.49)
    k = (11.49**2 + 36.0) / (11.49**2 - 36.0)
    edge_p = tight + edge["edge_bearing_mpa"]
    assert edge["edge_von_mises_tight_mpa"] == pytest.approx(
        edge_p * (k**2 + 1.0 + k) ** 0.5, rel=1e-12
    )
    # Owner ruling (b), #1570: past the 370 MPa yield locally, pinned at 400.
    assert edge["edge_von_mises_tight_mpa"] == pytest.approx(399.4, abs=0.5)
    assert (
        370.0
        < edge["edge_von_mises_tight_mpa"]
        <= arm.COLLAR_EDGE_VON_MISES_MAX_MPA
        == 400.0
    )
