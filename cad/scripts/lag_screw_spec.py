r"""Pure-data dimensional contract shared by the lag screw and drawing.

PURE DATA: modeled nominals + the marked-dimension map, so one edit rebuilds
both the SLDPRT and SLDDRW recipe.  Thread designation and the catalog-owned
shank nominals are re-derived from the fastener catalog row -- ONE hardware
source; the drawing never invents a thread the part does not build.
"""

from __future__ import annotations

from _fastener_catalog import fastener


_SPEC = fastener("lag-screw")

HEAD_DIA = 22.0  # round head in the base counterbore (low)
HEAD_H = 6.0

SHANK_DIA = _SPEC.model_diameter_mm  # 9/16-12 shank (rides the base hole)
SHANK_LEN = _SPEC.length_mm  # nominal under-head length
THREAD = _SPEC.thread  # "9/16-12"
THREAD_DESIGNATION = f"{THREAD} UNC-2A"

# The head-end view carries the two diameters; the side view carries the two
# lengths.  The lengths are the head/shank extrude DEPTH dimensions (named
# HeadHt/ShankLg in the build) inserted as model dims -- an axis-along-Y screw
# projects edge-on circle silhouettes for the shoulder and tip that SolidWorks
# will not point-select, so a drawing-native edge dimension cannot pick them.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDia"},
    "ShankProfile": {"ShankDia"},
    "Head": {"HeadHt"},
    "Shank": {"ShankLg"},
}
END_VIEW_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDia"},
    "ShankProfile": {"ShankDia"},
}
SIDE_VIEW_DIMENSIONS: dict[str, set[str]] = {
    "Head": {"HeadHt"},
    "Shank": {"ShankLg"},
}

DRAWING_NOTES = "\n".join(
    (
        f"{THREAD_DESIGNATION} SLOTTED CYLINDRICAL-HEAD HOLD-DOWN SCREW; "
        f"{SHANK_LEN:g} UNDER HEAD, FULL-LENGTH THREAD.",
        "SHANK MODELED AT THREAD MINOR DIA; THREADS OMITTED FOR CLARITY.",
        "DRIVER SLOT 2 WIDE x 2 DEEP, CENTERED ON THE HEAD.",
    )
)
END_VIEW_NOTE = "HEAD-END VIEW"
