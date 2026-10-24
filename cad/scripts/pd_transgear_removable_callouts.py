"""Native callout rows the MHA-PD-09 part authors on its marked dimensions.

The part builder writes each row on its source dimension; the drawing imports
them verbatim and only reads them back.  Setting dimension text from the
drawing writes through to the imported source dimension, and the drawing's
native save then saves the dirtied part outside its own recipe
(``cad/docs/pipeline/evidence/vm2-datum-placement/source-hash-cause.md``).
Kept out of ``pd_transgear_removable_spec``, which the chain solver and the
assemblies import.
"""

from __future__ import annotations

CALLOUT_ABOVE = 3  # swDimensionTextCalloutAbove
CALLOUT_BELOW = 4  # swDimensionTextCalloutBelow

# The pins the drive-pin holes slip over are pressed into these two parts.
CRANKSHAFT_NUMBER = "MHA-DT-11"
KNOB_COLLAR_NUMBER = "MHA-PD-22"

# Each pin centre's band serves those drive pins, so each location names
# them, in rows narrow enough to stop short of the T12 / T18 view labels.
PIN_LOCATION_CALLOUT = (
    f"SLIP FIT OVER\nPINS IN\n{CRANKSHAFT_NUMBER} AND\n{KNOB_COLLAR_NUMBER}"
)
# The plate band serves the chain's axial float on the supplied plate; the
# rows stand off the thickness dimension's lower arrow by leading spaces.
PLATE_CALLOUT = "   SUPPLIED PLATE; SETS\n   ANSI #25 CHAIN FLOAT"

# lane -> (feature, dimension) -> text.  The two pin holes share one size:
# the +Y hole's diameter prints for both, as "2X".  Both holes and the bore
# are drilled through: the title block's DRILLED HOLES row governs their
# sizes.  A linear dimension's above lane does not print, so the pin
# locations carry their mates below.
CALLOUTS: dict[int, dict[tuple[str, str], str]] = {
    CALLOUT_ABOVE: {("BorePinsProfile", "PinPosDia"): "2X"},
    CALLOUT_BELOW: {
        ("BorePinsProfile", "BoreDiaDim"): "DRILL THRU",
        ("BorePinsProfile", "PinPosDia"): "DRILL THRU",
        ("BorePinsProfile", "PinPosY"): PIN_LOCATION_CALLOUT,
        ("BorePinsProfile", "PinNegY"): PIN_LOCATION_CALLOUT,
        ("BlankProfile", "BlankWidth"): PLATE_CALLOUT,
    },
}


def callout_rows(text: str) -> tuple[str, ...]:
    """A callout's rows, independent of CRLF and of the standoff spaces."""
    return tuple(row.strip() for row in text.replace("\r", "").split("\n"))


def callouts_by_name(lane: int) -> dict[str, str]:
    """One lane's rows keyed by dimension name (the drawing's identity)."""
    return {name: text for (_feature, name), text in CALLOUTS[lane].items()}
