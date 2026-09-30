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
    RELIEF_DIA,
    RELIEF_LENGTH,
    RELIEF_LENGTH_TOL,
    RELIEF_STATION,
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
# The printed chain -- seat from the front face, the overall to the rear
# face, the relief back from it -- leaves the barrel between the arm shoulder
# and the relief shoulder unprinted (its length is the remainder).
if abs(HUB_SEAT_LENGTH + HUB_BARREL_LENGTH - RELIEF_STATION) > 1e-9:
    raise AssertionError("barrel does not end at the relief shoulder")
if abs(RELIEF_STATION + RELIEF_LENGTH - HUB_LENGTH) > 1e-9:
    raise AssertionError("relief does not end at the hub rear face")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HubProfile": {
        "SeatLength",
        "HubLength",
        "ReliefLength",
        "SeatDia",
        "BarrelDia",
        "ReliefDia",
    },
    "BoreProfile": {"BoreDia"},
    "ServicePinStationReference": {"ServicePinFromShoulder"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "HubProfile": {
        "SeatLength": 1,
        # Two places: front face to rear face with HUB_LENGTH_TOL.  The front
        # face is set flush with the crankshaft's dome root before the MHA-024
        # ream, so this length places the rear face against the removable.
        "HubLength": 2,
        # Two places: printed from the rear face with RELIEF_LENGTH_TOL, the
        # length that keeps the #25 plates clear of the barrel's rear shoulder.
        "ReliefLength": 2,
        "SeatDia": 1,
        "BarrelDia": 1,
        # A clearance diameter: the title block's .X (RELIEF_DIA_MAX is what
        # the drive train's chain-plate air reads).
        "ReliefDia": 1,
    },
    "BoreProfile": {"BoreDia": 3},
    # Two places: the .XX band is what keeps the MHA-024 ream's ligament to
    # the arm shoulder at 2.1 mm (crank_hub_geometry, policy rule 12).
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

# The arm bore is made first to its reference nominal; this seat is turned to
# suit it for a light press, so its nominal prints as a reference under the
# press-fit callout
# (crank_hub_notes owns the callout prose).
REFERENCE_DIMENSIONS = frozenset({"SeatDia"})
# No general notes (policy rule 6): the seat fit, the seam and the cross-hole
# each carry their requirement on their own callout, and the U29 hub leaves a
# 2-mm seam web at the printed bands, so no matched wall check.
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
