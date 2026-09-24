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
    HUB_BARREL_LENGTH,
    HUB_BORE_BAND,
    HUB_BORE_DIA,
    HUB_LENGTH,
    HUB_SEAT_DIA,
    HUB_SEAT_LENGTH,
    SERVICE_PIN_FROM_SHOULDER,
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
    "HubProfile": {"SeatLength", "BarrelLength", "SeatDia", "BarrelDia"},
    "BoreProfile": {"BoreDia"},
    "ServicePinStationReference": {"ServicePinFromShoulder"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "HubProfile": {
        "SeatLength": 1,
        "BarrelLength": 1,
        "SeatDia": 1,
        "BarrelDia": 1,
    },
    "BoreProfile": {"BoreDia": 3},
    # Two places: the .XX band is what keeps both MHA-024 ream ligaments at
    # 2.1 mm in the 12-mm barrel (crank_hub_geometry, policy rule 12).
    "ServicePinStationReference": {"ServicePinFromShoulder": 2},
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

# The arm bore is made first and carries the band; this seat is turned to fit
# it, so its nominal prints as a reference under the match-fit callout
# (crank_hub_notes owns the callout prose).
REFERENCE_DIMENSIONS = frozenset({"SeatDia"})
# No general notes (policy rule 6): the seat fit, the seam and the cross-hole
# each carry their requirement on their own callout, and the U29 hub leaves a
# 2-mm seam web at the printed bands, so no matched wall check.
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
# The one sheet-derived dimension: the parenthesised overall, the sum of the
# printed seat and barrel lengths.  Its places are still specification.
DRAWING_REFERENCE_PRECISION: dict[str, int] = {"overall length reference": 1}
