"""Drawing-only fit-up instructions for MHA-DT-00.

Part specifications own permitted cuts, limits and pin fits. The assembly
prints their bench checks and remedies, without design-clearance narration.
Kept separate from the explode contract so text changes do not rebuild CAD.
"""

import dt_crank_handle_spec as _handle
import dt_crank_pinion_spec as pinion
import dt_pinion_lever_geometry as _lever
import dt_pinion_lever_pin_spec as _lever_pin
from _inch_fraction import inch_fraction

# Owner ruling 2026-10-24 (#1900): MHA-DT-34 cures on a mandrel through the
# MHA-DT-08 pivot bore.  Step 7 prints the requirement, the bore's offset off
# that axis that MHA-DT-34's skimmed wall is budgeted on, not the mandrel;
# MHA-DT-32 passes through the larger MHA-DT-34 bore and does not locate it.
HANDLE_FERRULE_CURE = (
    "THE MHA-DT-34 BORE CENTRED ON THE MHA-DT-08 PIVOT BORE WITHIN "
    f"{_handle.FERRULE_OFFSET_MAX:.2f}"
)

T120_FITUP_ASSEMBLY_CHECK = "\n".join(
    (
        f"   PUSH {pinion.T120_FITUP_PUSHED[0]} AND {pinion.T120_FITUP_PUSHED[1]} TOWARD EACH OTHER;",
        "   TURN MHA-DT-07 SLOWLY BY HAND, READING A",
        f"   {pinion.T120_FITUP_FEELER_MM:.2f} FEELER ALL ROUND. MHA-DT-10 BAND TO T120 TIPS:",
        "   IF THE FEELER STOPS, TURN THE MHA-DT-10 BAND DOWN,",
        f"   Ø{pinion.TURNED_DIA_FITUP_MIN:.2f} MIN.",
        "   MHA-DT-10 SHOULDER TO T120 SOUTH FACE: IF THE FEELER STOPS,",
        "   FACE THE MHA-DT-10 SHOULDER BACK,",
        f"   {pinion.SHOULDER_LENGTH_FITUP_MIN:.2f} MIN. RESET, RECHECK.",
    )
)

# The lever and lift-rod prints defer this hole to assembly. The pin contract
# specifies a stock 1/16 in slip fit retained by peening, not a reamed press fit.
LEVER_PIN_HOLE_FIT = "\n".join(
    (
        f"HOLE AT {_lever_pin.LEVER_NUMBER}'S PRINTED STATION: "
        f"{inch_fraction(_lever.PIN_HOLE_DIA, what='lever pin hole')} IN DRILL THRU;",
        f"{_lever_pin.PIN_NUMBER} SLIP FIT.",
    )
)
