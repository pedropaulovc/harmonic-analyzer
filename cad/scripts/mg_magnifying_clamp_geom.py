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

from _inch import inch

# --- block envelope (DIMENSIONS.md ch20, p.48, low; all-inch) ------------------
BLOCK_WIDTH = inch(13, 16)  # X (was 20.0)
BLOCK_HEIGHT = inch(1)  # Y (was 26.0)
BLOCK_DEPTH = inch(1, 2)  # Z (was 12.0)

# --- rod bores (engineered running/slip fits over their rods; drill-chart sizes)
LEVER_BORE_DIA = inch(0.257)  # letter F drill on the Ø1/4 lever (along Z; was 6.2)
LEVER_BORE_Y = inch(3, 4)  # bore centre height (was 19.0)
ROD_BORE_DIA = inch(0.196)  # #9 drill on the Ø3/16 vertical rod (along Y; was 5.2)
ROD_BORE_X = inch(1, 4)  # skew offset from the lever-bore axis plane (was 6.5)
