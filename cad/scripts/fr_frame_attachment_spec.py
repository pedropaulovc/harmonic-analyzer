"""Frame cross-screw installation geometry, in millimetres.

Reconstruction approved by the user: stock 90280A837 screws pass through
match-drilled column walls and engage both casting walls. No bonded inserts.
The sockets and recessed purchased caps preserve the finished frame height.
"""

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
BASE_SCREW_Y = COLUMN_BOTTOM_Y + 12.7
BASE_SCREW_SEAT_Z = 133.0
TOP_SCREW_Y = 1017.95
TOP_SCREW_SEAT_Z = 137.6
SCREW_SPOTFACE_DIAMETER = 9.0
# The casting is tapped continuously across the interrupted column socket.
# Tube walls are clearance-drilled separately after matching their positions.
CASTING_FULL_THREAD_DEPTH = 46.0
# 49 MIN: the tap drill keeps two bottoming-tap pitches past the deepest
# printed thread (46.00 + 0.51 .XX band), not just past its nominal.
CASTING_TAP_DRILL_DEPTH = 49.0
TUBE_CROSS_HOLE_DIAMETER = 5.0

CAP_TOP_Y = 1044.8
CAP_MOUTH_Y = CAP_TOP_Y - CAP_HEIGHT
TUBE_TOP_Y = CAP_TOP_Y - CAP_ROOF
TUBE_CUT_LENGTH = TUBE_TOP_Y - COLUMN_BOTTOM_Y
TUBE_TOP_CHAMFER = 0.5
CAP_RECESS_DIAMETER = 27.5
CAP_RECESS_DEPTH = 16.3
