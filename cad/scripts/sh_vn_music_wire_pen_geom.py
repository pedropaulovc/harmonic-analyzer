r"""Pen-wire geometry nominals -- the prose-free import surface for assemblies.

``build_pn_pen_assembly`` imports these endpoint anchors and run length
directly, while ``build_sh_vn_music_wire`` consumes the same geometry for its
PenWire member. Print notes remain in the separate pure drawing contract.
"""

from __future__ import annotations

import mg_wheel_bar_geom as _wheel_bar
from _mcmaster_9666k142 import DIA as MEMBER_DIA
from _mg_wheel_rim_geometry import PEN_WIRE_DIA, RIM_WIRE_R
from mg_wheel_bar_geom import WHEEL_X
from _recording_geometry import PEN_ROD_X, PEN_Z_MID
from pn_pen_carriage_geom import STUD_HEAD_TOP_REST_Y

CONFIGURATION = "PenWire"

# Ø0.8 is the WIRE LANE the rim groove was laid out for, not the wire: the
# purchased 9666K142 wire is Ø.008 (MEMBER_DIA), modelled at that size on the
# lane's centreline (sh_vn_music_wire_lever_geom).
WIRE_DIA = PEN_WIRE_DIA
if MEMBER_DIA > WIRE_DIA:
    raise AssertionError("the pen wire is fatter than the lane laid out for it")

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
