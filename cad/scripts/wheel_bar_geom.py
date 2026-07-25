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
BAR_LENGTH = 240.8  # clamped end 29 past the west column + free end (photo,
# med). +6.8 with the 2026-07-24 frame re-anchor: the free end stays put (it
# carries the base-anchored pen hanger) while the clamped end follows the
# column line out.

# --- hole stations (local X; the bores run along Z, the front-back axis) --------
SCREW_HOLE_X = -117.9  # pen-hanger screw hole (near the free end); the free
# end did not move in MACHINE space, so its LOCAL station shifted with the
# lengthened bar's new centre
CLAMP_HOLE_X = (73.9, 108.9)  # clamp-screw holes flanking the column line at
# local +91.4 = column 203.8 - centre 112.4 (ears at +-17.5)

# Native Hole Wizard clearance contracts.  Keep the exact cut diameters beside
# the stations so the part and its note-based drawing cannot disagree about
# which clearance fit a machinist must drill.
PEN_HANGER_HOLE_SIZE = "#6"
PEN_HANGER_HOLE_FIT = "close"
PEN_HANGER_HOLE_DIA = 3.912
CLAMP_HOLE_SIZE = "#8"
CLAMP_HOLE_FIT = "normal"
CLAMP_HOLE_DIA = 4.978
