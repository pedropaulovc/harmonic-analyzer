r"""Pure-data dimensional contract shared by the pinion lift rod and drawing."""

from __future__ import annotations

import math

import _config
from _fit_shaft_h import SHAFT_H
from _gtol_cylinder import CylinderFace
from _package_units import drawing_unit
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from pinion_rig_layout import LIFT_ROD_LEN

UNIT = drawing_unit("parts/dt-pinion-lift-rod", _config.parts("dt-pinion-lift-rod"))
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
# #290: the crown's sphere radius snaps to .19, and the crown height follows
# from it on the 1/4 in diameter (1.19, the old 1.2).
CAP_R = 4.826  # .19
CAP_SAG = CAP_R - math.sqrt(CAP_R**2 - ROD_DIA**2 / 4.0)
ROD_DIA_BAND = SHAFT_H

LEVER_NUMBER = "MHA-DT-16"
PIVOT_BLOCK_NUMBER = "MHA-DT-18"

# drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates): the rod turns in the pivot blocks' west bores -- the one running
# surface on the part.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "bearing", MACHINED_UM, CylinderFace(ROD_DIA), display_unit=UNIT
    ),
)

# One revolved half-profile carries the rod's size, body length, crown and
# overall, so all four print on the side view, as the part sits in the lathe
# (drawing-guidelines.md rule 11 (turned parts read like the lathe)).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RodProfile": {"RodDia", "RodBody", "CapR", "RodOverall"},
    # U36: the MHA-DT-30 pin hole, located from the flat front end face -- the
    # part origin sits on that face, so the circle's own anchor IS the
    # front-end baseline (drawing-guidelines.md rule 10 (dimension from a real feature)).
    "PinHoleProfile": {"PinHoleDia", "PinHoleZ"},
}
# The overall (front face to crown apex) prints in parentheses: the body
# length to the crown rim is the controlling size, because the rig's worst
# fitted stack (pinion_rig_layout) reads its .XX band (machinist review r1:
# the body length alone read like an overall that was not one, rule 10).
DRAWING_REFERENCE_DIMENSIONS = frozenset({"RodOverall"})

# Decimal places ARE the tolerance statement (drawing-simplicity-policy.md `How the repository implements the guidelines`); the part authors
# them and the drawing reads them back.  Four on the banded bearing diameter;
# three on the drilled pin hole, which takes the title block's DRILLED HOLES
# row (.064, +.004/0); two on the length the rig's stacks read, the crown, the
# reference overall and the pin station, which the lever's mid-engagement
# sets at assembly.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RodProfile": {"RodDia": 4, "RodBody": 2, "CapR": 2, "RodOverall": 2},
    "PinHoleProfile": {"PinHoleDia": 3, "PinHoleZ": 2},
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

# drawing-guidelines.md rule 4 (tighten only for function, and name the mate):
# the h band rides the diameter because the rod turns in the two MHA-DT-18
# blocks' reamed lift bores (+.0015/+.0010 slide band); ground 1/4 in shafting
# already holds it, so the stock is good enough as supplied (machinist review
# r1: the band and Ra named no mate).
ROD_DIA_CALLOUT = "\n".join(
    (
        f"RUNNING FIT IN {PIVOT_BLOCK_NUMBER} LIFT BORES,",
        "1/4 IN GROUND STOCK OK",
    )
)

# drawing-guidelines.md rule 7 (notes: few, flagged, never a method): the matched fit rides the pin hole's own callout, as the hole
# specification only; the drive and peen are
# dt_pinion_lever_pin_spec.ASSEMBLY_STEP (LEVER PIN SET).  The sheet carries
# no general notes: the SR view defines the crown (machinist review r1).
PIN_HOLE_CALLOUT = "\n".join(
    (
        "MATCH-DRILL THRU AT ASSEMBLY",
        f"IN {LEVER_NUMBER} HUB",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
