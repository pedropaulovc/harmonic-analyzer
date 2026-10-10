"""Pure-data drawing contract for MHA-SM-004, the gooseneck spring screw.

PURE DATA -- no SolidWorks/COM imports.  ``sm_gooseneck_spring_screw_geom``
owns every size and band; this module adds only what the print states: the
marked dimensions, their authored places, the callouts and the notes.

Every marked size prints at two places, so the title block's .XX band
(+/-0.51) governs all but the three small turned features whose model
bands the builder authors: the relief diameter (die root), the relief lead
(printed as limits on the relief callout) and the tip chamfer.
"""

from __future__ import annotations

import _config
from sm_gooseneck_spring_screw_geom import (
    HEAD_H,
    HEAD_H_LOWER,
    RELIEF_LEAD_MAX,
    RELIEF_LEAD_MIN,
    SLOT_DEPTH,
    SLOT_DEPTH_UPPER,
    THREAD,
)

THREAD_CALLOUT = THREAD
CHAMFER_CALLOUT = "X 45 DEG"
# The lead prints as limits beside the relief diameter, its model band
# (RELIEF_LEAD_TOL) all the same.
RELIEF_CALLOUT = f"{RELIEF_LEAD_MIN:.2f}-{RELIEF_LEAD_MAX:.2f} {CHAMFER_CALLOUT} LEAD"

# Policy rule 12: the head left under the slot floor, at the shortest head,
# the deepest slot and a full under-head edge break, stays above the 2.0
# wall target (7.00 - 0.51 - 3.51 - 0.25 = 2.73).
EDGE_BREAK_MAX = float(_config.title_block("edge_break")["chamfer_max_mm"])
SLOT_WEB_TARGET = 2.0
SLOT_WEB_MIN = round(
    HEAD_H + HEAD_H_LOWER - (SLOT_DEPTH + SLOT_DEPTH_UPPER) - EDGE_BREAK_MAX, 6
)
if SLOT_WEB_MIN < SLOT_WEB_TARGET:
    raise AssertionError("spring-screw slot leaves under the rule-12 head web")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDia", "HeadHeight", "CrownRise"},
    "ShankProfile": {"UnderHeadLength", "ReliefDia", "ReliefWidth", "TipChamfer"},
    "SlotProfile": {"SlotWidth"},
    "DriverSlot": {"SlotDepth"},
    "StationReference": {"OverallLength"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    feature: {name: 2 for name in sorted(names)}
    for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
# The crown rise is the sagitta of the spherical crown and the overall length
# the stock cut-off: both restate model sizes as references.
REFERENCE_DIMENSIONS = frozenset({"CrownRise", "OverallLength"})

DRAWING_NOTES = "\n".join(
    (
        "1. CROWN SPHERICAL THROUGH RIM AND APEX.",
        "2. THREAD MATES THE TAPPED END PLUG OF MHA-SM-001.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 2:1"
