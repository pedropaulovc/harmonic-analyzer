r"""Pure-data dimensional contract shared by the clamp screw and drawing.

PURE DATA: modeled nominals + the marked-dimension map, so one edit rebuilds
both the SLDPRT and SLDDRW recipe.  Thread designation and the catalog-owned
shank nominals are re-derived from the fastener catalog row -- ONE hardware
source; the drawing never invents a thread the part does not build.
"""

from __future__ import annotations

from _fastener_catalog import fastener


_SPEC = fastener("clamp-screw")

HEAD_DIA = 8.0  # large slotted head on the bar front (low)
HEAD_H = 2.5

SHANK_DIA = _SPEC.model_diameter_mm  # #8-32 modeled thread minor diameter
SHANK_LEN = _SPEC.length_mm  # nominal under-head length
THREAD = _SPEC.thread  # "#8-32"
THREAD_DESIGNATION = f"{THREAD} UNC-2A"

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDia"},
    "ShankProfile": {"ShankDia"},
}

DRAWING_NOTES = "\n".join(
    (
        f"COMMERCIAL {THREAD_DESIGNATION} SLOTTED FILLISTER-HEAD MACHINE SCREW, "
        f"{SHANK_LEN:g} LONG, PER ASME B18.6.3, ACCEPTABLE IN PLACE OF A "
        "MADE PART.",
        "SHANK MODELED AT THREAD MINOR DIA; THREADS OMITTED FOR CLARITY.",
        "HEAD CARRIES A STRAIGHT DRIVER SLOT PER THE HEAD-END VIEW.",
    )
)
END_VIEW_NOTE = "HEAD-END VIEW"
