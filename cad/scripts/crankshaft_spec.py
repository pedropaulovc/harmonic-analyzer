r"""Pure-data dimensional contract shared by the crankshaft and its drawing."""

from __future__ import annotations

from _hole_spec import HoleSpec, drill_process
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
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


SHAFT_LENGTH = 122.0 + CRANK_FACE_SHIFT
# The common arm/hub/shaft cylinder face moved 8 mm outboard.  Adding the same
# shift to all inboard stations preserves every established bearing, T12 and
# pinion world interface and keeps the far end at its prior world coordinate.

# The installed v2 pivot post remains fixed.  Its Ø11.438 bore spans world
# z -142.244894428..-70.210494428.  Moving the common crank face from -175 to
# -183 and adding the same 8 mm to local stations leaves that journal, the T12
# and the pinion in their established world positions.
# The 0.05-mm journal clearance is intentional; the surrounding shaft remains
# the existing 3/8-in OD for the T12, pinion and through-hub fits.
JOURNAL_BORE_DIA = 11.438
JOURNAL_CLEARANCE = 0.05
JOURNAL_DIA = JOURNAL_BORE_DIA - JOURNAL_CLEARANCE
JOURNAL_DIA_BAND = (0.00, -0.02)  # (upper, lower) deviations
JOURNAL_START = 32.755105572 + CRANK_FACE_SHIFT
JOURNAL_END = 104.789505572 + CRANK_FACE_SHIFT
JOURNAL_LENGTH = JOURNAL_END - JOURNAL_START
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "bearing_journal",
        MACHINED_UM,
        CylinderFace(
            JOURNAL_DIA,
            contains_y_mm=JOURNAL_START + JOURNAL_LENGTH / 2.0,
        ),
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
    "JournalProfile": {"JournalDiaDim"},
    "StationReference": {
        "OverallLength",
        "JournalInboardStation",
        "JournalOutboardStation",
        "PinHoleStation",
        "DomeSphereRadius",
    },
}
# Decimal places ARE the tolerance (policy rule 2).  The two diameters are
# functional fits and keep their three-place size bands; every length on this
# hand-cranked shaft is routine (.X).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ShaftProfile": {"ShaftDiaDim": 3},
    "Shaft": {"Depth": 1},
    "ShaftDomeProfile": {"DomeHeight": 1},
    "JournalProfile": {"JournalDiaDim": 3},
    "StationReference": {
        "OverallLength": 1,
        "JournalInboardStation": 1,
        "JournalOutboardStation": 1,
        "PinHoleStation": 1,
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

# Matched-fit requirement on the feature callout (rule 6), above the native
# drill size, naming both mates and the acceptance of the custom 1:48 taper
# pin (crank_pin_spec).  Short lines keep the callout narrow enough to sit
# beside the cross-hole.
CROSS_HOLE_PROCESS = "\n".join(
    (
        "MATCH TAPER-REAM 1:48",
        "WITH CRANK HUB MHA-137",
        "TO TAPER PIN MHA-024:",
        "LIGHT DRIVE FIT",
        drill_process(PIN_HOLE_SPEC),
    )
)
# The punch mark is a visual witness: its clocking to the cross-hole shows in
# the end view's hidden lines, and its exact spot is deliberately free.
DRAWING_NOTES = "PUNCH FIDUCIAL MARK ON DOME WHERE SHOWN; LOCATE BY EYE."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 1:1"
