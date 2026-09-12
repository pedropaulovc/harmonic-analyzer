r"""Connecting-rod drawing prose -- the manufacturing notes the part build
stamps into the SLDPRT and the isometric-view label.

Split OUT of ``connecting_rod_spec`` (codex #354): assemblies import geometry
from the spec, so drawing-only prose living there made every notes edit
full-rebuild ``assembly:channel``.  This module is imported ONLY by
``build_connecting_rod`` (which stamps the properties) and the offline drawing
test -- never by an assembly -- so a notes edit rebuilds the part + drawing
and leaves the assembly to its cheap token refresh.
"""

from __future__ import annotations

# Every value that can be read from a view stays on a native dimension.  The
# two short notes below carry only the cross-part acceptance authority that a
# part view cannot show.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingDiscProfile": {"RingOuterDia"},
    "StrapBoreProfile": {"StrapBoreDia"},
    "ShankProfile": {"ShankWidthDim"},
    "HeadProfile": {"HeadCrownR", "HeadShoulderRiseR"},
    "ForkFlareProfile": {"FlareAxialRise", "FlareLength"},
    "ForkRootProfile": {"RootDiameter"},
    "ForkSlotProfile": {"SlotWidth"},
}

DIMENSION_PRECISION: dict[str, int] = {
    "RingOuterDia": 2,
    "StrapBoreDia": 2,
    "ShankWidthDim": 2,
    "HeadCrownR": 2,
    "HeadShoulderRiseR": 2,
    "FlareAxialRise": 3,
    "FlareLength": 2,
    "RootDiameter": 3,
    "SlotWidth": 3,
}

DIMENSION_CALLOUTS: dict[str, str] = {
    "StrapBoreDia": "RUNNING FIT WITH CYLINDER-GEAR CAM",
    "RootDiameter": "ROUND SLOT ROOT",
    "SlotWidth": "DESIGN NOMINAL; FINISH MATCHED SLOT",
}

DRAWING_NOTES = "\n".join(
    (
        "MATES WITH ROCKER ARM MHA-071.",
        "FINAL SIDEPLAY AND FREE PIVOT PER MHA-132.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
