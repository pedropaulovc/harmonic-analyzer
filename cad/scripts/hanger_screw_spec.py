r"""Pure-data dimensional contract shared by the hanger screw and drawing.

PURE DATA: modeled nominals + the marked-dimension map.  The hex head is a
polygon (no single diameter), so ONLY the shank diameter is a marked model dim;
the across-flats and head height are drawing-native linears.  Thread designation
and the catalog-owned shank nominals are re-derived from the fastener catalog
row -- ONE hardware source.
"""

from __future__ import annotations

from _fastener_catalog import fastener


_SPEC = fastener("hanger-screw")

HEAD_AF = 7.0  # hex across-flats
HEAD_H = 2.5

SHANK_DIA = _SPEC.model_diameter_mm  # #6-32 modeled thread minor diameter
SHANK_LEN = _SPEC.length_mm  # nominal under-head length
THREAD = _SPEC.thread  # "#6-32"
THREAD_DESIGNATION = f"{THREAD} UNC-2A"

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShankProfile": {"ShankDia"},
}

DRAWING_NOTES = "\n".join(
    (
        f"COMMERCIAL {THREAD_DESIGNATION} HEX-HEAD MACHINE SCREW, {SHANK_LEN:g} "
        "LONG, PER ASME B18.6.3, ACCEPTABLE IN PLACE OF A MADE PART.",
        "SHANK MODELED AT THREAD MINOR DIA; THREADS OMITTED FOR CLARITY.",
        f"HEAD IS A REGULAR HEXAGON, {HEAD_AF:g} ACROSS FLATS X {HEAD_H:g} HIGH.",
    )
)
END_VIEW_NOTE = "HEAD-END VIEW"
