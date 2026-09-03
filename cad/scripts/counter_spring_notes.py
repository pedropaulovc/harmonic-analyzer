r"""Counter-spring drawing prose -- the spec-sheet data table the part build
stamps into the SLDPRT, the isometric-view label, and the (empty)
marked-dimension contract.

Split OUT of ``counter_spring_spec`` (codex #354, same treatment as
``connecting_rod_notes``): ``build_summing_assembly`` imports the spring's
geometry constants, so table prose living in that import closure made every
table edit full-rebuild ``assembly:summing``.  Imported ONLY by
``build_counter_spring`` and the offline drawing test.
"""

from __future__ import annotations

from counter_spring_spec import (
    BOTTOM_HOOK_LEAD,
    COIL_COUNT,
    COIL_OD,
    FREE_EYE_C2C,
    HOOK_CL_RADIUS,
    TOP_HOOK_LEAD,
    WIRE_DIA,
)

# A spring is defined by its data table, not by graphical dimensions on the
# helix (whose wire cross-sections are not cleanly pickable), so NO marked
# dimensions.  The offline test asserts the empty marked set equals the empty
# kept set.
DRAWING_DIMENSIONS: dict[str, set[str]] = {}

# Compact purchase/manufacturing data.  Free length is measured eye-centre to
# eye-centre; the end line carries the unusual unequal leads without expanding
# the block back into a derived-geometry table.
DRAWING_NOTES = "\n".join(
    (
        "EXTENSION SPRING DATA",
        f"  WIRE Ø{WIRE_DIA:.2f}    OD {COIL_OD:.2f}",
        f"  FREE LENGTH {FREE_EYE_C2C:.2f} EYE C-C",
        f"  ACTIVE COILS {COIL_COUNT}    RIGHT HAND",
        f"  ENDS 270.0 DEG LOOPS, R{HOOK_CL_RADIUS:.2f} C/L",
        f"  LEADS {BOTTOM_HOOK_LEAD:.2f} BTM / {TOP_HOOK_LEAD:.2f} TOP; COPLANAR",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:3"
