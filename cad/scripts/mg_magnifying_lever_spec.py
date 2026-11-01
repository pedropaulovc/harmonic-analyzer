"""Native dimension and print contract for the full-body quarter-inch lever."""

import math

from _gtol_cylinder import CylinderFace
from _printed_tolerance import drilled_oversize_mm, printed_deviations
from _surface_finish import SEAT_UM, SurfaceFinishControl
import mg_magnifying_clamp_spec as clamp
from mg_lever_thread_joint import (
    INCOMPLETE_THREAD_MAX,
    LEVER_UNIT as UNIT,
    ROD_DIA,
    ROD_DIA_BAND,
    ROD_LENGTH_PLACES,
    THREAD,
    THREAD_LENGTH,
    THREAD_LENGTH_PLACES,
    THREAD_LENGTH_TOL,
)

DRAWING_DIMENSIONS = {
    "RodProfile": {"OverallLength", "RodDia"},
    "ThreadExtent": {"ThreadLength", "IncompleteLength"},
}
# Inch places; the rod diameter prints as its stock fraction (REF), so its
# places only govern the model before the sheet dresses it.
DRAWING_PRECISION = {
    "RodProfile": {"OverallLength": ROD_LENGTH_PLACES, "RodDia": 2},
    "ThreadExtent": {"ThreadLength": THREAD_LENGTH_PLACES, "IncompleteLength": 3},
}
SINGLE_LIMITS = {("ThreadExtent", "IncompleteLength"): (INCOMPLETE_THREAD_MAX, 6)}
ROD_DIA_FRACTION_DENOMINATOR = 4


def _inch(mm: float) -> str:
    return f"{mm / 25.4:.3f}".replace("0.", ".", 1)


# The sliding fit prints as limits: the stock band against the clamp sheet's
# printed drilled lever bore.
_BORE_LIMITS = tuple(
    clamp.LEVER_BORE_DIA + deviation
    for deviation in printed_deviations(
        clamp.LEVER_BORE_DIA, clamp.LEVER_BORE_DIA_PLACES,
        (0.0, drilled_oversize_mm(unit=clamp.UNIT)), unit=clamp.UNIT,
    )
)
ROD_BORE_CLEARANCE = (
    _BORE_LIMITS[0] - (ROD_DIA + ROD_DIA_BAND[0]),
    _BORE_LIMITS[1] - (ROD_DIA + ROD_DIA_BAND[1]),
)
ROD_DIA_CALLOUT = (
    f"AS-SUPPLIED STOCK {_inch(ROD_DIA_BAND[0])}/{_inch(ROD_DIA_BAND[1])}\n"
    f"{_inch(ROD_BORE_CLEARANCE[0])}-{_inch(ROD_BORE_CLEARANCE[1])} DIAMETRAL CLEARANCE IN MHA-MG-02 CLAMP BORE"
)
# Retain the model's cosmetic-thread metadata; only drawing instances omit the
# class already supplied by the title block. The tip chamfer is the
# title-block edge break (native limits 0..max), so it carries no callout.
THREAD_CALLOUT = f"{THREAD} UNC-2A\nMATES MHA-MG-01 BRACKET"
PRINT_THREAD_CALLOUT = f"{THREAD} UNC\nMATES MHA-MG-01\nBRACKET"
# Full thread between the two incomplete ends at the printed shortest thread,
# floored to the thread length's places.
FULL_THREAD_MIN = THREAD_LENGTH - THREAD_LENGTH_TOL - 2.0 * INCOMPLETE_THREAD_MAX
_FULL_THREAD_MIN_IN = math.floor(FULL_THREAD_MIN / 25.4 * 10**THREAD_LENGTH_PLACES + 1e-9) / 10**THREAD_LENGTH_PLACES
LEAD_CALLOUT = (
    "INCOMPLETE THREAD,\nEACH END OF THREAD\n"
    f"FULL THREAD {_FULL_THREAD_MIN_IN:.{THREAD_LENGTH_PLACES}f} MIN".replace(" 0.", " .")
)
FREE_END_CALLOUT = "FREE END: TANGENT HEMISPHERE"
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "clamp_screw_seat", SEAT_UM, CylinderFace(ROD_DIA, contains_x_mm=50.0), display_unit=UNIT,
    ),
)
SCREW_SEAT_CALLOUT = "MHA-MG-02 SCREW SEAT"
ISO_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
