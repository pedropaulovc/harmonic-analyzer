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
        f"THREAD {THREAD} UNC-2A; 11.00 MIN USABLE FULL-FORM LENGTH",
        "BETWEEN RUNOUTS. CLASS 2A LIMITS APPLY AFTER FINISH.",
        "CHAMFER BOTH THREAD STARTS 0.40 X 45 DEG.",
        "THE SHOWN DIA 6.20 IS THE THREAD-ROOT ENVELOPE, REFERENCE ONLY;",
        "THE THREAD CALLOUT AND COSMETIC THREAD LINES GOVERN.",
        "BLIND CUP DIA 2.00 +0.05/-0.00 X 6.00 +/-0.10 DEEP FROM",
        "THE END OPPOSITE THE SLOT; FLAT FLOOR, BOTTOM R0.20 MAX.",
        "CUP AXIS POSITION WITHIN DIA 0.05 OF THREAD PITCH-DIA AXIS.",
        "DRIVER SLOT 1.50 +/-0.10 WIDE X 1.50 +/-0.10 DEEP,",
        "CENTERED ON THREAD AXIS WITHIN 0.05.",
        "OVERALL LENGTH 14.00 +/-0.10. BREAK EDGES 0.25 MAX EXCEPT",
        "THE SPECIFIED THREAD-START CHAMFERS.",
    )
)
