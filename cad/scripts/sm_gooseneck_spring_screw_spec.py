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
    CROWN_RISE,
    CROWN_RISE_LOWER,
    CROWN_RISE_UPPER,
    HEAD_H,
    HEAD_H_LOWER,
    RELIEF_LEAD_MAX,
    RELIEF_LEAD_MIN,
    SLOT_DEPTH,
    SLOT_DEPTH_LOWER,
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
# The overall length is the stock cut-off, a restatement of the head height
# and under-head length; the crown rise is NOT a reference (see above).
REFERENCE_DIMENSIONS = frozenset({"OverallLength"})

# Line 3 is the installation step the static-clamp retention relies on
# (user ruling 2026-09-21: no torque value, no threadlocker). The three-view
# summing sheet prints no notes until it is built out (policy rule 9), so the
# fitter reads it here, on the screw's own sheet.
CLAMP_INSTRUCTION = (
    "3. AT ASSEMBLY TIGHTEN UNTIL THE MHA-VN-005 UPPER EYE IS CLAMPED\n"
    "   AND CANNOT SWIVEL; NO THREADLOCKER."
)
DRAWING_NOTES = "\n".join(
    (
        "1. CROWN SPHERICAL THROUGH RIM AND APEX.",
        "2. THREAD MATES THE TAPPED END PLUG OF MHA-SM-001.",
        CLAMP_INSTRUCTION,
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 2:1"
