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
    "3DSketch1": {"PinHeight"},
}
# The cross-hole's Ø/THRU callout comes from the associative native Hole Wizard
# annotation. Its axial station is the model's PinHeight dimension on the
# wizard's nested 3DSketch1 subfeature; the drawing-mark walker reaches the
# complete feature tree so that model-owned dimension can be imported.

# Lines kept short (<~66 chars) so the left-anchored block stays clear of the
# title block (x >= 0.264 m); it grows DOWNWARD from its anchor.
DRAWING_NOTES = "\n".join(
    (
        "<MOD-DIAM>4.98 +0.10/0 THRU IS THE FINISHED PILOT-HOLE CONDITION",
        "FOR THIS PART. HOLE AXIS SQUARE TO AND INTERSECTS THE SHAFT AXIS.",
        "BOTH END FACES SQUARE TO THE SHAFT AXIS WITHIN 0.05.",
        "MATCH-REAMING WITH THE CRANK ARM TO FIT CUSTOM TAPER PIN",
        "MHA-024 IS AN ASSEMBLY OPERATION OUTSIDE THIS PART DRAWING.",
    )
)
END_VIEW_NOTE = "CRANK-END VIEW SCALE 2:1"
CRANK_END_NOTE = "CRANK / OUTBOARD END = LOWER END OF LENGTH VIEW"
