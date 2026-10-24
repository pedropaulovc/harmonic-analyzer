"""Dimension text the MHA-MS-01 stick part authors on its marked dimensions.

The part builder writes each callout below its source dimension and reads it
back; the drawing imports the dimensions with that text and only reads it
back.  Setting text from the drawing writes through to the imported source
dimension (#1942; ``cad/docs/pipeline/evidence/vm2-datum-placement/
source-hash-cause.md``).  Kept out of ``ms_stick_spec``, which the measuring
stick assembly imports.
"""

from __future__ import annotations

import ms_stick_spec as part

CALLOUT_BELOW = 4  # swDimensionTextCalloutBelow

STOP_REBATE_FIT = "SLIDES IN MS-STOP-BLOCK\nMHA-MS-02 REBATE"
AMPLITUDE_STATIONS = "SETS CH-AMPLITUDE-BAR\nMHA-CH-01 STATIONS"
ENAMEL = "HOLDS ENAMEL FILL"

# dimension name -> the rows printed below its value.
CALLOUTS: dict[str, str] = {
    "BodyWidth": STOP_REBATE_FIT,
    "BodyThickness": STOP_REBATE_FIT,
    "ScaleStartX": f"SCALE ZERO CENTRELINE\n{AMPLITUDE_STATIONS}",
    "Tick0Width": f"ALL GRADUATIONS\n{ENAMEL}\n{part.GRADUATION_WIDTH_CALLOUT}",
    "TickDepth": f"GRADUATIONS ONLY, SQUARE-BOTTOM\n{ENAMEL}\n{part.GRADUATION_FLOOR_CALLOUT}",
    "FullTickLength": "FULL TICKS",
    "MinorTickLength": "MINOR TICKS",
    "HalfTickLength": "HALF-DIVISION TICK",
    "FullTickPitch": f"FULL TICK CENTRELINES\nNONCUMULATIVE FROM SCALE ZERO\n{AMPLITUDE_STATIONS}",
    "MinorTickPitch": f"MINOR TICK CENTRELINES\nNONCUMULATIVE FROM SCALE ZERO\n{AMPLITUDE_STATIONS}",
    "NumeralHeight": "NUMERAL HEIGHT",
    "NumeralXGap": "NUMERAL TO TICK EDGE",
    "NumeralYGap": "NUMERAL TO FULL-TICK END",
    "NumeralDepth": (
        f"NUMERAL DEPTH\n{part.NUMERAL_V_INCLUDED_ANGLE_DEG:g}° INCLUDED V\n{ENAMEL}\n"
        f"{part.NUMERAL_FLOOR_CALLOUT}"
    ),
}


def _owners() -> dict[str, str]:
    owners: dict[str, list[str]] = {}
    for feature, names in part.DRAWING_DIMENSIONS.items():
        for name in names:
            owners.setdefault(name, []).append(feature)
    missing = sorted(set(CALLOUTS) - set(owners))
    if missing:
        raise AssertionError(
            f"callouts name dimensions the part does not mark: {missing}"
        )
    shared = {
        name: features
        for name, features in owners.items()
        if name in CALLOUTS and len(features) != 1
    }
    if shared:
        raise AssertionError(
            f"callout dimensions marked on more than one feature: {shared}"
        )
    return {name: owners[name][0] for name in CALLOUTS}


# dimension name -> the feature that owns it (the builder's lookup key).
FEATURE_OF: dict[str, str] = _owners()


def callout_rows(text: str) -> tuple[str, ...]:
    """A callout's rows, independent of CRLF line endings."""
    return tuple(row.strip() for row in text.replace("\r", "").split("\n"))
