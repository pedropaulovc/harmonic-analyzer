r"""Pure-data dimensional contract shared by the pinion lift rod and drawing."""

from __future__ import annotations

from _fit_limits import SHAFT_H
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from pinion_rig_layout import LIFT_ROD_LEN

ROD_DIA = 6.35
# Back end flush with the back block, front end the lever hub's seat past the
# front block; ruling (c) moved that block inboard (pinion_rig_layout),
# 202 -> 192.4.
ROD_LEN = LIFT_ROD_LEN
CAP_SAG = 1.2
CAP_R = round((ROD_DIA**2 / 4.0 + CAP_SAG**2) / (2.0 * CAP_SAG), 2)  # 4.80
ROD_DIA_BAND = SHAFT_H

LEVER_NUMBER = "MHA-059"
PIN_NUMBER = "MHA-135"

# Rule 5: the rod turns in the pivot blocks' west bores -- the one running
# surface on the part.
SURFACE_FINISHES = (
    SurfaceFinishControl("bearing", MACHINED_UM, CylinderFace(ROD_DIA)),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RodProfile": {"RodDia"},
    "Rod": {"Depth"},
    "BackCapProfile": {"CapR"},
    # U36: the MHA-135 pin hole, located from the flat front end face -- the
    # part origin sits on that face, so the circle's own anchor IS the
    # front-end baseline (policy rule 7).
    "PinHoleProfile": {"PinHoleDia", "PinHoleZ"},
}

# Decimal places ARE the tolerance statement (policy rule 2); the part authors
# them and the drawing reads them back.  Two on the banded bearing diameter and
# the drilled pin hole; one on the length, the crown and the pin station,
# which the lever's mid-engagement sets at assembly.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RodProfile": {"RodDia": 2},
    "Rod": {"Depth": 1},
    "BackCapProfile": {"CapR": 1},
    "PinHoleProfile": {"PinHoleDia": 2, "PinHoleZ": 1},
}
_PRECISION_NAMES = [
    (feature, name) for feature, names in DRAWING_PRECISION.items() for name in names
]
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: DRAWING_PRECISION[feature][name] for feature, name in _PRECISION_NAMES
}
if len(DRAWING_PRECISION_BY_NAME) != len(_PRECISION_NAMES):
    raise AssertionError("DRAWING_PRECISION repeats a dimension name across features")
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked dimension must state its decimal places")

# Rule 6: the matched fit rides the pin hole's own callout.
PIN_HOLE_CALLOUT = "\n".join(
    (
        f"MATCH-DRILL THRU AT ASSEMBLY IN {LEVER_NUMBER}",
        f"HUB; DRIVE {PIN_NUMBER}, PEEN FLUSH",
    )
)
DRAWING_NOTES = "BACK-END CROWN BLENDS INTO THE OD WITH NO STEP."
END_VIEW_NOTE = "END VIEW SCALE 2:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
