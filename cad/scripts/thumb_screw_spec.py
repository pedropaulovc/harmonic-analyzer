r"""Pure-data dimensional contract shared by the thumb screw and drawing.

PURE DATA: modeled nominals + the marked-dimension map.  A knurled ("reeded")
thumb screw: the head OD and shank/thread minor Ø are marked model dims; the
knurl and cosmetic thread are called out in the notes.  Thread designation and
the catalog-owned shank nominals are re-derived from the fastener catalog row --
ONE hardware source.
"""

from __future__ import annotations

from _fastener_catalog import fastener


_SPEC = fastener("thumb-screw")

HEAD_DIA = 10.0  # knurled head OD
HEAD_LENGTH = 5.0  # knurled head length
GROOVE_COUNT = 24  # reeding grooves

SHANK_DIA = _SPEC.model_diameter_mm  # #4-40 modeled thread minor diameter
SHANK_LEN = _SPEC.length_mm  # exposed shank length below the head
THREAD = _SPEC.thread  # "#4-40"
THREAD_DESIGNATION = f"{THREAD} UNC-2A"

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDia"},
    "ShankProfile": {"ShankDia"},
}

DRAWING_NOTES = "\n".join(
    (
        f"COMMERCIAL {THREAD_DESIGNATION} KNURLED THUMB SCREW, {SHANK_LEN:g} MM "
        "LONG, ACCEPTABLE IN PLACE OF A MADE PART.",
        "SHANK MODELED AT THREAD MINOR DIA; THREADS OMITTED FOR CLARITY.",
        f"HEAD STRAIGHT-KNURLED (REEDED), {GROOVE_COUNT} GROOVES.",
    )
)
END_VIEW_NOTE = "HEAD-END VIEW"
