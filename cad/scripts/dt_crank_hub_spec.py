r"""Pure-data dimensional and drawing contract for through hub MHA-DT-31."""

from __future__ import annotations

from _hole_spec import HoleSpec
from _surface_finish import SurfaceFinishControl
from dt_crank_hub_geometry import (
    ARM_THICKNESS,
    AXIAL_PIN_DIA,
    AXIAL_PIN_RADIUS_FROM_AXIS,
    GENERAL_2PL_TOL_MM,
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

# The MHA-DT-09 taper ream's acceptance (rule 4, matched fit): the driven
# pin's big end stands at least PIN_PROUD out of the barrel, so its keeper
# ring's hole clears it.  A single MIN limit (swTolMIN prints the nominal, so
# the model value is the limit); only the short side is functional, and the
# native tolerance records the title block's .XX above it.
PIN_PROUD_MIN_BAND = (GENERAL_2PL_TOL_MM, 0.0)

SERVICE_PIN_HOLE_SPEC = HoleSpec("drilled_number", "#14")
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

if HUB_SEAT_LENGTH != ARM_THICKNESS:
    raise AssertionError("through hub cannot finish flush with both arm faces")
if AXIAL_PIN_RADIUS_FROM_AXIS != HUB_SEAT_DIA / 2.0:
    raise AssertionError("MHA-DT-VN-59 axis is not on the arm/hub seam")
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
    "ServicePinStationReference": {"ServicePinStation"},
    "PinProudReference": {"PinProud"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "HubProfile": {
        # The seat end is set flush with the arm's front face (the seat
        # callout's acceptance), so its length matches the 5/16 stock.
        "SeatLength": 2,
        # Three places, .990 +.004/-.010 (HUB_LENGTH_BAND): an inch nominal
        # carries its tolerance's places.  The front face is set flush with
        # the crankshaft's dome root before the MHA-DT-09 ream, so this
        # length places the rear face against the removable.
        "HubLength": 3,
        # Two places: printed from the rear face, its short side what keeps
        # the #25 plates clear of the barrel's rear shoulder.
        "ReliefLength": 2,
        "SeatDia": 2,
        # The arm's shoulder at the title block's .XX: HUB_BARREL_DIA_MIN, what
        # the shoulder land over the largest matched seat reads.
        "BarrelDia": 2,
        # A clearance diameter at the title block's .XX: RELIEF_DIA_MAX, what
        # the drive train's chain-plate air reads.
        "ReliefDia": 2,
    },
    "BoreProfile": {"BoreDia": 4},  # 9.5504, .376 in
    # Two places from the faced outboard end: with the seat length's .XX, the
    # band is what keeps the MHA-DT-09 ream's ligament to the arm shoulder
    # over the rule-17 wall (dt_crank_hub_geometry, drawing-guidelines.md rule 17 (walls and webs)).
    "ServicePinStationReference": {"ServicePinStation": 2},
    "PinProudReference": {"PinProud": 2},
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
# (dt_crank_hub_notes owns the callout prose).
REFERENCE_DIMENSIONS = frozenset({"SeatDia"})
# No general notes (drawing-guidelines.md rule 7 (notes: few, flagged, never a method)): the seat fit, the seam and the cross-hole
# each carry their requirement on their own callout, and the U29 hub leaves a
# 2-mm seam web at the printed bands, so no matched wall check.
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
