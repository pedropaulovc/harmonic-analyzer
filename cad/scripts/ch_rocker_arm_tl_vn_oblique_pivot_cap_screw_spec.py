"""VN-73 NAS1352N5H12; axis +Z, head bearing face on Front Plane z=0.

ScrewAxis is Right/Top intersection. Socket and six wire openings are real.
Catalogue-native threaded representation, not vendor-CAD replication.
"""
import math

from ch_rocker_arm_tl_oblique_retention_hardware_spec import (
    SCREW_SKU as SKU, SCREW_SOURCE_URL as SOURCE_URL,
    SCREW_DIMS as DIMS, SCREW_LENGTH_MIN as LENGTH_MIN,
    SCREW_WIRE_HEIGHT, SCREW_WIRE_HOLE_DIA, SCREW_WIRE_HOLE_ANGLES,
)

QUANTITY = 8
CALLOUT = "5/16-18 X 3/4 PREDRILLED SHCS NAS1352N5H12"
AXIS_NAME = "ScrewAxis"
SEAT_PLANE = "Front Plane"


def drilled_head_segments():
    """Three straight diametral drill axes in the stock builder's +Y frame.

    The wrapper's +90-degree X rotation maps these to the six NAS radial
    openings in the installed +Z head. Each drill crosses both head walls
    and the real socket, not a cosmetic indication.
    """
    segments = []
    for angle in SCREW_WIRE_HOLE_ANGLES[:3]:
        theta = math.radians(angle)
        x = DIMS.head_dia * math.cos(theta)
        z = -DIMS.head_dia * math.sin(theta)
        a = (-x, SCREW_WIRE_HEIGHT, -z)
        b = (x, SCREW_WIRE_HEIGHT, z)
        segments.append((a, tuple((2*u+v)/3 for u,v in zip(a,b)),
                         tuple((u+2*v)/3 for u,v in zip(a,b)), b))
    return tuple(segments)
