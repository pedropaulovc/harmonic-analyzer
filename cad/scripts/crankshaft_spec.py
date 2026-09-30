r"""Crankshaft manufacturing contract.

The v36 MHA-016 bore carries integral running lands again; the pinion sits
SEAT_FEELER_MM off its north boss face. All axial stations are measured from
the dome root in the model and printed from the far end; W15 uses the
printed worst cases.  Behind the crank hub an integral collar carries the
removable sprocket MHA-081's seat and its two pressed drive pins (ch. 23).
"""

from __future__ import annotations

import math

import _config
from _hole_spec import HoleSpec, drill_process
from _gtol_spec import CylinderFace, PlanarFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from cone_pivot_post_spec import CRANK_BORE_DIA as JOURNAL_BORE_DIA
from cone_pivot_post_spec import RUNNING_BORE_BAND as JOURNAL_BORE_BAND
import crank_pinion_spec
import crank_seat_drive_pin_spec
import transgear_removable_spec
from crank_hub_geometry import (
    CRANK_FACE_SHIFT,
    FIDUCIAL_MODEL_DEPTH,  # noqa: F401 -- re-exported to the drawing contract
    FIDUCIAL_MODEL_DIA,  # noqa: F401 -- re-exported to the drawing contract
    HUB_LENGTH,
    HUB_LENGTH_TOL,
    SERVICE_PIN_STATION,
    SHAFT_DIA,
    SHAFT_DIA_BAND,
    SHAFT_DOME_HEIGHT,  # noqa: F401 -- re-exported to the drawing contract
    SHAFT_FIDUCIAL_RADIUS,  # noqa: F401 -- re-exported to the drawing contract
)


# The restored v36 post's north boss face, measured from the shifted dome root.
# Keep this independent of the post's rebuild closure; assembly checks the mate.
POST_BORE_END = 104.789505572 + CRANK_FACE_SHIFT
SEAT_PINION = POST_BORE_END + crank_pinion_spec.SEAT_FEELER_MM
if SEAT_PINION <= POST_BORE_END:
    raise AssertionError("the 16T seat must clear the restored post boss north face")
# W15: the far end remains recessed inside the pinion's shorter boss. Its
# one-place length is floored so the printed nominal is the model's and an
# accepted shaft cannot be longer than the model. The pinion spec reserves
# enough boss for the retained pin at its worst printed limit.
SHAFT_LENGTH = crank_pinion_spec.floor_to_places(
    SEAT_PINION
    + crank_pinion_spec.OVERALL_LENGTH
    - crank_pinion_spec.SHAFT_END_RECESS_MIN,
    crank_pinion_spec.SHAFT_LENGTH_PLACES,
)  # floored to the drawing's one-place nominal
SHAFT_END_RECESS = SEAT_PINION + crank_pinion_spec.OVERALL_LENGTH - SHAFT_LENGTH
if not (
    crank_pinion_spec.SHAFT_END_RECESS_MIN - 1e-9
    <= SHAFT_END_RECESS
    <= crank_pinion_spec.SHAFT_END_RECESS_MAX + 1e-9
):
    raise AssertionError(
        f"crankshaft end recess {SHAFT_END_RECESS:.4f} left the range the 16T boss "
        "was sized for"
    )
# Unilateral: a long shaft would stand proud of the boss, and a short one only
# deepens the recess and shortens the pin's wall, which build_drive_train_
# assembly's worst-case stacks carry.  Printed on Depth from the model.
# W15-SHAFT-BAND (Main 2026-09-25): preserve unilateral +0/-0.4;
# the normal title-block .X +/-0.8 would leave the shortened boss's
# pin wall below 2.0 and make the shaft end stand proud at print-worst.
SHAFT_LENGTH_BAND = (0.00, -crank_pinion_spec.SHAFT_LENGTH_SHORT_MM)

# Integral lands run directly in the restored post bore. Derive the journal
# from the named running fit and the bore's published +0.005/-0.025 band.
_RUNNING_CLEARANCE = tuple(_config.fit("shaft_in_bushing")["diametral_clearance_mm"])
JOURNAL_DIA = JOURNAL_BORE_DIA + JOURNAL_BORE_BAND[1] - _RUNNING_CLEARANCE[0]
JOURNAL_DIA_BAND = (
    0.0,
    round(JOURNAL_BORE_DIA + JOURNAL_BORE_BAND[0] - _RUNNING_CLEARANCE[1] - JOURNAL_DIA, 3),
)
JOURNAL_CLEARANCE = JOURNAL_BORE_DIA - JOURNAL_DIA
JOURNAL_START = 32.755105572 + CRANK_FACE_SHIFT
_JOURNAL_CLEARANCE_LOW = JOURNAL_BORE_BAND[1] - JOURNAL_DIA_BAND[0] + JOURNAL_CLEARANCE
_JOURNAL_CLEARANCE_HIGH = JOURNAL_BORE_BAND[0] - JOURNAL_DIA_BAND[1] + JOURNAL_CLEARANCE
if not (
    _RUNNING_CLEARANCE[0] - 1e-9
    <= _JOURNAL_CLEARANCE_LOW
    <= _JOURNAL_CLEARANCE_HIGH
    <= _RUNNING_CLEARANCE[1] + 1e-9
):
    raise AssertionError("integral journal and post bore exceed the running-fit clearance band")

# Every axial station prints from the FAR END at one place (policy rule 7), and
# each one below is chosen to print EXACTLY, so its printed row IS its limit
# and no rounding of a printed nominal can eat a margin.  Local stations (from
# the dome root, where the features measure) follow from the far end.
STATION_PLACES = 1
STATION_ROW = crank_pinion_spec.printed_band_mm(STATION_PLACES)  # 0.8


def local_station(far_end_station: float) -> float:
    """Dome-root station of a feature printed ``far_end_station`` from the far end."""
    return SHAFT_LENGTH - far_end_station


# RULING (b), Main 2026-09-26 (#906): the 16T sits on a Ø9.0 seat, a step down
# from the 3/8 in shaft at the far end's side of the post bore.  The pinion is
# still set on its feeler and pinned, so the step never locates it; the step
# only has to stay out from under the pinion's nominal seat.  An accepted step
# can print 0.8 north of its nominal, and an inside corner up to the title
# block's edge-break radius stands the pinion's bore edge off it by that much
# more; together they must stay inside the seat gap's north range, which the
# pin-wall and recess stacks already carry.  So the step sits south of the
# seat, not at it: at SEAT_PINION it would print to 1.05 of standoff.
PINION_SEAT_DIA = crank_pinion_spec.SEAT_DIA
PINION_SEAT_DIA_BAND = SHAFT_DIA_BAND  # the through shaft's turned-fit band
PINION_SEAT_STATION = 25.9  # far end to the step
SEAT_STEP = local_station(PINION_SEAT_STATION)
STEP_CORNER_RADIUS_MAX = 0.25  # the title block's R0.25 edge break
SEAT_STEP_STANDOFF_WORST = SEAT_STEP + STATION_ROW + STEP_CORNER_RADIUS_MAX - SEAT_PINION
SEAT_GAP_NORTH_RANGE = crank_pinion_spec.SEAT_GAP_MAX_MM - crank_pinion_spec.SEAT_FEELER_MM
if SEAT_STEP_STANDOFF_WORST > SEAT_GAP_NORTH_RANGE + 1e-9:
    raise AssertionError(
        f"Ø{PINION_SEAT_DIA} seat step stands the 16T off {SEAT_STEP_STANDOFF_WORST:.3f} "
        f"at print-worst, past the seat gap's {SEAT_GAP_NORTH_RANGE:.2f} north range"
    )

# Restore the two bearing lands and the relieved middle. Printed stations
# remain baseline dimensions from the faced far end, at the routine .X band.
WEB_TARGET_MM = 2.0
JOURNAL_INBOARD_STATION = 29.5
JOURNAL_END = local_station(JOURNAL_INBOARD_STATION)
JOURNAL_LENGTH = JOURNAL_END - JOURNAL_START
# Both ends print from the far end, so the web is their printed difference.
STEP_WEB_WORST = JOURNAL_INBOARD_STATION - PINION_SEAT_STATION - 2.0 * STATION_ROW
RELIEF_DIA = 10.4
RELIEF_DIA_PLACES = 1
RELIEF_OUTBOARD_STATION = 82.8
RELIEF_INBOARD_STATION = 44.5
RELIEF_START = local_station(RELIEF_OUTBOARD_STATION)
RELIEF_END = local_station(RELIEF_INBOARD_STATION)
RELIEF_LENGTH = RELIEF_END - RELIEF_START
_RELIEF_ROW = crank_pinion_spec.printed_band_mm(RELIEF_DIA_PLACES)
_OUTBOARD_START_LOWER, _ = crank_pinion_spec.printed_deviations(
    SHAFT_LENGTH - JOURNAL_START, STATION_PLACES
)
JOURNAL_LAND_L_OVER_D_MIN = 1.0
JOURNAL_LANDS_WORST = (
    SHAFT_LENGTH - JOURNAL_START + _OUTBOARD_START_LOWER
    - RELIEF_OUTBOARD_STATION - STATION_ROW,
    RELIEF_INBOARD_STATION - JOURNAL_INBOARD_STATION - 2.0 * STATION_ROW,
)
if STEP_WEB_WORST < WEB_TARGET_MM:
    raise AssertionError("journal-to-pinion-seat web falls below its printed worst-case floor")
if JOURNAL_END + STATION_ROW >= POST_BORE_END:
    raise AssertionError("the journal must stay inside the restored post bore at print-worst")
if not RELIEF_START < RELIEF_END < JOURNAL_END:
    raise AssertionError("the relieved middle must stay within the integral journal lands")
if RELIEF_DIA + _RELIEF_ROW >= JOURNAL_DIA + JOURNAL_DIA_BAND[1]:
    raise AssertionError("relief must remain below the journal at print-worst")
if RELIEF_DIA - _RELIEF_ROW <= SHAFT_DIA + SHAFT_DIA_BAND[0]:
    raise AssertionError("relief must stand proud of the through shaft at print-worst")
if min(JOURNAL_LANDS_WORST) < JOURNAL_LAND_L_OVER_D_MIN * JOURNAL_DIA:
    raise AssertionError("the integral journal lands fall below their printed L/D floor")
# W15's printed worst cases are pure data, so they can be checked without
# importing an assembly builder. The retention hole is laid out at boss middle.
PINION_PIN_STATION_Y = SEAT_PINION + crank_pinion_spec.PIN_STATION
PINION_PIN_EDGE_TO_END = SHAFT_LENGTH - PINION_PIN_STATION_Y - crank_pinion_spec.PIN_DIA / 2.0
PINION_PIN_EDGE_STACK = {
    "nominal": PINION_PIN_EDGE_TO_END,
    "shaft length": SHAFT_LENGTH_BAND[1],
    "seat gap": -SEAT_GAP_NORTH_RANGE,
    "boss mid-length": -(crank_pinion_spec.W15_FACE_ALLOWANCE_MM + crank_pinion_spec.OVERALL_LENGTH_GRADE_MM) / 2.0,
    "pin layout": -crank_pinion_spec.PIN_STATION_LAYOUT_ALLOWANCE_MM,
    "drill oversize": -float(_config.title_block("drilled_hole")["plus_mm"]) / 2.0,
}
PINION_RECESS_STACK = {
    "nominal": SHAFT_END_RECESS,
    "pinion overall length": -crank_pinion_spec.OVERALL_LENGTH_GRADE_MM,
    "seat gap": 0.0,
    "shaft length": -SHAFT_LENGTH_BAND[0],
}
if sum(PINION_PIN_EDGE_STACK.values()) < crank_pinion_spec.PIN_EDGE_MIN_WORST:
    raise AssertionError("W15 pin edge-to-shaft-end wall falls below its print-worst floor")
if sum(PINION_RECESS_STACK.values()) < crank_pinion_spec.SHAFT_END_RECESS_MIN_WORST:
    raise AssertionError("W15 shaft end protrudes past its print-worst boss recess floor")
_BOSS_PRINT_STEP = 10.0 ** -crank_pinion_spec.BOSS_LENGTH_PLACES
_SHORTER_SHAFT_LENGTH = crank_pinion_spec.floor_to_places(
    SEAT_PINION
    + crank_pinion_spec.OVERALL_LENGTH
    - _BOSS_PRINT_STEP
    - crank_pinion_spec.SHAFT_END_RECESS_MIN,
    crank_pinion_spec.SHAFT_LENGTH_PLACES,
)
_SHORTER_PIN_EDGE_WORST = (
    sum(PINION_PIN_EDGE_STACK.values())
    + _SHORTER_SHAFT_LENGTH
    - SHAFT_LENGTH
    + _BOSS_PRINT_STEP / 2.0
)
if _SHORTER_PIN_EDGE_WORST >= crank_pinion_spec.PIN_EDGE_MIN_WORST:
    raise AssertionError(
        f"a boss one print step shorter still holds the W15 pin-edge floor "
        f"({_SHORTER_PIN_EDGE_WORST:.3f} >= {crank_pinion_spec.PIN_EDGE_MIN_WORST:.2f}); "
        "the pinion boss is not the shortest feasible"
    )
# MHA-024 hub-to-shaft cross-hole behind the crank arm.
PIN_HOLE_SPEC = HoleSpec("drilled_number", "#9")
PIN_HOLE_HEIGHT = SERVICE_PIN_STATION

# --- ch. 23 crank seat (CONTRACT-crank): the integral collar replaces the
# plain 5-mm T12 band.  Its front is a Ø17.5 seat spigot whose face is
# MHA-081's seat, at the removable's SEAT_FACE_Z, stepping up to the Ø20.6
# collar body; the turned MHA-172 thrust washer rides behind the body to the
# post boss south face.  The #25 plates wrapping the T12 pass over the spigot
# and in front of the body's front face: long enough that a bought chain's
# envelope, floated rearmost on the thinnest wheel
# (transgear_removable_spec.chain_reach_rear, 3.59 behind the seat), keeps
# air to the body at the spigot's print-worst length (the drive train asserts
# it, with the radial air for the CAD link and a real ANSI plate).  The seat
# diameter is the interface both shafts share, so it is the removable spec's.
SPIGOT_DIA = transgear_removable_spec.SEAT_SPIGOT_DIA
SPIGOT_LENGTH = 4.0
COLLAR_DIA = 20.6
COLLAR_LENGTH = 8.5  # seat face to rear face, spigot included
# Local stations from the dome root (the crank face, machine -183.0 as the
# drive train's CRANK_FACE_Z): 30.5 behind it is SEAT_FACE_Z -152.5, which
# build_drive_train_assembly asserts from both sides.
SEAT_COLLAR = 30.5
SPIGOT_END = SEAT_COLLAR + SPIGOT_LENGTH  # the body's front face, -148.5
COLLAR_REAR = SEAT_COLLAR + COLLAR_LENGTH
# Two pressed MHA-173 dowels on the wheel's pin circle at its +/-Y holes,
# which the placed shaft (local z = machine -y) carries on local -/+Z.  The
# pins' pressed ends bear on the blind holes' flat floor, so the depth is set
# by the proud length the wheel needs.
if transgear_removable_spec.PIN_HOLE_ANGLES_DEG != (90.0, 270.0):
    raise AssertionError("the drive-pin holes are laid out on local +/-Z only")
DRIVE_PIN_CIRCLE_RADIUS = transgear_removable_spec.PIN_CIRCLE_RADIUS
DRIVE_PIN_HOLE_DIA = transgear_removable_spec.DRIVE_PIN_HOLE_DIA
DRIVE_PIN_DEPTH = crank_seat_drive_pin_spec.PRESS_DEPTH  # 3.95
DRIVE_PIN_FLOOR = SEAT_COLLAR + DRIVE_PIN_DEPTH
if not SEAT_COLLAR < SPIGOT_END < COLLAR_REAR:
    raise AssertionError("the seat spigot must end inside the collar")
if not SEAT_COLLAR < DRIVE_PIN_FLOOR < COLLAR_REAR:
    raise AssertionError("the blind drive-pin holes must end inside the collar")
_PIN_HOLE_OUTER_R = DRIVE_PIN_CIRCLE_RADIUS + DRIVE_PIN_HOLE_DIA / 2.0
if not _PIN_HOLE_OUTER_R < SPIGOT_DIA / 2.0 < COLLAR_DIA / 2.0:
    raise AssertionError("the spigot must enclose the pin holes, inside the body")

# Functional bands (policy rule 12), each at the places that print it:
# - The two collar faces print from the far end like every station, but at
#   .X the seat face could come 0.8 + the Depth's 0.4 toward the crank and
#   close the contracted 0.7 air between the hub's rear face and the wheel,
#   and the rear face could eat the washer's 0.25 float.  +/-0.10 at .XX.
# - The spigot diameter is held under nominal, (0, -0.10) at .XX: over it
#   the ANSI #25 plates wrapping the T12 lose their 0.15 radial air, under
#   it the rim to the pin holes thins (DRIVE_PIN_SPIGOT_RIM_WORST).
# - The spigot's length prints from the seat face, not the far end, so the
#   body's front face rides with the wheel and the chain: +/-0.05 at .XX
#   keeps a bought chain's envelope clear of it.
# - The collar body OD is not a seat: +/-0.10 at .XX (it sets the washer's
#   bearing ring against the post boss).
# - The MHA-081 holes (PIN_HOLE_DIA) slip over the pins with 0.119 diametral
#   clearance, which absorbs the pin spacing error of BOTH parts; each pin
#   located +/-0.025 from the axis spends 0.05 of it here, leaving the
#   wheel the same share.  Printed at .XXX.
# - Pressed to the floor, the pin stands PROUD = LENGTH - depth: the depth
#   band plus the dowel's +/-0.010 in length grade must keep the tip clear
#   of the crank hub and engaged in the wheel.  +/-0.10 at .XX.
COLLAR_STATION_PLACES = 2
COLLAR_STATION_TOL = 0.10
COLLAR_DIA_TOL = 0.10
SPIGOT_DIA_BAND = (0.0, -0.10)
SPIGOT_LENGTH_TOL = 0.05
DRIVE_PIN_OFFSET_PLACES = transgear_removable_spec.DRIVE_PIN_OFFSET_PLACES
DRIVE_PIN_OFFSET_TOL = transgear_removable_spec.DRIVE_PIN_OFFSET_TOL
DRIVE_PIN_DEPTH_TOL = 0.10
# Local (dome-root) deviations of the two faces as (upper, lower): a station
# printed from the far end moves by its own band plus the Depth's.  The drive
# train's hub-air and washer-float stacks read these.
SEAT_COLLAR_BAND = (
    SHAFT_LENGTH_BAND[0] + COLLAR_STATION_TOL,
    SHAFT_LENGTH_BAND[1] - COLLAR_STATION_TOL,
)
COLLAR_REAR_BAND = SEAT_COLLAR_BAND
# Reamed for a light press of the stock hardened 3/32 dowel (its catalogue
# diameter tolerance is crank_seat_drive_pin_spec.DIA_BAND_IN).
DRIVE_PIN_HOLE_BAND = (0.000, -0.010)
_DOWEL_OD = tuple(
    crank_seat_drive_pin_spec.DIA + inch * crank_seat_drive_pin_spec.MM_PER_IN
    for inch in crank_seat_drive_pin_spec.DIA_BAND_IN
)
# The stock dowel's length grade, +/-0.010 in (the knob shaft's MHA-155 is the
# same 98381A family and reads it here too).
DRIVE_PIN_LENGTH_GRADE = 0.010 * transgear_removable_spec.MM_PER_IN
DRIVE_PIN_PRESS_INTERFERENCE = (
    _DOWEL_OD[0] - (DRIVE_PIN_HOLE_DIA + DRIVE_PIN_HOLE_BAND[0]),
    _DOWEL_OD[1] - (DRIVE_PIN_HOLE_DIA + DRIVE_PIN_HOLE_BAND[1]),
)
if min(DRIVE_PIN_PRESS_INTERFERENCE) <= 0.0:
    raise AssertionError("the drive-pin hole band loses the press at its upper limit")
_SPIGOT_R_WORST = (SPIGOT_DIA + SPIGOT_DIA_BAND[1]) / 2.0
_PIN_HOLE_OUTER_R_WORST = (
    DRIVE_PIN_CIRCLE_RADIUS
    + DRIVE_PIN_OFFSET_TOL
    + (DRIVE_PIN_HOLE_DIA + DRIVE_PIN_HOLE_BAND[0]) / 2.0
)
# Pin hole to the spigot rim: under the 1.5 floor at nominal (0.56) and at
# the printed worst case, rounded DOWN so a sheet never states more rim than
# the limits give.
DRIVE_PIN_SPIGOT_RIM = transgear_removable_spec.SEAT_SPIGOT_RIM
DRIVE_PIN_SPIGOT_RIM_WORST = (
    math.floor((_SPIGOT_R_WORST - _PIN_HOLE_OUTER_R_WORST) * 100.0 + 1e-9) / 100.0
)
if DRIVE_PIN_SPIGOT_RIM_WORST <= 0.0:
    raise AssertionError("the drive-pin holes break out of the spigot at print-worst")
DRIVE_PIN_SPACING_ERROR_MAX = 2.0 * DRIVE_PIN_OFFSET_TOL
if (
    2.0 * DRIVE_PIN_SPACING_ERROR_MAX
    >= transgear_removable_spec.PIN_HOLE_DIA - _DOWEL_OD[1]
):
    raise AssertionError("shaft + wheel pin spacing error exceeds the slip clearance")
_PROUD = crank_seat_drive_pin_spec.LENGTH - DRIVE_PIN_DEPTH
DRIVE_PIN_PROUD_RANGE = (
    _PROUD - DRIVE_PIN_DEPTH_TOL - DRIVE_PIN_LENGTH_GRADE,
    _PROUD + DRIVE_PIN_DEPTH_TOL + DRIVE_PIN_LENGTH_GRADE,
)  # 2.046 .. 2.754
if not 0.0 < DRIVE_PIN_PROUD_RANGE[0] < DRIVE_PIN_PROUD_RANGE[1]:
    raise AssertionError("a pressed drive pin sinks below the seat face at print-worst")


# What the proud tips can meet.  Nothing bears on the T12's front face: the
# first thing in front of it is the crank hub's rear face (the end face of
# its Ø16.5 relief, which covers the pin circle), the drive train's gap B
# away.  The hub is set flush with the dome root, so its rear face sits at
# local HUB_LENGTH +/-HUB_LENGTH_TOL.  The longest pin stands past the
# THINNEST wheel's front face (2.754 > 2.7) into that gap, which is harmless;
# what must hold is the tip's air to the hub (seat forward, hub long) and,
# with the thinnest wheel floated forward onto the hub (seat aft, hub short),
# the shortest pin's reach into the wheel's hole.
def drive_pin_front_clearances(
    proud_range: tuple[float, float],
    *,
    seat_face: float,
    seat_face_band: tuple[float, float],
    hub_rear: float,
    hub_rear_tol: float,
    plate_min: float,
) -> tuple[float, float]:
    """Worst-case ``(tip air to the hub rear face, floated engagement)`` of the
    seat's drive pins, local stations from the dome root; raises when either
    closes."""
    seat_fwd = seat_face + min(seat_face_band)
    seat_aft = seat_face + max(seat_face_band)
    hub_air = seat_fwd - max(proud_range) - (hub_rear + hub_rear_tol)
    wheel_float = seat_aft - plate_min - (hub_rear - hub_rear_tol)
    engagement = min(proud_range) - wheel_float
    if hub_air <= 0.0:
        raise AssertionError(
            f"the longest drive pin reaches the crank hub's rear face: air {hub_air:.3f}"
        )
    if engagement <= 0.0:
        raise AssertionError(
            f"the wheel floated onto the hub leaves the drive pins: {engagement:.3f}"
        )
    return hub_air, engagement


DRIVE_PIN_HUB_AIR_WORST, DRIVE_PIN_ENGAGEMENT_WORST = drive_pin_front_clearances(
    DRIVE_PIN_PROUD_RANGE,
    seat_face=SEAT_COLLAR,
    seat_face_band=SEAT_COLLAR_BAND,
    hub_rear=HUB_LENGTH,
    hub_rear_tol=HUB_LENGTH_TOL,
    plate_min=transgear_removable_spec.PLATE + min(transgear_removable_spec.PLATE_BAND),
)  # 0.196, 1.096
# The collar stays clear of the outboard journal land at both print limits.
if COLLAR_REAR + COLLAR_STATION_TOL >= JOURNAL_START - STATION_ROW:
    raise AssertionError(
        "the collar runs into the outboard journal land at print-worst"
    )
# Both Ø11.388 lands run in MHA-016 and therefore need their own Ra 1.6
# control on the native cylindrical face and their own drawing leader.  The
# collar's rear face runs against the floating MHA-172 thrust washer, so it
# carries the running grade too; the wheel's seat face is a static sprocket
# seat and stays "cast/machined" (rule 5).
SURFACE_FINISHES = (
    *(
        SurfaceFinishControl(
            key,
            MACHINED_UM,
            CylinderFace(JOURNAL_DIA, contains_y_mm=(start + end) / 2.0),
        )
        for key, start, end in (
            ("outboard_journal", JOURNAL_START, RELIEF_START),
            ("inboard_journal", RELIEF_END, JOURNAL_END),
        )
    ),
    SurfaceFinishControl(
        "collar_rear_face", MACHINED_UM, PlanarFace((0.0, 1.0, 0.0), COLLAR_REAR)
    ),
)


# Every printed axial station is a baseline from ONE origin: the FAR END, the
# one faced end the shop zeroes on (policy rule 7).  The features themselves
# measure from the dome root, so the far-end stations, the overall and the
# dome's spherical radius live on a construction-only StationReference sketch
# driven by the same globals (no geometry).  Depth (far end to dome root) and
# DomeHeight complete the chain; the overall and SR are references.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShaftProfile": {"ShaftDiaDim"},
    "Shaft": {"Depth"},
    "ShaftDomeProfile": {"DomeHeight"},
    "JournalProfile": {"JournalDiaDim"},
    "ReliefProfile": {"ReliefDiaDim"},
    "PinionSeatProfile": {"PinionSeatDiaDim"},
    "CollarProfile": {"CollarDiaDim"},
    "SpigotProfile": {"SpigotDiaDim"},
    "Spigot": {"SpigotLength"},
    "DrivePinProfile": {"DrivePinOffset1", "DrivePinOffset2"},
    "StationReference": {
        "OverallLength",
        "PinionSeatStation",
        "JournalInboardStation",
        "ReliefInboardStation",
        "ReliefOutboardStation",
        "JournalOutboardStation",
        "CollarRearStation",
        "CollarSeatStation",
        "PinHoleStation",
        "DomeSphereRadius",
    },
}
# Running/seat diameters carry their fit bands at three places. Relief and
# axial stations carry the routine one-place title-block band; the collar's
# functional bands print at the places that hold them.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ShaftProfile": {"ShaftDiaDim": 3},
    "Shaft": {"Depth": crank_pinion_spec.SHAFT_LENGTH_PLACES},
    "ShaftDomeProfile": {"DomeHeight": 1},
    "JournalProfile": {"JournalDiaDim": 3},
    "ReliefProfile": {"ReliefDiaDim": RELIEF_DIA_PLACES},
    "PinionSeatProfile": {"PinionSeatDiaDim": 3},
    "CollarProfile": {"CollarDiaDim": 2},
    "SpigotProfile": {"SpigotDiaDim": 2},
    "Spigot": {"SpigotLength": 2},
    "DrivePinProfile": {
        "DrivePinOffset1": DRIVE_PIN_OFFSET_PLACES,
        "DrivePinOffset2": DRIVE_PIN_OFFSET_PLACES,
    },
    "StationReference": {
        "OverallLength": 1,
        "PinionSeatStation": STATION_PLACES,
        "JournalInboardStation": STATION_PLACES,
        "ReliefInboardStation": STATION_PLACES,
        "ReliefOutboardStation": STATION_PLACES,
        "JournalOutboardStation": STATION_PLACES,
        "CollarRearStation": COLLAR_STATION_PLACES,
        "CollarSeatStation": COLLAR_STATION_PLACES,
        "PinHoleStation": STATION_PLACES,
        "DomeSphereRadius": 1,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked crankshaft dimension needs authored places")
# Read-only restatements: the overall is Depth + DomeHeight, and a spherical
# cap of DomeHeight on the Ø9.525 end already fixes its radius.
REFERENCE_DIMENSIONS = frozenset({"OverallLength", "DomeSphereRadius"})
SPHERICAL_DIMENSIONS = frozenset({"DomeSphereRadius"})

# The native cross-hole callout's process prefix: the drill reads first; the
# taper-ream prose under it lives in crankshaft_notes (drawing-only).
CROSS_HOLE_PROCESS = drill_process(PIN_HOLE_SPEC)
# The drive-pin holes print through a native callout on their cut-extrude
# (size and depth stay the model's), not as marked dimensions: the process
# prefix and the size/depth places live here, the press prose in the notes.
DRIVE_PIN_HOLE_PROCESS = "REAM"
HOLE_CALLOUT_PRECISION: dict[str, dict[str, int]] = {
    "DrivePinProfile": {"DrivePinHoleDia1": 3, "DrivePinHoleDia2": 3},
    "DrivePinHoles": {"DrivePinDepth": 2},
}
# The punch mark is a visual witness: its clocking to the cross-hole shows in
# the end view's hidden lines, and its exact spot is deliberately free.
DRAWING_NOTES = "PUNCH FIDUCIAL MARK ON DOME WHERE SHOWN; LOCATE BY EYE."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 1:1"
