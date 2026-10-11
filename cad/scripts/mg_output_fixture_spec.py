r"""MHA-MG-006 output fixture: the drawing contract shared by part and sheet.

PURE DATA, no SolidWorks/COM imports.  The shape is
``mg_output_fixture_geom``'s (the assembly and the wire read that module, not
this one); this module adds what the print states about it: the marked model
dimensions and their places, the explicit bands the model carries, the walls
at the worst case of those printed bands, and the manufacturing notes.

Sheet datums: the axial stations are baselined from the free end of the hex
(the rod bore, the shoulder, the groove and the spigot face); the rod bore
is located across the flats from one flat.  Both are dimensions on the model
(``build_mg_output_fixture``), so the sheet only proves it imported them.
"""

from __future__ import annotations

import mg_output_fixture_geom as _geom
from _printed_tolerance import printed_deviations
from mg_output_fixture_geom import (
    BORE_FROM_FLAT,
    FREE_END_X,
    GROOVE_RADIUS,
    GROOVE_ROOT_DIA,
    GROOVE_X,
    HEX_AF,
    HEX_LENGTH,
    OVERALL_LENGTH,
    ROD_BORE_DIA,
    ROD_STATION,
    SPIGOT_DIA,
    THREAD_MAJOR,
)

# The thumb-screw receiver: the joint-retention audit and the sheet's hole
# callout both read it here.
TAP_SPEC = _geom.TAP_SPEC

# Axial stations from the free end (local x - FREE_END_X).
GROOVE_STATION = GROOVE_X - FREE_END_X

# --- Explicit bands the model carries (policy rule 2) --------------------------
# (upper, lower): the reamed slip bore on the Ø5 rod.
ROD_BORE_DIA_BAND = (0.03, 0.0)
# +/- on the bore's location (the free-end and flat walls), on the shoulder,
# the groove and the spigot face (both groove lips), and on the spigot and
# groove sizes that set the groove's mouth.
POSITION_TOLERANCE = 0.05
SIZE_TOLERANCE = 0.05

# --- Places each printed dimension carries ---------------------------------------
HEX_AF_PLACES = 3  # the bar's flats: the .XXX general row
BORE_FROM_FLAT_PLACES = 2
ROD_STATION_PLACES = 2
HEX_LENGTH_PLACES = 2
GROOVE_STATION_PLACES = 2
OVERALL_LENGTH_PLACES = 2
SPIGOT_DIA_PLACES = 2
GROOVE_ROOT_DIA_PLACES = 2
GROOVE_RADIUS_PLACES = 2
ROD_BORE_DIA_PLACES = 2

# --- Printed limits ----------------------------------------------------------------
_POSITION = (-POSITION_TOLERANCE, POSITION_TOLERANCE)
_SIZE = (-SIZE_TOLERANCE, SIZE_TOLERANCE)
_AF_LO, _ = printed_deviations(HEX_AF, HEX_AF_PLACES)
_FLAT_LO, _FLAT_HI = printed_deviations(
    BORE_FROM_FLAT, BORE_FROM_FLAT_PLACES, _POSITION
)
_ROD_STATION_LO, _ = printed_deviations(ROD_STATION, ROD_STATION_PLACES, _POSITION)
_, _SHOULDER_HI = printed_deviations(HEX_LENGTH, HEX_LENGTH_PLACES, _POSITION)
_GROOVE_LO, _GROOVE_HI = printed_deviations(
    GROOVE_STATION, GROOVE_STATION_PLACES, _POSITION
)
_FACE_LO, _ = printed_deviations(OVERALL_LENGTH, OVERALL_LENGTH_PLACES, _POSITION)
_, _SPIGOT_HI = printed_deviations(SPIGOT_DIA, SPIGOT_DIA_PLACES, _SIZE)
_ROOT_LO, _ = printed_deviations(GROOVE_ROOT_DIA, GROOVE_ROOT_DIA_PLACES, _SIZE)
_, _RADIUS_HI = printed_deviations(GROOVE_RADIUS, GROOVE_RADIUS_PLACES, _SIZE)
_ROD_BORE_R_MAX = (ROD_BORE_DIA + ROD_BORE_DIA_BAND[0]) / 2.0
# A tap cuts up to 0.05 over the basic major: half of it on a wall.
_TAP_OVERSIZE_R = 0.025
_THREAD_R_MAX = THREAD_MAJOR / 2.0 + _TAP_OVERSIZE_R


def groove_half_opening(radius: float, root_dia: float, spigot_dia: float) -> float:
    """Half the groove's mouth along the axis: where the full-radius arc on a
    centre ``radius`` above the root meets the spigot OD."""
    centre_above_od = root_dia / 2.0 + radius - spigot_dia / 2.0
    return (radius**2 - centre_above_od**2) ** 0.5


# The widest mouth the printed bands allow: the largest radius on the
# smallest root under the largest OD.
GROOVE_HALF_OPENING_MAX = groove_half_opening(
    GROOVE_RADIUS + _RADIUS_HI, GROOVE_ROOT_DIA + _ROOT_LO, SPIGOT_DIA + _SPIGOT_HI
)

# --- Walls at the printed worst case (policy rule 12) ----------------------------
# (nominal, worst).
WALL_TARGET = 2.0
WALL_FLOOR = 1.5
BORE_WALL_NAME = "rod bore to the far flat"
WALLS: dict[str, tuple[float, float]] = {
    BORE_WALL_NAME: (
        HEX_AF - BORE_FROM_FLAT - ROD_BORE_DIA / 2.0,
        HEX_AF + _AF_LO - (BORE_FROM_FLAT + _FLAT_HI) - _ROD_BORE_R_MAX,
    ),
    "rod bore to the near flat": (
        BORE_FROM_FLAT - ROD_BORE_DIA / 2.0,
        BORE_FROM_FLAT + _FLAT_LO - _ROD_BORE_R_MAX,
    ),
    "rod bore to the free end": (
        ROD_STATION - ROD_BORE_DIA / 2.0,
        ROD_STATION + _ROD_STATION_LO - _ROD_BORE_R_MAX,
    ),
    "groove lip to the shoulder": (
        GROOVE_STATION - _geom.GROOVE_HALF_OPENING - HEX_LENGTH,
        GROOVE_STATION
        + _GROOVE_LO
        - GROOVE_HALF_OPENING_MAX
        - (HEX_LENGTH + _SHOULDER_HI),
    ),
    "groove lip to the spigot face": (
        OVERALL_LENGTH - GROOVE_STATION - _geom.GROOVE_HALF_OPENING,
        OVERALL_LENGTH
        + _FACE_LO
        - (GROOVE_STATION + _GROOVE_HI)
        - GROOVE_HALF_OPENING_MAX,
    ),
    "groove root over the thread major": (
        (GROOVE_ROOT_DIA - THREAD_MAJOR) / 2.0,
        (GROOVE_ROOT_DIA + _ROOT_LO) / 2.0 - _THREAD_R_MAX,
    ),
}
# The bore-to-far-flat wall is the one named shortfall; it keeps the floor.
BORE_WALL_STATED_MIN = 1.97
for _name, (_nominal, _worst) in WALLS.items():
    _limit = WALL_FLOOR if _name == BORE_WALL_NAME else WALL_TARGET
    if _worst < _limit - 1e-9:
        raise AssertionError(
            f"MHA-MG-006 {_name} wall {_worst:.3f} at the printed worst case is "
            f"under {_limit}"
        )
if round(WALLS[BORE_WALL_NAME][1], 2) != BORE_WALL_STATED_MIN:
    raise AssertionError("MHA-MG-006 stated bore-to-flat wall drifted from its geometry")

# --- Marked model dimensions and the places the model authors on them ------------
# The turned profile (Top plane) carries the axial stations from the free end
# and the spigot's Ø; the groove profile (Top plane) the groove's station from
# the free end, its root Ø and its radius; the hex sketch (the FreeEnd plane)
# the flats and the bore's location from one flat; the bore sketch (Top
# plane) its Ø.  The tap is a Hole Wizard feature: its native callout prints it.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "TurnedProfile": {
        "RodStation": ROD_STATION_PLACES,
        "HexLength": HEX_LENGTH_PLACES,
        "OverallLength": OVERALL_LENGTH_PLACES,
        "SpigotDia": SPIGOT_DIA_PLACES,
    },
    "GrooveProfile": {
        "GrooveStation": GROOVE_STATION_PLACES,
        "GrooveRootDia": GROOVE_ROOT_DIA_PLACES,
        "GrooveRadius": GROOVE_RADIUS_PLACES,
    },
    "HexProfile": {
        "HexAf": HEX_AF_PLACES,
        "BoreFromFlat": BORE_FROM_FLAT_PLACES,
    },
    "RodBoreProfile": {"RodBoreDia": ROD_BORE_DIA_PLACES},
}
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    feature: set(names) for feature, names in DRAWING_PRECISION.items()
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
# Model dimensions with an explicit symmetric band (name -> owning feature).
SYMMETRIC_BANDS: dict[str, tuple[str, float]] = {
    "RodStation": ("TurnedProfile", POSITION_TOLERANCE),
    "HexLength": ("TurnedProfile", POSITION_TOLERANCE),
    "GrooveStation": ("GrooveProfile", POSITION_TOLERANCE),
    "OverallLength": ("TurnedProfile", POSITION_TOLERANCE),
    "SpigotDia": ("TurnedProfile", SIZE_TOLERANCE),
    "GrooveRootDia": ("GrooveProfile", SIZE_TOLERANCE),
    "GrooveRadius": ("GrooveProfile", SIZE_TOLERANCE),
    "BoreFromFlat": ("HexProfile", POSITION_TOLERANCE),
}
if not set(SYMMETRIC_BANDS) <= set(DRAWING_PRECISION_BY_NAME):
    raise AssertionError("MHA-MG-006 banded a dimension the sheet does not print")

# --- Sheet text -------------------------------------------------------------------
# The bore is a fit on the rod: the callout under its Ø says how it is made.
ROD_BORE_CALLOUT = "REAM THRU"
# The thumb-screw tap runs from the spigot face until it breaks into the bore.
TAP_PROCESS = "TAP TO BORE"
STOCK_NOTE = "3/8 HEX BAR, FLATS AS SUPPLIED."
# Named exception: MHA-MG-006 bore-to-flat wall (drawing-simplicity-policy.md, "Named exceptions").
BORE_WALL_NOTE = f"BORE TO FLAT WALL {BORE_WALL_STATED_MIN:.2f} MIN."
DRAWING_NOTES = "\n".join((STOCK_NOTE, BORE_WALL_NOTE))
