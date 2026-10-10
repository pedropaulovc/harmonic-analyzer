"""Cone-shaft stations, measured along the shaft from its pivot end.

Placement-independent: these read only the cone seat pitch and the shaft and
collar stack, never the machine frame. ``cone_line`` maps them into the
machine; parts that need only shaft-local distances (the cone set stack and
the cone gear sheets that print from it) read them here, so they do not depend
on the channel table that places the line.
"""

from __future__ import annotations

from cone_pitch import SEAT_PITCH
from cone_shaft_land_bands import TIP_COLLAR_BODY_NORTH_SHIFT_MM
from dt_cone_pivot_post_installation import GEAR_AXIS_SHIFT

# Every station stays on the historical 6.5 cone reference face: the gears
# grew SOUTH to the full seat pitch with their north faces fixed, so they
# touch (dt_cone_gear_stack; build_dt_drive_train_assembly).
CONE_FACE_STATION_REFERENCE = 6.5

# Cone shaft: pivot end at seat station -28.25 from the T120 centre
# (25 journal + half of the first 6.5 face -- build_dt_cone_gear_shaft.py).
SHAFT_T120_STATION = 25.0 + CONE_FACE_STATION_REFERENCE / 2.0  # 28.25

# T006 is the reference gear for the tip-end stack: its north face is the
# fixed layout reference the MHA-VN-016 stack collar is feeler-set off.
T006_CENTER_STATION = SHAFT_T120_STATION + GEAR_AXIS_SHIFT + 19 * SEAT_PITCH
T006_NORTH_FACE = T006_CENTER_STATION + CONE_FACE_STATION_REFERENCE / 2.0
# Extend the tip, block and pivot by the SAME northward delta that moves only
# the custom collar's large body and tap. Its small south end remains feeler-
# set off T006; collar-to-block and block-to-pivot clearances are invariant.
# The retained 7.5-mm extension and ordinary bands are not regraded.
TIP_END_EXTENSION_MM = 7.5 + TIP_COLLAR_BODY_NORTH_SHIFT_MM
PIVOT_STATION = T006_NORTH_FACE + 23.0 + TIP_END_EXTENSION_MM
