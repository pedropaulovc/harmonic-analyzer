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
COIL_BODY_LENGTH = 325.3  # INSTALLED coil body length. The ch. 19 read was
# ~315 at the pre-rederive hang; the top-frame rederive (Cascade A,
# 2026-08-02) dropped the bottom anchor 10.3 with the summing chain while the
# gooseneck top loop stayed at 1370.7, so the modeled installed body
# stretched +10.3. The part models the installed hang, as it always has.
COIL_OD = 12.5  # coil outer diameter
WIRE_DIA = 1.8  # music-wire diameter
COIL_COUNT = 165  # active body coils

COIL_ID = COIL_OD - 2.0 * WIRE_DIA  # 8.9 inner diameter
MEAN_DIA = COIL_OD - WIRE_DIA  # 10.7 mean coil diameter
BOTTOM_HOOK_LEAD = 40.0
TOP_HOOK_LEAD = 2.0 * WIRE_DIA
HOOK_CL_RADIUS = MEAN_DIA / 2.0
FREE_EYE_C2C = COIL_BODY_LENGTH + BOTTOM_HOOK_LEAD + TOP_HOOK_LEAD
FREE_PITCH = COIL_BODY_LENGTH / COIL_COUNT  # 1.97 -- NOT close-wound
# Retained as derived engineering data for design checks; the compact shop
# block needs only wire, OD, free length, active coils, hand, and ends.
SPRING_RATE_REF = 79300.0 * WIRE_DIA**4 / (8.0 * MEAN_DIA**3 * COIL_COUNT)

# The spec-sheet data table + marked-dimension contract (DRAWING_DIMENSIONS /
# DRAWING_NOTES / ISOMETRIC_VIEW_NOTE) live in ``counter_spring_notes`` --
# ``build_summing_assembly`` imports this module, so drawing-only data here
# would put every table edit in the assembly rebuild closure (codex #354).
