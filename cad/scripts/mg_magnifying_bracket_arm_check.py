"""Tolerance-bounded static arm-section screen at the A1 force stations (#1559).

Pure data, import-time asserts. The bracket reaches from the current mounting
seat to the drum's wire lane (z -173.51). This module bounds the plain
threaded neck, cantilever and relocated two-screw mounting row:

* the load at the neck: the lever group's weight plus wire 1's tension at
  the output-fixture hook, which pulls toward the drum end in the x-y plane;
* the arm's torsion (moment about Z at the neck: the arm runs along Z) and
  bending, and the resulting hook deflection along wire 1, pen-equivalent
  through the wheel's rim/drum ratio;
* the two #2-56 screws seating the flange on MHA-SM-03's front face:
  the prying tension increment against preload, and the shank shear.

Section stiffness uses minimum accepted neck dimensions; span uses the longest
printed seat distance, shortest grip and independent head-axis location stack.
Load directions and X/Y force stations remain the nominal installed A1 pose,
not an all-geometric-variation or native articulation certificate.

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
import sh_vn_music_wire_lever_geom
from _printed_tolerance import printed_deviations
from mg_magnifying_bracket_spec import DRAWING_PRECISION
from mg_lever_thread_joint import (
    NECK_THICKNESS,
    NECK_THICKNESS_TOL,
    NOSE_R,
    NOSE_R_TOL,
    HOLE_LOCATION_TOL,
    ROD_DIA as LEVER_ROD_DIA,
    ROD_LENGTH_TOL,
)
from magnifying_bracket_joint_layout import (
    BRACKET_ORIGIN,
    BRACKET_HOLE_POINTS,
    SCREW_MACHINE_X,
    SCREW_POSITIONS,
    SCREW_MAJOR_DIA,
    SEAT_PLANE_Z,
    SIDE_PLATE_Y,
    SIDE_PLATE_Z,
    GRIP_MIN,
    POSITION_BAND,
    SIDE_PLATE_HEIGHT,
    SIDE_PLATE_HEIGHT_DEVIATIONS,
)
from mg_magnifying_clamp_geom import BLOCK_HEIGHT as CLAMP_HEIGHT
from mg_magnifying_clamp_geom import HEX_AF as CLAMP_HEX_AF
from mg_magnifying_lever_geom import (
    ROD_LENGTH as LEVER_ROD_LENGTH,
    THREAD_PROJECTION,
    THREAD_PROJECTION_TOL,
)
from mg_magnifying_vertical_rod_geom import ROD_DIA as VROD_DIA
from mg_magnifying_vertical_rod_geom import ROD_LENGTH as VROD_LENGTH
from mg_magnifying_wheel_geom import WIRE_RATIO
from mg_output_fixture_geom import HEX_AF as FIXTURE_HEX_AF
from mg_output_fixture_geom import OVERALL_LENGTH as FIXTURE_LENGTH

G = 9.81e-3  # N per gram
BRASS_G_PER_MM3 = (
    pn_pen_carriage_geom.BRASS_G_PER_MM3
)  # 8.5e-3, the denser bound for every part
# Representative low-carbon-steel elastic moduli, not certified material minima.
# The generic material designation supplies no grade/temper yield guarantee.
E_STEEL = 200_000.0  # N/mm^2, assumed for the compliance estimate
G_STEEL = 79_000.0  # N/mm^2, assumed for the compliance estimate

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
)  # conservative full-cylinder mass; excludes the dome/chamfer removal
_CLAMP_G = _HEX_AREA * CLAMP_HEX_AF**2 * CLAMP_HEIGHT * BRASS_G_PER_MM3
_VROD_G = math.pi / 4.0 * VROD_DIA**2 * VROD_LENGTH * BRASS_G_PER_MM3  # 22.1 g
_FIXTURE_G = _HEX_AREA * FIXTURE_HEX_AF**2 * FIXTURE_LENGTH * BRASS_G_PER_MM3  # 16.4 g
_THUMB_SCREWS_G = 2.0 * 3.0  # two 91882A221 knurled #4-40, generous
LEVER_GROUP_G = _LEVER_G + _CLAMP_G + _VROD_G + _FIXTURE_G + _THUMB_SCREWS_G
LEVER_GROUP_N = LEVER_GROUP_G * G
# Every gram is conservatively placed at the farthest accepted free tip.
# The fitted projection fixes the threaded end relative to the neck; the
# longest rod, thinnest neck and smallest projection maximize this gravity arm.
LEVER_GROUP_ARM_X = (
    LEVER_ROD_LENGTH + ROD_LENGTH_TOL
    - (NECK_THICKNESS - NECK_THICKNESS_TOL) / 2.0
    - (THREAD_PROJECTION - THREAD_PROJECTION_TOL)
)

NECK = BRACKET_ORIGIN
HOOK = (sh_vn_music_wire_lever_geom.HOOK_X, sh_vn_music_wire_lever_geom.HOOK_Y, sh_vn_music_wire_lever_geom.HOOK_Z)
_wx, _wy, _wz = (
    e - s
    for e, s in zip(
        sh_vn_music_wire_lever_geom.WIRE_END, sh_vn_music_wire_lever_geom.WIRE_START, strict=True
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
ARM_B = NECK_THICKNESS - NECK_THICKNESS_TOL
ARM_H = 2.0 * (NOSE_R - NOSE_R_TOL)
I_VERTICAL = ARM_B * ARM_H**3 / 12.0
I_LATERAL = ARM_H * ARM_B**3 / 12.0
_ratio = ARM_H / ARM_B
J_TORSION = (
    ARM_B * ARM_H**3 * (1.0 / 3.0 - 0.21 * _ratio * (1.0 - _ratio**4 / 12.0))
)  # rectangular-section approximation (Roark)
# The printed seat-to-profile-axis distance and two independent nose/axis
# controls bound the longest thread-axis-to-seat reach without moving the model.
AXIS_TO_SEAT_MAX = (
    SIDE_PLATE_Z[1]
    + printed_deviations(SIDE_PLATE_Z[1], DRAWING_PRECISION["NeckProfile"]["SeatToAxis"])[1]
    + NOSE_R_TOL + HOLE_LOCATION_TOL
)
ARM_SPAN = AXIS_TO_SEAT_MAX - GRIP_MIN


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
# Conservative simultaneous bending/torsion von Mises bound, with factor three.
# This is a required material property, NOT a guaranteed generic-steel yield.
STEEL_YIELD_REQUIRED = 3.0 * math.hypot(BENDING_STRESS, math.sqrt(3.0) * TORSION_STRESS)

# --- flange joint: two #2-56 at machine x 1 and 14.7 on the seat plane ----------
SCREW_PITCH_X = SCREW_MACHINE_X[1] - SCREW_MACHINE_X[0]  # 13.7
# The screw origins are on the flange's front face. Project their actual
# row centroid to the seat plane, where the joint carries shear and prying.
JOINT = (
    sum(point[0] for point in SCREW_POSITIONS) / len(SCREW_POSITIONS),
    sum(point[1] for point in SCREW_POSITIONS) / len(SCREW_POSITIONS),
    SEAT_PLANE_Z,
)
# Moments of the neck load about the screw row's centre.
_RX = NECK[0] - JOINT[0]
_RY = NECK[1] - JOINT[1]
JOINT_MX = AXIS_TO_SEAT_MAX * _FY  # longest accepted axial prying reach
JOINT_MY = -AXIS_TO_SEAT_MAX * _FX
JOINT_MZ = _MZ + _RX * _FY - _RY * _FX  # in-plane torque about the seat normal
# Conservative preload: 0.10 N m hand torque on a #2-56, K = 0.25 (dry, small
# screw, generous) -> F = T / (K d).
SCREW_PRELOAD_N = 100.0 / (0.25 * SCREW_MAJOR_DIA)  # 183 N
# In-plane direct shear plus the torque couple at the worse screw.
# Wire tension stays positive even with guide friction subtracted: torque
# does not reverse, so the flange settles once against the screw shanks.
# They then carry it in bearing and shear, rather than relying on friction.
JOINT_SHEAR_DEMAND_N = math.hypot(_FX, _FY) / 2.0 + abs(JOINT_MZ) / SCREW_PITCH_X
_MIN_FX, _MIN_FY, _MIN_MZ = joint_load(
    WIRE_RATIO * PEN_SIDE_G * G * (1.0 - GUIDE_FRICTION_FRACTION), LEVER_GROUP_N
)
JOINT_MZ_MIN_TENSION = _MIN_MZ + _RX * _MIN_FY - _RY * _MIN_FX
_WIRE_FX, _WIRE_FY, _WIRE_MZ = joint_load(WIRE1_TENSION_MAX_N, 0.0)
JOINT_MZ_NO_GROUP = _WIRE_MZ + _RX * _WIRE_FY - _RY * _WIRE_FX
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
# Charge the independent mounting location and the foot's own printed width,
# rather than the receiver's unrelated .XX depth/thickness band.
JOINT_PRYING_ARM_Y = min(
    min(
        point[1] - SIDE_PLATE_Y[0] - POSITION_BAND,
        SIDE_PLATE_HEIGHT + SIDE_PLATE_HEIGHT_DEVIATIONS[0]
        - (point[1] - SIDE_PLATE_Y[0]) - POSITION_BAND,
    )
    for point in BRACKET_HOLE_POINTS
)
JOINT_TENSION_INCREMENT_N = (
    abs(JOINT_MX) / (2.0 * JOINT_PRYING_ARM_Y) + abs(JOINT_MY) / SCREW_PITCH_X
)
JOINT_PRELOAD_MARGIN = SCREW_PRELOAD_N / JOINT_TENSION_INCREMENT_N

if not (JOINT_MZ < 0.0 and JOINT_MZ_MIN_TENSION < 0.0 and JOINT_MZ_NO_GROUP < 0.0):
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


def material_demand_report() -> dict[str, float | str | None]:
    """Report the load demand, not an unprovided generic-steel strength."""
    return {
        "specified_material": "generic low-carbon steel, blued",
        "bending_stress_MPa": BENDING_STRESS,
        "torsion_stress_MPa": TORSION_STRESS,
        "required_yield_for_factor_three_MPa": STEEL_YIELD_REQUIRED,
        "assumed_elastic_modulus_MPa": E_STEEL,
        "assumed_shear_modulus_MPa": G_STEEL,
        "verified_yield_MPa": None,
        "verified_yield_safety_factor": None,
        "status": "UNVERIFIED: no material strength data; procurement remains generic low-carbon steel",
    }

