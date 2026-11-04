"""The top-frame casting's faced underside and the stations hung from it.

PURE DATA with no imports, deliberately: MHA-FR-02's faced underside is the
plane the summing knife mounts clamp to and its rail top the seat of the
channel fulcrum keepers, so the knife-mount part, the spring mounts, the
magnifier's bracket joint and the amplitude bar read it alongside the frame.
Their recipes must not fold ``fr_frame_attachment_spec`` (the base,
column-station and cap specs) or ``frame_column_stations`` (the column line)
to get one height. ``fr_frame_attachment_spec`` derives the mid plane and
cross-screw axis from this plane.
"""

from __future__ import annotations

# MHA-FR-02's faced underside, on the inch grid (39.358), and its rail top one
# 1.437 rail band above it (the hanger washers' and fulcrum keepers' seat).
TOP_FRAME_UNDERSIDE_Y = 999.6932  # 39.358
TOP_FRAME_RAIL_TOP_Y = TOP_FRAME_UNDERSIDE_Y + 36.4998  # 1036.193, 40.795
# The fulcrum keepers (MHA-CH-07) seat 36.5 over the underside, as the
# 2026-08-02 contract placed them: 0.0002 above the 1.437 band's rail top, the
# float Main accepted on #2127, so the whole fulcrum chain translates with the
# knife line and every spring seat moves rigidly.
FULCRUM_KEEPER_SEAT_Y = TOP_FRAME_UNDERSIDE_Y + 36.5  # 1036.1932
# The summing knife line (the hex pivot centreline) hangs 20.0 below the
# underside: the knife-mount block's top seat stands 14.866 over the hex
# ridge, which stands 5.134 over the centreline (build_sm_knife_mount checks
# it).
KNIFE_Y = TOP_FRAME_UNDERSIDE_Y - 20.0  # 979.6932, 38.571
