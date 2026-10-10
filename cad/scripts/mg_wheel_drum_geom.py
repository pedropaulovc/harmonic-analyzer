r"""Wheel drum (MHA-MG-010) nominal geometry -- the drawing-FREE constant block.

The brass drum is the book's "inner hub" of the 5:1 wheel-and-axle: a plain
ring pressed on the magnifying wheel's spigot, front face flush with the
spigot face. The lever wire wraps it. Its OD is chosen so the wire-centre
ratio is 5: rim wire-centre r 49.2 / drum wire-centre r (9.45 + 0.4) = 4.995.

PURE DATA, no SolidWorks/COM and no drawing imports: the wheel geom, the
lever-wire solver and the magnifier assembly import it.

Part frame: drum axis local Z, mid-plane symmetric about the Front plane.
"""

from __future__ import annotations

DRUM_OD = 18.9
DRUM_BORE = 14.5
DRUM_LEN = 9.0
# Printed bands, (upper, lower) deviations. The bore is H7 on the wheel's p6
# spigot (mg_magnifying_wheel_geom.SPIGOT_BAND): a press fit.
DRUM_OD_BAND = (0.10, -0.10)
DRUM_BORE_BAND = (0.018, 0.0)
DRUM_LEN_BAND = (0.10, -0.10)

LEVER_WIRE_DIA = 0.8  # the lever wire the drum carries (mg_lever_wire_geom)
DRUM_WIRE_R = DRUM_OD / 2.0 + LEVER_WIRE_DIA / 2.0  # 9.85, wire-centre radius

MIN_WALL = 2.0  # drawing-simplicity rule 12 target, at the worst printed band
WALL_WORST = (
    DRUM_OD + DRUM_OD_BAND[1] - (DRUM_BORE + DRUM_BORE_BAND[0])
) / 2.0  # 2.141
if WALL_WORST < MIN_WALL:
    raise AssertionError(f"drum wall {WALL_WORST:.3f} < {MIN_WALL}")
