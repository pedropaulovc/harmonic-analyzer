r"""Pen-wire geometry nominals -- the prose-free import surface for assemblies.

``build_pn_pen_assembly`` needs the wire's endpoint anchors and run length, but
importing ``build_pn_vn_pen_wire`` for them folded the whole part build -- including
``pn_vn_pen_wire_spec``'s DRAWING_NOTES prose -- into the pen assembly recipe (codex
#361): a text-only note edit escalated to a full COM re-insert of the assembly.
Assemblies import THIS module; ``build_pn_vn_pen_wire`` re-imports the same
constants so the two can never drift.
"""

from __future__ import annotations

import mg_wheel_bar_geom as _wheel_bar
from _mcmaster_9666k56 import DIA_MAX as _STOCK_DIA_MAX, DIA_MIN as _STOCK_DIA_MIN
from _mg_wheel_rim_geometry import PEN_WIRE_DIA, RIM_WIRE_R
from mg_wheel_bar_geom import WHEEL_X
from _recording_geometry import PEN_ROD_X, PEN_Z_MID
from pn_pen_carriage_geom import STUD_HEAD_TOP_REST_Y

# Ø0.8 design nominal: inside the purchased 9666K56 0.031 +/-0.001 in band.
WIRE_DIA = PEN_WIRE_DIA
if not _STOCK_DIA_MIN <= WIRE_DIA <= _STOCK_DIA_MAX:
    raise AssertionError("pen wire Ø must lie in the 9666K56 catalogue band")

# --- endpoint anchors (machine frame; asserted by build_pn_pen_assembly) --------
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
WIRE_LEN = round(_wheel_bar.WHEEL_BAR_Y - STUD_HEAD_TOP_REST_Y, 6)
