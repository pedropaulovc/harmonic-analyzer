"""Dimension text the MHA-PD-09 part authors on its marked dimensions.

The part builder writes every lane below on its source dimension; the
drawing imports them verbatim and only reads them back.  Setting dimension
text from the drawing writes through to the imported source dimension, and
the drawing's native save then saves the dirtied part outside its own recipe
(``cad/docs/pipeline/evidence/vm2-datum-placement/source-hash-cause.md``).
Kept out of ``pd_transgear_removable_spec``, which the chain solver and the
assemblies import.
"""

from __future__ import annotations

import _config
from pd_transgear_removable_spec import BORE_DRILL, PIN_HOLE_DRILL

TEXT_PREFIX = 1  # swDimensionTextPrefix
TEXT_SUFFIX = 2  # swDimensionTextSuffix
CALLOUT_ABOVE = 3  # swDimensionTextCalloutAbove
CALLOUT_BELOW = 4  # swDimensionTextCalloutBelow

# The pins the drive-pin holes slip over are pressed into these two parts.
CRANKSHAFT_NUMBER = "MHA-DT-11"
KNOB_COLLAR_NUMBER = "MHA-PD-22"
# The #25 chain the plate band serves, by its drawing number (rule 4).
CHAIN_NUMBER = _config.parts("sh-vn-chain-link")["number"]

# Rule 7: the drive-pin pattern names its mates once, on its 2X callout, in a
# standard fit name; each location carries only its value and band.
PIN_HOLE_CALLOUT = (
    f"{PIN_HOLE_DRILL[0]} DRILL THRU\nSLIDING FIT ON PINS OF\n"
    f"{CRANKSHAFT_NUMBER} AND {KNOB_COLLAR_NUMBER}"
)
# The plate band serves the chain's axial float on the supplied plate; the
# rows stand off the thickness dimension's lower arrow by leading spaces.
PLATE_CALLOUT = f"   SUPPLIED PLATE; SETS\n   FLOAT OF CHAIN {CHAIN_NUMBER}"

# lane -> (feature, dimension) -> text.  The two pin holes share one size:
# the +Y hole's diameter prints for both, as "2X".  Both holes and the bore
# are drilled through with the named drill: the title block's DRILLED HOLES
# row governs their sizes.
CALLOUTS: dict[int, dict[tuple[str, str], str]] = {
    CALLOUT_ABOVE: {("BorePinsProfile", "PinPosDia"): "2X"},
    CALLOUT_BELOW: {
        ("BorePinsProfile", "BoreDiaDim"): f"{BORE_DRILL[0]} DRILL THRU",
        ("BorePinsProfile", "PinPosDia"): PIN_HOLE_CALLOUT,
        ("BlankProfile", "BlankWidth"): PLATE_CALLOUT,
    },
}

# The supplied outside diameter prints once per configuration's view as a
# REFERENCE: "(Ø2.05)".  A custom prefix replaces the automatic diameter
# glyph, so it carries SOLIDWORKS' own <MOD-DIAM> token.  Each view proves
# it (the drawing's ``_assert_outside_diameter``).
REFERENCE_TEXT: dict[tuple[str, str], dict[int, str]] = {
    ("BlankProfile", "BlankDia"): {TEXT_PREFIX: "(<MOD-DIAM>", TEXT_SUFFIX: ")"},
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


def callout_rows(text: str) -> tuple[str, ...]:
    """A callout's rows, independent of CRLF and of the standoff spaces."""
    return tuple(row.strip() for row in text.replace("\r", "").split("\n"))


def callouts_by_name(lane: int) -> dict[str, str]:
    """One lane's rows keyed by dimension name (the drawing's identity)."""
    return {name: text for (_feature, name), text in CALLOUTS[lane].items()}
