r"""Pure-data dimensional contract shared by the cone pivot screw and drawing.

The screw is a made, slotted shoulder screw.  Its ground shoulder carries the
6.35 mm swing plate with deliberate axial clearance; a distinct 1/4-20 UNC-2A
tail engages the matching blind UNC-2B base seat.  The catalog owns the thread,
overall under-head length, and shoulder diameter.
"""

from __future__ import annotations

from _fastener_catalog import fastener
from _holes import TAP_DRILL_MM


_SPEC = fastener("cone-pivot-screw")

HEAD_DIA = 9.5
HEAD_T = 3.0
SLOT_W = 1.6
SLOT_D = 1.2

PLATFORM_THICKNESS = 6.35
AXIAL_CLEARANCE = 0.25
SHOULDER_DIA = _SPEC.model_diameter_mm
SHOULDER_LEN = PLATFORM_THICKNESS + AXIAL_CLEARANCE
UNDERHEAD_LEN = _SPEC.length_mm
THREAD_TAIL_LEN = UNDERHEAD_LEN - SHOULDER_LEN
THREAD = _SPEC.thread
THREAD_DESIGNATION = f"{THREAD} UNC-2A"
# Thread geometry is omitted.  The smaller tail cylinder is a reference
# envelope at the mating tap-drill diameter, consistent with the repo's other
# simplified threaded fasteners; the drawing thread callout controls the part.
THREAD_REF_DIA = TAP_DRILL_MM[THREAD]

if THREAD_TAIL_LEN < SHOULDER_DIA:
    raise ValueError(
        "cone pivot thread engagement must be at least one nominal diameter"
    )

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDiaDim"},
    "ShoulderProfile": {"ShoulderDiaDim"},
    "Head": {"HeadHt"},
    "Shoulder": {"ShoulderLg"},
    "ThreadTail": {"ThreadLg"},
}

DRAWING_NOTES = "\n".join(
    (
        f"{THREAD_DESIGNATION} PER ASME B1.1-2024.",
        f"THREAD TAIL {THREAD_TAIL_LEN:.2f} MIN FULL THREAD; THREAD GEOMETRY "
        "OMITTED IN VIEWS.",
        f"GROUND SHOULDER Ø{SHOULDER_DIA:.2f} -0.02/-0.05 X "
        f"{SHOULDER_LEN:.2f} +/-0.05.",
        f"SHOULDER LENGTH PROVIDES {AXIAL_CLEARANCE:.2f} NOMINAL AXIAL "
        f"CLEARANCE OVER A {PLATFORM_THICKNESS:.2f} PLATE.",
        f"HEAD Ø{HEAD_DIA:.2f} +/-0.10 X {HEAD_T:.2f} +/-0.10.",
        f"STRAIGHT DRIVER SLOT {SLOT_W:.2f} +/-0.10 WIDE X "
        f"{SLOT_D:.2f} +/-0.10 DEEP, CENTERED.",
        "SLOT EXTENDS ACROSS FULL HEAD DIAMETER; OPEN AT BOTH SIDES.",
        "UNDERHEAD FILLET R0.25 MAX; THREAD RUNOUT 2P MAX.",
        "SHOULDER AND HEAD OD TOTAL RUNOUT 0.05 TO THREAD PITCH-DIAMETER AXIS.",
        "BEARING FACE AND SHOULDER END PERPENDICULAR 0.05 TO THREAD AXIS.",
    )
)
END_VIEW_NOTE = "SHOULDER-END VIEW"
