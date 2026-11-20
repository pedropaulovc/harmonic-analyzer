"""Magnifying-wheel rim and pen-wire interface, without wheel checks/solvers."""

from __future__ import annotations

from _mcmaster_9666k142 import DIA as _WIRE_DIA

# --- rim (DIMENSIONS.md ch21: Ø100 annotated) ----------------------------------
# The rim and the groove bottom set the pen interfaces and the 5:1 wire ratio:
# millimetre nominals, printed rounded on the inch sheet (#290).
RIM_OUTER_DIA = 100.0
RIM_RING_RADIAL = 6.0
RIM_AXIAL = 8.0  # centred on the spokes' mid-plane
RIM_INNER_DIA = RIM_OUTER_DIA - 2 * RIM_RING_RADIAL  # 88
# Pen-wire U-groove on the rim's mid-plane: a R.024 bottom with straight walls.
GROOVE_R = 0.6096  # .024
# The pen wire the groove carries: the fitted 9666K142 wire itself
# (sh_vn_music_wire_pen_geom), no wider lane.
PEN_WIRE_DIA = _WIRE_DIA
# The wire-centre radius the 5:1 ratio and the pen rod line are laid out on.
# The groove bottom seats the wire there (owner ruling 2026-11-20 on #2687,
# "A": the seat surfaces move out so the wire centres stay where they were).
# Both groove sizes print .XXX on the title block's row: the seat proof is
# mg_magnifying_wheel_spec's.
RIM_WIRE_R = 49.2
GROOVE_BOTTOM_DIA = round(2.0 * RIM_WIRE_R - PEN_WIRE_DIA, 6)  # 98.1968
GROOVE_DEPTH = (RIM_OUTER_DIA - GROOVE_BOTTOM_DIA) / 2.0  # 0.9016
