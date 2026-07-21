r"""Pure-data dimensional contract shared by the cone-tip-adjuster and drawing.

The turned/threaded set-screw nominals come from the fastener catalog row (pure
data) so the part keeps one thread source; the marked-dimension map lives here so
a change rebuilds both the SLDPRT and SLDDRW recipes.
"""

from __future__ import annotations

from _fastener_catalog import fastener


_SCREW = fastener("cone-tip-adjuster")

BODY_DIA = _SCREW.model_diameter_mm  # 6.2: interference-safe cosmetic-thread envelope
BODY_LEN = _SCREW.length_mm  # 14.0
THREAD = _SCREW.thread  # 5/16-18
CUP_DIA = 2.0  # blind bore the cone-shaft tip rests in (axial end-play takeup)
CUP_DEPTH = 6.0  # from the far (north) end
SLOT_W = 1.5  # driver slot width
SLOT_D = 1.5  # driver slot depth
CHAMFER = 0.4  # both thread starts, 45 degrees

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BodyProfile": {"BodyDiaDim"},
    "Body": {"BodyLenDim"},
    "CupProfile": {"CupDiaDim"},
    "SlotProfile": {"SlotWDim"},
}

DRAWING_NOTES = "\n".join(
    (
        "11.00 MIN USABLE FULL-FORM THREAD BETWEEN RUNOUTS.",
        "CLASS 2A LIMITS APPLY AFTER FINISH.",
        "DATUM A IS THE AXIS DERIVED FROM THE THREAD PITCH CYLINDER.",
        f"CHAMFER BOTH THREAD STARTS {CHAMFER:.2f} +/-0.10 X 45 DEG +/-1 DEG.",
        "BLIND CUP DIA 2.00 +0.05/-0.00 X 6.00 +/-0.10 DEEP FROM",
        "THE END OPPOSITE THE SLOT; FLAT FLOOR, BOTTOM R0.20 MAX.",
        "CUP AXIS POSITION WITHIN DIA 0.05 OF DATUM A.",
        "DRIVER SLOT 1.50 +/-0.10 WIDE X 1.50 +/-0.10 DEEP,",
        "POSITION FCF APPLIES TO THE SLOT MEDIAN PLANE.",
        "PARENTHETICAL DIA 6.20 IS THE REFERENCE THREAD ROOT ENVELOPE.",
    )
)
