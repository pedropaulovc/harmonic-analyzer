"""Dimension text the MHA-MG-07 wheel axle authors on its marked dimensions.

The part builder writes every lane below on its source dimension; the
drawing imports them verbatim and only reads them back.  Setting dimension
text from the drawing writes through to the imported source dimension, and
the drawing's native save then saves the dirtied part outside its own recipe
(fleet issue #1942; the ``pd_transgear_pin_callouts`` pattern).  Kept out of
``mg_wheel_axle_spec``, which the wheel group, the bar and the magnifier
assembly import.
"""

from __future__ import annotations

from mg_wheel_axle_spec import (
    PIN_DIA,
    PIN_DIA_TOL,
    THREAD,
)

TEXT_PREFIX = 1  # swDimensionTextPrefix
TEXT_SUFFIX = 2  # swDimensionTextSuffix
CALLOUT_ABOVE = 3  # swDimensionTextCalloutAbove
CALLOUT_BELOW = 4  # swDimensionTextCalloutBelow

BAR = "MHA-MG-08 WHEEL BAR"
WHEEL = "MHA-MG-05 MAGNIFYING WHEEL"

# The shank's stock Ø is an untoleranced REF (the drill rod's supplier limits
# govern; purchased precision stock is its fit route). Its callout names both
# fits, each mate by number and name (drawing-guidelines.md rule 4; v49
# machinist review), one line each (rule 7): the bond in the bar's 3/16
# drilled bore (owner ruling 2026-11-24, fit audit question 18), whose
# clearance prints once, on the bar's own sheet, and the wheel that runs on
# it, which is what the journal's Ra 63 uin marks (rule 6). The bond's gap
# (the stock over the bore's drilled limits) is mg_wheel_group.BAR_BOND_GAP,
# inside LOCTITE 638's. The running clearance is
# mg_wheel_group.HUB_RUNNING, a literal so the wheel stays out of this part's
# recipe (test_mg_wheel_axle_drawing pins it).
PIN_LIMITS = (PIN_DIA - PIN_DIA_TOL, PIN_DIA + PIN_DIA_TOL)
RUNNING_CLEARANCE_TEXT = ".0008-.0017"
PIN_DIA_CALLOUT = "\n".join(
    (
        f"BONDED IN {BAR}",
        f"RUNNING FIT IN {WHEEL} (CLEARANCE {RUNNING_CLEARANCE_TEXT})",
    )
)
# The lengths carry their values and bands only (rule 7): the extension lines
# show the step they read from; the nut stack is MHA-MG-00's.

# One radius prints for both roots (one fillet feature): its count rides
# above the value.
RELIEF_ROOTS_CALLOUT = "2X"
# #2399: the neck's Ø rides the title block's .XXX (.066-.076); its one
# function, staying under the die's root so the die runs out in the groove,
# names the third place (rule 3; machinist review r2 asked for the reason).
RELIEF_DIA_CALLOUT = f"CLEARS {THREAD} THREAD MINOR"

# lane -> (feature, dimension) -> text.
CALLOUTS: dict[int, dict[tuple[str, str], str]] = {
    CALLOUT_ABOVE: {("ReliefRoots", "ReliefRootR"): RELIEF_ROOTS_CALLOUT},
    CALLOUT_BELOW: {
        ("PinProfile", "PinDia"): PIN_DIA_CALLOUT,
        ("PinProfile", "ReliefDia"): RELIEF_DIA_CALLOUT,
    },
}
if any("\n" in text for text in CALLOUTS[CALLOUT_ABOVE].values()):
    raise AssertionError("an above-callout with a line break never prints")

# The overall is the shank, the thread and the dome summed: a "(2.20)"
# reference (rule 10). The shank's "(Ø3/16 in)" stock reference is dressed on
# the sheet (draw_mg_wheel_axle._pin_stock_reference).
REFERENCE_TEXT: dict[tuple[str, str], dict[int, str]] = {
    ("PinProfile", "PinLength"): {TEXT_PREFIX: "(", TEXT_SUFFIX: ")"},
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
