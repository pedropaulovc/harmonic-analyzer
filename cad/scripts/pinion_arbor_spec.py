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
from pinion_handle_geometry import ROD_DIA

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
BACK_RIM_FROM_HEAD_REAR = SHAFT_LEN - HEAD_REAR_Z
CROSS_HOLE_FROM_HEAD_REAR = HEAD_REAR_Z - HEAD_CENTER_Z

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
    "Head": {"HeadLen"},
    "Neck": {"NeckLen"},
    "ShaftProfile": {"ShaftDia"},
    "FrontCapProfile": {"HeadCapR", "HeadCapSagDim"},
    "BackCapProfile": {"BackCapSagDim"},
    "CrossHoleProfile": {"CrossHoleDia"},
    "BackRimReference": {"BackRimFromHeadRear"},
    "CrossHoleReference": {"CrossHoleFromHeadRear"},
    "OverallReference": {"OverallLen"},
}

DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "Head": {"HeadLen": 1},
    "Neck": {"NeckLen": 1},
    "HeadProfile": {"HeadDia": 1},
    "NeckProfile": {"NeckDia": 1},
    "ShaftProfile": {"ShaftDia": 2},
    "FrontCapProfile": {"HeadCapR": 1, "HeadCapSagDim": 1},
    "BackCapProfile": {"BackCapSagDim": 1},
    "CrossHoleProfile": {"CrossHoleDia": 1},
    "BackRimReference": {"BackRimFromHeadRear": 1},
    "CrossHoleReference": {"CrossHoleFromHeadRear": 1},
    "OverallReference": {"OverallLen": 1},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
_DRAWING_CREATED_DIMENSIONS = {"HeadDia", "NeckDia"}
if set(DRAWING_PRECISION_BY_NAME) != (
    set().union(*DRAWING_DIMENSIONS.values()) | _DRAWING_CREATED_DIMENSIONS
):
    raise AssertionError(
        "every imported or drawing-created integral-arbor dimension needs authored places"
    )

CROSS_HOLE_CALLOUT = (
    "MATCH-REAM THRU\n"
    "TO MHA-058 GRIP ROD\n"
    "LIGHT ARBOR-PRESS FIT"
)
DRAWING_NOTES = "\n".join(
    (
        "DIA 8 SHAFT RUNS IN MHA-056 REAMED BORE; BOND INTO MHA-002 WITH LOCTITE 638.",
        "INTERNAL SHOULDERS SHARP.",
        "INSTALLED MHA-058 ROD SHALL NOT TURN OR SLIDE BY HAND.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
