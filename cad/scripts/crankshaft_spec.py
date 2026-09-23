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

# Every printed length runs from ONE origin: the dome root (local y=0), the
# plane where the arm and through hub MHA-137 finish flush and from which the
# hub's own MHA-024 station is measured.  The overall to the dome tip is a
# construction-only reference sketch (no geometry), printed as a reference.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShaftProfile": {"ShaftDiaDim"},
    "Shaft": {"Depth"},
    "ShaftDomeProfile": {"DomeHeight"},
    "JournalStartPlane": {"JournalStart"},
    "JournalProfile": {"JournalDiaDim"},
    "Journal": {"JournalLength"},
    "PinHoleStationPlane": {"PinHoleHeight"},
    "OverallReference": {"OverallLength"},
}
# Decimal places ARE the tolerance (policy rule 2).  The two diameters are
# functional fits and keep their three-place size bands; every length on this
# hand-cranked shaft is routine (.X).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ShaftProfile": {"ShaftDiaDim": 3},
    "Shaft": {"Depth": 1},
    "ShaftDomeProfile": {"DomeHeight": 1},
    "JournalStartPlane": {"JournalStart": 1},
    "JournalProfile": {"JournalDiaDim": 3},
    "Journal": {"JournalLength": 1},
    "PinHoleStationPlane": {"PinHoleHeight": 1},
    "OverallReference": {"OverallLength": 1},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked crankshaft dimension needs authored places")
# The overall is a read-only restatement of Depth + DomeHeight.
REFERENCE_DIMENSIONS = frozenset({"OverallLength"})

# Matched-fit requirement on the feature callout (rule 6), above the native
# drill size; mirrors the hub's "MATCH-REAM WITH MHA-026".
CROSS_HOLE_PROCESS = (
    "MATCH-REAM WITH MHA-137 TO FIT MHA-024\n"
    f"{drill_process(PIN_HOLE_SPEC)}"
)
DRAWING_NOTES = "PUNCH FIDUCIAL MARK WHERE SHOWN."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 1:1"
