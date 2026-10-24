"""Dimension text the MHA-MG-08 part authors on its marked dimensions.

The part builder writes every lane below on its source dimension; the
drawing imports them verbatim and only reads them back.  Setting dimension
text from the drawing writes through to the imported source dimension, and
the drawing's native save then saves the dirtied part outside its own recipe
(``cad/docs/pipeline/evidence/vm2-datum-placement/source-hash-cause.md``,
fleet issue #1942).

The press interference and the axle back end's range are literals so the
wheel group and the axle stay out of this part's recipe;
``test_mg_wheel_bar_drawing`` pins them to ``mg_wheel_group.BAR_PRESS`` and
``mg_wheel_axle_spec``.
"""

from __future__ import annotations

CALLOUT_BELOW = 4  # swDimensionTextCalloutBelow

# The reamed bore names its press fit on the axle (rule 4).
AXLE_BORE_CALLOUT = "REAM THRU\nPRESS FIT MG-WHEEL-AXLE\n0.010-0.030 INTERFERENCE"
# The depth's band places the pressed axle's back end on the back face.
BAR_DEPTH_CALLOUT = "MG-WHEEL-AXLE BACK END\n0.35 PROUD TO 1.55 SUNK"
# One row for every bore; its band is the clamp holes' on the MHA-SH-02 taps
# (mg_wheel_bar_spec.CLAMP_POSITION_BAND).
BORE_ROW_CALLOUT = "ALL BORES;\nCLAMP HOLES TO\nMHA-SH-02 TAPS"
# Under the drawing's own native 2X clamp-hole callout: the taps the banded
# stations and row locate the holes to.  A drawing annotation, not an
# imported model dimension, so the sheet writes it.
CLAMP_HOLE_CALLOUT = "LOCATE TO MHA-SH-02 TAPS"

# lane -> (feature, dimension) -> text.
CALLOUTS: dict[int, dict[tuple[str, str], str]] = {
    CALLOUT_BELOW: {
        ("AxleBoreProfile", "AxleBoreDia"): AXLE_BORE_CALLOUT,
        ("Bar", "BarDepth"): BAR_DEPTH_CALLOUT,
        ("BoreRowReference", "BoreRowFromTop"): BORE_ROW_CALLOUT,
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
