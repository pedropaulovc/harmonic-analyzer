r"""Pure-data dimensional contract shared by the slotted screw and drawing.

PURE DATA: modeled nominals + the marked-dimension map, so one edit rebuilds
both the SLDPRT and SLDDRW recipe.  Thread designation and the catalog-owned
shank nominals are re-derived from the fastener catalog row -- ONE hardware
source; the drawing never invents a thread the part does not build.
"""

from __future__ import annotations

from _fastener_catalog import fastener
from _fastener_notes import slotted_head_notes, thread_length_note


_SPEC = fastener("slotted-screw")

HEAD_DIA = 8.0  # slotted cylindrical head (p.69, low)
HEAD_H = 2.5
SLOT_W = 1.2
SLOT_D = 1.0

SHANK_DIA = _SPEC.model_diameter_mm  # #8-32 modeled thread minor diameter
SHANK_LEN = _SPEC.length_mm  # nominal under-head length
THREAD = _SPEC.thread  # "#8-32"
THREAD_DESIGNATION = f"{THREAD} UNC"  # leadered to the shank on the side view

# The head-end view carries the head diameter; the side view the two lengths
# (the head/shank extrude DEPTH dimensions HeadHt/ShankLg -- an axis-along-Y
# screw projects edge-on circle silhouettes for the shoulder and tip that
# SolidWorks will not point-select); the slot-profile (*Right) view the slot
# width and depth, where the notch is visible rather than a hidden line.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDia"},
    "Head": {"HeadHt"},
    "Shank": {"ShankLg"},
    "DriverSlotProfile": {"SlotWidth"},
    "DriverSlot": {"SlotDepth"},
}
END_VIEW_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDia"},
}
SIDE_VIEW_DIMENSIONS: dict[str, set[str]] = {
    "Head": {"HeadHt"},
    "Shank": {"ShankLg"},
}
SLOT_VIEW_DIMENSIONS: dict[str, set[str]] = {
    "DriverSlotProfile": {"SlotWidth"},
    "DriverSlot": {"SlotDepth"},
}

DRAWING_NOTES = "\n".join(
    (
        *thread_length_note(thread=THREAD, underhead_length_mm=SHANK_LEN),
        *slotted_head_notes(),
    )
)
END_VIEW_NOTE = "DRIVER-FACE VIEW"
