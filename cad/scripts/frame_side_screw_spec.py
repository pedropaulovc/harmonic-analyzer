r"""Pure-data dimensional contract shared by the frame side screw and drawing.

PURE DATA: modeled nominals + the marked-dimension map, so one edit rebuilds
both the SLDPRT and SLDDRW recipe.  Thread designation and the catalog-owned
shank nominals are re-derived from the fastener catalog row -- ONE hardware
source; the drawing never invents a thread the part does not build.

Period-style slotted cheese-head machine screw: four of them pin the new
top-frame casting's corner bosses to the tube-frame columns (ch30 evidence).
Each screws into a tapped #10-24 boss hole behind a O9 x 0.5 spot-face; the
tip stops 0.15 short of the column surface.
"""

from __future__ import annotations

from _fastener_catalog import fastener
from _fastener_notes import slotted_round_head_notes, thread_control_notes


_SPEC = fastener("frame-side-screw")

HEAD_DIA = 7.0  # cheese head OD (seats on the O9 boss spot-face)
HEAD_H = 3.0  # cheese head height
SLOT_W = 1.4
SLOT_D = 1.2

SHANK_DIA = _SPEC.model_diameter_mm  # #10-24 modeled thread minor diameter
SHANK_LEN = _SPEC.length_mm  # nominal under-head length (12.7)
THREAD = _SPEC.thread  # "#10-24"
THREAD_DESIGNATION = f"{THREAD} UNC-2A"

# The head-end view carries the head diameter; the side view carries the two
# lengths.  The lengths are the head/shank extrude DEPTH dimensions (named
# HeadHt/ShankLg in the build) inserted as model dims -- an axis-along-Y screw
# projects edge-on circle silhouettes for the shoulder and tip that SolidWorks
# will not point-select, so a drawing-native edge dimension cannot pick them.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDia"},
    "Head": {"HeadHt"},
    "Shank": {"ShankLg"},
}
END_VIEW_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDia"},
}
SIDE_VIEW_DIMENSIONS: dict[str, set[str]] = {
    "Head": {"HeadHt"},
    "Shank": {"ShankLg"},
}

DRAWING_NOTES = "\n".join(
    (
        *thread_control_notes(
            thread=THREAD,
            thread_designation=THREAD_DESIGNATION,
            underhead_length_mm=SHANK_LEN,
        ),
        *slotted_round_head_notes(
            head_dia_mm=HEAD_DIA,
            head_height_mm=HEAD_H,
            slot_width_mm=SLOT_W,
            slot_depth_mm=SLOT_D,
        ),
    )
)
END_VIEW_NOTE = "DRIVER-FACE VIEW"
