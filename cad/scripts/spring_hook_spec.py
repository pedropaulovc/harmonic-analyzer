r"""Spring-hook dimensional contract -- the single source of truth shared by the
part build (``build_spring_hook.py``) and its manufacturing drawing
(``draw_spring_hook.py``).

PURE DATA, no SolidWorks/COM imports.  A small formed-wire open J-hook (like the
crank pin, it carries only a couple of graphical dimensions plus notes).  Values
MUST match build_spring_hook.py.
"""

from __future__ import annotations

from _surface_finish import SurfaceFinishControl

# --- Nominal geometry (DIMENSIONS.md "Chapter 17"; all LOW confidence). ---
ROD_DIA = 1.4  # wire diameter
SHANK_RISE = 7.6  # straight shank rise
ELBOW_R = 1.5  # centreline bend radius
ARM_RUN = 2.5  # horizontal hook arm

# --- Derived. ---
ARM_HEIGHT = SHANK_RISE + ELBOW_R  # 9.1 arm centreline above the shank base
ARM_TIP_X = ELBOW_R + ARM_RUN  # 4.0 arm tip

# No roughness callouts: the shank SEATS in the coefficient-plate bore and
# hangs there, nothing runs on it; the title block's Ra 3.2 covers every face
# (cad/docs/drawing-simplicity-policy.md rule 5).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()


# Drawing prose + marked-dimension contract (DRAWING_DIMENSIONS /
# DRAWING_NOTES / ISOMETRIC_VIEW_NOTE) live in ``spring_hook_notes`` --
# ``build_channel_assembly`` imports this module, so drawing-only data here
# would put every notes edit in the assembly rebuild closure (codex #354).
