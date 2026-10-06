r"""MHA-PD-022 transgear-drive-collar: the brass drive collar on the knob shaft.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  ``build_pd_transgear_drive_collar`` marks and tolerances exactly
``DRAWING_DIMENSIONS`` / ``DRAWING_PRECISION`` on the model and
``draw_pd_transgear_drive_collar`` keeps exactly the same names.

Contract §1.2 (round 10): a Ø17.5 × 4.000 brass collar reamed Ø6.350 to
slide on the knob shaft's plain Ø6.35 core (MHA-PD-008).  It is set on the core
at assembly and pinned by the MHA-VN-037 spring pin, drilled through the core
along the collar's diametral rear slot and lying in it, so the slot walls
carry the drive (R9-6).  The front face is the removable T24's (MHA-PD-009)
seat: the Ø10.00 pilot enters the wheel's Ø10.3 bore and two MHA-VN-038 dowels
pressed through reamed holes on the Ø14 circle drive the wheel.  R9-70
(N-A): the pilot is supplied long and faced at assembly to stand
PILOT_PROUD_RANGE proud of the T24's front face, and the thumbnut (MHA-PD-013)
seats on the pilot's front face, so the nut clamps the collar to the shaft
and the T24 floats that much between the collar and the nut.  The drive
runs T24 -> drive pins -> collar -> MHA-VN-037 -> shaft; the nut carries no
torque.  The model carries the pilot at its nominal fitted length.

Part frame: the axis is local +Z through the origin (``Axis1``, the bore
axis); +Z is machine +Z (rearward), so the assembly places the part without
rotation.  The origin is the front (seat) face, machine z -154.3 at the
nominal setting: the body runs z = 0..LENGTH, the pilot -PILOT_LENGTH..0, the
rear slot along local X from SLOT_FLOOR_Z to LENGTH, and the drive-pin holes
run along Z at (0, ±PIN_CIRCLE_RADIUS).

Named datums: ``Axis1``; ``Front Plane`` (the seat face); planes
``PilotFront``, ``RearFace`` and ``SlotFloor``; axes ``DrivePinAxis1`` (+Y)
and ``DrivePinAxis2`` (-Y).
"""

from __future__ import annotations

import math
import textwrap

from _printed_tolerance import drilled_oversize_mm, printed_band_mm, printed_deviations
from dt_crankshaft_spec import (
    DRIVE_PIN_HOLE_BAND,
    DRIVE_PIN_LENGTH_GRADE,
    DRIVE_PIN_OFFSET_PLACES,
    DRIVE_PIN_OFFSET_TOL,
    SPIGOT_DIA_BAND,
)
from vn_transgear_collar_cross_pin_spec import FREE_DIA_MAX as CROSS_PIN_FREE_DIA_MAX
from vn_transgear_collar_cross_pin_spec import FREE_DIA_MIN as CROSS_PIN_FREE_DIA_MIN
from vn_transgear_collar_cross_pin_spec import HOLE_BAND as CROSS_HOLE_BAND
from vn_transgear_collar_cross_pin_spec import HOLE_DIA as CROSS_HOLE_DIA
from vn_transgear_knob_drive_pin_spec import LENGTH as PIN_LENGTH
from vn_transgear_knob_drive_pin_spec import PROUD_RANGE, THINNEST_PLATE
from pd_transgear_knob_shaft_spec import (
    CORE_DIA,
    CORE_DIA_BAND,
    CORE_LENGTH,
    CORE_LENGTH_PLACES,
    END_FLOAT,
    END_FLOAT_SET_TOL,
    ENGAGEMENT_FLOOR_D,
    PLAIN_CORE,
    PLAIN_CORE_PLACES,
    RELIEF_DIA_MAX,
    THREAD_MAJOR,
    THREAD_PITCH,
    TIP_STATION,
    TIP_STATION_PLACES,
)
from pd_transgear_removable_spec import BORE_DIA as WHEEL_BORE_DIA
from pd_transgear_removable_spec import (
    DRIVE_PIN_HOLE_DIA,
    DRIVE_PIN_PROUD,
    PLATE,
    PLATE_BAND,
    SEAT_SPIGOT_DIA,
    SEAT_SPIGOT_RIM,
)
from pd_transgear_removable_spec import PIN_CIRCLE_RADIUS as _WHEEL_PIN_CIRCLE_RADIUS
from pd_transgear_thumbnut_spec import CSK_DIA as NUT_CSK_DIA
from pd_transgear_thumbnut_spec import FLANGE_DIA as NUT_FLANGE_DIA
from pd_transgear_thumbnut_spec import FLANGE_DIA_PLACES as NUT_FLANGE_DIA_PLACES
from pd_transgear_thumbnut_spec import FRONT_THREAD_LOSS as NUT_FRONT_THREAD_LOSS
from pd_transgear_thumbnut_spec import OVERALL_LENGTH as NUT_LENGTH
from pd_transgear_thumbnut_spec import OVERALL_LENGTH_LO as NUT_LENGTH_LO
from pd_transgear_thumbnut_spec import REAR_THREAD_LOSS as NUT_REAR_THREAD_LOSS
from pd_transgear_thumbnut_spec import TAP_MINOR_2B_MIN as NUT_MINOR_MIN

# The policy's wall floor for a named shortfall (the 2.0 target's floor).
WALL_FLOOR = 1.5

# --- Body: Ø17.5 × 4.000, the knob shaft's half of the seat interface --------
LENGTH = 4.0
LENGTH_PLACES = 3  # the rearward travel SET - L (contract §13)
OD = SEAT_SPIGOT_DIA  # 17.5, the crank spigot's seat
# The removables swap between shafts: the crank spigot's functional band.
OD_BAND = SPIGOT_DIA_BAND  # (upper, lower) = (0, -0.10)
OD_PLACES = 2

# --- Pilot on the front face, through the T24's Ø10.3 bore (ruling 5) ---------
PILOT_DIA = 10.0
PILOT_DIA_BAND = (0.0, -0.10)
PILOT_DIA_PLACES = 2
# R9-70 (N-A): the thumbnut's seat.  The fitter faces the pilot so its front
# face stands PILOT_PROUD_RANGE proud of the T24's front face (the plate
# measured, the pilot faced to it plus 0.10 ±0.05), so the T24 is free under
# the nut by the same amount.  The pilot's fitted length is the plate plus
# that: 2.70 + 0.05 = 2.75 .. 2.80 + 0.15 = 2.95; it is supplied
# PILOT_BLANK_LENGTH_MIN long and the model carries the nominal 2.8 + 0.10.
PILOT_PROUD_RANGE = (0.05, 0.15)
PILOT_PROUD = sum(PILOT_PROUD_RANGE) / 2.0  # 0.10
PILOT_LENGTH = PLATE + PILOT_PROUD  # 2.90, nominal fitted
PILOT_LENGTH_PLACES = 2
PILOT_LENGTH_FITTED_MIN = THINNEST_PLATE + min(PILOT_PROUD_RANGE)  # 2.75
PILOT_LENGTH_FITTED_MAX = PLATE + max(PLATE_BAND) + max(PILOT_PROUD_RANGE)  # 2.95
FACING_ALLOWANCE = 0.10
PILOT_BLANK_LENGTH_MIN = 3.40
if PILOT_BLANK_LENGTH_MIN < PILOT_LENGTH_FITTED_MAX + FACING_ALLOWANCE - 1e-9:
    raise AssertionError(
        f"MHA-PD-022 pilot blank {PILOT_BLANK_LENGTH_MIN:.2f} MIN leaves no "
        f"{FACING_ALLOWANCE} facing allowance over the "
        f"{PILOT_LENGTH_FITTED_MAX:.2f} longest fit"
    )
if not PILOT_LENGTH_FITTED_MIN <= PILOT_LENGTH <= PILOT_LENGTH_FITTED_MAX:
    raise AssertionError("MHA-PD-022's modelled pilot lies outside its fitted band")

# --- Bore: reamed through, sliding on the plain core --------------------------
BORE_DIA = CORE_DIA  # 6.35
BORE_DIA_BAND = (0.010, 0.0)
BORE_DIA_PLACES = 3

# --- Diametral rear slot along local X for the MHA-VN-037 spring pin (R9-6) ------
# The pin's ends, outside the core's hole, spring back toward their free
# diameter and lie in the slot, whose walls carry the drive.  R9-52: the slot
# clears the largest free pin at its narrowest, so the pin drops in at fit-up
# and the walls bear only under torque: 1.80 - 1.753 = 0.047 .. 1.90 - 1.676
# = 0.224 (B18.8.2 free diameter, MHA-VN-037's spec).
SLOT_WIDTH = 1.8
SLOT_WIDTH_BAND = (0.10, 0.0)
SLOT_DEPTH = 1.8
SLOT_DEPTH_BAND = (0.10, 0.0)
SLOT_PLACES = 1
SLOT_FLOOR_Z = LENGTH - SLOT_DEPTH  # 2.2
SLOT_PIN_CLEARANCE = (
    SLOT_WIDTH + min(SLOT_WIDTH_BAND) - CROSS_PIN_FREE_DIA_MAX,
    SLOT_WIDTH + max(SLOT_WIDTH_BAND) - CROSS_PIN_FREE_DIA_MIN,
)
if SLOT_PIN_CLEARANCE[0] <= 0.0:
    raise AssertionError(
        f"MHA-PD-022 slot / MHA-VN-037 pin: the narrowest slot "
        f"{SLOT_WIDTH + min(SLOT_WIDTH_BAND):.3f} grips the pin's free "
        f"Ø{CROSS_PIN_FREE_DIA_MAX:.3f} ({SLOT_PIN_CLEARANCE[0]:+.3f})"
    )

# --- Drive-pin holes: reamed THROUGH for the MHA-VN-038 press (the crank's twin) -
PIN_CIRCLE_RADIUS = _WHEEL_PIN_CIRCLE_RADIUS  # 7.0, ±Y
PIN_HOLE_DIA = DRIVE_PIN_HOLE_DIA  # 2.38
PIN_HOLE_BAND = DRIVE_PIN_HOLE_BAND  # (0, -0.010)
PIN_HOLE_PLACES = 3
PIN_OFFSET_TOL = DRIVE_PIN_OFFSET_TOL  # ±0.025 each centre
PIN_OFFSET_PLACES = DRIVE_PIN_OFFSET_PLACES
PIN_HOLE_DEPTH = LENGTH  # through the body

# --- Decimal places ARE the tolerance (policy rule 2) --------------------------
# .XXX: the length (the rearward travel) and the pin-centre offsets (±0.025);
# the fits carry their own bands; the pilot length reads .XX.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BodyProfile": {"CollarDia", "CollarLength", "PilotDia", "PilotLength"},
    "BoreProfile": {"BoreDia"},
    "SlotProfile": {"SlotWidth", "SlotDepth"},
    "PinHoleProfile": {"PinPosDia", "PinPosY", "PinNegY"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BodyProfile": {
        "CollarDia": OD_PLACES,
        "CollarLength": LENGTH_PLACES,
        "PilotDia": PILOT_DIA_PLACES,
        "PilotLength": PILOT_LENGTH_PLACES,
    },
    "BoreProfile": {"BoreDia": BORE_DIA_PLACES},
    "SlotProfile": {"SlotWidth": SLOT_PLACES, "SlotDepth": SLOT_PLACES},
    "PinHoleProfile": {
        "PinPosDia": PIN_HOLE_PLACES,
        "PinPosY": PIN_OFFSET_PLACES,
        "PinNegY": PIN_OFFSET_PLACES,
    },
}
if {feature: set(names) for feature, names in DRAWING_PRECISION.items()} != (
    DRAWING_DIMENSIONS
):
    raise AssertionError("every marked MHA-PD-022 dimension needs authored places")
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}

LENGTH_TOL = printed_band_mm(LENGTH_PLACES)  # 0.13
LENGTH_MIN = round(LENGTH - LENGTH_TOL, 6)  # 3.87
LENGTH_MAX = round(LENGTH + LENGTH_TOL, 6)  # 4.13
# An unlocated feature's centring on the axis (the slot, the cross hole): the
# fleet's position term, half the .XXX row (contract §8).
POSITION_TOL = printed_band_mm(3) / 2.0  # 0.065


def floor_2(value: float) -> float:
    """A MIN on the sheet never rounds up past the arithmetic."""
    return math.floor(value * 100.0 + 1e-9) / 100.0


# --- Walls (contract §8) ---------------------------------------------------------
_OD_R_MIN = (OD + min(OD_BAND)) / 2.0  # 8.70
_PIN_HOLE_R_MAX = (PIN_HOLE_DIA + max(PIN_HOLE_BAND)) / 2.0  # 1.19
# Drive-pin hole to the Ø17.5 rim: 8.75 - 7.0 - 1.19 = 0.56 nominal;
# 8.70 - 7.025 - 1.19 = 0.485 worst, printed 0.48.
DRIVE_PIN_COLLAR_RIM = OD / 2.0 - PIN_CIRCLE_RADIUS - PIN_HOLE_DIA / 2.0
DRIVE_PIN_COLLAR_RIM_WORST = floor_2(
    _OD_R_MIN - PIN_CIRCLE_RADIUS - PIN_OFFSET_TOL - _PIN_HOLE_R_MAX
)
# Pilot over the bore: (10.0 - 6.35) / 2 = 1.825; (9.90 - 6.36) / 2 = 1.77.
PILOT_WALL = (PILOT_DIA - BORE_DIA) / 2.0
PILOT_WALL_WORST = floor_2(
    (PILOT_DIA + min(PILOT_DIA_BAND) - (BORE_DIA + max(BORE_DIA_BAND))) / 2.0
)
# Slot floor to the front face: 4.0 - 1.8 = 2.2; 3.87 - 1.90 = 1.97.
SLOT_FLOOR_WALL = SLOT_FLOOR_Z
SLOT_FLOOR_WALL_WORST = floor_2(LENGTH_MIN - (SLOT_DEPTH + max(SLOT_DEPTH_BAND)))
# Slot side to the drive-pin holes (slot along X, pins on ±Y):
# 7.0 - 1.19 - 0.90 = 4.91; less the offset 0.025, the slot's +0.10 half
# 0.05 and its centring 0.065: 4.77.
SLOT_PIN_WALL = PIN_CIRCLE_RADIUS - PIN_HOLE_DIA / 2.0 - SLOT_WIDTH / 2.0
SLOT_PIN_WALL_WORST = (
    PIN_CIRCLE_RADIUS
    - PIN_OFFSET_TOL
    - _PIN_HOLE_R_MAX
    - (SLOT_WIDTH + max(SLOT_WIDTH_BAND)) / 2.0
    - POSITION_TOL
)
# Bore to the drive-pin holes: 7.0 - 1.19 - 3.175 = 2.635; 2.605 worst.
BORE_PIN_WALL = PIN_CIRCLE_RADIUS - PIN_HOLE_DIA / 2.0 - BORE_DIA / 2.0
BORE_PIN_WALL_WORST = (
    PIN_CIRCLE_RADIUS
    - PIN_OFFSET_TOL
    - _PIN_HOLE_R_MAX
    - (BORE_DIA + max(BORE_DIA_BAND)) / 2.0
)
# The holes run through the body beside the pilot, never into it.
PIN_HOLE_INNER_R_MIN = PIN_CIRCLE_RADIUS - PIN_OFFSET_TOL - _PIN_HOLE_R_MAX  # 5.785
PILOT_R_MAX = (PILOT_DIA + max(PILOT_DIA_BAND)) / 2.0  # 5.0

# --- Fits ------------------------------------------------------------------------
# Diametral sliding clearance on the core: 6.350..6.360 over 6.335..6.345.
BORE_CORE_CLEARANCE = (
    BORE_DIA + min(BORE_DIA_BAND) - (CORE_DIA + max(CORE_DIA_BAND)),
    BORE_DIA + max(BORE_DIA_BAND) - (CORE_DIA + min(CORE_DIA_BAND)),
)  # 0.005 .. 0.025
# Radial air round the pilot in the T24's drilled Ø10.3 bore: 0.15 .. 0.25.
PILOT_BORE_CLEARANCE = (
    (WHEEL_BORE_DIA - (PILOT_DIA + max(PILOT_DIA_BAND))) / 2.0,
    (WHEEL_BORE_DIA + drilled_oversize_mm() - (PILOT_DIA + min(PILOT_DIA_BAND))) / 2.0,
)
# R9-70 (N-A): the thumbnut seats on the pilot's front face, which stands
# PILOT_PROUD_RANGE proud of the T24's front face: the nut's seat bears on the
# pilot's annulus outside its rear countersink, (9.90 - 6.75) / 2 = 1.575 at
# the worst case, its flange covers the pilot all round, and the T24 is free
# under it by the proud.
_NUT_FLANGE_LO, _ = printed_deviations(NUT_FLANGE_DIA, NUT_FLANGE_DIA_PLACES)
NUT_PILOT_BEARING_WORST = (PILOT_DIA + min(PILOT_DIA_BAND) - NUT_CSK_DIA) / 2.0
NUT_FLANGE_OVER_PILOT_WORST = (
    NUT_FLANGE_DIA + _NUT_FLANGE_LO - (PILOT_DIA + max(PILOT_DIA_BAND))
) / 2.0
T24_FLOAT_RANGE = PILOT_PROUD_RANGE


# --- Drive pins pressed through to a stop (MHA-VN-038) ------------------------------
def pin_hole_meets_wall_floor(collar_length: float, depth: float) -> bool:
    """A pin hole either runs through the collar or leaves ``WALL_FLOOR`` of
    solid behind its floor; a thinner floor is a wall under the policy."""
    return depth >= collar_length or collar_length - depth >= WALL_FLOOR - 1e-9


def pin_rear_inset(collar_length: float, pin_length: float, proud: float) -> float:
    """How far the pressed end of a pin set ``proud`` of the seat face stays
    inside the collar's rear face (negative: it stands out toward the disc)."""
    return collar_length - (pin_length - proud)


# 4.0 - (4.7625 - 2.4) = 1.6375 nominal; the shortest collar, the longest
# dowel set lowest: 3.87 - (4.7625 + 0.254 - 2.30) = 1.1535.
PIN_REAR_INSET = pin_rear_inset(LENGTH, PIN_LENGTH, DRIVE_PIN_PROUD)
PIN_REAR_INSET_WORST = pin_rear_inset(
    LENGTH_MIN, PIN_LENGTH + DRIVE_PIN_LENGTH_GRADE, min(PROUD_RANGE)
)

# --- The fit-up setting (contract §13, (C)) --------------------------------------
# The T24 seat (this front face) stands SET_NOMINAL in front of the 12T front
# face F; the rearward travel ends where the collar's rear face meets F, the
# forward travel where the core's cross-pin hole, drilled at the setting,
# would reach the shaft's thread relief (below).
SET_NOMINAL = 6.2
FORWARD_TRAVEL_MAX = 0.7
SEAT_MAX_FROM_F = 6.90
REARWARD_TRAVEL_NOMINAL = SET_NOMINAL - LENGTH  # 2.2
REARWARD_TRAVEL_RANGE = (SET_NOMINAL - LENGTH_MAX, SET_NOMINAL - LENGTH_MIN)

# --- The core's cross-pin hole against the thread relief (R9-18, R9-53) ---------
# Collar frame: the seat at z 0 and F at z = the seat's setting in front of F.
# The hole is drilled along the slot at that setting, its axis one hole
# radius above the slot floor (2.2 + 0.8 = 3.0); its front edge comes forward
# by the hole's upper limit, the slot's +0.10, the centring 0.065 and the
# collar's .XXX length: 3.0 - 0.825 - 0.10 - 0.065 - 0.13 = 1.88, so it lies
# seat - 1.88 in front of F.  The full Ø6.35 core ends CORE_LENGTH in front
# of F, 0.13 nearer on the shortest printed core, where the thread relief
# (holding the die's run-out) begins.  The fitter may set the seat anywhere
# up to SEAT_MAX_FROM_F, so the hole must stay in the full core there.
CROSS_HOLE_Z = SLOT_FLOOR_Z + CROSS_HOLE_DIA / 2.0
CROSS_HOLE_FRONT_Z_WORST = (
    CROSS_HOLE_Z
    - (CROSS_HOLE_DIA + max(CROSS_HOLE_BAND)) / 2.0
    - max(SLOT_DEPTH_BAND)
    - POSITION_TOL
    - LENGTH_TOL
)
CORE_LENGTH_MIN = CORE_LENGTH - printed_band_mm(CORE_LENGTH_PLACES)  # 5.12


def core_hole_relief_margin(seat_from_f: float, core_length: float) -> float:
    """Full core between the cross hole's front edge, the hole drilled with
    the seat ``seat_from_f`` in front of F, and a core ``core_length`` long
    (negative: the hole breaks into the thread relief)."""
    return core_length - (seat_from_f - CROSS_HOLE_FRONT_Z_WORST)


# At the furthest setting the sheet accepts:
# 5.12 - (6.90 - 1.88) = 0.10 (0.80 at the nominal 6.2).
CORE_HOLE_RELIEF_MARGIN = core_hole_relief_margin(SEAT_MAX_FROM_F, CORE_LENGTH_MIN)
if CORE_HOLE_RELIEF_MARGIN <= 0.0:
    raise AssertionError(
        f"MHA-VN-037 cross hole / MHA-PD-008 thread relief: at the T24 seat "
        f"{SEAT_MAX_FROM_F:.2f} the hole's front edge reaches "
        f"{SEAT_MAX_FROM_F - CROSS_HOLE_FRONT_Z_WORST:.3f} in front of F, past "
        f"the shortest core {CORE_LENGTH_MIN:.3f} ({CORE_HOLE_RELIEF_MARGIN:+.3f})"
    )

for _ok, _what in (
    (
        math.isclose(DRIVE_PIN_COLLAR_RIM, SEAT_SPIGOT_RIM, abs_tol=1e-9),
        "the collar rim is not the seat interface's rim",
    ),
    (DRIVE_PIN_COLLAR_RIM_WORST > 0.0, "the drive-pin holes break out of the rim"),
    (PILOT_WALL_WORST >= WALL_FLOOR, "pilot wall under the floor"),
    (SLOT_FLOOR_WALL_WORST >= WALL_FLOOR, "slot floor to front face under the floor"),
    (SLOT_PIN_WALL_WORST >= WALL_FLOOR, "slot side to drive-pin hole under the floor"),
    (BORE_PIN_WALL_WORST >= WALL_FLOOR, "bore to drive-pin hole under the floor"),
    (PIN_HOLE_INNER_R_MIN > PILOT_R_MAX, "the drive-pin holes break into the pilot"),
    (min(BORE_CORE_CLEARANCE) > 0.0, "the bore binds on the plain core"),
    (min(PILOT_BORE_CLEARANCE) > 0.0, "the pilot binds in the T24 bore"),
    (NUT_PILOT_BEARING_WORST > 0.0, "the thumbnut's countersink swallows the pilot"),
    (
        NUT_FLANGE_OVER_PILOT_WORST > 0.0,
        "the thumbnut's flange no longer covers the pilot",
    ),
    (min(T24_FLOAT_RANGE) > 0.0, "the pilot no longer stands proud of the T24"),
    (
        pin_hole_meets_wall_floor(LENGTH, PIN_HOLE_DEPTH),
        "a blind drive-pin hole leaves a floor under the wall floor",
    ),
    (PIN_REAR_INSET_WORST >= 0.0, "a pressed drive pin stands out of the rear face"),
    (
        math.isclose(SEAT_MAX_FROM_F, SET_NOMINAL + FORWARD_TRAVEL_MAX, abs_tol=1e-9),
        "the printed seat maximum is not the nominal set plus the forward travel",
    ),
    (min(REARWARD_TRAVEL_RANGE) > 0.0, "the collar cannot move rearward of its set"),
):
    if not _ok:
        raise AssertionError(f"MHA-PD-022: {_what}")

BORE_CALLOUT = "REAM THROUGH"
# The slot is cut symmetric about the bore axis (the model's SlotHalfWidth is
# half the width from the axis) and runs along X, square to the ±Y pin line:
# its centre plane carries the fleet's unlocated-feature centring term.  The
# centring prints above the slot depth, which takes one line only (a line
# break in the above compartment never prints, run 20261001T151531763Z); the
# slot's square to the pin line prints under the pin holes' callout.
SLOT_CALLOUT = f"CENTRED ON BORE AXIS \u00b1{POSITION_TOL:.3f}"
SLOT_ORIENTATION = "REAR SLOT 90\u00b0 TO HOLE LINE"
PIN_HOLE_CALLOUT = f"2X REAM THROUGH\n{SLOT_ORIENTATION}"
# The overall, pilot front face to rear face, prints as a .X reference.
OVERALL_LENGTH = LENGTH + PILOT_LENGTH  # 6.9
DRAWING_REFERENCE_PRECISION = 1
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 2:1"

# The fit-up instruction (contract §13.2).  The paper-drive assembly prints
# it, and (R9-29) so does this sheet, below the walls: the collar ships
# unpinned and its setting is the fitter's.  R9-30: the setting band, the
# core drill and the stud cut are phrased once here; MHA-PD-000's steps print
# the same phrases.
# The T24 front face is set FIT_UP_OFFSET_TARGET forward of the T12 front
# face, within FIT_UP_OFFSET_SET_TOL at the setting (§13.2 procedure (4)).
FIT_UP_OFFSET_TARGET = 0.05
FIT_UP_OFFSET_SET_TOL = 0.05
FIT_UP_OFFSET_SET_TEXT = f"{FIT_UP_OFFSET_TARGET:.2f} \u00b1{FIT_UP_OFFSET_SET_TOL:.2f}"
# Procedure (5): the cross-pin hole, drilled through the shaft core at
# assembly to the cross pin's own hole band (R9-11).
CROSS_PIN_DRILL_PHRASE = (
    f"DRILL \u00d8{CROSS_HOLE_DIA:.1f} +{CROSS_HOLE_BAND[0]:.2f}/"
    f"{CROSS_HOLE_BAND[1]:g} THROUGH THE CORE ALONG THE COLLAR'S REAR SLOT"
)
# Procedure (7): a stud end standing proud of the thumbnut's rim is cut this
# far below the rim and re-chamfered 45 degrees to the thread minor (the
# MHA-PD-008 tip form).
STUD_CUT_BELOW_RIM = (0.3, 1.0)
STUD_RECHAMFER_DEG = 45
STUD_CUT_PHRASE = (
    f"CUT {STUD_CUT_BELOW_RIM[0]:.1f} TO {STUD_CUT_BELOW_RIM[1]:.1f} BELOW THE "
    f"RIM, RE-CHAMFER {STUD_RECHAMFER_DEG}\u00b0 TO THE MINOR"
)

# --- The thumbnut on the stud over the whole setting (R9-53, contract §7) ------
# The fitter may leave the T24 seat anywhere from the rearward stop (the
# collar's rear face on F, seat = the collar length) to SEAT_MAX_FROM_F.  The
# nut seats on the pilot's faced front face (R9-70), the fitted pilot length
# in front of the seat.
_TIP_STATION_MIN = TIP_STATION - printed_band_mm(TIP_STATION_PLACES)  # 23.39
_PLAIN_CORE_MAX = PLAIN_CORE + printed_band_mm(PLAIN_CORE_PLACES)  # 7.63
_CORE_LENGTH_MAX = CORE_LENGTH + printed_band_mm(CORE_LENGTH_PLACES)  # 5.38
NUT_LENGTH_MIN = NUT_LENGTH + NUT_LENGTH_LO  # 15.3


def thumbnut_engagement(seat_from_f: float) -> float:
    """Full stud thread inside the nut's full thread, the T24 seat
    ``seat_from_f`` in front of F, at the printed worst case: forward, the
    shortest stud tip (or the deepest cut below the shortest nut's rim) less
    one pitch for its chamfer, inside the rim's countersink, the nut on the
    shortest fitted pilot; rearward, the nut's seat countersink on the longest
    fitted pilot or the stud's full-thread end, whichever lies further
    forward.  Each countersink's loss is counted from the tap drill (R9-63)."""
    rim = seat_from_f + PILOT_LENGTH_FITTED_MIN + NUT_LENGTH_MIN
    tip = min(_TIP_STATION_MIN, rim - STUD_CUT_BELOW_RIM[1])
    front = min(tip - THREAD_PITCH, rim - NUT_FRONT_THREAD_LOSS)
    rear = max(
        seat_from_f + PILOT_LENGTH_FITTED_MAX + NUT_REAR_THREAD_LOSS, _PLAIN_CORE_MAX
    )
    return front - rear


# Each term is a min or max of lines in the seat, so the engagement is concave
# over the travel and least at one of its ends: 21.92 - 2.6225 - 7.6425 = 11.655
# at the rearward stop, 23.39 - 1.27 - 10.6725 = 11.4475 (1.80 D) at the seat
# maximum.
THUMBNUT_ENGAGEMENT_WORST = min(
    thumbnut_engagement(seat) for seat in (LENGTH_MIN, LENGTH_MAX, SEAT_MAX_FROM_F)
)
if THUMBNUT_ENGAGEMENT_WORST < ENGAGEMENT_FLOOR_D * THREAD_MAJOR - 1e-9:
    raise AssertionError(
        f"MHA-PD-013 thumbnut / MHA-PD-008 stud: {THUMBNUT_ENGAGEMENT_WORST:.3f} of full "
        f"thread ({THUMBNUT_ENGAGEMENT_WORST / THREAD_MAJOR:.2f} D) at the worst "
        f"setting, under {ENGAGEMENT_FLOOR_D} D"
    )
# At the rearward stop the nut's seat stands in front of the core's step, so
# its thread runs only on full thread or over the relief, never onto the core
# or a die run-out: 3.87 + 2.75 - 5.38 = 1.24.
NUT_CORE_STEP_AIR = LENGTH_MIN + PILOT_LENGTH_FITTED_MIN - _CORE_LENGTH_MAX
if NUT_CORE_STEP_AIR <= 0.0:
    raise AssertionError(
        f"MHA-PD-013 thumbnut / MHA-PD-008 core step: at the rearward stop the nut "
        f"seat {LENGTH_MIN + PILOT_LENGTH_FITTED_MIN:.3f} reaches the core step "
        f"{_CORE_LENGTH_MAX:.3f} ({NUT_CORE_STEP_AIR:+.3f})"
    )
# Over the relief the nut's smallest minor clears the largest relief:
# (4.978 - 4.51) / 2 = 0.234 radial.
NUT_RELIEF_RADIAL_AIR = (NUT_MINOR_MIN - RELIEF_DIA_MAX) / 2.0
if NUT_RELIEF_RADIAL_AIR <= 0.0:
    raise AssertionError(
        f"MHA-PD-013 thumbnut / MHA-PD-008 thread relief: the nut's 2B minor "
        f"Ø{NUT_MINOR_MIN:.3f} reaches the relief Ø{RELIEF_DIA_MAX:.3f}"
    )

# --- The chain plane in service (contract §13.2, R9-2 / R9-17) ----------------
# Tsubaki's ±1 sprocket offset at every printed corner, floats included.  The
# contract's enumeration sets the pair (T24 against T12, mid-planes) at
# CHAIN_SET_RANGE; in service the crank shaft's end play and the knob's end
# float move the T24 forward of it.  R9-70 adds the T24's own float under the
# thumbnut, forward only (the collar body is its rear stop), and K-1 sets the
# knob's end float on a feeler at fit-up, so it no longer carries the
# journal, ring and hub-to-boss bands (contract: 0..0.35).  R9-71: the
# MHA-VN-049 spring holds the arm on the MHA-PD-020 spacer, which is pressed on the
# MHA-VN-041 shoulder, so the hanger has no end play and its tilt is fixed in
# the bar's frame, where the fit-up reads it:
# -0.3103 - 0.25 - 0.25 - 0.15 = -0.9603 .. +0.05.
CHAIN_OFFSET_LIMIT = 1.0
CHAIN_SET_RANGE = (-0.3103, 0.05)
CRANK_END_PLAY_MAX = 0.25
HANGER_AXIAL_PLAY_MAX = 0.0
KNOB_END_FLOAT_MAX = END_FLOAT + END_FLOAT_SET_TOL  # 0.25
CHAIN_OFFSET_IN_SERVICE = (
    CHAIN_SET_RANGE[0] - CRANK_END_PLAY_MAX - KNOB_END_FLOAT_MAX - max(T24_FLOAT_RANGE),
    CHAIN_SET_RANGE[1] + HANGER_AXIAL_PLAY_MAX,
)
CHAIN_OFFSET_MARGIN = CHAIN_OFFSET_LIMIT - max(map(abs, CHAIN_OFFSET_IN_SERVICE))
if CHAIN_OFFSET_MARGIN < 0.0:
    raise AssertionError(
        f"chain plane in service {CHAIN_OFFSET_IN_SERVICE[0]:+.4f}.."
        f"{CHAIN_OFFSET_IN_SERVICE[1]:+.4f} leaves Tsubaki's "
        f"±{CHAIN_OFFSET_LIMIT} ({CHAIN_OFFSET_MARGIN:+.4f})"
    )

# The pilot's length: faced at assembly, its requirement printed with the
# dimension; the sheet appends the step that sets it.
PILOT_LENGTH_CALLOUT = (
    f"SET AT ASSEMBLY {PILOT_LENGTH_FITTED_MIN:.2f}-{PILOT_LENGTH_FITTED_MAX:.2f}"
    "\nFACED TO FIT"
)
PILOT_PROUD_TEXT = f"{PILOT_PROUD_RANGE[0]:.2f} TO {PILOT_PROUD_RANGE[1]:.2f}"
# The widest line the sheet's notes block holds (its layout test).
FIT_UP_NOTE_WIDTH = 66
FIT_UP_NOTE = "\n".join(
    textwrap.wrap(
        "COLLAR SUPPLIED UNPINNED, ITS PILOT LONG. AT ASSEMBLY FACE THE PILOT "
        f"{PILOT_PROUD_TEXT} PROUD OF THE T24 FRONT FACE, THEN SET THE COLLAR "
        "ON THE SHAFT SO "
        f"THAT THE T24 FRONT FACE LIES {FIT_UP_OFFSET_SET_TEXT} FORWARD OF THE "
        "T12 FRONT FACE WITH THE ARM AND THE CRANK SHAFT PULLED FORWARD AND THE "
        f"KNOB SHAFT PUSHED REARWARD; CLAMP, {CROSS_PIN_DRILL_PHRASE}, FIT "
        "1/16 \u00d7 9/16 SPRING PIN IN THE SLOT. COLLAR REAR FACE TO 12T FRONT "
        f"FACE 0 MIN. T24 SEAT {SEAT_MAX_FROM_F:.2f} MAX IN FRONT OF 12T FRONT "
        "FACE. THE THUMBNUT SEATS ON THE PILOT, THE T24 FREE UNDER IT. STUD END "
        f"PROUD OF THE THUMBNUT RIM: {STUD_CUT_PHRASE}.",
        width=FIT_UP_NOTE_WIDTH,
        break_on_hyphens=False,
    )
)

# The sheet states the approved shortfalls (contract §10.1); the ruling IDs
# stay here.
# Named exception: MHA-PD-022 collar rim (drawing-simplicity-policy.md, "Named exceptions").
# Named exception: MHA-PD-022 pilot wall (drawing-simplicity-policy.md, "Named exceptions").
# Named exception: MHA-PD-022 slot floor to front face (drawing-simplicity-policy.md, "Named exceptions").
DRAWING_NOTES = "\n".join(
    (
        f"DRIVE-PIN HOLE TO COLLAR RIM {DRIVE_PIN_COLLAR_RIM_WORST:.2f} MIN.",
        f"PILOT WALL {PILOT_WALL_WORST:.2f} MIN.",
        f"SLOT FLOOR TO FRONT FACE {SLOT_FLOOR_WALL_WORST:.2f} MIN.",
        f"SUPPLY THE PILOT {PILOT_BLANK_LENGTH_MIN:.2f} MIN LONG.",
        FIT_UP_NOTE,
    )
)
