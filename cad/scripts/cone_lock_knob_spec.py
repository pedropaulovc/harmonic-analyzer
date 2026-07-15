r"""Pure-data dimensional contract shared by the cone-lock-knob part and drawing.

PURE DATA: the turned-knob nominals and marked-dimension map live here so a
change rebuilds both the SLDPRT and SLDDRW recipes without making the drawing
import the part build implementation.  The clamp-stud nominals come from the
fastener catalog row (also pure data) so the knob keeps one thread source.
"""

from __future__ import annotations

from _fastener_catalog import fastener


_STUD = fastener("cone-lock-knob")

WASHER_DIA = 18.0  # clamp washer flange, seats on the plate top
WASHER_T = 1.5
BODY_DIA = 13.0  # knob body -- ONE straight wall (t00411: no mid step)
BODY_TOP = 13.5  # body top above the washer seat; height ~ diameter
DOME_R = 5.0  # top-edge fillet radius: the domed crown
STUD_DIA = _STUD.model_diameter_mm  # 1/4" clamp stud
STUD_LEN = _STUD.length_mm  # plate thickness exactly: stud ends flush with base top
STUD_THREAD = _STUD.thread  # 1/4-20

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
        "UOS, DIMENSIONS IN MM: +/-0.25. DEBURR; BREAK EDGES 0.15 MAX.",
        "TURN COMPLETE IN ONE SETUP; FORM DOME R5 BY RADIUS TOOL OR CNC.",
        f"THREAD STUD {STUD_THREAD} UNC-2A FULL LENGTH TO WASHER FACE.",
        "CHROME PLATE ALL OVER AFTER MACHINING; MASK STUD THREAD.",
    )
)
