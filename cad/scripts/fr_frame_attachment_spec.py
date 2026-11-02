"""Frame cross-screw installation geometry, in millimetres (decimal-inch grid).

Reconstruction approved by the user: stock 90280A837 screws pass through
match-drilled column walls and engage both casting walls. No bonded inserts.
The sockets and recessed purchased caps preserve the finished frame height.
"""

from frame_column_stations import (
    COLUMN_SOCKET_DEPTH,
    COLUMN_SOCKET_DIAMETER,  # noqa: F401  re-exported for existing importers
)
from fr_harmonic_base_spec import GREEN_TOP
from fr_vn_tube_frame_cap_spec import TOTAL_HEIGHT as CAP_HEIGHT, WALL_THICKNESS as CAP_ROOF

# The socket pair now lives in frame_column_stations: fr_harmonic_base_spec
# authors the socket-bore surface finishes and so needs the bore size, but
# this module derives its heights from fr_harmonic_base_spec and cannot be
# imported from there. The socket mouths open on the green land (user ruling
# 2026-10-09: the black deck is a raised pad clear of the columns), so the
# seated tube end stays at y 25.4 and the cross screws stay 1/2 in above it.
SOCKET_MOUTH_Y = GREEN_TOP
COLUMN_BOTTOM_Y = SOCKET_MOUTH_Y - COLUMN_SOCKET_DEPTH
BASE_SCREW_Y = COLUMN_BOTTOM_Y + 12.7  # .500 above the seated tube end
BASE_SCREW_SEAT_Z = 132.9944  # 5.236
# The top frame's insert plane (its mid plane) and its taps, .72 below its
# rail top (MHA-FR-02 prints them at .XX off that face), .0015 below the mid
# plane. The faced underside stays on the 999.7 plane that the summing knife
# mounts clamp to (build_sm_knife_mount.CASTING_UNDERSIDE_Y) and the hanger
# washers seat on, one 1.437 rail band (36.4998) below the rail top, so the mid
# plane is half a band above it. That leaves the installed tap axis off the
# inch grid (40.07527); the tube's upper hole is match-drilled from these taps
# and prints no station. The plane snaps to the inch grid together with the
# summing KNIFE_Y and the channel FULCRUM (#290 FR plane-snap PR).
TOP_FRAME_UNDERSIDE_Y = 999.7
TOP_FRAME_MID_Y = TOP_FRAME_UNDERSIDE_Y + 36.4998 / 2.0  # 1017.9499
TOP_SCREW_Y = TOP_FRAME_MID_Y - 0.0381  # 1017.9118, 40.07527
# MHA-FR-00 step 3 sets every corner's top cross-bore axis to one height above
# the base underside. It is a dimension on the frame assembly's blanked
# TopAxisSetting sketch (a construction line up the +X column's axis), which
# the drawing imports. Off the inch grid until the plane snap, it prints four
# places with its own band, the .XX grade the title block can't give a
# four-place print.
TOP_AXIS_SETTING_FEATURE = "TopAxisSetting"
TOP_AXIS_HEIGHT_DIMENSION = "TopCrossBoreAxisHeight"
TOP_AXIS_HEIGHT_PLACES = 4
TOP_AXIS_HEIGHT_BAND_MM = 0.254  # +/-.010
# Top-frame bosses take a flush counterbore, not a spotface: the stock
# fillister head (HEAD_H 4.572) sits below the Ø.35 mouth's lowest barrel point
# at every printed corner, and the floor stands far enough outboard to keep
# drawing-guidelines.md rule 17 (walls and webs)'s .080 to the cap recess at its .XX band (build_fr_top_frame proves
# both; at 128.1 the ligament was 1.80, codex review of 080fda97).
TOP_SCREW_SEAT_Z = 128.524  # 5.060 (.65 off the column line once it snaps to 4.410)
TOP_SCREW_COUNTERBORE_DIAMETER = 8.89  # .35
# The base keeps its spotface seat at the same diameter.
SCREW_SPOTFACE_DIAMETER = 8.89  # .35
# The casting is tapped continuously across the interrupted column socket.
# Tube walls are clearance-drilled separately after matching their positions.
CASTING_FULL_THREAD_DEPTH = 45.974  # 1.81
# 1.93 MIN: the tap drill keeps two bottoming-tap pitches past the deepest
# printed thread (1.81 + .01 .XX band), not just past its nominal.
CASTING_TAP_DRILL_DEPTH = 49.022  # 1.93
# Upper and lower screws share the same stock 1-3/4 in SKU and full thread.
# The upper drill runs .13 past the full thread: two bottoming-tap pitches
# remain with both depths at the ends of their printed bands.
TOP_CASTING_TAP_DRILL_DEPTH = CASTING_FULL_THREAD_DEPTH + 3.302  # 1.94
TUBE_CROSS_HOLE_DIAMETER = 5.0038  # .197

CAP_TOP_Y = 1044.8036  # 41.134
CAP_MOUTH_Y = CAP_TOP_Y - CAP_HEIGHT
TUBE_TOP_Y = CAP_TOP_Y - CAP_ROOF
TUBE_CUT_LENGTH = TUBE_TOP_Y - COLUMN_BOTTOM_Y
TUBE_TOP_CHAMFER = 0.508  # .02
CAP_RECESS_DIAMETER = 27.5082  # 1.083
CAP_RECESS_DEPTH = 16.3068  # .642
