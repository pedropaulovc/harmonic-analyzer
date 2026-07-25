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

WIRE_DIA = 0.8  # hair-thin in the photos; renderable stand-in (low)
CLEARANCE = 0.25  # surface stand-off (interference-gate margin convention)

# --- endpoint anchors (machine frame; asserted by build_pen_assembly) --------
WHEEL_X = 53.0  # magnifying-wheel centre (build_magnifier_assembly.WHEEL_X)
WHEEL_BAR_Y = 575.7  # wheel axis height = the vertical-tangent point's y
RIM_DIA = 100.0  # ch. 21 annotated (build_magnifying_wheel.RIM_OUTER_DIA)
WHEEL_MID_Z = -152.4  # rim groove mid-plane (wheel mid-plane)
WIRE_HOLE_Y = 513.0  # pen-rod wire hole: PEN_ROD_POS y 398 + local 115

# Hanging run: 0.25 off the rim surface at the pen-rod-side tangent, straight
# down to the wire-hole level (the wire passes 1.7 clear in front of the
# rod's z -154.5 front face -- the tie-off through the hole is implied).
WIRE_X = WHEEL_X - RIM_DIA / 2.0 - WIRE_DIA / 2.0 - CLEARANCE  # 2.35
WIRE_BOTTOM = (WIRE_X, WIRE_HOLE_Y, WHEEL_MID_Z)
WIRE_LEN = WHEEL_BAR_Y - WIRE_HOLE_Y  # 62.7
