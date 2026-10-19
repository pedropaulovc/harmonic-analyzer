"""Assembly-only fit-up instructions for MHA-DT-00.

Part specifications own permitted cuts, limits and pin fits. The assembly
prints their bench checks and remedies, without design-clearance narration.
Kept separate from the explode contract so text changes do not rebuild CAD.
"""

import dt_crank_pinion_spec as pinion

T120_FITUP_ASSEMBLY_CHECK = "\n".join(
    (
        f"   PUSH {pinion.T120_FITUP_PUSHED[0]} AND {pinion.T120_FITUP_PUSHED[1]} TOWARD EACH OTHER;",
        "   TURN MHA-DT-07 SLOWLY BY HAND, READING A",
        f"   {pinion.T120_FITUP_FEELER_MM:.2f} FEELER ALL ROUND. MHA-DT-10 BAND TO T120 TIPS:",
        "   IF THE FEELER STOPS, TURN THE MHA-DT-10 BAND DOWN,",
        f"   Ø{pinion.TURNED_DIA_FITUP_MIN:.{pinion.TURNED_DIA_PLACES}f} MIN.",
        "   MHA-DT-10 SHOULDER TO T120 SOUTH FACE: IF THE FEELER STOPS,",
        "   FACE THE MHA-DT-10 SHOULDER BACK,",
        f"   {pinion.SHOULDER_LENGTH_FITUP_MIN:.{pinion.SHOULDER_LENGTH_PLACES}f} MIN. RESET, RECHECK.",
    )
)

# The lever and lift-rod prints defer this hole to assembly. The pin contract
# specifies a stock 1/16 in slip fit retained by peening, not a reamed press fit.
LEVER_PIN_HOLE_FIT = "\n".join(
    (
        "HOLE AT MHA-DT-16'S PRINTED STATION: 1/16 IN DRILL THRU;",
        "MHA-DT-30 SLIP FIT.",
    )
)
