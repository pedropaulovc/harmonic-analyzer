r"""Pure-data contract for the pivot bracket's angle-plate ledge (MHA-CH-008-TL-01).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). In the
bracket's S4 setup (prechips bracket plan S4 hold) the bracket's seat face
lies on the reworked angle plate's upright (MHA-CH-008-TL-02) and its foot
free end rests on this 1018 block, screwed to the upright by two
#10-24 x 5/8 SHCS through #5 holes. The ledge top carries the downward
facing and drilling load; S4 indicates the foot edge and touches Z on the
part (its faced outer face, in the plane of the ear's inboard face, which the
hold-down station is given from), so the ledge is a plain stop. Fitting: the
ledge stands on a 1-2-3 block on the table, back face flat on the upright,
and the upright's taps are spotted through its two holes before it is
screwed down.

Frame (model, mm): origin at the ledge's left end, on its bottom face and in
its back face (the face that seats on the upright). +X along the ledge, +Y up,
+Z out of the front face (the back face is Z0, the front face Z LEDGE_THICK).
It is the angle plate's model frame translated by
(PLATE_LENGTH/2 - LEDGE_WIDTH/2, BLOCK_HEIGHT, 0), so the inventory's fixture
frame (bracket plan setup frame TC) is
TC = (x - LEDGE_WIDTH/2, -z, y + BLOCK_HEIGHT - (PLATE_HEIGHT + PART_PROUD)).
"""

from __future__ import annotations

import _config
import ch_pivot_bracket_spec as bracket
import ch_pivot_bracket_tl_angle_plate_spec as plate
from _hole_spec import blind_cut_dia_mm
from _printed_tolerance import drilled_oversize_mm, printed_deviations

# As thick as the foot's depth off the upright and as tall as the gap from the
# 1-2-3 block to the foot's free end. Wider than the 16 foot it carries so its
# two screw holes, spread for head clearance, keep the drawing-guidelines.md rule 17 (walls and webs) 2.0 walls at
# general tolerance; its ends stay clear of the bridge's stud nuts.
LEDGE_WIDTH = 22.6
LEDGE_THICK = bracket.FOOT_H  # 6.0
# 26.9, under the bracket's foot at the stack's worst case (angle-plate spec)
LEDGE_HEIGHT = round(plate.LEDGE_TOP_Y - plate.BLOCK_HEIGHT, 6)
SIZE_PLACES = 1
if LEDGE_WIDTH < bracket.FOOT_W:
    raise AssertionError("ledge narrower than the bracket foot it carries")
if round(LEDGE_WIDTH + printed_deviations(LEDGE_WIDTH, SIZE_PLACES)[1], 12) / 2.0 >= plate.STUD_HALF_PITCH - plate.STUD_NUT_DIA / 2.0:
    raise AssertionError("ledge end reaches a bridge stud nut")

# Two #5 screw holes, 10.5 under the top, on the upright's tap pitch. The taps
# are spotted through these holes, so their stations only have to keep the
# walls, all at the general one-place tolerance.
CLEARANCE_SPEC = plate.LEDGE_CLEARANCE_SPEC
HOLE_X = (
    round(LEDGE_WIDTH / 2.0 - plate.SCREW_HALF_PITCH, 6),
    round(LEDGE_WIDTH / 2.0 + plate.SCREW_HALF_PITCH, 6),
)
HOLE_Y = round(plate.SCREW_Y - plate.BLOCK_HEIGHT, 6)  # 16.4
HOLE_X_PLACES = 1
HOLE_Y_PLACES = 1
HOLE_DIA = blind_cut_dia_mm(CLEARANCE_SPEC)
_HOLE_R_MAX = (HOLE_DIA + drilled_oversize_mm()) / 2.0
_X1 = [round(HOLE_X[0] + deviation, 12) for deviation in printed_deviations(HOLE_X[0], HOLE_X_PLACES)]
_X2 = [round(HOLE_X[1] + deviation, 12) for deviation in printed_deviations(HOLE_X[1], HOLE_X_PLACES)]
_Y = [round(HOLE_Y + deviation, 12) for deviation in printed_deviations(HOLE_Y, HOLE_Y_PLACES)]
HOLE_LIGAMENTS_MIN = {
    "left end": _X1[0] - _HOLE_R_MAX,
    "right end": round(LEDGE_WIDTH + printed_deviations(LEDGE_WIDTH, SIZE_PLACES)[0], 12) - _X2[1] - _HOLE_R_MAX,
    "web": _X2[0] - _X1[1] - 2.0 * _HOLE_R_MAX,
    "bottom": _Y[0] - _HOLE_R_MAX,
    "top": round(LEDGE_HEIGHT + printed_deviations(LEDGE_HEIGHT, SIZE_PLACES)[0], 12) - _Y[1] - _HOLE_R_MAX,
}
if min(HOLE_LIGAMENTS_MIN.values()) < 2.0:
    raise AssertionError(f"ledge screw-hole ligaments {HOLE_LIGAMENTS_MIN} under 2.0")
# Each station floats on its own one-place band, so the pitch can close by
# both; the two SHCS heads, each up to its B18.3 eccentricity off its shank
# toward the other, must still stand apart at that worst case.
HEAD_GAP_MIN = (
    _X2[0] - _X1[1] - plate.SCREW_HEAD_DIA_MAX - 2.0 * plate.SCREW_HEAD_ECCENTRICITY_MAX
)
if HEAD_GAP_MIN < plate.SCREW_HEAD_GAP_MIN:
    raise AssertionError(f"ledge screw heads clear by only {HEAD_GAP_MIN:.2f} at worst-case pitch")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "LedgeProfile": {"Width", "Height"},
    "Ledge": {"Thick"},
    "ScrewHoles": {"Hole1X", "Hole2X", "Hole1Y"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "LedgeProfile": {"Width": SIZE_PLACES, "Height": SIZE_PLACES},
    "Ledge": {"Thick": SIZE_PLACES},
    "ScrewHoles": {"Hole1X": HOLE_X_PLACES, "Hole2X": HOLE_X_PLACES, "Hole1Y": HOLE_Y_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dimensions in DRAWING_PRECISION.values() for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked ledge dimension needs authored places")

SURFACE_FINISHES = ()
# The upright's taps are spotted through the two screw holes, so that transfer
# rides the holes' 2X callout, naming the mate by its part number (rule 7:
# flag it where it applies; rule 4: name the mate), not a floating note. The
# callout's own drill row follows these lines.
ANGLE_PLATE_NUMBER = _config.parts("ch-pivot-bracket-tl-angle-plate")["number"]
SPOT_TAPS_LINES = (
    "SPOT TAPS IN ANGLE PLATE",
    f"{ANGLE_PLATE_NUMBER} THROUGH",
    "THESE HOLES AT ASSEMBLY;",
)
SPOT_TAPS_NOTE = " ".join(SPOT_TAPS_LINES)
# No general note: the one fact the views cannot carry is on the hole callout.
DRAWING_NOTES = ""
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"

