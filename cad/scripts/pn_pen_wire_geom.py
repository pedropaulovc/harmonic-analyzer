r"""Pen-wire geometry nominals -- the prose-free import surface for assemblies.

``build_pen_assembly`` needs the wire's endpoint anchors and run length, but
importing ``build_pen_wire`` for them folded the whole part build -- including
``pen_wire_spec``'s DRAWING_NOTES prose -- into the pen assembly recipe (codex
#361, same closure leak the channel batch fixed with its ``<part>_notes``
split): a text-only note edit escalated to a full COM re-insert of the
assembly.  Assemblies import THIS module; ``build_pen_wire`` re-imports the
same constants so the two can never drift.
"""

from __future__ import annotations

from _inch import inch
from mg_magnifying_wheel_geom import PEN_WIRE_DIA, RIM_WIRE_R

WIRE_DIA = PEN_WIRE_DIA  # hair-thin in the photos; renderable stand-in (low)

# --- endpoint anchors (machine frame; asserted by build_pn_pen_assembly) --------
WHEEL_X = inch(33, 16)  # 2-1/16: magnifying-wheel centre (build_mg_magnifier_assembly.WHEEL_X)
WHEEL_BAR_Y = inch(363, 16)  # 22-11/16: wheel axis height = the vertical-tangent point's y
WHEEL_MID_Z = -147.75375  # rim groove mid-plane (mg_wheel_group.WHEEL_MID_Z, derived)
# pen-rod wire hole: PEN_ROD_POS y 14-1/2 + rod-local 5-11/16 = 20-3/16 (asserted
# by build_pn_pen_assembly)
WIRE_HOLE_Y = inch(323, 16)

# Hanging run: the wire centre rides the rim groove at RIM_WIRE_R; it leaves
# the groove at the pen-rod-side (3 o'clock from the front) tangent, straight
# down to the wire-hole level (the wire runs behind the rod, clear of its
# back face -- the tie-off through the hole is implied).
WIRE_X = round(WHEEL_X - RIM_WIRE_R, 6)  # 3.5625
WIRE_BOTTOM = (WIRE_X, WIRE_HOLE_Y, WHEEL_MID_Z)
WIRE_LEN = WHEEL_BAR_Y - WIRE_HOLE_Y  # 63.5 (2-1/2)
