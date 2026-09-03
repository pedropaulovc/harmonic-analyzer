r"""Pure-data dimensional contract shared by the cone-lock-knob part and drawing.

PURE DATA: the turned-knob nominals and marked-dimension map live here so a
change rebuilds both the SLDPRT and SLDDRW recipes without making the drawing
import the part build implementation.  The clamp-stud nominals come from the
fastener catalog row (also pure data) so the knob keeps one thread source.
"""

from __future__ import annotations

from _fastener_catalog import fastener
from _surface_finish import SurfaceFinishControl


_STUD = fastener("cone-lock-knob")

WASHER_DIA = 18.0  # clamp washer flange, seats on the plate top
WASHER_T = 1.5  # no band: an ordinary clamp flange under the title block .XX
BODY_DIA = 13.0  # knob body -- ONE straight wall (t00411: no mid step)
BODY_TOP = 13.5  # body top above the washer seat; height ~ diameter
DOME_R = 5.0  # top-edge fillet radius: the domed crown
DOME_MAJOR_R = BODY_DIA / 2.0 - DOME_R
DOME_CENTER_Y = BODY_TOP - DOME_R
STUD_DIA = _STUD.model_diameter_mm  # 1/4" clamp stud
STUD_LEN = _STUD.length_mm  # plate thickness exactly: stud ends flush with base top
STUD_THREAD = _STUD.thread  # 1/4-20
OVERALL_LENGTH = BODY_TOP + STUD_LEN  # dome apex to stud end, a REFERENCE on the print

# No roughness callouts: nothing runs on the knob -- the dome is a hand grip
# and the stud is a clamp thread -- so the title block's Ra 3.2 covers every
# face (cad/docs/drawing-simplicity-policy.md rule 5).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "WasherProfile": {"WasherDia"},
    "Washer": {"WasherT"},
    "BodyProfile": {"BodyDia"},
    "Body": {"BodyTop"},
    "DomeCrown": {"DomeR"},
    "StudProfile": {"StudDia"},
    "Stud": {"StudLen"},
}

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).  The views define the
# turned profile; setup and tooling are the machinist's call.
DRAWING_NOTES = "\n".join(
    (
        "THREAD RELIEF AT THE STUD SHOULDER PERMITTED, 1.0 WIDE X 0.4 DEEP MAX.",
        "MASK THE THREAD FOR PLATING; DIMENSIONS APPLY BEFORE PLATING.",
    )
)
