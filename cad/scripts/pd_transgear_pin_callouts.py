"""Dimension text the MHA-PD-23 part authors on its marked dimensions.

The part builder writes every lane below on its source dimension; the
drawing imports them verbatim and only reads them back.  Setting dimension
text from the drawing writes through to the imported source dimension, and
the drawing's native save then saves the dirtied part outside its own recipe
(``cad/docs/pipeline/evidence/vm2-datum-placement/source-hash-cause.md``,
fleet issue #1942).  Kept out of ``pd_transgear_pin_spec``, which the cluster
fit, the bushings and the paper-drive assembly import.
"""

from __future__ import annotations

import pd_vn_transgear_retaining_ring_spec as RING
from pd_cluster_stack_band import STACK_NAME, STACK_SHEET
from pd_transgear_pin_spec import (
    ARM_NUMBER,
    PRESS_INTERFERENCE,
    RING_NUMBER,
    RUNNING_MATES,
    SEAT_FILLET_SUFFIX,
    inch_text,
)

TEXT_PREFIX = 1  # swDimensionTextPrefix
TEXT_SUFFIX = 2  # swDimensionTextSuffix
CALLOUT_ABOVE = 3  # swDimensionTextCalloutAbove
CALLOUT_BELOW = 4  # swDimensionTextCalloutBelow

# The ring the groove takes, named once above the groove Ø (one line: an
# above-callout holding a line break is stored but never printed).
GROOVE_CALLOUT = f"FOR {RING_NUMBER} RING, McMASTER {RING.SKU}"
# The groove width's catalogue band names the same ring at its own callout
# (rule 4: every tight band names its mate).
GROOVE_WIDTH_CALLOUT = f"FOR {RING_NUMBER} RING"
# The shank's band names its two fits at the Ø (rule 4, review of 6de7230aa
# and the 2026-10-23 ENFORCE review): the press in the arm's ream and the
# running bores whose bearing surface the Ra 63 marks.
SHANK_CALLOUT = "\n".join(
    (
        f"PRESS FIT IN {ARM_NUMBER} REAM,",
        f"{inch_text(PRESS_INTERFERENCE[0], 4)}-{inch_text(PRESS_INTERFERENCE[1], 4)} "
        "DIAMETRAL INTERFERENCE;",
        f"RUNS IN {', '.join(RUNNING_MATES)}",
    )
)
# The .0007 band station names the stack it serves and what it holds (rule 4;
# machinist review round 2): a term of the disc cluster's printed stack
# (``transgear_cluster_fit.GS``), which no part is faced or shimmed to close
# (owner ruling #2038), so the band itself holds the disc's end float.
GROOVE_STATION_CALLOUT = (
    f"TO RING LOAD WALL;\n{STACK_NAME} ({STACK_SHEET}),\nHOLDS END FLOAT, NO FIT-UP"
)
# The seat's root radius names what it keeps (rule 4): the head seats flat on
# the arm's rear face, its root clear of the ream mouth's deburr.
SEAT_RADIUS_CALLOUT = f"HEAD SEATS FLAT ON\n{ARM_NUMBER} REAM MOUTH"

# lane -> (feature, dimension) -> text.
CALLOUTS: dict[int, dict[tuple[str, str], str]] = {
    CALLOUT_ABOVE: {("PinProfile", "GrooveDia"): GROOVE_CALLOUT},
    CALLOUT_BELOW: {
        ("PinProfile", "ShankDia"): SHANK_CALLOUT,
        ("PinProfile", "GrooveStation"): GROOVE_STATION_CALLOUT,
        ("PinProfile", "GrooveWidth"): GROOVE_WIDTH_CALLOUT,
        ("SeatFillet", "SeatRadius"): SEAT_RADIUS_CALLOUT,
    },
    # The root radius is a single limit: the modelled size IS the max, and
    # the part authors the MAX (SolidWorks' native swTolMAX prints "max.").
    TEXT_SUFFIX: {("SeatFillet", "SeatRadius"): SEAT_FILLET_SUFFIX},
}
if any("\n" in text for text in CALLOUTS[CALLOUT_ABOVE].values()):
    raise AssertionError("an above-callout with a line break never prints")

# The dome heights follow from each radius on its land's Ø, and the land
# ahead of the groove from the tip apex's station, the load wall's and the
# tip dome: all three print as REFERENCES, "(.03)", "(.04)", "(.12)"
# (rules 10 and 11: the land ends at the dome's junction, which the shop
# cannot pick up).
REFERENCE_TEXT: dict[tuple[str, str], dict[int, str]] = {
    ("HeadDomeProfile", "HeadDomeSagDim"): {TEXT_PREFIX: "(", TEXT_SUFFIX: ")"},
    ("TipDomeProfile", "TipDomeSagDim"): {TEXT_PREFIX: "(", TEXT_SUFFIX: ")"},
    ("PinProfile", "FrontLand"): {TEXT_PREFIX: "(", TEXT_SUFFIX: ")"},
}


def authored_text() -> dict[str, dict[str, dict[int, str]]]:
    """feature -> dimension -> lane -> text: everything the part writes."""
    authored: dict[str, dict[str, dict[int, str]]] = {}
    for lane, rows in CALLOUTS.items():
        for (feature, name), text in rows.items():
            authored.setdefault(feature, {}).setdefault(name, {})[lane] = text
    for (feature, name), lanes in REFERENCE_TEXT.items():
        authored.setdefault(feature, {}).setdefault(name, {}).update(lanes)
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


def callouts_by_lane(lane: int) -> dict[str, str]:
    """One lane's rows keyed by dimension name (the drawing's identity)."""
    return {name: text for (_feature, name), text in CALLOUTS[lane].items()}
