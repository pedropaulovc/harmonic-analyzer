r"""Pure-data dimensional contract shared by the pinion arbor and drawing.

The Ø2 retention hole is a reconstruction choice from the upper tee-handle
photos, not a measured historical dimension.  It is match-drilled through the
MHA-058 socket and this arbor at the socket's mid-length.
"""

from __future__ import annotations

from _fit_limits import SHAFT_H
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from _gtol_spec import CylinderFace
from pinion_handle_spec import (
    RETENTION_PIN_DIA,
    RETENTION_PIN_STATION_FROM_FLOOR,
)


SHAFT_DIA = 8.0
SHAFT_LEN = 226.25
SHAFT_DIA_BAND = SHAFT_H
CAP_SAG = 1.2
CAP_R = (SHAFT_DIA / 2.0) ** 2 / (2.0 * CAP_SAG) + CAP_SAG / 2.0  # 7.27
RETENTION_HOLE_DIA = RETENTION_PIN_DIA
RETENTION_PIN_STATION = RETENTION_PIN_STATION_FROM_FLOOR

# The arbor is a running journal through the drum and strap bores, so the size
# band and one bearing-surface roughness remain under simplicity-policy rules
# 2 and 5.  Shafts are not on the geometric-control allowlist.
SURFACE_FINISHES = (
    SurfaceFinishControl("bearing", MACHINED_UM, CylinderFace(SHAFT_DIA)),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShaftProfile": {"ShaftDia"},
    "Shaft": {"Depth"},
    "BackCapProfile": {"CapSagDim"},
    "RetentionHoleProfile": {"RetentionHoleDia", "RetentionPinStation"},
}

DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ShaftProfile": {"ShaftDia": 2},
    "Shaft": {"Depth": 2},
    "BackCapProfile": {"CapSagDim": 1},
    "RetentionHoleProfile": {
        "RetentionHoleDia": 1,
        "RetentionPinStation": 1,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked arbor dimension needs authored places")

RETENTION_HOLE_CALLOUT = (
    "MATCH-DRILL WITH MHA-058\n"
    "REAM TO ACTUAL MHA-136\n"
    "LIGHT DRIVE FIT"
)
DRAWING_NOTES = "MHA-136 ENDS FLUSH WITH MHA-058 SOCKET O.D. AFTER ASSEMBLY."
