r"""Pen-wire geometry nominals -- the prose-free import surface for assemblies.

``build_pn_pen_assembly`` needs the wire's endpoint anchors and run length, but
importing ``build_pn_pen_wire`` for them folded the whole part build -- including
``pn_pen_wire_spec``'s DRAWING_NOTES prose -- into the pen assembly recipe (codex
#361): a text-only note edit escalated to a full COM re-insert of the assembly.
Assemblies import THIS module; ``build_pn_pen_wire`` re-imports the same
constants so the two can never drift.
"""

from __future__ import annotations

from mg_magnifying_wheel_geom import PEN_WIRE_DIA, RIM_WIRE_R
from mg_wheel_bar_geom import WHEEL_X
from paper_drive_geom import PEN_ROD_X, PEN_Z_MID
from pn_pen_carriage_geom import STUD_HEAD_TOP_REST_Y

WIRE_DIA = PEN_WIRE_DIA  # hair-thin in the photos; renderable stand-in (low)

# --- endpoint anchors (machine frame; asserted by build_pn_pen_assembly) --------
WHEEL_BAR_Y = 575.7  # wheel axis height = the vertical-tangent point's y
# The rim groove's mid-plane IS the pen rod line: the wire hangs plumb from the
# rim tangent onto the adjuster stud's eye on the rod axis.
WHEEL_MID_Z = PEN_Z_MID

# Hanging run: the wire centre rides the rim groove at RIM_WIRE_R; it leaves
# the groove at the pen-rod-side (3 o'clock from the front) tangent, straight
# down onto the adjuster stud's eye head (the tie-off through the eye is implied).
WIRE_X = round(WHEEL_X - RIM_WIRE_R, 6)  # 3.8
if WIRE_X != PEN_ROD_X:
    raise AssertionError("the pen wire must hang plumb onto the rod axis")
WIRE_BOTTOM = (WIRE_X, STUD_HEAD_TOP_REST_Y, WHEEL_MID_Z)
WIRE_LEN = round(WHEEL_BAR_Y - STUD_HEAD_TOP_REST_Y, 6)
