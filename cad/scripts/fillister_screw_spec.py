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
from _fastener_notes import slotted_round_head_notes, thread_control_notes


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
THREAD_DESIGNATION = f"{THREAD} UNC-2A"  # external screw thread, class 2A

# Two named model diameters, marked for the head-end view; the head-height and
# under-head length are drawing-native linear dimensions on the side view (the
# extrude depths carry no named display dim, exactly as the crank-pin slice adds
# its end diameters natively).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDia"},
    "ShankProfile": {"ShankDia"},
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
            axis_control_style="native",
            size_control_style="dimensions",
        ),
        "DATUM FEATURE A IS THE #4-40 UNC-2A THREAD.",
        "DATUM AXIS A IS THE PITCH-CYLINDER AXIS.",
        "CUSTOM CYLINDRICAL SLOTTED HEAD; B18.6.3 HEAD DIMENSIONS DO NOT APPLY.",
        "ALL UNSPECIFIED HEAD EDGES PER TITLE BLOCK.",
    )
)
END_VIEW_NOTE = "DRIVER-FACE VIEW"
