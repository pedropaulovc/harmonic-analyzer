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
FULL_THREAD_MIN = 11.0  # full-form thread between runouts, a MIN on the print

# Machining tolerances, applied to the MODEL dimension by
# build_cone_tip_adjuster -- never typed as sheet callout text, which
# SolidWorks freezes and never re-renders on a unit change.
#
# The driver slot takes a screwdriver blade, so its width carries a band; the
# body length and cup depth of a hand-adjusted screw are ordinary machined
# features under the title-block tolerance.
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
    "DriverSlot": {"SlotDepth"},
}

# Both thread-start chamfers, flagged from the north chamfer rim on the
# elevation (never buried in the note block).
CHAMFER_NOTE = f"2X {CHAMFER:.2f} X 45<MOD-DEG>"

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).  The cup and slot are
# dimensioned in SECTION A-A; the thread designation rides the body-diameter
# callout; the chamfers ride their own leader.
DRAWING_NOTES = "\n".join(
    (
        f"FULL-FORM THREAD {FULL_THREAD_MIN:.1f} MIN BETWEEN RUNOUTS.",
        f"({BODY_DIA:.2f}) IS THE MODELLED THREAD ROOT ENVELOPE, NOT A TURNED SIZE.",
    )
)
