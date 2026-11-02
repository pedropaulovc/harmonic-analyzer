r"""MHA-DT-VN-67 crank-seat-drive-pin: McMaster 98381A434 stock dowel.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Two are pressed into the crankshaft collar's seat face (ch23 p.56:
the removable sprocket's two holes drop over two pins standing out of the
shaft's seat).  The stock recipe, the crankshaft and the drive train read the pin here;
its diameter must be the seat interface's (``_sprocket_seat_geometry``).

Catalogue: 3/32 x 1/4 alloy-steel dowel, Round x Chamfer ends; the size row
and the diameter tolerance are ``diagnostics.diag_mcmaster_dowel``'s.  No
recommended hole size is stated; the hole is the crankshaft's own reamed
press fit (``_sprocket_seat_geometry.DRIVE_PIN_HOLE_BAND``).

Part frame: axis local +Y through the origin; the pressed (chamfered) end
face at y = 0, the rounded lead end at y = LENGTH.
"""

from __future__ import annotations

import _config
from _mcmaster_98381a434 import (
    DIA_BAND_IN,  # noqa: F401 -- re-exported: catalogue diameter tolerance (in)
    DOWEL_SIZE,
    MM_PER_IN,  # noqa: F401 -- re-exported with the inch band
)
from _package_units import drawing_unit
from _sprocket_seat_geometry import DRIVE_PIN_DIA, DRIVE_PIN_PROUD
from _supplier_pin_data import SupplierPinReference

# #290: the registry row's drawing_unit (in) is this sheet's unit; it drops
# the supplier REFs' inch suffix.
UNIT = drawing_unit(
    "parts/dt-vn-crank-seat-drive-pin", _config.parts("dt-vn-crank-seat-drive-pin")
)

SKU = "98381A434"
DIA, LENGTH = DOWEL_SIZE  # 2.38125 x 6.35
# Pressed to the blind hole's floor, the pin stands the interface's proud
# length out of the crank collar's seat face.
PRESS_DEPTH = LENGTH - DRIVE_PIN_PROUD  # 3.95
if abs(DIA - DRIVE_PIN_DIA) > 1e-12:
    raise AssertionError(f"{SKU} is not the seat interface's drive pin")

# McMaster engineering drawing inspected 2026-10-19. Its .0937 nominal
# differs from exact 3/32 stock geometry: print equivalent .0938/.0940
# native reference limits rather than rounding or moving the cylinder.
# The catalogue-derived DIA_BAND_IN and all fit controls remain unchanged.
SUPPLIER_REFERENCE = SupplierPinReference(
    sku=SKU,
    units="in",
    diameter_mm=DIA,
    length_mm=LENGTH,
    diameter_nominal=0.0937,
    diameter_precision=4,
    length_precision=2,
    diameter_band=(0.0001, 0.0003),
    sheet_unit=UNIT,
)
