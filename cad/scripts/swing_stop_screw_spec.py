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

SHANK_DIA = _SPEC.model_diameter_mm  # #8-32 modeled thread minor diameter
SHANK_LEN = _SPEC.length_mm  # full shank (proud + embedded), the nominal length
THREAD = _SPEC.thread  # "#8-32"
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
        "HEAD CARRIES A STRAIGHT DRIVER SLOT PER THE HEAD-END VIEW.",
    )
)
END_VIEW_NOTE = "HEAD-END VIEW"
