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
# Slotted cap screw in the collar's face (ch23 p.59 page002_img04: a brass
# collar with a small slotted round head in its centre; modelled integral).
CAP_DIA = 5.0
CAP_LEN = 1.5  # proud of the collar face
CAP_SLOT_W = 0.8
CAP_SLOT_D = 0.6

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

# Geometric controls, authored on the model as plain annotations by the part build
# (_part_pmi.author_part_pmi) and IMPORTED onto the sheet — the sheet types no
# tolerance strings. The slotted cap shares the seat diameter, so the seat
# selector also names an axial station inside its span.
SEAT_FACE = CylinderFace(
    SEAT_DIA,
    contains_y_mm=BASE_LEN + SEAT_LEN / 2.0,
)
PART_DATUMS = (
    # The stud base axis the seat runout is measured against.
    PartDatum("A", CylinderFace(BASE_DIA)),
)
GEOMETRIC_CONTROLS = (
    GeometricControl(
        "seat_cylindricity", "cylindricity", "0.01", SEAT_FACE
    ),
    GeometricControl(
        "seat_runout", "circular_runout", "0.03", SEAT_FACE, datums=("A",)
    ),
)
SURFACE_FINISHES = (
    SurfaceFinishControl("gear_seat", MACHINED_UM, SEAT_FACE),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StubProfile": {
        "BaseDia",
        "SeatDia",
        "CollarDia",
        "BaseLength",
        "SeatLength",
        "CollarLength",
    },
}

DRAWING_NOTES = "\n".join(
    (
        "TURN FROM 16 MM (5/8 IN) BAR IN ONE SETUP; SEAT AND COLLAR "
        "CONCENTRIC WITH BASE.",
        f"COLLAR AND CAP BRIGHT BRASS; CAP DIA {CAP_DIA:.2f} X {CAP_LEN:.2f} PROUD OF THE "
        f"COLLAR FACE WITH A {CAP_SLOT_W:.2f} X {CAP_SLOT_D:.2f} SLOT (MODELLED INTEGRAL).",
    )
)
