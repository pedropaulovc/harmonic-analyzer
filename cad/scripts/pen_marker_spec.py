r"""Pure-data dimensional contract shared by the pen marker and drawing."""

from __future__ import annotations

import math
from itertools import pairwise


from _gtol_spec import ConeFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

# Published regular Fine Point product envelope.  Only these two measurements
# are dimensional facts from the reference; the deliberately sparse station
# chain below is a project-authored interpretation of the visible silhouette,
# not copied mesh topology.
OVERALL_LENGTH = 123.11
MAX_DIAMETER = 12.24

# Independently chosen axial stations, measured from the writing point.  The
# felt point and narrow holder grow through a short shoulder into the barrel's
# gentle flare; the last two stations reduce the rear in broad facets that read
# as a rounded/tapered closed end after revolution.
TIP_POINT_Y = 3.0
TIP_POINT_DIAMETER = 1.6
TIP_NECK_Y = 7.0
TIP_NECK_DIAMETER = 3.8
SHOULDER_Y = 15.5
SHOULDER_DIAMETER = 10.9
BARREL_FLARE_Y = 84.0
REAR_TAPER_Y = 108.0
REAR_TAPER_DIAMETER = 10.7
REAR_ROUND_Y = 116.0
REAR_ROUND_DIAMETER = 7.6
BARREL_FLARE_HALF_ANGLE_DEG = math.degrees(
    math.atan(
        ((MAX_DIAMETER - SHOULDER_DIAMETER) / 2.0) / (BARREL_FLARE_Y - SHOULDER_Y)
    )
)

PROFILE_STATIONS: tuple[tuple[float, float], ...] = (
    (0.0, 0.0),
    (TIP_POINT_Y, TIP_POINT_DIAMETER / 2.0),
    (TIP_NECK_Y, TIP_NECK_DIAMETER / 2.0),
    (SHOULDER_Y, SHOULDER_DIAMETER / 2.0),
    (BARREL_FLARE_Y, MAX_DIAMETER / 2.0),
    (REAR_TAPER_Y, REAR_TAPER_DIAMETER / 2.0),
    (REAR_ROUND_Y, REAR_ROUND_DIAMETER / 2.0),
    (OVERALL_LENGTH, 0.0),
)


def marker_radius_mm(axial_y: float) -> float:
    """Return the piecewise-linear profile radius at ``axial_y``."""
    if not 0.0 <= axial_y <= OVERALL_LENGTH:
        raise ValueError(f"marker station {axial_y:g} is outside its envelope")
    for (y0, r0), (y1, r1) in pairwise(PROFILE_STATIONS):
        if axial_y <= y1:
            fraction = (axial_y - y0) / (y1 - y0)
            return r0 + fraction * (r1 - r0)
    raise AssertionError("profile station chain does not reach the overall length")


def revolved_profile_volume_mm3() -> float:
    """Exact volume of the line-segment profile as a sum of conical frusta."""
    return sum(
        math.pi * (y1 - y0) * (r0 * r0 + r0 * r1 + r1 * r1) / 3.0
        for (y0, r0), (y1, r1) in pairwise(PROFILE_STATIONS)
    )


SURFACE_FINISHES = (
    SurfaceFinishControl(
        "barrel",
        MACHINED_UM,
        ConeFace(BARREL_FLARE_HALF_ANGLE_DEG),
    ),
)

# Overall length and maximum diameter are drawing-native picked dimensions.
# Retain one model dimension for the narrow felt-point reach.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "MarkerProfile": {"TipPointY"},
}

DRAWING_NOTES = "\n".join(
    (
        "REFERENCE REGULAR FINE POINT MARKER ENVELOPE: 123.11 LONG X 12.24 MAX DIA.",
        "SIMPLIFIED PROJECT-AUTHORED REVOLVED SILHOUETTE; NO THIRD-PARTY MESH GEOMETRY.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"


GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "marker tip runout": "0.10",
}
