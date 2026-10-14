r"""Wheel drum (MHA-MG-010) nominal geometry -- the drawing-FREE constant block.

The brass drum is the book's "inner hub" of the 5:1 wheel-and-axle: a plain
ring pressed on the magnifying wheel's spigot up to the boss, its front face
never proud of the spigot face. The lever wire wraps it. Its OD is chosen so
the wire-centre ratio is about 5: rim wire-centre r 48.825 / drum wire-centre r
(9.525 + 0.4064) = 4.916 (all-inch experiment; was 49.2 / 9.85 = 4.995).

PURE DATA, no SolidWorks/COM and no drawing imports: the wheel geom, the
lever-wire solver and the magnifier assembly import it.

Part frame: drum axis local Z, mid-plane symmetric about the Front plane.
"""

from __future__ import annotations

from _inch import inch
from _printed_tolerance import printed_band_mm

DRUM_OD = inch(3, 4)  # was 18.9
# Ø14.0, not the first Ø14.5: the Ø14.5 bore left the wall under 2.0 at the
# worst corner (Main, Q1-A, 2026-10-12). All-inch: 17/32 (1/32 step), as the
# nearest 9/16 left the worst-band wall 1.97 < 2.0 under the 3/4 O.D.
DRUM_BORE = inch(17, 32)
DRUM_LEN = inch(3, 8)  # was 9.0
# Printed bands, (upper, lower) deviations. The bore is H7, made first: the
# wheel's spigot is turned to the stated interference in it (DRUM_PRESS in
# mg_magnifying_wheel_geom). The length is minus-only against the spigot's
# plus-only length (DRUM_RECESS there). The O.D. carries no band of its own:
# the wire wraps it, so it takes the title block's .X row, which moves the
# wire-centre radius by 0.8 / 2 in 9.85 (4 %); the wall below is the bound.
DRUM_OD_PLACES = 1
DRUM_BORE_BAND = (0.018, 0.0)
DRUM_LEN_BAND = (0.0, -0.10)

LEVER_WIRE_DIA = inch(0.032)  # .032 music wire (was 0.8; mg_lever_wire_geom)
DRUM_WIRE_R = DRUM_OD / 2.0 + LEVER_WIRE_DIA / 2.0  # 9.9314, wire-centre radius

MIN_WALL = 2.0  # drawing-guidelines.md rule 17 (walls and webs) target, at the worst printed band
WALL_WORST = (
    DRUM_OD - printed_band_mm(DRUM_OD_PLACES) - (DRUM_BORE + DRUM_BORE_BAND[0])
) / 2.0  # 2.369: (18.25 - 13.512) / 2
if WALL_WORST < MIN_WALL:
    raise AssertionError(f"drum wall {WALL_WORST:.3f} < {MIN_WALL}")
