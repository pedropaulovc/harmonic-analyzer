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
    raise AssertionError("every marked MHA-138 dimension needs authored places")

# Rule 6: the part facts only.  How the seam is match-drilled and the pin
# driven is the drive-train sheet's step 6 (the #814 class; #921 follow-up),
# the fit is the MHA-020/MHA-137 seam callouts', and the six o'clock station
# is modelled on both parts.  The pin cannot reach the hub bore:
# crank_hub_geometry.SEAM_WEB_WORST_MM holds the web to the wall target.
DRAWING_NOTES = "\n".join(
    (
        "SEAM PIN FOR THE MHA-020 ARM AND MHA-137 HUB, FITTED AT ASSEMBLY.",
        "DIA 4.0: 4 mm m6 DOWEL STOCK AS SUPPLIED.",
    )
)
