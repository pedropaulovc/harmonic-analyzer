r"""Pure-data dimensional contract shared by the crankshaft and its drawing."""

from __future__ import annotations

from _hole_spec import HoleSpec
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
        production_method="BEARING JOURNAL",
    ),
)
# MHA-024 hub-to-shaft cross-hole behind the crank arm.
PIN_HOLE_SPEC = HoleSpec("drilled_number", "#9")
PIN_HOLE_HEIGHT = SERVICE_PIN_STATION

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShaftProfile": {"ShaftDiaDim"},
    "Shaft": {"Depth"},
    "ShaftDomeProfile": {"DomeHeight"},
    "JournalStartPlane": {"JournalStart"},
    "JournalProfile": {"JournalDiaDim"},
    "Journal": {"JournalLength"},
}
# The cross-hole's Ø/THRU callout comes from the associative native Hole Wizard
# annotation. Its axial station is a drawing-native basic dimension from the
# crank-end face to the hole axis.

# Lines kept short (<~66 chars) so the left-anchored block stays clear of the
# title block (x >= 0.264 m); it grows DOWNWARD from its anchor.
DRAWING_NOTES = "\n".join(
    (
        "PUNCH FIDUCIAL MARK WHERE SHOWN.",
        "THE CROSS-HOLE CALLOUT IS THE FINISHED SIZE FOR THIS PART.",
        "MATCH-REAM WITH CRANK HUB MHA-137 TO FIT CUSTOM TAPER PIN",
        "MHA-024; ASSEMBLY OPERATION OUTSIDE THIS PART DRAWING.",
        f"DIA {JOURNAL_DIA:.3f} BEARING JOURNAL RUNS IN DIA",
        f"{JOURNAL_BORE_DIA:.3f} POST BORE: "
        f"{JOURNAL_CLEARANCE:.2f} DIAMETRAL CLEARANCE.",
        "KEEP DIA 9.525 ON T12, PINION, AND CRANK-HUB SEATS.",
    )
)
END_VIEW_NOTE = "CRANK-END VIEW SCALE 2:1"
CRANK_END_NOTE = (
    "OUTBOARD CYLINDER ENDS FLUSH WITH MHA-020/MHA-137; "
    "ONLY INTEGRAL DOME PROJECTS"
)


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "end-face perpendicularity": "0.05",
    "cross-hole true position": "0.20",
}
