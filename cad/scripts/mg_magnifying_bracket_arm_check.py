"""Worst-case static check of the MHA-MG-01 arm under the A1 pose (#1559).

Pure data, import-time asserts. The bracket reaches from the current mounting
seat to the drum's wire lane (z -173.51). This module bounds the plain
threaded neck, cantilever and unchanged two-screw mounting joint:

* the load at the neck: the lever group's weight plus wire 1's tension at
  the output-fixture hook, which pulls toward the drum end in the x-y plane;
* the arm's torsion (moment about Z at the neck: the arm runs along Z) and
  bending, and the resulting hook deflection along wire 1, pen-equivalent
  through the wheel's rim/drum ratio;
* the two #2-56 screws seating the flange on MHA-SM-03's front face:
  the prying tension increment against preload, and the shank shear.

Wire-1 tension source: the pen side hangs on wire 2 from the magnifying
wheel's rim (build_pn_pen_assembly: the pen rod slides in the hanger's U
guides, the carriage hangs on it). The carriage mass is
pn_pen_carriage_geom.plan_cg_local(); the pen rod is pn_pen_rod_spec's 5 mm
square stock. The wheel balances that weight at RIM_WIRE_R against wire 1 at
DRUM_WIRE_R, so wire 1 carries WIRE_RATIO (4.995) times the pen-side load.

Stiffness criterion: the arm's share of the output chain's SERIES
compliance. error_budget.yaml has no structural allowance, and the static
offset is zeroed with every other preload (its knife note: "zero-setting
slides the gooseneck to include measured preloads and weight"). What the arm
adds is compliance in series with the summing springs' own: wire 1 already
sees the springs' rotational stiffness through the wire moment arm. The arm's
share must stay under 1 % of that. The springs' compliance comes from
error_budget (numpy, config-heavy), so test_mg_magnifying_bracket_arm_check
computes and asserts the ratio; this module stays pure and exports
ARM_COMPLIANCE_MM_PER_N.
"""

from __future__ import annotations

import math

import pn_pen_carriage_geom
import pn_pen_rod_spec
import mg_vn_lever_wire_geom
from mg_lever_thread_joint import NECK_THICKNESS, NOSE_R, ROD_DIA as LEVER_ROD_DIA
from magnifying_bracket_joint_layout import (
    BRACKET_ORIGIN,
    SCREW_MACHINE_X,
    SCREW_MAJOR_DIA,
    SEAT_PLANE_Z,
    SIDE_PLATE_HEIGHT,
    SIDE_PLATE_Z,
)
from mg_magnifying_clamp_geom import BLOCK_HEIGHT as CLAMP_HEIGHT
from mg_magnifying_clamp_geom import HEX_AF as CLAMP_HEX_AF
from mg_magnifying_lever_geom import ROD_LENGTH as LEVER_ROD_LENGTH
from mg_magnifying_vertical_rod_geom import ROD_DIA as VROD_DIA
from mg_magnifying_vertical_rod_geom import ROD_LENGTH as VROD_LENGTH
from mg_magnifying_wheel_geom import WIRE_RATIO
from mg_output_fixture_geom import HEX_AF as FIXTURE_HEX_AF
from mg_output_fixture_geom import OVERALL_LENGTH as FIXTURE_LENGTH

G = 9.81e-3  # N per gram
BRASS_G_PER_MM3 = (
    pn_pen_carriage_geom.BRASS_G_PER_MM3
)  # 8.5e-3, the denser bound for every part
E_STEEL = 200_000.0  # N/mm^2, 1018 cold-drawn (low end of 200-205 GPa)
G_STEEL = 79_000.0  # N/mm^2 (low end of ~80 GPa)

# --- loads ---------------------------------------------------------------------
_HEX_AREA = math.sqrt(3.0) / 2.0  # hex area per AF^2
_CARRIAGE_G = pn_pen_carriage_geom.plan_cg_local()[0]  # 114.2 g
_PEN_ROD_G = (
    pn_pen_rod_spec.ROD_SECTION**2 * pn_pen_rod_spec.TOTAL_LENGTH * BRASS_G_PER_MM3
)  # 26.1 g
_PEN_HARDWARE_G = 5.0  # #0-80 adjust stud + jam nut, generous
PEN_SIDE_G = _CARRIAGE_G + _PEN_ROD_G + _PEN_HARDWARE_G  # 145.3 g
# U-guide friction reverses with the stroke: bounded at 50 % of the hanging
# weight (a generous allowance for a brass block on a sliding square rod).
GUIDE_FRICTION_FRACTION = 0.5
PEN_LOAD_MAX_N = PEN_SIDE_G * G * (1.0 + GUIDE_FRICTION_FRACTION)  # 2.14 N
PEN_LOAD_SWING_N = 2.0 * GUIDE_FRICTION_FRACTION * PEN_SIDE_G * G  # 1.43 N peak-to-peak
WIRE1_TENSION_MAX_N = WIRE_RATIO * PEN_LOAD_MAX_N  # 10.7 N
WIRE1_TENSION_SWING_N = WIRE_RATIO * PEN_LOAD_SWING_N  # 7.1 N

_LEVER_G = (
    math.pi / 4.0 * LEVER_ROD_DIA**2 * LEVER_ROD_LENGTH * BRASS_G_PER_MM3
)  # 39.7 g
_CLAMP_G = _HEX_AREA * CLAMP_HEX_AF**2 * CLAMP_HEIGHT * BRASS_G_PER_MM3  # 26.0 g
_VROD_G = math.pi / 4.0 * VROD_DIA**2 * VROD_LENGTH * BRASS_G_PER_MM3  # 22.1 g
_FIXTURE_G = _HEX_AREA * FIXTURE_HEX_AF**2 * FIXTURE_LENGTH * BRASS_G_PER_MM3  # 16.4 g
_THUMB_SCREWS_G = 2.0 * 3.0  # two 91882A221 knurled #4-40, generous
LEVER_GROUP_G = _LEVER_G + _CLAMP_G + _VROD_G + _FIXTURE_G + _THUMB_SCREWS_G  # 110.2 g
LEVER_GROUP_N = LEVER_GROUP_G * G  # 1.08 N
# Every gram placed at the farthest station, the lever's free tip (machine x
# 200, the lever spanning x 32.5..200 with the threaded neck at x 40): 160 mm.
LEVER_GROUP_ARM_X = 160.0

NECK = BRACKET_ORIGIN
HOOK = (mg_vn_lever_wire_geom.HOOK_X, mg_vn_lever_wire_geom.HOOK_Y, mg_vn_lever_wire_geom.HOOK_Z)
_wx, _wy, _wz = (
    e - s
    for e, s in zip(
        mg_vn_lever_wire_geom.WIRE_END, mg_vn_lever_wire_geom.WIRE_START, strict=True
    )
)
_wl = math.sqrt(_wx * _wx + _wy * _wy + _wz * _wz)
WIRE_DIR = (_wx / _wl, _wy / _wl, _wz / _wl)  # (-0.272, -0.962, 0) toward the drum
if abs(HOOK[2] - NECK[2]) > 1e-9 or abs(WIRE_DIR[2]) > 1e-9:
    raise AssertionError(
        "arm check assumes the A1 plumb plane: hook, wire and neck at one z"
    )
HOOK_DX = HOOK[0] - NECK[0]
HOOK_DY = HOOK[1] - NECK[1]


def joint_load(tension: float, weight: float) -> tuple[float, float, float]:
    """(Fx, Fy, Mz) at the neck axis: wire at the hook plus group weight."""
    fx = tension * WIRE_DIR[0]
    fy = tension * WIRE_DIR[1] - weight
    mz = (
        HOOK_DX * tension * WIRE_DIR[1]
        - HOOK_DY * tension * WIRE_DIR[0]
        - LEVER_GROUP_ARM_X * weight
    )
    return fx, fy, mz


# --- arm section -----------------------------------------------------------------
ARM_B = NECK_THICKNESS
ARM_H = 2.0 * NOSE_R
I_VERTICAL = ARM_B * ARM_H**3 / 12.0
I_LATERAL = ARM_H * ARM_B**3 / 12.0
_ratio = ARM_H / ARM_B
J_TORSION = (
    ARM_B * ARM_H**3 * (1.0 / 3.0 - 0.21 * _ratio * (1.0 - _ratio**4 / 12.0))
)  # rectangular-section approximation (Roark)
# The full axis-to-front-face span is conservative; no stiff collar shell is
# subtracted from the cantilever now that the plain neck carries the thread.
ARM_SPAN = SIDE_PLATE_Z[0]


def hook_deflection_along_wire(span: float, tension: float, weight: float) -> float:
    """Hook motion along wire 1 (mm; signed, negative toward the drum).

    Twist phi = Mz L / (G J) turns the hook about the arm's axis (Z) through
    the neck; the cantilever tip moves by F L^3 / (3 E I) in Y and in X and
    carries the lever rigidly. Bending slope rotates the group about X and Y,
    moving the hook only by its z offset from the neck: zero in the A1 plane.
    """
    fx, fy, mz = joint_load(tension, weight)
    phi = mz * span / (G_STEEL * J_TORSION)
    # Rotation phi about +Z: hook offset (dx, dy) moves by phi * (-dy, dx).
    dx = phi * -HOOK_DY + fx * span**3 / (3.0 * E_STEEL * I_LATERAL)
    dy = phi * HOOK_DX + fy * span**3 / (3.0 * E_STEEL * I_VERTICAL)
    return -(dx * WIRE_DIR[0] + dy * WIRE_DIR[1])


ARM_COMPLIANCE_MM_PER_N = abs(
    hook_deflection_along_wire(ARM_SPAN, 1.0, 0.0)
)
# The test compares this series compliance with the summing springs.
ARM_SHARE_OF_SPRING_COMPLIANCE_MAX = 0.01

# Peak arm stresses at the flange (the fixed end).
_FX, _FY, _MZ = joint_load(WIRE1_TENSION_MAX_N, LEVER_GROUP_N)
BENDING_STRESS = (
    abs(_FY) * ARM_SPAN * (ARM_H / 2.0) / I_VERTICAL
    + abs(_FX) * ARM_SPAN * (ARM_B / 2.0) / I_LATERAL
)
# Shigley's rectangular-bar maximum shear with the current section.
TORSION_STRESS = (
    abs(_MZ) * (3.0 * ARM_B + 1.8 * ARM_H) / (ARM_B**2 * ARM_H**2)
)
STEEL_YIELD = 370.0  # N/mm^2, 1018 cold drawn

# --- flange joint: two #2-56 at machine x 1 and 14.7 on the seat plane ----------
SCREW_PITCH_X = SCREW_MACHINE_X[1] - SCREW_MACHINE_X[0]  # 13.7
JOINT = (
    (SCREW_MACHINE_X[0] + SCREW_MACHINE_X[1]) / 2.0,
    BRACKET_ORIGIN[1],
    SEAT_PLANE_Z,
)
# Moments of the neck load about the screw row's centre.
_RX, _RY, _RZ = (
    c - j for c, j in zip(NECK, JOINT, strict=True)
)
JOINT_MX = -_RZ * _FY  # prying about X (the row lies along X): both screws load
JOINT_MY = _RZ * _FX  # prying about Y: the screws load differentially
JOINT_MZ = _MZ + _RX * _FY - _RY * _FX  # in-plane torque about the seat normal
# Conservative preload: 0.10 N m hand torque on a #2-56, K = 0.25 (dry, small
# screw, generous) -> F = T / (K d).
SCREW_PRELOAD_N = 100.0 / (0.25 * SCREW_MAJOR_DIA)  # 183 N
# In-plane direct shear plus the torque couple at the worse screw.
# Wire tension stays positive even with guide friction subtracted: torque
# does not reverse, so the flange settles once against the screw shanks.
# They then carry it in bearing and shear, rather than relying on friction.
JOINT_SHEAR_DEMAND_N = math.hypot(_FX, _FY) / 2.0 + abs(JOINT_MZ) / SCREW_PITCH_X
_MZ_MIN_TENSION = joint_load(
    WIRE_RATIO * PEN_SIDE_G * G * (1.0 - GUIDE_FRICTION_FRACTION), LEVER_GROUP_N
)[2]
_MZ_NO_GROUP = joint_load(WIRE1_TENSION_MAX_N, 0.0)[2]
# Shear plane at the seat face, conservatively in the thread: #2-56 basic
# minor D - 1.299 P = 1.595 mm, 2.00 mm^2.
SCREW_MINOR_DIA = SCREW_MAJOR_DIA - 1.299 * (25.4 / 56.0)
SCREW_SHEAR_STRESS = JOINT_SHEAR_DEMAND_N / (
    math.pi / 4.0 * SCREW_MINOR_DIA**2
)
# 18-8 stainless (config/parts/mg-vn-magnifying-bracket-screw.yaml, AISI 304):
# McMaster's 70 ksi (483 MPa) minimum tensile, shear ultimate 0.6 x = 290 MPa,
# allowable a third of that.
SCREW_SHEAR_ALLOWABLE = 0.6 * 483.0 / 3.0  # 96.6 N/mm^2
# Prying: the flange tips about its lower (or upper) edge, SIDE_PLATE_HEIGHT/2
# from the row; about Y, about its far end, the row's pitch the lever arm.
JOINT_TENSION_INCREMENT_N = (
    abs(JOINT_MX) / (2.0 * SIDE_PLATE_HEIGHT / 2.0) + abs(JOINT_MY) / SCREW_PITCH_X
)
JOINT_PRELOAD_MARGIN = SCREW_PRELOAD_N / JOINT_TENSION_INCREMENT_N

if max(BENDING_STRESS, TORSION_STRESS * math.sqrt(3.0)) > STEEL_YIELD / 3.0:
    raise AssertionError("magnifying bracket arm stress exceeds a third of 1018 yield")
if not (_MZ < 0.0 and _MZ_MIN_TENSION < 0.0 and _MZ_NO_GROUP < 0.0):
    raise AssertionError(
        "magnifying bracket joint torque reverses; the shanks would not stay bearing"
    )
if SCREW_SHEAR_STRESS > SCREW_SHEAR_ALLOWABLE:
    raise AssertionError(
        "magnifying bracket #2-56 shank shear exceeds a third of 18-8 ultimate"
    )
# The worst load already carries the +50 % guide friction: no separation.
if JOINT_PRELOAD_MARGIN <= 1.0:
    raise AssertionError("magnifying bracket #2-56 joint separates under prying")

