"""Frame cross-screw installation geometry, in millimetres.

Reconstruction approved by the user: stock 90280A837 screws pass through
match-drilled column walls and engage both casting walls. No bonded inserts.
The lower sockets preserve the existing exposed column length and frame height.
"""

from harmonic_base_spec import STACK_HEIGHT

COLUMN_SOCKET_DEPTH = 25.4
COLUMN_BOTTOM_Y = STACK_HEIGHT - COLUMN_SOCKET_DEPTH
COLUMN_SOCKET_DIAMETER = 25.5
BASE_SCREW_Y = STACK_HEIGHT - COLUMN_SOCKET_DEPTH / 2.0
BASE_SCREW_SEAT_Z = 133.0
TOP_SCREW_Y = 1017.95
TOP_SCREW_SEAT_Z = 137.6
SCREW_SPOTFACE_DIAMETER = 9.0
# The casting is tapped continuously across the interrupted column socket.
# Tube walls are clearance-drilled separately after matching their positions.
CASTING_FULL_THREAD_DEPTH = 46.0
CASTING_TAP_DRILL_DEPTH = 48.0
TUBE_CROSS_HOLE_DIAMETER = 5.0
