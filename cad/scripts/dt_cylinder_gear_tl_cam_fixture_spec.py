r"""Pure-data contract for the cylinder gears' cam turning fixture (MHA-DT-12-TL-01).

Shop tooling, not a machine part (cad/docs/subsystem-identities.md), issue
#2361. Each of the 20 MHA-DT-12 cylinder gears carries an integral eccentric
cam whose throw is the channel's gain and whose lobe direction, read against
the alignment notch, is the channel's phase. The gear's bore is reamed, its
120 teeth and the notch are cut concentric on an arbor first; the cam is
turned last, on this fixture, so throw and cam-to-notch phase are set once in
the fixture and repeat over 20 gears without indicating each one.

The fixture is one made part, a round steel body gripped in the lathe's
4-jaw and indicated true once on its turned register (the OD), then left in
the chuck for all 20 gears. Its front face carries, all bought
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
stands on -Y so the cam lobe points +Y, as on the gear; the clock pin stands
1.5 deg counter-clockwise of the +Y line seen from +Z (the tailstock), the
gear's own NOTCH_PHASE_DEG. Every number of the gear is imported from
``dt_cylinder_gear_spec``.

Accuracy (this module asserts only what is true). Each error is split into
(a) terms fixed in the fixture and so the same on all 20 gears (the stub and
pin hole stations, the register's indication, the printed stations'
rounding) and (b) per-gear terms (the gear's bore clearance on the stub,
the gear's tooth form within its own bands): (b) is asserted inside the
gear's printed band for the fixture's worst as-made state; (a) and the total
are recorded, not asserted.

* Throw: (a) ``THROW_FIXED_MAX_MM`` .0023, (b) ``THROW_PER_PART_MAX_MM``
  .0007, total .0030 against the print's +/-.0020. A common throw error is a
  uniform gain on every channel.
* Phase: (a) ``PHASE_FIXED_WORST_DEG`` .39 deg, (b)
  ``PHASE_PER_PART_WORST_DEG`` .13 deg, total ``PHASE_TOTAL_WORST_DEG`` .60
  deg against the print's +/-.25 deg. Every gear seats on the same flank of
  the pin (TL-00 step 2), so the pin stands its mean half-play
  (``SEATED_HALF_PLAY_DEG``, .19 deg) counter-clockwise of the phase and a
  nominal fixture's common error is nil. A common phase error phi0 is NOT a
  uniform gain: every channel draws cos(k theta + phi0), the same angle in
  each gear's own turn, and zeroing (MHA-DT-00 check 5) sets the notches,
  not the lobes, so nothing in the machine removes it.

The hole stations carry the shop table's +/-.002 for a reamed hole from its
datum and nothing tighter: one tool made once, cut to a number. The fixed
parts exceed the gear's printed bands at the fixture's worst as-made state;
whether MHA-DT-12's 1.5 +/-.25 deg and .3402 +/-.0020 stand is an owner
question on #2356. The TL-00 checks accept the as-made stub runout and the
pin's seat in a gear.
"""

from __future__ import annotations

import math
from functools import cache

import _config
import dt_cylinder_gear_spec as gear
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
PHASE_DEG = gear.NOTCH_PHASE_DEG
PHASE_TOLERANCE_DEG = gear.CAM_PHASE_TOLERANCE_DEG

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
# Press ream for the 97175A344 dowel (+.0001/+.0003 over 3/8): the .3745
# reamer, REAM_H7's +.0005/0.
STUB_HOLE_DIA = 0.3745 * INCH
STUB_HOLE_DEVIATIONS = REAM_H7[::-1]  # (lower, upper)
HOLE_PLACES = 4
DOWEL_DIA_MIN = DOWEL_DIA + DOWEL_DIA_BAND_IN[0] * INCH
DOWEL_DIA_MAX = DOWEL_DIA + DOWEL_DIA_BAND_IN[1] * INCH
STUB_PRESS_INTERFERENCE = (
    DOWEL_DIA_MIN - (STUB_HOLE_DIA + REAM_H7[0]),
    DOWEL_DIA_MAX - (STUB_HOLE_DIA + REAM_H7[1]),
)
if min(STUB_PRESS_INTERFERENCE) <= 0.0:
    raise AssertionError("the stub dowel loses its press in the .3745 ream")
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

# The clamp pulls the pressed dowel out of the body; its press (steel in
# steel, the least interference, Lamé for a pin in a large body) holds more
# than a firm hand-tightened 10-32 (about 10 in-lbf, nut factor .2).
_STEEL_E_PSI = 30.0e6
_FRICTION = 0.15
CLAMP_TORQUE_IN_LBF = 10.0
CLAMP_PRELOAD_LBF = CLAMP_TORQUE_IN_LBF / (0.2 * SCREW.major_dia / INCH)
_PRESS_PSI = (
    _STEEL_E_PSI * (STUB_PRESS_INTERFERENCE[0] / INCH) / (2.0 * DOWEL_DIA / INCH)
)
STUB_RETENTION_LBF = (
    _FRICTION * _PRESS_PSI * math.pi * (DOWEL_DIA / INCH) * (STUB_PRESS_DEPTH / INCH)
)
if STUB_RETENTION_LBF <= CLAMP_PRELOAD_LBF:
    raise AssertionError("the clamp screw can pull the stub out of the body")

# --- Throw, worst case ------------------------------------------------------------
# The DTI's .0005 division is the register's indicated runout (TIR): the
# register axis then sits within half of it of the lathe axis.
REGISTER_TIR = 0.0005 * INCH
REGISTER_OFFSET = REGISTER_TIR / 2.0
# Fixed in the fixture, so the same on all 20 gears: the stub's station and
# the register's indication. Per gear: the gear's bore floating on the stub.
THROW_FIXED_MAX_MM = abs(STUB_OFFSET - THROW) + POSITION_BAND + REGISTER_OFFSET
THROW_PER_PART_MAX_MM = BORE_FLOAT
if THROW_PER_PART_MAX_MM > THROW_TOLERANCE:
    raise AssertionError("the 20 gears' throw scatter exceeds the printed band")
# Recorded, not asserted: at the shop row the fixed part alone exceeds the
# gear's printed +/-.0020 (MHA-DT-12 print vs this tool: owner question).
THROW_ERROR_MAX_MM = THROW_FIXED_MAX_MM + THROW_PER_PART_MAX_MM

# --- Clamp: one 10-32 SHCS into the dowel's tap, a #10 washer on the cam face --------
# The screw centres in the dowel's thread; the washer floats on the screw.
_THREAD_FLOAT = 0.002 * INCH  # 10-32 2B/3A pitch-diameter float, radial
_WASHER_FLOAT = (WASHER_ID - SCREW.major_dia) / 2.0
_WASHER_OD_MAX = WASHER_OD + 0.005 * INCH  # commercial washer, no band given
_WASHER_OD_MIN = WASHER_OD - 0.005 * INCH
_STUB_FROM_AXIS_MAX = STUB_OFFSET + POSITION_BAND + REGISTER_OFFSET
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
# Engagement of the 5/16 screw in the dowel's full thread, from the washer
# on the cam face: never past the .255 full-thread depth (it would jam in the
# tap's lead), and its least value stated as a fact (rule 18 shortfall).
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
if SCREW_ENGAGEMENT_MIN <= 2.0 * SCREW.pitch:
    raise AssertionError("the clamp screw barely catches the dowel's thread")
SCREW_ENGAGEMENT_MIN_PRINTED = math.floor(SCREW_ENGAGEMENT_MIN / INCH * 100.0) / 100.0
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
# line: the gear's NOTCH_PHASE_DEG plus the seated half-play
# (``SEATED_HALF_PLAY_DEG``, below). Its radius is a function, not a number:
# the pin enters a tooth space only from about 1.260 out (``_play_table``),
# and the stub and pin stations each move it .002, so it stands .004 farther
# out than the bare entry radius.
PIN_X = -0.0373 * INCH  # -X: counter-clockwise of +Y seen from the tailstock
PIN_Y = 0.9260 * INCH
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
# fitting step 2 turns it clockwise (seen from the tailstock) onto the pin and
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
                        axis = (REGISTER_OFFSET * ax, REGISTER_OFFSET * ay)
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
if PHASE_PER_PART_WORST_DEG > PHASE_TOLERANCE_DEG:
    raise AssertionError("the 20 gears' phase scatter exceeds the printed band")
# Recorded, not asserted: (a) alone exceeds the printed +/-.25 deg at the
# shop row (module docstring); the fixture is cut to that row, not tightened.
PHASE_TOTAL_WORST_DEG = _BUDGET["total"]


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
# register axis and each press ream.
MODEL_BANDS_MM: dict[tuple[str, str], tuple[float, float]] = {
    ("StubHoleProfile", "StubOffset"): POSITION_DEVIATIONS,
    ("PinHoleProfile", "PinX"): POSITION_DEVIATIONS,
    ("PinHoleProfile", "PinY"): POSITION_DEVIATIONS,
    ("StubHoleProfile", "StubHoleDia"): STUB_HOLE_DEVIATIONS,
    ("PinHoleProfile", "PinHoleDia"): PIN_HOLE_DEVIATIONS,
}


def inch_text(value_mm: float, places: int) -> str:
    """``value_mm`` as the sheet prints it: decimal inch, no leading zero."""
    text = f"{value_mm / INCH:.{places}f}"
    return text[1:] if text.startswith("0.") else text


# Each REAM callout names its pressed pin by its short form (a member of this
# sheet's MHA-DT-12-TL-00 kit) and, once, what its stations' +/-.002 sets on
# the gear (rules 4 and 7); the location dimensions carry value and band
# only. The clock pin's blind press is permanent: no knockout behind a .0375
# pin (rule 16's permanent pair). Rows short enough to stand between the
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
        f"REAM THRU\nPRESS FIT ON {kit_short_form(STUB_NUMBER)}\n"
        f"SETS {GEAR_NUMBER} CAM THROW"
    ),
    "PinHoleDia": (
        f"REAM <HOLE-DEPTH> {PIN_HOLE_DEPTH_TEXT}\n"
        f"PRESS FIT ON {kit_short_form(CLOCK_PIN_NUMBER)}, PERMANENT PAIR\n"
        f"SETS {GEAR_NUMBER} CAM PHASE"
    ),
}
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"

# --- Kit sheet facts (MHA-DT-12-TL-00), worded here so the sheet only places them --
# The stub's set stand-out, read with the caliper's depth rod.
STUB_STAND_TEXT = f"{inch_text(STUB_STAND, 2)} ±{inch_text(STUB_STAND_BAND, 2)}"
# The clamp screw's least engagement, stated as fact (rules 18 and 20).
SCREW_ENGAGEMENT_TEXT = (
    f"{inch_text(SCREW_ENGAGEMENT_MIN_PRINTED * INCH, 2)} MIN "
    f"({SCREW_ENGAGEMENT_DIAMETERS:.2f}D, UNDER THE 1.5D FLOOR)"
)
# The stub's runout with the register true: twice its station, +/- twice
# the station band, read on the 1 in dial indicator.
STUB_RUNOUT_TIR = 2.0 * STUB_OFFSET
STUB_RUNOUT_TEXT = (
    f"{inch_text(STUB_RUNOUT_TIR - 2.0 * POSITION_BAND, 4)} TO "
    f"{inch_text(STUB_RUNOUT_TIR + 2.0 * POSITION_BAND, 4)}"
)
