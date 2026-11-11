"""Cone-shaft stations, measured along the shaft from its pivot end.

Placement-independent: these read only the cone seat pitch and the shaft and
collar stack, never the machine frame. ``cone_line`` maps them into the
machine; parts that need only shaft-local distances (the cone set stack and
the cone gear sheets that print from it) read them here, so they do not depend
on the channel table that places the line.
"""

from __future__ import annotations

from cone_pitch import SEAT_PITCH
from _cone_axis_constants import GEAR_AXIS_SHIFT

# Every station stays on the historical 6.5 cone reference face: the gears
# grew SOUTH to the full seat pitch with their north faces fixed, so they
# touch (dt_cone_gear_stack; build_dt_drive_train_assembly).
CONE_FACE_STATION_REFERENCE = 6.5

# Cone shaft: pivot end at seat station -28.25 from the T120 centre
# (25 journal + half of the first 6.5 face -- build_dt_cone_gear_shaft.py).
SHAFT_T120_STATION = 25.0 + CONE_FACE_STATION_REFERENCE / 2.0  # 28.25

# T006 is the reference gear for the tip-end stack: its north face is the
# fixed layout reference the tip cluster's stations are laid out from
# (cone_tip_cluster).
T006_CENTER_STATION = SHAFT_T120_STATION + GEAR_AXIS_SHIFT + 19 * SEAT_PITCH
T006_NORTH_FACE = T006_CENTER_STATION + CONE_FACE_STATION_REFERENCE / 2.0
# The pivot's station north of T006: 23.0 plus TIP_END_EXTENSION_MM.  The
# extension was 7.5, then 7.5 + 0.50 when the retired MHA-DT-VN-54 collar's
# body moved north; the C1 keyed tip (owner decision 2026-11-09, PR #1992)
# keeps the swing-platform pivot where it is, so the 8.0 is a literal now and
# the pivot's station north of T006 is unchanged.  PIVOT_STATION itself
# follows T006, 19 seat pitches out: the #1038 re-pitch moved it by
# 19 x (7.452801 - 6.875612) = +10.97.
TIP_END_EXTENSION_MM = 8.0
PIVOT_STATION = T006_NORTH_FACE + 23.0 + TIP_END_EXTENSION_MM
