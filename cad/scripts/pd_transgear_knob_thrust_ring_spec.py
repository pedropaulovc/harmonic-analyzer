r"""MHA-PD-15 transgear-knob-thrust-ring: the loose brass ring in front of the plate hub.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  The ring rides the knob shaft's (MHA-PD-08) Ø.249 journal between the
pinion's rear face and the arm plate's front hub face (contract §1.7, round 6
K5: the journal runs straight in the steel plate, no bushing).  It is loose:
located by the journal, it rotates with the shaft or not.  Its length is the
FORWARD stop of the knob's end-float pair (the cup behind the rear boss is
the other), so it carries an explicit band; it is not a fit-up shim.

The O.D. stands a little proud of the plate's front hub radially (book p.59:
a brass ring slightly larger than the silver hub).

Part frame: axis local +Y through the origin (``Axis1``); the front face
(on the pinion) is the Top Plane, y = 0; the rear face (on the plate hub's front
face) is y = LENGTH.
"""

from __future__ import annotations

import _config
from _gtol_planar import PlanarFace
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import drilled_oversize_mm, printed_deviations
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from pd_cluster_stack_band import FIT_LENGTH_BAND_IN, STACK_NAME

# #290: the sheet prints decimal inch; nominals are the exact millimetres of
# their printed inch values.
UNIT = drawing_unit(
    "parts/pd-transgear-knob-thrust-ring", _config.parts("pd-transgear-knob-thrust-ring")
)

OD = 13.716  # .54
# .257, a letter F drill (#290 fit F9): the .249 journal forced it up from
# 6.05, and the charged rear tooth-end bearing stays above 1.0 mm^2.
ID = 6.5278  # .257
# Clears the journal; drilled, never under size.  The DRILL THRU callout
# inherits this band from the title block's DRILLED HOLES row, so the model
# dimension carries no band of its own (machinist review: a restated row is
# over-specification).
ID_BAND = (drilled_oversize_mm(unit=UNIT), 0.0)  # (upper, lower) deviations
LENGTH = 5.207  # .205
# The forward stop of the knob's end float (contract §12): explicit ± band.
# It spaces the knob shaft's pinion (MHA-PD-08) from the arm plate's front hub
# (MHA-PD-19), so the knob's F datum, chain plane and disc/platen gap stacks
# (paper_drive_arm_registration, the paper-drive assembly) consume it; the
# sheet names that stack at the callout (drawing-guidelines rule 4).  F is
# the disc cluster's printed stack's reference too (transgear_cluster_fit),
# so the band is the cluster's +/-.001 (#2124).
LENGTH_TOL = FIT_LENGTH_BAND_IN

# Places each printed dimension carries (drawing-guidelines.md rule 3 (decimal places carry the tolerance)): the O.D. is routine
# at .XX (the wall below holds at that row, and nothing fits on the O.D.); the
# bore prints its drill size at .XXX under the DRILLED HOLES row; the length
# at .XXX under its explicit band.
OD_PLACES = 2
ID_PLACES = 3
LENGTH_PLACES = 3

WALL_FLOOR = WALL_TARGET_MM


def worst_wall(od_places: int = OD_PLACES) -> float:
    """Radial wall at the smallest printed O.D. over the largest bore."""
    od_lower, _ = printed_deviations(OD, od_places, unit=UNIT)
    return ((OD + od_lower) - (ID + max(ID_BAND))) / 2.0


WALL_NOMINAL = (OD - ID) / 2.0
WALL_WORST = worst_wall()
if WALL_WORST < WALL_FLOOR - 1e-9:
    raise AssertionError(
        f"MHA-PD-15 wall {WALL_WORST:.3f} at the printed worst case is under "
        f"the {WALL_FLOOR} floor"
    )

# The sheet: the bore's process under its size.
BORE_CALLOUT = "DRILL THRU"
# drawing-guidelines.md rule 4: the length's ± band names the stack it
# serves -- the ring spaces the knob shaft's pinion from the arm plate's hub,
# a term of the disc cluster's printed stack.
LENGTH_CALLOUT = (
    f"SPACES {_config.parts('pd-transgear-knob-shaft')['number']} PINION\n"
    f"FROM {_config.parts('pd-transgear-arm-plate')['number']} HUB\n"
    f"{STACK_NAME}"
)
# Below-text the part build authors on its source dimensions; the drawing
# imports and reads it back (text set from the drawing writes through to the
# built part, fleet issue #1942).
DIMENSION_CALLOUTS: dict[str, dict[str, str]] = {
    "RingProfile": {"BoreDia": BORE_CALLOUT},
    "Ring": {"RingLength": LENGTH_CALLOUT},
}

# Both faces are thrust faces (pinion in front, plate hub behind): MACHINED, on
# the exact native faces the part build resolves.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "front_face", MACHINED_UM, PlanarFace((0.0, -1.0, 0.0), 0.0), display_unit=UNIT
    ),
    SurfaceFinishControl(
        "rear_face", MACHINED_UM, PlanarFace((0.0, 1.0, 0.0), LENGTH), display_unit=UNIT
    ),
)

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity-policy.md `How the repository implements the guidelines`).
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
