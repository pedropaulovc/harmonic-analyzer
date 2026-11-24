"""Dimension text the MHA-PD-20 pivot spacer authors on its marked dimensions.

The part builder writes every lane below on its source dimension; the
drawing imports them verbatim and only reads them back.  Setting dimension
text from the drawing writes through to the imported source dimension, and
the drawing's native save then saves the dirtied part outside its own recipe
(fleet issue #1942; the ``pd_transgear_pin_callouts`` pattern).  Kept out of
``pd_transgear_pivot_spacer_spec``, which the hanger joints, the arm and the
paper-drive assembly import.
"""

from __future__ import annotations

import math

import _config
from pd_transgear_pivot_spacer_spec import BOND_GAP, BORE_CALLOUT

CALLOUT_BELOW = 4  # swDimensionTextCalloutBelow

# Rule 23: a bonded seat prints its mate and the diametral clearance both
# limits produce (printed outward to four inch places), inside the grade's
# gap; the grade and the cure are MHA-PD-00's step.  A drilled hole at the
# DRILLED HOLES row is no tight band, so it prints no necessity answer
# (rule 4).  Two lines of words under the drill's row (rule 7).
# The length's ±.001 is a tight band, so it prints its one answer to rule
# 4's necessity test: with no parallelism frame its spread is the faces'
# taper, which tilts the hanger and, looser, closes the MHA-PD-06 disc's air
# to the MHA-PD-02 platen (pd_transgear_pivot_spacer_spec LENGTH_TOLERANCE;
# build_pd_paper_drive_assembly PLATEN_AIR).  One reason in three words,
# set on two rows to stand inside the lane beside the dimension.
SCREW_NUMBER = _config.parts("pd-vn-transgear-pivot-screw")["number"]
DISC_NUMBER = _config.parts("pd-rack-pinion")["number"]
PLATEN_NUMBER = _config.parts("pd-platen")["number"]
_BOND_GAP_IN = (
    math.floor(BOND_GAP[0] / 25.4 * 1e4 + 1e-6) / 1e4,
    math.ceil(BOND_GAP[1] / 25.4 * 1e4 - 1e-6) / 1e4,
)
BOND_CALLOUT = (
    f"BONDED FIT ON {SCREW_NUMBER}\n(CLEARANCE "
    + f"{_BOND_GAP_IN[0]:.4f}-{_BOND_GAP_IN[1]:.4f}".replace("0.", ".")
    + ")"
)
LENGTH_CALLOUT = f"KEEPS {DISC_NUMBER}\nCLEAR OF {PLATEN_NUMBER}"

# lane -> (feature, dimension) -> text.
CALLOUTS: dict[int, dict[tuple[str, str], str]] = {
    CALLOUT_BELOW: {
        ("RingProfile", "BoreDia"): f"{BORE_CALLOUT}\n{BOND_CALLOUT}",
        ("Ring", "RingLength"): LENGTH_CALLOUT,
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
