r"""Channel-spring (installed) drawing prose -- the spec-sheet data table the
part build stamps into the SLDPRT, the isometric-view label, and the (empty)
marked-dimension contract.

Split OUT of ``channel_spring_installed_spec`` (codex #354, same treatment as
``connecting_rod_notes``): ``_spring`` (imported by ``build_channel_assembly``
for the spring geometry helpers) imports the spec's geometry constants, so
table prose living in that import closure made every table edit full-rebuild
``assembly:channel``.  Imported ONLY by ``build_channel_spring_installed`` and
the offline drawing test.
"""

from __future__ import annotations

from channel_spring_installed_spec import (
    COIL_COUNT,
    COIL_ID,
    COIL_OD,
    FREE_BODY_LENGTH,
    FREE_EYE_C2C,
    FREE_PITCH,
    HOOK_CL_RADIUS,
    HOOK_LEAD,
    INSTALLED_BODY_LENGTH,
    INSTALLED_EYE_C2C,
    MEAN_DIA,
    SPRING_RATE_REF,
    WIRE_DIA,
)

# No graphical marked dimensions -- the data table governs (see counter_spring).
DRAWING_DIMENSIONS: dict[str, set[str]] = {}

# The free pitch is stated (28 x 1.00 close-wound would be 28, not 32 -- the
# body is wound slightly OPEN and the table must say so); hook leads carry
# their measurement endpoints; the rate is a REF functional requirement; the
# title-block QTY cell owns the 20-off count.
DRAWING_NOTES = "\n".join(
    (
        "EXTENSION SPRING DATA",
        f"  WIRE DIA .......... {WIRE_DIA:.2f}",
        f"  COIL OD ........... {COIL_OD:.2f}",
        f"  COIL ID ........... {COIL_ID:.2f}",
        f"  MEAN DIA .......... {MEAN_DIA:.2f}",
        f"  FREE BODY LENGTH .. {FREE_BODY_LENGTH:.2f} (RELAXED)",
        f"  INSTALLED BODY .... {INSTALLED_BODY_LENGTH:.2f} (STRETCHED)",
        f"  TOTAL COILS ....... {COIL_COUNT}",
        f"  FREE PITCH ........ {FREE_PITCH:.2f} (OPEN-WOUND)",
        "  WIND .............. RIGHT HAND",
        f"  RATE .............. ~{SPRING_RATE_REF:.2f} N/MM (REF)",
        f"  HOOK LEADS ......... {HOOK_LEAD:.2f} EACH END",
        "    (BODY END TO EYE C/L)",
        f"  ENDS .............. 270 DEG LOOP, R{HOOK_CL_RADIUS:.2f} CL;",
        "    EYES COPLANAR (0 DEG CLOCKING)",
        f"  FREE EYE C-C ...... {FREE_EYE_C2C:.2f}",
        f"  INSTALLED EYE C-C . {INSTALLED_EYE_C2C:.2f}",
        "VIEWS SHOW THE INSTALLED (STRETCHED) LENGTH; SUPPLIED RELAXED.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
