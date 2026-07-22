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
THREAD_PITCH = 25.4 / 20.0
THREAD_LENGTH_TOL = 0.10
THREAD_RUNOUT_PITCHES = 1.0
DISTAL_CHAMFER = 0.50
MIN_FULL_FORM = 6.00
# Thread geometry is omitted.  The smaller tail cylinder is a reference
# envelope at the mating tap-drill diameter, consistent with the repo's other
# simplified threaded fasteners; the drawing thread callout controls the part.
THREAD_REF_DIA = TAP_DRILL_MM[THREAD]

if THREAD_TAIL_LEN < SHOULDER_DIA:
    raise ValueError(
        "cone pivot thread engagement must be at least one nominal diameter"
    )
if (
    THREAD_TAIL_LEN
    - THREAD_LENGTH_TOL
    - THREAD_RUNOUT_PITCHES * THREAD_PITCH
    - DISTAL_CHAMFER
    < MIN_FULL_FORM
):
    raise ValueError("cone pivot full-form thread requirement exceeds worst-case tail")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDiaDim"},
    "ShoulderProfile": {"ShoulderDiaDim"},
    "Head": {"HeadHt"},
    "Shoulder": {"ShoulderLg"},
    "ThreadTail": {"ThreadLg"},
}

DRAWING_NOTES = "\n".join(
    (
        f"{THREAD_DESIGNATION} PER ASME B1.1-2024; DATUM FEATURE A.",
        "DATUM A IS THE DERIVED THREAD PITCH-DIAMETER AXIS.",
        f"THREAD LENGTH {THREAD_TAIL_LEN:.2f}; {MIN_FULL_FORM:.2f} MIN FULL-FORM THREAD.",
        f"INCOMPLETE THREAD/RUNOUT AT SHOULDER {THREAD_RUNOUT_PITCHES:g}P MAX.",
        "THREAD GEOMETRY OMITTED IN VIEWS.",
        f"FUNCTIONAL INTERFACE: MATING PLATE THICKNESS {PLATFORM_THICKNESS:.2f} "
        f"MAX; {AXIAL_CLEARANCE:.2f} MIN AXIAL CLEARANCE.",
        "GROUND SHOULDER SURFACE Ra 0.8 MAX.",
        f"STRAIGHT DRIVER SLOT {SLOT_W:.2f} +/-0.10 WIDE X "
        f"{SLOT_D:.2f} +/-0.10 DEEP, CENTERED.",
        "SLOT EXTENDS ACROSS FULL HEAD DIAMETER; OPEN AT BOTH SIDES.",
        f"UNDERHEAD FILLET R0.25 MAX; DISTAL START CHAMFER {DISTAL_CHAMFER:.2f} "
        "X 45° MAX.",
    )
)
END_VIEW_NOTE = "SHOULDER-END VIEW"
