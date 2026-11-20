r"""Wheel drum (MHA-MG-10) nominal geometry -- the drawing-FREE constant block.

The brass drum is the book's "inner hub" of the 5:1 wheel-and-axle: a plain
ring pressed on the magnifying wheel's spigot up to the boss, its front face
never proud of the spigot face. The lever wire wraps it. Its OD seats the
fitted Ø.008 wire's centre where the 5:1 ratio is laid out: rim wire-centre
r 49.2 / drum wire-centre r 9.85 = 4.995.

PURE DATA, no SolidWorks/COM and no drawing imports: the wheel geom, the
lever-wire solver and the magnifier assembly import it.

Part frame: drum axis local Z, mid-plane symmetric about the Front plane.
"""

from __future__ import annotations

import _config
from _mcmaster_9666k142 import DIA as _WIRE_DIA
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_deviations

# #290: the registry row's drawing_unit (in) is this sheet's unit.
UNIT = drawing_unit("parts/mg-wheel-drum", _config.parts("mg-wheel-drum"))

# The lever wire the drum carries: the fitted 9666K142 wire itself
# (sh_vn_music_wire_lever_geom), no wider lane.
LEVER_WIRE_DIA = _WIRE_DIA
# The wire-centre radius the 5:1 ratio is laid out on (mg_magnifying_wheel_geom
# WIRE_RATIO). The O.D. seats the wire there (owner ruling 2026-11-20 on
# #2687, "A": the seat surfaces move out so the wire centres stay where they
# were): it keeps its millimetre value, prints rounded (.77) and the checks
# take the printed limits.
DRUM_WIRE_R = 9.85
DRUM_OD = round(2.0 * DRUM_WIRE_R - LEVER_WIRE_DIA, 6)  # 19.4968
# #290 owner ruling: the bore is reamed on the owned .4990 reamer.
DRUM_BORE = 12.6746  # .4990
# On the inch grid, .010 short of the wheel spigot's .354 (a 9.0 hub
# station): both lengths print on the title block's .XXX row, and the gap
# takes both bands, so the drum's face never stands proud of the spigot's
# (DRUM_RECESS in mg_magnifying_wheel_geom).
DRUM_LEN = 8.7376  # .344
# Printed bands, (upper, lower) deviations. The bore is reamed first: the
# wheel's spigot is turned to the stated interference in it (DRUM_PRESS in
# mg_magnifying_wheel_geom). The O.D. carries no band of its own: the wire
# wraps it, so it takes the title block's .XX row, which moves the
# wire-centre radius by at most .005 + its print rounding.
DRUM_OD_PLACES = 2
DRUM_BORE_PLACES = 4
DRUM_LEN_PLACES = 3
DRUM_BORE_BAND = (0.0127, 0.0)  # +.0005/.0000

# (lower, upper) deviations of the printed O.D. from the model.
DRUM_OD_DEVIATIONS = printed_deviations(DRUM_OD, DRUM_OD_PLACES, unit=UNIT)
if not DRUM_OD_DEVIATIONS[0] <= 0.0 <= DRUM_OD_DEVIATIONS[1]:
    raise AssertionError(
        f"drum O.D. model outside its printed limits: {DRUM_OD_DEVIATIONS}"
    )
# (lower, upper) deviations of the printed length from the model: .XXX.
DRUM_LEN_DEVIATIONS = printed_deviations(DRUM_LEN, DRUM_LEN_PLACES, unit=UNIT)

MIN_WALL = WALL_TARGET_MM  # drawing-guidelines.md rule 17 (walls and webs) target, at the worst printed band
WALL_WORST = (
    DRUM_OD + DRUM_OD_DEVIATIONS[0] - (DRUM_BORE + DRUM_BORE_BAND[0])
) / 2.0  # 3.308: (.76 - .4995) / 2 in
if WALL_WORST < MIN_WALL:
    raise AssertionError(f"drum wall {WALL_WORST:.3f} < {MIN_WALL}")
