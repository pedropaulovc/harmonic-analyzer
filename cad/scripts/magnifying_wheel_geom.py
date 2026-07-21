r"""Magnifying-wheel nominal geometry -- the drawing-FREE constant block shared
by the part build, its ``_spec`` (drawing contract) and ``build_magnifier_assembly``
(which imports the hub diameter + spoke axial width to place the wheel on its
axle).

PURE DATA, no SolidWorks/COM and no drawing imports (the
``column_clamp_front_geom`` precedent): the assembly depends on whatever module
it imports a constant from, so the drawing contract must NOT live here.
"""

from __future__ import annotations

# --- annotated diameters (DIMENSIONS.md ch21; self-validate 5x = Ø100/Ø20) -----
RIM_OUTER_DIA = 100.0
HUB_DIA = 20.0
SPOKE_COUNT = 6  # counted on the p.51 full-page photo

# --- photo-scaled sections (low) ----------------------------------------------
RIM_RING_RADIAL = 6.0  # rim ring radial thickness
RIM_AXIAL = 8.0  # rim axial width
HUB_AXIAL = 10.0  # brass drum axial length
SPOKE_WIDTH = 5.0
SPOKE_AXIAL = 4.0
BORE_DIA = 5.0  # axle bore

# --- derived spans ------------------------------------------------------------
RIM_INNER_DIA = RIM_OUTER_DIA - 2 * RIM_RING_RADIAL  # 88
SPOKE_OVERLAP = 1.0  # spokes bite into hub and rim so the bodies merge
