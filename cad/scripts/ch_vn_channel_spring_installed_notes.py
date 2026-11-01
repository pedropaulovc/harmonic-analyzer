"""Purchased reference-sheet notes for the 9432K31 channel spring.

The sheet's footer holds at most three note lines (drawing-guidelines rule 7):
the matched-set acceptance only.  The catalogue's +/-10% rate band is too wide
for channel consistency, so the springs are bought as one lot and the set is
selected by measured rate (tolerance-policy.md, spring rate); the ITEM row
identifies the spring and the Front view shows it at its installed length.
"""

from __future__ import annotations

import _config


_MATCHED_SET_SIZE = len(_config.channels())
# Owner ruling relayed with the machinist-review fleet pass: order twice the
# set from one lot; if the lot cannot supply a matched set, select from
# another lot (tolerance-policy.md).
_ORDER_QUANTITY = 2 * _MATCHED_SET_SIZE
_MATCH_TOLERANCE_PERCENT = float(
    _config._doc("error_budget")["critical_features"]["spring_rate"]["tolerance"]
)


# Function only: the rate is measured between any two inside-hook lengths
# within the free and maximum lengths the sheet dimensions natively.
DRAWING_NOTES = "\n".join(
    (
        f"MATCHED SET: ORDER {_ORDER_QUANTITY} FROM ONE LOT; KEEP {_MATCHED_SET_SIZE} "
        "WHOSE RATE, MEASURED",
        "BETWEEN TWO LENGTHS WITHIN THE FREE AND MAXIMUM SHOWN, IS WITHIN",
        f"\u00b1{_MATCH_TOLERANCE_PERCENT:.2f}% OF THEIR MEAN, FOR EQUAL FORCE IN EVERY CHANNEL.",
    )
)
