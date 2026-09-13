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
# line runs along Z at machine (pre-mirror) (15, 984.834); in lever-local coords
# (assembly placement (-200, 979.7, -128.3), rod along +X) that is (215, 5.134).
# Duplicated literals -- build_magnifier_assembly asserts them against
# build_summing_assembly's KNIFE/KNIFE_CONTACT_Y and its own placement.
KNIFE_LOCAL_X = 215.0
KNIFE_LOCAL_Y = 5.134

# --- clamp travel along the rod = the magnification range ---------------------
# The sliding clamp (magnifying_clamp_geom.BLOCK_DEPTH along the rod) rides the
# rod between its free west tip (local 0) and the bracket collar that carries
# the rod at its east end. Its radius from the knife axis, over the summing
# lever's spring-hook arm, is the magnification the operator sets (book p. 46:
# "up to 4x"); the reachable band is what cad/scripts/error_budget.py derives
# the pen scale and the ordinate-capacity rule from. Lever-local x (rod along
# +X, knife at KNIFE_LOCAL_X); build_magnifier_assembly asserts its bracket and
# clamp placements against these, so a layout move fails loud there.
COLLAR_LOCAL_X = 160.0  # bracket collar centre on the rod (machine x +40)
COLLAR_HALF_LEN = 5.0  # == build_magnifying_bracket.COLLAR_HALF_LEN (asserted)
CLAMP_LOCAL_X = 50.0  # as-built clamp centre (machine x +150, p.46/48 insets)


def clamp_radius_band(block_depth: float) -> tuple[float, float, float]:
    """(min, as-built, max) knife -> clamp-centre radius, mm, for a clamp of
    ``block_depth`` along the rod: the block face against the collar face
    (minimum magnification), the as-built pose, the block flush with the rod
    tip (maximum -- a mechanical bound; the wire route past the as-built pose
    is not gated)."""
    half = block_depth / 2.0
    nearest = COLLAR_LOCAL_X - COLLAR_HALF_LEN - half
    farthest = half
    return (
        KNIFE_LOCAL_X - nearest,
        KNIFE_LOCAL_X - CLAMP_LOCAL_X,
        KNIFE_LOCAL_X - farthest,
    )
