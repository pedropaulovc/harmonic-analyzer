r"""Pure-data contract for the MHA-DT-VN-59 axial arm-to-hub seam pin.

Cut from a McMaster-Carr 98381A487 alloy-steel dowel pin (5/32 x 1/2,
Ø.1563 +.0001/+.0003, Round x Chamfer ends; dt_crank_hub_geometry).  The
diameter is the pin's as supplied; only the length is made here.
"""

from __future__ import annotations

import _config
from _package_units import drawing_unit
from dt_crank_hub_geometry import AXIAL_PIN_DIA as PIN_DIA
from dt_crank_hub_geometry import AXIAL_PIN_LENGTH as PIN_LEN  # noqa: F401 -- re-exported to the build

UNIT = drawing_unit("parts/dt-vn-crank-hub-pin", _config.parts("dt-vn-crank-hub-pin"))
SKU = "98381A487"

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia", "PinLen"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {"PinDia": 3, "PinLen": 2},
}
# The diameter is the bought pin's, printed as the supplier's fraction
# reference: its tolerance is the catalogue's, not a title-block band.
STOCK_FRACTION_DENOMINATOR = 32
STOCK_FRACTION_DIMENSIONS = {"PinDia": PIN_DIA}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if {name for names in DRAWING_DIMENSIONS.values() for name in names} != set(
    DRAWING_PRECISION_BY_NAME
):
    raise AssertionError("every marked MHA-DT-VN-59 dimension needs authored places")

DRAWING_NOTES = "\n".join(
    (
        "MATCH-DRILL/REAM MHA-DT-06 ARM AND MHA-DT-31 HUB AT SIX O'CLOCK TO",
        "LIGHT DRIVE FIT ON ACTUAL MHA-DT-VN-59 PIN; DRIVE AXIALLY FROM OUTBOARD FACE;",
        "OUTER END FLUSH. PIN SHALL NOT ENTER HUB BORE.",
        f"CUT FROM McMASTER-CARR {SKU} DOWEL PIN; DIAMETER AS SUPPLIED.",
    )
)
