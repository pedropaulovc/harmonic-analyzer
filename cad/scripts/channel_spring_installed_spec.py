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

# --- Nominal geometry (DIMENSIONS.md ch. 17; matches ``_spring``). ---
FREE_BODY_LENGTH = 32.0  # relaxed body (the ch.17 p.41 inset callout)
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


# No graphical marked dimensions -- the data table governs (see counter_spring).
DRAWING_DIMENSIONS: dict[str, set[str]] = {}

DRAWING_NOTES = "\n".join(
    (
        "EXTENSION SPRING DATA (1 OF 20)",
        "  WIRE DIA .......... 1.0",
        "  COIL OD ........... 6.5",
        "  COIL ID ........... 4.5",
        "  MEAN DIA .......... 5.5",
        "  FREE BODY LENGTH .. 32 (RELAXED)",
        "  INSTALLED BODY .... 62 (STRETCHED)",
        "  TOTAL COILS ....... 28 (CLOSE-WOUND)",
        "  WIND .............. RIGHT HAND",
        "  HOOK LEADS ......... 2.0 EACH END",
        "  ENDS .............. 270 DEG LOOP, R2.75 CL",
        "  FREE EYE C-C ...... 36.0",
        "  INSTALLED EYE C-C . 65.98",
        "NOTE: DRAWN AT THE INSTALLED LENGTH;",
        "SPRING SHIPS RELAXED AT 32 BODY.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
