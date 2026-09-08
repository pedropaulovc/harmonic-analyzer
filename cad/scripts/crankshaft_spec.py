r"""Pure-data dimensional contract shared by the crankshaft and its drawing."""

from __future__ import annotations

from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from crank_end_retainer_spec import (
    FINISHED_TAPER_NEAR_END,
    MIN_TAP_TO_TAPER_WEB,
    SHAFT_TAP_DRILL_DEPTH,
    SHAFT_TAP_POINT_END,
    SHAFT_TAP_TO_FINISHED_TAPER_WEB,
    SHAFT_THREAD_DEPTH,
    SCREW_THREAD as RETAINER_THREAD,
)


MM_PER_IN = 25.4

SHAFT_DIA = 0.375 * MM_PER_IN  # 9.525: ch11 legacy ShaftDiameter, uncontradicted
SHAFT_DIA_BAND = (0.00, -0.02)  # (upper, lower) deviations
SHAFT_LENGTH = 122.0  # 2026-09 re-derive: ends 6.2 past the 16T pinion's north
# face (ch12 page002_img02 shows a short capped end right behind the pinion,
# not the 34 mm bare stub the 150 left poking out the column's back)

# The installed v2 pivot post is turned end-for-end and remains fixed at its
# ch30-fitted world placement. Its Ø11.438 bore therefore spans world
# z -142.244894428..-70.210494428.  The crank/chain plane stays photo-anchored
# at the existing world z=-175 shaft origin, so the integral running journal
# occupies these local stations.  The 0.05 mm diametral clearance is
# intentional; the surrounding shaft remains
# the existing 3/8-in OD for the T12, pinion, and crank-arm fits.
JOURNAL_BORE_DIA = 11.438
JOURNAL_CLEARANCE = 0.05
JOURNAL_DIA = JOURNAL_BORE_DIA - JOURNAL_CLEARANCE
JOURNAL_DIA_BAND = (0.00, -0.02)  # (upper, lower) deviations
JOURNAL_START = 32.755105572
JOURNAL_END = 104.789505572
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
# Tapered-pin cross-hole: a native Hole Wizard #9 number drill radially through
# the crank seat (axis along Z). The diameter comes from the wizard drill table
# (_holes.NUMBER_DRILL_MM["#9"]); the value is mirrored here so the drawing's
# view math and notes stay COM-free.
PIN_HOLE_DIA = 4.978
PIN_HOLE_HEIGHT = 4.0  # arm mid-plane above the outboard end

# Coaxial crank-end retainer: shallow #0-80 bottoming tap from the outboard
# face.  The complete 118-degree drill point leaves a specified web before the
# FINISHED 1:48 taper bore; checking only the smaller #9 pilot is insufficient.
if SHAFT_TAP_POINT_END >= FINISHED_TAPER_NEAR_END:
    raise AssertionError("crank-end tap drill reaches the finished taper bore")
if SHAFT_TAP_TO_FINISHED_TAPER_WEB < MIN_TAP_TO_TAPER_WEB:
    raise AssertionError("crank-end tap lacks its finished-taper web allowance")
if SHAFT_THREAD_DEPTH > SHAFT_TAP_DRILL_DEPTH:
    raise AssertionError("crank-end thread depth exceeds its tap-drill depth")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShaftProfile": {"ShaftDiaDim"},
    "Shaft": {"Depth"},
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
        "THE CROSS-HOLE CALLOUT IS THE FINISHED SIZE FOR THIS PART.",
        "MATCH-REAM WITH CRANK ARM MHA-020 TO FIT CUSTOM TAPER PIN",
        "MHA-024; ASSEMBLY OPERATION OUTSIDE THIS PART DRAWING.",
        f"DIA {JOURNAL_DIA:.3f} BEARING JOURNAL RUNS IN DIA",
        f"{JOURNAL_BORE_DIA:.3f} POST BORE: "
        f"{JOURNAL_CLEARANCE:.2f} DIAMETRAL CLEARANCE.",
        f"{RETAINER_THREAD} UNF-2B BOTTOMING TAP IN CRANK END;",
        f"{SHAFT_THREAD_DEPTH:.2f} MIN FULL THREAD.",
        f"KEEP {MIN_TAP_TO_TAPER_WEB:.2f} MIN WEB TO FINISHED TAPER BORE.",
        "KEEP DIA 9.525 ON T12, PINION, AND CRANK-ARM SEATS.",
    )
)
END_VIEW_NOTE = "CRANK-END VIEW SCALE 2:1"
CRANK_END_NOTE = "CRANK / OUTBOARD END = LOWER END OF LENGTH VIEW"


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "end-face perpendicularity": "0.05",
    "cross-hole true position": "0.20",
}
