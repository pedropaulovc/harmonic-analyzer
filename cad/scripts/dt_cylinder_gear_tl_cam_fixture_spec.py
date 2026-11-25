r"""Pure-data contract for the cylinder gears' cam turning fixture (MHA-DT-12-TL-01).

Shop tooling, not a machine part (cad/docs/subsystem-identities.md), issue
#2361. Each of the 20 MHA-DT-12 cylinder gears carries an integral eccentric
cam whose throw is the channel's gain and whose lobe direction, read against
the alignment notch, is the channel's phase. The gear's bore is reamed, its
120 teeth and the notch are cut concentric on an arbor first; the cam is
turned last, on this fixture, so throw and cam-to-notch phase are set once in
the fixture and repeat over 20 gears without indicating each one.

The fixture is one made part, a round steel body gripped in the lathe's
4-jaw, its turned register (the OD) indicated true, then the throw SET by the
two jaws in line with the stub until a wrung gauge-block stack of twice the
gear's throw (``THROW_STACK``) fills the gap the stub leaves a zeroed test
indicator in half a turn, and left in the chuck
for all 20 gears. Its front face carries, all bought
(``dt_cylinder_gear_tl_vn_cam_*``, the MHA-DT-12-TL-00 kit):

* the stub, a 3/8 pull-out dowel pressed in a reamed hole set off the
  register axis by the cam throw: the gear's Ø.3760 bore slides on it;
* the clock pin, a class Z minus gauge pin cut short and pressed in a reamed
  hole so it stands in ONE tooth space of the gear, the notched space itself
  (the .016 notch kerf is too narrow for a pin; the pin locates on the two
  flanks of the tooth space the kerf is sawn into);
* the clamp, one 10-32 socket head screw and a #10 washer: the screw threads
  into the dowel's tapped end and the washer bears on the gear's cam face
  inside the cam circle.

Why one centre clamp, not screws on the disc face: the turning tool runs the
cam OD down to the disc face, so in front of the disc face it sweeps every
point farther from the lathe axis than the cam radius, and the exposed disc
face is all farther than that. Nothing may bear there. The washer and screw
head stay inside the cam circle (``TOOL_SWEEP_MARGIN``). Cutting torque turns
the gear clockwise seen from the tailstock about the stub, for every
position of the cut (``CUT_TURNS_GEAR_CLOCKWISE``); the fitter turns the gear
clockwise onto the pin before tightening, so the cut seats it (TL-00 steps).

Body material: low-carbon steel, not 6061. The clamp screw's preload pulls
on the pressed dowel; steel grips the dowel about three times harder than
aluminium at the same interference, wears the small pin hole less and keeps
the register round in the jaws. The body still weighs under 3 lb.

Frame (the SolidWorks model): the register axis, which is the lathe axis
once indicated, is model Z through the origin. The back face (Z0) faces the
chuck; the front face (Z = THICKNESS) seats the gear's back face. The stub
stands on -Y so the cam lobe points +Y in this frame. The clock pin is
clocked about the stub (the gear's bore axis), counter-clockwise of the +Y
line through it seen from +Z (the tailstock), by ``PIN_PHASE_DEG``: the
gear's lobe-to-notch phase (``dt_cylinder_gear_phase_band.CAM_NOTCH_PHASE_DEG``,
the lobe cut half a pitch clockwise of a crest and the notch half a pitch
counter-clockwise of it, #749) plus the seated half-play
(``SEATED_HALF_PLAY_DEG``), about 3.19 deg, so a gear turned onto the pin
seats its notch on the phase. Every number of the gear is imported from
``dt_cylinder_gear_spec`` and ``dt_cylinder_gear_phase_band``.

Accuracy (this module asserts only what is true). MHA-DT-12 prints throw
.3402 +/-.0020 (owner ruling 2026-11-08, #2144 item 8.2) and cam phase
3.0 +/-.7 deg (``dt_cylinder_gear_phase_band``, band by delegated ruling
2026-11-17 on #2361); every gear is held to that print.

* Throw is set, not cut to a number: a dial test indicator is zeroed on the
  stub where the stub stands nearest it, the chuck is turned half a turn, and
  the jaws in line with the stub are moved until the shop's gauge blocks
  wrung to twice the throw (``THROW_STACK``) read zero within
  ``THROW_READING_BAND`` between the stub and the stylus. The indicator
  reads only near its zero, so its error over travel is not in the throw,
  and the stub hole's station and the register's indication drop out. What
  is left is ``THROW_GAP_TERMS`` (``THROW_SET_MAX_MM``) plus each gear's
  bore floating on the stub (``BORE_FLOAT``); ``THROW_ERROR_MAX_MM`` is
  asserted inside the print.
* Phase is not set by reading: the pin hole and stub hole stations (+/-.002
  each), the register's indication and the jaw pair's line put a fixed error
  of up to ``PHASE_FIXED_WORST_DEG`` (.47 deg) on all 20 gears, and each gear
  adds its bore float and tooth form (``PHASE_PER_PART_WORST_DEG``, .13 deg).
  The gear-to-gear part is asserted inside the error budget's per-channel
  ``cam_phase`` (+/-.25 deg) and the total, ``PHASE_TOTAL_WORST_DEG``
  (.68 deg), inside the print's +/-.7 deg; the common part is a common cam
  phase, which error_budget.yaml records and scores. A reading of
  the phase on the set fixture was weighed and rejected: its baseline is the
  .34 throw, so a .001 reading moves the phase about .17 deg
  (``PHASE_PER_THOU_READING_DEG``). Every gear seats on the same flank of the
  pin (TL-00 step 17), so the pin stands its mean half-play
  (``SEATED_HALF_PLAY_DEG``, .19 deg) counter-clockwise of the phase and a
  nominal fixture's common error is nil.

The hole stations carry the shop table's +/-.002 for a reamed hole from its
datum and nothing tighter: one tool made once, cut to a number.
"""

from __future__ import annotations

import math
from functools import cache

import _config
import dt_cylinder_gear_spec as gear
from dt_cylinder_gear_phase_band import CAM_NOTCH_PHASE_DEG, NOTCH_PHASE_TOLERANCE_DEG
from _fit_ream_h7 import REAM_H7
from _inch_wall_limits import WALL_TARGET_MM
from _mcmaster_23065a503 import (
    CUT_LENGTH as PIN_LENGTH,
    SIZE as PIN_DIA,
    SIZE_BAND_IN as PIN_DIA_BAND_IN,
)
from _mcmaster_91251a337 import DIMS as SCREW, LENGTH_SHORT as SCREW_LENGTH_SHORT
from _mcmaster_92141a011 import (
    ID as WASHER_ID,
    MODEL_THICKNESS as WASHER_MODEL_THICKNESS,
    OD as WASHER_OD,
    THICKNESS_MAX as WASHER_THICKNESS_MAX,
    THICKNESS_MIN as WASHER_THICKNESS_MIN,
)
from _mcmaster_97175a344 import (
    DIA as DOWEL_DIA,
    DIA_BAND_IN as DOWEL_DIA_BAND_IN,
    FULL_THREAD_DEPTH_MIN as DOWEL_THREAD_DEPTH_MIN,
    LENGTH as DOWEL_LENGTH,
    THREAD_MAJOR as DOWEL_THREAD_MAJOR,
)
from _package_units import drawing_unit
from _printed_tolerance import edge_break_chamfer_mm, printed_band_mm

PART_NAME = "dt-cylinder-gear-tl-cam-fixture"
UNIT = drawing_unit(
    "parts/dt-cylinder-gear-tl-cam-fixture",
    _config.parts("dt-cylinder-gear-tl-cam-fixture"),
)
assert UNIT == "in"
INCH = 25.4
PART_NUMBER = str(_config.parts("dt-cylinder-gear-tl-cam-fixture")["number"])
_XX = printed_band_mm(2, unit=UNIT)
_EDGE_BREAK = edge_break_chamfer_mm(unit=UNIT)

# --- The gear, imported ------------------------------------------------------------
THROW = gear.ECCENTRICITY
THROW_TOLERANCE = gear.ECCENTRICITY_TOLERANCE_MM
GEAR_BORE_MIN = gear.BORE_DIA + gear.BORE_DIA_BAND[1]
GEAR_BORE_MAX = gear.BORE_DIA + gear.BORE_DIA_BAND[0]
CAM_RADIUS_MIN = (gear.CAM_DIA + gear.CAM_DIA_BAND[1]) / 2.0
GEAR_THICKNESS_MIN = gear.OVERALL_THICKNESS + gear.OVERALL_THICKNESS_BAND[1]
GEAR_THICKNESS_MAX = gear.OVERALL_THICKNESS + gear.OVERALL_THICKNESS_BAND[0]
FACE_WIDTH_MIN = gear.FACE_WIDTH - gear.FACE_WIDTH_TOLERANCE_MM
GEAR_TIP_RADIUS = gear.OUTSIDE_DIA / 2.0
PHASE_DEG = CAM_NOTCH_PHASE_DEG
# The budget's per-channel (gear-to-gear) phase and the printed NotchPhase band.
PHASE_SCATTER_TOLERANCE_DEG = gear.CAM_PHASE_TOLERANCE_DEG
PHASE_TOLERANCE_DEG = NOTCH_PHASE_TOLERANCE_DEG

# --- Body ----------------------------------------------------------------------------
# The register is the OD: indicated true once, its diameter only has to be
# round, so .XX. It covers the gear's whole swing about the lathe axis, so the
# gear's back face is supported everywhere and no tooth overhangs the body.
BODY_DIA = 3.25 * INCH
THICKNESS = 1.00 * INCH
GEAR_SWING_RADIUS = THROW + GEAR_TIP_RADIUS
if (BODY_DIA - _XX) / 2.0 <= GEAR_SWING_RADIUS:
    raise AssertionError("the gear overhangs the fixture body's register")
# PM-1127: 11 in swing over the bed.
LATHE_SWING = 11.0 * INCH
if BODY_DIA + _XX >= LATHE_SWING / 2.0:
    raise AssertionError("the fixture body is not a small part in the PM-1127")
STEEL_LB_PER_IN3 = 0.284
BODY_WEIGHT_LB = (
    math.pi / 4.0 * (BODY_DIA / INCH) ** 2 * (THICKNESS / INCH) * (STEEL_LB_PER_IN3)
)
if BODY_WEIGHT_LB > 3.0:
    raise AssertionError("the fixture body is heavier than it needs to be")

# --- Stub: the pull-out dowel at the throw ------------------------------------------
# Printed on the .0001 grid at the gear's own printed .3402 (the gear model's
# 8.64 mm prints at four places; the fixture's print IS its model).
POSITION_PLACES = 4
STUB_OFFSET = round(THROW / INCH, POSITION_PLACES) * INCH
# +/- on each hole coordinate from the register axis: the shop table's row for
# a reamed hole up to 6 in from its datum, the narrowest band cut to a number.
POSITION_BAND = 0.002 * INCH
POSITION_DEVIATIONS = (-POSITION_BAND, POSITION_BAND)
# Press ream for the 97175A344 dowel (+.0001/+.0003 over 3/8): the .3740
# (3/8 undersize) reamer, REAM_H7's +.0005/0, so .0006-.0013 interference:
# the least press holds the clamp screw's pull (``STUB_RETENTION_MARGIN``).
STUB_HOLE_DIA = 0.3740 * INCH
STUB_HOLE_DEVIATIONS = REAM_H7[::-1]  # (lower, upper)
HOLE_PLACES = 4
DOWEL_DIA_MIN = DOWEL_DIA + DOWEL_DIA_BAND_IN[0] * INCH
DOWEL_DIA_MAX = DOWEL_DIA + DOWEL_DIA_BAND_IN[1] * INCH
STUB_PRESS_INTERFERENCE = (
    DOWEL_DIA_MIN - (STUB_HOLE_DIA + REAM_H7[0]),
    DOWEL_DIA_MAX - (STUB_HOLE_DIA + REAM_H7[1]),
)
if min(STUB_PRESS_INTERFERENCE) <= 0.0:
    raise AssertionError("the stub dowel loses its press in the .3740 ream")
# The dowel stands this far above the front face (set when pressed, TL-00).
STUB_STAND = 0.24 * INCH
STUB_STAND_BAND = _XX
STUB_PRESS_DEPTH = DOWEL_LENGTH - STUB_STAND
# Gear bore on the stub: (minimum, maximum) diametral clearance.
STUB_CLEARANCE = (GEAR_BORE_MIN - DOWEL_DIA_MAX, GEAR_BORE_MAX - DOWEL_DIA_MIN)
if STUB_CLEARANCE[0] <= 0.0:
    raise AssertionError("the gear's smallest bore does not slide on the stub")
BORE_FLOAT = STUB_CLEARANCE[1] / 2.0  # radial, any direction
if STUB_STAND + STUB_STAND_BAND >= GEAR_THICKNESS_MIN:
    raise AssertionError("the stub stands proud of the gear's cam face")

# The clamp pulls the pressed dowel out of the body. TL-00 has item 5
# tightened snug by hand with the 5/32 hex key held by its SHORT arm, so the
# torque is that arm times a finger force. The short arm of a 5/32 key is
# .750-.938 long (ASME B18.3, Unbrako Socket Products Engineering Guide
# p. 32, https://unbrako.com/docs/engguide.pdf, read 2026-11-14); the finger
# force at its end, 15 lbf, is an ASSUMPTION, not measured. Preload from
# T = K D P with K = .20, as-received steel screw into steel (the same guide,
# p. 62). The press (steel in steel, the least interference, Lamé for a pin
# in a large body) holds that preload.
_STEEL_E_PSI = 30.0e6
_FRICTION = 0.15
KEY_SHORT_ARM_MAX_IN = 0.938
FINGER_FORCE_LBF = 15.0  # assumption
NUT_FACTOR = 0.20
CLAMP_TORQUE_IN_LBF = FINGER_FORCE_LBF * KEY_SHORT_ARM_MAX_IN
CLAMP_PRELOAD_LBF = CLAMP_TORQUE_IN_LBF / (NUT_FACTOR * SCREW.major_dia / INCH)
_PRESS_PSI = (
    _STEEL_E_PSI * (STUB_PRESS_INTERFERENCE[0] / INCH) / (2.0 * DOWEL_DIA / INCH)
)
STUB_RETENTION_LBF = (
    _FRICTION * _PRESS_PSI * math.pi * (DOWEL_DIA / INCH) * (STUB_PRESS_DEPTH / INCH)
)
STUB_RETENTION_MARGIN = STUB_RETENTION_LBF / CLAMP_PRELOAD_LBF
if STUB_RETENTION_MARGIN < 1.5:
    raise AssertionError("the clamp screw can pull the stub out of the body")

# --- Throw: set by the jaws, read on the stub -----------------------------------
# The register's indicated runout (TIR) in the 4-jaw: .001 with a dial test
# indicator (run 20261114T231845023Z's review: .0005 was tighter than the
# shop's runout row). It places the cross axis for phase; along item 2's
# line the jaw pair in line with it then moves item 1 until item 2 stands
# the throw off the lathe axis, so the stub hole's station drops out.
REGISTER_TIR = 0.001 * INCH
REGISTER_OFFSET = REGISTER_TIR / 2.0
# The throw is read as a gap, not as a travel. Item 2 orbits the lathe axis,
# so in half a turn it stands twice the throw farther from an indicator
# zeroed on it at its nearest; the shop's gauge blocks wrung to that length
# (cad/config/shop-equipment/ gauges.gauge-blocks-mitutoyo, the 81-piece
# inch set: .1001-.1009 by .0001, .101-.149 by .001, .050-.950 by .050) must
# bring the indicator back to zero. A 1 in dial indicator swept over the .68
# is not used: its error over that many turns of its hand is not known to
# the shop, and item 2 orbits off its plunger (Codjiflo, #2712).
THROW_STACK_BLOCKS_IN = (0.1004, 0.130, 0.450)
THROW_STACK = sum(THROW_STACK_BLOCKS_IN) * INCH
if abs(THROW_STACK - 2.0 * STUB_OFFSET) > 1e-9:
    raise AssertionError("the gauge-block stack is not twice the printed throw")
# The dial test indicator's division (cad/process/shop.toml gauges.dti: the
# shop's lever indicator, graduation 0.001 mm, range 0.14 mm, owner
# 2026-11-17).
THROW_INDICATOR_DIVISION = 0.001
# The check's band on the gap: .001 in either side of zero.
THROW_READING_BAND = 0.001 * INCH
# Every error in the gap, worst case, each added to the next:
# * band: the check's own window.
# * reading: half a division at the zero and half at the check. Both are
#   read at the same place on the dial, so the indicator's error over its
#   travel and its cosine error are not in the gap.
# * turn-back: the zero is taken where the reading turns back as the chuck
#   is rocked (item 2 nearest), the check where it turns back as the chuck
#   and the stack are rocked (item 2 farthest, stack square). A turn-back is
#   found until the reading no longer moves, half a division; three of them
#   (about 2 deg of chuck each: e(1 - cos 2.2 deg) = .00025).
# * stack: three shop-grade blocks, each within about .00002 (ASME B89.1.9
#   grade AS-2 limit deviation up to 1 in); .00003 a block charged with its
#   wring (an ASSUMPTION: the set's grade certificate is not recorded).
THROW_GAP_TERMS = {
    "band": THROW_READING_BAND,
    "reading": THROW_INDICATOR_DIVISION,
    "turn-back": 3 * THROW_INDICATOR_DIVISION / 2.0,
    "stack": len(THROW_STACK_BLOCKS_IN) * 0.00003 * INCH,
}
THROW_GAP_ERROR_MAX = sum(THROW_GAP_TERMS.values())
THROW_PER_PART_MAX_MM = BORE_FLOAT
# The gap is twice the throw, so half its error is the setting's; the stack
# is twice the printed .3402, .00004 off the model's throw.
THROW_SET_MAX_MM = THROW_GAP_ERROR_MAX / 2.0 + abs(STUB_OFFSET - THROW)
# .00060 gap + .00004 rounding + .00070 float = .00134 in +/-.0020: .00066 left.
THROW_ERROR_MAX_MM = THROW_SET_MAX_MM + THROW_PER_PART_MAX_MM
if THROW_ERROR_MAX_MM > THROW_TOLERANCE:
    raise AssertionError("a gear's throw can leave MHA-DT-12's printed band")
# The jaw pair moves item 1 along its own line; item 2 stands in that line by
# eye, within JAW_LINE_ERROR_DEG (an ASSUMPTION), so the move it needs (the
# stub's station error, the register's offset and the .0001 rounding) puts a
# little of itself across the throw line, a phase term.
JAW_LINE_ERROR_DEG = 5.0
THROW_CORRECTION_MAX = abs(STUB_OFFSET - THROW) + POSITION_BAND + REGISTER_OFFSET
AXIS_LATERAL = REGISTER_OFFSET + THROW_CORRECTION_MAX * math.sin(
    math.radians(JAW_LINE_ERROR_DEG)
)

# --- Clamp: one 10-32 SHCS into the dowel's tap, a #10 washer on the cam face --------
# The screw centres in the dowel's thread; the washer floats on the screw.
_THREAD_FLOAT = 0.002 * INCH  # 10-32 2B/3A pitch-diameter float, radial
_WASHER_FLOAT = (WASHER_ID - SCREW.major_dia) / 2.0
_WASHER_OD_MAX = WASHER_OD + 0.005 * INCH  # commercial washer, no band given
_WASHER_OD_MIN = WASHER_OD - 0.005 * INCH
_STUB_FROM_AXIS_MAX = (THROW_STACK + THROW_GAP_ERROR_MAX) / 2.0
CLAMP_REACH_MAX = (
    _STUB_FROM_AXIS_MAX + _THREAD_FLOAT + _WASHER_FLOAT + _WASHER_OD_MAX / 2.0
)
# The tool turns the cam OD down to the disc face: everything in front of
# the disc face farther from the lathe axis than the smallest cam radius is
# swept. The washer and the 5/16 head stay inside it.
TOOL_SWEEP_MARGIN = CAM_RADIUS_MIN - CLAMP_REACH_MAX
if TOOL_SWEEP_MARGIN <= 0.0:
    raise AssertionError("the clamp washer reaches into the turning tool's sweep")
if SCREW.head_dia >= _WASHER_OD_MIN:
    raise AssertionError("the screw head does not bear on the washer")
# The washer bears on the cam face outside the gear's bore edge break, with
# the washer floated, the gear floated on the stub and the largest bore.
WASHER_BEARING_MIN = (
    _WASHER_OD_MIN / 2.0
    - _WASHER_FLOAT
    - _THREAD_FLOAT
    - BORE_FLOAT
    - GEAR_BORE_MAX / 2.0
    - _EDGE_BREAK
)
if WASHER_BEARING_MIN <= 0.0:
    raise AssertionError("the washer falls into the gear's bore")
# The washer's ring on the brass: the washer's least OD over the largest
# bore and its edge break (off-centre, the ring keeps that area). C360-H02
# yield 17 ksi (OnlineMetals #1500 listing, as
# ch_rocker_arm_tl_oblique_jig_assembly_spec._BRASS_YIELD_MPA). At the
# short-arm grip's preload the margin is about 1.1; the ring yields at
# about 400 lbf, 15 in-lbf on the key (``WASHER_YIELD_TORQUE_IN_LBF``).
BRASS_YIELD_PSI = 17_000.0
WASHER_BEARING_AREA_IN2 = (
    math.pi
    / 4.0
    * ((_WASHER_OD_MIN / INCH) ** 2 - ((GEAR_BORE_MAX + 2.0 * _EDGE_BREAK) / INCH) ** 2)
)
WASHER_BEARING_PSI = CLAMP_PRELOAD_LBF / WASHER_BEARING_AREA_IN2
WASHER_BEARING_MARGIN = BRASS_YIELD_PSI / WASHER_BEARING_PSI
WASHER_YIELD_PRELOAD_LBF = BRASS_YIELD_PSI * WASHER_BEARING_AREA_IN2
WASHER_YIELD_TORQUE_IN_LBF = (
    WASHER_YIELD_PRELOAD_LBF * NUT_FACTOR * SCREW.major_dia / INCH
)
if WASHER_BEARING_MARGIN < 1.0:
    raise AssertionError("the clamp washer yields the gear's brass")
# Overlap of the 5/16 screw with the dowel's thread, from the washer on the
# cam face: never past the .255 full-thread depth (it would jam in the tap's
# lead).
SCREW_ENGAGEMENT_MAX = (
    STUB_STAND + STUB_STAND_BAND - (GEAR_THICKNESS_MIN + WASHER_THICKNESS_MIN)
) + SCREW.length
SCREW_ENGAGEMENT_MIN = (
    STUB_STAND
    - STUB_STAND_BAND
    - (GEAR_THICKNESS_MAX + WASHER_THICKNESS_MAX)
    + SCREW.length
    - SCREW_LENGTH_SHORT
)
if SCREW_ENGAGEMENT_MAX >= DOWEL_THREAD_DEPTH_MIN:
    raise AssertionError("the clamp screw bottoms in the dowel's tap")
# Full thread only (rule 18): the overlap less the screw's chamfered point,
# which runs slightly below the thread root (ASME B18.3, Unbrako guide p. 13),
# one external thread height 0.61343P (ASME B1.1) at 45 deg; and less the
# dowel's tap mouth, taken as a 90 deg countersink to the major diameter, one
# internal thread depth 0.54127P (ASME B1.1; the catalogue gives no mouth
# form, so an ASSUMPTION). The least full thread, .12 (0.63D), is printed
# alone; .12-.21 (0.63D-1.10D) is under rule 18's 1.5D floor, the exception
# MHA-DT-12-TL-00 RV-01 (cad/config/assemblies).
SCREW_POINT_INCOMPLETE = 0.61343 * SCREW.pitch
TAP_MOUTH_INCOMPLETE = 0.54127 * SCREW.pitch
SCREW_FULL_THREAD_MIN = (
    SCREW_ENGAGEMENT_MIN - SCREW_POINT_INCOMPLETE - TAP_MOUTH_INCOMPLETE
)
SCREW_FULL_THREAD_MAX = (
    SCREW_ENGAGEMENT_MAX - SCREW_POINT_INCOMPLETE - TAP_MOUTH_INCOMPLETE
)
if SCREW_FULL_THREAD_MIN <= 2.0 * SCREW.pitch:
    raise AssertionError("the clamp screw barely catches the dowel's thread")
SCREW_ENGAGEMENT_MIN_PRINTED = math.floor(SCREW_FULL_THREAD_MIN / INCH * 100.0) / 100.0
SCREW_ENGAGEMENT_DIAMETERS = SCREW_ENGAGEMENT_MIN_PRINTED * INCH / DOWEL_THREAD_MAJOR


def cut_turns_gear_clockwise(cam_radius: float = CAM_RADIUS_MIN) -> bool:
    """Seen from the tailstock the work turns counter-clockwise; the tool's
    reaction at the cam OD pushes the gear clockwise about the lathe axis. Its
    moment about the stub keeps that sign at every work angle because the cam
    radius exceeds the throw (moment arm r + t cos(phi) > 0)."""
    return cam_radius > THROW + POSITION_BAND


CUT_TURNS_GEAR_CLOCKWISE = cut_turns_gear_clockwise()
if not CUT_TURNS_GEAR_CLOCKWISE:
    raise AssertionError("the cut can unseat the gear from the clock pin")

# --- Clock pin: a class Z gauge pin in the notched tooth space ---------------------
# Printed coordinates from the register axis, on the .0001 grid. The pin
# stands at radius PIN_RADIUS from the stub, PIN_PHASE_DEG from the throw
# line: the gear's lobe-to-notch phase (PHASE_DEG) plus the seated half-play
# (``SEATED_HALF_PLAY_DEG``, below). Its radius is a function, not a number:
# the pin enters a tooth space only from about 1.260 out (``_play_table``),
# and the stub and pin stations each move it .002, so it stands .004 farther
# out than the bare entry radius.
PIN_X = -0.0704 * INCH  # -X: counter-clockwise of +Y seen from the tailstock
PIN_Y = 0.9246 * INCH
PIN_RADIUS = math.hypot(PIN_X, PIN_Y + STUB_OFFSET)
PIN_PHASE_DEG = math.degrees(math.atan2(-PIN_X, PIN_Y + STUB_OFFSET))
# Press ream for the .0375 minus pin (the .0365 reamer, REAM_H7).
PIN_HOLE_DIA = 0.0365 * INCH
PIN_HOLE_DEVIATIONS = REAM_H7[::-1]
PIN_DIA_MIN = PIN_DIA + PIN_DIA_BAND_IN[0] * INCH
PIN_DIA_MAX = PIN_DIA + PIN_DIA_BAND_IN[1] * INCH
PIN_PRESS_INTERFERENCE = (
    PIN_DIA_MIN - (PIN_HOLE_DIA + REAM_H7[0]),
    PIN_DIA_MAX - (PIN_HOLE_DIA + REAM_H7[1]),
)
if min(PIN_PRESS_INTERFERENCE) <= 0.0:
    raise AssertionError("the clock pin loses its press in the .0365 ream")
# Pressed to the floor of its reamed hole: it stands the cut length less the
# depth, inside the gear's disc (face width) and clear of the root.
PIN_HOLE_DEPTH = 0.20 * INCH
PIN_STAND = PIN_LENGTH - PIN_HOLE_DEPTH
_PIN_STAND_MAX = PIN_STAND + 2.0 * _XX  # cut length and depth, each .XX
_PIN_STAND_MIN = PIN_STAND - 2.0 * _XX
if _PIN_STAND_MAX >= FACE_WIDTH_MIN:
    raise AssertionError("the clock pin stands into the turning tool's plane")
if _PIN_STAND_MIN < 0.5 * FACE_WIDTH_MIN:
    raise AssertionError("the clock pin engages too little of the tooth space")

# Rule 17 walls: each hole to the register edge, the pin hole to the stub hole.
WALLS_MM = {
    "stub hole to register": (BODY_DIA - _XX) / 2.0
    - (STUB_OFFSET + POSITION_BAND)
    - (STUB_HOLE_DIA + REAM_H7[0]) / 2.0,
    "pin hole to register": (BODY_DIA - _XX) / 2.0
    - math.hypot(PIN_X, PIN_Y)
    - 2.0 * POSITION_BAND
    - (PIN_HOLE_DIA + REAM_H7[0]) / 2.0,
    "pin hole to stub hole": PIN_RADIUS
    - 2.0 * POSITION_BAND
    - (PIN_HOLE_DIA + STUB_HOLE_DIA + 2.0 * REAM_H7[0]) / 2.0,
}
for _wall, _mm in WALLS_MM.items():
    if _mm < WALL_TARGET_MM:
        raise AssertionError(f"cam fixture {_wall} wall {_mm:.3f} under rule 17")


# --- Phase: the pin's play in a tooth space ------------------------------------------
def _upper_flank(profile) -> tuple[tuple[float, float], ...]:
    """The tooth space's upper boundary below the tip (gap frame: the space
    centred on +X), sampled densely enough that chords err well under .0001."""
    points: list[tuple[float, float]] = []
    for segment in profile.gap_segments():
        if segment.name.startswith("Upper"):
            points += [segment.point(i / 120) for i in range(121)]
    return tuple(points)


def _distance_to(points, px: float, py: float) -> float:
    best = math.inf
    for (ax, ay), (bx, by) in zip(points, points[1:]):
        dx, dy = bx - ax, by - ay
        span = dx * dx + dy * dy
        t = (
            0.0
            if span == 0.0
            else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / span))
        )
        best = min(best, math.hypot(px - ax - t * dx, py - ay - t * dy))
    return best


def pin_half_play_rad(profile, radius: float, pin_dia: float) -> float | None:
    """Half the angle a gear of ``profile`` can turn about its own axis with
    a pin of ``pin_dia`` centred ``radius`` from that axis in a tooth space;
    None if the pin does not enter. The space is symmetric, so the turn to
    the upper flank is the turn either way."""
    flank = _upper_flank(profile)
    rho = pin_dia / 2.0
    if _distance_to(flank, radius, 0.0) < rho:
        return None
    lo, hi = 0.0, math.pi / gear.TEETH
    for _ in range(32):
        mid = (lo + hi) / 2.0
        if _distance_to(flank, radius * math.cos(mid), radius * math.sin(mid)) > rho:
            lo = mid
        else:
            hi = mid
    return lo


PROFILES = gear.manufacturing_corner_profiles()
# Radial reach of every error onto the pin's radius from the gear's axis.
_RADIAL_SPREAD = 2.0 * POSITION_BAND + BORE_FLOAT + REGISTER_OFFSET


@cache
def _play_table(pin_dia: float) -> tuple[tuple[tuple[float, float], ...], ...]:
    """Half-play (rad) against radius for each corner profile, on a grid
    spanning every reachable pin radius; linear between grid points."""
    lo = PIN_RADIUS - _RADIAL_SPREAD
    hi = PIN_RADIUS + _RADIAL_SPREAD
    radii = [lo + (hi - lo) * k / 8 for k in range(9)]
    tables = []
    for profile in PROFILES:
        row = []
        for r in radii:
            play = pin_half_play_rad(profile, r, pin_dia)
            if play is None:
                raise AssertionError(
                    f"the Ø{pin_dia / INCH:.4f} clock pin does not enter a tooth"
                    f" space {r / INCH:.4f} from the gear axis"
                )
            row.append((r, play))
        tables.append(tuple(row))
    return tuple(tables)


# Every gear seats on the counter-clockwise flank of its notched space: TL-00
# step 17 turns it clockwise (seen from the tailstock) onto the pin and
# the cut pushes it the same way (``CUT_TURNS_GEAR_CLOCKWISE``), so the
# space's centre stands one half-play clockwise of the pin (side -1). The pin
# is clocked that mean half-play counter-clockwise of the notch phase, so a
# nominal gear's seated notch lands on the phase.
SEATED_SIDE = -1.0
_SEATED_PLAYS = [
    pin_half_play_rad(profile, PIN_RADIUS, dia)
    for profile in PROFILES
    for dia in (PIN_DIA_MIN, PIN_DIA_MAX)
]
if None in _SEATED_PLAYS:
    raise AssertionError("the clock pin does not enter the notched space")
SEATED_HALF_PLAY_DEG = math.degrees(sum(_SEATED_PLAYS) / len(_SEATED_PLAYS))
if abs(PIN_PHASE_DEG - SEATED_HALF_PLAY_DEG - PHASE_DEG) > 0.01:
    raise AssertionError("the clock pin's printed station misses the seated phase")


def _play(table, radius: float) -> float:
    for (r0, p0), (r1, p1) in zip(table, table[1:]):
        if r0 <= radius <= r1:
            return p0 + (p1 - p0) * (radius - r0) / (r1 - r0)
    raise ValueError("pin radius outside the play table")


_DIRECTIONS = tuple(
    (math.cos(2.0 * math.pi * k / 16), math.sin(2.0 * math.pi * k / 16))
    for k in range(16)
)


def _phase_errors_deg(
    stub_error, pin_error, axis_error, pin_dia: float, side: float = SEATED_SIDE
) -> list[float]:
    """Every per-part phase error (deg) for one as-made fixture: the gear's
    bore anywhere on the stub's clearance circle, each corner profile, the
    gear seated on the ``side`` flank (``SEATED_SIDE``: all 20 gears seat on
    the same flank of the same pin)."""
    errors = []
    for cx, cy in _DIRECTIONS:
        gx = stub_error[0] + BORE_FLOAT * cx
        gy = -STUB_OFFSET + stub_error[1] + BORE_FLOAT * cy
        px, py = PIN_X + pin_error[0], PIN_Y + pin_error[1]
        radius = math.hypot(px - gx, py - gy)
        space = math.atan2(py - gy, px - gx)
        lobe = math.atan2(axis_error[1] - gy, axis_error[0] - gx)
        for table in _play_table(pin_dia):
            play = _play(table, radius)
            errors.append(math.degrees(space + side * play - lobe) - PHASE_DEG)
    return errors


def phase_budget_deg() -> dict[str, float]:
    """(a) fixed, (b) per-part and total worst-case phase errors, deg.

    (a): the lobe-to-seated-notch angle error, the mean half-play seated,
    with every hole and indication error at its limit; (b): half the scatter
    of the 20 gears on the worst as-made fixture, all seated on one flank of
    its one pin; total: the largest error any gear on any as-made fixture can
    show."""
    signs = (-1.0, 1.0)
    fixed = 0.0
    scatter = 0.0
    total = 0.0
    for sbx in signs:
        for sby in signs:
            for spx in signs:
                for spy in signs:
                    for ax, ay in _DIRECTIONS[::4]:
                        stub = (sbx * POSITION_BAND, sby * POSITION_BAND)
                        pin = (spx * POSITION_BAND, spy * POSITION_BAND)
                        axis = (AXIS_LATERAL * ax, REGISTER_OFFSET * ay)
                        gx, gy = stub[0], -STUB_OFFSET + stub[1]
                        px, py = PIN_X + pin[0], PIN_Y + pin[1]
                        fixed = max(
                            fixed,
                            abs(
                                math.degrees(
                                    math.atan2(py - gy, px - gx)
                                    - math.atan2(axis[1] - gy, axis[0] - gx)
                                )
                                - SEATED_HALF_PLAY_DEG
                                - PHASE_DEG
                            ),
                        )
                        for pin_dia in (PIN_DIA_MIN, PIN_DIA_MAX):
                            errors = _phase_errors_deg(stub, pin, axis, pin_dia)
                            scatter = max(scatter, (max(errors) - min(errors)) / 2.0)
                            total = max(total, max(map(abs, errors)))
    return {"fixed": fixed, "per_part": scatter, "total": total}


_BUDGET = phase_budget_deg()
PHASE_FIXED_WORST_DEG = _BUDGET["fixed"]  # (a), common to all 20 gears
PHASE_PER_PART_WORST_DEG = _BUDGET["per_part"]  # (b), gear-to-gear scatter
if PHASE_PER_PART_WORST_DEG > PHASE_SCATTER_TOLERANCE_DEG:
    raise AssertionError("the 20 gears' phase scatter exceeds the budget's cam_phase")
PHASE_TOTAL_WORST_DEG = _BUDGET["total"]
if PHASE_TOTAL_WORST_DEG > PHASE_TOLERANCE_DEG:
    raise AssertionError("a gear's worst phase exceeds MHA-DT-12's printed band")
# A reading that would set phase on the fixture finds the throw line through
# the stub, whose baseline is the throw: .001 read wrong turns it this much.
PHASE_PER_THOU_READING_DEG = math.degrees(0.001 * INCH / STUB_OFFSET)


# --- The kit (MHA-DT-12-TL-00): each component's place in the kit frame, mm ---
# The kit stands the body's front face up: its frame turns the body's +Z to
# the assembly's +Y (so the bought parts keep their own +Y axes) and the
# body's +Y to the assembly's -Z. The assembly's top view is then the view
# from the tailstock with the lobe up, as on the body's own face view. The
# gear is never placed; the washer and screw stand where a nominal gear would
# hold them.
def kit_point(body_xyz: tuple[float, float, float]) -> tuple[float, float, float]:
    """A body-frame point (mm) in the kit (assembly) frame."""
    x, y, z = body_xyz
    return (x, z, -y)


STUB_BASE = kit_point((0.0, -STUB_OFFSET, THICKNESS + STUB_STAND - DOWEL_LENGTH))
PIN_BASE = kit_point((PIN_X, PIN_Y, THICKNESS - PIN_HOLE_DEPTH))
WASHER_BASE = kit_point((0.0, -STUB_OFFSET, THICKNESS + gear.OVERALL_THICKNESS))
SCREW_SEAT = kit_point(
    (0.0, -STUB_OFFSET, THICKNESS + gear.OVERALL_THICKNESS + WASHER_MODEL_THICKNESS)
)
# The nominal screw's reach into the stub's thread, the modelled overlap.
SCREW_ENGAGEMENT = THICKNESS + STUB_STAND - (SCREW_SEAT[1] - SCREW.length)
if not SCREW_ENGAGEMENT_MIN < SCREW_ENGAGEMENT < SCREW_ENGAGEMENT_MAX:
    raise AssertionError("the kit's nominal screw sits outside its engagement range")
# The stub's pressed length in the body, the modelled press overlap.
STUB_PRESS_DEPTH_IN_BODY = min(STUB_PRESS_DEPTH, THICKNESS)

# --- Model globals: name -> value (mm); the build sets each and drives from it --
GLOBALS: dict[str, float] = {
    "BodyDia": BODY_DIA,
    "BodyThick": THICKNESS,
    "StubOffset": STUB_OFFSET,
    "StubHoleDia": STUB_HOLE_DIA,
    "PinX": -PIN_X,
    "PinY": PIN_Y,
    "PinHoleDia": PIN_HOLE_DIA,
    "PinHoleDepth": PIN_HOLE_DEPTH,
}

# --- Drawing -------------------------------------------------------------------------
# The pin hole's depth rides its callout (no view shows the blind floor:
# hidden lines removed and no section, draw_dt_cone_tip_block's dowel ream).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BodyProfile": {"BodyDia"},
    "Body": {"BodyThick"},
    "StubHoleProfile": {"StubOffset", "StubHoleDia"},
    "PinHoleProfile": {"PinX", "PinY", "PinHoleDia"},
}
_FOUR_PLACE = frozenset({"StubOffset", "StubHoleDia", "PinX", "PinY", "PinHoleDia"})
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    feature: {name: (4 if name in _FOUR_PLACE else 2) for name in names}
    for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dims in DRAWING_PRECISION.values() for name, places in dims.items()
}
DRAWING_VALUES_BY_NAME: dict[str, float] = {
    "BodyDia": BODY_DIA,
    "BodyThick": THICKNESS,
    "StubOffset": STUB_OFFSET,
    "StubHoleDia": STUB_HOLE_DIA,
    "PinX": -PIN_X,
    "PinY": PIN_Y,
    "PinHoleDia": PIN_HOLE_DIA,
}
PIN_HOLE_DEPTH_PLACES = 2
if abs(PIN_HOLE_DEPTH / INCH - round(PIN_HOLE_DEPTH / INCH, 2)) > 1e-9:
    raise AssertionError("the pin hole depth is off its .XX grid")
if set(DRAWING_VALUES_BY_NAME) != set(DRAWING_PRECISION_BY_NAME):
    raise AssertionError("every printed cam fixture dimension needs a value")
# Fabricated nominals sit on their printed inch grid (rule 3).
for _name, _value in DRAWING_VALUES_BY_NAME.items():
    _inches = _value / INCH
    _places = DRAWING_PRECISION_BY_NAME[_name]
    if abs(_inches - round(_inches, _places)) > 1e-9:
        raise AssertionError(f"cam fixture {_name} {_inches} in is off its grid")
# The explicit bands the model carries: each hole coordinate from the
# register axis.  The two press reams print the reamer's size and no band
# (fit audit 2026-11-23, MHA-DT-12-TL-01.stub_hole and .clock_pin_hole;
# drawing-guidelines rule 4, form 3): the bought pin is the gauge.
# STUB_HOLE_DEVIATIONS and PIN_HOLE_DEVIATIONS stay the analysis bands
# (REAM_H7, what the reamer cuts) that the press and wall checks consume.
MODEL_BANDS_MM: dict[tuple[str, str], tuple[float, float]] = {
    ("StubHoleProfile", "StubOffset"): POSITION_DEVIATIONS,
    ("PinHoleProfile", "PinX"): POSITION_DEVIATIONS,
    ("PinHoleProfile", "PinY"): POSITION_DEVIATIONS,
}


def inch_text(value_mm: float, places: int) -> str:
    """``value_mm`` as the sheet prints it: decimal inch, no leading zero."""
    text = f"{value_mm / INCH:.{places}f}"
    return text[1:] if text.startswith("0.") else text


# Each REAM callout names its pressed pin by its short form (a member of this
# sheet's MHA-DT-12-TL-00 kit), the fit and its acceptance; why each stays
# reamed and why each station keeps its +/-.002 is in the necessity register
# (cad/config/necessity/dt-cylinder-gear-tl-cam-fixture.yaml), not on the
# sheet (rule 4).  The location dimensions carry value and band only. The
# clock pin's blind press is permanent: no knockout behind a .0375 pin
# (rule 16's permanent pair).  Rows short enough to stand between the
# register and the edge view.
STUB_NUMBER = str(_config.parts("dt-cylinder-gear-tl-vn-cam-stub")["number"])
CLOCK_PIN_NUMBER = str(_config.parts("dt-cylinder-gear-tl-vn-cam-clock-pin")["number"])
GEAR_NUMBER = str(_config.parts("dt-cylinder-gear")["number"])
_KIT_PREFIX = f"{GEAR_NUMBER}-"


def kit_short_form(number: str) -> str:
    """A kit member's drawing number less the prefix it shares with this sheet."""
    if not number.startswith(_KIT_PREFIX):
        raise AssertionError(f"{number} is not a member of {_KIT_PREFIX}TL-00")
    return number[len(_KIT_PREFIX) :]


PIN_HOLE_DEPTH_TEXT = inch_text(PIN_HOLE_DEPTH, PIN_HOLE_DEPTH_PLACES)
CALLOUTS_BELOW: dict[str, str] = {
    "StubHoleDia": (
        f"REAM THRU\nPRESS FIT ON {kit_short_form(STUB_NUMBER)},\nDOES NOT TURN BY HAND"
    ),
    # Machinist review of 25a5c536c2 (blocker, 2 of 3 runs): the press fit
    # prints its acceptance, worded as the stub's (delegated ruling
    # 2026-11-24 (Main), no precedent; owner review #2144).
    "PinHoleDia": (
        f"REAM <HOLE-DEPTH> {PIN_HOLE_DEPTH_TEXT}\n"
        f"PRESS FIT ON {kit_short_form(CLOCK_PIN_NUMBER)}, PERMANENT PAIR,\n"
        "DOES NOT TURN BY HAND"
    ),
}
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"

# --- Kit sheet facts (MHA-DT-12-TL-00), worded here so the sheet only places them --
# The stub's set stand-out, read with the caliper's depth rod.
STUB_STAND_TEXT = f"{inch_text(STUB_STAND, 2)} ±{inch_text(STUB_STAND_BAND, 2)}"
# The clamp screw's least full-thread engagement, the value only (rule 18
# exception RV-01 on MHA-DT-12-TL-00, cad/config/assemblies).
SCREW_ENGAGEMENT_TEXT = f"{inch_text(SCREW_ENGAGEMENT_MIN_PRINTED * INCH, 2)} MIN"
# The register's set-up: item 1's OD (its sheet's Ø3.25) indicated to the
# REGISTER_TIR the phase budget carries, with a dial test indicator.
BODY_DIA_TEXT = inch_text(BODY_DIA, 2)
REGISTER_TIR_TEXT = inch_text(REGISTER_TIR, 3)
# The throw setting: the wrung stack's blocks, and the check's band on the
# dial test indicator.
THROW_STACK_TEXT = (
    ", ".join(
        inch_text(b * INCH, 4 if b < 0.101 else 3) for b in THROW_STACK_BLOCKS_IN[:-1]
    )
    + f" AND {inch_text(THROW_STACK_BLOCKS_IN[-1] * INCH, 3)}"
)
THROW_STACK_TOTAL_TEXT = inch_text(THROW_STACK, 4)
THROW_READING_BAND_TEXT = inch_text(THROW_READING_BAND, 3)
