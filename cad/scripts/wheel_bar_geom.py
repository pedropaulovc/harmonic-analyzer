r"""Wheel-bar nominal geometry -- the drawing-FREE constant block shared by the
part build, its ``_spec`` (drawing contract) and ``build_magnifier_assembly``
(which imports the bar depth + the clamp-hole stations to seat the bar on the
column clamp-screw lines).

PURE DATA, no SolidWorks/COM and no drawing imports (the
``column_clamp_front_geom`` precedent): the assembly depends on whatever module
it imports a constant from, so the drawing contract must NOT live here.
"""

from __future__ import annotations

# --- bar section + length (DIMENSIONS.md ch21; M6.8 ch30 8-view pass) ----------
BAR_SIDE = 10.0  # tall (Y)
BAR_DEPTH = 9.0  # deep (Z) -- support-bar stock; back face seats on the clamp arc
BAR_LENGTH = 234.0  # clamped end 29 past the west column + free end (photo, med)

# --- hole stations (local X; the bores run along Z, the front-back axis) --------
SCREW_HOLE_X = -114.5  # pen-hanger screw hole (near the free end)
CLAMP_HOLE_X = (70.5, 105.5)  # clamp-screw holes flanking the column line at +88
