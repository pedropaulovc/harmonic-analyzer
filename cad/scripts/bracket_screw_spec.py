r"""Pure-data dimensional contract shared by the bracket screw and drawing.

PURE DATA: modeled nominals + the marked-dimension map, so one edit rebuilds
both the SLDPRT and SLDDRW recipe.  Thread designation and the catalog-owned
shank nominals are re-derived from the fastener catalog row -- ONE hardware
source; the drawing never invents a thread the part does not build.
"""

from __future__ import annotations

from _fastener_catalog import fastener


_SPEC = fastener("bracket-screw")

HEAD_DIA = 8.0  # large slotted head on the bracket back (low)
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
        f"{THREAD_DESIGNATION} FULL THREAD OVER {SHANK_LEN:.2f} UNDER-HEAD LENGTH; "
        "THREAD FORM, RUNOUT, AND LIMITS PER ASME B1.1.",
        "THREAD GEOMETRY OMITTED IN VIEWS; CYLINDRICAL SHANK OUTLINE IS "
        "REFERENCE ONLY.",
        f"STRAIGHT DRIVER SLOT {SLOT_W:.2f} +/-0.10 WIDE X {SLOT_D:.2f} "
        "+/-0.10 DEEP, CENTERED, THROUGH HEAD DIAMETER.",
    )
)
END_VIEW_NOTE = "DRIVER-FACE VIEW"
