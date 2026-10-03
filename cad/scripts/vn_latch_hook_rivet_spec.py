r"""MHA-VN-045 latch-hook-rivet: McMaster 97482A015 stock solid rivet.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Two 1/16 x 3/16 domed-head solid rivets join the latch hook's
(MHA-PD-014) strip to the latch-hook bracket's (MHA-PD-021) flap; the flap's holes
are drilled at assembly through the hook's (ruling R9-15).

Catalogue (mcmaster.com, read live 2026-09-30; dt-logs
transgear-evidence/mcmaster-skus.md "Round 10 - hook rivets"): Aluminum
Domed Head Solid Rivet, 1100 aluminum, 1/16 in diameter; 97482A015 is the
0.188 in length under the head, for material up to 0.157 in thick.  The
family's 97482A010 row (read live) gives the round domed head Ø0.13 x 0.051
in high and a 0.067 in (#51 drill) hole; [INFERENCE] 97482A015 shares them
(one head per diameter in the family; its own row not yet read live).  No
vendor model was supplied or harvested, so the part is catalogue-only.

R9-51: the 1/8 length (97482A010) in Ø1.6 holes could neither clear the
largest shank at the least hole nor form a full shop head at the largest
hole; the 3/16 length in a Ø1.65 hole does both (below).

[INFERENCE: the page states no head radius] The dome is modelled as the
spherical cap through the head's rim and its apex.

Part frame: rivet axis local +Y; the head's flat bearing face at y = 0 (the
Top Plane), the shank running -Y to y = -LENGTH, the dome +Y to y = HEAD_H.
The Front and Right Planes contain the axis, published as ``ScrewAxis``.
"""

from __future__ import annotations

import math

import pd_latch_hook_bracket_geometry as bracket
import pd_latch_hook_bracket_spec as bracket_spec
import pd_latch_hook_geometry as hook
import pd_latch_hook_spec as hook_spec

MM_PER_IN = 25.4

SKU = "97482A015"
DIA = MM_PER_IN / 16.0  # 1.5875
LENGTH = 3.0 * MM_PER_IN / 16.0  # 4.7625 under the head (listed 0.188 in)
HEAD_DIA = 0.13 * MM_PER_IN  # 3.302
HEAD_H = 0.051 * MM_PER_IN  # 1.2954
MAX_GRIP = 0.157 * MM_PER_IN  # 3.9878, the vendor's max material thickness
VENDOR_HOLE_DIA = 0.067 * MM_PER_IN  # 1.7018, #51 drill
# ASME B18.1.1 1/16 solid rivet: shank Ø0.064 / 0.059 in (max / min), length
# +/-0.016 in (https://itpbolt.com/wp-content/uploads/2015/08/Button-Head-Solid-Rivets.pdf,
# https://www.njrivet.com/products/solid/).
SHANK_DIA_MAX = 0.064 * MM_PER_IN  # 1.6256
SHANK_DIA_MIN = 0.059 * MM_PER_IN  # 1.4986
LENGTH_TOL = 0.016 * MM_PER_IN  # 0.4064
# MIL-R-47196A Table III, the driven (shop) head of a 1/16 rivet: Ø0.081 in
# min, 0.025 in thick min
# (https://www.vansaircraft.com/wp-content/uploads/2019/02/MIL-R-47196A_MI.pdf).
SHOP_HEAD_DIA_MIN = 0.081 * MM_PER_IN  # 2.0574
SHOP_HEAD_T_MIN = 0.025 * MM_PER_IN  # 0.635

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

# --- R9-51: MHA-VN-045 rivet in the MHA-PD-014 / MHA-PD-021 holes, at the worst case --
# The largest hole either part may drill, judged with the vendor's #51 drill.
HOLE_LARGEST = max(
    hook.RIVET_HOLE_DIA + max(max(hook_spec.HOLE_BAND), max(bracket_spec.HOLE_BAND)),
    VENDOR_HOLE_DIA,
)
# The largest B18.1.1 shank enters the least hole: Ø1.65 - 1.6256 = +0.024.
SHANK_CLEARANCE_MIN = HOLE_MIN - SHANK_DIA_MAX
if SHANK_CLEARANCE_MIN <= 0.0:
    raise AssertionError(
        f"MHA-VN-045 rivet / MHA-PD-014 + MHA-PD-021 holes: the largest shank Ø"
        f"{SHANK_DIA_MAX:.4f} binds in the least Ø{HOLE_MIN:.4f} hole"
        f" ({SHANK_CLEARANCE_MIN:+.4f})"
    )


def shop_head_volume(hole: float, shank: float, length: float, grip: float) -> float:
    """The shank volume left past the joint to form the shop head, mm^3, once
    the upset shank has filled the hole's clearance over the grip."""
    area = math.pi / 4.0
    return area * shank**2 * (length - grip) - area * (hole**2 - shank**2) * grip


# The least shop head: the shortest, thinnest rivet in the largest hole over
# the thickest grip, against MIL-R-47196A's least head.
SHOP_HEAD_VOLUME_MIN = math.pi / 4.0 * SHOP_HEAD_DIA_MIN**2 * SHOP_HEAD_T_MIN  # 2.111
SHOP_HEAD_VOLUME_WORST = shop_head_volume(
    HOLE_LARGEST, SHANK_DIA_MIN, LENGTH - LENGTH_TOL, GRIP_WORST
)  # 2.392
if SHOP_HEAD_VOLUME_WORST < SHOP_HEAD_VOLUME_MIN:
    raise AssertionError(
        f"MHA-VN-045 rivet / MHA-PD-014 + MHA-PD-021 holes: {SHOP_HEAD_VOLUME_WORST:.3f}"
        f" mm^3 left for the shop head at the worst case, under MIL-R-47196A's"
        f" {SHOP_HEAD_VOLUME_MIN:.3f}"
    )

# What either end of the rivet may fill in the flap plane (the guide-lock
# sweep in build_pd_paper_drive_assembly checks it, unbounded in x): the set
# dome, the shank's tail (modelled undriven, LENGTH - GRIP_NOMINAL = 2.66 past
# the flap's outer face, TAIL_PROUD_MAX at the longest rivet in the thinnest
# grip), or the shop head.  Its widest is the most shank the joint leaves --
# the longest, fattest rivet in the least hole over the thinnest grip --
# flattened to MIL-R-47196A's least head thickness.
GRIP_LEAST = hook.STRIP_T + bracket.SHEET_T - bracket.SHEET_T_MINUS  # 2.0
TAIL_PROUD_MAX = LENGTH + LENGTH_TOL - GRIP_LEAST  # 3.169
SHOP_HEAD_VOLUME_MAX = shop_head_volume(
    HOLE_MIN, SHANK_DIA_MAX, LENGTH + LENGTH_TOL, GRIP_LEAST
)  # 6.451
SHOP_HEAD_DIA_BOUND = math.sqrt(
    4.0 * SHOP_HEAD_VOLUME_MAX / (math.pi * SHOP_HEAD_T_MIN)
)  # 3.597
ENVELOPE_DIA = max(HEAD_DIA, SHANK_DIA_MAX, SHOP_HEAD_DIA_BOUND)

# Recorded, not enforced: the vendor's #51 hole (1.7018) against the top of
# the printed Ø1.65 +0.10/0 band (negative: inside it).
VENDOR_HOLE_OVER_BAND = VENDOR_HOLE_DIA - HOLE_MAX
