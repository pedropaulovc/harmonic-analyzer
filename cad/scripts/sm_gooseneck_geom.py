r"""Gooseneck geometry nominals; the light assembly import surface.

Part origin is the vertical leg's mid-height. The arm runs toward negative
part X; the summing assembly places it Ry(180), so machine X = COLUMN_X -
part X. Sliding the post sets spring tension, not the part's dimensions.
"""

from __future__ import annotations

from _inch import inch
from vn_counter_spring_stock_geom import END_OCCUPIED_WIDTH_MM

TUBE_DIA = inch(5, 8)  # 15.875 tube stock OD (was Ø16; DIMENSIONS.md ch19 scale)
WALL_T = inch(0.083)  # 2.1082: 5/8 OD x .083 (14 ga) WALL seamless tube stock
# Left in mm: the arm axis, eye station, arm end and plug length are stamped in
# the counter spring's native calibration (settled_spring_seats.
# counter_upper_support_geometry / gooseneck_origin_y_mm); snapping them needs
# diagnostics/calibrate_spring_seats.py --write on a farm seat.
ARM_Y = 163.3  # arm/screw axis above the part origin
BEND_R = inch(2)  # 50.8 90-degree bend centreline radius (was R51)
SPRING_EYE_X = -105.8
SPRING_EYE_GAP = END_OCCUPIED_WIDTH_MM
ARM_END_X = SPRING_EYE_X + SPRING_EYE_GAP / 2.0
ARM_RUN = -ARM_END_X - BEND_R
PLUG_LENGTH = 8.0
