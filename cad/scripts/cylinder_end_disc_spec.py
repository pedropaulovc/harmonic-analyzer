r"""Pure-data contract for the cylinder-bank end thrust washer (MHA-121).

One washer at each end of the cylinder-gear bank, between the end gear and its
arbor-pedestal strap (issue #743). The back-side photographs (ch13
page002_img01, ch25 page002_img03) show a grey annulus of about 2.6x the ~O10
arbor dome between the strap and gear 19 (inferred, photo-scaled); the front
side shows gear 0's cam and rod directly behind the strap, with no large disc.
The back washer's thickness sits in the bank's axial datum chain
(``cylinder_bank_layout``), so it carries a held band: one facing cut per
side, checked with a micrometer.
"""

from __future__ import annotations


WASHER_OD = 25.0
WASHER_BORE = 9.6  # slips on the O9.525 (3/8 in) cylinder arbor
WASHER_THICK = 1.5
WASHER_THICK_TOLERANCE_MM = 0.05
# Running clearance on the arbor: never under the bore (drilled/reamed class).
WASHER_BORE_BAND = (0.10, 0.0)  # (upper, lower) deviations

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity policy rule 2): the thickness is held, the rest routine.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {"DiscDia", "BoreDia"},
    "Disc": {"DiscThick"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RingProfile": {"DiscDia": 1, "BoreDia": 2},
    "Disc": {"DiscThick": 2},
}
