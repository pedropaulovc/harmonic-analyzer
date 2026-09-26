r"""Pure-data contract for the cylinder-arbor apex set screw (MHA-147, #743).

One #4-40 x 1/4 in hex socket cup-point set screw in each arbor pedestal's
crown apex (user ruling on #743, Q3: "set screw located at apex of straps").
The back pedestal's screw fixes the arbor; the front one is tightened once the
bank's end-play leaf is set (cylinder_bank_layout).

PURCHASED: McMaster-Carr 91375A106, alloy steel cup-tip set screw, black
oxide, Class 3A, Rockwell C45, 0.050 in hex drive (ASME B18.3 / ASTM F912).
The C45 cup bites the spotted steel arbor where an 18-8 (B80) cup would not.
The model is ASME B18.3 nominal geometry, not a replica of the vendor model:
the native comparison against the 91375A106 file is a release requirement
(the 90280A837 / 90280A110 precedent in diag_build_mcmaster).
"""

from __future__ import annotations

import math

from _hole_spec import THREAD_MAJOR_MM
from arbor_pedestal_spec import SET_SCREW_THREAD

MM_PER_IN = 25.4

THREAD = SET_SCREW_THREAD  # #4-40 UNC-2A
MAJOR_DIA = THREAD_MAJOR_MM[THREAD]  # 0.112 in
LENGTH = 0.250 * MM_PER_IN  # nominal length, point to socket face
# ASME B18.3 hex socket set screw, #4 row (nominal/mid values): hex key
# 0.050 in across flats; cup point 0.054-0.061 in; the point's 118-degree
# included cone from the major diameter down to the cup rim.
HEX_AF = 0.050 * MM_PER_IN
SOCKET_DEPTH = 0.045 * MM_PER_IN
CUP_DIA = 0.0575 * MM_PER_IN
POINT_HALF_ANGLE_DEG = 59.0
POINT_LENGTH = (MAJOR_DIA - CUP_DIA) / 2.0 / math.tan(
    math.radians(POINT_HALF_ANGLE_DEG)
)
CUP_DEPTH = 0.30  # the cup's own conical recess at the point
SOCKET_CHAMFER = 0.25  # 45-degree chamfer at the socket face

if POINT_LENGTH + SOCKET_CHAMFER >= LENGTH:
    raise AssertionError("set-screw point and chamfer overrun its length")
if HEX_AF / math.sqrt(3.0) >= MAJOR_DIA / 2.0 - SOCKET_CHAMFER:
    raise AssertionError("hex socket corners break out of the socket face")
