r"""Pure-data dimensional contract shared by the clamp screw and drawing.

PURE DATA: modeled nominals + the marked-dimension map, so one edit rebuilds
both the SLDPRT and SLDDRW recipe.  Thread designation and the catalog-owned
shank nominals are re-derived from the fastener catalog row -- ONE hardware
source; the drawing never invents a thread the part does not build.
"""

from __future__ import annotations

from _fastener_catalog import fastener
from _fastener_notes import slotted_round_head_notes, thread_control_notes


_SPEC = fastener("clamp-screw")

HEAD_DIA = 8.0  # large slotted head on the bar front (low)
HEAD_H = 2.5
SLOT_W = 1.2
SLOT_D = 1.0

SHANK_DIA = _SPEC.model_diameter_mm  # #8-32 modeled thread minor diameter
SHANK_LEN = _SPEC.length_mm  # nominal under-head length
THREAD = _SPEC.thread  # "#8-32"
THREAD_DESIGNATION = f"{THREAD} UNC-2A"

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDia"},
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
