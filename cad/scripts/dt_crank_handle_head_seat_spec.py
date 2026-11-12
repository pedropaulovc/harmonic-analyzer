r"""Pure-data contract for the MHA-DT-32 head's seat on the MHA-DT-35 floor (#1757).

The pivot screw's head bears on the butt cup's floor whenever the handle is
drawn outward through its fitted end play.  Three corners meet at that seat,
and each is real model geometry printed by its own native dimension:

* the screw's under-head inside corner, Ø.156 shoulder into the head: a radius
  of ``R.004 MAX``.  Left to the title block's INSIDE CORNERS R.040 MAX, a
  turning-tool nose could leave a radius ten times larger, which rides on the
  floor hole's edge and stands the head off the floor;
* the cup's floor-hole mouth on the pocket side: a 45-degree break between
  two limits, so even the largest under-head radius, with the shoulder pushed
  against the hole wall, lands in the break and not on its edge;
* the head's outer edge on the under-head side: a 45-degree break between the
  same limits, so it clears the cup's ``R.004 MAX`` pocket-floor corner with
  the head pushed against the pocket wall.

Owner ruling on #1757 (the millimetre R0.1 MAX, 0.11-0.25 and 0.11-0.26 X 45
of the #1694 proof), at this inch package's three places: each break's
minimum exceeds the radius it clears, and the two maxima together still leave
the flat bearing annulus.  The maxima equal the title block's edge break, so
the part specs' worst-case floor and annulus figures, which budget that break
on these edges, stay valid unchanged.

Split from both part specs: the crank arm, the handle and the keeper chain
import those, so the seat's numbers living there re-keyed parts that never
touch it.  Only the screw's and the cup's builders and drawings import this
module.  It therefore also carries each part's complete marked-dimension
contract: the part spec's rows plus the seat dimensions above.

PURE DATA, no SolidWorks/COM imports.
"""

from __future__ import annotations

import math

import dt_crank_handle_butt_cup_spec as cup
import dt_crank_handle_pivot_screw_spec as screw
from _printed_tolerance import drilled_oversize_mm, edge_break_chamfer_mm

# The screw's under-head radius, printed as the single limit R.004 MAX
# (swTolMAX: the modelled radius IS the printed limit, sharp allowed).
UNDER_HEAD_RADIUS_MAX = 0.1016  # .004
UNDER_HEAD_RADIUS_BAND = (0.0, -UNDER_HEAD_RADIUS_MAX)  # (upper, lower)
UNDER_HEAD_RADIUS_TOL_TYPE = 6  # swTolType_e.swTolMAX
# Both 45-degree breaks print their two limits (swTolLIMIT); each is modelled
# at the middle of its limits.  (min, max) axial legs.
LIMIT_TOL_TYPE = 3  # swTolType_e.swTolLIMIT
HEAD_CHAMFER_LIMITS = (0.127, 0.254)  # .005-.010
FLOOR_HOLE_CHAMFER_LIMITS = (0.127, 0.254)  # .005-.010
HEAD_CHAMFER = round(sum(HEAD_CHAMFER_LIMITS) / 2.0, 6)
FLOOR_HOLE_CHAMFER = round(sum(FLOOR_HOLE_CHAMFER_LIMITS) / 2.0, 6)

# Corner air at the worst case, normal to each break, with the mating corner
# pushed against its wall (zero radial gap).  A radius R fills its corner out
# to R along both faces, so a 45-degree break of leg c clears it by
# (c - R)/sqrt(2); the smallest break meets the largest radius.
UNDER_HEAD_AIR_MIN = round(
    (FLOOR_HOLE_CHAMFER_LIMITS[0] - UNDER_HEAD_RADIUS_MAX) / math.sqrt(2.0), 6
)
HEAD_EDGE_AIR_MIN = round(
    (HEAD_CHAMFER_LIMITS[0] - cup.POCKET_FLOOR_CORNER_R_MAX) / math.sqrt(2.0), 6
)
# The flat annulus the head bears on: the smallest head less its largest break,
# over the largest drilled floor hole plus its largest break, on the narrow
# side with the head pushed off-centre by its running play.
FLOOR_HOLE_DIA_MAX = round(cup.FLOOR_HOLE_DIA + drilled_oversize_mm(unit=cup.UNIT), 6)
HEAD_BEARING_FLAT_MIN = round(
    (screw.HEAD_DIA - screw.HEAD_DIA_TOL) / 2.0
    - HEAD_CHAMFER_LIMITS[1]
    - (FLOOR_HOLE_DIA_MAX / 2.0 + FLOOR_HOLE_CHAMFER_LIMITS[1])
    - screw.HEAD_RUNNING_OFFSET_MAX,
    6,
)
HEAD_BEARING_FLAT_FLOOR_MM = 0.1

for _ok, _what in (
    (
        UNDER_HEAD_AIR_MIN > 0.0,
        "the largest under-head radius lands on the floor-hole mouth",
    ),
    (
        HEAD_EDGE_AIR_MIN > 0.0,
        "the head's outer edge lands on the cup's pocket-floor radius",
    ),
    (
        HEAD_BEARING_FLAT_MIN >= HEAD_BEARING_FLAT_FLOOR_MM,
        "under 0.1 mm of flat under-head bearing on the cup floor",
    ),
    (
        HEAD_CHAMFER_LIMITS[1] <= screw.EDGE_BREAK_MAX_MM,
        "the head break exceeds the edge break the screw spec's annulus budgets",
    ),
    (
        FLOOR_HOLE_CHAMFER_LIMITS[1] <= edge_break_chamfer_mm(unit=cup.UNIT),
        "the floor-hole break exceeds the edge break the cup spec's floor budgets",
    ),
    (
        UNDER_HEAD_RADIUS_MAX + HEAD_CHAMFER_LIMITS[1]
        < (screw.HEAD_DIA - screw.HEAD_DIA_TOL - screw.SHOULDER_DIA_MAX) / 2.0,
        "the under-head radius and head break leave no flat under-head face",
    ),
    (
        cup.FLOOR_HOLE_DIA / 2.0 + FLOOR_HOLE_CHAMFER_LIMITS[1]
        < cup.POCKET_DIA / 2.0 - cup.POCKET_FLOOR_CORNER_R_MAX,
        "the floor-hole break meets the pocket-floor radius",
    ),
):
    if not _ok:
        raise AssertionError(f"MHA-DT-32/35 head seat: {_what}")

# Each part's complete marked-dimension contract: its spec's rows plus the
# seat's.  Decimal places are the tolerance (drawing-guidelines.md rule 3):
# the radius limit and both breaks print at three places.
SCREW_SEAT_DIMENSIONS = {"UnderHeadRadius": 3, "HeadChamfer": 3}
CUP_SEAT_DIMENSIONS = {"FloorHoleChamfer": 3}
SCREW_DRAWING_DIMENSIONS: dict[str, set[str]] = {
    **screw.DRAWING_DIMENSIONS,
    "ScrewProfile": screw.DRAWING_DIMENSIONS["ScrewProfile"]
    | set(SCREW_SEAT_DIMENSIONS),
}
SCREW_DRAWING_PRECISION: dict[str, dict[str, int]] = {
    **screw.DRAWING_PRECISION,
    "ScrewProfile": {
        **screw.DRAWING_PRECISION["ScrewProfile"],
        **SCREW_SEAT_DIMENSIONS,
    },
}
CUP_DRAWING_DIMENSIONS: dict[str, set[str]] = {
    **cup.DRAWING_DIMENSIONS,
    "CupProfile": cup.DRAWING_DIMENSIONS["CupProfile"] | set(CUP_SEAT_DIMENSIONS),
}
CUP_DRAWING_PRECISION: dict[str, dict[str, int]] = {
    **cup.DRAWING_PRECISION,
    "CupProfile": {**cup.DRAWING_PRECISION["CupProfile"], **CUP_SEAT_DIMENSIONS},
}


def _by_name(precision: dict[str, dict[str, int]]) -> dict[str, int]:
    return {name: places for row in precision.values() for name, places in row.items()}


SCREW_DRAWING_PRECISION_BY_NAME = _by_name(SCREW_DRAWING_PRECISION)
CUP_DRAWING_PRECISION_BY_NAME = _by_name(CUP_DRAWING_PRECISION)
for _label, _dimensions, _places in (
    ("MHA-DT-32", SCREW_DRAWING_DIMENSIONS, SCREW_DRAWING_PRECISION_BY_NAME),
    ("MHA-DT-35", CUP_DRAWING_DIMENSIONS, CUP_DRAWING_PRECISION_BY_NAME),
):
    if set(_places) != set().union(*_dimensions.values()):
        raise AssertionError(f"every marked {_label} dimension needs authored places")
