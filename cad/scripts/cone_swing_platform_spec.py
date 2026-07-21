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
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {"PlateLenDim"},
}

DRAWING_NOTES = "\n".join(
    (
        "1. PLAN VIEW: PIVOT END IS NORTH; NOTCH SIDE IS WEST. SHOWN CONE",
        "   AXIS PASSES THROUGH THE PIVOT-HOLE CENTRE.",
        "2. FROM CONE AXIS, EAST/WEST EDGES ARE 12.00 +/-0.10 / 9.50 +/-0.10",
        "   AT NORTH EDGE AND 20.00 +/-0.10 / 37.00 +/-0.10 AT SOUTH EDGE;",
        "   JOIN CORRESPONDING END POINTS STRAIGHT.",
        "3. PIVOT HOLE <MOD-DIAM>6.756 +0.050/0 THRU ON CONE AXIS, 7.00",
        "   +/-0.10 SOUTH OF NORTH EDGE.",
        "4. LOCK NOTCH 8.000 +0.100/0 WIDE WITH R4.000 +0.050/0 CLOSED END.",
        "   CLOSED-END CENTRE 24.50 +/-0.10 WEST AND 190.10 +/-0.10 SOUTH",
        "   OF PIVOT; AXIS 7.35 +/-0.10 DEG NORTH OF WEST; OPEN WEST END.",
        "5. PLAN CORNER RADII: NE R10.00, NW R8.00, SW R10.00, SE R12.00.",
        "6. MACHINE BOTH BROAD FACES; FINISHED THICKNESS 6.35 +/-0.10;",
        "   BROAD FACES PARALLEL WITHIN 0.10.",
    )
)
PLAN_VIEW_NOTE = "PLAN VIEW SCALE 1:3"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:3"
