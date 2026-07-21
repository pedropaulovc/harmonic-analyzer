r"""Pure-data dimensional contract shared by the hex bolt and drawing.

PURE DATA: modeled nominals + the marked-dimension map.  The hex head is a
polygon (no single diameter), so ONLY the shank diameter is a marked model dim;
the across-flats and head height are drawing-native linears.  Thread designation
and the catalog-owned shank nominals are re-derived from the fastener catalog
row -- ONE hardware source.
"""

from __future__ import annotations

from _fastener_catalog import fastener


_SPEC = fastener("hex-bolt")

HEAD_AF = 12.7  # hex across-flats (1/2 in wrench)
HEAD_H = 5.5

SHANK_DIA = _SPEC.model_diameter_mm  # 5/16 shank
SHANK_LEN = _SPEC.length_mm  # nominal under-head length
THREAD = _SPEC.thread  # "5/16-18"
THREAD_DESIGNATION = f"{THREAD} UNC-2A"

# The hex head carries no single diameter dim, so only the shank Ø is marked;
# HEAD_AF (across flats) and the head height are drawing-native linears.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShankProfile": {"ShankDia"},
}

DRAWING_NOTES = "\n".join(
    (
        f"COMMERCIAL {THREAD_DESIGNATION} HEX-HEAD BOLT, {SHANK_LEN:g} MM LONG, "
        "PER ASME B18.2.1, ACCEPTABLE IN PLACE OF A MADE PART.",
        "SHANK MODELED AT THREAD MINOR DIA; THREADS OMITTED FOR CLARITY.",
        f"HEAD IS A REGULAR HEXAGON, {HEAD_AF:g} ACROSS FLATS.",
    )
)
END_VIEW_NOTE = "HEAD-END VIEW"
