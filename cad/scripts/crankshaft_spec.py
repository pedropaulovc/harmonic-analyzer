r"""Pure-data dimensional contract shared by the crankshaft and its drawing."""

from __future__ import annotations


MM_PER_IN = 25.4

SHAFT_DIA = 0.375 * MM_PER_IN  # 9.525: ch11 legacy ShaftDiameter, uncontradicted
SHAFT_LENGTH = 145.0  # ch11: derived (crank seat + pedestal bearing + seats)

# The v2 pivot-post crank boss has an Ø11.438 bore spanning world
# z -148.3760944280..-75.9640944280.  With the shaft origin fixed at world
# z -175, its integral running journal occupies local stations
# 26.623905572..99.035905572.  The
# 0.05 mm diametral clearance is intentional; the surrounding shaft remains
# the existing 3/8-in OD for the T12, pinion, and crank-arm fits.
JOURNAL_BORE_DIA = 11.438
JOURNAL_CLEARANCE = 0.05
JOURNAL_DIA = JOURNAL_BORE_DIA - JOURNAL_CLEARANCE
JOURNAL_START = 26.623905572
JOURNAL_END = 99.035905572
JOURNAL_LENGTH = JOURNAL_END - JOURNAL_START
# Tapered-pin cross-hole: a native Hole Wizard #9 number drill radially through
# the crank seat (axis along Z). The diameter comes from the wizard drill table
# (_holes.NUMBER_DRILL_MM["#9"]); the value is mirrored here so the drawing's
# view math and notes stay COM-free.
PIN_HOLE_DIA = 4.978
PIN_HOLE_HEIGHT = 4.0  # arm mid-plane above the outboard end

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
        "KEEP DIA 9.525 ON T12, PINION, AND CRANK-ARM SEATS.",
    )
)
END_VIEW_NOTE = "CRANK-END VIEW SCALE 2:1"
CRANK_END_NOTE = "CRANK / OUTBOARD END = LOWER END OF LENGTH VIEW"
