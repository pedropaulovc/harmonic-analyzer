r"""Pure-data dimensional contract shared by the crankshaft and its drawing."""

from __future__ import annotations

from _hole_spec import HoleSpec, drill_process
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
import crank_pinion_spec
from crank_hub_geometry import (
    CRANK_FACE_SHIFT,
    FIDUCIAL_MODEL_DEPTH,
    FIDUCIAL_MODEL_DIA,
    SERVICE_PIN_STATION,
    SHAFT_DIA,
    SHAFT_DIA_BAND,
    SHAFT_DOME_HEIGHT,
    SHAFT_FIDUCIAL_RADIUS,
)


# The common arm/hub/shaft cylinder face moved 8 mm outboard.  Adding the same
# shift to all inboard stations preserves every established bearing, T12 and
# pinion world interface.  The 16T pinion's toothed south face seats here.
SEAT_PINION = 105.039505572 + CRANK_FACE_SHIFT  # 113.039505572
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
)  # 136.8
SHAFT_END_RECESS = SEAT_PINION + crank_pinion_spec.OVERALL_LENGTH - SHAFT_LENGTH  # 1.1395
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
# RULING W15-SHAFT-BAND (Main 2026-09-25): unilateral +0/-0.4 is required by
# the W15 pin-wall and recess stacks (pinion_pin_edge_stack /
# pinion_recess_stack in build_drive_train_assembly); at the title-block .X
# +/-0.8 the wall is 1.873 < 2.0 and the recess -0.461.
SHAFT_LENGTH_BAND = (0.00, -0.40)  # (upper, lower) deviations

# #906 R1: the shaft runs in the MHA-149 eccentric bushing on its plain 3/8 in
# core; the integral journal and its relief are gone.  The bushing's north
# end sits flush with the post boss's spot face here (the old journal
# bore's inboard end), which the Ø9.0 seat step stays at.
POST_BORE_END = 104.789505572 + CRANK_FACE_SHIFT  # 112.79

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

# The core runs in the bushing (rule 5); the finish rides its middle.
BEARING_MID_STATION = POST_BORE_END - 38.5
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "bearing_core",
        MACHINED_UM,
        CylinderFace(SHAFT_DIA, contains_y_mm=BEARING_MID_STATION),
    ),
)
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
    "PinionSeatProfile": {"PinionSeatDiaDim"},
    "StationReference": {
        "OverallLength",
        "PinionSeatStation",
        "PinHoleStation",
        "DomeSphereRadius",
    },
}
# Decimal places ARE the tolerance (policy rule 2).  The two running/seat
# diameters are functional fits and keep their three-place size bands; every
# length on this hand-cranked shaft is routine (.X).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ShaftProfile": {"ShaftDiaDim": 3},
    "Shaft": {"Depth": crank_pinion_spec.SHAFT_LENGTH_PLACES},
    "ShaftDomeProfile": {"DomeHeight": 1},
    "PinionSeatProfile": {"PinionSeatDiaDim": 3},
    "StationReference": {
        "OverallLength": 1,
        "PinionSeatStation": STATION_PLACES,
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
