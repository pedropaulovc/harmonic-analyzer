"""Magnifying-wheel rim and pen-wire interface, without wheel checks/solvers."""

from __future__ import annotations

# --- rim (DIMENSIONS.md ch21: Ø100 annotated) ----------------------------------
RIM_OUTER_DIA = 100.0
RIM_RING_RADIAL = 6.0
RIM_AXIAL = 8.0  # centred on the spokes' mid-plane
RIM_INNER_DIA = RIM_OUTER_DIA - 2 * RIM_RING_RADIAL  # 88
# Pen-wire U-groove on the rim's mid-plane: a R0.6 bottom with straight walls.
GROOVE_R = 0.6
GROOVE_DEPTH = 1.2
GROOVE_BOTTOM_DIA = RIM_OUTER_DIA - 2 * GROOVE_DEPTH  # 97.6
# Printed bands, (upper, lower): the seat proof is mg_magnifying_wheel_spec's.
GROOVE_R_BAND = (0.10, -0.10)
GROOVE_BOTTOM_BAND = (0.10, -0.10)
PEN_WIRE_DIA = 0.8  # the pen wire the groove carries (sh_vn_music_wire_pen_geom)
RIM_WIRE_R = round(GROOVE_BOTTOM_DIA / 2.0 + PEN_WIRE_DIA / 2.0, 6)  # 49.2
