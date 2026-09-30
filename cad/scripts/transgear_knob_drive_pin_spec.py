r"""MHA-155 transgear-knob-drive-pin: McMaster 98381A433 stock dowel.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Two are pressed into the knob shaft's Ø17.5 seat collar (MHA-078)
and stand ``transgear_removable_spec.DRIVE_PIN_PROUD`` out of its seat face,
where the removable sprocket's two holes drop over them.  The collar is only
3.6 long, so the knob takes the 3/16 length of the crank's 3/32 dowel.

Catalogue: 3/32 x 3/16 alloy-steel dowel, Round x Chamfer ends; the size row
and the diameter tolerance are ``diagnostics.diag_mcmaster_dowel``'s.

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

SKU = "98381A433"
DIA, LENGTH = DOWEL_SIZES[SKU]  # 2.38125 x 4.7625
# Pressed to the blind hole's floor, the pin stands the interface's proud
# length out of the knob collar's seat face.
PRESS_DEPTH = LENGTH - DRIVE_PIN_PROUD  # 2.3625
if abs(DIA - DRIVE_PIN_DIA) > 1e-12:
    raise AssertionError(f"{SKU} is not the seat interface's drive pin")
