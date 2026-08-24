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
PIVOT_BEARING_RELIEF_DIAMETER = 10.50
PIVOT_BEARING_RELIEF_DEPTH = 0.25
PIVOT_BEARING_THICKNESS = PLATE_THICKNESS - PIVOT_BEARING_RELIEF_DEPTH
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

DRAWING_NOTES = "\n".join(
    (
        "1. PLAN VIEW: PIVOT END IS NORTH; NOTCH SIDE IS WEST. CONE AXIS IS THE",
        "   CENTRELINE THROUGH THE PIVOT-HOLE AXIS NORMAL TO THE NORTH END PLANE.",
        "   N/S DISTANCES ARE ALONG AXIS; E/W OFFSETS ARE NORMAL TO AXIS.",
        "2. END OFFSETS LOCATE VIRTUAL-SHARP INTERSECTIONS OF UNFILLETED END",
        "   AND STRAIGHT SIDE LINES: N EAST/WEST 12.00 +/-0.10 / 8.00 +/-0.10;",
        "   S EAST/WEST 24.00 +/-0.10 / 37.00 +/-0.10; SOUTH EDGE 223.354",
        "   +/-0.10 FROM PIVOT WITH 3.175 MIN POST-RIM CLEARANCE. APPLY RADII.",
        "3. PIVOT HOLE SIZE PER PLAN-VIEW CALLOUT. CENTRE ON CONE AXIS,",
        "   7.00 +/-0.10 SOUTH OF NORTH EDGE. HOLD THE AXIS PERPENDICULAR TO THE",
        "   MACHINED BROAD FACES WITHIN 0.10 DIA.",
        f"   TOP RELIEF DIA {PIVOT_BEARING_RELIEF_DIAMETER:.2f} X "
        f"{PIVOT_BEARING_RELIEF_DEPTH:.2f} DEEP;",
        f"   LOCAL BEARING THICKNESS {PIVOT_BEARING_THICKNESS:.2f} +/-0.05.",
        f"4. POST MOUNT: 2X {POST_MOUNT_THREAD} UNC-2B THRU PER PLAN-VIEW CALLOUT.",
        "   PAIR CENTROID ON CONE AXIS, 192.174 +/-0.10 SOUTH OF PIVOT; 26.887",
        "   +/-0.10 PITCH ON A LINE 12.5182 +/-0.10 DEG NORTH OF WEST.",
        "5. LOCK NOTCH 8.000 +0.100/0 WIDE; FULL-R CLOSED END (R4.000 REF).",
        "   CLOSED-END CENTRE 27.50 +/-0.10 WEST AND 175.00 +/-0.10 SOUTH",
        "   OF PIVOT; AXIS 8.23 +/-0.10 DEG NORTH OF WEST. RUN PARALLEL SIDES",
        "   FROM END TANGENCIES THROUGH THE WEST PROFILE; OPEN THROUGH EDGE.",
        "6. PLAN CORNER RADII: NE R10.00, NW R8.00, SW R10.00, SE R12.00.",
        "   HOLD EACH OF THE 2X LONG STRAIGHT PLAN EDGES STRAIGHT WITHIN 0.25.",
        f"7. CRANK-GEAR SWEPT OD CLEARS THE LOWER BROAD FACE BY "
        f"{CRANK_GEAR_PLATFORM_CLEARANCE:.3f} REF;",
        "   KEEP THE PLATE FULL THICKNESS BENEATH THE GEAR.",
        "8. MACHINE BOTH BROAD FACES; FINISHED THICKNESS 6.35 +/-0.10.",
        "   HOLD EACH BROAD FACE FLAT WITHIN 0.10 AND THE TWO PARALLEL WITHIN 0.10.",
    )
)
PLAN_VIEW_NOTE = "PLAN VIEW SCALE 1:2"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:3"
END_VIEW_NOTE = "END VIEW SCALE 1:2"
