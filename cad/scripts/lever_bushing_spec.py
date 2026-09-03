r"""Dimensional contract shared by the lever-bushing part and drawing.

PURE DATA: keep the turned-part nominals and marked-dimension map here so a
change rebuilds both the SLDPRT and SLDDRW recipes without making the drawing
import the part build implementation.
"""

from __future__ import annotations

from _gtol_spec import GeometricControl, PartDatum
from _surface_finish import SurfaceFinishControl


OUTER_DIA = 12.0
BORE_DIA = 6.5
LENGTH = 4.0565
BORE_DIA_BAND = (0.03, 0.00)
# Nineteen of these stack between the twenty channel levers on the fulcrum
# shaft and SET the 7.0565 channel pitch, so the length is the one functional
# dimension of the part: at the block's .XX +/-0.51 the stack could be 10 mm
# out. The band stays (the machinist review of 2026-09-02 read it as an
# ordinary bushing length; the MATES WITH note now says what the stack does).
LENGTH_TOLERANCE_MM = 0.03

# No geometric controls and no roughness callouts: the bushing is a stationary
# spacer between the levers on the fulcrum shaft, so nothing runs on its bore
# and the reamed bore's fit band on the model dimension is the whole spec
# (cad/docs/drawing-simplicity-policy.md rules 3 and 5). The typed tuples stay
# so build_lever_bushing's author_part_pmi call shape is unchanged.
PART_DATUMS: tuple[PartDatum, ...] = ()
GEOMETRIC_CONTROLS: tuple[GeometricControl, ...] = ()
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "AnnulusProfile": {"OuterDia", "BoreDia"},
    "Bushing": {"Depth"},
}

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6). The REAM instruction
# rides the bore callout itself; how the OD, faces and bore are chucked and
# whether the 19 are made together is the shop's call (machinist review,
# 2026-09-02) -- the print says what the stack is for instead.
DRAWING_NOTES = "MATES WITH MHA-031 FULCRUM SHAFT; 19 STACKED BETWEEN THE CHANNEL LEVERS."
