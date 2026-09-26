r"""Pure-data contract for the MHA-016 / MHA-091 dowel pair (#917 S1).

PURE DATA, no SolidWorks/COM imports.  The fit-up process (user ruling via
Main, 2026-09-26) transfers the post's screw pattern into the platform, sets
the post with its screws finger-tight (the tip block sets the T006 end, the
engaged swing the T120 end), tightens, and then match-drills this dowel pair
from under the platform, through the plate and on into the post foot.  The
pins are pressed from underneath and stop below the base-slide face.

A leaf module because both parts need it and ``cone_swing_platform_spec``
already imports ``cone_pivot_post_spec``: the post reading the pattern from
the platform spec would be an import cycle.  The platform spec re-exports the
four names conegear's C2 imports from it.
"""

from __future__ import annotations

from _fit_limits import deviations

MM_PER_IN = 25.4

# MHA-151: McMaster-Carr 98381A304, black-oxide alloy-steel dowel pin,
# 1/8 x 1/2, oversize (+0.0001/+0.0003 in): Ø0.1251-0.1253 in.
POST_DOWEL_PART_NUMBER = "MHA-151"
POST_DOWEL_SKU = "98381A304"
POST_DOWEL_DIA = 0.125 * MM_PER_IN
POST_DOWEL_PIN_DIA_RANGE = (0.1251 * MM_PER_IN, 0.1253 * MM_PER_IN)
POST_DOWEL_LENGTH = 0.5 * MM_PER_IN

# Plate-local (x, z) from the pivot, north then south: on the post's
# crank-axis diameter at the screws' pitch radius (13.444), 90 deg from the
# screws.  build_cone_swing_platform asserts them against the post's station.
POST_DOWEL_PLATE_XZ = ((-2.914, -179.050), (2.914, -205.298))
# Blind depth into the post foot (.X), and how far the pressed pins stop
# short of the base-slide face (nothing may stand proud of it).
POST_DOWEL_BLIND_DEPTH = 8.5
POST_DOWEL_RECESS = 0.25

# Reamed sizes: a press fit in the plate (a 0.0005-undersize dowel reamer),
# a slip fit in the post, so the post lifts off and re-seats.  Both bands are
# the reamers', +.0002/0, written (upper, lower) like every _fit_limits band.
PLATE_DOWEL_REAM_DIA_IN = 0.1245
POST_DOWEL_REAM_DIA_IN = 0.1255
POST_DOWEL_REAM_MAX_IN = 0.1257  # never looser than this
DOWEL_REAM_BAND = (0.0002 * MM_PER_IN, 0.0)
PLATE_DOWEL_REAM_DIA = PLATE_DOWEL_REAM_DIA_IN * MM_PER_IN
POST_DOWEL_REAM_DIA = POST_DOWEL_REAM_DIA_IN * MM_PER_IN
_REAM_LOWER, _REAM_UPPER = deviations(DOWEL_REAM_BAND)
# (minus, plus) magnitudes, as _holes.wizard_holes' dia_tolerance_mm takes them.
DOWEL_REAM_TOLERANCE_MM = (-_REAM_LOWER, _REAM_UPPER)
PLATE_DOWEL_REAM_LIMITS = (
    PLATE_DOWEL_REAM_DIA + _REAM_LOWER,
    PLATE_DOWEL_REAM_DIA + _REAM_UPPER,
)
POST_DOWEL_REAM_LIMITS = (
    POST_DOWEL_REAM_DIA + _REAM_LOWER,
    POST_DOWEL_REAM_DIA + _REAM_UPPER,
)
PLATE_DOWEL_INTERFERENCE = (
    POST_DOWEL_PIN_DIA_RANGE[0] - PLATE_DOWEL_REAM_LIMITS[1],
    POST_DOWEL_PIN_DIA_RANGE[1] - PLATE_DOWEL_REAM_LIMITS[0],
)
POST_DOWEL_CLEARANCE = (
    POST_DOWEL_REAM_LIMITS[0] - POST_DOWEL_PIN_DIA_RANGE[1],
    POST_DOWEL_REAM_LIMITS[1] - POST_DOWEL_PIN_DIA_RANGE[0],
)
if PLATE_DOWEL_INTERFERENCE[0] <= 0.0:
    raise AssertionError("the smallest pin is not pressed in the largest plate ream")
if POST_DOWEL_CLEARANCE[0] < 0.0:
    raise AssertionError("the largest pin does not slip into the smallest post ream")
if POST_DOWEL_REAM_LIMITS[1] > POST_DOWEL_REAM_MAX_IN * MM_PER_IN + 1e-9:
    raise AssertionError("the post ream can open past .1257 in")


def _inch(value_in: float) -> str:
    return f"{value_in:.4f}".lstrip("0")


# Native Hole Wizard callout prefixes: the matched-fit instruction naming the
# mating part, then the reamer (the print is metric; the reamer is bought by
# its inch size).  The reamed size, its band and the depth stay native.
PLATE_DOWEL_CALLOUT = (
    f"MATCH-DRILL/REAM WITH\nMHA-016 AT ASSEMBLY;\nREAM ({_inch(PLATE_DOWEL_REAM_DIA_IN)} IN)"
)
POST_DOWEL_CALLOUT = (
    f"MATCH-DRILL/REAM WITH\nMHA-091 AT ASSEMBLY;\n"
    f"REAM ({_inch(POST_DOWEL_REAM_DIA_IN)} IN) FROM FOOT"
)
