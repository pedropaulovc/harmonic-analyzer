r"""Magnifying-lever nominal geometry -- the drawing-FREE constant block shared
by the part build, its ``_spec`` (drawing contract) and ``build_magnifier_assembly``
(which imports the knife-axis station).

PURE DATA, no SolidWorks/COM and no drawing imports.  Kept SEPARATE from
``magnifying_lever_spec`` on purpose (the ``column_clamp_front_geom`` precedent):
the assembly depends -- via ``_buildgraph.module_deps_of`` -- on whatever module
it imports a constant from, so the drawing contract (notes / marked-dimension
map) must NOT live here, else a print-note edit would move the assembly's recipe
digest and force a needless rebuild.  ``_spec`` re-exports these for its
drawing-side consumers and adds only the drawing data.
"""

from __future__ import annotations

# --- rod nominals (DIMENSIONS.md ch20; Ø6 photo-scaled, low) ------------------
ROD_LENGTH = 165.0  # calibrated p1, x -200..-35 (med; supersedes the 310 "4x" guess)
ROD_DIA = 6.0  # round brass rod (low)

# --- knife-edge pivot axis (KnifeAxis = Axis2) --------------------------------
# The lever does NOT spin in the bracket collar: it EXTENDS FROM the pivoted
# summing bar and pivots WITH it about the knife-edge ridge (engineerguy video
# 2/4 + 4/4; the tip draws a ~6 mm arc, and the clamp's position along the rod --
# the radius from this pivot -- is what sets the <=4x magnification). The ridge
# line runs along Z at machine (pre-mirror) (15, 1018.484); in lever-local coords
# (assembly placement (-200, 990, -85), rod along +X) that is (215, 5.134).
# Duplicated literals -- build_magnifier_assembly asserts them against
# build_summing_assembly's KNIFE/KNIFE_CONTACT_Y and its own placement.
KNIFE_LOCAL_X = 215.0
KNIFE_LOCAL_Y = 5.134
