r"""Gooseneck geometry nominals; the light assembly import surface.

Part origin is the vertical leg's mid-height. The arm runs toward negative
part X; the summing assembly places it Ry(180), so machine X = COLUMN_X -
part X. Sliding the post sets spring tension, not the part's dimensions.
"""

from __future__ import annotations

from vn_counter_spring_stock_geom import END_OCCUPIED_WIDTH_MM

TUBE_DIA = 16.0  # DIMENSIONS.md ch19: scaled vs frame anchors (med)
WALL_T = 2.0  # tube wall: O16 x 2.0 WALL tube stock (codex review #361)
ARM_Y = 163.3  # arm/screw axis above the part origin
BEND_R = 51.0  # 90-degree bend centreline radius (med)
SPRING_EYE_X = -105.8
SPRING_EYE_GAP = END_OCCUPIED_WIDTH_MM
ARM_END_X = SPRING_EYE_X + SPRING_EYE_GAP / 2.0
ARM_RUN = -ARM_END_X - BEND_R
PLUG_LENGTH = 16.0
