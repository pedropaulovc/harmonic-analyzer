"""Frame cross-screw installation geometry, in millimetres.

Reconstruction approved by the user: stock 90280A837 screws pass through
match-drilled column walls and engage both casting walls. No bonded inserts.
The sockets and recessed purchased caps preserve the finished frame height.
"""

from _inch import inch
from frame_column_stations import (
    COLUMN_SOCKET_DEPTH,
    COLUMN_SOCKET_DIAMETER,  # noqa: F401  re-exported for existing importers
)
from fr_harmonic_base_spec import GREEN_TOP
from vn_tube_frame_cap_spec import TOTAL_HEIGHT as CAP_HEIGHT, WALL_THICKNESS as CAP_ROOF

# The socket pair now lives in frame_column_stations: fr_harmonic_base_spec
# authors the socket-bore surface finishes and so needs the bore size, but
# this module derives its heights from fr_harmonic_base_spec and cannot be
# imported from there. The socket mouths open on the green land (user ruling
# 2026-10-09: the black deck is a raised pad clear of the columns), so the
# seated tube end stays at y 25.4 and the cross screws stay 1/2 in above it.
SOCKET_MOUTH_Y = GREEN_TOP
COLUMN_BOTTOM_Y = SOCKET_MOUTH_Y - COLUMN_SOCKET_DEPTH
BASE_SCREW_Y = COLUMN_BOTTOM_Y + inch(1, 2)
BASE_SCREW_SEAT_Z = inch(5.25)  # 133.35 (was 133.0)
# Top-frame ring mid-plane and upper cross-screw axis: 40-1/16 in, so the
# tube's upper cross-hole station (from its inserted end) is 39-1/16 in.
TOP_SCREW_Y = inch(641, 16)  # 1017.5875 (was 1017.95)
# Top-frame bosses take a flush counterbore, not a spotface: the stock
# fillister head (HEAD_H 4.572) sits below the counterbore mouth's lowest barrel point
# at every printed corner, and the floor stands far enough outboard to keep
# drawing-guidelines.md rule 17 (walls and webs)'s 2.0 to the cap recess at its .XX band (build_fr_top_frame proves
# both; at 128.1 the ligament was 1.80, codex review of 080fda97). With the
# 1-3/4 boss the head-recess limit sits below 128.86, so the seat drops to
# 5-1/16 and the recess floor rises 1/32 (CAP_RECESS_DEPTH) for the ligament.
TOP_SCREW_SEAT_Z = inch(81, 16)  # 5-1/16 = 128.5875 (was 128.35)
TOP_SCREW_COUNTERBORE_DIAMETER = inch(3, 8)  # 9.525 (was 9.0)
# The base keeps its spotface seat at the same diameter.
SCREW_SPOTFACE_DIAMETER = inch(3, 8)  # 9.525 (was 9.0)
# The casting is tapped continuously across the interrupted column socket.
# Tube walls are clearance-drilled separately after matching their positions.
CASTING_FULL_THREAD_DEPTH = inch(29, 16)  # 1-13/16 = 46.0375 (was 46.0)
# 1-15/16 MIN: the tap drill keeps two bottoming-tap pitches past the deepest
# printed thread (46.04 + 0.51 .XX band), not just past its nominal.
CASTING_TAP_DRILL_DEPTH = inch(31, 16)  # 49.2125 (was 49.0)
# Upper and lower screws share the same stock 1-3/4 in SKU and full thread.
# The upper sheet prints depths to .X (±0.8): a 1/8 in lead retains two
# bottoming-tap pitches at worst case; the lower .XX drill stays unchanged.
TOP_CASTING_TAP_DRILL_DEPTH = CASTING_FULL_THREAD_DEPTH + inch(1, 8)
# #9 drill (.1960): clearance through both tube walls for the #10-32 shank.
TUBE_CROSS_HOLE_DIAMETER = 4.978  # was 5.0

# The tube is cut to a 1/16 in length; the purchased cap's roof stacks on it.
TUBE_CUT_LENGTH = inch(321, 8)  # 40-1/8 = 1019.175 (was 1018.765, derived)
TUBE_TOP_Y = COLUMN_BOTTOM_Y + TUBE_CUT_LENGTH
CAP_TOP_Y = TUBE_TOP_Y + CAP_ROOF  # 1045.21 (was 1044.8)
CAP_MOUTH_Y = CAP_TOP_Y - CAP_HEIGHT
TUBE_TOP_CHAMFER = inch(1, 32)  # 0.79375 deburr (was 0.5)
CAP_RECESS_DIAMETER = 27.5  # clearance on the purchased cap (vendor fit, exempt)
# 19/32 (1/32): at 5/8 the cap-recess-to-counterbore ligament is 1.76 < 2.0;
# the cap mouth stands 0.79 (1/32) above the floor (was 1.5).
CAP_RECESS_DEPTH = inch(19, 32)  # 15.08125 (was 16.3)
