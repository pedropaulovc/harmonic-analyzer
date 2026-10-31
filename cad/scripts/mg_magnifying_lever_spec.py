"""Native dimension and print contract for the full-body quarter-inch lever."""

from _gtol_cylinder import CylinderFace
from _surface_finish import SEAT_UM, SurfaceFinishControl
from mg_lever_thread_joint import (
    INCOMPLETE_THREAD_MAX,
    LEVER_UNIT as UNIT,
    ROD_DIA,
    ROD_LENGTH_PLACES,
    THREAD,
    THREAD_LENGTH_PLACES,
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
ROD_DIA_CALLOUT = "AS-SUPPLIED STOCK\nMHA-MG-02 CLAMP BORE - SLIDING FIT"
# Retain the model's cosmetic-thread metadata; only drawing instances omit the
# class already supplied by the title block. The tip chamfer is the
# title-block edge break (native limits 0..max), so it carries no callout.
THREAD_CALLOUT = f"{THREAD} UNC-2A\nMATES MHA-MG-01 BRACKET"
PRINT_THREAD_CALLOUT = f"{THREAD} UNC\nMATES MHA-MG-01\nBRACKET"
LEAD_CALLOUT = "INCOMPLETE THREAD,\nEACH END"
FREE_END_CALLOUT = "FREE END: TANGENT HEMISPHERE"
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "clamp_screw_seat", SEAT_UM, CylinderFace(ROD_DIA, contains_x_mm=50.0), display_unit=UNIT,
    ),
)
SCREW_SEAT_CALLOUT = "MHA-MG-02 SCREW SEAT"
ISO_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
