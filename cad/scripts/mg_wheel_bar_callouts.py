"""Dimension text the MHA-MG-08 part authors on its marked dimensions.

The part builder writes every lane below on its source dimension; the
drawing imports them verbatim and only reads them back.  Setting dimension
text from the drawing writes through to the imported source dimension, and
the drawing's native save then saves the dirtied part outside its own recipe
(``cad/docs/pipeline/evidence/vm2-datum-placement/source-hash-cause.md``,
fleet issue #1942).

The axle's number, the press interference and the axle back end's range are
literals so the wheel group and the axle stay out of this part's recipe;
``test_mg_wheel_bar_drawing`` pins them to the axle's config row,
``mg_wheel_group.BAR_PRESS`` and ``mg_wheel_axle_spec``.
"""

from __future__ import annotations

from _title_block_units import render_number
from mg_wheel_bar_spec import WALL_CALLOUT_MIN_IN

CALLOUT_BELOW = 4  # swDimensionTextCalloutBelow


def _wall_row(bore: str) -> str:
    """The hole's least wall at the full worst case, an owner-ruled minor
    (owner ruling 2026-10-26, #1532; mg_wheel_bar_spec.BORE_ROW_WALLS)."""
    return f"WALL {render_number(WALL_CALLOUT_MIN_IN[bore], 'in', 3)} MIN"


# The reamed bore names its press fit on the axle by number (rule 4).
AXLE_BORE_CALLOUT = (
    "REAM THRU\nPRESS FIT MHA-MG-07 AXLE\n.0003-.0012 DIAMETRAL\nINTERFERENCE\n"
    + _wall_row("axle bore")
)
# The depth's band places the pressed axle's back end on the back face.
BAR_DEPTH_CALLOUT = "MHA-MG-07 AXLE BACK END\n.008 TO .040 SUNK"
# The clamp pair's row: its band is the MHA-SH-02 taps'
# (mg_wheel_bar_spec.CLAMP_POSITION_BAND).
CLAMP_ROW_CALLOUT = "2X CLAMP HOLES TO\nMHA-SH-02 TAPS"
# Under the drawing's own native hole callouts (drawing annotations, not
# imported model dimensions, so the sheet writes them): the hanger hole's
# least wall; the taps the clamp pair's banded stations and row locate them
# to, and their least wall.
HANGER_HOLE_CALLOUT = _wall_row("hanger hole")
CLAMP_HOLE_CALLOUT = "LOCATE TO MHA-SH-02 TAPS\n" + _wall_row("clamp holes")

# lane -> (feature, dimension) -> text.
CALLOUTS: dict[int, dict[tuple[str, str], str]] = {
    CALLOUT_BELOW: {
        ("AxleBoreProfile", "AxleBoreDia"): AXLE_BORE_CALLOUT,
        ("Bar", "BarDepth"): BAR_DEPTH_CALLOUT,
        ("BoreRowReference", "ClampRowFromTop"): CLAMP_ROW_CALLOUT,
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
