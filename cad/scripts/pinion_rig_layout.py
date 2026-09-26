r"""Axial (machine-z) stations of the alignment-pinion swing rig -- one source
for the drive-train assembly, the harmonic base's transferred seats and the
torque-shaft / lift-rod lengths.

GEOMETRY ONLY: no drawing notes, no annotation contract, no drawing spec
imports (the ``pinion_cam_geometry`` precedent), so a print-wording edit can
never re-key the base or the drive train.

User ruling (c), 2026-09-24: the two pivot blocks locate the swing cluster
(strap / drum / strap) axially, as the ch25 photos show -- no collar, no
spacer.  At fit-up the cluster is pushed hard against the BACK block and the
FRONT block is stood off the front strap with a 0.25 feeler before its base
seats are spotted through it (the existing U28 transfer-at-assembly step).
The same ruling moved the drum's bond station 0.3 aft on the MHA-102 arbor
(drum front end 61.55 from the head shoulder), so j = 19 reads full face at
nominal; RIG_AFT_SHIFT then moved the whole rig aft so it reads full face at
the worst stack too.

Option E-a pins both straps to the torque shaft, so the fit-up has two
running clearances, each set with a feeler to +/- 0.10 (Main, restricted
review of #858).  The strap / shaft / strap group slides between the blocks
by the 0.25 front-block feeler, P.  The drum, bonded on MHA-102, turns between
the pinned straps in the gap the 0.45 shim left at its front end when the
shaft was match-drilled.  The saved pose IS that drilling set-up (Codex
#854/#858 P1): the back strap hard on the back stop, the drum hard on the back
strap, the feeler at the drum's front end and at the front block, so every
station a part is made or drilled at -- base seats, strap cross holes, shaft
holes -- is the station the assembly shows.  The worst-case gates sweep both
clearances (``test_drive_train_support_layout``).
"""

from __future__ import annotations

import math

from _printed_tolerance import printed_band_mm, printed_deviations
from cone_pivot_post_installation import MECHANISM_Z_SHIFT
from pinion_bracket_geometry import THICKNESS as STRAP_T
from pinion_bracket_geometry import THICKNESS_PLACES as STRAP_T_PLACES
from pinion_cam_geometry import CAM_LEN
from pinion_lever_geometry import BORE_DEPTH as LEVER_BORE_DEPTH
from pinion_lever_geometry import BORE_DEPTH_PLACES as LEVER_BORE_DEPTH_PLACES
from pinion_lever_geometry import GRIP_FROM_B_PLACES as LEVER_GRIP_FROM_B_PLACES
from pinion_lever_geometry import HUB_LEN as LEVER_HUB_LEN
from pinion_lever_geometry import ROD_DIA as LEVER_ROD_DIA
from pinion_lever_geometry import ROD_DIA_PLACES as LEVER_ROD_DIA_PLACES
from pinion_lever_geometry import WALL_T as LEVER_WALL_T
from pinion_pivot_block_geometry import (
    BLOCK_DEPTH,
    BLOCK_DEPTH_BAND as BLOCK_DEPTH_BAND,
    BLOCK_DEPTH_PLACES,
)
from pinion_spring_geometry import PAD_WIDTH as SPRING_PAD_WIDTH
from pinion_spring_geometry import PAD_WIDTH_PLACES as SPRING_PAD_WIDTH_PLACES
from pinion_spring_geometry import WIDTH as SPRING_W

# The novice-margin rule (Main, restricted review of #858): every rig-scope
# margin stands at least this much over its floor at the worst stack, and the
# drive train asserts the whole table at import.
RIG_MARGIN_SPARE = 0.25

# The front-block feeler and its ruled band (Codex #854 P1: MHA-A03 prints
# FEELER +/- BAND).  It sets the pinned cluster's end play, and the worst
# stacks read its band as the setting's error.
FRONT_BLOCK_FEELER = 0.25
FRONT_BLOCK_FEELER_BAND = 0.10
# The drum turns between the pinned straps, so it needs running clearance:
# the shaft is match-drilled with a feeler as a shim at the drum's FRONT end
# (MHA-A03's SHAFT DRILL SET), freezing the strap spacing at the drum plus the
# shim.  The drum then runs in DRUM_END_SHIM +/- DRUM_END_SHIM_SET_ERROR of end
# play (pinion_arbor_geometry.drum_total_air), set with the same band as the
# front-block feeler.  The shim is the smallest 0.05 blade whose tightest
# setting keeps the drum's MIN_END_PLAY (0.1) with RIG_MARGIN_SPARE to spare:
# 0.45, a stock leaf of the same metric gage set as the 0.25 feeler
# (pinion_rig_fitup.FEELER_GAGE); the rig's 0.25 feeler left 0.05.
DRUM_END_SHIM = 0.45
DRUM_END_SHIM_SET_ERROR = FRONT_BLOCK_FEELER_BAND
# The shaft is set for that drill with its rear end flush with MHA-061's rear
# face.  The SR crown keeps a straightedge off the crown root, so the setting
# carries its own error, printed on that step.
FLUSH_SET_ERROR = 0.10

# Every fit-up setting is a stock leaf (or a pair of leaves) of one purchased
# metric thickness gage (pinion_rig_fitup.FEELER_GAGE pins the set: 0.05 to
# 1.00 in 0.05 steps), set to the same +/- FEELER_SET_ERROR.
FEELER_LEAF_STEP = 0.05
FEELER_LEAF_MAX = 1.00
FEELER_SET_ERROR = FRONT_BLOCK_FEELER_BAND


def smallest_leaf_setting(required: float) -> float:
    """The thinnest gage setting (one leaf, or a pair) of at least ``required``."""
    setting = round(math.ceil(required / FEELER_LEAF_STEP - 1e-9) * FEELER_LEAF_STEP, 2)
    if setting > 2.0 * FEELER_LEAF_MAX:
        raise AssertionError(f"{setting} needs more than two gage leaves")
    return setting


def leaf_pair(setting: float) -> tuple[float, ...]:
    """The leaves a setting is made of: one leaf up to the thickest, else the
    thickest plus the remainder."""
    if setting <= FEELER_LEAF_MAX + 1e-9:
        return (setting,)
    return (FEELER_LEAF_MAX, round(setting - FEELER_LEAF_MAX, 2))


# MHA-002 drum.  The length is alignment_pinion_spec.FACE_WIDTH (a drawing
# contract this module must not import); a lockstep test pins the two.  It is
# trapped between the straps' inner faces, and at the drilling set-up it sits
# hard on the back strap, so the back stop sets its station (61.55 from the
# MHA-102 head shoulder, ruling (c)'s bond station).
DRUM_LEN = 143.2
DRUM_LEN_PLACES = 1  # FaceWidth prints .X (alignment_pinion_spec)
DRUM_LEN_BAND = printed_band_mm(DRUM_LEN_PLACES)  # 0.8
DRUM_OD_PLACES = 2  # OutsideDia prints .XX (alignment_pinion_spec)

# The rig's axial datum (user ruling, 2026-09-25, P1-2): the base seats are
# transferred from the blocks, so nothing in the frame fixes the rig along z
# until the fitter sets it.  With the cluster hard back and the drum hard on
# the back strap, and the cylinder-gear bank pushed north (back), the drum's
# back end is set RIG_SET_LEAF_D off gear j = 19's back face, and only then
# are the block seats spotted (the base's transfer callout,
# pinion_rig_fitup.RIG_SET_STEP).  With the bank pushed north at the set, g19
# never sits north of that datum: the bank's end play E_b only moves it south,
# away from j = 19's worst case, so the bank adds nothing to the advance
# (#743's G19_BACK_NORTH_STACK is empty; without the precondition the stack
# would carry E_b max).  The drum is located from g19
# directly, so neither the strap thickness nor g19's own station reaches
# j = 19.  From that set-up the drum's back end can only advance: the pinned
# cluster runs forward to the front block, the drum forward in its shimmed
# end play, and the leaf itself sets to its band.  j = 19 keeps its FULL 3.0
# face with RIG_MARGIN_SPARE to spare, so D is the thinnest gage setting that
# covers the advance plus the spare.
# TODO(#743): the cylinder-gear bank's end play (E_b) and its g0 -> g19
# pitch-stack band come from the bank retention design
# (cylinder_bank_layout.G0_FRONT_SOUTH_STACK) and join the front stack below
# as named terms; until that module lands they are listed, never valued.
G19_BACK_FACE_Z = (
    71.56188830854866  # Z_DRUM0 + 19 Z_PITCH + 1.5 (the drive train pins it)
)
DRUM_BACK_ADVANCE_STACK = {
    "MHA-A03 feeler, widest (the pinned cluster's end play)": FRONT_BLOCK_FEELER
    + FRONT_BLOCK_FEELER_BAND,
    "MHA-A03 feeler, widest (the drum's shimmed end play)": DRUM_END_SHIM
    + DRUM_END_SHIM_SET_ERROR,
    "rig-set leaf D, thinnest setting": FEELER_SET_ERROR,
}
DRUM_BACK_ADVANCE_OPEN_TERMS: tuple[str, ...] = ()  # the bank is pushed north
DRUM_FRONT_RETREAT_STACK = {
    "MHA-002 drum length .X": -printed_deviations(DRUM_LEN, DRUM_LEN_PLACES)[0],
    "rig-set leaf D, thickest setting": FEELER_SET_ERROR,
}
DRUM_FRONT_RETREAT_OPEN_TERMS = (
    "MHA-027 bank end play E_b (#743)",
    "MHA-027 g0 -> g19 pitch stack (#743)",
)
RIG_SET_LEAF_D = smallest_leaf_setting(
    sum(DRUM_BACK_ADVANCE_STACK.values()) + RIG_MARGIN_SPARE
)  # 1.25
RIG_SET_LEAVES = leaf_pair(RIG_SET_LEAF_D)  # (1.00, 0.25)
BACK_STOP_Z = G19_BACK_FACE_Z + RIG_SET_LEAF_D + STRAP_T
# BACK_STOP_Z, the back block's inner face, is where every station below
# derives from.  The U28 block put it at 77.75 (its outer face at the
# released machine z 88.0, 10.25 deep); the E-a re-size deepened MHA-061
# OUTWARD, and the D set-up now moves the whole rig RIG_AFT_SHIFT aft of it.
U28_BACK_BLOCK_OUTER_Z = 88.0
U28_BLOCK_DEPTH = 10.25
U28_BACK_STOP_Z = U28_BACK_BLOCK_OUTER_Z - U28_BLOCK_DEPTH  # 77.75
RIG_AFT_SHIFT = BACK_STOP_Z - U28_BACK_STOP_Z - MECHANISM_Z_SHIFT  # derived
BACK_BLOCK_Z0 = BACK_STOP_Z
BACK_BLOCK_OUTER_Z = BACK_BLOCK_Z0 + BLOCK_DEPTH

DRUM_BACK_Z = BACK_BLOCK_Z0 - STRAP_T
DRUM_FRONT_Z = DRUM_BACK_Z - DRUM_LEN
STRAP_Z_INNER = (DRUM_FRONT_Z - DRUM_END_SHIM, DRUM_BACK_Z)
STRAP_Z_OUTER = (STRAP_Z_INNER[0] - STRAP_T, BACK_BLOCK_Z0)

# The front block stands the feeler off the front strap's outer face: the
# strap / shaft / strap group's end play between the blocks.
FRONT_BLOCK_Z0 = STRAP_Z_OUTER[0] - FRONT_BLOCK_FEELER - BLOCK_DEPTH
BLOCK_Z0 = (FRONT_BLOCK_Z0, BACK_BLOCK_Z0)
# Each block's two #8 hold-down seats sit at its mid-depth (the base spots
# them through the block holes at assembly).
BLOCK_SEAT_Z = tuple(z0 + BLOCK_DEPTH / 2.0 for z0 in BLOCK_Z0)

# The span between the blocks' inner faces: both straps, the drum, its end
# shim and the front-block feeler (Codex #854 P1), the same in the pose and on
# the machine.
INNER_SPAN = BACK_BLOCK_Z0 - (FRONT_BLOCK_Z0 + BLOCK_DEPTH)  # 161.90
_SOLID_SPAN = 2.0 * STRAP_T + DRUM_LEN + DRUM_END_SHIM + FRONT_BLOCK_FEELER
if abs(INNER_SPAN - _SOLID_SPAN) > 1e-9:
    raise AssertionError("the block span is not the stack plus shim and feeler")


# Worst fitted stack (Codex #854 P1).  The span between the blocks is two
# straps, the drum, its end shim and the feeler, each inside its own printed
# band -- the straps' and the drum's .X (U27: never tightened to .XX for
# this), the shim's and the feeler's ruled band -- and each block adds its own
# .XX depth.  The stacks
# below carry every term by name; nothing sums them into one symmetric band.
# The torque shaft and the lift rod are set back-flush, so those terms land
# at their front ends and size both lengths.

# Torque shaft and lift rod: back ends flush with the back block's outer face,
# both printed at .X (title-block +/-0.8, U27) and rounded UP.
LENGTH_PLACES = 1
LENGTH_BAND = printed_band_mm(LENGTH_PLACES)  # 0.8

# Each term reads the deviation the part's sheet PRINTS (_printed_tolerance):
# the thickest strap, the longest drum and the deepest block lengthen the stack.
_STRAP_T_UPPER = printed_deviations(STRAP_T, STRAP_T_PLACES)[1]
_DRUM_LEN_UPPER = printed_deviations(DRUM_LEN, DRUM_LEN_PLACES)[1]
_BLOCK_DEPTH_UPPER = printed_deviations(BLOCK_DEPTH, BLOCK_DEPTH_PLACES)[1]


def _up_to_tenth(length: float) -> float:
    return math.ceil(length * 10.0 - 1e-6) / 10.0


# The shortest shaft in the longest stack must still bear
# FRONT_BLOCK_MIN_BEARING of the front block's bore (rule 12's 1.5 D on the
# 1/4 in shaft), and BLOCK_BEARING_MARGIN more (Main, #858: rounding the
# length to its .X place had left 0.09).  Set back-flush, the shaft's front
# end reaches past the back block and the inner span into the front block;
# each term below names the dimension that moves it and the part that prints
# it (the W15 stack pattern).
FRONT_BLOCK_MIN_BEARING = 9.5
BLOCK_BEARING_MARGIN = 0.5


def torque_shaft_bearing_stack(shaft_len: float) -> dict[str, float]:
    """Worst-case engagement of the torque shaft in the front block's bore."""
    return {
        "nominal (shaft - back block - inner span)": shaft_len
        - BLOCK_DEPTH
        - INNER_SPAN,
        "MHA-062 shaft length .X": printed_deviations(shaft_len, LENGTH_PLACES)[0],
        "MHA-061 back block depth .XX": -_BLOCK_DEPTH_UPPER,
        "MHA-056 strap thickness .X (2 straps)": -2.0 * _STRAP_T_UPPER,
        "MHA-002 drum length .X": -_DRUM_LEN_UPPER,
        "MHA-A03 front block feeler band": -FRONT_BLOCK_FEELER_BAND,
        "MHA-062 drum end shim set error": -DRUM_END_SHIM_SET_ERROR,
        "MHA-062 rear end flush set": -FLUSH_SET_ERROR,
    }


def _stack_text(stack: dict[str, float]) -> str:
    terms = ", ".join(f"{name} {value:+.3f}" for name, value in stack.items())
    return f"{terms} = {sum(stack.values()):.3f}"


_FRONT_BEARING_REQUIRED = FRONT_BLOCK_MIN_BEARING + BLOCK_BEARING_MARGIN
TORQUE_SHAFT_LEN = _up_to_tenth(
    _FRONT_BEARING_REQUIRED - sum(torque_shaft_bearing_stack(0.0).values())
)
TORQUE_SHAFT_BEARING_STACK = torque_shaft_bearing_stack(TORQUE_SHAFT_LEN)
if sum(TORQUE_SHAFT_BEARING_STACK.values()) < _FRONT_BEARING_REQUIRED - 1e-9:
    raise AssertionError(
        "torque shaft bearing in the front block, worst case: "
        f"{_stack_text(TORQUE_SHAFT_BEARING_STACK)} < {_FRONT_BEARING_REQUIRED}"
    )
TORQUE_SHAFT_Z0 = BACK_BLOCK_OUTER_Z - TORQUE_SHAFT_LEN

# Option E-a (pinion_strap_pin_spec): MHA-062's two set-pin holes are
# match-drilled through the MHA-056 cross holes at the fit-up stack, so they
# sit at the strap mid-planes, measured from the shaft's front end (local z 0).
# Computed here, beside the stations they come from, so the drive train reads
# them without importing the shaft's drawing contract (restricted review).
STRAP_MID_Z = tuple(
    (outer + inner) / 2.0 for outer, inner in zip(STRAP_Z_OUTER, STRAP_Z_INNER)
)  # (front, back)
TORQUE_SHAFT_PIN_HOLE_Z = tuple(z - TORQUE_SHAFT_Z0 for z in STRAP_MID_Z)

# Option E-a (pinion_strap_pin_spec): pinned to the straps, the shaft rides the
# cluster's end play.  Match-drilled flush with the back block's outer face at
# the back stop, it retreats up to the widest feeler setting into the back
# block when the cluster runs forward to the front block, so the shallowest
# printed back block must still give it the front block's floor (rule 12's
# 1.5 D on the 1/4 in shaft).  Geometry, not a tighter band, carries it:
# BLOCK_DEPTH, with BLOCK_BEARING_MARGIN over that floor (Main, #858: the
# 10.5 block left 0.04 once the flush setting was booked).
BACK_BLOCK_MIN_BEARING = FRONT_BLOCK_MIN_BEARING


def torque_shaft_back_bearing_stack() -> dict[str, float]:
    """Worst-case engagement of the pinned torque shaft in the back block."""
    return {
        "MHA-061 back block depth": BLOCK_DEPTH,
        "MHA-061 back block depth .XX": printed_deviations(
            BLOCK_DEPTH, BLOCK_DEPTH_PLACES
        )[0],
        "MHA-A03 feeler, widest (the E-a shaft's end play)": -(
            FRONT_BLOCK_FEELER + FRONT_BLOCK_FEELER_BAND
        ),
        "MHA-062 rear end flush set": -FLUSH_SET_ERROR,
    }


TORQUE_SHAFT_BACK_BEARING_STACK = torque_shaft_back_bearing_stack()
_BACK_BEARING_REQUIRED = BACK_BLOCK_MIN_BEARING + BLOCK_BEARING_MARGIN
if sum(TORQUE_SHAFT_BACK_BEARING_STACK.values()) < _BACK_BEARING_REQUIRED - 1e-9:
    raise AssertionError(
        "pinned torque shaft bearing in the back block, worst case: "
        f"{_stack_text(TORQUE_SHAFT_BACK_BEARING_STACK)} < {_BACK_BEARING_REQUIRED}"
    )

# The rod floats north until the back MHA-104 collar lands on the back block;
# the MHA-059 lever hub must never be that stop.  User ruling (2026-09-25,
# P1-1): the back collar's back face is set BACK_COLLAR_LEAF_F off the back
# block's inner face with a gage leaf, mirroring the front collar's feeler
# against the front block.  Its gap is then the leaf and its set error only --
# no collar length, strap thickness or by-eye term -- and the follower pin
# rides wherever that puts it (BACK_CAM_PIN_STATION, from the collar's front
# face).  The by-eye set to the pin it replaces had no feasible station once
# the collar's .X length band was booked (Main, restricted review of #858).
# F = 0.90 (user ruling): one step thicker than the thinnest leaf whose
# tightest setting keeps the collar BACK_COLLAR_MIN_GAP + RIG_MARGIN_SPARE off
# the block (0.85), so that row keeps 0.05 in hand.
BACK_COLLAR_MIN_GAP = 0.5  # the collar never lands on the block but as the stop
HUB_STOP_MARGIN = 0.25
BACK_COLLAR_LEAF_F = 0.90
if BACK_COLLAR_LEAF_F < smallest_leaf_setting(
    BACK_COLLAR_MIN_GAP + RIG_MARGIN_SPARE + FEELER_SET_ERROR
):
    raise AssertionError("the back-collar leaf no longer covers its floor and spare")
BACK_COLLAR_GAP_MIN = BACK_COLLAR_LEAF_F - FEELER_SET_ERROR  # 0.80
BACK_COLLAR_GAP_MAX = BACK_COLLAR_LEAF_F + FEELER_SET_ERROR  # 1.00
_STRAP_T_LOWER = printed_deviations(STRAP_T, STRAP_T_PLACES)[0]
BACK_CAM_PIN_STATION = CAM_LEN + BACK_COLLAR_LEAF_F - STRAP_T / 2.0  # 5.40
LEVER_SEAT_MIN = LEVER_BORE_DEPTH + BACK_COLLAR_GAP_MAX + HUB_STOP_MARGIN  # 9.25


def lift_rod_seat_stack(rod_len: float) -> dict[str, float]:
    """Worst-case length of lift rod standing proud of the front block."""
    return {
        "nominal (rod - both blocks - inner span)": rod_len
        - 2.0 * BLOCK_DEPTH
        - INNER_SPAN,
        "MHA-060 rod length .X": printed_deviations(rod_len, LENGTH_PLACES)[0],
        "MHA-061 block depth .XX (2 blocks)": -2.0 * _BLOCK_DEPTH_UPPER,
        "MHA-056 strap thickness .X (2 straps)": -2.0 * _STRAP_T_UPPER,
        "MHA-002 drum length .X": -_DRUM_LEN_UPPER,
        "MHA-A03 front block feeler band": -FRONT_BLOCK_FEELER_BAND,
        "MHA-062 drum end shim set error": -DRUM_END_SHIM_SET_ERROR,
    }


# The MHA-059 lever rides the rod's front end, just south of the torque
# shaft's front end, so a SHORT rod pulls the lever's throw plane toward it.
# The grip arm's axis sits GripFromB from the hub's mouth face B, which sits
# BoreDepth from the floor the rod seats on, and the arm is RodDia across
# (pinion_lever_geometry); the drive train pins this nominal to its pose.
LEVER_THROW_MIN_AIR = 0.25
# Lever throw plane north face, measured from the rod's front end.
LEVER_PLANE_NORTH_FROM_ROD_END = (
    LEVER_HUB_LEN / 2.0 - LEVER_WALL_T + LEVER_ROD_DIA / 2.0
)


def _lever_arm_stack(direction: str) -> dict[str, float]:
    """The grip arm's own printed bands, toward ``direction``."""
    bore = printed_deviations(LEVER_BORE_DEPTH, LEVER_BORE_DEPTH_PLACES)
    grip = printed_deviations(LEVER_HUB_LEN / 2.0, LEVER_GRIP_FROM_B_PLACES)
    arm = printed_deviations(LEVER_ROD_DIA, LEVER_ROD_DIA_PLACES)
    return {
        "MHA-059 bore depth .X": -bore[0] if direction == "south" else bore[1],
        "MHA-059 grip from face B .XX": grip[1] if direction == "south" else -grip[0],
        "MHA-059 arm dia .X, half": arm[1] / 2.0,
    }


def lever_north_travel_stack(rod_len: float) -> dict[str, float]:
    """Worst-case travel of the lever's throw plane north of the pose."""
    return {
        "MHA-060 rod length .X (shortest)": -printed_deviations(rod_len, LENGTH_PLACES)[
            0
        ],
        "MHA-060 floated north to the back collar": BACK_COLLAR_GAP_MAX,
        **_lever_arm_stack("north"),
    }


def lever_south_travel_stack(rod_len: float) -> dict[str, float]:
    """Worst-case travel of the lever's throw plane south of the pose."""
    return {
        "MHA-060 rod length .X (longest)": printed_deviations(rod_len, LENGTH_PLACES)[
            1
        ],
        "MHA-060 floated south to the front collar (widest feeler)": (
            FRONT_BLOCK_FEELER + FRONT_BLOCK_FEELER_BAND
        ),
        **_lever_arm_stack("south"),
    }


SHAFT_FRONT_SOUTH_TRAVEL_STACK = {
    "MHA-062 length .X (longest)": printed_deviations(TORQUE_SHAFT_LEN, LENGTH_PLACES)[
        1
    ],
    "MHA-A03 feeler, widest (the pinned cluster runs forward)": (
        FRONT_BLOCK_FEELER + FRONT_BLOCK_FEELER_BAND
    ),
    "MHA-062 rear end flush set": FLUSH_SET_ERROR,
}


def lever_to_shaft_front_worst(rod_len: float) -> float:
    """Worst-case air from the lever's throw plane to the shaft's front end."""
    nominal = rod_len - TORQUE_SHAFT_LEN - LEVER_PLANE_NORTH_FROM_ROD_END
    return (
        nominal
        - sum(lever_north_travel_stack(rod_len).values())
        - sum(SHAFT_FRONT_SOUTH_TRAVEL_STACK.values())
    )


# MHA-060 is the longer of two requirements, each at its worst stack with
# RIG_MARGIN_SPARE: the rod standing LEVER_SEAT_MIN proud of the front block,
# and the lever's throw plane clearing the torque shaft's front end (the leaf
# F shortened the seat requirement by 1.6, and the lever then crowded the
# shaft to 0.14 -- Main, restricted review of #858).
_LEVER_SEAT_REQUIRED = LEVER_SEAT_MIN + RIG_MARGIN_SPARE
_LEVER_AIR_REQUIRED = LEVER_THROW_MIN_AIR + RIG_MARGIN_SPARE
LIFT_ROD_LEN = _up_to_tenth(
    max(
        _LEVER_SEAT_REQUIRED - sum(lift_rod_seat_stack(0.0).values()),
        _LEVER_AIR_REQUIRED - lever_to_shaft_front_worst(0.0),
    )
)
LEVER_NORTH_TRAVEL_STACK = lever_north_travel_stack(LIFT_ROD_LEN)
LEVER_SOUTH_TRAVEL_STACK = lever_south_travel_stack(LIFT_ROD_LEN)
LEVER_TO_SHAFT_FRONT_WORST = lever_to_shaft_front_worst(LIFT_ROD_LEN)
if LEVER_TO_SHAFT_FRONT_WORST < _LEVER_AIR_REQUIRED - 1e-9:
    raise AssertionError(
        f"lever throw plane to the shaft front, worst {LEVER_TO_SHAFT_FRONT_WORST:.3f}"
    )
LIFT_ROD_SEAT_STACK = lift_rod_seat_stack(LIFT_ROD_LEN)
if sum(LIFT_ROD_SEAT_STACK.values()) < _LEVER_SEAT_REQUIRED - 1e-9:
    raise AssertionError(
        "lift rod seat past the front block, worst case: "
        f"{_stack_text(LIFT_ROD_SEAT_STACK)} < {_LEVER_SEAT_REQUIRED}"
    )
# The nominal rod standing proud of the front block, as built.
LEVER_SEAT_PROUD = LIFT_ROD_LEN - 2.0 * BLOCK_DEPTH - INNER_SPAN  # 15.60
LIFT_ROD_Z0 = BACK_BLOCK_OUTER_Z - LIFT_ROD_LEN

# MHA-114 return spring: the blade rides the back strap's flank, and its foot
# pad lies on the base beside the back block.  Main (restricted review of
# #858): the pad is set SPRING_PAD_LEAF off the back block's inner face with a
# gage leaf before its seat is transferred, so the spring is stationed from
# the block, not from the strap.  The blade's inset from the strap's NOMINAL
# inner face follows, and a thin strap (inner face 0.8 aft) or the leaf's
# set error only moves the flank under it: 1.00 leaves the blade exactly
# SPRING_BLADE_MIN_ON_FLANK + RIG_MARGIN_SPARE on the flank at the worst
# setting, and the pad 0.645 off the block.
SPRING_PAD_LEAF = 1.00
SPRING_Z = BACK_BLOCK_Z0 - SPRING_PAD_LEAF - SPRING_PAD_WIDTH / 2.0
SPRING_BLADE_INSET = SPRING_Z - SPRING_W / 2.0 - STRAP_Z_INNER[1]  # 1.25
SPRING_BLADE_MIN_ON_FLANK = 0.1
SPRING_BLADE_ON_FLANK_WORST = (
    SPRING_BLADE_INSET + _STRAP_T_LOWER - FEELER_SET_ERROR
)  # 0.35
SPRING_PAD_MIN_AIR = 0.25
SPRING_PAD_TO_BLOCK_WORST = (
    SPRING_PAD_LEAF
    - FEELER_SET_ERROR
    - printed_deviations(SPRING_PAD_WIDTH, SPRING_PAD_WIDTH_PLACES)[1] / 2.0
)  # 0.645
for _name, _worst, _floor in (
    (
        "spring blade on the back strap flank",
        SPRING_BLADE_ON_FLANK_WORST,
        SPRING_BLADE_MIN_ON_FLANK,
    ),
    (
        "spring foot pad to the back block",
        SPRING_PAD_TO_BLOCK_WORST,
        SPRING_PAD_MIN_AIR,
    ),
):
    if _worst < _floor + RIG_MARGIN_SPARE - 1e-9:
        raise AssertionError(
            f"{_name}, worst case {_worst:.3f} < {_floor} + {RIG_MARGIN_SPARE}"
        )
