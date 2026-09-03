r"""Pure-data dimensional contract shared by the cone pivot screw and drawing.

The screw is a made, slotted shoulder screw.  Its ground shoulder carries the
6.35 mm swing plate with deliberate axial clearance; a distinct #10-24 UNC
tail engages the matching blind UNC base seat.  The catalog owns the thread,
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
# The shoulder length sets the plate's running clearance, so it keeps a real
# band (the block's .XX +-0.51 could clamp the plate); +-0.10 leaves the
# clearance between 0.15 and 0.35 on a hobby lathe.
SHOULDER_LENGTH_TOL = 0.10
UNDERHEAD_LEN = _SPEC.length_mm
THREAD_TAIL_LEN = UNDERHEAD_LEN - SHOULDER_LEN
THREAD = _SPEC.thread
THREAD_DESIGNATION = f"{THREAD} UNC"  # leadered to the tail on the side view
THREAD_PITCH = 25.4 / int(THREAD.rsplit("-", 1)[1])
THREAD_LENGTH_TOL = 0.10
THREAD_RUNOUT_PITCHES = 1.0
DISTAL_CHAMFER = 0.50
UNDERHEAD_FILLET_MAX = 0.25
MIN_FULL_FORM = 6.00
# The manufacturing contract remains the nominal external thread.  The CAD body
# uses the matching tap-drill envelope so the simplified male/female solids do
# not overlap; the drawing carries the #10-24 form as a leadered designation.
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

# Both turned diameters and every length sit on the longitudinal (side)
# view; the slot on the slot-profile (*Right) view; the thread-end view
# carries only the ground shoulder's roughness symbol.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDiaDim"},
    "ShoulderProfile": {"ShoulderDiaDim"},
    "Head": {"HeadHt"},
    "Shoulder": {"ShoulderLg"},
    "ThreadTail": {"ThreadLg"},
    "SlotProfile": {"SlotWDim"},
    "DriverSlot": {"SlotDepth"},
}

# Leadered callouts on the side view: the edge forms at the two ends of the
# tail that no model feature carries.
THREAD_CHAMFER_CALLOUT = f"C{DISTAL_CHAMFER:.2f} THREAD START"
UNDERHEAD_FILLET_CALLOUT = f"R{UNDERHEAD_FILLET_MAX:.2f} MAX FILLET"

# Notes: every size and band is a model dimension or a leadered callout, so
# the notes carry only the ground shoulder (a process fact) and the slot
# location (cad/docs/drawing-simplicity-policy.md rule 6).  No datums, no
# frames: a pivot screw is not on the rule-3 allowlist; the one roughness
# symbol on the ground shoulder is the running surface.
DRAWING_NOTES = "\n".join(
    (
        "SHOULDER GROUND TO SIZE; PIVOT RUNNING SURFACE.",
        "SLOT CENTERED ON THE HEAD AXIS, FULL WIDTH OF HEAD; FLAT FLOOR.",
    )
)
END_VIEW_NOTE = "THREAD-END VIEW"
