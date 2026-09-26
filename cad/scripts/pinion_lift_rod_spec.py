r"""Pure-data dimensional contract shared by the pinion lift rod and drawing."""

from __future__ import annotations

from _fit_limits import SHAFT_H
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from pinion_rig_layout import LIFT_ROD_LEN

ROD_DIA = 6.35
# Back end flush with the back block, front end the lever hub's seat past the
# front block; ruling (c) moved that block inboard (pinion_rig_layout),
# 202 -> 192.0 (Codex #854), then 197.0 so the hub clears the block at the
# worst fitted stack, both blocks' .XX depth bands included
# (pinion_rig_layout.lift_rod_seat_stack, Codex #837/#854), then 197.5 for
# the deeper E-a blocks (Codex #858), then 197.8 for the drum's end shim
# (Main, #858 ruling 3), then 198.8 for the 11.0 blocks, then 199.5 for the
# 0.45 drum shim, the 6.25 back-collar pin plane and RIG_MARGIN_SPARE past
# the lever seat (Main, #858), then 198.3 once the back collar went on its
# leaf F (user ruling P1-1): the lever throw plane's air to the torque shaft's
# front end now sizes it, not the seat.
ROD_LEN = LIFT_ROD_LEN
CAP_SAG = 1.2
CAP_R = round((ROD_DIA**2 / 4.0 + CAP_SAG**2) / (2.0 * CAP_SAG), 2)  # 4.80
ROD_DIA_BAND = SHAFT_H

LEVER_NUMBER = "MHA-059"

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

# Rule 6: the matched fit rides the pin hole's own callout, as the hole
# specification only; the drive and peen are
# pinion_lever_pin_spec.ASSEMBLY_STEP (LEVER PIN SET).
PIN_HOLE_CALLOUT = "\n".join(
    (
        "MATCH-DRILL THRU AT ASSEMBLY",
        f"IN {LEVER_NUMBER} HUB",
    )
)
DRAWING_NOTES = "BACK-END CROWN BLENDS INTO THE OD WITH NO STEP."
END_VIEW_NOTE = "END VIEW SCALE 2:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
