r"""Crankshaft manufacturing contract.

The v36 MHA-016 bore carries integral running lands again; the pinion sits
SEAT_FEELER_MM off its north boss face. All axial stations are measured from
the dome root in the model and printed from the far end; W15 uses the
printed worst cases.
"""

from __future__ import annotations

import _config
from _hole_spec import HoleSpec, drill_process
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from cone_pivot_post_spec import CRANK_BORE_DIA as JOURNAL_BORE_DIA
from cone_pivot_post_spec import RUNNING_BORE_BAND as JOURNAL_BORE_BAND
import crank_pinion_spec
from crank_hub_geometry import (
    CRANK_FACE_SHIFT,
    FIDUCIAL_MODEL_DEPTH,  # noqa: F401 -- re-exported to the drawing contract
    FIDUCIAL_MODEL_DIA,  # noqa: F401 -- re-exported to the drawing contract
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
# W15 (Main, 2026-09-25): the far end sits recessed inside the pinion's boss,
# and crank_pinion_spec sizes that boss so the retention pin keeps its wall to
# this end.  The length is floored to the places it prints (Codex P2 on #892),
# so the sheet's nominal IS the model's and an accepted shaft is never longer
# than the model; the recess that leaves lies between the pinion's
# SHAFT_END_RECESS_MIN and _MAX, the range its boss was sized for.
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
# W15-SHAFT-BAND (Main 2026-09-25): unilateral +0/-0.4 is required by
# the W15 pin-wall and recess stacks (pinion_pin_edge_stack /
# pinion_recess_stack in build_drive_train_assembly); at the title-block .X
# +/-0.8 the restored stack's wall is 1.873 < 2.0 and recess -0.461.
SHAFT_LENGTH_BAND = (0.00, -0.40)  # (upper, lower) deviations

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
PINION_SEAT_STATION = 24.1  # far end to the step
SEAT_STEP = local_station(PINION_SEAT_STATION)  # 112.7
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
JOURNAL_INBOARD_STATION = 27.7
JOURNAL_END = local_station(JOURNAL_INBOARD_STATION)
JOURNAL_LENGTH = JOURNAL_END - JOURNAL_START
STEP_WEB_WORST = SEAT_STEP - JOURNAL_END - 2.0 * STATION_ROW
RELIEF_DIA = 10.4
RELIEF_DIA_PLACES = 1
RELIEF_OUTBOARD_STATION = 81.0
RELIEF_INBOARD_STATION = 42.7
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
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "bearing_journal",
        MACHINED_UM,
        CylinderFace(JOURNAL_DIA, contains_y_mm=(RELIEF_END + JOURNAL_END) / 2.0),
    ),
)

# W15's printed worst cases are pure data, so they can be checked without
# importing an assembly builder. The retention hole is laid out at boss middle.
PINION_PIN_STATION_Y = SEAT_PINION + crank_pinion_spec.PIN_STATION
PINION_PIN_EDGE_TO_END = SHAFT_LENGTH - PINION_PIN_STATION_Y - crank_pinion_spec.PIN_DIA / 2.0
PINION_PIN_EDGE_STACK = {
    "nominal": PINION_PIN_EDGE_TO_END,
    "shaft length": SHAFT_LENGTH_BAND[1],
    "seat gap": -SEAT_GAP_NORTH_RANGE,
    "boss mid-length": -crank_pinion_spec.OVERALL_LENGTH_GRADE_MM,
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
# MHA-024 hub-to-shaft cross-hole behind the crank arm.
PIN_HOLE_SPEC = HoleSpec("drilled_number", "#9")
PIN_HOLE_HEIGHT = SERVICE_PIN_STATION

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
    "StationReference": {
        "OverallLength",
        "PinionSeatStation",
        "JournalInboardStation",
        "ReliefInboardStation",
        "ReliefOutboardStation",
        "JournalOutboardStation",
        "PinHoleStation",
        "DomeSphereRadius",
    },
}
# Running/seat diameters carry their fit bands at three places. Relief and
# axial stations carry the routine one-place title-block band.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ShaftProfile": {"ShaftDiaDim": 3},
    "Shaft": {"Depth": crank_pinion_spec.SHAFT_LENGTH_PLACES},
    "ShaftDomeProfile": {"DomeHeight": 1},
    "JournalProfile": {"JournalDiaDim": 3},
    "ReliefProfile": {"ReliefDiaDim": RELIEF_DIA_PLACES},
    "PinionSeatProfile": {"PinionSeatDiaDim": 3},
    "StationReference": {
        "OverallLength": 1,
        "PinionSeatStation": STATION_PLACES,
        "JournalInboardStation": STATION_PLACES,
        "ReliefInboardStation": STATION_PLACES,
        "ReliefOutboardStation": STATION_PLACES,
        "JournalOutboardStation": STATION_PLACES,
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
# The punch mark is a visual witness: its clocking to the cross-hole shows in
# the end view's hidden lines, and its exact spot is deliberately free.
DRAWING_NOTES = "PUNCH FIDUCIAL MARK ON DOME WHERE SHOWN; LOCATE BY EYE."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 1:1"
