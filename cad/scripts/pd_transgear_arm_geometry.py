r"""Pure transgear-arm (MHA-PD-018) geometry shared by the arm, its plate, its
pivot hardware and the paper-drive assembly.

Book ch. 23 (t157 / t161 / t241): a steel link that swings on the MHA-VN-041
shoulder screw at the pivot P on the support bar, carries the MHA-PD-023 pin of
the disc cluster (pressed into a reamed hole) at S, the MHA-PD-019 plate (and
through it the knob shaft) on two #8-32 taps between them, and the 1/8 latch
pin in its square end.

Local frame (the part's origin and axes; the assembly places it by a pure
rotation about Z and a translation):

* origin on the pivot axis P, on the arm's FRONT face (the face that bears on
  the MHA-PD-020 spacer; machine z FRONT_FACE_MACHINE_Z, -124.4);
* +X along the arm centreline from P toward the square end (machine U);
* +Y across the arm toward its upper tangent edge (machine N = U rotated
  +90 deg about +Z), the edge the plate's top edge sits flush with;
* +Z through the thickness toward the rear face (machine +Z), so the arm
  occupies z 0..THICKNESS and the plate mounts on z = THICKNESS.

Keep drawing-only notes and annotation contracts out of this module so that
sheet-text edits cannot invalidate the assembly recipe.
"""

from __future__ import annotations

import math
from fractions import Fraction

import pd_rack_pinion_spec as DISC
import pd_support_bar_spec as BAR

from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm

MM_PER_IN = 25.4
# The assembly's anchor for the arm: its front face on the spacer.
FRONT_FACE_MACHINE_Z = -124.4

# --- Stock: 5/16 x 1 precision-ground flat bar, faces as supplied ------------
# The arm is cut from McMaster 9517K466 (R9-6, R9-25): its thickness is the
# stock's, ±0.001 in as supplied, not a machined band.  The sheet prints it
# as a reference to the stock; walls, joints and the chain stack read
# THICKNESS_BAND.
STOCK_SKU = "9517K466"
STOCK_THICKNESS_IN = Fraction(5, 16)
THICKNESS = float(STOCK_THICKNESS_IN) * MM_PER_IN  # 7.9375
THICKNESS_BAND = 0.001 * MM_PER_IN  # ±0.0254

# --- Outline: hull of r12.5 about P and r7 about T, cut square through T ----
PIVOT_END_R = 12.5
TIP_END_R = 7.0
# T: the r7 round's centre; the square end face lies on it.  The model
# carries the printed 128.9 (R9-13); the outline's lean and end width derive
# from it.  The sheet prints it .XX (R9-23, TIP_STATION_BAND): the latch
# pin's full diameter must pass the hook's far face, and the hook's fit-up
# set moves the hook in y/z only, so nothing absorbs the station along the
# pin axis.  With the 7/8 pin, the flap's bend and the pin's length grade
# (R9-50, transgear_hanger_joints) the worst is +0.306 at .XX, +0.016 at .X.
TIP_STATION = 128.9
# The straight edges are tangent to both rounds; each leans in toward the
# square end by EDGE_LEAN, its outward normal (sin, cos) of that angle.
EDGE_LEAN = math.asin((PIVOT_END_R - TIP_END_R) / TIP_STATION)
# Tangent point of the upper edge on the pivot round (the lower is its mirror
# in y); the square end truncates both edges at the tip station, short of
# their tangent points on the r7 round.
PIVOT_TANGENT_X = PIVOT_END_R * math.sin(EDGE_LEAN)
PIVOT_TANGENT_Y = PIVOT_END_R * math.cos(EDGE_LEAN)


def edge_half_width(x: float) -> float:
    """The outline's half-width at station x on its straight tangent edges."""
    if not PIVOT_TANGENT_X <= x <= TIP_STATION:
        raise ValueError(f"station {x} is off the straight edges")
    return PIVOT_END_R / math.cos(EDGE_LEAN) - x * math.tan(EDGE_LEAN)


END_HALF_WIDTH = edge_half_width(TIP_STATION)

# --- Pivot at P: Ø4.900 running bore + rear spot face for the head ---------
PIVOT_BORE_DIA = 4.9  # on the Ø4.7625 (-0.0254/0) shoulder, 0.069 radial
PIVOT_BORE_DIA_BAND = 0.13  # .XXX
# The spot face seats the MHA-VN-049 curved disc spring's OD rim (Ø10.744) under
# the MHA-VN-041 head; the spring's float on the shoulder still clears its rim.
SPOT_FACE_DIA = 11.5
SPOT_FACE_DIA_GROWTH = 0.10  # +0.10/0 (drilled row)
# The floor is dimensioned from the FRONT face so the spring's room never
# sees the arm's stock thickness (transgear_hanger_joints.SPRING_ROOM_*):
# 0.70..0.95, inside the spring's catalogue deflection at every corner.
SPOT_FACE_FLOOR_FROM_FRONT = 6.4
SPOT_FACE_FLOOR_BAND = 0.05
SPOT_FACE_DEPTH = THICKNESS - SPOT_FACE_FLOOR_FROM_FRONT

# --- Pin at S: REAM THROUGH, the press for the MHA-PD-023 pin (R9-68) ---------
# The pin (pd_transgear_pin_spec: Ø3.900 0/-0.008, ground) is pressed in from
# the rear until its head seats on the rear face, so the hole is reamed
# square through the ground faces.  The interference (0.010..0.026) is
# asserted in pd_transgear_arm_spec, which imports both: the pin spec imports
# this module.
PIN_STATION = 68.815  # |S - P|, printed .XXX (hole position)
# Preserve the pivot, latch and pressed stud: the rack's mounting height,
# not the hanger pose, takes up the shifted feed mesh's axis distance.
STUD_MACHINE_X = 0.0
ARM_U = (
    (STUD_MACHINE_X - BAR.PIVOT_TAP_X) / PIN_STATION,
    -math.sqrt(1.0 - ((STUD_MACHINE_X - BAR.PIVOT_TAP_X) / PIN_STATION) ** 2),
)
ARM_N = (-ARM_U[1], ARM_U[0])
ARM_ANGLE_DEG = math.degrees(math.atan2(ARM_U[1], ARM_U[0]))
_MESH_ANGLE = math.radians(DISC.MESH_ANGLE_DEG)
KNOB_BORE_STATION = PIN_STATION + DISC.CENTRE_DISTANCE * (
    math.cos(_MESH_ANGLE) * ARM_U[0] + math.sin(_MESH_ANGLE) * ARM_U[1]
)
KNOB_BORE_OFFSET = DISC.CENTRE_DISTANCE * (
    math.cos(_MESH_ANGLE) * ARM_N[0] + math.sin(_MESH_ANGLE) * ARM_N[1]
)
PIN_BORE_DIA = 3.874
PIN_BORE_DIA_BAND = (0.008, 0.0)  # (upper, lower) deviations, reamed
PIN_BORE_DIA_MAX = round(PIN_BORE_DIA + PIN_BORE_DIA_BAND[0], 6)
PIN_BORE_DIA_MIN = round(PIN_BORE_DIA + PIN_BORE_DIA_BAND[1], 6)
# --- Plate taps: 2 x #8-32 THROUGH on the centreline, countersunk both ends -
PLATE_SCREW_PITCH = 15.0
PLATE_CENTRELINE_OFFSET = -3.375  # 1-1/4 in plate's centreline from its bore
PLATE_SCREW_MID_STATION = KNOB_BORE_STATION + PLATE_CENTRELINE_OFFSET
PLATE_TAP_STATIONS = (
    PLATE_SCREW_MID_STATION - PLATE_SCREW_PITCH / 2.0,
    PLATE_SCREW_MID_STATION + PLATE_SCREW_PITCH / 2.0,
)
PLATE_TAP_SPEC = HoleSpec("tapped", "#8-32")
PLATE_TAP_CSK_DIA = 4.3  # MAX, both ends
TAP_CSK_ANGLE_DEG = 90.0
# Thread each plate-tap countersink takes at its largest, over the smallest
# tap drill (R9-63): (4.3 - 3.454) / 2 = 0.423.
PLATE_TAP_MOUTH_LOSS_MAX = (PLATE_TAP_CSK_DIA - blind_cut_dia_mm(PLATE_TAP_SPEC)) / 2.0

# --- Latch pin: reamed press hole along -X into the square end, flat floor --
PIN_HOLE_DIA = 3.175
# REAM 0/-0.010: the press fit for the 98381A474 dowel (+0.0025/+0.0076 over
# nominal) holds at both limits; .XXX (±0.13) could not hold a press.  The
# band follows the crank seat drive-pin holes' convention (R9-12).
PIN_HOLE_DIA_BAND = (0.0, -0.010)
# The dowel is pressed to the hole's flat floor (R9-12, the MHA-DT-011 / MHA-VN-044
# precedent), so the depth sets the pin's proud length: 22.225 - 8.50 = 13.725.
# R9-50: 8.50 (was 6.05 for the 3/4 pin) keeps the full diameter past the
# latch hook's far face with the flap's bend and the pin's length grade.
PIN_HOLE_DEPTH = 8.50
# The depth prints .XX: the hanger joints judge the pin's full-diameter grip
# at the shallowest hole, and the latch hook's grip on the pin over the proud
# range, both at this band.
PIN_HOLE_DEPTH_BAND = 0.51
PIN_HOLE_Z = THICKNESS / 2.0  # mid-thickness, on y = 0
# The latch pin's axis in the machine frame; the hook's hole is drilled on it.
PIN_MACHINE_Z = FRONT_FACE_MACHINE_Z + PIN_HOLE_Z  # -120.43125

# --- Bands the sheet prints (hard-coded title-block rows, policy rule 12) ---
BAND_X = 0.8
BAND_XX = 0.51
BAND_XXX = 0.13
HOLE_POSITION_BAND = 0.065  # .XXX position, per side
WALL_TARGET = 2.0
# The tip station's printed band (R9-23; see TIP_STATION).
TIP_STATION_BAND = BAND_XX

_HALF_BAND_XXX = BAND_XXX / 2.0


def _tap_major(spec: HoleSpec) -> float:
    return THREAD_MAJOR_MM[spec.size]


# Walls: nominal and worst at the printed bands (contract §8).  The hull
# radii and the tip station print .X; hole positions .XXX (±0.065); tap
# majors carry a 0.025 radial allowance for the tap's oversize.
_TAP_OVERSIZE_R = 0.025
WALLS: dict[str, tuple[float, float]] = {
    "pivot bore to end round": (
        PIVOT_END_R - PIVOT_BORE_DIA / 2.0,
        PIVOT_END_R - BAND_X - PIVOT_BORE_DIA / 2.0 - _HALF_BAND_XXX,
    ),
    "pivot bore to spot face": (
        (SPOT_FACE_DIA - PIVOT_BORE_DIA) / 2.0,
        # conservative, as the contract: the counterbore's growth is charged
        # against the ring too (it only widens it in fact)
        (SPOT_FACE_DIA - SPOT_FACE_DIA_GROWTH - PIVOT_BORE_DIA - BAND_XXX) / 2.0,
    ),
    "spot-face floor": (
        SPOT_FACE_FLOOR_FROM_FRONT,
        SPOT_FACE_FLOOR_FROM_FRONT - SPOT_FACE_FLOOR_BAND,
    ),
    "spot face to end round": (
        PIVOT_END_R - SPOT_FACE_DIA / 2.0,
        PIVOT_END_R - BAND_X - (SPOT_FACE_DIA + SPOT_FACE_DIA_GROWTH) / 2.0,
    ),
    "pin bore to edges": (
        edge_half_width(PIN_STATION) - PIN_BORE_DIA / 2.0,
        edge_half_width(PIN_STATION)
        - BAND_X
        - HOLE_POSITION_BAND
        - PIN_BORE_DIA_MAX / 2.0,
    ),
    "plate taps to edges": (
        edge_half_width(PLATE_TAP_STATIONS[1]) - _tap_major(PLATE_TAP_SPEC) / 2.0,
        edge_half_width(PLATE_TAP_STATIONS[1])
        - BAND_X
        - HOLE_POSITION_BAND
        - _tap_major(PLATE_TAP_SPEC) / 2.0
        - _TAP_OVERSIZE_R,
    ),
    # The hole's height is dimensioned from the FRONT face, so thin stock
    # takes its whole band off the rear ligament.
    "pin hole to faces": (
        (THICKNESS - PIN_HOLE_DIA) / 2.0,
        (THICKNESS - PIN_HOLE_DIA - PIN_HOLE_DIA_BAND[0]) / 2.0
        - THICKNESS_BAND
        - HOLE_POSITION_BAND,
    ),
    "pin hole to end-face edges": (
        TIP_END_R - PIN_HOLE_DIA / 2.0,
        TIP_END_R
        - BAND_X
        - (PIN_HOLE_DIA + PIN_HOLE_DIA_BAND[0]) / 2.0
        - HOLE_POSITION_BAND,
    ),
    # The latch pin's hole, at its deepest on the shortest tip station, to
    # the pin bore's far side.
    "latch-pin hole floor to pin bore": (
        TIP_STATION - PIN_HOLE_DEPTH - PIN_STATION - PIN_BORE_DIA / 2.0,
        TIP_STATION
        - TIP_STATION_BAND
        - PIN_HOLE_DEPTH
        - PIN_HOLE_DEPTH_BAND
        - PIN_STATION
        - HOLE_POSITION_BAND
        - PIN_BORE_DIA_MAX / 2.0,
    ),
}
for _name, (_nominal, _worst) in WALLS.items():
    if _worst < WALL_TARGET:
        raise AssertionError(f"arm {_name} wall {_worst:.3f} < {WALL_TARGET}")
