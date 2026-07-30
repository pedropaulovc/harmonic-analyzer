r"""Pure-data dimensional contract shared by the cone-tip-adjuster and drawing.

The turned/threaded set-screw nominals come from the fastener catalog row (pure
data) so the part keeps one thread source; the marked-dimension map lives here so
a change rebuilds both the SLDPRT and SLDDRW recipes.
"""

from __future__ import annotations

from _fit_limits import band_text

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

# Machining tolerances, applied to the MODEL dimension by
# build_cone_tip_adjuster -- never typed as sheet callout text, which
# SolidWorks freezes and never re-renders on a unit change.
#
# The general turned/milled class for this part: the body length and the driver
# slot are ordinary machined features with no fit partner.
GENERAL_TOL_MM = 0.10
# The cup is a blind bore the cone-shaft tip rests in; it may run oversize (more
# end-play takeup) but never under, so the band is unilateral.
CUP_DIA_BAND = (0.050, 0.000)


DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BodyProfile": {"BodyDiaDim"},
    "Body": {"BodyLenDim"},
    "CupProfile": {"CupDiaDim"},
    "Cup": {"CupDepth"},
    "SlotProfile": {"SlotWDim"},
}

DRAWING_NOTES = "\n".join(
    (
        "11.00 MIN USABLE FULL-FORM THREAD BETWEEN RUNOUTS.",
        "CLASS 2A LIMITS APPLY AFTER FINISH.",
        "DATUM A IS THE AXIS DERIVED FROM THE THREAD PITCH CYLINDER.",
        f"CHAMFER BOTH THREAD STARTS {CHAMFER:.2f} +/-{GENERAL_TOL_MM:.2f} X 45 DEG +/-1 DEG.",
        f"BLIND CUP DIA {CUP_DIA:.2f} {band_text(CUP_DIA_BAND)} X {CUP_DEPTH:.2f} "
        f"+/-{GENERAL_TOL_MM:.2f} DEEP FROM",
        "THE END OPPOSITE THE SLOT; FLAT FLOOR, BOTTOM R0.20 MAX.",
        "CUP AXIS POSITION WITHIN DIA 0.05 OF DATUM A.",
        f"DRIVER SLOT {SLOT_W:.2f} +/-{GENERAL_TOL_MM:.2f} WIDE X {SLOT_D:.2f} "
        f"+/-{GENERAL_TOL_MM:.2f} DEEP,",
        "POSITION FCF APPLIES TO THE SLOT MEDIAN PLANE.",
        f"PARENTHETICAL DIA {BODY_DIA:.2f} IS THE REFERENCE THREAD ROOT ENVELOPE.",
    )
)
