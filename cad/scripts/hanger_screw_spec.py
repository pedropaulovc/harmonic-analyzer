r"""Pure-data dimensional contract shared by the hanger screw and drawing.

PURE DATA: modeled nominals + the marked-dimension map.  The hex head is a
polygon (no single diameter), so its across-flats is a drawing-native linear
on the head-end view; the head height and under-head length are the extrude
depths (``HeadHt``/``ShankLg``).  The shank cylinder is the modeled thread
minor, so it is never dimensioned: the thread designation is leadered to it.
Thread designation and the catalog-owned shank nominals are re-derived from
the fastener catalog row -- ONE hardware source.
"""

from __future__ import annotations

from _fastener_catalog import fastener
from _fastener_notes import thread_length_note


_SPEC = fastener("hanger-screw")

HEAD_AF = 7.0  # hex across-flats
HEAD_H = 2.5

SHANK_DIA = _SPEC.model_diameter_mm  # #6-32 modeled thread minor diameter
SHANK_LEN = _SPEC.length_mm  # nominal under-head length
THREAD = _SPEC.thread  # "#6-32"
THREAD_DESIGNATION = f"{THREAD} UNC"  # leadered to the shank on the side view

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HexHead": {"HeadHt"},
    "Shank": {"ShankLg"},
}

# The hex head is drawn (and named by the end-view label); the one fact a
# machinist cannot read off the views is how far the thread runs.
DRAWING_NOTES = "\n".join(
    thread_length_note(thread=THREAD, underhead_length_mm=SHANK_LEN)
)
END_VIEW_NOTE = "HEX-HEAD VIEW"
