r"""Pure transgear-arm-plate (MHA-PD-019) geometry shared by the plate, its
screws, the knob-shaft stack and the paper-drive assembly.

Book ch. 23 (t157 / p.63; ruling 3): a piece of 1-1/4 in steel bar screwed
across the MHA-PD-018 arm by two 8-32 oval-head screws.  It carries the knob
shaft's running bore on axis K, a front hub (the thrust ring's seat) and a
rear boss (the cup runs behind it).  Its rear portion is 5 thick where it
lies over the arm; below the arm's lower edge it drops the arm's thickness
(7.9375) more to the arm's front face, so the step (the "notch") wraps that
edge, NOTCH_RELIEF clear of it (the screws locate the plate).

Local frame (same axes as the arm, so the assembly places both with one
rotation about Z):

* origin on the bore axis K, on the MOUNTING face -- the plate's front face
  that seats on the arm's rear face (machine z -116.4625);
* +X and +Y are the arm's +X (toward its square end) and +Y (toward its upper
  tangent edge); the plate's long axis runs along -Y;
* +Z toward the rear (machine +Z): the over-arm section spans z 0..5, the
  section below the arm z -7.9375..5, the front hub z -20.5375..-7.9375 and
  the rear boss z 5..8.5.

Keep drawing-only notes out of this module.
"""

from __future__ import annotations

import math

import pd_transgear_arm_geometry as ARM

# --- Where the bore sits on the arm (arm frame, mm) -------------------------
# K = the knob shaft axis, 44.766 from the stud on the permanent latch C2C;
# expressed in the arm frame it is the plate's own datum.  The integrator
# asserts it against the machine layout.
BORE_STATION = 36.917  # arm x of K
BORE_OFFSET = -31.409  # arm y of K (below the arm)

# --- Section ----------------------------------------------------------------
WIDTH = 31.75  # 1-1/4 in bar
END_R = 12.5  # full round about K; the +X edge is tangent to it
THICKNESS_OVER_ARM = 5.0  # ruling 3; prints .XX (plate-screw engagement)
NOTCH_DEPTH = ARM.THICKNESS  # the section below the arm reaches its front face
THICKNESS_BELOW_ARM = THICKNESS_OVER_ARM + NOTCH_DEPTH  # 12.9375

# Edges along the plate's long axis, in the plate frame (x from K).
EDGE_PLUS_X = END_R
EDGE_MINUS_X = END_R - WIDTH
# The −X edge runs parallel to the long axis down to the kink, then straight
# to tangency with the end round.  [INFERENCE] kink station from the notch
# crop (row ≈ 790): arm y -20.
KINK_Y = -20.0 - BORE_OFFSET

# The screws' midpoint must be the plate's centreline, the station the arm
# taps are laid out on.
if (
    abs(BORE_STATION + (EDGE_PLUS_X + EDGE_MINUS_X) / 2.0 - ARM.PLATE_SCREW_MID_STATION)
    > 5e-4
):
    raise AssertionError("plate centreline is off the arm's plate-screw midpoint")


def arm_upper_edge_y(x: float) -> float:
    """Plate-frame y of the arm's upper tangent edge (the plate's top edge)."""
    return ARM.edge_half_width(x + BORE_STATION) - BORE_OFFSET


def arm_lower_edge_y(x: float) -> float:
    """Plate-frame y of the arm's lower tangent edge."""
    return -ARM.edge_half_width(x + BORE_STATION) - BORE_OFFSET


# The screws locate the plate (its holes and countersinks on the arm's taps);
# the notch face only clears the arm's lower edge.  It stands NOTCH_RELIEF (in
# y) below that edge, parallel to it, so the arm's .X outline, the face's .X
# corner heights, the holes' position and the screws' float in them never
# close it (transgear_hanger_joints.NOTCH_AIR_WORST).
NOTCH_RELIEF = 2.5


def notch_face_y(x: float) -> float:
    """Plate-frame y of the notch face, NOTCH_RELIEF clear of the arm edge."""
    return arm_lower_edge_y(x) - NOTCH_RELIEF


TOP_LEFT = (EDGE_MINUS_X, arm_upper_edge_y(EDGE_MINUS_X))
TOP_RIGHT = (EDGE_PLUS_X, arm_upper_edge_y(EDGE_PLUS_X))
KINK = (EDGE_MINUS_X, KINK_Y)
_KINK_DIST = math.hypot(*KINK)
_TANGENT_ANGLE = math.atan2(KINK[1], KINK[0]) + math.acos(END_R / _KINK_DIST)
KINK_TANGENT = (END_R * math.cos(_TANGENT_ANGLE), END_R * math.sin(_TANGENT_ANGLE))
NOTCH_LEFT = (EDGE_MINUS_X, notch_face_y(EDGE_MINUS_X))
NOTCH_RIGHT = (EDGE_PLUS_X, notch_face_y(EDGE_PLUS_X))
if NOTCH_LEFT[1] <= KINK[1]:
    raise AssertionError("the relieved notch face drops below the -X edge's kink")

# --- Knob-shaft bearing: bore, front hub, rear boss (contract 1.10) ---------
BORE_DIA = 8.5
BORE_DIA_LIMITS = (0.015, 0.040)  # running fit on the Ø8.5 −0.013/−0.035 journal
HUB_DIA = 13.2  # .XX
# The hub stands 12.6 proud of the arm's front face, which puts its face (the
# thrust ring's seat) at machine z -137.0 whatever the arm stock (R9-25): the
# mounting face to the hub face is 20.5375 on the 7.9375 arm.  .XXX: the
# chain-plane station (contract §13).
HUB_LENGTH = 12.6
HUB_FACE_TO_MOUNTING = NOTCH_DEPTH + HUB_LENGTH  # 20.5375
BOSS_DIA = 20.0  # .X
BOSS_HEIGHT = 3.5
HUB_TO_BOSS = HUB_FACE_TO_MOUNTING + THICKNESS_OVER_ARM + BOSS_HEIGHT  # 29.0375
HUB_TO_BOSS_BAND = 0.05  # knob float
HUB_FACE_Z = -HUB_FACE_TO_MOUNTING
REAR_FACE_Z = THICKNESS_OVER_ARM
BOSS_FACE_Z = REAR_FACE_Z + BOSS_HEIGHT
FRONT_FACE_Z = -NOTCH_DEPTH

# --- Screw holes: 2 x 82° countersinks for the #8 oval heads ----------------
# Clearance, drilled +0.10/0.  Ø4.5 (not 4.4): the two shanks must float over
# the plate-to-arm pitch mismatch both parts' hole-position bands allow
# (transgear_hanger_joints.PLATE_SCREW_PITCH_MARGIN).
SCREW_HOLE_DIA = 4.5
CSK_DIA = 7.9248  # 0.312 in, the head's Ø at the top of the bevel
CSK_ANGLE_DEG = 82.0
CSK_DEPTH = (
    (CSK_DIA - SCREW_HOLE_DIA) / 2.0 / math.tan(math.radians(CSK_ANGLE_DEG / 2.0))
)
SCREW_HOLES = tuple(
    (station - BORE_STATION, -BORE_OFFSET) for station in ARM.PLATE_TAP_STATIONS
)

# --- Bands the sheet prints (hard-coded title-block rows, policy rule 12) ---
BAND_X = ARM.BAND_X
BAND_XX = ARM.BAND_XX
BAND_XXX = ARM.BAND_XXX
HOLE_POSITION_BAND = ARM.HOLE_POSITION_BAND
DRILL_GROWTH = 0.10
WALL_TARGET = ARM.WALL_TARGET
# The countersink Ø prints .X: the screws are cut flush at assembly, so the
# seat only moves the oval head proud (the shortest stock screw must still
# stand past the cut, transgear_hanger_joints.PLATE_SCREW_STOCK_PROUD_MIN) or
# sunk (the land left under the cone, WALLS), and both hold at the .X row.
CSK_DIA_BAND = BAND_X
# The notch face's corner heights print .X: the face only clears the arm's
# lower edge (transgear_hanger_joints.NOTCH_AIR_WORST).
NOTCH_BAND = BAND_X
_CSK_DEPTH_MAX = (
    (CSK_DIA + CSK_DIA_BAND - SCREW_HOLE_DIA)
    / 2.0
    / math.tan(math.radians(CSK_ANGLE_DEG / 2.0))
)

_BORE_R_MAX = (BORE_DIA + BORE_DIA_LIMITS[1]) / 2.0
_NOTCH_DISTANCE = (
    BORE_STATION * math.sin(ARM.EDGE_LEAN)
    - BORE_OFFSET * math.cos(ARM.EDGE_LEAN)
    - ARM.PIVOT_END_R
    - NOTCH_RELIEF * math.cos(ARM.EDGE_LEAN)
)
_NEAR_HOLE = min(SCREW_HOLES, key=lambda xy: math.hypot(*xy))
WALLS: dict[str, tuple[float, float]] = {
    "hub over the bore": (
        (HUB_DIA - BORE_DIA) / 2.0,
        (HUB_DIA - BAND_XX) / 2.0 - _BORE_R_MAX,
    ),
    "boss over the bore": (
        (BOSS_DIA - BORE_DIA) / 2.0,
        (BOSS_DIA - BAND_X) / 2.0 - _BORE_R_MAX,
    ),
    "bore to end round": (END_R - BORE_DIA / 2.0, END_R - BAND_X - _BORE_R_MAX),
    "bore to notch": (
        _NOTCH_DISTANCE - BORE_DIA / 2.0,
        _NOTCH_DISTANCE - NOTCH_BAND - _BORE_R_MAX,
    ),
    "bore to screw holes": (
        math.hypot(*_NEAR_HOLE) - BORE_DIA / 2.0 - SCREW_HOLE_DIA / 2.0,
        math.hypot(*_NEAR_HOLE)
        - HOLE_POSITION_BAND
        - _BORE_R_MAX
        - (SCREW_HOLE_DIA + DRILL_GROWTH) / 2.0,
    ),
    "under the countersinks": (
        THICKNESS_OVER_ARM - CSK_DEPTH,
        THICKNESS_OVER_ARM - BAND_XX - _CSK_DEPTH_MAX,
    ),
    "countersinks to the side edges": (
        SCREW_HOLES[0][0] - EDGE_MINUS_X - CSK_DIA / 2.0,
        SCREW_HOLES[0][0]
        - EDGE_MINUS_X
        - (CSK_DIA + CSK_DIA_BAND) / 2.0
        - BAND_X
        - HOLE_POSITION_BAND,
    ),
}
for _name, (_nominal, _worst) in WALLS.items():
    if _worst < WALL_TARGET:
        raise AssertionError(f"arm-plate {_name} wall {_worst:.3f} < {WALL_TARGET}")
