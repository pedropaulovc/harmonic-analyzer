r"""Pure-data dimensional contract shared by the crankshaft and its drawing."""

from __future__ import annotations

from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl


MM_PER_IN = 25.4

SHAFT_DIA = 0.375 * MM_PER_IN  # 9.525: ch11 legacy ShaftDiameter, uncontradicted
# No band on the 3/8 shaft: every part on it (T12 wheel, 16T pinion, crank
# arm) is pinned or set-screwed, not running, so the three-place block
# tolerance holds it (drawing-simplicity-policy.md rule 2; review 2026-09-02).
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
JOURNAL_DIA_BAND = (0.00, -0.02)  # (upper, lower) deviations: the one running fit
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
# The journal's two turned shoulder roots are drawn sharp; a machinist cannot
# produce a dead-sharp internal corner, so the print allows a small tool-nose
# root on both (machinist review 2026-09-02).  Leadered onto the shoulder
# rather than noted: nothing on the shaft butts hard against either root
# (the pinion seat sits 0.25 past the upper shoulder; the T12 seat is 15 mm
# short of the lower one).
JOURNAL_ROOT_NOTE = "2X ROOT R0.25 MAX"
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
# annotation. Its axial station is a drawing-native dimension from the
# crank-end face to the hole axis.

# Notes: part-specific process facts only, never a tolerance (the journal's
# fit band rides the model dimension), never the title block
# (drawing-simplicity-policy.md rule 6).
DRAWING_NOTES = "\n".join(
    (
        "TURN BETWEEN CENTRES IN ONE SETTING; CENTRES OK.",
        "CROSS-HOLE: MATCH-REAM AT ASSEMBLY WITH CRANK ARM MHA-020",
        "FOR TAPER PIN MHA-024.",
    )
)
END_VIEW_NOTE = "CRANK-END VIEW SCALE 2:1"
CRANK_END_NOTE = "CRANK / OUTBOARD END = LOWER END OF LENGTH VIEW"
