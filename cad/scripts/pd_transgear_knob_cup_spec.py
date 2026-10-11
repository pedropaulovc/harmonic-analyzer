r"""MHA-PD-016 transgear-knob-cup: the brass cup pinned on the knob shaft's rear end.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  A plain turned ring, reamed to slide on the knob shaft's (MHA-PD-008)
Ø8.5 journal where it runs on behind the arm plate's rear boss.  Its front
face runs END_FLOAT behind that boss: the cup is the REAR stop of the knob's
end float (the MHA-PD-015 thrust ring is the forward one).  K-1 (R9-70): at
assembly the cup is slid on against a feeler at the boss, then a Ø1.6 hole
is match-drilled through cup and journal PIN_HOLE_FROM_FRONT behind its
front face and the MHA-VN-048 spring pin pressed through both, so the cup is
locked to the shaft in shear and carries no thread.  The hole is drilled at
assembly and is not modelled on the part.

Part frame: axis local +Y through the origin (``Axis1``); the front face
(the running face) is the Top Plane, y = 0; the rear face is y = LENGTH.
"""

from __future__ import annotations

import math

from _gtol_planar import PlanarFace
from _printed_tolerance import printed_deviations
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from pd_transgear_arm_plate_geometry import BORE_DIA_LIMITS as PLATE_BORE_LIMITS
from vn_transgear_knob_cup_pin_spec import HOLE_MAX as PIN_HOLE_MAX
from vn_transgear_knob_cup_pin_spec import PIN_LEN, PIN_LEN_MAX
from pd_transgear_knob_shaft_spec import (
    JOURNAL_DIA,
    JOURNAL_DIA_BAND,
    JOURNAL_DIA_MIN,
    JOURNAL_REAR_EXTENSION,
    JOURNAL_REAR_EXTENSION_MAX,
    JOURNAL_REAR_EXTENSION_MIN,
)

OD = 19.0
LENGTH = 8.0
BORE_DIA = JOURNAL_DIA  # 6.0 g6 shaft
# Reamed to the plate's H7 limits; the same journal runs/slides in both.
# ISO over 3 THROUGH 6 mm: 0.004..0.024 diametral clearance.
BORE_BAND = (max(PLATE_BORE_LIMITS), min(PLATE_BORE_LIMITS))

# Places each printed dimension carries (policy rule 12): the O.D. and the
# length are routine at .X -- the walls and the pin hold at that row; the bore
# prints .XXX under its own band.
OD_PLACES = 1
LENGTH_PLACES = 1
BORE_PLACES = 3

WALL_FLOOR = 2.0

_OD_LO, _ = printed_deviations(OD, OD_PLACES)
_LENGTH_LO, _ = printed_deviations(LENGTH, LENGTH_PLACES)
OD_MIN = OD + _OD_LO  # 18.2
LENGTH_MIN = LENGTH + _LENGTH_LO  # 7.2
BORE_MAX = BORE_DIA + max(BORE_BAND)

BORE_JOURNAL_CLEARANCE = (
    BORE_DIA + min(BORE_BAND) - (JOURNAL_DIA + max(JOURNAL_DIA_BAND)),
    BORE_MAX - JOURNAL_DIA_MIN,
)
if min(BORE_JOURNAL_CLEARANCE) <= 0.0:
    raise AssertionError("MHA-PD-016's reamed bore binds on the journal")

# --- The pin hole, match-drilled at assembly (R9-70, K-1) ---------------------
# Its centre stands PIN_HOLE_FROM_FRONT behind the cup's front face, marked
# out within PIN_HOLE_STATION_TOL; Ø1.6 +0.05/0 (MHA-VN-048's hole band).
PIN_HOLE_FROM_FRONT = 3.0
PIN_HOLE_STATION_TOL = 0.10
_PIN_HOLE_R_MAX = PIN_HOLE_MAX / 2.0  # 0.825

# --- Walls at the printed worst case (contract §8, policy rule 12) -------------
# Journal beside the hole: (5.988 - 1.65) / 2 = 2.169.
JOURNAL_PIN_WALL = (JOURNAL_DIA - PIN_HOLE_MAX) / 2.0
JOURNAL_PIN_WALL_WORST = (JOURNAL_DIA_MIN - PIN_HOLE_MAX) / 2.0
# Cup front face to the hole's edge: 3.0 - 0.825 = 2.18 nominal; less the
# marking-out 0.10, 2.08.
FRONT_PIN_WALL = PIN_HOLE_FROM_FRONT - _PIN_HOLE_R_MAX
FRONT_PIN_WALL_WORST = PIN_HOLE_FROM_FRONT - PIN_HOLE_STATION_TOL - _PIN_HOLE_R_MAX
# Hole to the journal's rear end, the journal at its shortest behind the
# cup's front face (MHA-PD-008's .XXX length, the ring and hub-to-boss bands and
# the feeler setting): 6.22 - 3.10 - 0.825 = 2.30 (6.5 - 3.0 - 0.825 = 2.68
# nominal).
END_PIN_WALL = JOURNAL_REAR_EXTENSION - PIN_HOLE_FROM_FRONT - _PIN_HOLE_R_MAX
END_PIN_WALL_WORST = (
    JOURNAL_REAR_EXTENSION_MIN
    - PIN_HOLE_FROM_FRONT
    - PIN_HOLE_STATION_TOL
    - _PIN_HOLE_R_MAX
)
# Cup ring around the bore at the hole: (18.2 - 6.012) / 2 = 6.094.
RADIAL_WALL = (OD - BORE_DIA) / 2.0
RADIAL_WALL_WORST = (OD_MIN - BORE_MAX) / 2.0
# Hole to the cup's rear face, the shortest cup: 7.2 - 3.10 - 0.825 = 3.28.
REAR_PIN_WALL_WORST = (
    LENGTH_MIN - PIN_HOLE_FROM_FRONT - PIN_HOLE_STATION_TOL - _PIN_HOLE_R_MAX
)
for _name, _wall in (
    ("journal beside the pin hole", JOURNAL_PIN_WALL_WORST),
    ("front face to the pin hole", FRONT_PIN_WALL_WORST),
    ("pin hole to the journal's rear end", END_PIN_WALL_WORST),
    ("ring round the bore", RADIAL_WALL_WORST),
    ("pin hole to the rear face", REAR_PIN_WALL_WORST),
):
    if _wall < WALL_FLOOR - 1e-9:
        raise AssertionError(
            f"MHA-PD-016 {_name} {_wall:.3f} at the printed worst case is under "
            f"the {WALL_FLOOR} floor"
        )

# The pin's ends stay inside the cup's O.D.: (19.0 - 15.875) / 2 = 1.56 at
# nominal, (18.2 - 16.256) / 2 = 0.97 for the longest pin in the smallest
# cup, pressed centred.
PIN_END_INSIDE_OD = (OD - PIN_LEN) / 2.0
PIN_END_INSIDE_OD_WORST = (OD_MIN - PIN_LEN_MAX) / 2.0
if PIN_END_INSIDE_OD_WORST <= 0.0:
    raise AssertionError("MHA-VN-048's ends stand out of MHA-PD-016's O.D.")
# The pin spans the journal and bites both cup walls.
if not PIN_LEN > BORE_MAX:
    raise AssertionError("MHA-VN-048 does not reach through both cup walls")

# The journal's rear end stays inside the cup, behind its rear face:
# 7.2 - 6.78 = 0.42 at the worst case, 1.5 at nominal.
JOURNAL_END_INSET = LENGTH - JOURNAL_REAR_EXTENSION
JOURNAL_END_INSET_WORST = LENGTH_MIN - JOURNAL_REAR_EXTENSION_MAX
if JOURNAL_END_INSET_WORST <= 0.0:
    raise AssertionError("the knob shaft's rear end stands out of MHA-PD-016")
if not math.isclose(JOURNAL_END_INSET, 1.5, abs_tol=1e-9):
    raise AssertionError("MHA-PD-016 no longer covers the journal's end by 1.5")

# The sheet: the bore's process, and the hole the assembly drills.
BORE_CALLOUT = "REAM THRU\nPIN HOLE DRILLED AT ASSEMBLY"

# The front face is the running face on the plate's rear boss: MACHINED, on
# the exact native face the part build resolves.
SURFACE_FINISHES = (
    SurfaceFinishControl("front_face", MACHINED_UM, PlanarFace((0.0, -1.0, 0.0), 0.0)),
)

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity policy rule 2).  The turned profile carries the O.D.
# and the length; the bore is its own feature.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "CupProfile": {"CupDia", "CupLength"},
    "BoreProfile": {"BoreDia"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "CupProfile": {"CupDia": OD_PLACES, "CupLength": LENGTH_PLACES},
    "BoreProfile": {"BoreDia": BORE_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
