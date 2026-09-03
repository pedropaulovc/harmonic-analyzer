r"""Pure-data dimensional contract shared by the gooseneck set screw and drawing.

PURE DATA: modeled nominals + the marked-dimension map, so one edit rebuilds
both the SLDPRT and SLDDRW recipe.  Thread designation and the catalog-owned
shank nominals are re-derived from the fastener catalog row -- ONE hardware
source; the drawing never invents a thread the part does not build.

Period square-head set screw (book p.45 spec; reuses the deleted
gooseneck-clamp's screw spec): drives along +X through the top-frame casting's
tapped 1/4-20 hub hole and grips the O16 gooseneck post, replacing the retired
clamp.  Black oxide, wrench-driven square head -- no driver slot.
"""

from __future__ import annotations

from _fastener_catalog import fastener
from _fastener_notes import square_head_notes, thread_length_note


_SPEC = fastener("gooseneck-set-screw")

HEAD_AF = 10.0  # square head across-flats
HEAD_H = 6.0  # square head height

SHANK_DIA = _SPEC.model_diameter_mm  # 1/4-20 modeled thread minor diameter
SHANK_LEN = _SPEC.length_mm  # nominal under-head length (16)
THREAD = _SPEC.thread  # "1/4-20"
THREAD_DESIGNATION = f"{THREAD} UNC"  # leadered to the shank on the side view

# The square head is a polygon (no single diameter), so the end view carries
# the sketch across-flats width; the side view carries the two lengths as the
# head/shank extrude DEPTH dimensions (named HeadHt/ShankLg in the build) --
# an axis-along-Y screw projects edge-on silhouettes for the shoulder and tip
# that SolidWorks will not point-select.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadWDim"},
    "Head": {"HeadHt"},
    "Shank": {"ShankLg"},
}
END_VIEW_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadWDim"},
}
SIDE_VIEW_DIMENSIONS: dict[str, set[str]] = {
    "Head": {"HeadHt"},
    "Shank": {"ShankLg"},
}

DRAWING_NOTES = "\n".join(
    (
        *thread_length_note(thread=THREAD, underhead_length_mm=SHANK_LEN),
        *square_head_notes(point="PLAIN FLAT"),
    )
)
END_VIEW_NOTE = "WRENCH-FLATS VIEW"
