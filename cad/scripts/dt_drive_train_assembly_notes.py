"""Assembly-only fit-up instructions for MHA-DT-000.

Part specifications own the permitted cuts and their limits. The assembly
prints the check and its remedies, without the design-clearance narration.
Kept separate from the explode contract so text changes do not rebuild CAD.
"""

import dt_crank_pinion_spec as pinion

T120_FITUP_ASSEMBLY_CHECK = "\n".join(
    (
        f"   PUSH {pinion.T120_FITUP_PUSHED[0]} AND {pinion.T120_FITUP_PUSHED[1]} TOWARD EACH OTHER;",
        "   TURN MHA-DT-007 SLOWLY BY HAND, READING A",
        f"   {pinion.T120_FITUP_FEELER_MM:.2f} FEELER ALL ROUND. MHA-DT-010 BAND TO T120 TIPS:",
        "   IF THE FEELER STOPS, TURN THE MHA-DT-010 BAND DOWN,",
        f"   Ø{pinion.TURNED_DIA_FITUP_MIN:.{pinion.TURNED_DIA_PLACES}f} MIN.",
        "   MHA-DT-010 SHOULDER TO T120 SOUTH FACE: IF THE FEELER STOPS,",
        "   FACE THE MHA-DT-010 SHOULDER BACK,",
        f"   {pinion.SHOULDER_LENGTH_FITUP_MIN:.{pinion.SHOULDER_LENGTH_PLACES}f} MIN. RESET, RECHECK.",
    )
)
