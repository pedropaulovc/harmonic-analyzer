r"""Pure-data dimensional contract shared by the cone-tip-adjuster and drawing.

The turned/threaded set-screw nominals come from the fastener catalog row (pure
data) so the part keeps one thread source; the marked-dimension map lives here so
a change rebuilds both the SLDPRT and SLDDRW recipes.
"""

from __future__ import annotations

from _fastener_catalog import fastener


_SCREW = fastener("cone-tip-adjuster")

BODY_DIA = _SCREW.model_diameter_mm  # 6.2: 5/16-18 modeled thread minor diameter
BODY_LEN = _SCREW.length_mm  # 14.0
THREAD = _SCREW.thread  # 5/16-18
CUP_DIA = 2.0  # blind bore the cone-shaft tip rests in (axial end-play takeup)
CUP_DEPTH = 6.0  # from the far (north) end
SLOT_W = 1.5  # driver slot width
SLOT_D = 1.5  # driver slot depth

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BodyProfile": {"BodyDiaDim"},
    "Body": {"BodyLenDim"},
    "SlotProfile": {"SlotWDim"},
}

DRAWING_NOTES = "\n".join(
    (
        f"THREAD {THREAD} UNC-2A, FULL BODY LENGTH; THE SHOWN",
        "  OD IS THE MODELED THREAD MINOR DIA, REFERENCE ONLY.",
        "BLIND CUP DIA 2.0 X 6.0 DEEP (FLAT BOTTOM) BORED FROM",
        "  THE END OPPOSITE THE SLOT, CONCENTRIC W/ THREAD",
        "  AXIS -- THE CONE-SHAFT TIP SEATS ON THE FLOOR; DEBURR LIP.",
        "DRIVER SLOT 1.5 WIDE X 1.5 DEEP ACROSS THE SLOTTED",
        "  END, CENTERED ON THE THREAD AXIS.",
        "MATERIAL AISI 12L14 FREE-MACHINING STEEL, BLUED",
        "  (BLACK OXIDE) AFTER MACHINING.",
    )
)
