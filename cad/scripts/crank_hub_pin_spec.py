r"""Pure-data contract for the MHA-138 axial arm-to-hub seam pin."""

from __future__ import annotations

from crank_hub_geometry import AXIAL_PIN_DIA as PIN_DIA
from crank_hub_geometry import AXIAL_PIN_LENGTH as PIN_LEN


DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia", "PinLen"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {"PinDia": 1, "PinLen": 1},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if {name for names in DRAWING_DIMENSIONS.values() for name in names} != set(
    DRAWING_PRECISION_BY_NAME
):
    raise AssertionError("every marked MHA-138 dimension needs authored places")

DRAWING_NOTES = (
    "MATCH-DRILL/REAM MHA-020 ARM AND MHA-137 HUB AT SIX O'CLOCK TO "
    "LIGHT DRIVE FIT ON ACTUAL MHA-138 PIN; DRIVE AXIALLY FROM OUTBOARD "
    "FACE; OUTER END FLUSH. PIN SHALL NOT ENTER HUB BORE."
)
