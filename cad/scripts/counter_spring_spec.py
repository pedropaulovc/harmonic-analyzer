r"""Counter-spring dimensional contract -- the single source of truth shared by
the part build (``build_counter_spring.py``) and its manufacturing drawing
(``draw_counter_spring.py``).

PURE DATA, no SolidWorks/COM imports.  A coil spring is a SPEC SHEET: the print
is a single side view plus a data table, so there are NO graphical marked model
dimensions -- the whole spring is defined by the table carried in the notes.
The nominal values MUST match build_counter_spring.py.
"""

from __future__ import annotations

# --- Nominal geometry (DIMENSIONS.md "Chapter 19"). ---
COIL_BODY_LENGTH = 315.0  # close-wound coil body length
COIL_OD = 12.5  # coil outer diameter
WIRE_DIA = 1.8  # music-wire diameter
COIL_COUNT = 165  # total coils (close-wound)

COIL_ID = COIL_OD - 2.0 * WIRE_DIA  # 8.9 inner diameter
MEAN_DIA = COIL_OD - WIRE_DIA  # 10.7 mean coil diameter
BOTTOM_HOOK_LEAD = 40.0
TOP_HOOK_LEAD = 2.0 * WIRE_DIA
HOOK_CL_RADIUS = MEAN_DIA / 2.0
FREE_EYE_C2C = COIL_BODY_LENGTH + BOTTOM_HOOK_LEAD + TOP_HOOK_LEAD
FREE_PITCH = COIL_BODY_LENGTH / COIL_COUNT  # 1.91 -- NOT close-wound
# Nominal rate k = G d^4 / (8 Dm^3 n), ASTM A228 G = 79.3 GPa -- stated REF so
# the table carries a functional requirement, not just geometry.
SPRING_RATE_REF = 79300.0 * WIRE_DIA**4 / (8.0 * MEAN_DIA**3 * COIL_COUNT)


# A spring is defined by its data table, not by graphical dimensions on the
# helix (whose wire cross-sections are not cleanly pickable), so NO marked
# dimensions.  The offline test asserts the empty marked set equals the empty
# kept set.
DRAWING_DIMENSIONS: dict[str, set[str]] = {}

# The spec table (rendered as a property-linked note).  Columns are space-padded
# for a monospace-style read.
# The free pitch is stated (165 x 1.80 close-wound would be 297, not 315 --
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
