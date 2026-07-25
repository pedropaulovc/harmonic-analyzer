r"""Pure-data dimensional contract shared by the cone swing platform and drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_cone_swing_platform`` imports the
marked-dimension NAME map + notes from here; ``draw_cone_swing_platform`` keeps
exactly ``DRAWING_DIMENSIONS`` and imports the plate's plan geometry from
``build_cone_swing_platform`` for its view math.
"""

from __future__ import annotations


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
        "7. MACHINE BOTH BROAD FACES; FINISHED THICKNESS 6.35 +/-0.10.",
        "   DATUM A FLATNESS AND OPPOSITE-FACE PARALLELISM: SEE END VIEW.",
    )
)
PLAN_VIEW_NOTE = "PLAN VIEW SCALE 1:2"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:3"
END_VIEW_NOTE = "END VIEW SCALE 1:2"
