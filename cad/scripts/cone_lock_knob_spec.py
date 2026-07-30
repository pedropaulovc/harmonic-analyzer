r"""Pure-data dimensional contract shared by the cone-lock-knob part and drawing.

PURE DATA: the turned-knob nominals and marked-dimension map live here so a
change rebuilds both the SLDPRT and SLDDRW recipes without making the drawing
import the part build implementation.  The clamp-stud nominals come from the
fastener catalog row (also pure data) so the knob keeps one thread source.
"""

from __future__ import annotations

from _fastener_catalog import fastener
from _gtol_spec import TorusFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl


_STUD = fastener("cone-lock-knob")

WASHER_DIA = 18.0  # clamp washer flange, seats on the plate top
WASHER_T = 1.5
WASHER_THICKNESS_TOLERANCE_MM = 0.10
BODY_DIA = 13.0  # knob body -- ONE straight wall (t00411: no mid step)
BODY_TOP = 13.5  # body top above the washer seat; height ~ diameter
DOME_R = 5.0  # top-edge fillet radius: the domed crown
DOME_MAJOR_R = BODY_DIA / 2.0 - DOME_R
DOME_CENTER_Y = BODY_TOP - DOME_R
STUD_DIA = _STUD.model_diameter_mm  # 1/4" clamp stud
STUD_LEN = _STUD.length_mm  # plate thickness exactly: stud ends flush with base top
STUD_THREAD = _STUD.thread  # 1/4-20

SURFACE_FINISHES = (
    SurfaceFinishControl(
        "dome_crown",
        MACHINED_UM,
        TorusFace(
            DOME_MAJOR_R,
            DOME_R,
            center_mm=(0.0, DOME_CENTER_Y, 0.0),
        ),
    ),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "WasherProfile": {"WasherDia"},
    "Washer": {"WasherT"},
    "BodyProfile": {"BodyDia"},
    "Body": {"BodyTop"},
    "DomeCrown": {"DomeR"},
    "StudProfile": {"StudDia"},
    "Stud": {"StudLen"},
}

DRAWING_NOTES = "\n".join(
    (
        "TURN COMPLETE IN ONE SETUP; FORM DOME R5 BY RADIUS TOOL OR CNC;",
        "  DOME TANGENT TO BODY OD, O3 FLAT AT APEX (REF).",
        f"THREAD STUD {STUD_THREAD} UNC-2A; THREAD RELIEF AT SHOULDER",
        "  PERMITTED, 1.0 WIDE X 0.4 DEEP MAX.",
        "CHROME PLATE PER ASTM B456 SC2 AFTER MACHINING; MASK THREAD;",
        "  DIMENSIONS APPLY BEFORE PLATING.",
    )
)
