"""Dimension text the MHA-PD-20 pivot spacer authors on its marked dimensions.

The part builder writes every lane below on its source dimension; the
drawing imports them verbatim and only reads them back.  Setting dimension
text from the drawing writes through to the imported source dimension, and
the drawing's native save then saves the dirtied part outside its own recipe
(fleet issue #1942; the ``pd_transgear_pin_callouts`` pattern).  Kept out of
``pd_transgear_pivot_spacer_spec``, which the hanger joints, the arm and the
paper-drive assembly import.
"""

from __future__ import annotations

import math

import _config
from pd_transgear_pivot_spacer_spec import BORE_CALLOUT, PRESS_INTERFERENCE

CALLOUT_BELOW = 4  # swDimensionTextCalloutBelow

# Rule 4: every tight band names its mate.  The ream's band holds a light
# press on the MHA-PD-VN-57 shoulder: the interference both limits produce,
# printed outward to four inch places, on the screw named by its number.
# The length's ±.002 sets the MHA-PD-VN-63 spring's room between the arm's
# spot-face floor and the screw head (transgear_hanger_joints).
SCREW_NUMBER = _config.parts("pd-vn-transgear-pivot-screw")["number"]
SPRING_NUMBER = _config.parts("pd-vn-transgear-pivot-spring")["number"]
_PRESS_IN = (
    math.floor(PRESS_INTERFERENCE[0] / 25.4 * 1e4 + 1e-6) / 1e4,
    math.ceil(PRESS_INTERFERENCE[1] / 25.4 * 1e4 - 1e-6) / 1e4,
)
PRESS_CALLOUT = (
    f"{_PRESS_IN[0]:.4f}-{_PRESS_IN[1]:.4f}".replace("0.", ".") + " DIAMETRAL\n"
    f"INTERFERENCE ON\n{SCREW_NUMBER} SHOULDER"
)
LENGTH_CALLOUT = f"SETS {SPRING_NUMBER}\nSPRING ROOM"

# lane -> (feature, dimension) -> text.
CALLOUTS: dict[int, dict[tuple[str, str], str]] = {
    CALLOUT_BELOW: {
        ("RingProfile", "BoreDia"): f"{BORE_CALLOUT}\n{PRESS_CALLOUT}",
        ("Ring", "RingLength"): LENGTH_CALLOUT,
    },
}


def authored_text() -> dict[str, dict[str, dict[int, str]]]:
    """feature -> dimension -> lane -> text: everything the part writes."""
    authored: dict[str, dict[str, dict[int, str]]] = {}
    for lane, rows in CALLOUTS.items():
        for (feature, name), text in rows.items():
            authored.setdefault(feature, {}).setdefault(name, {})[lane] = text
    return authored


def authored_by_name() -> dict[str, dict[int, str]]:
    """dimension name -> lane -> text (the drawing's identity is the name)."""
    return {
        name: lanes
        for by_name in authored_text().values()
        for name, lanes in by_name.items()
    }


def callout_rows(text: str) -> tuple[str, ...]:
    """A callout's rows, independent of CRLF."""
    return tuple(row.strip() for row in text.replace("\r", "").split("\n"))
