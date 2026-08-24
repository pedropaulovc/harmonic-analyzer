r"""Pure-data dimensional contract shared by the cone pivot screw and drawing.

The modeled screw represents McMaster-Carr 91829A560, a stock slotted 18-8
stainless precision shoulder screw.  Its 6.35 mm shoulder carries the locally
relieved swing-platform bearing with deliberate axial clearance; a distinct
#10-24 UNC-2A tail engages the matching blind UNC-2B base seat.
"""

from __future__ import annotations

from _fastener_catalog import fastener
from _gtol_spec import CylinderFace
from _holes import TAP_DRILL_MM, THREAD_MAJOR_MM
from _surface_finish import GROUND_UM, SurfaceFinishControl
from cone_swing_platform_spec import PIVOT_BEARING_THICKNESS


_SPEC = fastener("cone-pivot-screw")

SUPPLIER = "McMaster-Carr"
SUPPLIER_PART_NUMBER = "91829A560"
HEAD_DIA = 9.525
HEAD_T = 4.7625
SLOT_W = 1.6
SLOT_D = 1.2

AXIAL_CLEARANCE = 0.25
SHOULDER_DIA = _SPEC.model_diameter_mm
SHOULDER_LEN = 6.35
UNDERHEAD_LEN = _SPEC.length_mm
THREAD_TAIL_LEN = UNDERHEAD_LEN - SHOULDER_LEN
THREAD = _SPEC.thread
THREAD_DESIGNATION = f"{THREAD} UNC-2A"
THREAD_PITCH = 25.4 / int(THREAD.rsplit("-", 1)[1])
THREAD_LENGTH_TOL = 0.10
THREAD_RUNOUT_PITCHES = 1.0
DISTAL_CHAMFER = 0.50
MIN_FULL_FORM = 6.00
# The manufacturing contract remains the nominal external thread.  The CAD body
# uses the matching tap-drill envelope so the simplified male/female solids do
# not overlap; the native cosmetic thread and drawing carry the #10-24 form.
THREAD_MAJOR_DIA = THREAD_MAJOR_MM[THREAD]
THREAD_TAP_DRILL_DIA = TAP_DRILL_MM[THREAD]
THREAD_SOLID_DIA = THREAD_TAP_DRILL_DIA

SURFACE_FINISHES = (
    SurfaceFinishControl(
        "ground_shoulder",
        GROUND_UM,
        CylinderFace(SHOULDER_DIA, contains_y_mm=-SHOULDER_LEN / 2.0),
    ),
)

if abs(SHOULDER_LEN - PIVOT_BEARING_THICKNESS - AXIAL_CLEARANCE) > 1e-9:
    raise ValueError("cone pivot shoulder no longer provides its axial clearance")
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
        f"PURCHASED {SUPPLIER} {SUPPLIER_PART_NUMBER}; DIMENSIONS SHOWN ARE "
        "INSPECTION REFERENCE.",
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
