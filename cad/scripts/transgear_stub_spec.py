r"""Pure-data dimensional contract shared by the transgear stud and drawing.

PURE DATA: keep the turned-part nominals and marked-dimension map here so a
change rebuilds both the SLDPRT and SLDDRW recipes without making the drawing
import the part build implementation.
"""

from __future__ import annotations

from _fit_limits import SHAFT_H
from _gtol_spec import CylinderFace, GeometricControl, PartDatum
from _surface_finish import MACHINED_UM, SurfaceFinishControl


MM_PER_IN = 25.4

BASE_DIA = 0.375 * MM_PER_IN  # 9.525 machine-standard stock (low)
BASE_LEN = 9.1  # bracket plate (4) + gap + latch big hub (z -125.9..-135)
SEAT_DIA = 5.0  # turned-down gear seat (feed pinion + disc bores)
SEAT_LEN = 13.8  # feed pinion 9.5 + disc 3 + slack (z -135..-148.8)
COLLAR_DIA = 14.0
COLLAR_LEN = 4.0

# Fit bands, (upper, lower) deviations in mm off the nominal above.  These
# tolerance the MODEL dimension (build_transgear_stub applies them via
# _drawing_marks.set_dimension_bilateral_tolerance) so SolidWorks renders the
# limits natively and re-renders them if the document's unit system changes.  A
# band typed as callout text on the sheet would be a frozen string instead.
#
# SEAT: the gear seat carries the 12T feed-pinion and 120T disc bores, so it is
# the shared ground-shaft h class, not a value peculiar to this part.
SEAT_DIA_BAND = SHAFT_H
# BASE: slip into the transgear bracket bore and the latch hub.  Looser than any
# _fit_limits class and specific to this stud, so it lives here beside BASE_DIA.
BASE_DIA_BAND = (0.000, -0.050)

# No geometric controls: the stud is one revolve turned in one setting, and
# its two fits are the bands on the model diameters
# (cad/docs/drawing-simplicity-policy.md rule 3). The typed tuples stay so
# build_transgear_stub's author_part_pmi call shape is unchanged.
PART_DATUMS: tuple[PartDatum, ...] = ()
GEOMETRIC_CONTROLS: tuple[GeometricControl, ...] = ()
# The gear seat is the one running surface: the feed pinion and disc turn on
# it (rule 5).
SURFACE_FINISHES = (
    SurfaceFinishControl("gear_seat", MACHINED_UM, CylinderFace(SEAT_DIA)),
)

# Marked model dimensions: the three land diameters plus three axial
# stations, every one from the base (faced) end -- 9.10 to the base
# shoulder, 22.90 to the collar shoulder, 26.90 overall -- so the machinist
# sets the DRO once (policy rule 7; machinist review 2026-09-02: the old
# per-land chain ran from three faces and left no conspicuous overall).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StubProfile": {
        "BaseDia",
        "SeatDia",
        "CollarDia",
        "BaseLength",
        "SeatEnd",
        "Overall",
    },
}

# The two concave shoulder roots (base -> seat, seat -> collar) are modelled
# sharp; the print allows the turning tool's nose radius as a leadered note
# on one shoulder rather than a fillet feature (policy rule 7: every
# shoulder fillet on a turned part has a size; machinist review 2026-09-02:
# an unspecified root is a bench question). Nothing butts hard against
# either root -- the feed pinion sits on the seat with slack -- so R0.25 MAX
# is a clearance, not a fit.
ROOT_NOTE = "2X ROOT R0.25 MAX"

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).
DRAWING_NOTES = "TURN COMPLETE IN ONE SETUP FROM 5/8 IN BAR."
