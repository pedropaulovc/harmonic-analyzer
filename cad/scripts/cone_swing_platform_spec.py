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
        "1. PLAN VIEW: PIVOT END IS NORTH; NOTCH SIDE IS WEST. DATUM B IS THE",
        "   PIVOT-HOLE AXIS; DATUM C IS THE NORTH END PLANE. CONE AXIS IS THE",
        "   CENTRELINE THROUGH B NORMAL TO C.",
        "   N/S DISTANCES ARE ALONG AXIS; E/W OFFSETS ARE NORMAL TO AXIS.",
        "2. END OFFSETS LOCATE VIRTUAL-SHARP INTERSECTIONS OF UNFILLETED END",
        "   AND STRAIGHT SIDE LINES: N EAST/WEST 12.00 +/-0.10 / 9.50 +/-0.10;",
        "   S EAST/WEST 24.00 +/-0.10 / 37.00 +/-0.10. APPLY TANGENT RADII.",
        "3. PIVOT HOLE SIZE PER PLAN-VIEW CALLOUT. CENTRE ON CONE AXIS,",
        "   7.00 +/-0.10 SOUTH OF NORTH EDGE. AXIS PERPENDICULARITY TO A: SEE FCF.",
        f"4. POST MOUNT: 2X {POST_MOUNT_THREAD} UNC-2B THRU PER PLAN-VIEW CALLOUT.",
        "   PAIR CENTROID ON CONE AXIS, 235.901 +/-0.10 SOUTH OF PIVOT; 26.887",
        "   +/-0.10 PITCH ON A LINE 12.5182 +/-0.10 DEG NORTH OF WEST.",
        "5. LOCK NOTCH 8.000 +0.100/0 WIDE; FULL-R CLOSED END (R4.000 REF).",
        "   CLOSED-END CENTRE 24.50 +/-0.10 WEST AND 190.10 +/-0.10 SOUTH",
        "   OF PIVOT; AXIS 7.35 +/-0.10 DEG NORTH OF WEST. RUN PARALLEL SIDES",
        "   FROM END TANGENCIES THROUGH THE WEST PROFILE; OPEN THROUGH EDGE.",
        "6. PLAN CORNER RADII: NE R10.00, NW R8.00, SW R10.00, SE R12.00.",
        "   LONG STRAIGHT PLAN-EDGE FORM: SEE STRAIGHTNESS FCF.",
        f"7. CRANK-GEAR SWEPT OD CLEARS DATUM A BY {CRANK_GEAR_PLATFORM_CLEARANCE:.3f} REF;",
        "   KEEP THE PLATE FULL THICKNESS BENEATH THE GEAR.",
        "8. MACHINE BOTH BROAD FACES; FINISHED THICKNESS 6.35 +/-0.10.",
        "   DATUM A FLATNESS AND OPPOSITE-FACE PARALLELISM: SEE END VIEW.",
    )
)
PLAN_VIEW_NOTE = "PLAN VIEW SCALE 1:2"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:3"
END_VIEW_NOTE = "END VIEW SCALE 1:2"
