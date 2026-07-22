r"""Pure-data dimensional contract shared by the swing-stop screw and drawing.

PURE DATA: modeled nominals + the marked-dimension map (the slot-cut builder
names its diameters ``HeadDiaDim``/``ShankDiaDim``).  The shank is one
continuous cylinder (proud + embedded segments, same Ø), so the under-head
length is its full length.  Thread designation and the catalog-owned shank
nominals are re-derived from the fastener catalog row -- ONE hardware source.
"""

from __future__ import annotations

from _fastener_catalog import fastener
from _fastener_notes import slotted_round_head_notes, thread_control_notes


_SPEC = fastener("swing-stop-screw")

HEAD_DIA = 8.0  # slotted head OD
HEAD_T = 2.5  # head thickness
SLOT_W = 1.2
SLOT_D = 1.0

SHANK_DIA = _SPEC.model_diameter_mm  # #8-32 modeled thread minor diameter
SHANK_LEN = _SPEC.length_mm  # full shank (proud + embedded), the nominal length
THREAD = _SPEC.thread  # "#8-32"
THREAD_DESIGNATION = f"{THREAD} UNC-2A"

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDiaDim"},
}

DRAWING_NOTES = "\n".join(
    (
        *thread_control_notes(
            thread=THREAD,
            thread_designation=THREAD_DESIGNATION,
            underhead_length_mm=SHANK_LEN,
            length_control="note",
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
