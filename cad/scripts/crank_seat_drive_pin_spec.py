r"""MHA-173 crank-seat-drive-pin: McMaster 98381A434 stock dowel.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Two are pressed into the crankshaft collar's seat face (ch23 p.56:
the removable sprocket's two holes drop over two pins standing out of the
shaft's seat).  The stock recipe, the crankshaft and the drive train read the pin here;
its diameter must be the seat interface's (``transgear_removable_spec``).

Catalogue: 3/32 x 1/4 alloy-steel dowel, Round x Chamfer ends; the size row
and the diameter tolerance are ``diagnostics.diag_mcmaster_dowel``'s.  No
recommended hole size is stated; the hole is the crankshaft's own reamed
press fit (``crankshaft_spec.DRIVE_PIN_HOLE_BAND``).

Part frame: axis local +Y through the origin; the pressed (chamfered) end
face at y = 0, the rounded lead end at y = LENGTH.
"""

from __future__ import annotations

from diagnostics.diag_mcmaster_dowel import (
    DIA_BAND_IN,  # noqa: F401 -- re-exported: catalogue diameter tolerance (in)
    DOWEL_SIZES,
    MM_PER_IN,  # noqa: F401 -- re-exported with the inch band
)
from transgear_removable_spec import DRIVE_PIN_DIA, DRIVE_PIN_PROUD

SKU = "98381A434"
DIA, LENGTH = DOWEL_SIZES[SKU]  # 2.38125 x 6.35
# Pressed to the blind hole's floor, the pin stands the interface's proud
# length out of the crank collar's seat face.
PRESS_DEPTH = LENGTH - DRIVE_PIN_PROUD  # 3.95
if abs(DIA - DRIVE_PIN_DIA) > 1e-12:
    raise AssertionError(f"{SKU} is not the seat interface's drive pin")
