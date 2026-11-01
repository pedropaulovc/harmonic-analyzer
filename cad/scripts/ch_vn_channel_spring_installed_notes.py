"""Purchased reference-sheet notes for the 9432K31 channel spring.

The sheet's footer holds at most three note lines (drawing-guidelines rule 7):
the matched-set acceptance only.  The catalogue's +/-10% rate band is too wide
for channel consistency, so the springs are bought as one lot and the set is
selected by measured rate (tolerance-policy.md, spring rate); the ITEM row
identifies the spring and the Front view shows it at its installed length.
"""

from __future__ import annotations

import _config


# The rate check's two inside-hook lengths and its pins, inch (the sheet's
# unit), both inside the 9432K31's free-to-maximum range.
_QC_LENGTH_1_IN = 2.40
_QC_LENGTH_2_IN = 3.20
_QC_PIN_DIA_IN = 0.08
_MATCHED_SET_SIZE = len(_config.channels())
# Owner ruling relayed with the machinist-review fleet pass: order twice the
# set from one lot; if the lot cannot supply a matched set, select from
# another lot (tolerance-policy.md).
_ORDER_QUANTITY = 2 * _MATCHED_SET_SIZE
_MATCH_TOLERANCE_PERCENT = float(
    _config._doc("error_budget")["critical_features"]["spring_rate"]["tolerance"]
)


def _in(value: float) -> str:
    """Inch print text, leading zero suppressed."""
    return f"{value:.2f}".removeprefix("0")


DRAWING_NOTES = "\n".join(
    (
        f"MATCHED SET: ORDER {_ORDER_QUANTITY} FROM ONE LOT; KEEP {_MATCHED_SET_SIZE} "
        "WHOSE RATE (F2-F1)/(L2-L1)",
        f"IS WITHIN \u00b1{_MATCH_TOLERANCE_PERCENT:.2f}% OF THEIR MEAN, "
        "FOR EQUAL FORCE IN EVERY CHANNEL.",
        f"F1/F2 AT L1/L2 = {_in(_QC_LENGTH_1_IN)}/{_in(_QC_LENGTH_2_IN)} INSIDE HOOKS; "
        f"\u00d8{_in(_QC_PIN_DIA_IN)} PINS AT "
        f"{_in(_QC_LENGTH_1_IN - _QC_PIN_DIA_IN)}/{_in(_QC_LENGTH_2_IN - _QC_PIN_DIA_IN)} C-C.",
    )
)
