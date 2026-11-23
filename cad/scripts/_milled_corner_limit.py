r"""The local inside-corner limit the 1/8 in end mill leaves, and the section
area such a corner adds.

Owner ruling 2026-11-23, tool audit Q9 (C:/farm-runs/triage-2026-11-19/cnc/
rulings.md): "Print a local corner limit R.065 (.060-.070), cut with the 1/8
end mill; no 5/64 cutter", on the inside corners a 5/64 in end mill recut
from the 1/8 in cutter's R.0625 to the title block's INSIDE CORNERS R.040
MAX: MHA-CH-02's two bar-to-hub roots, MHA-CH-03's four shank corners (the
flanks onto the ring and onto the fork's step), MHA-PN-01's four window
corners and MHA-PN-05's two relief-slot corners at the step.  Nothing seats
in any of them.  Every other inside corner keeps the title block's limit.

The radius prints at three places, so the title block's .XXX band is its
.060-.070 limit; the callout names why the corner may stand over R.040.
Imported only by those four parts' own modules, so a change here re-keys
those parts, their sheets and the assemblies that place them.
"""

from __future__ import annotations

import math

from _printed_tolerance import printed_band_mm

CORNER_R = 1.651  # .065
CORNER_PLACES = 3  # the title block's .XXX: R.060-.070
CORNER_REASON = "NOTHING SEATS IN\nTHESE CORNERS"


def corner_r_limits(*, unit: str) -> tuple[float, float]:
    """The printed corner radius's (least, greatest), in mm."""
    band = printed_band_mm(CORNER_PLACES, unit=unit)
    return CORNER_R - band, CORNER_R + band


def corner_prefix(count: int) -> str:
    """The radius dimension's native prefix: the count, then the R."""
    return f"{count}X R"


def line_circle_fillet_area(radius: float, circle_r: float, offset: float) -> float:
    """Section area a fillet of ``radius`` adds in the inside corner where a
    straight edge ``offset`` from a round boss's centre (the metal on the
    centre's side of it) runs into the boss of radius ``circle_r``.

    The fillet circle touches the edge and the boss outside it: its centre
    stands ``radius`` off the edge and ``circle_r + radius`` from the boss's
    centre.  The area is the quadrilateral corner, tangent point, fillet
    centre, boss tangent point, less the fillet's sector and the boss's
    segment over the chord from its tangent point to the corner."""
    if not 0.0 < offset < circle_r:
        raise ValueError("the edge must cut the boss")
    corner = (math.sqrt(circle_r**2 - offset**2), offset)
    reach = circle_r + radius
    centre = (math.sqrt(reach**2 - (offset + radius) ** 2), offset + radius)
    on_edge = (centre[0], offset)
    on_boss = (centre[0] * circle_r / reach, centre[1] * circle_r / reach)
    loop = (corner, on_edge, centre, on_boss)
    quad = 0.5 * abs(
        sum(
            a[0] * b[1] - b[0] * a[1]
            for a, b in zip(loop, loop[1:] + loop[:1])
        )
    )
    sector = 0.5 * radius**2 * math.acos((offset + radius) / reach)
    theta = math.atan2(centre[1], centre[0]) - math.atan2(corner[1], corner[0])
    segment = 0.5 * circle_r**2 * (theta - math.sin(theta))
    return quad - sector - segment


def runout_fillet_area(radius: float, step: float) -> float:
    """Section area a cutter of ``radius`` leaves in the inside corner where
    a flank meets a step only ``step`` wide (``step`` < ``radius``) before
    the next flank, parallel to the first, rises: the cutter touches the
    first flank and passes through the step's outer corner, so its arc runs
    from the flank straight onto that corner and no step face is left.  The
    area is the triangle tangent point, inside corner, outer corner, less
    the cutter's segment over the chord from its tangent point to the outer
    corner."""
    if not 0.0 < step < radius:
        raise ValueError("a step as wide as the radius seats a full fillet")
    rise = math.sqrt(radius**2 - (radius - step) ** 2)
    phi = math.acos((radius - step) / radius)
    return 0.5 * rise * step - 0.5 * radius**2 * (phi - math.sin(phi))


def runout_rise(radius: float, step: float) -> float:
    """How far below the step the cutter's arc leaves the first flank."""
    return math.sqrt(radius**2 - (radius - step) ** 2)
