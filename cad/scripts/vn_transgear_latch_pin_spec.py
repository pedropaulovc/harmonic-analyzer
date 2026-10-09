r"""MHA-VN-042 transgear-latch-pin: McMaster 98381A474 stock dowel.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  One 1/8 x 7/8 alloy-steel dowel, Round x Chamfer ends, pressed
chamfer end first to the flat floor of a blind hole in the transgear arm's
square end face, along the arm's centreline (contract round 9 section 4.1,
user ruling 7, ruling R9-12).  It stands PROUD out of that face; its proud
length passes through the latch hook's (MHA-PD-014) Ø5.4 hole, which holds the
swung arm until the strip is flexed off it.

R9-50: the 3/4 length (98381A473) left the pin's full diameter short of the
hook's far face at the worst case once the MHA-PD-014 ear's 1 deg bend and the
dowel's length grade are counted; the 7/8 length of the same series, in a
deeper hole, passes it (``transgear_hanger_joints``).

Catalogue: this pure module owns the shared dowel size table, the 98381A*
diameter band and end forms; stock pin specs and native recipes consume them.
Catalogue provenance: each size's McMaster product page, read live 2026-09-30
(dt-logs transgear-evidence/mcmaster-skus.md R6): alloy steel, unplated,
diameter +0.0001 to +0.0003 in over nominal, "Round x Chamfer" ends.
The 98381A433/434 pages state neither end radius nor chamfer and have no
vendor model, so their reference geometry remains a plain nominal cylinder.
[INFERENCE] The SKU is the 7/8 length of the 1/8 series, not yet read live,
and its end forms are the 98381A473 vendor model's (harvested 2026-09-30):
the chamfered end a flat Ø2.921 face and a cone 16 deg to the axis, 0.443
long; the round end an R0.406 tangent to the diameter down to a flat Ø2.362
face.  Vendor check pending.

Part frame: axis local +Y through the origin; the pressed (chamfered) end
face at y = 0, the rounded lead end at y = LENGTH.  The Front and Right
Planes contain the axis, published as ``ScrewAxis`` (Front x Right); the Top
Plane is the pressed end face, so an assembly places the pin by that plane
at PRESS_DEPTH inside the arm's end face.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


MM_PER_IN = 25.4

DOWEL_SIZES = {
    # part:        (nominal dia, length), mm
    "98381A433": (3.0 / 32.0 * MM_PER_IN, 3.0 / 16.0 * MM_PER_IN),  # 3/32 x 3/16
    "98381A434": (3.0 / 32.0 * MM_PER_IN, 0.25 * MM_PER_IN),  # 3/32 x 1/4
    "98381A473": (0.125 * MM_PER_IN, 0.75 * MM_PER_IN),  # 1/8 x 3/4
    "98381A474": (0.125 * MM_PER_IN, 0.875 * MM_PER_IN),  # 1/8 x 7/8 [INFERENCE]
    # 316 stainless nominal reference only; its m6/incoming limits live in its spec.
    "93600A189": (2.0, 6.0),
}
# Catalogue diameter tolerance for the 98381A* alloy series only, in inches.
DIA_BAND_IN = (0.0001, 0.0003)


@dataclass(frozen=True)
class DowelEnds:
    """A vendor-modelled Round x Chamfer pair of end forms, mm and degrees."""

    point_dia: float  # the chamfered end's flat face
    chamfer_deg: float  # the chamfer cone's angle to the pin axis
    crown_r: float  # the round end's radius, tangent to the diameter

    def chamfer_len(self, dia: float) -> float:
        """Axial length of the chamfer cone on a pin of ``dia``."""
        return (dia - self.point_dia) / 2.0 / math.tan(math.radians(self.chamfer_deg))


# Read off the 98381A473 harvest (Sketch2 "Point Diameter" 2.921, D3 16 deg,
# "Crown Radius" 0.4064; Revolve1 faces: cone x -9.525..-9.0821, torus
# x 9.1186..9.525, end faces Ø2.921 and Ø2.3622).
_ROUND_X_CHAMFER_1_8 = DowelEnds(
    point_dia=0.115 * MM_PER_IN, chamfer_deg=16.0, crown_r=0.016 * MM_PER_IN
)
DOWEL_ENDS = {
    "98381A473": _ROUND_X_CHAMFER_1_8,
    # [INFERENCE] the 1/8 series' end forms, read off the 98381A473 harvest.
    "98381A474": _ROUND_X_CHAMFER_1_8,
}


def dowel_volume(part_no: str) -> float:
    """The recipe's solid volume, mm^3: the nominal cylinder less the chamfer
    ring and the round end's corner ring (Pappus, each about the pin axis)."""
    dia, length = DOWEL_SIZES[part_no]
    radius = dia / 2.0
    volume = math.pi * radius**2 * length
    ends = DOWEL_ENDS.get(part_no)
    if ends is None:
        return volume
    step = radius - ends.point_dia / 2.0
    chamfer_area = 0.5 * step * ends.chamfer_len(dia)
    volume -= 2.0 * math.pi * (radius - step / 3.0) * chamfer_area
    r = ends.crown_r
    corner_area = (1.0 - math.pi / 4.0) * r**2
    corner_centroid = radius - r + (r / 6.0) / (1.0 - math.pi / 4.0)
    volume -= 2.0 * math.pi * corner_centroid * corner_area
    return volume


def dowel_section(part_no: str) -> list[tuple[float, float]]:
    """The half-section's corners (radius, y), mm: from the round end's flat
    face rim round the axis and the chamfered end to the round end's tangent
    point.  The round end's arc closes it from the last point to the first."""
    dia, length = DOWEL_SIZES[part_no]
    radius = dia / 2.0
    ends = DOWEL_ENDS[part_no]
    r = ends.crown_r
    return [
        (radius - r, length),
        (0.0, length),
        (0.0, 0.0),
        (ends.point_dia / 2.0, 0.0),
        (radius, ends.chamfer_len(dia)),
        (radius, length - r),
    ]


SKU = "98381A474"
DIA, LENGTH = DOWEL_SIZES[SKU]  # 3.175 x 22.225
# Catalogue diameter band over nominal, mm, as (upper, lower) deviations:
# +0.00762 / +0.00254 (the catalogue row lists it low-first).
DIA_BAND = tuple(band * MM_PER_IN for band in reversed(DIA_BAND_IN))
DIA_MAX = DIA + max(DIA_BAND)
ENDS = DOWEL_ENDS[SKU]
# The pressed end's chamfer: the length of it that grips nothing.
CHAMFER_LEN = ENDS.chamfer_len(DIA)  # 0.443
# The lead end's round: where the full diameter stops short of the tip.
CROWN_R = ENDS.crown_r  # 0.406
# The family's length grade, +/-0.010 in (``dt_crankshaft_spec``'s
# DRIVE_PIN_LENGTH_GRADE for the same 98381A family): it moves the pressed
# pin's lead end by as much.
LENGTH_GRADE = 0.010 * MM_PER_IN  # 0.254

# The pin is pressed to the floor of the arm's blind hole (R9-12, the
# MHA-DT-011 / MHA-VN-044 precedent), so the hole's depth sets its installed length
# out of the arm's end face (contract 4.1): through the strip plane with the
# lead end clear past it.
PROUD = 13.725
# The pressed end on the hole floor: the length the press fit grips, and the
# arm's nominal hole depth.
PRESS_DEPTH = LENGTH - PROUD  # 8.50
# A press-fit dowel grips at least 1.5 D (the rule-12 engagement floor,
# applied to the press as the contract does), counted over the full
# diameter only: the chamfer inside the hole carries no interference.
PRESS_ENGAGEMENT_MIN_D = 1.5


def proud_length(hole_depth: float, length_dev: float = 0.0) -> float:
    """The pin's length out of the arm's end face when it is pressed to the
    floor of a blind hole ``hole_depth`` deep, the pin ``length_dev`` off its
    nominal length.  The arm owns the depth and its band; the hanger joints
    call this at both ends of it and of LENGTH_GRADE."""
    return LENGTH + length_dev - hole_depth


def press_engagement_d(hole_depth: float) -> float:
    """Full-diameter press engagement, in D, of the pin bottomed in a blind
    hole ``hole_depth`` deep."""
    return (hole_depth - CHAMFER_LEN) / DIA


# (8.50 - 0.443) / 3.175 = 2.54 D at the nominal depth.
PRESS_ENGAGEMENT_D = press_engagement_d(PRESS_DEPTH)
if PRESS_ENGAGEMENT_D < PRESS_ENGAGEMENT_MIN_D:
    raise AssertionError(
        f"latch pin grips {PRESS_ENGAGEMENT_D:.2f} D in the arm, under"
        f" {PRESS_ENGAGEMENT_MIN_D} D"
    )
