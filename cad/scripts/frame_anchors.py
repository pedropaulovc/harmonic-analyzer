r"""Upper-frame anchor stations -- the ONE import surface for the four numbers
every column-clamped or frame-carried part derives from.

PURE DATA, no SolidWorks/COM and no drawing imports (the
``column_clamp_front_geom`` precedent). It exists for two reasons:

1. **One chokepoint.** The columns, the top-frame casting, the top-lever bank,
   the ball mounts, the support/wheel bars, the platen and pen lines and the
   gooseneck socket all hang off the same four measured stations
   (``cad/config/machine/frame.yaml``). Reading them here -- never re-pasting a
   literal -- is what makes a re-anchor a config edit plus a rebuild.
2. **The build graph reads string literals.** ``_buildgraph._references`` decides
   an assembly's DAG edges by scanning its script for ``"<dashed-stem>"``
   literals, and ``frame`` is itself an ASSEMBLY stem -- so a bare
   ``_config.machine("frame", ...)`` call inside an assembly script reads as a
   (false) dependency on ``frame.SLDASM``. Importing from here keeps the literal
   in a module the matcher never scans, while ``config_files_of`` still follows
   the import and keeps ``machine/frame.yaml`` in the recipe.
"""

from __future__ import annotations

import _config

COLUMN_X = float(_config.machine("frame", "column_x_mm"))  # 203.8, machine |x|
COLUMN_Z = float(_config.machine("frame", "column_z_mm"))  # 117.5, machine |z|
TOP_FACE_Y = float(_config.machine("frame", "top_frame_top_y_mm"))  # 1074.6
RAIL_HEIGHT = float(_config.machine("frame", "top_frame_height_mm"))  # 41.0
RAIL_WIDTH = float(_config.machine("frame", "top_frame_rail_width_mm"))  # 34.0

# --- derived (kept here so the arithmetic is stated once) --------------------
UNDERSIDE_Y = TOP_FACE_Y - RAIL_HEIGHT  # 1033.6: rail + cross-rib underside
MID_Y = TOP_FACE_Y - RAIL_HEIGHT / 2.0  # 1054.1: the gooseneck set-screw axis
RAIL_HALF = RAIL_WIDTH / 2.0  # 17.0: outer rail face = COLUMN_X +- this
