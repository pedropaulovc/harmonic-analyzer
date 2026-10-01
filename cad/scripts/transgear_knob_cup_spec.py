r"""MHA-157 transgear-knob-cup: the brass cup clamped on the knob shaft's rear end.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  The MHA-158 retaining screw (``transgear_knob_retaining_screw_spec``)
seats its pan head on the counterbore floor and clamps the cup's front face
on the knob shaft's (MHA-078) rear end face.  The outer ring of that same
front face runs 0.2 behind the arm plate's rear boss: the cup is the REAR
stop of the knob's end float (the MHA-156 thrust ring is the forward one).
Contract §1.8, round 7 default c: the cup is 5.6 long so the floor is 2.6,
printed as ONE dimension from the front face at .XX.  The floor band is also
the screw's engagement band (contract §7).

Part frame: axis local +Y through the origin (``Axis1``); the front face
(clamp and running face) is the Top Plane, y = 0; the counterbore opens at
the rear face, y = LENGTH; its floor -- the screw's seat -- is the
``ScrewSeat`` plane at y = FLOOR.
"""

from __future__ import annotations

from _gtol_spec import PlanarFace
from _printed_tolerance import printed_deviations
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from transgear_knob_retaining_screw_spec import (
    FIRST_THREAD_LOSS,
    HEAD_DIA,
    HEAD_H,
    SHANK_DIA,
    SHANK_LEN,
    SHANK_LEN_BAND,
)

OD = 19.0
LENGTH = 5.6
COUNTERBORE_DIA = 9.5
FLOOR = 2.6  # front face to the counterbore floor
BORE_DIA = 4.3
# Clears the #8-32 shank; drilled, never under size (drilled-hole class).
BORE_BAND = (0.10, 0.0)  # (upper, lower) deviations

# Places each printed dimension carries (policy rule 12, contract §12): the
# floor at .XX (the screw's engagement band), the bore at .XX under its own
# band; the O.D., the counterbore and the length are routine at .X -- the
# walls, the floor ligament and the pan head's entry all hold at that row.
OD_PLACES = 1
COUNTERBORE_PLACES = 1
FLOOR_PLACES = 2
BORE_PLACES = 2
LENGTH_PLACES = 1

WALL_FLOOR = 2.0
ENGAGEMENT_FLOOR_D = 1.5


def _band(model: float, places: int) -> tuple[float, float]:
    return printed_deviations(model, places)


_OD_LO, _ = _band(OD, OD_PLACES)
_CB_LO, _CB_HI = _band(COUNTERBORE_DIA, COUNTERBORE_PLACES)
_FLOOR_LO, _FLOOR_HI = _band(FLOOR, FLOOR_PLACES)
_LENGTH_LO, _ = _band(LENGTH, LENGTH_PLACES)

# --- Walls at the printed worst case (contract §8) ----------------------------
FLOOR_WORST = FLOOR + _FLOOR_LO
COUNTERBORE_WALL = (OD - COUNTERBORE_DIA) / 2.0
COUNTERBORE_WALL_WORST = ((OD + _OD_LO) - (COUNTERBORE_DIA + _CB_HI)) / 2.0
# The floor annulus the pan head bears on, bore to counterbore (informational).
FLOOR_LIGAMENT = (COUNTERBORE_DIA - BORE_DIA) / 2.0
FLOOR_LIGAMENT_WORST = ((COUNTERBORE_DIA + _CB_LO) - (BORE_DIA + max(BORE_BAND))) / 2.0
for _name, _wall in (
    ("floor", FLOOR_WORST),
    ("counterbore wall", COUNTERBORE_WALL_WORST),
):
    if _wall < WALL_FLOOR - 1e-9:
        raise AssertionError(
            f"MHA-157 {_name} {_wall:.3f} at the printed worst case is under "
            f"the {WALL_FLOOR} floor"
        )

# --- The screw's side of its engagement (contract §7) -------------------------
# The shank reaches past the cup's front face -- into the shaft's tap -- by
# its length under the head less the floor.  Worst case: the shortest screw
# its B18.6.3 band allows in the thickest floor the sheet accepts, less the
# incomplete first thread.  The shaft's side (its tap entry countersink, its
# full-thread depth) is MHA-078's and is added by the assembly.
REACH = SHANK_LEN - FLOOR
REACH_MIN = SHANK_LEN - SHANK_LEN_BAND[1] - (FLOOR + _FLOOR_HI)
REACH_MAX = SHANK_LEN + SHANK_LEN_BAND[0] - FLOOR_WORST
ENGAGEMENT_OWN_WORST = REACH_MIN - FIRST_THREAD_LOSS
if ENGAGEMENT_OWN_WORST < ENGAGEMENT_FLOOR_D * SHANK_DIA - 1e-9:
    raise AssertionError(
        f"MHA-158 engages {ENGAGEMENT_OWN_WORST:.3f} "
        f"({ENGAGEMENT_OWN_WORST / SHANK_DIA:.2f} D) at the thickest printed "
        f"MHA-157 floor, under {ENGAGEMENT_FLOOR_D} D before the shaft's own terms"
    )

# --- The pan head in the counterbore ------------------------------------------
HEAD_CLEARANCE = (COUNTERBORE_DIA - HEAD_DIA) / 2.0
HEAD_CLEARANCE_WORST = ((COUNTERBORE_DIA + _CB_LO) - HEAD_DIA) / 2.0
if HEAD_CLEARANCE_WORST <= 0.0:
    raise AssertionError("MHA-158's pan head does not enter the smallest counterbore")
# Head top below the rear face (positive = recessed); the length prints .X,
# so at the worst case the head can stand proud of the rear face.
HEAD_RECESS = LENGTH - (FLOOR + HEAD_H)
HEAD_RECESS_WORST = (LENGTH + _LENGTH_LO) - (FLOOR + _FLOOR_HI + HEAD_H)

# The sheet: the bore's process under its size.
BORE_CALLOUT = "DRILL THRU"

# The front face is the running face on the plate's rear boss (and the
# clamp face on the shaft's end): MACHINED, on the exact native face the part
# build resolves.
SURFACE_FINISHES = (
    SurfaceFinishControl("front_face", MACHINED_UM, PlanarFace((0.0, -1.0, 0.0), 0.0)),
)

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity policy rule 2).  The turned profile carries both
# diameters, the length and the floor from the front face; the bore is its
# own feature.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "CupProfile": {"CupDia", "CounterboreDia", "CupLength", "FloorDepth"},
    "BoreProfile": {"BoreDia"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "CupProfile": {
        "CupDia": OD_PLACES,
        "CounterboreDia": COUNTERBORE_PLACES,
        "CupLength": LENGTH_PLACES,
        "FloorDepth": FLOOR_PLACES,
    },
    "BoreProfile": {"BoreDia": BORE_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
