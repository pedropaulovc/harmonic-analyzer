r"""Pure-data dimensional contract shared by the cone pivot screw and drawing.

The screw is a made, slotted shoulder screw.  Its ground shoulder carries the
6.35 mm swing plate with deliberate axial clearance; a distinct #10-24 UNC-2A
tail engages the matching blind UNC-2B base seat.  The catalog owns the thread,
overall under-head length, and shoulder diameter.
"""

from __future__ import annotations

from _fastener_catalog import fastener
from _gtol_spec import CylinderFace
from _holes import TAP_DRILL_MM, THREAD_MAJOR_MM
from _surface_finish import GROUND_UM, SurfaceFinishControl


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
THREAD_PITCH = 25.4 / int(THREAD.rsplit("-", 1)[1])
THREAD_LENGTH_TOL = 0.10
THREAD_RUNOUT_PITCHES = 1.0
DISTAL_CHAMFER = 0.50
MIN_FULL_FORM = 6.00
# The manufacturing contract remains the nominal external thread. The CAD body
# retains the matching tap-drill envelope to avoid simplified male/female solid
# overlap. A boss cosmetic thread draws its MINOR diameter: it cannot restore
# the absent nominal-major solid outline. Changing that outline requires a
# separate assembly-fit/interference decision, not an annotation correction.
THREAD_MAJOR_DIA = THREAD_MAJOR_MM[THREAD]
THREAD_TAP_DRILL_DIA = TAP_DRILL_MM[THREAD]
THREAD_SOLID_DIA = THREAD_TAP_DRILL_DIA
# Installed SOLIDWORKS R2026x Toolbox swbrowser.sldedb: AI_DATA_THRD row
# full_size='#10-24', THD_MINOR='.1404' inches. AI_Type_CThread names its type
# 'Machine Threads'. This is the vendor cosmetic depiction, not a new ASME
# dimensional tolerance. Keep unsupported catalog changes loud.
if THREAD != "#10-24":
    raise ValueError("cone pivot cosmetic-thread vendor row only covers #10-24")
THREAD_COSMETIC_MINOR_DIA = 0.1404 * 25.4
THREAD_COSMETIC_TYPE = "Machine Threads"
if not 0 < THREAD_COSMETIC_MINOR_DIA < THREAD_SOLID_DIA:
    raise ValueError("cone pivot cosmetic minor diameter must fit its solid envelope")

SURFACE_FINISHES = (
    SurfaceFinishControl(
        "ground_shoulder",
        GROUND_UM,
        CylinderFace(SHOULDER_DIA, contains_y_mm=-SHOULDER_LEN / 2.0),
    ),
)

if THREAD_TAIL_LEN < THREAD_MAJOR_DIA:
    raise ValueError(
        "cone pivot thread engagement must be at least one nominal diameter"
    )
if THREAD_MAJOR_DIA >= SHOULDER_DIA:
    raise ValueError("cone pivot thread must leave a positive annular shoulder seat")
if THREAD_SOLID_DIA >= THREAD_MAJOR_DIA:
    raise ValueError(
        "cone pivot solid thread envelope must remain below major diameter"
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
    "SlotProfile": {"SlotWDim"},
    "DriverSlot": {"SlotDepth"},
}

DRAWING_NOTES = "\n".join(
    (
        f"{THREAD_DESIGNATION} PER ASME B1.1-2024; DATUM A IS THE AXIS "
        "DERIVED FROM THE EXTERNAL THREAD PITCH CYLINDER.",
        f"{MIN_FULL_FORM:.2f} MIN FULL-FORM THREAD WITHIN DIMENSIONED THREAD LENGTH.",
        f"INCOMPLETE THREAD/RUNOUT AT SHOULDER {THREAD_RUNOUT_PITCHES:g}P MAX.",
        "SLOT EXTENDS ACROSS FULL HEAD DIAMETER; OPEN AT BOTH SIDES.",
        "SLOT FLOOR CORNERS R0.05-0.15.",
        "MANDATORY UNDERHEAD FILLET R0.10-0.25.",
        f"MANDATORY DISTAL START CHAMFER 0.25-{DISTAL_CHAMFER:.2f} X 45°.",
        "TITLE-BLOCK EDGE OVERRIDE: 0.05-0.10; EXCEPT THREAD, GROUND OD, SLOT FLOOR.",
    )
)
END_VIEW_NOTE = (
    f"THREAD-END VIEW: INNER CIRCLE = {THREAD} EXTERNAL THREAD\n"
    "MIDDLE CIRCLE = GROUND SHOULDER OD"
)


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "head bearing face perpendicularity": "0.05",
    "shoulder end perpendicularity": "0.05",
    "slot median-plane position": "0.10",
    "shoulder total runout": "0.05",
    "head total runout": "0.05",
}
