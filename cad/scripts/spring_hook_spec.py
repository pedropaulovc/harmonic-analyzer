r"""Spring-hook dimensional contract -- the single source of truth shared by the
part build (``build_spring_hook.py``) and its manufacturing drawing
(``draw_spring_hook.py``).

PURE DATA, no SolidWorks/COM imports.  A small formed-wire open J-hook (like the
crank pin, it carries only a couple of graphical dimensions plus notes).  Values
MUST match build_spring_hook.py.
"""

from __future__ import annotations

# --- Nominal geometry (DIMENSIONS.md "Chapter 17"; all LOW confidence). ---
ROD_DIA = 1.4  # wire diameter
SHANK_RISE = 7.6  # straight shank rise
ELBOW_R = 1.5  # centreline bend radius
ARM_RUN = 2.5  # horizontal hook arm

# --- Derived. ---
ARM_HEIGHT = SHANK_RISE + ELBOW_R  # 9.1 arm centreline above the shank base
ARM_TIP_X = ELBOW_R + ARM_RUN  # 4.0 arm tip


# --- Marked-dimension contract. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HookPath": {"Rise", "ArmRun"},
    "WireProfile": {"RodDia"},
}

DRAWING_NOTES = "\n".join(
    (
        "1. OPEN J-HOOK: SHANK, 90 DEG ELBOW",
        "   R1.5 CL, THEN A 2.5 ARM.",
        "2. SHANK SEATS IN THE SUMMING-LEVER",
        "   PLATE BORE; ARM CATCHES THE",
        "   CHANNEL-SPRING BOTTOM EYE.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 5:1"
