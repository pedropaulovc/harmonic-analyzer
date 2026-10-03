r"""Pure-data contract for the MHA-VN-029 axial arm-to-hub seam pin."""

from __future__ import annotations

from dt_crank_hub_geometry import AXIAL_PIN_DIA as PIN_DIA
from dt_crank_hub_geometry import AXIAL_PIN_LENGTH as PIN_LEN


DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia", "PinLen"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {"PinDia": 1, "PinLen": 1},
}
# The diameter is the as-supplied m6 dowel, so it prints as a reference: its
# one place must not read as a .X band to machine to.
REFERENCE_DIMENSIONS = frozenset({"PinDia"})
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if {name for names in DRAWING_DIMENSIONS.values() for name in names} != set(
    DRAWING_PRECISION_BY_NAME
):
    raise AssertionError("every marked MHA-VN-029 dimension needs authored places")

DRAWING_NOTES = "\n".join(
    (
        "MATCH-DRILL/REAM MHA-DT-006 ARM AND MHA-DT-031 HUB AT SIX O'CLOCK TO",
        "LIGHT DRIVE FIT ON ACTUAL MHA-VN-029 PIN; DRIVE AXIALLY FROM OUTBOARD FACE;",
        "OUTER END FLUSH. PIN SHALL NOT ENTER HUB BORE.",
        "DIA 4.0: 4 mm m6 DOWEL STOCK AS SUPPLIED.",
    )
)
