r"""MHA-PD-16 transgear-knob-cup: the brass cup pinned on the knob shaft's rear end.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  A plain turned ring, reamed to slide on the knob shaft's (MHA-PD-08)
journal where it runs on behind the arm plate's rear boss.  Its front
face runs END_FLOAT behind that boss: the cup is the REAR stop of the knob's
end float (the MHA-PD-15 thrust ring is the forward one).  K-1 (R9-70): at
assembly the cup is slid on against a feeler at the boss, then the
MHA-PD-VN-62 pin's hole is match-drilled through cup and journal
PIN_HOLE_FROM_FRONT behind its front face and the spring pin pressed through
both, so the cup is locked to the shaft in shear and carries no thread.  The
hole is drilled at assembly and is not modelled on the part.

Decimal inch (#290): the bore is the journal's .249 REAM_H7 at four places.

Part frame: axis local +Y through the origin (``Axis1``); the front face
(the running face) is the Top Plane, y = 0; the rear face is y = LENGTH.
"""

from __future__ import annotations

import math

import _config
from _gtol_planar import PlanarFace
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_deviations
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from pd_transgear_arm_plate_geometry import BORE_DIA_LIMITS as PLATE_BORE_LIMITS
from pd_vn_transgear_knob_cup_pin_spec import HOLE_MAX as PIN_HOLE_MAX
from pd_vn_transgear_knob_cup_pin_spec import PIN_LEN, PIN_LEN_MAX
from pd_rack_pinion_spec import inch_ceil_mm, inch_floor_mm, inch_text
from pd_transgear_knob_shaft_spec import (
    JOURNAL_DIA,
    JOURNAL_DIA_BAND,
    JOURNAL_DIA_MIN,
    JOURNAL_REAR_EXTENSION,
    JOURNAL_REAR_EXTENSION_MAX,
    JOURNAL_REAR_EXTENSION_MIN,
)

# #290: the registry row's drawing_unit (in) is this sheet's unit.
UNIT = drawing_unit("parts/pd-transgear-knob-cup", _config.parts("pd-transgear-knob-cup"))

OD = 19.05  # .75
LENGTH = 8.128  # .32
BORE_DIA = JOURNAL_DIA  # .249 g6 shaft
# Reamed to the plate's H7 limits; the same journal runs/slides in both.
BORE_BAND = (max(PLATE_BORE_LIMITS), min(PLATE_BORE_LIMITS))

# Places each printed dimension carries (drawing-guidelines.md rule 3 (decimal
# places carry the tolerance)): the O.D. and the length are routine at .XX
# (the shortest .32 cup still covers the journal's end and the pin hole's
# rear wall: machinist review, .315 named no stack); the bore prints four
# places under its own reamed band.
OD_PLACES = 2
LENGTH_PLACES = 2
BORE_PLACES = 4

WALL_FLOOR = WALL_TARGET_MM

_OD_LO, _ = printed_deviations(OD, OD_PLACES, unit=UNIT)
_LENGTH_LO, _ = printed_deviations(LENGTH, LENGTH_PLACES, unit=UNIT)
OD_MIN = OD + _OD_LO
LENGTH_MIN = LENGTH + _LENGTH_LO
BORE_MAX = BORE_DIA + max(BORE_BAND)
BORE_JOURNAL_CLEARANCE = (
    BORE_DIA + min(BORE_BAND) - (JOURNAL_DIA + max(JOURNAL_DIA_BAND)),
    BORE_MAX - JOURNAL_DIA_MIN,
)
if min(BORE_JOURNAL_CLEARANCE) <= 0.0:
    raise AssertionError("MHA-PD-16's reamed bore binds on the journal")
# The bore callout's diametral clearance, rounded outward onto the inch grid.
BORE_CLEARANCE_TEXT = (
    f"{inch_text(inch_floor_mm(min(BORE_JOURNAL_CLEARANCE), 4), 4)}-"
    f"{inch_text(inch_ceil_mm(max(BORE_JOURNAL_CLEARANCE), 4), 4)}"
)

# --- The pin hole, match-drilled at assembly (R9-70, K-1) ---------------------
# Its centre stands PIN_HOLE_FROM_FRONT behind the cup's front face, marked
# out within PIN_HOLE_STATION_TOL; MHA-PD-VN-62's .062 +.003/0 hole.
PIN_HOLE_FROM_FRONT = 3.048  # .120
PIN_HOLE_STATION_TOL = 0.1016  # .004
_PIN_HOLE_R_MAX = PIN_HOLE_MAX / 2.0

# --- Walls at the printed worst case (contract §8, drawing-guidelines.md rule 17 (walls and webs)) -------------
# Journal beside the hole.
JOURNAL_PIN_WALL = (JOURNAL_DIA - PIN_HOLE_MAX) / 2.0
JOURNAL_PIN_WALL_WORST = (JOURNAL_DIA_MIN - PIN_HOLE_MAX) / 2.0
# Cup front face to the hole's edge, less the marking-out tolerance.
FRONT_PIN_WALL = PIN_HOLE_FROM_FRONT - _PIN_HOLE_R_MAX
FRONT_PIN_WALL_WORST = PIN_HOLE_FROM_FRONT - PIN_HOLE_STATION_TOL - _PIN_HOLE_R_MAX
# Hole to the journal's rear end, the journal at its shortest behind the
# cup's front face (MHA-PD-08's length, the ring and hub-to-boss bands and
# the feeler setting).
END_PIN_WALL = JOURNAL_REAR_EXTENSION - PIN_HOLE_FROM_FRONT - _PIN_HOLE_R_MAX
END_PIN_WALL_WORST = (
    JOURNAL_REAR_EXTENSION_MIN
    - PIN_HOLE_FROM_FRONT
    - PIN_HOLE_STATION_TOL
    - _PIN_HOLE_R_MAX
)
# Cup ring around the bore at the hole.
RADIAL_WALL = (OD - BORE_DIA) / 2.0
RADIAL_WALL_WORST = (OD_MIN - BORE_MAX) / 2.0
# Hole to the cup's rear face, the shortest cup.
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
            f"MHA-PD-16 {_name} {_wall:.3f} at the printed worst case is under "
            f"the {WALL_FLOOR} floor"
        )

# The pin's ends stay inside the cup's O.D., for the longest pin in the
# smallest cup, pressed centred.
PIN_END_INSIDE_OD = (OD - PIN_LEN) / 2.0
PIN_END_INSIDE_OD_WORST = (OD_MIN - PIN_LEN_MAX) / 2.0
if PIN_END_INSIDE_OD_WORST <= 0.0:
    raise AssertionError("MHA-PD-VN-62's ends stand out of MHA-PD-16's O.D.")
# The pin spans the journal and bites both cup walls.
if not PIN_LEN > BORE_MAX:
    raise AssertionError("MHA-PD-VN-62 does not reach through both cup walls")

# The journal's rear end stays inside the cup, behind its rear face.
JOURNAL_END_INSET = LENGTH - JOURNAL_REAR_EXTENSION
JOURNAL_END_INSET_WORST = LENGTH_MIN - JOURNAL_REAR_EXTENSION_MAX
if JOURNAL_END_INSET_WORST <= 0.0:
    raise AssertionError("the knob shaft's rear end stands out of MHA-PD-16")
if not math.isclose(JOURNAL_END_INSET, 1.6256, abs_tol=1e-9):
    raise AssertionError("MHA-PD-16 no longer covers the journal's end by .064")

# The front face is the running face on the plate's rear boss: MACHINED, on
# the exact native face the part build resolves.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "front_face", MACHINED_UM, PlanarFace((0.0, -1.0, 0.0), 0.0), display_unit=UNIT,
    ),
)

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity-policy.md `How the repository implements the guidelines`).  The turned profile carries the O.D.,
# the bore and the length, so all three print on the axial section (rule 11).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "CupProfile": {"CupDia", "CupLength", "BoreDia"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "CupProfile": {
        "CupDia": OD_PLACES,
        "CupLength": LENGTH_PLACES,
        "BoreDia": BORE_PLACES,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
