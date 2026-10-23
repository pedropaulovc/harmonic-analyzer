r"""Pure-data dimensional contract shared by the tube frame column and drawing.

PURE DATA, no SolidWorks/COM imports (see ``dt_crank_arm_spec`` for the reference
split). ``build_fr_tube_frame`` imports the tube nominals + the marked-dimension
NAME map from here; ``draw_fr_tube_frame`` imports the same nominals for its view
math and keeps exactly ``DRAWING_DIMENSIONS``.
"""

from __future__ import annotations

import math

from fr_frame_attachment_spec import (
    BASE_SCREW_Y,
    COLUMN_BOTTOM_Y,
    TUBE_CROSS_HOLE_DIAMETER,
    TUBE_CUT_LENGTH,
    TUBE_TOP_CHAMFER,
    TOP_SCREW_Y,
)


MM_PER_IN = 25.4

# --- Regular open steel tube. The lower end enters the base socket; the upper
# end receives a separately purchased recessed cap. The tube cut length follows
# the shared installed cap stack, keeping the finished cap top at Y=1044.8. ---
OUTER_DIA = 1.0 * MM_PER_IN  # 25.4
WALL_THICKNESS = 0.12 * MM_PER_IN  # 3.048
INNER_DIA = OUTER_DIA - 2.0 * WALL_THICKNESS  # 19.304
COLUMN_LENGTH = TUBE_CUT_LENGTH
TOP_END_CHAMFER = TUBE_TOP_CHAMFER

# --- Matched cross-drilling stations, part-local Y from the inserted end. ---
LOWER_CROSS_HOLE_Y = BASE_SCREW_Y - COLUMN_BOTTOM_Y
UPPER_CROSS_HOLE_Y = TOP_SCREW_Y - COLUMN_BOTTOM_Y
CROSS_HOLE_DIAMETER = TUBE_CROSS_HOLE_DIAMETER

# --- Marked-dimension contract: feature -> parametric dimensions kept by the
# drawing. The hole diameter is shown once with a 2-station THRU BOTH WALLS
# callout; both axial stations remain independently inspectable from the bottom. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "AnnulusProfile": {"OuterDia"},
    "Column": {"Length"},
    "CrossHoleProfile": {"LowerHoleY", "UpperHoleY", "CrossHoleDia"},
    "TopEndBreak": {"TopChamfer"},
}

# Decimal places ARE the tolerance statement (drawing-simplicity-policy.md `How the repository implements the guidelines`
# ), so the MODEL owns them: build_fr_tube_frame applies this map to the .SLDPRT
# and draw_fr_tube_frame only reads it back. Two places on the cross-hole trio
# because all three are MATCH-DRILLED from the assembled frame and the sheet's
# stations are what the fitter sets up to -- 12.70 and 992.55 are exact
# 0.5/39.077 in conversions, and rounding them to .X would move the upper
# station by half a millimetre. One place on the cut length and the top break:
# the length is final-match-cut to the actual stack, and a 0.5 chamfer is a
# deburr. OuterDia stays at the document default -- it is purchased stock.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "Column": {"Length": 1},
    "CrossHoleProfile": {"LowerHoleY": 2, "UpperHoleY": 2, "CrossHoleDia": 2},
    "TopEndBreak": {"TopChamfer": 1},
}

_PRECISION_NAMES = [
    (feature, name) for feature, names in DRAWING_PRECISION.items() for name in names
]
if any(
    name not in DRAWING_DIMENSIONS.get(feature, frozenset())
    for feature, name in _PRECISION_NAMES
):
    raise AssertionError("DRAWING_PRECISION names a dimension the part never marks")
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: DRAWING_PRECISION[feature][name] for feature, name in _PRECISION_NAMES
}
if len(DRAWING_PRECISION_BY_NAME) != len(_PRECISION_NAMES):
    raise AssertionError("DRAWING_PRECISION repeats a dimension name across features")

TOP_END_CALLOUT = "MHA-FR-VN-54 CAP MUST SEAT FULLY BY HAND"
# Which edge the 0.5 break is on: the imported chamfer dimension's arrows sit
# on the top face's extension lines, so the suffix names the edge (MR r1/r3).
TOP_END_CHAMFER_SUFFIX = " X 45 DEG TOP END OD"

# The tube is the frame's height adjuster: MHA-FR-00 step 1 rough-cuts it
# oversize and step 4 final match-cuts it to the actual base/top/cap stack
# (drawing-guidelines.md rule 19). The sheet flags that on the length itself
# with a supply size (MR fleet: the cut-to-fit lived only in a note and no
# blank length was given). 10 mm over the nominal cut leaves both saw ends
# room to square and the match-cut room to absorb the stack, rounded up to a
# 5 mm saw mark.
SUPPLY_LENGTH_ALLOWANCE = 10.0
SUPPLY_LENGTH_MIN = math.ceil((COLUMN_LENGTH + SUPPLY_LENGTH_ALLOWANCE) / 5.0) * 5.0
if not SUPPLY_LENGTH_MIN > COLUMN_LENGTH:
    raise AssertionError("the supplied tube is shorter than its cut length")
LENGTH_SUPPLY_CALLOUT = f"SUPPLY {SUPPLY_LENGTH_MIN:.0f} MIN"
LENGTH_FIT_CALLOUT = "\n".join(
    (
        "CUT TO FIT AT ASSEMBLY",
        "MHA-FR-01/MHA-FR-02/",
        "MHA-FR-VN-54 STACK",
    )
)

# drawing-guidelines.md rule 7 (flag it where it applies): each station's
# match-drill mate rides on the cross-hole callout itself, so the sheet needs
# no free note. Marking, height setting and the match-cut sequence are
# MHA-FR-00 steps 1-4 (rule 24).
CROSS_HOLE_CALLOUT = "\n".join(
    (
        "2 STA; MATCH-DRILL CLEARANCE THRU BOTH WALLS",
        "AT ASSEMBLY: UPPER STA WITH MHA-FR-02,",
        "LOWER STA WITH MHA-FR-01",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 2:1"
LENGTH_VIEW_NOTE = "LENGTH VIEW SCALE 1:5"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:10"

# Frame parts carry no datums or feature-control frames under the drawing
# simplicity policy.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {}
