r"""Magnifying vertical-rod dimensional contract -- the single source of truth
shared by the part build (``build_mg_magnifying_vertical_rod.py``) and its
manufacturing drawing (``draw_mg_magnifying_vertical_rod.py``).

PURE DATA, no SolidWorks/COM imports. Sizes live in the drawing-free geometry
module because the magnifier assembly and the fixture installation consume
them; the threaded joint to MHA-MG-002 lives in ``mg_rod_clamp_joint`` (#1559).
Drawing notes and marks stay out of the magnifier assembly recipe closure.
The offline lockstep test asserts part marks and drawing keeps.

Part frame: rod axis local +X, origin at the thread tip on the axis; the
shoulder at SHOULDER_X, the bottom dome's tip at ROD_LENGTH.
"""

from __future__ import annotations

from _gtol_cylinder import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from mg_magnifying_vertical_rod_geom import (
    BODY_LENGTH,
    DOME_R,
    RELIEF_START_X,
    ROD_DIA,
    ROD_LENGTH,
    SHOULDER_X,
    TIP_CHAMFER,
)
from mg_rod_clamp_joint import (
    DIE_RUNOUT,
    RELIEF_DIA,
    RELIEF_DIA_BAND,
    RELIEF_WIDTH,
    RELIEF_WIDTH_BAND,
    ROD_THREAD_LEN,
    ROD_THREAD_LEN_BAND,
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
    "DRAWING_BANDS",
    "DRAWING_DIMENSIONS",
    "DRAWING_NOTES",
    "DRAWING_PRECISION",
    "FULL_THREAD_END_X",
    "FULL_THREAD_START_X",
    "ISO_VIEW_NOTE",
    "RELIEF_DIA",
    "RELIEF_DIA_BAND",
    "RELIEF_START_X",
    "RELIEF_WIDTH",
    "RELIEF_WIDTH_BAND",
    "ROD_DIA",
    "ROD_LENGTH",
    "ROD_THREAD_LEN",
    "ROD_THREAD_LEN_BAND",
    "SHOULDER_X",
    "SURFACE_FINISHES",
    "THREAD",
    "THREAD_BASIC_MINOR",
    "THREAD_CALLOUT",
    "THREAD_MAJOR",
    "THREAD_PITCH",
    "TIP_CHAMFER",
    "TIP_INCOMPLETE",
]

# Full thread on the rod (drawing-guidelines.md rule 18 counts full thread
# only): from one pitch behind the tip chamfer to the relief's far edge; the
# die's run-out lies in the relief (mg_rod_clamp_joint checks its width).
FULL_THREAD_START_X = TIP_INCOMPLETE
FULL_THREAD_END_X = RELIEF_START_X

# ONE revolved profile. The thread end reads from the shoulder, the seating
# face that plumbs the rod (drawing-guidelines.md rule 10, functional datum):
# the thread length and the body length both baseline from it. The overall
# (thread + body) is a reference carried in the note, never a third control.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RodProfile": {
        "RodDia",
        "BodyLength",
        "DomeR",
        "ThreadLength",
        "ReliefWidth",
        "ReliefDia",
    },
}
DRAWING_BANDS: dict[tuple[str, str], tuple[float, float]] = {
    ("RodProfile", "ThreadLength"): ROD_THREAD_LEN_BAND,
    ("RodProfile", "ReliefWidth"): RELIEF_WIDTH_BAND,
    ("RodProfile", "ReliefDia"): RELIEF_DIA_BAND,
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RodProfile": {
        "RodDia": 1,
        "BodyLength": 1,
        "DomeR": 1,
        "ThreadLength": 2,
        "ReliefWidth": 2,
        "ReliefDia": 2,
    },
}

# drawing-guidelines.md rule 7: few notes, each flagged by its function.
DRAWING_NOTES = "\n".join(
    (
        f"Ø{ROD_DIA:g} ROUND BAR, ONE PIECE; OVERALL LENGTH ({ROD_LENGTH:g}) REF.",
        "THREADED END SCREWS INTO MHA-MG-002 AND SEATS ON THE SHOULDER:",
        "SHOULDER FACE SQUARE TO THE AXIS AND FLAT (IT PLUMBS THE ROD).",
        f"BOTTOM END A FULL HEMISPHERE (R{DOME_R:g} = ROD RADIUS).",
    )
)
ISO_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"

# drawing-guidelines.md rule 6: the output fixture slides along the Ø5 OD.
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = (
    SurfaceFinishControl("mg_vrod_slide", MACHINED_UM, CylinderFace(ROD_DIA)),
)

if (
    abs(SHOULDER_X - ROD_THREAD_LEN) > 1e-9
    or abs(ROD_LENGTH - SHOULDER_X - BODY_LENGTH) > 1e-9
):
    raise AssertionError("MHA-MG-004 printed lengths do not sum to the overall")
if not 0.0 < TIP_CHAMFER < FULL_THREAD_START_X < FULL_THREAD_END_X < SHOULDER_X:
    raise AssertionError("MHA-MG-004 full-thread stations out of order")
if abs(SHOULDER_X - RELIEF_START_X - RELIEF_WIDTH) > 1e-9:
    raise AssertionError("MHA-MG-004 relief does not end on the shoulder")
