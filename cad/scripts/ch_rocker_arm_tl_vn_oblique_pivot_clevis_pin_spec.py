"""VN-74 Huyett clevis: +X from head bearing face x=0, head toward -X.

ScrewAxis is Front/Top intersection; Right Plane is head bearing plane.
CotterHoleAxis runs +Z at (CLEVIS_HOLE_FROM_HEAD,0,0). This longer SKU
puts both retainers outside the removable washer; the 1-inch pin is rejected.
"""
from ch_rocker_arm_tl_oblique_retention_hardware_spec import (
    CLEVIS_SKU as SKU, CLEVIS_SOURCE_URL as SOURCE_URL,
    CLEVIS_DIA, CLEVIS_DIA_MIN, CLEVIS_DIA_MAX,
    CLEVIS_LENGTH, CLEVIS_HEAD_DIA, CLEVIS_HEAD_HEIGHT,
    CLEVIS_HOLE_DIA, CLEVIS_HOLE_FROM_HEAD,
)

QUANTITY = 2
CALLOUT = "3/16 X 1-1/4 HEADED CLEVIS PIN"
AXIS_NAME = "ScrewAxis"
SEAT_PLANE = "Right Plane"
COTTER_AXIS_NAME = "CotterHoleAxis"
