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
    COIL_BODY_LENGTH,
    COIL_COUNT,
    COIL_ID,
    COIL_OD,
    FREE_EYE_C2C,
    FREE_PITCH,
    HOOK_CL_RADIUS,
    MEAN_DIA,
    SPRING_RATE_REF,
    TOP_HOOK_LEAD,
    WIRE_DIA,
)

# A spring is defined by its data table, not by graphical dimensions on the
# helix (whose wire cross-sections are not cleanly pickable), so NO marked
# dimensions.  The offline test asserts the empty marked set equals the empty
# kept set.
DRAWING_DIMENSIONS: dict[str, set[str]] = {}

# The spec table (rendered as a property-linked note).  Columns are space-padded
# for a monospace-style read.
# The free pitch is stated (165 x 1.80 close-wound would be 297, not 325.3 --
# the body is wound slightly OPEN and the table must say so); hook leads carry
# their measurement endpoints; the rate is a REF functional requirement.
DRAWING_NOTES = "\n".join(
    (
        "EXTENSION SPRING DATA",
        f"  WIRE DIA .......... {WIRE_DIA:.2f}",
        f"  COIL OD ........... {COIL_OD:.2f}",
        f"  COIL ID ........... {COIL_ID:.2f}",
        f"  MEAN DIA .......... {MEAN_DIA:.2f}",
        f"  FREE BODY LENGTH .. {COIL_BODY_LENGTH:.2f}",
        f"  TOTAL COILS ....... {COIL_COUNT}",
        f"  FREE PITCH ........ {FREE_PITCH:.2f} (OPEN-WOUND)",
        "  WIND .............. RIGHT HAND",
        f"  RATE .............. ~{SPRING_RATE_REF:.2f} N/MM (REF)",
        f"  HOOK LEADS ......... {BOTTOM_HOOK_LEAD:.2f} BOTTOM / "
        f"{TOP_HOOK_LEAD:.2f} TOP",
        "    (BODY END TO EYE C/L, EACH)",
        f"  ENDS .............. 270 DEG LOOP, R{HOOK_CL_RADIUS:.2f} CL;",
        "    EYES COPLANAR (0 DEG CLOCKING)",
        f"  FREE EYE C-C ...... {FREE_EYE_C2C:.2f}",
        "NOTE: TOWERS ABOVE THE MACHINE;",
        "TENSION SET BY SLIDING THE GOOSENECK POST.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:3"
