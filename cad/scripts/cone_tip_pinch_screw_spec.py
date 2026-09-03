r"""Pure-data dimensional contract shared by the cone tip pinch screw and drawing.

PURE DATA: modeled nominals + the marked-dimension map (the slot-cut builder
names its head diameter ``HeadDiaDim``, its extrude depths ``HeadHt``/
``ShankLg``, its slot width ``SlotWDim`` and the slot cut depth
``SlotDepth``).  Thread designation and the catalog-owned shank nominals are
re-derived from the fastener catalog row -- ONE hardware source.
"""

from __future__ import annotations

from _fastener_catalog import fastener
from _fastener_notes import slotted_head_notes, thread_length_note


_SPEC = fastener("cone-tip-pinch-screw")

HEAD_DIA = 4.8  # slotted head OD
HEAD_T = 2.0  # head thickness
SLOT_W = 0.8
SLOT_D = 0.8

SHANK_DIA = _SPEC.model_diameter_mm  # #3-48 modeled thread minor diameter
SHANK_LEN = _SPEC.length_mm  # nominal under-head length
THREAD = _SPEC.thread  # "#3-48"
THREAD_DESIGNATION = f"{THREAD} UNC"  # leadered to the shank on the side view

# The head-end view carries the head diameter; the side view the two
# extrude-depth lengths; the slot-profile (*Right) view the slot width and
# depth, where the notch is visible rather than a hidden line.  The shank
# cylinder is the modeled thread minor, so it is never dimensioned: the
# thread leader owns it.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDiaDim"},
    "Head": {"HeadHt"},
    "Shank": {"ShankLg"},
    "SlotProfile": {"SlotWDim"},
    "DriverSlot": {"SlotDepth"},
}

DRAWING_NOTES = "\n".join(
    (
        *thread_length_note(thread=THREAD, underhead_length_mm=SHANK_LEN),
        *slotted_head_notes(),
    )
)
END_VIEW_NOTE = "DRIVER-FACE VIEW"
