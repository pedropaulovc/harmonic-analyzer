"""MHA-PD-05 purchased-strip receiving callouts, read only by its drawing.

The two stock sizes print as REF with their receiving maxima as callout text
(pd_platen_rack_spec's ruling comment above its DIMENSION_CALLOUTS). The
maxima are the same _gear_quality ceilings the cut-end reserve is paid at;
they print in a plain inch step at .XXX, rounded down so the print never
admits a section the cut-end envelope refuses (v49 machinist review, rule 4:
.1889 read as converted millimetres). This module keeps the presentation out
of the spec, whose edit would re-key the paper-drive assembly and its sheets.
"""

from __future__ import annotations

import math

import _gear_quality as quality
from pd_platen_rack_spec import FEED_PINION_NUMBER, GUIDE_RAIL_NUMBER, MM_PER_IN

RECEIVING_LIMIT_PLACES = 3


def _receiving_ceiling_text(limit_mm: float, purpose: str) -> str:
    """An incoming maximum floored to the plain inch step, then its mate."""
    scale = 10**RECEIVING_LIMIT_PLACES
    value = math.floor(round(limit_mm / MM_PER_IN * scale, 9)) / scale
    return f"{value:.{RECEIVING_LIMIT_PLACES}f} MAX{purpose}".removeprefix("0")


DIMENSION_CALLOUTS = {
    "RackHeight": _receiving_ceiling_text(
        quality.rack_stock_height_max_mm(), f"\nCLEARS {GUIDE_RAIL_NUMBER}"
    ),
    "RackDepth": _receiving_ceiling_text(
        quality.rack_face_width_max_mm(), f" FOR {FEED_PINION_NUMBER} MESH"
    ),
}
