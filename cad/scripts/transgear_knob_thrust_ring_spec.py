r"""MHA-156 transgear-knob-thrust-ring: the loose brass ring in front of the plate hub.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  The ring rides the knob shaft's (MHA-078) Ø8.5 journal between the
12T's rear face and the arm plate's front hub face (contract §1.7, round 6
K5: the journal runs straight in the steel plate, no bushing).  It is loose:
located by the journal, it rotates with the shaft or not.  Its length is the
FORWARD stop of the knob's end-float pair (the cup behind the rear boss is
the other), so it carries an explicit band; it is not a fit-up shim.

The O.D. stands a little proud of the plate's front hub radially (book p.59:
a brass ring slightly larger than the silver hub).

Part frame: axis local +Y through the origin (``Axis1``); the front face
(on the 12T) is the Top Plane, y = 0; the rear face (on the plate hub's front
face) is y = LENGTH.
"""

from __future__ import annotations

from _gtol_spec import PlanarFace
from _printed_tolerance import printed_deviations
from _surface_finish import MACHINED_UM, SurfaceFinishControl

OD = 13.6
ID = 8.6
# Clears the journal; drilled, never under size (drilled-hole class).
ID_BAND = (0.10, 0.0)  # (upper, lower) deviations
LENGTH = 5.2
# The forward stop of the knob's end float (contract §12): explicit ± band.
LENGTH_TOL = 0.05

# Places each printed dimension carries (policy rule 12): the O.D. at .XX
# holds the wall below; the bore prints at .XX under its own band; the length
# at .XXX under its explicit band.
OD_PLACES = 2
ID_PLACES = 2
LENGTH_PLACES = 3

WALL_FLOOR = 2.0


def worst_wall(od_places: int = OD_PLACES) -> float:
    """Radial wall at the smallest printed O.D. over the largest bore."""
    od_lower, _ = printed_deviations(OD, od_places)
    return ((OD + od_lower) - (ID + max(ID_BAND))) / 2.0


WALL_NOMINAL = (OD - ID) / 2.0
WALL_WORST = worst_wall()
if WALL_WORST < WALL_FLOOR - 1e-9:
    raise AssertionError(
        f"MHA-156 wall {WALL_WORST:.3f} at the printed worst case is under "
        f"the {WALL_FLOOR} floor"
    )

# The sheet: the bore's process under its size.
BORE_CALLOUT = "DRILL THRU"

# Both faces are thrust faces (12T in front, plate hub behind): MACHINED, on
# the exact native faces the part build resolves.
SURFACE_FINISHES = (
    SurfaceFinishControl("front_face", MACHINED_UM, PlanarFace((0.0, -1.0, 0.0), 0.0)),
    SurfaceFinishControl("rear_face", MACHINED_UM, PlanarFace((0.0, 1.0, 0.0), LENGTH)),
)

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity policy rule 2).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {"RingOd", "BoreDia"},
    "Ring": {"RingLength"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RingProfile": {"RingOd": OD_PLACES, "BoreDia": ID_PLACES},
    "Ring": {"RingLength": LENGTH_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
