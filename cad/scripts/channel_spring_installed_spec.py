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

# Installed (in-machine) eye anchor heights -- the assembly-facing placement
# contract (build_channel_assembly imports these; moved here from
# build_channel_spring_installed so the assembly needs no builder import).
LEVER_EYE_Y = 1096.4234  # LIVE neutral top eye = lever spring hole 1099.79 -
# drop 3.37 (ch14 ROM re-derive: the LEVEL rocker rest pose flattens the neutral
# lever tilt to -0.002 deg, dropping the eye 0.73). Carried +33.9 by the
# 2026-07-24 upper-frame re-anchor, with the lever bank it hangs from. The assembly's solve_state is the authority --
# verify:math spring:neutral-body-canonical guards this value.
PLATE_EYE_Y = 1019.89  # bottom eye centre, ABOVE the .cs plate (top 1015.89) on
# the spring-hook arm: plate bottom 1010.79 + hook arm height (SHANK_RISE 7.6 +
# ELBOW_R 1.5 = 9.1). High enough that the eye's O5.5 ring clears the plate (its
# bottom 1016.64 > 1015.89). The spring no longer threads the plate -- the hook bridges it.

COIL_ID = COIL_OD - 2.0 * WIRE_DIA  # 4.5
MEAN_DIA = COIL_OD - WIRE_DIA  # 5.5
HOOK_LEAD = 2.0 * WIRE_DIA
HOOK_CL_RADIUS = MEAN_DIA / 2.0
FREE_EYE_C2C = FREE_BODY_LENGTH + 2.0 * HOOK_LEAD
# Installed (in-machine) stretched body length -- exact (61.9834); the table
# renders it .2f. build_channel_spring_installed and the channel assembly both
# derive from this single value.
INSTALLED_BODY_LENGTH = LEVER_EYE_Y - PLATE_EYE_Y - 2.0 * HOOK_LEAD
INSTALLED_EYE_C2C = round(INSTALLED_BODY_LENGTH + 2.0 * HOOK_LEAD, 2)
FREE_PITCH = FREE_BODY_LENGTH / COIL_COUNT  # 1.14 -- NOT close-wound
# Nominal rate k = G d^4 / (8 Dm^3 n), ASTM A228 G = 79.3 GPa -- stated REF so
# the table carries a functional requirement, not just geometry.
SPRING_RATE_REF = 79300.0 * WIRE_DIA**4 / (8.0 * MEAN_DIA**3 * COIL_COUNT)

# The spec-sheet data table + marked-dimension contract (DRAWING_DIMENSIONS /
# DRAWING_NOTES / ISOMETRIC_VIEW_NOTE) live in ``channel_spring_installed_notes``
# -- ``_spring`` (in the channel-assembly closure) imports this module, so
# drawing-only data here would put every table edit in the assembly rebuild
# closure (codex #354).
