r"""Channel-spring (installed) dimensional contract -- the single source of truth
shared by the part build (``build_channel_spring_installed.py``) and its
manufacturing drawing (``draw_channel_spring_installed.py``).

PURE DATA, no SolidWorks/COM imports.  Like the counter spring this is a SPEC
SHEET (side view + data table, NO graphical marked dimensions).  This is the
SAME spring as the free channel spring, drawn at its INSTALLED (stretched)
length, so the table states BOTH the free body length and the installed body
length distinctly.  Values MUST match ``_spring`` / build_channel_spring_installed.
"""

from __future__ import annotations

import _config

# --- Nominal geometry (DIMENSIONS.md ch. 17; matches ``_spring``). ---
FREE_BODY_LENGTH = float(
    _config.parts("channel-spring-installed")["free_length_mm"]
)  # relaxed body (the ch.17 p.41 inset callout)
COIL_OD = 6.5
WIRE_DIA = 1.0
COIL_COUNT = 28

# Installed (in-machine) stretched body length -- from build_channel_spring_installed.
INSTALLED_BODY_LENGTH = 61.98

COIL_ID = COIL_OD - 2.0 * WIRE_DIA  # 4.5
MEAN_DIA = COIL_OD - WIRE_DIA  # 5.5
HOOK_LEAD = 2.0 * WIRE_DIA
HOOK_CL_RADIUS = MEAN_DIA / 2.0
FREE_EYE_C2C = FREE_BODY_LENGTH + 2.0 * HOOK_LEAD
INSTALLED_EYE_C2C = round(INSTALLED_BODY_LENGTH + 2.0 * HOOK_LEAD, 2)
FREE_PITCH = FREE_BODY_LENGTH / COIL_COUNT  # 1.14 -- NOT close-wound
# Nominal rate k = G d^4 / (8 Dm^3 n), ASTM A228 G = 79.3 GPa -- stated REF so
# the table carries a functional requirement, not just geometry.
SPRING_RATE_REF = 79300.0 * WIRE_DIA**4 / (8.0 * MEAN_DIA**3 * COIL_COUNT)


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
        "NOTE: DRAWN AT THE INSTALLED LENGTH;",
        f"SPRING SHIPS RELAXED AT {FREE_BODY_LENGTH:.2f} BODY.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
