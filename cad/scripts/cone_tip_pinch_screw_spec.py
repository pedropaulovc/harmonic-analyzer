r"""Pure-data dimensional contract shared by the cone tip pinch screw and drawing.

PURE DATA: modeled nominals + the marked-dimension map (the slot-cut builder
names its diameters ``HeadDiaDim``/``ShankDiaDim``).  Thread designation and the
catalog-owned shank nominals are re-derived from the fastener catalog row -- ONE
hardware source.
"""

from __future__ import annotations

from _fastener_catalog import fastener


_SPEC = fastener("cone-tip-pinch-screw")

HEAD_DIA = 4.8  # slotted head OD
HEAD_T = 2.0  # head thickness
SLOT_W = 0.8
SLOT_D = 0.8

SHANK_DIA = _SPEC.model_diameter_mm  # #3-48 modeled thread minor diameter
SHANK_LEN = _SPEC.length_mm  # nominal under-head length
THREAD = _SPEC.thread  # "#3-48"
THREAD_DESIGNATION = f"{THREAD} UNC-2A"

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDiaDim"},
    "ShankProfile": {"ShankDiaDim"},
}

DRAWING_NOTES = "\n".join(
    (
        f"COMMERCIAL {THREAD_DESIGNATION} SLOTTED FILLISTER-HEAD MACHINE SCREW, "
        f"{SHANK_LEN:g} LONG, PER ASME B18.6.3, ACCEPTABLE IN PLACE OF A "
        "MADE PART.",
        "SHANK MODELED AT THREAD MINOR DIA; THREADS OMITTED FOR CLARITY.",
        f"HEAD {HEAD_T:g} THICK; STRAIGHT DRIVER SLOT {SLOT_W:g} WIDE X "
        f"{SLOT_D:g} DEEP.",
    )
)
END_VIEW_NOTE = "HEAD-END VIEW"
