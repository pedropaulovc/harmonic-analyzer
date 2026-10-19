r"""MHA-VN-029: purchased McMaster 91585A377 ISO 2338-m6 seam pin.

The live engineering PDF prints 4.000 mm +0.012/+0.004 and 4 mm overall.
The vendor STEP read headlessly on 2026-10-19 supplies the two 15-degree
end leads: 0.630 mm axially, not a project edge-break prescription.
Source: https://www.mcmaster.com/91585A377/
STEP SHA-256: 17baf944ce1b2cd76389991fc04f604aa3c5a6ac30d507787bdc6aceb80b5f20.
"""

from __future__ import annotations

import math

import _config
from _supplier_pin_data import SupplierPinReference

from dt_crank_hub_geometry import AXIAL_PIN_DIA as PIN_DIA
from dt_crank_hub_geometry import AXIAL_PIN_LENGTH as PIN_LEN

SKU = "91585A377"
PIN_DIA_BAND = (0.004, 0.012)
PIN_CHAMFER_AXIAL = 0.630
PIN_CHAMFER_ANGLE_DEG = 15.0
PIN_END_RADIUS = PIN_DIA / 2.0 - PIN_CHAMFER_AXIAL * math.tan(
    math.radians(PIN_CHAMFER_ANGLE_DEG)
)
PIN_FULL_DIA_LENGTH = PIN_LEN - 2.0 * PIN_CHAMFER_AXIAL
SUPPLIER_REFERENCE = SupplierPinReference(
    sku=SKU,
    units="mm",
    diameter_mm=4.0,
    length_mm=4.0,
    diameter_nominal=4.000,
    diameter_precision=3,
    length_precision=0,
    diameter_band=PIN_DIA_BAND,
)
if (PIN_DIA, PIN_LEN) != (
    SUPPLIER_REFERENCE.diameter_mm,
    SUPPLIER_REFERENCE.length_mm,
):
    raise AssertionError("91585A377 stock must retain the shared 4 mm seam interface")


DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia", "PinLen"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {"PinDia": 3, "PinLen": 0},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if {name for names in DRAWING_DIMENSIONS.values() for name in names} != set(
    DRAWING_PRECISION_BY_NAME
):
    raise AssertionError("every marked MHA-VN-029 dimension needs authored places")

# Installation is unchanged; neither size is a fabrication control.
DRAWING_NOTES = str(_config.parts("vn-crank-hub-pin")["installation_notes"])
