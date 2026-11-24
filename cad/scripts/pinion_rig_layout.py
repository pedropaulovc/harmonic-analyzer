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
The same ruling moved the drum's bond station 0.3 aft on the MHA-DT-22 arbor
(drum front end 61.55 from the head shoulder), so j = 19 reads full face at
nominal; RIG_AFT_SHIFT then moved the whole rig aft so it reads full face at
the worst stack too.

Option E-a pins both straps to the torque shaft, so the fit-up has two
running clearances, each set on any one leaf of a printed range (owner ruling
2026-11-24, fit audit part 2 C7).  The strap / shaft / strap group slides
between the blocks by the front-block gap, P.  The drum, bonded on MHA-DT-22,
turns between the pinned straps in the gap the drum-end leaf left at its front
end when the shaft was match-drilled.  The saved pose IS that drilling set-up (Codex
#854/#858 P1): the back strap hard on the back stop, the drum hard on the back
strap, the feeler at the drum's front end and at the front block, so every
station a part is made or drilled at -- base seats, strap cross holes, shaft
holes -- is the station the assembly shows.  The worst-case gates sweep both
clearances (``test_drive_train_support_layout``).
"""

from __future__ import annotations

import math

import _config
import dt_feeler_leaves as _leaves
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm, printed_deviations
from _title_block_units import LENGTH_UNITS
from _cone_axis_constants import MECHANISM_Z_SHIFT
from cylinder_bank_layout import (
    G0_FRONT_SOUTH_STACK as _BANK_G0_FRONT_SOUTH_STACK,
    G19_BACK_FACE_Z,
)
from dt_pinion_bracket_geometry import THICKNESS as STRAP_T
from dt_pinion_bracket_geometry import THICKNESS_PLACES as STRAP_T_PLACES
from dt_pinion_bracket_geometry import UNIT as STRAP_UNIT
from dt_pinion_cam_geometry import CAM_LEN
from dt_pinion_lever_geometry import BORE_DEPTH as LEVER_BORE_DEPTH
from dt_pinion_lever_geometry import BORE_DEPTH_PLACES as LEVER_BORE_DEPTH_PLACES
from dt_pinion_lever_geometry import GRIP_FROM_B_PLACES as LEVER_GRIP_FROM_B_PLACES
from dt_pinion_lever_geometry import HUB_LEN as LEVER_HUB_LEN
from dt_pinion_lever_geometry import ROD_DIA as LEVER_ROD_DIA
from dt_pinion_lever_geometry import ROD_DIA_PLACES as LEVER_ROD_DIA_PLACES
from dt_pinion_lever_geometry import UNIT as LEVER_UNIT
from dt_pinion_lever_geometry import WALL_T as LEVER_WALL_T
from dt_pinion_pivot_block_geometry import (
    BLOCK_DEPTH,
    BLOCK_DEPTH_BAND as BLOCK_DEPTH_BAND,
    BLOCK_DEPTH_PLACES,
    UNIT as BLOCK_UNIT,
)
from dt_pinion_spring_section import PAD_WIDTH as SPRING_PAD_WIDTH
from dt_pinion_spring_section import UNIT as SPRING_UNIT
from dt_pinion_spring_section import WIDTH as SPRING_W
from dt_pinion_spring_section import WIDTH_PLACES as SPRING_W_PLACES

# RIG_MARGIN_SPARE is a coordinator's planning margin (Main, restricted review
# of #858): rig-scope margins stood this much over their floors at the worst
# stack.  The owner's fit-up ranges (C7, below) override it: Main's C7 ruling
# of 2026-11-24.  The rows those ranges size keep their floors only -- j = 19's
# full face, the drum's end play, the spring pad's air and the lift rod's
# seat (build_dt_drive_train_assembly.OWNER_RANGED_RIG_MARGINS); the margins
# no range sets still keep this spare.
RIG_MARGIN_SPARE = 0.25

# Owner ruling 2026-11-24, fit audit part 2 C7 ("Yes: ranges, longer flats,
# no leaf miking."), with P2 ("one feeler leaf as a single limit"): each rig
# fit-up gap is set on ANY ONE LEAF of a printed range of the inch feeler
# gauge the shop owns (dt_feeler_leaves; owner ruling 2026-11-23, #3042), D
# (19A) on two leaves or a 1/16 drill shank.  A set gap is then the leaf, or
# the pair, within each leaf's own tolerance: the 0.10 feel band booked over
# it (an agent's, #858) and PR #3478's micrometer check of each leaf are gone.
# The model keeps one nominal leaf inside each range, so no station moves;
# every worst stack books the range's ends.
FEELER_LEAF_STEP = _leaves.LEAF_STEP
SMALL_LEAF_RANGE = (_leaves.thousandths(10), _leaves.thousandths(20))  # 16B, 19, 21C
LARGE_LEAF_RANGE = (_leaves.thousandths(20), _leaves.thousandths(40))  # 19B, 21D
RIG_SET_D_RANGE = (_leaves.thousandths(49), _leaves.thousandths(65))  # 19A
RIG_SET_D_SHANK = 25.4 / 16.0  # the 1/16 drill shank 19A also takes
if not RIG_SET_D_RANGE[0] <= RIG_SET_D_SHANK <= RIG_SET_D_RANGE[1]:
    raise AssertionError("the 1/16 drill shank is outside D's leaf range")


def leaf_gap(leaf_range: tuple[float, float], leaves: int = 1) -> tuple[float, float]:
    """The (least, widest) gap a setting on any leaf of ``leaf_range`` leaves:
    the range's ends, each widened by the tolerance of the ``leaves`` it takes."""
    error = leaves * _leaves.LEAF_TOLERANCE
    return (leaf_range[0] - error, leaf_range[1] + error)


def _check_nominal(name: str, nominal: float, leaf_range: tuple[float, float]) -> None:
    if not leaf_range[0] - 1e-9 <= nominal <= leaf_range[1] + 1e-9:
        raise AssertionError(f"the model's {name} {nominal} mm is outside its range")


# The front block is set off the front strap on a SMALL_LEAF_RANGE leaf (Codex
# #854 P1): the pinned cluster's end play.  The model stands it on .010.
FRONT_BLOCK_FEELER = _leaves.thousandths(10)
FRONT_BLOCK_GAP = leaf_gap(SMALL_LEAF_RANGE)
_check_nominal("front block feeler", FRONT_BLOCK_FEELER, SMALL_LEAF_RANGE)
# The drum turns between the pinned straps, so it needs running clearance:
# the shaft is match-drilled with a leaf as a shim at the drum's FRONT end
# (MHA-DT-00's SHAFT DRILL SET), freezing the strap spacing at the drum plus the
# shim.  The drum then runs in DRUM_END_GAP of end play
# (dt_pinion_arbor_geometry.drum_total_air), its least keeping the drum's
# MIN_END_PLAY.  The model's shim is .019 (#858's sizing, kept so no station
# moves).
DRUM_MIN_END_PLAY = 0.1  # dt_pinion_arbor_geometry.MIN_END_PLAY, by lockstep
DRUM_END_SHIM = _leaves.thousandths(19)
DRUM_END_GAP = leaf_gap(SMALL_LEAF_RANGE)
_check_nominal("drum end shim", DRUM_END_SHIM, SMALL_LEAF_RANGE)
if DRUM_END_GAP[0] < DRUM_MIN_END_PLAY:
    raise AssertionError("the drum end range's least gap binds the drum")
# The shaft is set for that drill with its rear end flush with MHA-DT-18's rear
# face.  The SR crown keeps a straightedge off the crown root, so the setting
# carries its own error, printed on that step.
FLUSH_SET_ERROR = 0.10


# MHA-DT-01 drum.  The length is dt_alignment_pinion_spec.FACE_WIDTH (a drawing
# contract this module must not import); a lockstep test pins the two.  It is
# trapped between the straps' inner faces, and at the drilling set-up it sits
# hard on the back strap, so the back stop sets its station (61.55 from the
# MHA-DT-22 head shoulder, ruling (c)'s bond station).
# #1038 re-pitch: the former 5.64 in plus 19 x 0.5635 is 6.0615 in, so 6.06
# keeps the j = 0 slack (J0_SLACK_WORST 3.367, was 3.405); 5.93 in is the
# shortest drum that still covers g0 at its printed limits.
DRUM_LEN = 153.924  # 6.06 in
DRUM_LEN_PLACES = 2  # FaceWidth prints .XX (dt_alignment_pinion_spec)
DRUM_LEN_UNIT = "in"  # dt_alignment_pinion_spec.UNIT, by the same lockstep
DRUM_LEN_BAND = printed_band_mm(DRUM_LEN_PLACES, unit=DRUM_LEN_UNIT)  # .01 in

# The rig's axial datum (user ruling, 2026-09-25, P1-2): the base seats are
# transferred from the blocks, so nothing in the frame fixes the rig along z
# until the fitter sets it. With the cluster hard back and the drum hard on
# the back strap, the drum's back end is set RIG_SET_LEAF_D off the ACTUAL
# gear 19 north face, only then spotting the block seats. The cylinder bank
# is spring-preloaded south (user ruling 2026-10-20); its accepted stack may
# move g19, but the feeler setting follows it, so neither that absolute
# position nor the south strap/disc chain reaches this relative budget.
# From the set-up the drum's back end can only advance: the pinned cluster
# runs forward to the front block, the drum forward in its shimmed end play,
# and D may be any setting of its range.  Gear 19 keeps its full face at the
# thinnest D and the widest plays (the owner's ranges, C7).
# At the front, g0's tooth-front face relative to the ACTUAL g19 still
# carries gears 1-19 and gear 0's face width. These relative terms do not
# change when the bank's hard datum reverses, and are booked once.
# The rig itself cannot sit north of its set (cluster hard back, drum hard on
# the back strap) beyond D's thickest setting, which DRUM_FRONT_RETREAT_STACK
# books; its float south is DRUM_BACK_ADVANCE_STACK at j = 19 and
# grows the drum's overhang at j = 0.
# G19_BACK_FACE_Z is the nominal configured-grid end face, not a hard datum.
# At fit-up every rig station and transferred seat follows its ACTUAL face.
_DRUM_BACK_ADVANCE_PLAY = {
    "MHA-DT-00 front block gap, widest (cluster end play)": FRONT_BLOCK_GAP[1],
    "MHA-DT-00 drum end gap, widest (the drum's shimmed end play)": DRUM_END_GAP[1],
}
# D stands on RIG_SET_D_RANGE (two leaves or the 1/16 shank).  The model sets
# it on .053, the .028 and .025 leaves (#858's sizing, kept so no station
# moves).
RIG_SET_LEAF_D = _leaves.thousandths(53)
RIG_SET_LEAVES = _leaves.leaf_stack(RIG_SET_LEAF_D)
RIG_SET_D_GAP = leaf_gap(RIG_SET_D_RANGE, 2)
_check_nominal("rig-set D", RIG_SET_LEAF_D, RIG_SET_D_RANGE)
if RIG_SET_D_GAP[0] < sum(_DRUM_BACK_ADVANCE_PLAY.values()):
    raise AssertionError(
        "at the thinnest D the drum's back end passes gear 19's back face"
    )
DRUM_BACK_ADVANCE_STACK = {
    **_DRUM_BACK_ADVANCE_PLAY,
    "rig-set D, thinnest setting": RIG_SET_LEAF_D - RIG_SET_D_GAP[0],
}
DRUM_BACK_ADVANCE_OPEN_TERMS: tuple[str, ...] = ()  # bank held south; set follows actual g19
DRUM_FRONT_RETREAT_STACK = {
    "MHA-DT-01 drum length .XX": -printed_deviations(
        DRUM_LEN, DRUM_LEN_PLACES, unit=DRUM_LEN_UNIT
    )[0],
    "rig-set D, thickest setting": RIG_SET_D_GAP[1] - RIG_SET_LEAF_D,
}
# g0's front face south of the rig's g19-based set: gears 1-19 long inside
# the L20 acceptance and gear 0's face width at +0.05. These are relative
# gear-to-gear terms, independent of which end preloads onto a hard datum.
G0_FRONT_SOUTH_STACK = {
    f"MHA-DT-12 {name}": value for name, value in _BANK_G0_FRONT_SOUTH_STACK.items()
}
DRUM_FRONT_RETREAT_OPEN_TERMS: tuple[str, ...] = ()  # booked in G0_FRONT_SOUTH_STACK
BACK_STOP_Z = G19_BACK_FACE_Z + RIG_SET_LEAF_D + STRAP_T
# BACK_STOP_Z, the back block's inner face, is where every station below
# derives from.  The U28 block put it at 77.75 (its outer face at the
# released machine z 88.0, 10.25 deep); the E-a re-size deepened MHA-DT-18
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
# band -- the straps' .XX and the drum's own row, the shim's and the
# feeler's ruled band -- and each block adds its own .XX depth.  The stacks
# below carry every term by name; nothing sums them into one symmetric band.
# The torque shaft and the lift rod are set back-flush, so those terms land
# at their front ends and size both lengths.

# Torque shaft and lift rod: back ends flush with the back block's outer face,
# both printed at .XX (#290: the stacks read them, so never .X) and rounded UP
# to that grid.  The two sheets share one unit.
LENGTH_UNIT = drawing_unit("parts/dt-pinion-lift-rod", _config.parts("dt-pinion-lift-rod"))
if LENGTH_UNIT != drawing_unit(
    "parts/dt-pinion-pivot-shaft", _config.parts("dt-pinion-pivot-shaft")
):
    raise AssertionError("the torque shaft and lift rod sheets print different units")
LENGTH_PLACES = 2
LENGTH_BAND = printed_band_mm(LENGTH_PLACES, unit=LENGTH_UNIT)  # .01 in
_LENGTH_STEP = LENGTH_UNITS[LENGTH_UNIT] / 10**LENGTH_PLACES

# Each term reads the deviation the part's sheet PRINTS (_printed_tolerance):
# the thickest strap, the longest drum and the deepest block lengthen the stack.
_STRAP_T_UPPER = printed_deviations(STRAP_T, STRAP_T_PLACES, unit=STRAP_UNIT)[1]
_DRUM_LEN_UPPER = printed_deviations(DRUM_LEN, DRUM_LEN_PLACES, unit=DRUM_LEN_UNIT)[1]
_BLOCK_DEPTH_UPPER = printed_deviations(BLOCK_DEPTH, BLOCK_DEPTH_PLACES, unit=BLOCK_UNIT)[1]


def _up_to_grid(length: float) -> float:
    """``length`` rounded UP to the shaft and rod sheets' printed grid."""
    return round(math.ceil(length / _LENGTH_STEP - 1e-6) * _LENGTH_STEP, 9)


# The shortest shaft in the longest stack must still bear
# FRONT_BLOCK_MIN_BEARING of the front block's bore (drawing-guidelines.md rule 18 (thread engagement)'s 1.5 D on the
# 1/4 in shaft), and BLOCK_BEARING_MARGIN more (Main, #858: rounding the
# length to its printed place had left 0.09).  Set back-flush, the shaft's front
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
        "MHA-DT-19 shaft length .XX": printed_deviations(
            shaft_len, LENGTH_PLACES, unit=LENGTH_UNIT
        )[0],
        "MHA-DT-18 back block depth .XX": -_BLOCK_DEPTH_UPPER,
        "MHA-DT-14 strap thickness .XX (2 straps)": -2.0 * _STRAP_T_UPPER,
        "MHA-DT-01 drum length .XX": -_DRUM_LEN_UPPER,
        "MHA-DT-00 front block gap, widest over the model's": -(
            FRONT_BLOCK_GAP[1] - FRONT_BLOCK_FEELER
        ),
        "MHA-DT-19 drum end gap, widest over the model's shim": -(
            DRUM_END_GAP[1] - DRUM_END_SHIM
        ),
        "MHA-DT-19 rear end flush set": -FLUSH_SET_ERROR,
    }


def _stack_text(stack: dict[str, float]) -> str:
    terms = ", ".join(f"{name} {value:+.3f}" for name, value in stack.items())
    return f"{terms} = {sum(stack.values()):.3f}"


_FRONT_BEARING_REQUIRED = FRONT_BLOCK_MIN_BEARING + BLOCK_BEARING_MARGIN
TORQUE_SHAFT_LEN = _up_to_grid(
    _FRONT_BEARING_REQUIRED - sum(torque_shaft_bearing_stack(0.0).values())
)
TORQUE_SHAFT_BEARING_STACK = torque_shaft_bearing_stack(TORQUE_SHAFT_LEN)
if sum(TORQUE_SHAFT_BEARING_STACK.values()) < _FRONT_BEARING_REQUIRED - 1e-9:
    raise AssertionError(
        "torque shaft bearing in the front block, worst case: "
        f"{_stack_text(TORQUE_SHAFT_BEARING_STACK)} < {_FRONT_BEARING_REQUIRED}"
    )
TORQUE_SHAFT_Z0 = BACK_BLOCK_OUTER_Z - TORQUE_SHAFT_LEN

# Option E-a (dt_vn_pinion_strap_pin_spec): MHA-DT-19's two set-pin holes are
# match-drilled through the MHA-DT-14 cross holes at the fit-up stack, so they
# sit at the strap mid-planes, measured from the shaft's front end (local z 0).
# Computed here, beside the stations they come from, so the drive train reads
# them without importing the shaft's drawing contract (restricted review).
STRAP_MID_Z = tuple(
    (outer + inner) / 2.0 for outer, inner in zip(STRAP_Z_OUTER, STRAP_Z_INNER)
)  # (front, back)
TORQUE_SHAFT_PIN_HOLE_Z = tuple(z - TORQUE_SHAFT_Z0 for z in STRAP_MID_Z)

# Option E-a (dt_vn_pinion_strap_pin_spec): pinned to the straps, the shaft rides the
# cluster's end play.  Match-drilled flush with the back block's outer face at
# the back stop, it retreats up to the widest feeler setting into the back
# block when the cluster runs forward to the front block, so the shallowest
# printed back block must still give it the front block's floor (drawing-guidelines.md rule 17 (walls and webs)'s
# 1.5 D on the 1/4 in shaft).  Geometry, not a tighter band, carries it:
# BLOCK_DEPTH, with BLOCK_BEARING_MARGIN over that floor (Main, #858: the
# 10.5 block left 0.04 once the flush setting was booked).
BACK_BLOCK_MIN_BEARING = FRONT_BLOCK_MIN_BEARING


def torque_shaft_back_bearing_stack() -> dict[str, float]:
    """Worst-case engagement of the pinned torque shaft in the back block."""
    return {
        "MHA-DT-18 back block depth": BLOCK_DEPTH,
        "MHA-DT-18 back block depth .XX": printed_deviations(
            BLOCK_DEPTH, BLOCK_DEPTH_PLACES, unit=BLOCK_UNIT
        )[0],
        "MHA-DT-00 front block gap, widest (E-a shaft end play)": -FRONT_BLOCK_GAP[1],
        "MHA-DT-19 rear end flush set": -FLUSH_SET_ERROR,
    }


TORQUE_SHAFT_BACK_BEARING_STACK = torque_shaft_back_bearing_stack()
_BACK_BEARING_REQUIRED = BACK_BLOCK_MIN_BEARING + BLOCK_BEARING_MARGIN
if sum(TORQUE_SHAFT_BACK_BEARING_STACK.values()) < _BACK_BEARING_REQUIRED - 1e-9:
    raise AssertionError(
        "pinned torque shaft bearing in the back block, worst case: "
        f"{_stack_text(TORQUE_SHAFT_BACK_BEARING_STACK)} < {_BACK_BEARING_REQUIRED}"
    )

# The rod floats north until the back MHA-DT-23 collar lands on the back block;
# the MHA-DT-16 lever hub must never be that stop.  User ruling (2026-09-25,
# P1-1): the back collar's back face is set off the back block's inner face on
# a leaf, mirroring the front collar's against the front block; owner ruling
# C7 makes that any leaf of LARGE_LEAF_RANGE.  Its gap is then the leaf alone
# -- no collar length, strap thickness or by-eye term -- and the follower pin
# rides wherever that puts it (BACK_CAM_PIN_STATION, from the collar's front
# face, on the model's .035 leaf).
# Main's C7 ruling (2026-11-24) replaced the agent floor BACK_COLLAR_MIN_GAP
# (0.5, #858: "the collar never lands on the block but as the stop") with what
# the gap is for.  At zero the back collar's back face bears on the back
# MHA-DT-18's inner face at the set pose: that is the rod's north stop, which
# binds nothing while the rod can still run south off it.  MHA-DT-17 binds
# only when both collars bear on their blocks at once, its end play between
# them closed.  Nothing moves either gap after the setting (each leaf is set
# against its own block, so neither the rod's rim-flush pose nor the
# cluster's end play enters), so the check is the least end play the two
# ranges leave, after the setting.
HUB_STOP_MARGIN = 0.25
BACK_COLLAR_LEAF_F = _leaves.thousandths(35)
BACK_COLLAR_GAP = leaf_gap(LARGE_LEAF_RANGE)
_check_nominal("back collar leaf F", BACK_COLLAR_LEAF_F, LARGE_LEAF_RANGE)
# The front collar is flush with the front strap's outer face in the model,
# on the front block's own leaf (ruling (c)); it is set on SMALL_LEAF_RANGE.
FRONT_CAM_GAP = leaf_gap(SMALL_LEAF_RANGE)
LIFT_ROD_END_PLAY_MIN = FRONT_CAM_GAP[0] + BACK_COLLAR_GAP[0]
if LIFT_ROD_END_PLAY_MIN <= 0.0:
    raise AssertionError("MHA-DT-17 is clamped between its cams")
_STRAP_T_LOWER = printed_deviations(STRAP_T, STRAP_T_PLACES, unit=STRAP_UNIT)[0]
BACK_CAM_PIN_STATION = CAM_LEN + BACK_COLLAR_LEAF_F - STRAP_T / 2.0  # 5.404
# The deepest printed MHA-DT-16 bore seats the hub furthest onto the rod, so
# the seat requirement books the bore's upper .XX deviation (Codjiflo on #2106).
_LEVER_BORE_DEPTH_UPPER = printed_deviations(
    LEVER_BORE_DEPTH, LEVER_BORE_DEPTH_PLACES, unit=LEVER_UNIT
)[1]
LEVER_SEAT_MIN = (
    LEVER_BORE_DEPTH + _LEVER_BORE_DEPTH_UPPER + BACK_COLLAR_GAP[1] + HUB_STOP_MARGIN
)  # 9.661


def lift_rod_seat_stack(rod_len: float) -> dict[str, float]:
    """Worst-case length of lift rod standing proud of the front block."""
    return {
        "nominal (rod - both blocks - inner span)": rod_len
        - 2.0 * BLOCK_DEPTH
        - INNER_SPAN,
        "MHA-DT-17 rod length .XX": printed_deviations(
            rod_len, LENGTH_PLACES, unit=LENGTH_UNIT
        )[0],
        "MHA-DT-18 block depth .XX (2 blocks)": -2.0 * _BLOCK_DEPTH_UPPER,
        "MHA-DT-14 strap thickness .XX (2 straps)": -2.0 * _STRAP_T_UPPER,
        "MHA-DT-01 drum length .XX": -_DRUM_LEN_UPPER,
        "MHA-DT-00 front block gap, widest over the model's": -(
            FRONT_BLOCK_GAP[1] - FRONT_BLOCK_FEELER
        ),
        "MHA-DT-19 drum end gap, widest over the model's shim": -(
            DRUM_END_GAP[1] - DRUM_END_SHIM
        ),
    }


# The MHA-DT-16 lever rides the rod's front end, just south of the torque
# shaft's front end, so a SHORT rod pulls the lever's throw plane toward it.
# The grip arm's axis sits GripFromB from the hub's mouth face B, which sits
# BoreDepth from the floor the rod seats on, and the arm is RodDia across
# (dt_pinion_lever_geometry); the drive train pins this nominal to its pose.
LEVER_THROW_MIN_AIR = 0.25
# Lever throw plane north face, measured from the rod's front end.
LEVER_PLANE_NORTH_FROM_ROD_END = (
    LEVER_HUB_LEN / 2.0 - LEVER_WALL_T + LEVER_ROD_DIA / 2.0
)


def _lever_arm_stack(direction: str) -> dict[str, float]:
    """The grip arm's own printed bands, toward ``direction``."""
    bore = printed_deviations(LEVER_BORE_DEPTH, LEVER_BORE_DEPTH_PLACES, unit=LEVER_UNIT)
    grip = printed_deviations(
        LEVER_HUB_LEN / 2.0, LEVER_GRIP_FROM_B_PLACES, unit=LEVER_UNIT
    )
    arm = printed_deviations(LEVER_ROD_DIA, LEVER_ROD_DIA_PLACES, unit=LEVER_UNIT)
    return {
        "MHA-DT-16 bore depth .XX": -bore[0] if direction == "south" else bore[1],
        "MHA-DT-16 grip from face B .XX": grip[1] if direction == "south" else -grip[0],
        "MHA-DT-16 arm dia .XX, half": arm[1] / 2.0,
    }


def lever_north_travel_stack(rod_len: float) -> dict[str, float]:
    """Worst-case travel of the lever's throw plane north of the pose."""
    return {
        "MHA-DT-17 rod length .XX (shortest)": -printed_deviations(
            rod_len, LENGTH_PLACES, unit=LENGTH_UNIT
        )[0],
        "MHA-DT-17 floated north to the back collar": BACK_COLLAR_GAP[1],
        **_lever_arm_stack("north"),
    }


def lever_south_travel_stack(rod_len: float) -> dict[str, float]:
    """Worst-case travel of the lever's throw plane south of the pose."""
    return {
        "MHA-DT-17 rod length .XX (longest)": printed_deviations(
            rod_len, LENGTH_PLACES, unit=LENGTH_UNIT
        )[1],
        "MHA-DT-17 floated south to the front collar (widest leaf)": FRONT_CAM_GAP[1],
        **_lever_arm_stack("south"),
    }


SHAFT_FRONT_SOUTH_TRAVEL_STACK = {
    "MHA-DT-19 length .XX (longest)": printed_deviations(
        TORQUE_SHAFT_LEN, LENGTH_PLACES, unit=LENGTH_UNIT
    )[1],
    "MHA-DT-00 front block gap, widest (cluster runs forward)": FRONT_BLOCK_GAP[1],
    "MHA-DT-19 rear end flush set": FLUSH_SET_ERROR,
}


def lever_to_shaft_front_worst(rod_len: float) -> float:
    """Worst-case air from the lever's throw plane to the shaft's front end."""
    nominal = rod_len - TORQUE_SHAFT_LEN - LEVER_PLANE_NORTH_FROM_ROD_END
    return (
        nominal
        - sum(lever_north_travel_stack(rod_len).values())
        - sum(SHAFT_FRONT_SOUTH_TRAVEL_STACK.values())
    )


# MHA-DT-17 is the longer of two requirements, each at its worst stack: the
# rod standing LEVER_SEAT_MIN proud of the front block, and the lever's throw
# plane clearing the torque shaft's front end with RIG_MARGIN_SPARE (the leaf
# F shortened the seat requirement by 1.6, and the lever then crowded the
# shaft to 0.14 -- Main, restricted review of #858).  The seat's spare went
# with the owner's ranges (C7): the widest back collar gap is the range's, and
# LEVER_SEAT_MIN already holds HUB_STOP_MARGIN over the hub's stop.
_LEVER_SEAT_REQUIRED = LEVER_SEAT_MIN
_LEVER_AIR_REQUIRED = LEVER_THROW_MIN_AIR + RIG_MARGIN_SPARE
LIFT_ROD_LEN = _up_to_grid(
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
LEVER_SEAT_PROUD = LIFT_ROD_LEN - 2.0 * BLOCK_DEPTH - INNER_SPAN  # 12.31
LIFT_ROD_Z0 = BACK_BLOCK_OUTER_Z - LIFT_ROD_LEN

# MHA-DT-24 return spring: the blade rides the back strap's flank, and its foot
# pad lies on the base east of the back block.  Main (restricted review of
# #858): the pad is set off the back block's inner face on a leaf before its
# seat is transferred, so the spring is stationed from the block, not from
# the strap; owner ruling C7 makes that any leaf of LARGE_LEAF_RANGE.  #859
# option (iv) (Main, 2026-09-26): the pad is flush with the strip's AFT edge
# and widens forward only, so the edge the leaf sets is the strip's own and
# neither width band moves it; centred on the pad, the strip's front edge had
# stood off the flank at every leaf.  The foot lies wholly east of the block's
# east end, so the leaf stands on edge against the block's inner face and
# overhangs that end to meet the pad (pinion_rig_fitup).  At the worst setting
# a thin strap (inner face 0.8 aft), the range's thickest leaf and the widest
# strip all move the blade's front edge onto less flank; the thinnest leaf
# brings the pad nearest the block.  The model sets it on .026.
SPRING_PAD_MIN_AIR = 0.25
SPRING_PAD_LEAF = _leaves.thousandths(26)
SPRING_PAD_GAP = leaf_gap(LARGE_LEAF_RANGE)
_check_nominal("spring pad leaf", SPRING_PAD_LEAF, LARGE_LEAF_RANGE)
SPRING_PAD_AFT_Z = BACK_BLOCK_Z0 - SPRING_PAD_LEAF  # the pad's and the strip's
SPRING_Z = SPRING_PAD_AFT_Z - SPRING_W / 2.0  # the strip's mid-plane
SPRING_PAD_Z = SPRING_PAD_AFT_Z - SPRING_PAD_WIDTH / 2.0  # the pad's, its screw's
SPRING_BLADE_INSET = SPRING_Z - SPRING_W / 2.0 - STRAP_Z_INNER[1]
SPRING_BLADE_MIN_ON_FLANK = 0.1
SPRING_BLADE_ON_FLANK_WORST = (
    SPRING_BLADE_INSET
    + _STRAP_T_LOWER
    - (SPRING_PAD_GAP[1] - SPRING_PAD_LEAF)
    - printed_deviations(SPRING_W, SPRING_W_PLACES, unit=SPRING_UNIT)[1]
)
SPRING_PAD_TO_BLOCK_WORST = SPRING_PAD_GAP[0]  # 0.495
# The model's single-leaf settings are each one leaf of the set.
for _name, _setting in (
    ("front block feeler", FRONT_BLOCK_FEELER),
    ("drum end shim", DRUM_END_SHIM),
    ("back collar leaf F", BACK_COLLAR_LEAF_F),
    ("spring pad leaf", SPRING_PAD_LEAF),
):
    if len(_leaves.leaf_stack(_setting)) != 1:
        raise AssertionError(f"the {_name} is not one leaf of the set")
# The blade's flank keeps the planning spare; the pad's air is the owner's
# range (C7) and keeps its floor.
if SPRING_BLADE_ON_FLANK_WORST < SPRING_BLADE_MIN_ON_FLANK + RIG_MARGIN_SPARE - 1e-9:
    raise AssertionError(
        f"spring blade on the back strap flank, worst case {SPRING_BLADE_ON_FLANK_WORST:.3f}"
        f" < {SPRING_BLADE_MIN_ON_FLANK} + {RIG_MARGIN_SPARE}"
    )
if SPRING_PAD_TO_BLOCK_WORST < SPRING_PAD_MIN_AIR - 1e-9:
    raise AssertionError(
        f"spring foot pad to the back block, worst case {SPRING_PAD_TO_BLOCK_WORST:.3f}"
        f" < {SPRING_PAD_MIN_AIR}"
    )
