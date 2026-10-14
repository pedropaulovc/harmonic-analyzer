"""Cone-shaft stations, measured along the shaft from its pivot end.

Placement-independent: these read only the cone seat pitch and the shaft and
collar stack, never the machine frame. ``cone_line`` maps them into the
machine; parts that need only shaft-local distances (the cone set stack and
the cone gear sheets that print from it) read them here, so they do not depend
on the channel table that places the line.
"""

from __future__ import annotations

from _inch import inch
from cone_pitch import SEAT_PITCH
from dt_cone_pivot_post_installation import GEAR_AXIS_SHIFT

# Every station stays on the historical 6.5 cone reference face: the gears
# grew SOUTH to the full seat pitch with their north faces fixed, so they
# touch (dt_cone_gear_stack; build_dt_drive_train_assembly).  A layout
# reference, not a printed length: changing it would move every gear seat
# against the fixed post (cone_line.POST_STATION), so it stays.
CONE_FACE_STATION_REFERENCE = 6.5

# Cone shaft: pivot end at seat station -28.25 from the T120 centre
# (25 journal + half of the first 6.5 face -- build_dt_cone_gear_shaft.py).
# The station datum only: cone_line hangs the post (fixed POST_STATION) and
# the gear seats off it, so it is a closure anchor and stays in mm.
SHAFT_T120_STATION = 25.0 + CONE_FACE_STATION_REFERENCE / 2.0  # 28.25

# T006 is the reference gear for the tip-end stack: its north face is the
# fixed layout reference the MHA-VN-016 stack collar is feeler-set off.
T006_CENTER_STATION = SHAFT_T120_STATION + GEAR_AXIS_SHIFT + 19 * SEAT_PITCH
T006_NORTH_FACE = T006_CENTER_STATION + CONE_FACE_STATION_REFERENCE / 2.0
# The pivot stands 1-1/4 in north of T006's face: the historical 15/16 in
# T006-to-tip run plus the 5/16 in tip extension that clears the collar,
# block and pivot-screw head (cone_line, build_dt_drive_train_assembly).
# Only the tip, block and pivot follow it; no gear seat moves.
TIP_END_EXTENSION_MM = inch(5, 16)
PIVOT_STATION = T006_NORTH_FACE + inch(15, 16) + TIP_END_EXTENSION_MM
