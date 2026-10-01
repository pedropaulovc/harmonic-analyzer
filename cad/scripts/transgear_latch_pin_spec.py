r"""MHA-169 transgear-latch-pin: McMaster 98381A473 stock dowel.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  One 1/8 x 3/4 alloy-steel dowel, Round x Chamfer ends, pressed
chamfer end first to the flat floor of a blind hole in the transgear arm's
square end face, along the arm's centreline (contract round 9 section 4.1,
user ruling 7, ruling R9-12).  It stands PROUD out of that face; its proud
length passes through the latch hook's (MHA-127) Ø5.4 hole, which holds the
swung arm until the strip is flexed off it.

Catalogue: 1/8 x 3/4 alloy-steel dowel, Round x Chamfer ends; the size row
and the family's diameter band are ``diagnostics.diag_mcmaster_dowel``'s.
The end forms are the vendor model's (harvested 2026-09-30): the chamfered
end a flat Ø2.921 face and a cone 16 deg to the axis, 0.443 long; the round
end an R0.406 tangent to the diameter down to a flat Ø2.362 face.

Part frame: axis local +Y through the origin; the pressed (chamfered) end
face at y = 0, the rounded lead end at y = LENGTH.  The Front and Right
Planes contain the axis, published as ``ScrewAxis`` (Front x Right); the Top
Plane is the pressed end face, so an assembly places the pin by that plane
at PRESS_DEPTH inside the arm's end face.
"""

from __future__ import annotations

from diagnostics.diag_mcmaster_dowel import (
    DIA_BAND_IN,
    DOWEL_ENDS,
    DOWEL_SIZES,
    MM_PER_IN,
)

SKU = "98381A473"
DIA, LENGTH = DOWEL_SIZES[SKU]  # 3.175 x 19.05
# Catalogue diameter band over nominal, mm, as (upper, lower) deviations:
# +0.00762 / +0.00254 (the catalogue row lists it low-first).
DIA_BAND = tuple(band * MM_PER_IN for band in reversed(DIA_BAND_IN))
DIA_MAX = DIA + max(DIA_BAND)
ENDS = DOWEL_ENDS[SKU]
# The pressed end's chamfer: the length of it that grips nothing.
CHAMFER_LEN = ENDS.chamfer_len(DIA)  # 0.443
# The lead end's round: where the full diameter stops short of the tip.
CROWN_R = ENDS.crown_r  # 0.406

# The pin is pressed to the floor of the arm's blind hole (R9-12, the
# MHA-026 / MHA-173 precedent), so the hole's depth sets its installed length
# out of the arm's end face (contract 4.1): through the strip plane with the
# lead end clear past it.
PROUD = 13.0
# The pressed end on the hole floor: the length the press fit grips, and the
# arm's nominal hole depth.
PRESS_DEPTH = LENGTH - PROUD  # 6.05
# A press-fit dowel grips at least 1.5 D (the rule-12 engagement floor,
# applied to the press as the contract does), counted over the full
# diameter only: the chamfer inside the hole carries no interference.
PRESS_ENGAGEMENT_MIN_D = 1.5


def proud_length(hole_depth: float) -> float:
    """The pin's length out of the arm's end face when it is pressed to the
    floor of a blind hole ``hole_depth`` deep.  The arm owns the depth and its
    band; the hanger joints call this at both ends of it."""
    return LENGTH - hole_depth


def press_engagement_d(hole_depth: float) -> float:
    """Full-diameter press engagement, in D, of the pin bottomed in a blind
    hole ``hole_depth`` deep."""
    return (hole_depth - CHAMFER_LEN) / DIA


# (6.05 - 0.443) / 3.175 = 1.77 D at the nominal depth.
PRESS_ENGAGEMENT_D = press_engagement_d(PRESS_DEPTH)
if PRESS_ENGAGEMENT_D < PRESS_ENGAGEMENT_MIN_D:
    raise AssertionError(
        f"latch pin grips {PRESS_ENGAGEMENT_D:.2f} D in the arm, under"
        f" {PRESS_ENGAGEMENT_MIN_D} D"
    )
