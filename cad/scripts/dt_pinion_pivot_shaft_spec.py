r"""Pure-data dimensional contract shared by the pinion strap torque shaft
(MHA-DT-19) and its manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A plain Ø6.35 steel shaft with a
shallow spherical crown at each end -- the pivot the two swing straps rock on.

Part frame: axis along Z, origin on the axis at the FRONT end of the cylinder,
the body running toward +Z.  It is modelled as one Right-plane half-profile
revolved (sketch u = -z), so the diameter and the body length import into
the side view (drawing-guidelines.md rule 11 (turned parts read like the
lathe)), one Right-plane revolved crown at each end, and one Right-plane cut
for both pin holes, whose sketch also carries the overall length between the
two crown tips.  The nominals drive the part's named equation globals AND
the drawing's coordinate math; the marked-dimension map keeps the part marks
and the drawing in lockstep (``test_dt_pinion_pivot_shaft_drawing.py``).
"""

from __future__ import annotations

import _config
from _fit_shaft_h import SHAFT_H
from _gtol_cylinder import CylinderFace
from _package_units import drawing_unit
from _surface_finish import MACHINED_UM, SurfaceFinishControl
import dt_vn_pinion_strap_pin_spec as _strap_pin
from pinion_rig_layout import (
    TORQUE_SHAFT_LEN,
    TORQUE_SHAFT_PIN_HOLE_Z,
)

UNIT = drawing_unit(
    "parts/dt-pinion-pivot-shaft", _config.parts("dt-pinion-pivot-shaft")
)
SHAFT_DIA = 6.35  # 1/4 in: rides both pivot blocks' east bores and the straps
# Set back-flush with the back block's outer face; ruling (c) moved the front
# block inboard to the front strap (pinion_rig_layout), 192 -> 182.0, then
# the worst fitted stack (Codex #854 P1) made it long enough that the
# shortest shaft still bears 9.5 of the front block
# (pinion_rig_layout.torque_shaft_bearing_stack).
SHAFT_LEN = TORQUE_SHAFT_LEN
CAP_SAG = 1.27  # .05; shallow spherical crown height at each end
CAP_RADIUS = ((SHAFT_DIA / 2.0) ** 2 + CAP_SAG**2) / (2.0 * CAP_SAG)
SHAFT_DIA_BAND = SHAFT_H
# U27 (Main, 2026-09-24): the length carries the title-block band, not a
# tight one (#290: .XX, since the rig's stacks read it).  Pinned to the straps
# (option E-a) the shaft rides the cluster's end play (0.25 +/- 0.10): drilled
# back-flush at the back stop, its back end then sits inside the back block,
# still bearing the shallowest one's floor past its flush setting
# (pinion_rig_layout.torque_shaft_back_bearing_stack).
# Nothing stands on the shaft's axis past either block: the nearest body, the
# MHA-DT-16 lever, rides the lift rod 18.63 off it -- hub 8.95 radial clear,
# arm >= 12.42 clear over the -82 degree throw (test_dt_drive_train_support_layout::
# test_torque_shaft_length_band_clears_both_ends).
# Decimal places are the tolerance (drawing-guidelines.md rule 3).  The body
# length, its crown height and the overall length read the title-block .XX
# row; the O.D. carries its running band and the spring pin's hole its
# +.0025/0 band at four places.  The crown's sphere radius is a reference: the
# crown height on the toleranced diameter already fixes it.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ShaftProfile": {"ShaftDia": 4, "ShaftLength": 2},
    "CapFrontProfile": {"CapFrontSag": 2, "CapFrontR": 2},
    "PinHoleProfile": {"PinHoleDia": 4, "OverallLength": 2},
}

# Option E-a set pins (dt_vn_pinion_strap_pin_spec): one cross hole under each
# MHA-DT-14 strap, match-drilled through the strap's own cross hole with the
# shaft back-flush and the cluster at the back stop -- the fit-up stack the
# assembly shows (pinion_rig_layout) -- so they sit at its strap mid-planes,
# from the front end (local z 0).  The print
# carries no station: the strap sets it at assembly, so a printed one would be
# a second, conflicting specification on a shaft whose length floats +/-.01.
PIN_HOLE_DIA = _strap_pin.HOLE_DIA
PIN_HOLE_BAND = _strap_pin.HOLE_BAND  # the spring pin's functional band
PIN_HOLE_Z = TORQUE_SHAFT_PIN_HOLE_Z  # (front, back), pinion_rig_layout
# The hole specification only.  The drilling set-up the pin-hole stations
# and both bearing stacks assume is an assembly step: Main's re-ruling
# (2026-09-26) moved it from this callout to MHA-DT-00's SHAFT DRILL SET
# (pinion_rig_fitup.SHAFT_DRILL_STEP), where the fitter drills, superseding
# the #858 restricted review's rulings 2 and 3.  The drawing adds the
# pointer to that step (draw_dt_pinion_pivot_shaft): it is sheet text, so the
# part never reads the assembly step registry.
PIN_HOLE_CALLOUT = "\n".join(
    (
        "MATCH-DRILL THRU AT ASSEMBLY",
        "IN MHA-DT-14 CROSS HOLES, 2 PL",
    )
)

SURFACE_FINISHES = (
    SurfaceFinishControl(
        "bearing", MACHINED_UM, CylinderFace(SHAFT_DIA), display_unit=UNIT
    ),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    feature: set(names) for feature, names in DRAWING_PRECISION.items()
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
if len(DRAWING_PRECISION_BY_NAME) != sum(map(len, DRAWING_PRECISION.values())):
    raise AssertionError("DRAWING_PRECISION repeats a dimension name across features")

# The two crowns are one recipe: the front one prints for BOTH ENDS.
CROWN_CALLOUT = "BOTH ENDS"
OVERALL_LEN = SHAFT_LEN + 2.0 * CAP_SAG  # tip to tip, a reference

# Part-specific facts a machinist cannot read off the views
# (drawing-guidelines.md rule 7 (notes: few, flagged, never a method)).
# A 7.4 in long 1/4 in bar is turned between centres; nothing bears on either
# crown's apex, so a centre hole there does no harm.
DRAWING_NOTES = "CENTRES OK."
# The isometric renders at ISO_SCALE (1, 2) while the sheet/title block reads
# 1:1, so without this the pictorial is silently half scale.
ISO_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
