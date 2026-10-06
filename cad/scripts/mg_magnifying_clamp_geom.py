r"""Magnifying-clamp nominal geometry -- the drawing-FREE constant block shared
by the part build, its ``_spec`` (drawing contract) and ``build_magnifier_assembly``
(which imports the block depth + the two bore stations to place the clamp on the
lever rod).

PURE DATA, no SolidWorks/COM and no drawing imports (the
``column_clamp_front_geom`` precedent): the assembly depends -- via
``_buildgraph.module_deps_of`` -- on whatever module it imports a constant from,
so the drawing contract must NOT live here.  ``_spec`` re-exports these and adds
the drawing data.
"""

from __future__ import annotations

# --- block envelope (DIMENSIONS.md ch20, p.48, low) ---------------------------
BLOCK_WIDTH = 20.0  # X
BLOCK_HEIGHT = 26.0  # Y
BLOCK_DEPTH = 12.0  # Z

# --- rod bores (engineered running/slip fits, 0.2 mm clearance over their rods)
LEVER_BORE_DIA = 6.2  # Ø6 lever + clearance (along Z)
LEVER_BORE_Y = 19.0  # bore centre height
ROD_BORE_DIA = 5.2  # Ø5 vertical rod + clearance (along Y)
ROD_BORE_X = 6.5  # skew offset from the lever-bore axis plane
