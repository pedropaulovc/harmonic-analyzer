r"""Pure-data dimensional contract shared by the cone tip pinch screw and drawing.

PURE DATA: modeled nominals + the marked-dimension map (the slot-cut builder
names its diameters ``HeadDiaDim``/``ShankDiaDim``).  Thread designation and the
catalog-owned shank nominals are re-derived from the fastener catalog row -- ONE
hardware source.
"""

from __future__ import annotations

from _fastener_catalog import fastener
from _fastener_notes import slotted_round_head_notes, thread_control_notes


_SPEC = fastener("cone-tip-pinch-screw")

HEAD_DIA = 4.8  # slotted head OD
HEAD_T = 2.0  # head thickness
SLOT_W = 0.8
SLOT_D = 0.8

SHANK_DIA = _SPEC.model_diameter_mm  # #3-48 modeled thread minor diameter
SHANK_LEN = _SPEC.length_mm  # nominal under-head length
THREAD = _SPEC.thread  # "#3-48"
THREAD_DESIGNATION = f"{THREAD} UNC-2A"

DRAWING_DIMENSIONS: dict[str, set[str]] = {}

DRAWING_NOTES = "\n".join(
    (
        "APPLICATION NAME ONLY: FLAT-END PINCH SCREW; NO CONICAL POINT.",
        *thread_control_notes(
            thread=THREAD,
            thread_designation=THREAD_DESIGNATION,
            underhead_length_mm=SHANK_LEN,
        ),
        *slotted_round_head_notes(
            head_dia_mm=HEAD_DIA,
            head_height_mm=HEAD_T,
            slot_width_mm=SLOT_W,
            slot_depth_mm=SLOT_D,
        ),
    )
)
END_VIEW_NOTE = "DRIVER-FACE VIEW"
