r"""Pure-data contract for the MHA-DT-12-TL-VN-51 cam fixture clock pin.

Shop fixture hardware (cad/docs/subsystem-identities.md). Cut from a
McMaster-Carr 23065A503 class Z minus gauge pin ordered at .0375
(``_mcmaster_23065a503``, read live 2026-11-12: -.0001/0, 2 in long,
Rockwell C60, $7.50 each); the diameter is the pin's as supplied, only the
length is made here (the dt-vn-crank-hub-pin pattern). Pressed to the floor
of the MHA-DT-12-TL-01 body's .0365 ream, it stands in each cylinder gear's
notched tooth space; the press, the stand-out and the phase it sets are the
fixture's (``dt_cylinder_gear_tl_cam_fixture_spec``).

Part frame: axis local +Y through the origin; the pressed end face (on the
ream's floor) at y = 0, the standing end at y = PIN_LEN.
"""

from __future__ import annotations

import _config
from _mcmaster_23065a503 import CUT_LENGTH as PIN_LEN
from _mcmaster_23065a503 import PART_NO
from _mcmaster_23065a503 import SIZE as PIN_DIA
from _package_units import drawing_unit

PART_NAME = "dt-cylinder-gear-tl-vn-cam-clock-pin"
UNIT = drawing_unit(
    "parts/dt-cylinder-gear-tl-vn-cam-clock-pin",
    _config.parts("dt-cylinder-gear-tl-vn-cam-clock-pin"),
)
SKU = PART_NO
FIXTURE_NUMBER = str(_config.parts("dt-cylinder-gear-tl-cam-fixture")["number"])

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia", "PinLen"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {"PinDia": 4, "PinLen": 2},
}
# The diameter is the bought gauge's, printed as the supplier's reference:
# its tolerance is the catalogue's, not a title-block band.
STOCK_REFERENCE_DIMENSIONS = {"PinDia": PIN_DIA}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if {name for names in DRAWING_DIMENSIONS.values() for name in names} != set(
    DRAWING_PRECISION_BY_NAME
):
    raise AssertionError("every marked MHA-DT-12-TL-VN-51 dimension needs places")
if abs(PIN_LEN / 25.4 - round(PIN_LEN / 25.4, 2)) > 1e-9:
    raise AssertionError("the clock pin's cut length is off its .XX grid")

# The fit and its mate (by drawing number, rule 4) under the diameter.
PIN_DIA_CALLOUT = f"PRESS FIT IN {FIXTURE_NUMBER}"
DRAWING_NOTES = f"CUT FROM McMASTER-CARR {SKU} GAUGE PIN; DIAMETER AS SUPPLIED."
