r"""Pure-data contract for the MHA-DT-35 floor hole's mouth break (#1757).

The cup's side of the MHA-DT-32 head seat (``dt_crank_handle_head_seat_spec``
holds the screw's side and the cross-part proofs).  Split from it so the cup's
recipes import the cup spec alone: the screw spec imports the handle spec and
the hub geometry, whose edits must not re-key the cup.  It carries the cup's
complete marked-dimension contract: the cup spec's rows plus the mouth break.

PURE DATA, no SolidWorks/COM imports.
"""

from __future__ import annotations

import dt_crank_handle_butt_cup_spec as cup
from _printed_tolerance import edge_break_chamfer_mm

# Delegated ruling 2026-11-12 (#1757, #2144): the owner's millimetre cup
# mouth 0.11-0.25 X 45 (#1694 proof), at this inch package's three places as
# .005-.010 (0.127-0.254).  The larger minimum only adds air over the R.004
# MAX under-head radius; the maximum is the title block's edge break, which
# the cup spec's floor budget already holds, and with the head's .010 the two
# maxima (0.508) stay inside the ruling's 0.51 break budget.  swTolLIMIT
# prints the two limits; the model sits at their middle.  (min, max) legs.
LIMIT_TOL_TYPE = 3  # swTolType_e.swTolLIMIT
FLOOR_HOLE_CHAMFER_LIMITS = (0.127, 0.254)  # .005-.010
FLOOR_HOLE_CHAMFER = round(sum(FLOOR_HOLE_CHAMFER_LIMITS) / 2.0, 6)

for _ok, _what in (
    (
        FLOOR_HOLE_CHAMFER_LIMITS[1] <= edge_break_chamfer_mm(unit=cup.UNIT),
        "the floor-hole break exceeds the edge break the cup spec's floor budgets",
    ),
    (
        cup.FLOOR_HOLE_DIA / 2.0 + FLOOR_HOLE_CHAMFER_LIMITS[1]
        < cup.POCKET_DIA / 2.0 - cup.POCKET_FLOOR_CORNER_R_MAX,
        "the floor-hole break meets the pocket-floor radius",
    ),
):
    if not _ok:
        raise AssertionError(f"MHA-DT-35 floor-hole mouth: {_what}")

# Decimal places are the tolerance (drawing-guidelines.md rule 3): the break's
# limits print at three places.
CUP_SEAT_DIMENSIONS = {"FloorHoleChamfer": 3}
CUP_DRAWING_DIMENSIONS: dict[str, set[str]] = {
    **cup.DRAWING_DIMENSIONS,
    "CupProfile": cup.DRAWING_DIMENSIONS["CupProfile"] | set(CUP_SEAT_DIMENSIONS),
}
CUP_DRAWING_PRECISION: dict[str, dict[str, int]] = {
    **cup.DRAWING_PRECISION,
    "CupProfile": {**cup.DRAWING_PRECISION["CupProfile"], **CUP_SEAT_DIMENSIONS},
}
CUP_DRAWING_PRECISION_BY_NAME = {
    name: places
    for row in CUP_DRAWING_PRECISION.values()
    for name, places in row.items()
}
if set(CUP_DRAWING_PRECISION_BY_NAME) != set().union(*CUP_DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-DT-35 dimension needs authored places")
