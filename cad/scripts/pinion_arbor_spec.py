r"""Pure-data dimensional contract for the integral MHA-102 pinion arbor.

The turned head, neck, and long shaft are deliberately one piece.  This is an
approved photo-derived reconstruction choice, not proof of the historical
joint detail.  The exact released external envelope is preserved while the
former socket and unsupported radial retention pin are removed.
"""

from __future__ import annotations

from _fit_limits import SHAFT_H
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from pinion_handle_spec import ROD_DIA

SHAFT_DIA = 8.0
SHAFT_LEN = 226.25  # unchanged origin-to-back-crown-root station
SHAFT_DIA_BAND = SHAFT_H
BACK_CAP_SAG = 1.2
BACK_CAP_R = (SHAFT_DIA / 2.0) ** 2 / (2.0 * BACK_CAP_SAG) + BACK_CAP_SAG / 2.0

# Preserved former handle-body envelope, now turned integrally with the arbor.
HEAD_DIA = 15.0
HEAD_LEN = 9.0
HEAD_CAP_SAG = 3.0
HEAD_CAP_R = ((HEAD_DIA / 2.0) ** 2 + HEAD_CAP_SAG**2) / (2.0 * HEAD_CAP_SAG)
HEAD_REAR_Z = -2.0
HEAD_FRONT_Z = HEAD_REAR_Z - HEAD_LEN
HEAD_CENTER_Z = HEAD_FRONT_Z + HEAD_LEN / 2.0
NECK_DIA = 10.5
NECK_END_Z = 10.0
NECK_LEN = NECK_END_Z - HEAD_REAR_Z
EXPOSED_SHAFT_LEN = SHAFT_LEN - NECK_END_Z
CROSS_HOLE_DIA = 6.005
OVERALL_LEN = SHAFT_LEN + BACK_CAP_SAG - (HEAD_FRONT_Z - HEAD_CAP_SAG)

if HEAD_CENTER_Z != -6.5:
    raise AssertionError("integral head center must preserve the released world station")
if abs(ROD_DIA - CROSS_HOLE_DIA - 0.0125) > 1e-12:
    raise AssertionError("crossrod/head nominal interference changed")
if min(HEAD_LEN, NECK_LEN, EXPOSED_SHAFT_LEN) <= 0.0:
    raise AssertionError("integral arbor axial spans must be positive")

SURFACE_FINISHES = (
    SurfaceFinishControl("bearing", MACHINED_UM, CylinderFace(SHAFT_DIA)),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDia"},
    "Head": {"HeadLen"},
    "NeckProfile": {"NeckDia"},
    "Neck": {"NeckLen"},
    "ShaftProfile": {"ShaftDia"},
    "Shaft": {"ExposedShaftLen"},
    "FrontCapProfile": {"HeadCapR"},
    "BackCapProfile": {"BackCapSagDim"},
    "CrossHoleProfile": {"CrossHoleDia"},
}

DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "HeadProfile": {"HeadDia": 1},
    "Head": {"HeadLen": 1},
    "NeckProfile": {"NeckDia": 1},
    "Neck": {"NeckLen": 1},
    "ShaftProfile": {"ShaftDia": 2},
    "Shaft": {"ExposedShaftLen": 1},
    "FrontCapProfile": {"HeadCapR": 1},
    "BackCapProfile": {"BackCapSagDim": 1},
    "CrossHoleProfile": {"CrossHoleDia": 1},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked integral-arbor dimension needs authored places")

CROSS_HOLE_CALLOUT = (
    "MATCH-REAM THRU TO ACTUAL GRIP ROD MHA-058\n"
    "ON HEAD MIDPLANE\n"
    "LIGHT ARBOR-PRESS FIT"
)
DRAWING_NOTES = "\n".join(
    (
        "TURN HEAD, NECK, AND ARBOR FROM ONE STEEL BLANK.",
        "MATCH-REAM HEAD CROSS HOLE TO ACTUAL MHA-058 ROD.",
        "INSTALLED ROD SHALL NOT TURN OR SLIDE BY HAND.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
