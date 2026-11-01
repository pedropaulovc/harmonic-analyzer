r"""Pure-data dimensional contract shared by the tube frame column and drawing.

PURE DATA, no SolidWorks/COM imports (see ``dt_crank_arm_spec`` for the reference
split). ``build_fr_tube_frame`` imports the tube nominals + the marked-dimension
NAME map from here; ``draw_fr_tube_frame`` imports the same nominals for its view
math and keeps exactly ``DRAWING_DIMENSIONS``.
"""

from __future__ import annotations

import math

import _config
from _package_units import drawing_unit
from fr_frame_attachment_spec import (
    BASE_SCREW_Y,
    COLUMN_BOTTOM_Y,
    TUBE_CROSS_HOLE_DIAMETER,
    TUBE_CUT_LENGTH,
    TUBE_TOP_CHAMFER,
    TOP_SCREW_Y,
)


MM_PER_IN = 25.4
# The sheet prints decimal inch (issue #290, ``drawing_unit: in``).
UNIT = drawing_unit("parts/fr-tube-frame", _config.parts("fr-tube-frame"))

# --- Regular open steel tube. The lower end enters the base socket; the upper
# end receives a separately purchased recessed cap. The tube cut length follows
# the shared installed cap stack, keeping the finished cap top at Y=41.134 in. ---
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
# callout. The lower station prints; the upper one prints no number: it is
# match-drilled from MHA-FR-02's taps (the callout names that mate), whose
# installed axis lies off the .001 grid. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "AnnulusProfile": {"OuterDia"},
    "Column": {"Length"},
    "CrossHoleProfile": {"LowerHoleY", "CrossHoleDia"},
    "TopEndBreak": {"TopChamfer"},
}

# Decimal places ARE the tolerance statement (drawing-simplicity-policy.md `How the repository implements the guidelines`
# ), so the MODEL owns them: build_fr_tube_frame applies this map to the .SLDPRT
# and draw_fr_tube_frame only reads it back. The cut length prints three
# places: it follows the cap stack on the .001 grid (40.109), and rounding it
# to .XX would move it by up to .005.
# The lower station is .50 exactly. The cross hole is a .197 drill (title
# block +.004/0). The top break is a .02 deburr. OuterDia stays at the document
# default -- it is purchased stock.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "Column": {"Length": 3},
    "CrossHoleProfile": {"LowerHoleY": 2, "CrossHoleDia": 3},
    "TopEndBreak": {"TopChamfer": 2},
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
# Which edge the .02 break is on: the imported chamfer dimension's arrows sit
# on the top face's extension lines, so the suffix names the edge (MR r1/r3).
TOP_END_CHAMFER_SUFFIX = " X 45 DEG TOP END OD"

# The tube is the frame's height adjuster: MHA-FR-00 step 1 rough-cuts it
# oversize and step 4 final match-cuts it to the actual base/top/cap stack
# (drawing-guidelines.md rule 19). The sheet flags that on the length itself
# with a supply size (MR fleet: the cut-to-fit lived only in a note and no
# blank length was given). .40 over the nominal cut leaves both saw ends
# room to square and the match-cut room to absorb the stack, rounded up to the
# .XX grid the callout prints.
SUPPLY_LENGTH_ALLOWANCE = 10.16  # .40
SUPPLY_LENGTH_MIN_IN = (
    math.ceil(round((COLUMN_LENGTH + SUPPLY_LENGTH_ALLOWANCE) / MM_PER_IN * 100.0, 6))
    / 100.0
)
SUPPLY_LENGTH_MIN = SUPPLY_LENGTH_MIN_IN * MM_PER_IN
if not SUPPLY_LENGTH_MIN > COLUMN_LENGTH:
    raise AssertionError("the supplied tube is shorter than its cut length")
LENGTH_SUPPLY_CALLOUT = f"SUPPLY {SUPPLY_LENGTH_MIN_IN:.2f} MIN"
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
# MHA-FR-00 steps 1-4 (rule 24). Both lanes stay one line: a multi-line
# above-lane on this broken-leader diametric drew its shoulder as if the text
# were one 280 mm line (layout audit, run 20261023T231525949Z-3bf8c768).
CROSS_HOLE_CALLOUT = "2 STA; MATCH-DRILL THRU BOTH WALLS AT ASSEMBLY"
CROSS_HOLE_MATES_SUFFIX = " UPPER WITH MHA-FR-02, LOWER WITH MHA-FR-01"

END_VIEW_NOTE = "END VIEW SCALE 2:1"
LENGTH_VIEW_NOTE = "LENGTH VIEW SCALE 1:5"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:10"

# Frame parts carry no datums or feature-control frames under the drawing
# simplicity policy.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {}
