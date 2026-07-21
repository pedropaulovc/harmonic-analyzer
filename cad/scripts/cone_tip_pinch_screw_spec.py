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
}

DRAWING_NOTES = "\n".join(
    (
        f"{THREAD_DESIGNATION} FULL THREAD OVER {SHANK_LEN:.2f} UNDER-HEAD LENGTH; "
        "THREAD FORM, RUNOUT, AND LIMITS PER ASME B1.1.",
        "THREAD GEOMETRY OMITTED IN VIEWS; CYLINDRICAL SHANK OUTLINE IS "
        "REFERENCE ONLY.",
        f"HEAD {HEAD_T:.2f} THICK; STRAIGHT DRIVER SLOT {SLOT_W:.2f} +/-0.10 "
        f"WIDE X {SLOT_D:.2f} +/-0.10 DEEP, CENTERED, THROUGH HEAD DIAMETER.",
    )
)
END_VIEW_NOTE = "DRIVER-FACE VIEW"
