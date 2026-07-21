r"""Pure-data dimensional contract shared by the foot screw and drawing.

PURE DATA: modeled nominals + the marked-dimension map, so one edit rebuilds
both the SLDPRT and SLDDRW recipe.  Thread designation and the catalog-owned
shank nominals are re-derived from the fastener catalog row -- ONE hardware
source; the drawing never invents a thread the part does not build.
"""

from __future__ import annotations

from _fastener_catalog import fastener


_SPEC = fastener("foot-screw")

HEAD_DIA = 5.5  # fillister-size head (fits the pedestal's 6-long flange)
HEAD_H = 2.2

SHANK_DIA = _SPEC.model_diameter_mm  # #4-40 modeled thread minor diameter
SHANK_LEN = _SPEC.length_mm  # nominal under-head length
THREAD = _SPEC.thread  # "#4-40"
THREAD_DESIGNATION = f"{THREAD} UNC-2A"

# The head-end view carries the two diameters; the side view carries the two
# lengths.  The lengths are the head/shank extrude DEPTH dimensions (named
# HeadHt/ShankLg in the build) inserted as model dims -- an axis-along-Y screw
# projects edge-on circle silhouettes for the shoulder and tip that SolidWorks
# will not point-select, so a drawing-native edge dimension cannot pick them.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDia"},
    "Head": {"HeadHt"},
    "Shank": {"ShankLg"},
}
END_VIEW_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDia"},
}
SIDE_VIEW_DIMENSIONS: dict[str, set[str]] = {
    "Head": {"HeadHt"},
    "Shank": {"ShankLg"},
}

DRAWING_NOTES = "\n".join(
    (
        f"{THREAD_DESIGNATION} FULL THREAD OVER {SHANK_LEN:g} UNDER-HEAD LENGTH; "
        "THREAD FORM, RUNOUT, AND LIMITS PER ASME B1.1.",
        "THREAD GEOMETRY OMITTED IN VIEWS; CYLINDRICAL SHANK OUTLINE IS "
        "REFERENCE ONLY.",
        "STRAIGHT DRIVER SLOT 0.8 WIDE X 0.7 DEEP, CENTERED, THROUGH HEAD "
        "DIAMETER.",
    )
)
END_VIEW_NOTE = "DRIVER-FACE VIEW"
