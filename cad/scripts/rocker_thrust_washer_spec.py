r"""Pure-data contract for the rocker-bank south thrust washer (MHA-148).

One turned steel washer on the pivot shaft between rocker 0's hub and the
south pivot-bracket ear (issue #743 PR2). It mirrors the pivot shaft's
integral north shoulder: both are the rocker hub's own O10 and 1.5 thick, so
each stands its bracket ear off the end hub. Each amplitude bar straddles its
arm plate and can reach past a thin hub face, so an ear or a wide washer
against hub 0 would meet the ch0 bar. A O10 face stays under the bar foot,
as the hubs do (``rocker_bank_layout``, ``test_rocker_bank_layout``). The
end-play leaf is set between this washer and the south ear, so the thickness
sits in no datum chain and stays at the title block's .XX grade.
"""

from __future__ import annotations

from pivot_bracket_spec import BORE_DIA as _BRACKET_BORE_DIA
from rocker_arm_spec import HUB_DIA

OD = HUB_DIA
BORE_DIA = _BRACKET_BORE_DIA  # slips on the O6.35 pivot shaft
THICKNESS = 1.5
# Running clearance on the shaft: never under the bore (drilled class).
BORE_BAND = (0.10, 0.0)  # (upper, lower) deviations

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity policy rule 2): all routine, the bore banded.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {"DiscDia", "BoreDia"},
    "Disc": {"DiscThick"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RingProfile": {"DiscDia": 2, "BoreDia": 2},
    "Disc": {"DiscThick": 2},
}
