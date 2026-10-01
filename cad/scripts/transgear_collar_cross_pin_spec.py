r"""MHA-154 transgear-collar-cross-pin: McMaster 98296A026 stock spring pin.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  One 1/16 x 9/16 slotted spring pin to ASME B18.8.2 is sprung
diametrally through the MHA-078 knob shaft's core, in a hole drilled at
assembly along the MHA-177 drive collar's rear slot, and lies in that slot,
so collar and shaft turn as one (contract §1.3, fit-up E).  The collar has
no cross hole; the pin drives through the slot's walls.  The sprung pin
fills the hole; nothing is modelled between them.

Catalogue: McMaster 98296A026, read live on September 30, 2026 (dt-logs
transgear-evidence mcmaster-skus.md): 1050-1095 spring steel, unplated,
1/16 in diameter, 9/16 in long, 0.012 in wall, chamfered ends, for a
0.062-0.065 in hole; no diameter tolerance stated.  It is MHA-145's 1/2 in
98296A027 in its 9/16 length; both are rows of
``diagnostics/diag_mcmaster_spring_pin.py``, whose table this module reads.

Part frame: axis along local X through the origin, centred on it, so the
ends sit at x = -PIN_LEN / 2 and +PIN_LEN / 2.  The Right Plane is the
mid-length plane; the Front and Top Planes contain the axis, which the part
publishes as ``ScrewAxis`` (Front Plane x Top Plane).  MHA-145's layout.
"""

from __future__ import annotations

from diagnostics.diag_mcmaster_spring_pin import SPRING_PIN_SIZES
from diagnostics.diag_mcmaster_spring_pin import WALL_T as _CATALOGUE_WALL

INCH = 25.4
SKU = "98296A026"
PIN_STANDARD = "ASME B18.8.2"
PIN_DIA, PIN_LEN = SPRING_PIN_SIZES[SKU]  # 1/16 x 9/16 in
WALL_T = _CATALOGUE_WALL  # 0.012 in
# The contract's length band (§1.3): +/-0.015 in.
PIN_LEN_BAND = 0.015 * INCH
PIN_LEN_MIN = PIN_LEN - PIN_LEN_BAND
PIN_LEN_MAX = PIN_LEN + PIN_LEN_BAND

# B18.8.2's recommended hole for a 1/16 pin, as the catalogue states it.
HOLE_WINDOW = (0.062 * INCH, 0.065 * INCH)
# The hole drilled at assembly through the core only: a functional band
# (R9-11) kept inside the window the pin is sold to grip.
HOLE_DIA = 1.6
HOLE_BAND = (0.05, 0.0)  # (upper, lower) deviations
HOLE_MAX = HOLE_DIA + HOLE_BAND[0]
if not (HOLE_WINDOW[0] <= HOLE_DIA and HOLE_MAX <= HOLE_WINDOW[1]):
    raise AssertionError("the cross hole's band leaves B18.8.2's recommended hole")
if not HOLE_WINDOW[0] <= PIN_DIA <= HOLE_WINDOW[1]:
    raise AssertionError("the pin's nominal diameter leaves its own hole window")
