"""Dimension text the MHA-MG-08 part authors on its marked dimensions.

The part builder writes every lane below on its source dimension; the
drawing imports them verbatim and only reads them back.  Setting dimension
text from the drawing writes through to the imported source dimension, and
the drawing's native save then saves the dirtied part outside its own recipe
(``cad/docs/pipeline/evidence/vm2-datum-placement/source-hash-cause.md``,
fleet issue #1942).

The axle's number is a literal so the wheel group and the axle stay out of
this part's recipe; ``test_mg_wheel_bar_drawing`` pins it to the axle's
config row.
"""

from __future__ import annotations

from _title_block_units import render_number
from mg_wheel_bar_spec import WALL_CALLOUT_MIN_IN

CALLOUT_BELOW = 4  # swDimensionTextCalloutBelow


def _wall_row(bore: str) -> str:
    """The hole's least wall at the full worst case, an owner-ruled minor
    (owner ruling 2026-10-26, #1532; mg_wheel_bar_spec.BORE_ROW_WALLS)."""
    return f"WALL {render_number(WALL_CALLOUT_MIN_IN[bore], 'in', 3)} MIN"


# The reamed bore names its standard fit on the axle by number (rule 4); the
# interference prints once, as REF on the axle's own sheet, keeping this
# callout to two lines of words (rule 7).
AXLE_BORE_CALLOUT = "REAM THRU\nPRESS FIT ON MHA-MG-07 AXLE\n" + _wall_row("axle bore")
# The depth's .XXX is a three-place size given a function: it sets the stack
# that places the pressed axle's end under the back face, so it names that
# stack once (rules 3 and 4); the end's range is the MHA-MG-00 assembly
# step's acceptance, not this sheet's. Two short lines keep the text right
# of the end view's extension lines inside the border (rule 14).
BAR_DEPTH_CALLOUT = "SETS MHA-MG-07\nAXLE END STACK"
# Under the drawing's own native hole callouts (drawing annotations, not
# imported model dimensions, so the sheet writes them): the hanger hole's
# least wall; the clamp pair, drilled to the printed stations and row, names
# the taps it clears, and its least wall.
HANGER_HOLE_CALLOUT = _wall_row("hanger hole")
CLAMP_HOLE_CALLOUT = "CLEARS MHA-SH-02 TAPPED HOLES\n" + _wall_row("clamp holes")

# lane -> (feature, dimension) -> text.
CALLOUTS: dict[int, dict[tuple[str, str], str]] = {
    CALLOUT_BELOW: {
        ("AxleBoreProfile", "AxleBoreDia"): AXLE_BORE_CALLOUT,
        ("Bar", "BarDepth"): BAR_DEPTH_CALLOUT,
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
