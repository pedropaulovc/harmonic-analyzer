r"""MHA-175 latch-hook-rivet: McMaster 97482A010 stock solid rivet.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Two 1/16 x 1/8 domed-head solid rivets join the latch hook's
(MHA-127) strip to the latch-hook bracket's (MHA-170) flap; the flap's holes
are drilled at assembly through the hook's (ruling R9-15).

Catalogue (mcmaster.com, read live 2026-09-30; dt-logs
transgear-evidence/mcmaster-skus.md "Round 10 - hook rivets"): Aluminum
Domed Head Solid Rivet, 1100 aluminum, 1/16 in diameter, 0.125 in long
under the head, round domed head Ø0.13 x 0.051 in high, for material up to
0.094 in thick and a 0.067 in (#51 drill) hole.  No vendor model was supplied
or harvested, so the part is catalogue-only.

[INFERENCE: the page states no head radius] The dome is modelled as the
spherical cap through the head's rim and its apex.

Part frame: rivet axis local +Y; the head's flat bearing face at y = 0 (the
Top Plane), the shank running -Y to y = -LENGTH, the dome +Y to y = HEAD_H.
The Front and Right Planes contain the axis, published as ``ScrewAxis``.
"""

from __future__ import annotations

import math

import latch_hook_bracket_geometry as bracket
import latch_hook_bracket_spec as bracket_spec
import latch_hook_geometry as hook
import latch_hook_spec as hook_spec

MM_PER_IN = 25.4

SKU = "97482A010"
DIA = MM_PER_IN / 16.0  # 1.5875
LENGTH = 0.125 * MM_PER_IN  # 3.175, under the head
HEAD_DIA = 0.13 * MM_PER_IN  # 3.302
HEAD_H = 0.051 * MM_PER_IN  # 1.2954
MAX_GRIP = 0.094 * MM_PER_IN  # 2.3876, the vendor's max material thickness
VENDOR_HOLE_DIA = 0.067 * MM_PER_IN  # 1.7018, #51 drill

# [INFERENCE] The dome: a spherical cap of height HEAD_H on the Ø HEAD_DIA
# rim, R = (a^2 + h^2) / 2h = (1.651^2 + 1.2954^2) / 2.5908 = 1.6998.
DOME_R = ((HEAD_DIA / 2.0) ** 2 + HEAD_H**2) / (2.0 * HEAD_H)
DOME_CENTRE_Y = HEAD_H - DOME_R  # -0.4044, on the axis under the bearing face


def rivet_volume() -> float:
    """The modelled solid, mm^3: shank cylinder plus the spherical cap."""
    shank = math.pi * (DIA / 2.0) ** 2 * LENGTH
    cap = math.pi * HEAD_H**2 * (3.0 * DOME_R - HEAD_H) / 3.0
    return shank + cap


# The joint: the hook strip on the bracket flap.  The strip is taken as
# supplied (its sheet carries no band); the flap at its thickest stock.
GRIP_NOMINAL = hook.STRIP_T + bracket.SHEET_T  # 2.1
GRIP_WORST = hook.STRIP_T + bracket.SHEET_T + bracket.SHEET_T_PLUS  # 2.2
if GRIP_WORST > MAX_GRIP:
    raise AssertionError(
        f"rivet grip {GRIP_WORST:.4f} exceeds the vendor's {MAX_GRIP:.4f} max"
    )

if hook.RIVET_HOLE_DIA != bracket.RIVET_HOLE_DIA:
    raise AssertionError(
        f"hook rivet hole Ø{hook.RIVET_HOLE_DIA} != bracket's"
        f" Ø{bracket.RIVET_HOLE_DIA}; one match-drilled hole"
    )
# The smallest and largest printed rivet hole across both parts.
HOLE_MIN = hook.RIVET_HOLE_DIA + max(
    min(hook_spec.HOLE_BAND), min(bracket_spec.HOLE_BAND)
)
HOLE_MAX = hook.RIVET_HOLE_DIA + min(
    max(hook_spec.HOLE_BAND), max(bracket_spec.HOLE_BAND)
)
if not DIA < HOLE_MIN:
    raise AssertionError(f"rivet Ø{DIA:.4f} does not enter a Ø{HOLE_MIN:.4f} hole")

# Recorded, not enforced: the vendor's #51 hole (1.7018) sits 0.0018 over the
# top of the printed Ø1.6 +0.10/0 band.
VENDOR_HOLE_OVER_BAND = VENDOR_HOLE_DIA - HOLE_MAX
