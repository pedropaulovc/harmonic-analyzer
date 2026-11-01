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

from _title_block_units import render_number
from mg_wheel_axle_spec import (
    BAR_BORE_LIMITS,
    BAR_BORE_PLACES,
    MM_PER_IN,
    PIN_DIA,
    PIN_DIA_TOL,
)

TEXT_PREFIX = 1  # swDimensionTextPrefix
TEXT_SUFFIX = 2  # swDimensionTextSuffix
CALLOUT_ABOVE = 3  # swDimensionTextCalloutAbove
CALLOUT_BELOW = 4  # swDimensionTextCalloutBelow

BAR = "MG-WHEEL-BAR"
WHEEL = "MG-MAGNIFYING-WHEEL"
ASSEMBLY = "MHA-MG-00"
NUT = "MHA-MG-VN-52"


def _limits(low_mm: float, high_mm: float) -> str:
    """``.XXXX-.XXXX``: an inch limit pair at the four places fits print."""
    return "-".join(
        render_number(value / MM_PER_IN, "in", BAR_BORE_PLACES)
        for value in (low_mm, high_mm)
    )


# The shank's stock Ø states the drill rod's supplier limits and both of its
# fits (drawing-guidelines.md rule 4; the matched-fit pattern: the nominal
# stays a reference, the fit is stated on its dimension): the press in the
# bar's reamed bore, and the wheel that runs on it, which is what the
# journal's Ra 63 uin marks (rule 6). The press follows from the stock and
# the bore limits; the running clearance is mg_wheel_group.HUB_RUNNING, a
# literal so the wheel stays out of this part's recipe
# (test_mg_wheel_axle_drawing pins it).
PIN_LIMITS = (PIN_DIA - PIN_DIA_TOL, PIN_DIA + PIN_DIA_TOL)
PRESS_LIMITS = (
    PIN_LIMITS[0] - BAR_BORE_LIMITS[1],
    PIN_LIMITS[1] - BAR_BORE_LIMITS[0],
)
if PRESS_LIMITS[0] <= 0.0:
    raise AssertionError(f"axle stock is not a press fit in the bar: {PRESS_LIMITS}")
RUNNING_CLEARANCE_TEXT = ".0008-.0017"
PIN_DIA_CALLOUT = "\n".join(
    (
        f"STOCK <MOD-DIAM>{_limits(*PIN_LIMITS)};",
        f"{_limits(*PRESS_LIMITS)} DIAMETRAL INTERFERENCE IN",
        f"{BAR} <MOD-DIAM>{_limits(*BAR_BORE_LIMITS)} REAMED BORE;",
        f"{RUNNING_CLEARANCE_TEXT} RUNNING CLEARANCE IN",
        f"{WHEEL} BORE",
    )
)
SHANK_LENGTH_CALLOUT = "FROM SHANK STEP"
# The thread length's band names the stack it sets and its mate (rule 4: a
# width that sets a stack names the stack): the MHA-MG-00 nut stack and its
# MHA-MG-VN-52 locknut, and the feature the length ends on. The assembled
# ".114 MAX past the locknut" is checked on MHA-MG-00 (its press-gauge
# acceptance, mg_magnifier_assembly_spec), not on this part (run
# 20261027T030250671Z review).
THREAD_LENGTH_CALLOUT = "\n".join(
    (
        "FROM SHANK STEP TO THREAD END;",
        f"SETS {ASSEMBLY} NUT STACK,",
        f"LOCKNUT {NUT}",
    )
)
# The relief's width limit keeps the first nut on full thread.
RELIEF_WIDTH_CALLOUT = f"FIRST NUT {NUT}\nON FULL THREAD"
# One radius prints for both roots (one fillet feature): its count rides
# above the value.
RELIEF_ROOTS_CALLOUT = "2X"

# lane -> (feature, dimension) -> text.
CALLOUTS: dict[int, dict[tuple[str, str], str]] = {
    CALLOUT_ABOVE: {("ReliefRoots", "ReliefRootR"): RELIEF_ROOTS_CALLOUT},
    CALLOUT_BELOW: {
        ("PinProfile", "PinDia"): PIN_DIA_CALLOUT,
        ("PinProfile", "ShankLength"): SHANK_LENGTH_CALLOUT,
        ("PinProfile", "ThreadLength"): THREAD_LENGTH_CALLOUT,
        ("PinProfile", "ReliefWidth"): RELIEF_WIDTH_CALLOUT,
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
