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

The owner's millimetre ruling on #1757 and its delegated inch adaptation sit
beside the constants they govern, here and in the cup's
``dt_crank_handle_butt_cup_seat_spec``.  Each break's minimum exceeds the
radius it clears, and the maxima equal the title block's edge break, so the
screw spec's worst-case bearing annulus (``HEAD_BEARING_RADIAL_MIN``), which
budgets that break on both edges, stays the one figure for the flat seat.

Split from both part specs: the crank arm, the handle and the keeper chain
import those, so the seat's numbers living there re-keyed parts that never
touch it.  Only the screw's builder and drawing import this module (the
cup's recipes import the cup-side module alone).  It therefore also carries
the screw's complete marked-dimension contract: the screw spec's rows plus
the seat dimensions above.

PURE DATA, no SolidWorks/COM imports.
"""

from __future__ import annotations

import math

import dt_crank_handle_butt_cup_spec as cup
import dt_crank_handle_pivot_screw_spec as screw
from dt_crank_handle_butt_cup_seat_spec import FLOOR_HOLE_CHAMFER_LIMITS

# Delegated ruling 2026-11-12 (#1757, #2144): the owner's millimetre inner
# R0.1 MAX and head outer 0.11-0.26 X 45 (#1694 proof), at this inch
# package's three places.  The radius prints the single limit R.004 MAX
# (swTolMAX: the modelled radius IS the printed limit, sharp allowed); the
# 1.6 um over R0.1 is swallowed by the larger break minima.  The break prints
# .005-.010 (0.127-0.254) as two limits (swTolLIMIT), modelled at their
# middle: its larger minimum only adds air over the cup's R.004 MAX floor
# corner, and its maximum is the title block's edge break.  (min, max) legs.
UNDER_HEAD_RADIUS_MAX = 0.1016  # .004
UNDER_HEAD_RADIUS_BAND = (0.0, -UNDER_HEAD_RADIUS_MAX)  # (upper, lower)
UNDER_HEAD_RADIUS_TOL_TYPE = 6  # swTolType_e.swTolMAX
HEAD_CHAMFER_LIMITS = (0.127, 0.254)  # .005-.010
HEAD_CHAMFER = round(sum(HEAD_CHAMFER_LIMITS) / 2.0, 6)

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

for _ok, _what in (
    (
        UNDER_HEAD_AIR_MIN > 0.0,
        "the largest under-head radius lands on the floor-hole mouth",
    ),
    (
        HEAD_EDGE_AIR_MIN > 0.0,
        "the head's outer edge lands on the cup's pocket-floor radius",
    ),
    # The screw spec's bearing annulus budgets the edge break on the head's
    # edge and on the floor hole's mouth: neither break may exceed it.
    (
        max(HEAD_CHAMFER_LIMITS[1], FLOOR_HOLE_CHAMFER_LIMITS[1])
        <= screw.EDGE_BREAK_MAX_MM,
        "a seat break exceeds the edge break the screw spec's annulus budgets",
    ),
    (
        UNDER_HEAD_RADIUS_MAX + HEAD_CHAMFER_LIMITS[1]
        < (screw.HEAD_DIA - screw.HEAD_DIA_TOL - screw.SHOULDER_DIA_MAX) / 2.0,
        "the under-head radius and head break leave no flat under-head face",
    ),
):
    if not _ok:
        raise AssertionError(f"MHA-DT-32/35 head seat: {_what}")

# The screw's complete marked-dimension contract: its spec's rows plus the
# seat's.  Decimal places are the tolerance (drawing-guidelines.md rule 3):
# the radius limit and the break print at three places.
SCREW_SEAT_DIMENSIONS = {"UnderHeadRadius": 3, "HeadChamfer": 3}
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
SCREW_DRAWING_PRECISION_BY_NAME = {
    name: places
    for row in SCREW_DRAWING_PRECISION.values()
    for name, places in row.items()
}
if set(SCREW_DRAWING_PRECISION_BY_NAME) != set().union(
    *SCREW_DRAWING_DIMENSIONS.values()
):
    raise AssertionError("every marked MHA-DT-32 dimension needs authored places")
