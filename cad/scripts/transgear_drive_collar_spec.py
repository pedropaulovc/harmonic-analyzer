r"""MHA-152 transgear-drive-collar: the brass drive collar on the knob shaft.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  ``build_transgear_drive_collar`` marks and tolerances exactly
``DRAWING_DIMENSIONS`` / ``DRAWING_PRECISION`` on the model and
``draw_transgear_drive_collar`` keeps exactly the same names.

Contract §1.2 (round 10): a Ø17.5 × 4.000 brass collar reamed Ø6.350 to
slide on the knob shaft's plain Ø6.35 core (MHA-078).  It is set on the core
at assembly and pinned by the MHA-154 spring pin, drilled through the core
along the collar's diametral rear slot and lying in it, so the slot walls
carry the drive (R9-6).  The front face is the removable T24's (MHA-081)
seat: the Ø10.00 × 1.90 pilot enters the wheel's Ø10.3 bore, two MHA-155
dowels pressed through reamed holes on the Ø14 circle drive the wheel, and
the thumbnut (MHA-126) clamps it on this face.

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

from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from crankshaft_spec import (
    DRIVE_PIN_HOLE_BAND,
    DRIVE_PIN_LENGTH_GRADE,
    DRIVE_PIN_OFFSET_PLACES,
    DRIVE_PIN_OFFSET_TOL,
    SPIGOT_DIA_BAND,
)
from transgear_collar_cross_pin_spec import HOLE_BAND as CROSS_HOLE_BAND
from transgear_collar_cross_pin_spec import HOLE_DIA as CROSS_HOLE_DIA
from transgear_knob_drive_pin_spec import LENGTH as PIN_LENGTH
from transgear_knob_drive_pin_spec import PROUD_RANGE, THINNEST_PLATE
from transgear_knob_shaft_spec import (
    CORE_DIA,
    CORE_DIA_BAND,
    DIE_RUNOUT_MAX,
    PLAIN_CORE,
    PLAIN_CORE_PLACES,
)
from transgear_removable_spec import BORE_DIA as WHEEL_BORE_DIA
from transgear_removable_spec import (
    DRIVE_PIN_HOLE_DIA,
    DRIVE_PIN_PROUD,
    PLATE,
    SEAT_SPIGOT_DIA,
    SEAT_SPIGOT_RIM,
)
from transgear_removable_spec import PIN_CIRCLE_RADIUS as _WHEEL_PIN_CIRCLE_RADIUS

# The policy's wall floor for a named shortfall (the 2.0 target's floor).
WALL_FLOOR = 1.5

# --- Body: Ø17.5 × 4.000, the knob shaft's half of the seat interface --------
LENGTH = 4.0
LENGTH_PLACES = 3  # the rearward travel SET - L (contract §13)
OD = SEAT_SPIGOT_DIA  # 17.5, the crank spigot's seat
# The removables swap between shafts: the crank spigot's functional band.
OD_BAND = SPIGOT_DIA_BAND  # (upper, lower) = (0, -0.10)
OD_PLACES = 2

# --- Pilot on the front face, inside the T24's Ø10.3 bore (ruling 5) ----------
PILOT_DIA = 10.0
PILOT_DIA_BAND = (0.0, -0.10)
PILOT_DIA_PLACES = 2
PILOT_LENGTH = 1.9
PILOT_LENGTH_PLACES = 2

# --- Bore: reamed through, sliding on the plain core --------------------------
BORE_DIA = CORE_DIA  # 6.35
BORE_DIA_BAND = (0.010, 0.0)
BORE_DIA_PLACES = 3

# --- Diametral rear slot along local X for the MHA-154 spring pin (R9-6) ------
SLOT_WIDTH = 1.7
SLOT_WIDTH_BAND = (0.10, 0.0)
SLOT_DEPTH = 1.8
SLOT_DEPTH_BAND = (0.10, 0.0)
SLOT_PLACES = 1
SLOT_FLOOR_Z = LENGTH - SLOT_DEPTH  # 2.2

# --- Drive-pin holes: reamed THROUGH for the MHA-155 press (the crank's twin) -
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
    "CollarProfile": {"CollarDia"},
    "Collar": {"CollarLength"},
    "PilotProfile": {"PilotDia"},
    "Pilot": {"PilotLength"},
    "BoreProfile": {"BoreDia"},
    "SlotProfile": {"SlotWidth", "SlotDepth"},
    "PinHoleProfile": {"PinPosDia", "PinPosY", "PinNegY"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "CollarProfile": {"CollarDia": OD_PLACES},
    "Collar": {"CollarLength": LENGTH_PLACES},
    "PilotProfile": {"PilotDia": PILOT_DIA_PLACES},
    "Pilot": {"PilotLength": PILOT_LENGTH_PLACES},
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
    raise AssertionError("every marked MHA-152 dimension needs authored places")
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}

LENGTH_TOL = printed_band_mm(LENGTH_PLACES)  # 0.13
LENGTH_MIN = round(LENGTH - LENGTH_TOL, 6)  # 3.87
LENGTH_MAX = round(LENGTH + LENGTH_TOL, 6)  # 4.13
PILOT_LENGTH_MAX = round(PILOT_LENGTH + printed_band_mm(PILOT_LENGTH_PLACES), 6)  # 2.41
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
# 7.0 - 1.19 - 0.85 = 4.96; less the offset 0.025, the slot's +0.10 half
# 0.05 and its centring 0.065: 4.82.
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
# The pilot's front face stays behind the T24's front face, where the
# thumbnut bears: 2.8 - 1.9 = 0.9 nominal, 2.7 - 2.41 = 0.29 worst.
PILOT_FACE_INSET = PLATE - PILOT_LENGTH
PILOT_FACE_INSET_WORST = THINNEST_PLATE - PILOT_LENGTH_MAX


# --- Drive pins pressed through to a stop (MHA-155) ------------------------------
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
# would reach the die run-out (below).
SET_NOMINAL = 6.2
FORWARD_TRAVEL_MAX = 0.7
SEAT_MAX_FROM_F = 6.90
REARWARD_TRAVEL_NOMINAL = SET_NOMINAL - LENGTH  # 2.2
REARWARD_TRAVEL_RANGE = (SET_NOMINAL - LENGTH_MAX, SET_NOMINAL - LENGTH_MIN)

# --- The core's cross-pin hole against the die run-out (R9-18, R9-22) ------------
# Collar frame: the seat at z 0 and F at z = the seat's setting in front of F,
# so the full thread ends PLAIN_CORE in front of F, 0.13 nearer on the
# shortest printed plain core.  The hole is drilled along the slot at that
# setting, its axis one hole radius above the slot floor (2.2 + 0.8 = 3.0);
# its front edge comes forward by the hole's upper limit, the slot's +0.10,
# the centring 0.065 and the collar's .XXX length:
# 3.0 - 0.825 - 0.10 - 0.065 - 0.13 = 1.88.  The fitter may set the seat
# anywhere up to SEAT_MAX_FROM_F, so the hole must clear the run-out there.
CROSS_HOLE_Z = SLOT_FLOOR_Z + CROSS_HOLE_DIA / 2.0
CROSS_HOLE_FRONT_Z_WORST = (
    CROSS_HOLE_Z
    - (CROSS_HOLE_DIA + max(CROSS_HOLE_BAND)) / 2.0
    - max(SLOT_DEPTH_BAND)
    - POSITION_TOL
    - LENGTH_TOL
)


def core_hole_runout_margin(runout: float, seat_from_f: float) -> float:
    """Solid core between a die run-out ``runout`` long and the cross hole's
    front edge, the hole drilled with the seat ``seat_from_f`` in front of F
    (negative: the hole meets the run-out)."""
    thread_end_z = seat_from_f - PLAIN_CORE + printed_band_mm(PLAIN_CORE_PLACES)
    return CROSS_HOLE_FRONT_Z_WORST - (thread_end_z + runout)


# At the furthest setting the sheet accepts:
# 1.88 - (6.90 - 6.5 + 0.13 + 1.27) = 0.08 (0.78 at the nominal 6.2).
CORE_HOLE_RUNOUT_MARGIN = core_hole_runout_margin(DIE_RUNOUT_MAX, SEAT_MAX_FROM_F)

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
    (
        PILOT_FACE_INSET_WORST > 0.0,
        "the pilot reaches the T24's front face (the thumbnut's seat)",
    ),
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
    (
        CORE_HOLE_RUNOUT_MARGIN > 0.0,
        "the core's cross-pin hole meets the die run-out at the furthest setting",
    ),
):
    if not _ok:
        raise AssertionError(f"MHA-152: {_what}")

BORE_CALLOUT = "REAM THROUGH"
PIN_HOLE_CALLOUT = "2X REAM THROUGH"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 2:1"

# The fit-up instruction (contract §13.2).  The paper-drive assembly prints
# it, and (R9-29) so does this sheet, below the walls: the collar ships
# unpinned and its setting is the fitter's.  R9-30: the setting band, the
# core drill and the stud cut are phrased once here; MHA-A06's steps print
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
# MHA-078 tip form).
STUD_CUT_BELOW_RIM = (0.3, 1.0)
STUD_RECHAMFER_DEG = 45
STUD_CUT_PHRASE = (
    f"CUT {STUD_CUT_BELOW_RIM[0]:.1f} TO {STUD_CUT_BELOW_RIM[1]:.1f} BELOW THE "
    f"RIM, RE-CHAMFER {STUD_RECHAMFER_DEG}\u00b0 TO THE MINOR"
)
# The widest line the sheet's notes block holds (its layout test).
FIT_UP_NOTE_WIDTH = 66
FIT_UP_NOTE = "\n".join(
    textwrap.wrap(
        "COLLAR SUPPLIED UNPINNED. AT ASSEMBLY SET THE COLLAR ON THE SHAFT SO "
        f"THAT THE T24 FRONT FACE LIES {FIT_UP_OFFSET_SET_TEXT} FORWARD OF THE "
        "T12 FRONT FACE WITH THE ARM AND THE CRANK SHAFT PULLED FORWARD AND THE "
        f"KNOB SHAFT PUSHED REARWARD; CLAMP, {CROSS_PIN_DRILL_PHRASE}, FIT "
        "1/16 \u00d7 9/16 SPRING PIN IN THE SLOT. COLLAR REAR FACE TO 12T FRONT "
        f"FACE 0 MIN. T24 SEAT {SEAT_MAX_FROM_F:.2f} MAX IN FRONT OF 12T FRONT "
        f"FACE. STUD END PROUD OF THE THUMBNUT RIM: {STUD_CUT_PHRASE}.",
        width=FIT_UP_NOTE_WIDTH,
        break_on_hyphens=False,
    )
)

# The sheet states the approved shortfalls (contract §10.1); the ruling IDs
# stay here.
# Named exception: MHA-152 collar rim (drawing-simplicity-policy.md, "Named exceptions").
# Named exception: MHA-152 pilot wall (drawing-simplicity-policy.md, "Named exceptions").
# Named exception: MHA-152 slot floor to front face (drawing-simplicity-policy.md, "Named exceptions").
DRAWING_NOTES = "\n".join(
    (
        f"DRIVE-PIN HOLE TO COLLAR RIM {DRIVE_PIN_COLLAR_RIM_WORST:.2f} MIN.",
        f"PILOT WALL {PILOT_WALL_WORST:.2f} MIN.",
        f"SLOT FLOOR TO FRONT FACE {SLOT_FLOOR_WALL_WORST:.2f} MIN.",
        FIT_UP_NOTE,
    )
)
