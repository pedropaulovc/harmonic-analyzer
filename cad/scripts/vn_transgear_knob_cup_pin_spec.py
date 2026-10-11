r"""MHA-VN-048 transgear-knob-cup-pin: McMaster 98296A031 stock spring pin.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  One 1/16 x 5/8 slotted spring pin to ASME B18.8.2 is pressed
diametrally through the MHA-PD-016 knob cup and the rear end of the MHA-PD-008
knob shaft's journal, in a hole match-drilled through both at assembly with
the cup set on a feeler at the plate's rear boss (R9-70, K-1).  The pin locks
the cup to the shaft in shear: the cup is the rear stop of the knob's end
float and carries no thread.  The sprung pin fills the hole; nothing is
modelled between them.

Catalogue: McMaster 98296A031, read live on October 2, 2026 (dt-logs
transgear-evidence mcmaster-skus.md): 1050-1095 spring steel, unplated,
1/16 in diameter, 5/8 in long, 0.012 in wall, chamfered ends, for a
0.062-0.065 in hole; no diameter tolerance stated.  It is MHA-VN-037's
98296A026 in its 5/8 length; both are rows of
``diagnostics/diag_mcmaster_spring_pin.py``, whose table this module reads.

Part frame: axis along local X through the origin, centred on it, so the
ends sit at x = -PIN_LEN / 2 and +PIN_LEN / 2.  The Right Plane is the
mid-length plane; the Front and Top Planes contain the axis, which the part
publishes as ``ScrewAxis`` (Front Plane x Top Plane).  MHA-VN-037's layout.
"""

from __future__ import annotations

import vn_transgear_collar_cross_pin_spec as _cross_pin
from _mcmaster_98296a031 import SPRING_PIN_SIZE
from _mcmaster_98296a031 import WALL_T as _CATALOGUE_WALL

INCH = 25.4
SKU = "98296A031"
PIN_STANDARD = "ASME B18.8.2"
PIN_DIA, PIN_LEN = SPRING_PIN_SIZE  # 1/16 x 5/8 in
WALL_T = _CATALOGUE_WALL  # 0.012 in
# MHA-VN-037's length band (contract §1.3): +/-0.015 in.
PIN_LEN_BAND = _cross_pin.PIN_LEN_BAND
PIN_LEN_MIN = PIN_LEN - PIN_LEN_BAND
PIN_LEN_MAX = PIN_LEN + PIN_LEN_BAND

# The hole match-drilled through cup and journal at assembly: MHA-VN-037's
# functional band (R9-11), inside the window B18.8.2 sells the 1/16 pin to
# grip, and under its free diameter so the pin is sprung in it.
HOLE_WINDOW = _cross_pin.HOLE_WINDOW
HOLE_DIA = _cross_pin.HOLE_DIA  # 1.6
HOLE_BAND = _cross_pin.HOLE_BAND  # (+0.05, 0)
HOLE_MAX = HOLE_DIA + HOLE_BAND[0]
# The match-drilled hole as the A06 knob-stack step prints it.
HOLE_TEXT = f"\u00d8{HOLE_DIA:.1f} +{HOLE_BAND[0]:.2f}/0"
FREE_DIA_MIN = _cross_pin.FREE_DIA_MIN
if not (HOLE_WINDOW[0] <= HOLE_DIA and HOLE_MAX <= HOLE_WINDOW[1]):
    raise AssertionError("the cup pin hole's band leaves B18.8.2's recommended hole")
if not HOLE_WINDOW[0] <= PIN_DIA <= HOLE_WINDOW[1]:
    raise AssertionError("the pin's nominal diameter leaves its own hole window")
if not HOLE_MAX < FREE_DIA_MIN:
    raise AssertionError("the cup pin hole no longer compresses the spring pin")
