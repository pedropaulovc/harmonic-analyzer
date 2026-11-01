r"""Wheel drum (MHA-MG-10) nominal geometry -- the drawing-FREE constant block.

The brass drum is the book's "inner hub" of the 5:1 wheel-and-axle: a plain
ring pressed on the magnifying wheel's spigot up to the boss, its front face
never proud of the spigot face. The lever wire wraps it. Its OD is chosen so
the wire-centre ratio is 5: rim wire-centre r 49.2 / drum wire-centre r
(9.45 + 0.4) = 4.995.

PURE DATA, no SolidWorks/COM and no drawing imports: the wheel geom, the
lever-wire solver and the magnifier assembly import it.

Part frame: drum axis local Z, mid-plane symmetric about the Front plane.
"""

from __future__ import annotations

import _config
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_deviations

# #290: the registry row's drawing_unit (in) is this sheet's unit.
UNIT = drawing_unit("parts/mg-wheel-drum", _config.parts("mg-wheel-drum"))

# The O.D. keeps its millimetre nominal (it sets the wire ratio), prints
# rounded (.74) and the checks take the printed limits.
DRUM_OD = 18.9
# #290 owner ruling: the bore is reamed on the owned .4990 reamer.
DRUM_BORE = 12.6746  # .4990
# On the inch grid, so the model sits inside its minus-only band; the wheel's
# spigot keeps its 9.0 (a hub station), so the drum's face sits .0003 under it.
DRUM_LEN = 8.9916  # .354
# Printed bands, (upper, lower) deviations. The bore is reamed first: the
# wheel's spigot is turned to the stated interference in it (DRUM_PRESS in
# mg_magnifying_wheel_geom). The length is minus-only against the spigot's
# plus-only length (DRUM_RECESS there). The O.D. carries no band of its own:
# the wire wraps it, so it takes the title block's .XX row, which moves the
# wire-centre radius by at most .005 + its print rounding.
DRUM_OD_PLACES = 2
DRUM_BORE_PLACES = 4
DRUM_LEN_PLACES = 3
DRUM_BORE_BAND = (0.0127, 0.0)  # +.0005/.0000
DRUM_LEN_BAND = (0.0, -0.1016)  # +.000/-.004

LEVER_WIRE_DIA = 0.8  # the lever wire the drum carries (sh_vn_music_wire_lever_geom)
DRUM_WIRE_R = DRUM_OD / 2.0 + LEVER_WIRE_DIA / 2.0  # 9.85, wire-centre radius

# (lower, upper) deviations of the printed O.D. from the model.
DRUM_OD_DEVIATIONS = printed_deviations(DRUM_OD, DRUM_OD_PLACES, unit=UNIT)
if not DRUM_OD_DEVIATIONS[0] <= 0.0 <= DRUM_OD_DEVIATIONS[1]:
    raise AssertionError(
        f"drum O.D. model outside its printed limits: {DRUM_OD_DEVIATIONS}"
    )

MIN_WALL = WALL_TARGET_MM  # drawing-guidelines.md rule 17 (walls and webs) target, at the worst printed band
WALL_WORST = (
    DRUM_OD + DRUM_OD_DEVIATIONS[0] - (DRUM_BORE + DRUM_BORE_BAND[0])
) / 2.0  # 2.927: (.73 - .4995) / 2 in
if WALL_WORST < MIN_WALL:
    raise AssertionError(f"drum wall {WALL_WORST:.3f} < {MIN_WALL}")
