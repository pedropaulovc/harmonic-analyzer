"""Native dimension and print contract for the full-body quarter-inch lever."""

from _gtol_cylinder import CylinderFace
from _surface_finish import SEAT_UM, SurfaceFinishControl
from mg_lever_thread_joint import INCOMPLETE_THREAD_MAX, ROD_DIA, THREAD

DRAWING_DIMENSIONS = {
    "RodProfile": {"OverallLength", "RodDia", "TipChamfer"},
    "ThreadExtent": {"ThreadLength", "IncompleteLength"},
}
DRAWING_PRECISION = {
    "RodProfile": {"OverallLength": 1, "RodDia": 2, "TipChamfer": 2},
    "ThreadExtent": {"ThreadLength": 2, "IncompleteLength": 3},
}
SINGLE_LIMITS = {("ThreadExtent", "IncompleteLength"): (INCOMPLETE_THREAD_MAX, 6)}
ROD_DIA_CALLOUT = "1/4 IN STOCK OK WITHIN LIMITS\nMHA-MG-02 CLAMP BORE - SLIDING FIT"
# Retain the model's cosmetic-thread metadata; only drawing instances omit the
# class already supplied by the title block.
THREAD_CALLOUT = f"{THREAD} UNC-2A\nMATES MHA-MG-01 BRACKET"
PRINT_THREAD_CALLOUT = f"{THREAD} UNC\nMATES MHA-MG-01 BRACKET"
TIP_CALLOUT = "45° AT THREADED END ONLY\nMHA-MG-01 THREAD ENTRY;\nLIMIT RETAINS FULL ENGAGEMENT"
LEAD_CALLOUT = "INCOMPLETE THREAD,\nEACH END"
FREE_END_CALLOUT = "FREE END: TANGENT HEMISPHERE"
SURFACE_FINISHES = (SurfaceFinishControl("clamp_screw_seat", SEAT_UM, CylinderFace(ROD_DIA, contains_x_mm=50.0)),)
SCREW_SEAT_CALLOUT = "MHA-MG-02 SCREW SEAT"
ISO_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
