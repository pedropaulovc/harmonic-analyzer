"""Pure-data drawing contract for MHA-SM-04, the gooseneck spring screw.

PURE DATA -- no SolidWorks/COM imports.  ``sm_gooseneck_spring_screw_geom``
owns every size and band; this module adds only what the print states: the
marked dimensions, their authored places, the callouts and the notes.

The title block's band for each mark's places governs every size but the
relief diameter and its 45-degree lead.  The relief Ø prints as the native
LIMIT band 2.35/2.15 about the model's 2.20.  The upper limit is derived from
the estimated deepest #6-32 die root (geom's THREAD_MINOR_2A_MIN_EST, 2.38).
The floor is the design's pre-existing 2.15, unchanged here, which keeps the
neck's clamp-torque strength (its adequacy is tracked in #1951).  The lead
prints as a single MAX limit (the model value is the limit) from the hidden
``LeadReference`` sketch on the profile's lower silhouette, driven by the
profile's ``ReliefLead``.
"""

from __future__ import annotations

import _config
from sm_gooseneck_spring_screw_geom import (
    CROWN_RISE,
    CROWN_RISE_LOWER,
    CROWN_RISE_UPPER,
    HEAD_H,
    HEAD_H_LOWER,
    SLOT_DEPTH,
    SLOT_DEPTH_LOWER,
    SLOT_DEPTH_UPPER,
    THREAD,
)

THREAD_CALLOUT = THREAD
CHAMFER_CALLOUT = "X 45 DEG"
# Below-value callouts the PART authors on its dimensions (the drawing only
# reads them back; a drawing-side SetText can write through to the part,
# #1942).  The lead's MAX and the relief's LIMIT band are tighter than the
# title block, so each names what it serves (drawing-guidelines.md rule 4):
# the flat under-head seat that clamps the counter spring's upper loop; the
# die root that caps the relief and the clamp torque that floors it.
COUNTER_SPRING_NUMBER = str(_config.parts("sm-vn-counter-spring")["number"])
DIMENSION_CALLOUTS: dict[str, dict[str, str]] = {
    "LeadReference": {
        "HeadLead": f"{CHAMFER_CALLOUT}\nFLAT SEAT FOR\n{COUNTER_SPRING_NUMBER} LOOP"
    },
    "ShankProfile": {
        "ReliefDia": "UNDER DIE ROOT,\nMIN FOR\nCLAMP TORQUE",
        "TipChamfer": CHAMFER_CALLOUT,
    },
}
DIMENSION_CALLOUTS_BY_NAME: dict[str, str] = {
    name: text
    for callouts in DIMENSION_CALLOUTS.values()
    for name, text in callouts.items()
}

# drawing-guidelines.md rule 17 (walls and webs): the head left under the slot floor, at the shortest head,
# the deepest slot and a full under-head edge break, stays above the 2.0
# wall target (7.00 - 0.51 - 3.51 - 0.25 = 2.73).
EDGE_BREAK_MAX = float(_config.title_block("edge_break")["chamfer_max_mm"])
SLOT_WEB_TARGET = 2.0
SLOT_WEB_MIN = round(
    HEAD_H + HEAD_H_LOWER - (SLOT_DEPTH + SLOT_DEPTH_UPPER) - EDGE_BREAK_MAX, 6
)
if SLOT_WEB_MIN < SLOT_WEB_TARGET:
    raise AssertionError("spring-screw slot leaves under the drawing-guidelines.md rule 17 (walls and webs) head web")

# The crown rise is the only printed size that fixes the dome (the head Ø and
# height do not), so it controls at the .XX band.  Across that band the dome
# must stay a usable fillister head: the shallowest slot still cuts through
# the cylindrical rim under the tallest crown, so a full-width blade bears on
# both slot walls, and the tallest crown on the shortest head still leaves a
# cylindrical side after a full edge break.
CROWN_RISE_MIN = CROWN_RISE + CROWN_RISE_LOWER
CROWN_RISE_MAX = CROWN_RISE + CROWN_RISE_UPPER
SLOT_RIM_CUT_MIN = round(SLOT_DEPTH + SLOT_DEPTH_LOWER - CROWN_RISE_MAX, 6)
HEAD_SIDE_MIN = round(HEAD_H + HEAD_H_LOWER - CROWN_RISE_MAX - EDGE_BREAK_MAX, 6)
if CROWN_RISE_MIN <= 0.0 or SLOT_RIM_CUT_MIN <= 0.0 or HEAD_SIDE_MIN <= 0.0:
    raise AssertionError("spring-screw crown band does not leave a fillister head")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDia", "HeadHeight", "CrownRise"},
    "ShankProfile": {"UnderHeadLength", "ReliefDia", "ReliefWidth", "TipChamfer"},
    "SlotProfile": {"SlotWidth"},
    "DriverSlot": {"SlotDepth"},
    "StationReference": {"OverallLength"},
    "LeadReference": {"HeadLead"},
}
# Chamfers never need extra places (drawing-guidelines.md rule 3): the tip
# chamfer rides the title block's .X band and the lead's single MAX limit
# prints at one place too.  Every other mark prints at two.
ONE_PLACE_DIMENSIONS = frozenset({"TipChamfer", "HeadLead"})
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    feature: {name: 1 if name in ONE_PLACE_DIMENSIONS else 2 for name in sorted(names)}
    for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
# The overall length is the stock cut-off, a restatement of the head height
# and under-head length; the crown rise is NOT a reference (see above).
REFERENCE_DIMENSIONS = frozenset({"OverallLength"})

# The fitter's clamp step (user ruling 2026-09-21: no torque value, no
# threadlocker) prints on the summing assembly sheet as MHA-SM-00 step 8,
# not here: a part sheet carries no assembly instruction (machinist review
# 2026-10-23).
DRAWING_NOTES = "\n".join(
    (
        "1. CROWN SPHERICAL THROUGH RIM AND APEX.",
        "2. THREAD MATES THE TAPPED END PLUG OF MHA-SM-01.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 2:1"
