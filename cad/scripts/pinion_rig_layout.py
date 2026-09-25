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
running clearances, each set with the one 0.25 +/- 0.10 feeler (Main,
restricted review of #858).  The strap / shaft / strap group slides between
the blocks by the front-block feeler, P.  The drum, bonded on MHA-102, turns
between the pinned straps in the gap the feeler left at its front end when
the shaft was match-drilled.  The saved pose IS that drilling set-up (Codex
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
from pinion_bracket_geometry import THICKNESS_BAND as STRAP_T_BAND
from pinion_bracket_geometry import THICKNESS_PLACES as STRAP_T_PLACES
from pinion_cam_geometry import CAM_LEN
from pinion_lever_geometry import BORE_DEPTH as LEVER_BORE_DEPTH
from pinion_pivot_block_geometry import (
    BLOCK_DEPTH,
    BLOCK_DEPTH_BAND as BLOCK_DEPTH_BAND,
    BLOCK_DEPTH_PLACES,
)
from pinion_spring_geometry import WIDTH as SPRING_W

# BACK_STOP_Z, the back block's inner face and the cluster's back stop, is the
# one axial reference.  At fit-up the cluster is pushed hard against it, so the
# back strap, the drum and the front strap close up in front of it and every
# other station below derives from it.  The U28 block put it at 77.75 (its
# outer face at the released machine z 88); the E-a re-size deepened MHA-061
# OUTWARD, leaving the cluster where it was, and RIG_AFT_SHIFT then moved the
# whole rig aft.
#
# RIG_AFT_SHIFT (Main, restricted review of #858): the drum is a 3.0-face
# gear's partner at j = 19, so that gear must keep its FULL face at the worst
# stack.  At the drilling pose the drum's back end stands 0.276 past g19's back
# face.  DRUM_BACK_ADVANCE_STACK below -- the thickest back strap (+0.8), the
# pinned cluster run forward to the front block (widest feeler, 0.35) and the
# drum run forward in its shimmed end play (widest shim, 0.35) -- advances it
# by up to 1.50, so j = 19 engages min(3.0, 1.776 + s) at the worst stack.
# Gear j = 0, at the drum's front end, loses the same s of its 3.25 worst
# slack (DRUM_FRONT_RETREAT_STACK).  On the 0.25 grid, 1.0 still reads 2.776,
# so 1.25 is the smallest shift giving the full face: 0.026 to spare, with j0
# keeping 2.00.  The rig-internal margins do not move with it; every rig-to-
# frame margin the move touches holds (the grip against the crank cluster
# opens, the base rim and base seats keep >= 33 and >= 35, the rocker support
# opens, and the back block overlaps the north pedestal only in z, 19.97 clear
# in x).  build_drive_train_assembly asserts both gears at import.
RIG_AFT_SHIFT = 1.25
RIG_AFT_SHIFT_STEP = 0.25  # the grid the shift is chosen on
BACK_STOP_Z = 77.75 + RIG_AFT_SHIFT + MECHANISM_Z_SHIFT
BACK_BLOCK_Z0 = BACK_STOP_Z
BACK_BLOCK_OUTER_Z = BACK_BLOCK_Z0 + BLOCK_DEPTH

# The rig's one fit-up feeler and its ruled band (Codex #854 P1: MHA-A03
# prints FEELER +/- BAND).  It sets both running clearances below, and the
# worst stacks read its band as each one's set error.
FRONT_BLOCK_FEELER = 0.25
FRONT_BLOCK_FEELER_BAND = 0.10
# The drum turns between the pinned straps, so it needs running clearance:
# the shaft is match-drilled with the feeler as a shim at the drum's FRONT end
# (MHA-062's drilling note), freezing the strap spacing at the drum plus the
# shim.  The drum then runs in DRUM_END_SHIM +/- DRUM_END_SHIM_SET_ERROR of end
# play (pinion_arbor_spec.drum_total_air).
DRUM_END_SHIM = FRONT_BLOCK_FEELER
DRUM_END_SHIM_SET_ERROR = FRONT_BLOCK_FEELER_BAND
# The shaft is set for that drill with its rear end flush with MHA-061's rear
# face.  The SR crown keeps a straightedge off the crown root, so the setting
# carries its own error, printed on the drilling note.
FLUSH_SET_ERROR = 0.10

# MHA-002 drum.  The length is alignment_pinion_spec.FACE_WIDTH (a drawing
# contract this module must not import); a lockstep test pins the two.  It is
# trapped between the straps' inner faces, and at the drilling set-up it sits
# hard on the back strap, so the back stop sets its station (61.55 from the
# MHA-102 head shoulder, ruling (c)'s bond station).
DRUM_LEN = 143.2
DRUM_LEN_PLACES = 1  # FaceWidth prints .X (alignment_pinion_spec)
DRUM_LEN_BAND = printed_band_mm(DRUM_LEN_PLACES)  # 0.8
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
INNER_SPAN = BACK_BLOCK_Z0 - (FRONT_BLOCK_Z0 + BLOCK_DEPTH)  # 161.70
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

# The drum's ends against the cylinder gears at its two ends (RIG_AFT_SHIFT).
# The pose is the drilling set-up: the cluster hard on the back stop and the
# drum hard on the back strap, so the drum's back end can only advance from it
# and its front end can only retreat (the drive train asserts both gears).
DRUM_BACK_ADVANCE_STACK = {
    "MHA-056 back strap thickness .X": _STRAP_T_UPPER,
    "MHA-A03 feeler, widest (the pinned cluster's end play)": FRONT_BLOCK_FEELER
    + FRONT_BLOCK_FEELER_BAND,
    "MHA-A03 feeler, widest (the drum's shimmed end play)": DRUM_END_SHIM
    + DRUM_END_SHIM_SET_ERROR,
}
DRUM_FRONT_RETREAT_STACK = {
    "MHA-056 back strap thickness .X": -printed_deviations(STRAP_T, STRAP_T_PLACES)[0],
    "MHA-002 drum length .X": -printed_deviations(DRUM_LEN, DRUM_LEN_PLACES)[0],
}


def _up_to_tenth(length: float) -> float:
    return math.ceil(length * 10.0 - 1e-6) / 10.0


# The shortest shaft in the longest stack must still bear
# FRONT_BLOCK_MIN_BEARING of the front block's bore.  Set back-flush, the
# shaft's front end reaches past the back block and the inner span into the
# front block; each term below names the dimension that moves it and the part
# that prints it (the W15 stack pattern).
FRONT_BLOCK_MIN_BEARING = 9.5


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


TORQUE_SHAFT_LEN = _up_to_tenth(
    FRONT_BLOCK_MIN_BEARING - sum(torque_shaft_bearing_stack(0.0).values())
)
TORQUE_SHAFT_BEARING_STACK = torque_shaft_bearing_stack(TORQUE_SHAFT_LEN)
if sum(TORQUE_SHAFT_BEARING_STACK.values()) < FRONT_BLOCK_MIN_BEARING - 1e-9:
    raise AssertionError(
        "torque shaft bearing in the front block, worst case: "
        f"{_stack_text(TORQUE_SHAFT_BEARING_STACK)} < {FRONT_BLOCK_MIN_BEARING}"
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
# BLOCK_DEPTH.
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
if sum(TORQUE_SHAFT_BACK_BEARING_STACK.values()) < BACK_BLOCK_MIN_BEARING - 1e-9:
    raise AssertionError(
        "pinned torque shaft bearing in the back block, worst case: "
        f"{_stack_text(TORQUE_SHAFT_BACK_BEARING_STACK)} < {BACK_BLOCK_MIN_BEARING}"
    )

# The rod floats north until the back MHA-104 collar lands on the back block;
# the MHA-059 lever hub must never be that stop.  The back collar is set to its
# follower pin (plane BACK_CAM_PIN_STATION from its front face, by eye to
# BACK_CAM_SET_ERR) with the cluster hard back, so its gap to the block peaks
# at the thickest back strap.  The hub bottoms the rod in its bore, so the rod
# must stand LEVER_SEAT_MIN -- the bore, that gap and a margin -- proud of the
# front block's outer face even for the shortest rod in the longest stack.
BACK_CAM_PIN_STATION = 6.0
BACK_CAM_SET_ERR = 0.5
HUB_STOP_MARGIN = 0.25
BACK_COLLAR_GAP_MAX = (
    (STRAP_T + STRAP_T_BAND) / 2.0 - (CAM_LEN - BACK_CAM_PIN_STATION) + BACK_CAM_SET_ERR
)  # 2.4
LEVER_SEAT_MIN = LEVER_BORE_DEPTH + BACK_COLLAR_GAP_MAX + HUB_STOP_MARGIN  # 10.65


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


LIFT_ROD_LEN = _up_to_tenth(LEVER_SEAT_MIN - sum(lift_rod_seat_stack(0.0).values()))
LIFT_ROD_SEAT_STACK = lift_rod_seat_stack(LIFT_ROD_LEN)
if sum(LIFT_ROD_SEAT_STACK.values()) < LEVER_SEAT_MIN - 1e-9:
    raise AssertionError(
        "lift rod seat past the front block, worst case: "
        f"{_stack_text(LIFT_ROD_SEAT_STACK)} < {LEVER_SEAT_MIN}"
    )
# The nominal rod standing proud of the front block, as built.
LEVER_SEAT_PROUD = LIFT_ROD_LEN - 2.0 * BLOCK_DEPTH - INNER_SPAN  # 15.10
LIFT_ROD_Z0 = BACK_BLOCK_OUTER_Z - LIFT_ROD_LEN

# MHA-114 return spring: the blade rides the back strap's flank.  The inset
# from the strap's inner face keeps the whole 4.0-wide blade on the flank at
# every split of P and every strap thickness in its .X band (the worst case is
# the thinnest strap hard back: inner face 0.8 aft of the nominal one), which
# the support-layout gate proves.
SPRING_BLADE_INSET = 1.0
SPRING_Z = STRAP_Z_INNER[1] + SPRING_BLADE_INSET + SPRING_W / 2.0
