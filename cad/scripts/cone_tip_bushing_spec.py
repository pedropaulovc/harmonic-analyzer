r"""Dimensional contract shared by the cone-tip-bushing part and drawing.

PURE DATA: keep the turned-part nominals and marked-dimension map here so a
change rebuilds both the SLDPRT and SLDDRW recipes without making the drawing
import the part build implementation.
"""

from __future__ import annotations

from _surface_finish import SurfaceFinishControl


OUTER_DIA = 6.0
BORE_DIA = 0.03125 * 25.4  # 0.79375: the cone shaft's 1/32 in tip stub
LENGTH = 4.0

# No bands and no roughness callouts (machinist review, 2026-09-02): the
# bushing is the axial spacer in the cone shaft's end-play take-up stack, so
# the adjuster screw absorbs its length and the block's .XX governs the 4.00;
# the bore is a plain 1/32 in drill governed by the block's DRILLED HOLES row,
# not a bearing (the shaft's tip stub is located by the tip block, and a
# drilled 0.79 hole is not held to Ra 1.6 without reaming). No geometric
# controls either (cad/docs/drawing-simplicity-policy.md rules 3 and 5).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BodyProfile": {"ODDim"},
    "BoreProfile": {"BoreDiaDim"},
    "Body": {"Depth"},
}

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6). The DRILL instruction
# and the 1/32 in size ride the bore callout itself; how the OD, faces and
# bore are chucked is the shop's call (review 2026-09-02) -- the print says
# what the bore rides instead.
DRAWING_NOTES = "MATES WITH MHA-014 CONE GEAR SHAFT TIP STUB."
