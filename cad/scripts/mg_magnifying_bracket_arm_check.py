"""Worst-case static check of the MHA-MG-01 arm under the A1 pose (#1559).

Pure data, import-time asserts. The magnifying group moved forward into the
drum's wire lane (z -173.51), so the bracket arm grew from ~52 to ~97 mm
between the flange and the collar. This module bounds what that costs:

* the load at the collar: the lever group's weight plus wire 1's tension at
  the output-fixture hook, which pulls toward the drum end in the x-y plane;
* the arm's torsion (moment about Z at the collar: the arm runs along Z) and
  bending, and the resulting hook deflection along wire 1, pen-equivalent
  through the wheel's rim/drum ratio, old 52 arm against the new one;
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
import sh_vn_music_wire_lever_geom
from build_mg_magnifying_bracket import ARM_HALF_X, ARM_Y, COLLAR_OD
from magnifying_bracket_joint_layout import (
    BRACKET_ORIGIN,
    SCREW_MACHINE_X,
    SCREW_MAJOR_DIA,
    SEAT_PLANE_Z,
    SIDE_PLATE_HEIGHT,
    SIDE_PLATE_Z,
)
from mg_lever_press_fit_geom import ROD_DIA as LEVER_ROD_DIA
from mg_lever_press_fit_geom import collar_edge_bending, press_holding
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
# 200, the lever spanning x 35..200 with the collar at x 40): 160 mm.
LEVER_GROUP_ARM_X = 160.0

COLLAR = BRACKET_ORIGIN
HOOK = (sh_vn_music_wire_lever_geom.HOOK_X, sh_vn_music_wire_lever_geom.HOOK_Y, sh_vn_music_wire_lever_geom.HOOK_Z)
_wx, _wy, _wz = (
    e - s
    for e, s in zip(
        sh_vn_music_wire_lever_geom.WIRE_END, sh_vn_music_wire_lever_geom.WIRE_START, strict=True
    )
)
_wl = math.sqrt(_wx * _wx + _wy * _wy + _wz * _wz)
WIRE_DIR = (_wx / _wl, _wy / _wl, _wz / _wl)  # (-0.272, -0.962, 0) toward the drum
if abs(HOOK[2] - COLLAR[2]) > 1e-9 or abs(WIRE_DIR[2]) > 1e-9:
    raise AssertionError(
        "arm check assumes the A1 plumb plane: hook, wire and collar at one z"
    )
HOOK_DX = HOOK[0] - COLLAR[0]  # 99.98
HOOK_DY = HOOK[1] - COLLAR[1]  # -60.0


def collar_load(tension: float, weight: float) -> tuple[float, float, float]:
    """(Fx, Fy, Mz) at the collar centre: wire 1 at the hook plus the group's weight."""
    fx = tension * WIRE_DIR[0]
    fy = tension * WIRE_DIR[1] - weight
    mz = (
        HOOK_DX * tension * WIRE_DIR[1]
        - HOOK_DY * tension * WIRE_DIR[0]
        - LEVER_GROUP_ARM_X * weight
    )
    return fx, fy, mz


# --- arm section -----------------------------------------------------------------
ARM_B = 2.0 * ARM_HALF_X  # 10, along X
ARM_H = ARM_Y[1] - ARM_Y[0]  # 7.5, along Y
I_VERTICAL = ARM_B * ARM_H**3 / 12.0  # 351.6 mm^4, Y load
I_LATERAL = ARM_H * ARM_B**3 / 12.0  # 625 mm^4, X load
_ratio = ARM_H / ARM_B
J_TORSION = (
    ARM_B * ARM_H**3 * (1.0 / 3.0 - 0.21 * _ratio * (1.0 - _ratio**4 / 12.0))
)  # 759 mm^4 (Roark)
# Free span: the collar's shell to the flange's free (front) face.
OLD_FLANGE_FRONT_LOCAL_Z = 52.01  # pre-A1 SIDE_PLATE_Z[0] (BRACKET_ORIGIN z -128.3)
ARM_SPAN = SIDE_PLATE_Z[0] - COLLAR_OD / 2.0  # 91.22
OLD_ARM_SPAN = OLD_FLANGE_FRONT_LOCAL_Z - COLLAR_OD / 2.0  # 46.01


def hook_deflection_along_wire(span: float, tension: float, weight: float) -> float:
    """Hook motion along wire 1 (mm; signed, negative toward the drum).

    Twist phi = Mz L / (G J) turns the hook about the arm's axis (Z) through
    the collar; the cantilever tip moves by F L^3 / (3 E I) in Y and in X and
    carries the lever rigidly. The collar's bending slope turns the group
    about X and Y, which moves the hook only by its z offset from the collar:
    zero in the A1 plane.
    """
    fx, fy, mz = collar_load(tension, weight)
    phi = mz * span / (G_STEEL * J_TORSION)
    # Rotation phi about +Z: hook offset (dx, dy) moves by phi * (-dy, dx).
    dx = phi * -HOOK_DY + fx * span**3 / (3.0 * E_STEEL * I_LATERAL)
    dy = phi * HOOK_DX + fy * span**3 / (3.0 * E_STEEL * I_VERTICAL)
    return -(dx * WIRE_DIR[0] + dy * WIRE_DIR[1])


HOOK_OFFSET_NEW = abs(
    hook_deflection_along_wire(ARM_SPAN, WIRE1_TENSION_MAX_N, LEVER_GROUP_N)
)  # 0.276 mm
HOOK_OFFSET_OLD = abs(
    hook_deflection_along_wire(OLD_ARM_SPAN, WIRE1_TENSION_MAX_N, LEVER_GROUP_N)
)  # 0.123 mm
PEN_OFFSET_NEW = WIRE_RATIO * HOOK_OFFSET_NEW  # 1.38 mm, static, zeroed at setup
PEN_OFFSET_OLD = WIRE_RATIO * HOOK_OFFSET_OLD  # 0.61 mm
ARM_COMPLIANCE_MM_PER_N = abs(
    hook_deflection_along_wire(ARM_SPAN, 1.0, 0.0)
)  # 0.0227 along wire 1
OLD_ARM_COMPLIANCE_MM_PER_N = abs(
    hook_deflection_along_wire(OLD_ARM_SPAN, 1.0, 0.0)
)  # 0.0101
# Pen-equivalent swing as the guide friction reverses: 0.36 (old) -> 0.81 mm
# here, a fraction (ARM / spring compliance) of what the same load swing
# already does through the springs. The test bounds that fraction.
PEN_SWING_NEW = WIRE_RATIO * ARM_COMPLIANCE_MM_PER_N * WIRE1_TENSION_SWING_N
PEN_SWING_OLD = WIRE_RATIO * OLD_ARM_COMPLIANCE_MM_PER_N * WIRE1_TENSION_SWING_N
ARM_SHARE_OF_SPRING_COMPLIANCE_MAX = 0.01

# Peak arm stresses at the flange (the fixed end).
_FX, _FY, _MZ = collar_load(WIRE1_TENSION_MAX_N, LEVER_GROUP_N)
BENDING_STRESS = (
    abs(_FY) * ARM_SPAN * (ARM_H / 2.0) / I_VERTICAL
    + abs(_FX) * ARM_SPAN * (ARM_B / 2.0) / I_LATERAL
)  # 13.1 N/mm^2
# Shigley's rectangular-bar maximum shear, a = 10 the long side, b = 7.5.
TORSION_STRESS = (
    abs(_MZ) * (3.0 * ARM_B + 1.8 * ARM_H) / (ARM_B**2 * ARM_H**2)
)  # 10.6 N/mm^2
STEEL_YIELD = 370.0  # N/mm^2, 1018 cold drawn

# --- flange joint: two #2-56 at machine x 1 and 14.7 on the seat plane ----------
SCREW_PITCH_X = SCREW_MACHINE_X[1] - SCREW_MACHINE_X[0]  # 13.7
JOINT = (
    (SCREW_MACHINE_X[0] + SCREW_MACHINE_X[1]) / 2.0,
    BRACKET_ORIGIN[1],
    SEAT_PLANE_Z,
)
# Moments of the collar load about the screw row's centre (r = collar - joint).
_RX, _RY, _RZ = (
    c - j for c, j in zip(COLLAR, JOINT, strict=True)
)  # (32.15, 0, -100.4)
JOINT_MX = -_RZ * _FY  # prying about X (the row lies along X): both screws load
JOINT_MY = _RZ * _FX  # prying about Y: the screws load differentially
JOINT_MZ = _MZ + _RX * _FY - _RY * _FX  # in-plane torque about the seat normal
# Conservative preload: 0.10 N m hand torque on a #2-56, K = 0.25 (dry, small
# screw, generous) -> F = T / (K d).
SCREW_PRELOAD_N = 100.0 / (0.25 * SCREW_MAJOR_DIA)  # 183 N
# In-plane: direct shear plus the torque couple, the worse screw: 132 N.
# Friction alone carries 55 N at the row (mu 0.15 steel on aluminium), a
# 0.21 slip margin that is PRE-EXISTING and independent of the arm's length
# (the torque is the hook's moment about the collar plus the collar's x
# offset from the row, both in the seat plane). It is not a slip criterion:
# the torque never reverses sign (wire 1's tension is the pen side's weight,
# positive even with the guide friction subtracted), so the flange settles
# once against the screw shanks and then bears. The shank carries it in shear.
JOINT_SHEAR_DEMAND_N = math.hypot(_FX, _FY) / 2.0 + abs(JOINT_MZ) / SCREW_PITCH_X
_MZ_MIN_TENSION = collar_load(
    WIRE_RATIO * PEN_SIDE_G * G * (1.0 - GUIDE_FRICTION_FRACTION), LEVER_GROUP_N
)[2]
_MZ_NO_GROUP = collar_load(WIRE1_TENSION_MAX_N, 0.0)[2]
# Shear plane at the seat face, conservatively in the thread: #2-56 basic
# minor D - 1.299 P = 1.595 mm, 2.00 mm^2.
SCREW_MINOR_DIA = SCREW_MAJOR_DIA - 1.299 * (25.4 / 56.0)
SCREW_SHEAR_STRESS = JOINT_SHEAR_DEMAND_N / (
    math.pi / 4.0 * SCREW_MINOR_DIA**2
)  # 66 N/mm^2
# 18-8 stainless (config/parts/mg-vn-magnifying-bracket-screw.yaml, AISI 304):
# McMaster's 70 ksi (483 MPa) minimum tensile, shear ultimate 0.6 x = 290 MPa,
# allowable a third of that.
SCREW_SHEAR_ALLOWABLE = 0.6 * 483.0 / 3.0  # 96.6 N/mm^2
# Prying: the flange tips about its lower (or upper) edge, SIDE_PLATE_HEIGHT/2
# from the row; about Y, about its far end, the row's pitch the lever arm.
# Old 52 arm: 61 N per screw, margin 3.0; A1: 111 N, margin 1.65.
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

# --- collar press: the lever held by the press alone (#1570, PRESS ONLY) -------
# The lever rod runs along machine X through the collar. Wire 1 and the group's
# weight load it in the A1 plane through its axis, so the rod sees axial _FX
# and the bending _MZ (carried by the collar bore in bearing) but nominally no
# twist. The twist is bounded by putting the whole wire tension and group
# weight one lever diameter out of that plane.
COLLAR_TWIST_OFFSET = LEVER_ROD_DIA
COLLAR_TORQUE_DEMAND_NMM = (
    WIRE1_TENSION_MAX_N + LEVER_GROUP_N
) * COLLAR_TWIST_OFFSET  # 70 N mm
PRESS_HOLDING = press_holding(abs(_FX), COLLAR_TORQUE_DEMAND_NMM)
# 241 N against 2.9 N; 724 N mm against 70 N mm at the loosest corner, after
# DIN 7190 smoothing (effective 0.00188 of the 0.007 minimum).
PRESS_HOLDING_MARGIN_MIN = 3.0
if min(PRESS_HOLDING["axial_margin"], PRESS_HOLDING["torque_margin"]) < (
    PRESS_HOLDING_MARGIN_MIN
):
    raise AssertionError(
        "the collar press alone does not hold the lever 3x at its loosest corner"
    )
# The bending _MZ tilts the press pressure along the straight cylinder
# (6 M / (d L^2) at each edge). At the loosest corner it exceeds the moment
# that just unloads one edge (890 N mm), so that edge carries the couple in
# bearing; the pressure stays a positive part of a linear field, whose integral
# (the friction's normal force) cannot fall below the uniform press's, so the
# holds above stand. At the tightest, thinnest-wall corner the loaded edge's
# Lamé von Mises is 399 MPa, past the 1018 collar's 370 yield: a local,
# self-limiting edge yield the owner accepted (#1570 ruling b) because no
# stock collar OD brings it under 0.9 x yield (the edge bearing does not fall
# with OD). The uniform press stays under that limit (330.8 MPa).
COLLAR_EDGE_BENDING = collar_edge_bending(abs(_MZ))
COLLAR_EDGE_VON_MISES_MAX_MPA = 400.0  # the accepted edge yield's pinned ceiling
if COLLAR_EDGE_BENDING["edge_von_mises_tight_mpa"] > COLLAR_EDGE_VON_MISES_MAX_MPA:
    raise AssertionError(
        "the collar edge's bending yield grew past its accepted 400 MPa"
    )
