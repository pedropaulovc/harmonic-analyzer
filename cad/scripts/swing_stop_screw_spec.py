r"""Pure-data dimensional contract shared by the swing-stop screw and drawing.

PURE DATA: modeled nominals + the marked-dimension map (the slot-cut builder
names its diameters ``HeadDiaDim``/``ShankDiaDim``).  The shank is one
continuous cylinder (proud + embedded segments, same Ø), so the under-head
length is its full length.  Thread designation and the catalog-owned shank
nominals are re-derived from the fastener catalog row -- ONE hardware source.
"""

from __future__ import annotations

from _fastener_catalog import fastener


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
        f"{THREAD_DESIGNATION} FULL THREAD OVER {SHANK_LEN:g} UNDER-HEAD LENGTH; "
        "THREAD FORM, RUNOUT, AND LIMITS PER ASME B1.1.",
        "THREAD GEOMETRY OMITTED IN VIEWS; CYLINDRICAL SHANK OUTLINE IS "
        "REFERENCE ONLY.",
        f"HEAD {HEAD_T:g} THICK; STRAIGHT DRIVER SLOT {SLOT_W:g} WIDE X "
        f"{SLOT_D:g} DEEP, CENTERED, THROUGH HEAD DIAMETER.",
    )
)
END_VIEW_NOTE = "DRIVER-FACE VIEW"
