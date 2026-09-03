r"""Pure-data dimensional contract shared by the fillister screw and drawing.

PURE DATA: the modeled screw nominals and the marked-dimension map live here so
one edit rebuilds both the SLDPRT and the SLDDRW recipe without the drawing
importing the part build.  The thread designation and the two catalog-owned
nominals (shank minor diameter, shank length) are re-derived from the fastener
catalog row so the screw keeps ONE hardware source -- the drawing never invents
a thread it does not build.
"""

from __future__ import annotations

from _fastener_catalog import fastener
from _fastener_notes import slotted_head_notes, thread_length_note


_SPEC = fastener("fillister-screw")

# Modeled head geometry (build_fillister_screw.py owns the same literals).
HEAD_DIA = 5.5  # fillister head OD (low)
HEAD_H = 2.2  # head height
SLOT_W = 0.8
SLOT_D = 0.7

# Catalog-owned: the shank is the modeled thread MINOR diameter and the screw's
# nominal (under-head) length.  Re-derived, never duplicated.
SHANK_DIA = _SPEC.model_diameter_mm  # #4-40 modeled thread minor diameter
SHANK_LEN = _SPEC.length_mm  # nominal under-head length
THREAD = _SPEC.thread  # "#4-40"
THREAD_DESIGNATION = f"{THREAD} UNC"  # leadered to the shank on the side view

# The head diameter on the driver-face view; the head height, under-head
# length and the driver slot (width across the notch, depth into the face)
# on the profile view, all as marked model dimensions.  The shank cylinder is
# the modeled thread minor, so it is never dimensioned: the thread leader
# owns it.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDia"},
    "Head": {"HeadHt"},
    "Shank": {"ShankLg"},
    "DriverSlotProfile": {"SlotWidth"},
    "DriverSlot": {"SlotDepth"},
}

# Notes: thread extent and slot location only -- every size is a dimension
# and the title block carries every tolerance (cad/docs/
# drawing-simplicity-policy.md rule 6).
DRAWING_NOTES = "\n".join(
    (
        *thread_length_note(thread=THREAD, underhead_length_mm=SHANK_LEN),
        *slotted_head_notes(),
    )
)
END_VIEW_NOTE = "DRIVER-FACE VIEW"
