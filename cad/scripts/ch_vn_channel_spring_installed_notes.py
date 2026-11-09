"""Purchased reference-sheet notes for the 9432K31 channel spring.

The sheet's footer holds at most three note lines (drawing-guidelines rule 7):
the matched-set acceptance only.  The catalogue's +/-10% rate band is too wide
for channel consistency, so the springs are bought as one lot and the set is
selected by measured rate (tolerance-policy.md, spring rate); the ITEM row
identifies the spring and the Front view shows it at its installed length.
"""

from __future__ import annotations

import _config
from spring_mount_geom import channel_force_n


_MATCHED_SET_SIZE = len(_config.channels())
# Owner ruling relayed with the machinist-review fleet pass: order twice the
# set from one lot; if the lot cannot supply a matched set, select from
# another lot (tolerance-policy.md).
_ORDER_QUANTITY = 2 * _MATCHED_SET_SIZE
_MATCH_TOLERANCE_PERCENT = float(
    _config._doc("error_budget")["critical_features"]["spring_rate"]["tolerance"]
)

# The shop owns no force gauge (drawing-guidelines shop table), so the rate is
# read as the stretch between two dead loads that are the same for every
# spring: the rate is the load step over the stretch, and with one load step a
# stretch within the tolerance of the set's mean is a rate within it.  The
# loads put a catalogue spring at error_budget's SET QC inside-hook lengths.
_LB_N = 4.4482216152605
QC_LENGTHS_MM = (60.0, 80.0)
QC_LOADS_LB = tuple(round(channel_force_n(length) / _LB_N, 1) for length in QC_LENGTHS_MM)

DRAWING_NOTES = "\n".join(
    (
        f"MATCHED SET: ORDER {_ORDER_QUANTITY} FROM ONE LOT. HANG EACH FROM A PIN; "
        "CALIPER THE",
        f"INSIDE-HOOK LENGTH UNDER {QC_LOADS_LB[0]:.1f} LB, THEN "
        f"{QC_LOADS_LB[1]:.1f} LB (SAME WEIGHTS FOR ALL).",
        f"KEEP {_MATCHED_SET_SIZE} WHOSE LENGTH CHANGE IS WITHIN "
        f"\u00b1{_MATCH_TOLERANCE_PERCENT:.2f}% OF THEIR MEAN.",
    )
)
