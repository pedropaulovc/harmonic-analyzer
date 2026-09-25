"""ASME B18.6.3 slotted fillister head machine screw head limits (inch).

Pure data.  One row per size the project buys, so a part that has to clear a
purchased screw's head reads the standard's envelope from here instead of a
vendor page or a comment.  Values: ASME B18.6.3-2013 slotted fillister head
table (head diameter A max/min, total head height O max), cross-checked
2026-09-25 against boltingspecialist.com's B18.6.3 table and Huyett's 1/4-20
fillister listing (A max .414).
"""

from __future__ import annotations

from typing import NamedTuple


class FillisterHead(NamedTuple):
    dia_max_in: float
    dia_min_in: float
    height_max_in: float  # total head height, O


FILLISTER_HEAD: dict[str, FillisterHead] = {
    "1/4": FillisterHead(dia_max_in=0.414, dia_min_in=0.389, height_max_in=0.237),
}
