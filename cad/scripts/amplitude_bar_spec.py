r"""Amplitude-bar dimensional contract -- the single source of truth shared by
the part build (``build_amplitude_bar.py``) and its manufacturing drawing
(``draw_amplitude_bar.py``).

PURE DATA, no SolidWorks/COM imports (see ``crank_arm_spec`` for the pattern).
The nominal geometry MUST match the constants in build_amplitude_bar.py.

The bar is ~808 mm long but only 6.35 mm square, so the print shows a 1:4
full-length front view (overall length only) beside a 1:4 right view, and
dimensions the two end notches and the top pin hole in three 4:1 details
(machinist review 2026-09-02: at 1:4 the working features are edge-on, and a
note is not a location).
"""

from __future__ import annotations

from _gtol_spec import PlanarFace
from _holes import NUMBER_DRILL_MM
from _surface_finish import MACHINED_UM, SurfaceFinishControl

MM_PER_IN = 25.4

# --- Nominal geometry (DIMENSIONS.md "Chapter 15"). ---
BAR_LENGTH = 32.0 * MM_PER_IN - 4.5  # 808.3: legacy 32" (~80 cm) SHORTENED 4.5
# at the TOP by the 2026-08-02 top-frame rederive (fulcrum chain -4.5: bar top
# 1072.25 -> 1067.75, top pin 1065.9 -> 1061.4; the foot/arc contact at the
# rocker is UNCHANGED, preserving the level d=0 rest pose)
BAR_WIDTH = 0.25 * MM_PER_IN  # 6.35 square section
BAR_DEPTH = 0.25 * MM_PER_IN  # 6.35
BOTTOM_NOTCH_WIDTH = 0.125 * MM_PER_IN  # 3.175
BOTTOM_NOTCH_HEIGHT = 0.09375 * MM_PER_IN  # 2.381
TOP_NOTCH_WIDTH = 0.125 * MM_PER_IN  # 3.175
TOP_NOTCH_HEIGHT = 0.5 * MM_PER_IN  # 12.7
TOP_PIN_DROP = 0.25 * MM_PER_IN  # 6.35 hole centre below the bar top
TOP_PIN_DIA = NUMBER_DRILL_MM["#47"]  # 1.994, the wizard's #47 number drill

# --- Derived. ---
TOP_PIN_Y = BAR_LENGTH - TOP_PIN_DROP  # 801.95
NOTCH_OFFSET = (BAR_WIDTH - BOTTOM_NOTCH_WIDTH) / 2.0  # 1.5875: cheek from the face
TOP_NOTCH_FLOOR_Y = BAR_LENGTH - TOP_NOTCH_HEIGHT  # 795.6

# The bottom-notch floor slides on the rocker arm's top edge in service: the
# one surface on the bar that runs, so the one roughness symbol
# (cad/docs/drawing-simplicity-policy.md rule 5).  The floor faces DOWN into
# the open bottom end; the plane offset is n . p along that outward normal.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "slide_floor",
        MACHINED_UM,
        PlanarFace((0.0, -1.0, 0.0), -BOTTOM_NOTCH_HEIGHT),
    ),
)


# --- Marked-dimension contract.  Only the overall length is a graphical marked
# dim; the notch and pin-hole sizes/locations are sheet dimensions in the 4:1
# end details (edge picks, so no detail-view model-item import is needed). ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BarProfile": {"BarLength"},
}

# Notes (drawing-simplicity-policy.md rule 6): process facts the views cannot
# carry -- the stock, the plating allowance, the notch orientation (both
# notches live in ONE profile sketch cut thru the full depth, so
# open-to-opposite-ends / one-plane IS the model truth) and the root radius.
# Sizes, locations, the drill and the floor's Ra are on the details now.
DRAWING_NOTES = "\n".join(
    (
        f"{BAR_WIDTH:.2f} SQ BAR STOCK FACES OK AS RECEIVED; DIMS APPLY AFTER PLATING.",
        "END NOTCHES THRU THE DEPTH, OPEN TO OPPOSITE ENDS, ON ONE PLANE; ROOTS R0.40 MAX.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:8"
# The 4:1 end view looks at the TOP end (the open top notch and the hidden pin
# hole); say so -- "END VIEW" alone leaves the viewing direction to be inferred.
END_VIEW_NOTE = "TOP END VIEW SCALE 4:1"
