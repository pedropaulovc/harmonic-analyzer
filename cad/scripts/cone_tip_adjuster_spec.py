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

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).  Every band is on its
# model dimension; the thread designation rides the body-diameter callout.
DRAWING_NOTES = "\n".join(
    (
        "FULL-FORM THREAD 11.00 MIN BETWEEN RUNOUTS; 2A LIMITS APPLY AFTER FINISH.",
        f"CHAMFER BOTH THREAD STARTS {CHAMFER:.2f} X 45 DEG; SLOT {SLOT_D:.2f} DEEP ACROSS THE HEAD.",
        "CUP: FLAT FLOOR, FROM THE END OPPOSITE THE SLOT.",
        f"({BODY_DIA:.2f}) IS THE MODELLED THREAD ROOT ENVELOPE, NOT A TURNED SIZE.",
    )
)
