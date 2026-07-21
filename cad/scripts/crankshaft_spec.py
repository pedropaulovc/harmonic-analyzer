r"""Pure-data dimensional contract shared by the crankshaft and its drawing."""

from __future__ import annotations


MM_PER_IN = 25.4

SHAFT_DIA = 0.375 * MM_PER_IN  # 9.525: ch11 legacy ShaftDiameter, uncontradicted
SHAFT_LENGTH = 145.0  # ch11: derived (crank seat + pedestal bearing + seats)
# Tapered-pin cross-hole: a native Hole Wizard #9 number drill radially through
# the crank seat (axis along Z). The diameter comes from the wizard drill table
# (_holes.NUMBER_DRILL_MM["#9"]); the value is mirrored here so the drawing's
# view math and notes stay COM-free.
PIN_HOLE_DIA = 4.978
PIN_HOLE_HEIGHT = 12.0  # crank hub centre above the outboard end

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShaftProfile": {"ShaftDiaDim"},
    "Shaft": {"Depth"},
}
# The #9 cross-hole is NOT in the marked-dimension set: its Ø/THRU callout is
# the associative native Hole Wizard callout and its station is a drawing-side
# reference dimension (the placement dim lives on a wizard SUBfeature sketch,
# which mark_dimensions_for_drawing's top-level feature walk cannot reach).

# Lines kept short (<~66 chars) so the left-anchored block stays clear of the
# title block (x >= 0.264 m); it grows DOWNWARD from its anchor.
DRAWING_NOTES = "\n".join(
    (
        "DEBURR; BREAK ENDS 0.15 MAX; CENTRE MARKS 1.0 DEEP MAX.",
        "TURN OR CENTRELESS-GRIND FULL BEARING LENGTH; NO FLATS OR STEPS.",
        "BOTH ENDS FACED SQUARE TO AXIS A WITHIN 0.05; END FACES 3.2 Ra.",
        "CROSS-HOLE: #9 (4.978) DRILL THRU AT CRANK SEAT, 12 FROM",
        "OUTBOARD END; TAPER-REAM AT ASSEMBLY WITH CRANK ARM FOR",
        "NO. 2 TAPER PIN, 1:48, LARGE END OUTBOARD.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 2:1"
