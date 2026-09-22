r"""Pure-data dimensional and drawing contract for through hub MHA-137."""

from __future__ import annotations

from _hole_spec import HoleSpec
from _surface_finish import SurfaceFinishControl
from crank_hub_geometry import (
    ARM_THICKNESS,
    AXIAL_PIN_DIA,
    AXIAL_PIN_LENGTH,
    AXIAL_PIN_RADIUS_FROM_AXIS,
    HUB_BARREL_DIA,
    HUB_BORE_BAND,
    HUB_BORE_DIA,
    HUB_LENGTH,
    HUB_SEAT_DIA,
    HUB_SEAT_LENGTH,
    SERVICE_PIN_STATION,
    SHAFT_CLEARANCE_MAX,
    SHAFT_CLEARANCE_MIN,
)


SERVICE_PIN_HOLE_SPEC = HoleSpec("drilled_number", "#14")
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

if HUB_SEAT_LENGTH != ARM_THICKNESS:
    raise AssertionError("through hub cannot finish flush with both arm faces")
if AXIAL_PIN_LENGTH != ARM_THICKNESS / 2.0:
    raise AssertionError("MHA-138 length is not half the arm thickness")
if AXIAL_PIN_RADIUS_FROM_AXIS != HUB_SEAT_DIA / 2.0:
    raise AssertionError("MHA-138 axis is not on the arm/hub seam")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HubProfile": {"HubLength", "SeatLength", "SeatDia", "BarrelDia"},
    "BoreProfile": {"BoreDia"},
    "ServicePinStationReference": {"ServicePinStation"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "HubProfile": {
        "HubLength": 1,
        "SeatLength": 1,
        "SeatDia": 1,
        "BarrelDia": 1,
    },
    "BoreProfile": {"BoreDia": 3},
    "ServicePinStationReference": {"ServicePinStation": 1},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if {name for names in DRAWING_DIMENSIONS.values() for name in names} != set(
    DRAWING_PRECISION_BY_NAME
):
    raise AssertionError("every marked crank-hub dimension needs authored places")

BORE_CALLOUT = (
    "REAM THRU\n"
    f"{SHAFT_CLEARANCE_MIN:.3f}-{SHAFT_CLEARANCE_MAX:.3f} DIAMETRAL CLEARANCE "
    "ON MHA-026"
)
SEAT_CALLOUT = (
    "MATCH-FIT TO ASSIGNED MHA-020 BORE\n"
    "LIGHT ARBOR-PRESS TO SHOULDER; NO TURN OR SLIDE BY HAND"
)
DRAWING_NOTES = "\n".join(
    (
        "KEEP MHA-020 ARM AND MHA-137 HUB AS A MATCHED ASSEMBLY.",
        "WITH SHOULDER SEATED, FINISH OUTBOARD HUB AND ARM FACES FLUSH.",
        "AT SIX O'CLOCK MATCH-DRILL/REAM AXIAL SEAM GROOVE TO ACTUAL MHA-138.",
        "LIGHT DRIVE FIT; DRIVE FROM OUTBOARD; PIN OUTER END FLUSH.",
        "VERIFY 0.50 MIN HUB WALL FROM FINISHED MHA-138 SEAM TO SHAFT BORE "
        "AFTER EDGE BREAK.",
        "MATCH-REAM #14 CROSS-HOLE WITH MHA-026 FOR MHA-024 TAPER PIN.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
