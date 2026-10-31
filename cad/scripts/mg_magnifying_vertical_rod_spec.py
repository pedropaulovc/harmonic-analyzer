r"""Magnifying vertical-rod dimensional contract -- the single source of truth
shared by the part build (``build_mg_magnifying_vertical_rod.py``) and its
manufacturing drawing (``draw_mg_magnifying_vertical_rod.py``).

PURE DATA, no SolidWorks/COM imports. Sizes live in the drawing-free geometry
module because the magnifier assembly and the fixture installation consume
them; the threaded joint to MHA-MG-02 lives in ``mg_rod_clamp_joint`` (#1559).
Drawing notes and marks stay out of the magnifier assembly recipe closure.
The offline lockstep test asserts part marks and drawing keeps.

Part frame: rod axis local +X, origin at the thread tip on the axis; the
shoulder at SHOULDER_X, the bottom dome's tip at ROD_LENGTH.
"""

from __future__ import annotations

import _config
from _package_units import drawing_unit
from mg_magnifying_vertical_rod_geom import (
    BODY_LENGTH,
    DOME_R,
    RELIEF_START_X,
    ROD_DIA,
    ROD_DIA_FRACTION_DENOMINATOR,
    ROD_LENGTH,
    SHOULDER_X,
    TIP_CHAMFER,
)
from mg_rod_clamp_joint import (
    DIE_RUNOUT,
    RELIEF_DIA,
    RELIEF_DIA_PLACES,
    RELIEF_DIA_TOL_TYPE,
    RELIEF_ROOT_R,
    RELIEF_ROOT_R_PLACES,
    RELIEF_ROOT_R_TOL_TYPE,
    RELIEF_WIDTH,
    RELIEF_WIDTH_PLACES,
    ROD_THREAD_LEN,
    ROD_THREAD_LEN_PLACES,
    THREAD,
    THREAD_BASIC_MINOR,
    THREAD_CALLOUT,
    THREAD_MAJOR,
    THREAD_PITCH,
    TIP_INCOMPLETE,
)

__all__ = [
    "BODY_LENGTH",
    "DIE_RUNOUT",
    "DOME_R",
    "DRAWING_DIMENSIONS",
    "DRAWING_PRECISION",
    "FULL_THREAD_END_X",
    "FULL_THREAD_START_X",
    "ISO_VIEW_NOTE",
    "REFERENCE_DIMENSIONS",
    "RELIEF_DIA",
    "RELIEF_DIA_TOL_TYPE",
    "RELIEF_ROOT_R",
    "RELIEF_ROOT_R_TOL_TYPE",
    "RELIEF_ROOTS_CALLOUT",
    "RELIEF_START_X",
    "RELIEF_WIDTH",
    "ROD_DIA",
    "ROD_DIA_FRACTION_DENOMINATOR",
    "ROD_LENGTH",
    "ROD_THREAD_LEN",
    "SHOULDER_X",
    "SINGLE_LIMITS",
    "STOCK_REFERENCE_DIMENSION",
    "THREAD",
    "THREAD_BASIC_MINOR",
    "THREAD_CALLOUT",
    "THREAD_MAJOR",
    "THREAD_PITCH",
    "TIP_CHAMFER",
    "TIP_INCOMPLETE",
    "UNIT",
]

# #290: the sheet prints decimal inch.
UNIT = drawing_unit(
    "parts/mg-magnifying-vertical-rod", _config.parts("mg-magnifying-vertical-rod")
)

# Full thread on the rod (drawing-guidelines.md rule 18 counts full thread
# only): from one pitch behind the tip chamfer to the relief's far edge; the
# die's run-out lies in the relief (mg_rod_clamp_joint checks its width).
FULL_THREAD_START_X = TIP_INCOMPLETE
FULL_THREAD_END_X = RELIEF_START_X

# ONE revolved profile. The thread end reads from the shoulder, the seating
# face that plumbs the rod (drawing-guidelines.md rule 10, functional datum):
# the thread length and the body length both baseline from it. The overall
# (thread + body) is a driven reference, never a third control.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RodProfile": {
        "RodDia",
        "BodyLength",
        "OverallLength",
        "DomeR",
        "ThreadLength",
        "ReliefWidth",
        "ReliefDia",
    },
    # The relief's two internal corners, one fillet feature over both edges.
    "ReliefRoots": {"ReliefRootR"},
}
# The thread length (it keeps the tip clear of the tap's incomplete thread,
# mg_rod_clamp_joint) and the relief width print at the title block's .XX
# band, the relief Ø as the single limit "Ø.072 MAX" and its two roots as
# "R.008 MAX".
SINGLE_LIMITS: dict[tuple[str, str], tuple[float, int]] = {
    ("RodProfile", "ReliefDia"): (RELIEF_DIA, RELIEF_DIA_TOL_TYPE),
    ("ReliefRoots", "ReliefRootR"): (RELIEF_ROOT_R, RELIEF_ROOT_R_TOL_TYPE),
}
REFERENCE_DIMENSIONS: tuple[tuple[str, str], ...] = (("RodProfile", "OverallLength"),)
# The as-bought 7/32 rod's Ø prints as a supplier REF fraction; its tolerance
# is the supplier's (mg_magnifying_vertical_rod_geom.ROD_DIA_BAND).
STOCK_REFERENCE_DIMENSION = "RodDia"
# The body length and the dome (tangent to the body) print .XX.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RodProfile": {
        "RodDia": 3,
        "BodyLength": 2,
        "OverallLength": 2,
        "DomeR": 2,
        "ThreadLength": ROD_THREAD_LEN_PLACES,
        "ReliefWidth": RELIEF_WIDTH_PLACES,
        "ReliefDia": RELIEF_DIA_PLACES,
    },
    "ReliefRoots": {"ReliefRootR": RELIEF_ROOT_R_PLACES},
}
# ONE radius prints for both roots (one fillet feature): its count rides
# above the value.
RELIEF_ROOTS_CALLOUT = "2X"

# No general notes (drawing-guidelines.md rule 7): the overall, the seat on
# MHA-MG-02 and the hemisphere each ride their own callout. The as-bought rod
# body carries no roughness symbol: the shop does nothing to it.
ISO_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"

if (
    abs(SHOULDER_X - ROD_THREAD_LEN) > 1e-9
    or abs(ROD_LENGTH - SHOULDER_X - BODY_LENGTH) > 1e-9
):
    raise AssertionError("MHA-MG-04 printed lengths do not sum to the overall")
if not 0.0 < TIP_CHAMFER < FULL_THREAD_START_X < FULL_THREAD_END_X < SHOULDER_X:
    raise AssertionError("MHA-MG-04 full-thread stations out of order")
if abs(SHOULDER_X - RELIEF_START_X - RELIEF_WIDTH) > 1e-9:
    raise AssertionError("MHA-MG-04 relief does not end on the shoulder")
