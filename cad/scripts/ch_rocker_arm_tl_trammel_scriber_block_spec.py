r"""Pure-data contract for the rocker template trammel's scriber block (MHA-CH-06-TL-15).

Shop tooling, not a machine part (cad/docs/subsystem-identities.md). The
second clamp-on block of the rocker outline-template trammel kit
(``ch_rocker_arm_tl_trammel_spec``, trial route ``rocker-template-route.md``
section 2.1): the pivot block's body, bar slot, set screws and pinch screw
(``ch_rocker_arm_tl_trammel_pivot_block_spec``, the shared section) with two
point holes 16.000 +/-0.025 apart for the two scriber points
(MHA-CH-06-TL-16): the inner one scribes R800, the outer one R816. Both holes
are reamed in one setting; the setting bar's H800/H816 cones
(MHA-CH-06-TL-17) prove the spacing.

The slit runs from the block's near end face through both point holes into
the pivot block's 3.0 drilled relief, 9 past the outer one (an 8 hinge less
the relief's radius). Two #8-32 socket head cap screws
pinch it: one between the near end and the inner hole, one midway between the
holes.

Frame: the pivot block's frame (see its spec) with the origin on the INNER
(R800) point hole's axis. The block occupies X = -17..+33, Y = -19.05..0,
Z = 0..38.1; kit (x, y, z) = (825 + X, Z - 13.0, Y). Every station prints
from the inner hole's axis; the outer hole is held to it by the 16.000 band.
"""

from __future__ import annotations

import ch_rocker_arm_tl_trammel_pivot_block_spec as block
import ch_rocker_arm_tl_trammel_spec as kit
from _printed_tolerance import printed_band_mm

HOLE_FROM_END = kit.SCRIBER_HOLE_L[0]  # 17.0: the end face to the inner hole
BLOCK_X0 = -HOLE_FROM_END
BLOCK_X1 = BLOCK_X0 + block.BLOCK_LENGTH
SCRIBER_SPACING = kit.SCRIBER_SPACING
HOLE_X = (0.0, SCRIBER_SPACING)
POINT_MATE_NUMBER = "MHA-CH-06-TL-16"
POINT_HOLE_CALLOUT = block.point_hole_callout(len(HOLE_X), POINT_MATE_NUMBER)
# drawing-guidelines.md rule 4: the tight spacing names what checks it, in
# one line (round 5).
SCRIBER_SPACING_CALLOUT = "CHECKED ON MHA-CH-06-TL-17"

SLIT_END_X = 42.0 - HOLE_FROM_END  # L42: the relief, 9 past the outer hole
SLIT_START_X = BLOCK_X0 - 1.0  # the slit sketch starts beyond the end face
SET_SCREW_X = tuple(station - HOLE_FROM_END for station in kit.SET_SCREW_L)
# L8 (between the near end and the inner hole) and L25 (midway between the
# holes, the only place a pinch can close the slit at the outer point).
PINCH_X = (8.0 - HOLE_FROM_END, 25.0 - HOLE_FROM_END)
if abs(PINCH_X[1] - SCRIBER_SPACING / 2.0) > 1e-9:
    raise AssertionError(
        "the scriber block's middle pinch is not midway between the points"
    )

# --- Worst cases (rules 17, 18) at the printed bands ----------------------------
_SPACING_TOL = max(abs(limit) for limit in kit.SCRIBER_SPACING_BAND)
WORST_WALLS = block.worst_walls(
    BLOCK_X0, HOLE_X, _SPACING_TOL, SET_SCREW_X, PINCH_X, SLIT_END_X
)
for _name, _wall in WORST_WALLS.items():
    if _wall < block.WALL_FLOOR:
        raise AssertionError(
            f"scriber block {_name} wall {_wall:.3f} under the rule 17 floor"
        )
# drawing-guidelines.md rule 20: walls between the floor and the target. The
# middle pinch's webs to the two point holes are the 16.000 spacing less two
# reamed radii and one #8 clearance: no station gives them 2.0.
RULE_20_SHORTFALLS = {
    name: wall for name, wall in WORST_WALLS.items() if wall < block.WALL_TARGET
}

# Each block's point-to-slot-wall distance rides one-place bands, so the two
# blocks can stand their points up to DELTA apart across the bar. At R816 the
# outer point then sits DELTA * 16 / 800 off the line through the pivot and
# the inner point: far inside the setting bar's H816 centre-drill pilot.
_X = printed_band_mm(1)
_POINT_TO_WALL_DELTA = 2.0 * (
    _X + _X + (kit.SLOT_WIDTH_BAND[0] - kit.SLOT_WIDTH_BAND[1]) / 2.0
)
H816_LATERAL_MISS = _POINT_TO_WALL_DELTA * SCRIBER_SPACING / kit.TEMPLATE_RADII[0]
if H816_LATERAL_MISS >= kit.CENTER_DRILL_PILOT_DIA / 2.0:
    raise AssertionError("the outer scriber misses the setting bar's H816 cone")

# --- Drawing ----------------------------------------------------------------------
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"BlockLength", "BlockWidth", "HoleFromEnd"},
    "Block": {"BlockHeight"},
    "SlotProfile": {"SlotWidth", "SlotFromEdgeA", "SlotDepth"},
    "SlitProfile": {"SlitWidth"},
    "SlitReliefProfile": {"SlitEnd", "SlitReliefDia"},
    "PointHoleProfile": {"PointHoleDia", "PointFromEdgeA", "ScriberSpacing"},
    "SetScrewTaps": {"SetScrewX1", "SetScrewX2", "SetScrewDepth"},
    "PinchTaps": {"PinchX1", "PinchX2", "PinchDepth"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlockProfile": {"BlockLength": 1, "BlockWidth": 1, "HoleFromEnd": 1},
    "Block": {"BlockHeight": block.BLOCK_HEIGHT_PLACES},
    "SlotProfile": {
        "SlotWidth": 2,
        "SlotFromEdgeA": 1,
        "SlotDepth": block.SLOT_DEPTH_PLACES,
    },
    "SlitProfile": {"SlitWidth": 1},
    "SlitReliefProfile": {"SlitEnd": 1, "SlitReliefDia": 1},
    "PointHoleProfile": {"PointHoleDia": 3, "PointFromEdgeA": 1, "ScriberSpacing": 3},
    "SetScrewTaps": {"SetScrewX1": 1, "SetScrewX2": 1, "SetScrewDepth": 1},
    "PinchTaps": {"PinchX1": 1, "PinchX2": 1, "PinchDepth": block.PINCH_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked scriber block dimension needs authored places")

# The same slot, so the same bar-contact faces and Ra (the pivot block's rows).
SURFACE_FINISHES = block.SURFACE_FINISHES
DRAWING_NOTES = "THE PINCH SCREWS CLOSE THE SLIT ON BOTH SCRIBER POINTS."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
