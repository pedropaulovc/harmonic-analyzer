r"""Pure-data dimensional contract shared by the cone swing platform and drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_cone_swing_platform`` imports the
marked-dimension NAME map + notes from here; ``draw_cone_swing_platform`` keeps
exactly ``DRAWING_DIMENSIONS`` and imports the plate's plan geometry from
``build_cone_swing_platform`` for its view math.
"""

from __future__ import annotations

from cone_pivot_post_spec import BORE_HEIGHT as POST_CONE_BORE_HEIGHT
from crank_drive_gear_spec import OUTSIDE_DIA as CRANK_GEAR_OUTSIDE_DIA


PLATE_THICKNESS = 6.35
PLATE_LENGTH_TOLERANCE_MM = 0.25

# The recentered DP25.731 gear is smaller than the intermediate DP24.74 gear;
# its complete swept OD now clears the platform top, so the obsolete scallop is
# removed and the plate remains full thickness beneath the mesh.
CRANK_GEAR_PLATFORM_CLEARANCE = (
    POST_CONE_BORE_HEIGHT - CRANK_GEAR_OUTSIDE_DIA / 2.0
)
if CRANK_GEAR_PLATFORM_CLEARANCE < 0.5:
    raise AssertionError("recentered crank gear has under 0.5 mm platform air")


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. Only the overall axial length is marked. The axis-relative edge
# offsets in the notes define each end without duplicating north/south widths. ---
POST_MOUNT_THREAD = "1/4-20"


DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {"PlateLenDim"},
}

# Notes: coordinates the plan does not dimension natively (only the overall
# length is marked), stated once, without bands -- the title block's general
# tolerances govern (drawing-simplicity-policy.md rules 1, 2 and 6).  This
# runs past the policy's four lines because the notes are the wedge's only
# definition; it shortens as those coordinates become native dimensions.
DRAWING_NOTES = "\n".join(
    (
        "PIVOT END IS NORTH; NOTCH SIDE IS WEST. CONE AXIS IS THE CENTRELINE",
        "THROUGH THE PIVOT HOLE, NORMAL TO THE NORTH END. STATIONS ARE ALONG",
        "THE AXIS; OFFSETS ARE NORMAL TO IT, TO THE VIRTUAL-SHARP SIDE LINES.",
        "NORTH END 12.00 E / 8.00 W; SOUTH END 24.00 E / 37.00 W.",
        "PIVOT HOLE ON AXIS 7.00 SOUTH OF THE NORTH EDGE.",
        "POST-MOUNT PAIR CENTROID ON AXIS 192.174 SOUTH OF PIVOT; 26.887 PITCH",
        "ON A LINE 12.518 DEG NORTH OF WEST.",
        "LOCK NOTCH 8.00 WIDE, FULL-R CLOSED END 27.50 W / 175.00 S OF PIVOT,",
        "AXIS 8.23 DEG NORTH OF WEST, OPEN THROUGH THE WEST EDGE.",
        "PLAN CORNERS NE R10, NW R8, SW R10, SE R12. MACHINE BOTH BROAD FACES;",
        f"FINISHED THICKNESS {PLATE_THICKNESS:.2f}.",
    )
)
PLAN_VIEW_NOTE = "PLAN VIEW SCALE 1:2"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:3"
END_VIEW_NOTE = "END VIEW SCALE 1:2"
