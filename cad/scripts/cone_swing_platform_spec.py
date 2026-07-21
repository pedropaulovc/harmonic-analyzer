r"""Pure-data dimensional contract shared by the cone swing platform and drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_cone_swing_platform`` imports the
marked-dimension NAME map + notes from here; ``draw_cone_swing_platform`` keeps
exactly ``DRAWING_DIMENSIONS`` and imports the plate's plan geometry from
``build_cone_swing_platform`` for its view math.
"""

from __future__ import annotations


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The wedge envelope (length + the two end widths) is marked; the
# asymmetric taper, the pivot station, the lock notch and the corner radii are
# carried in the notes -- an asymmetric plan with a mouth notch dimensioned in
# full would swamp the sheet, and the plate is a swing fixture, not a precision
# outline. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {"PlateLenDim", "NorthEdge", "SouthEdge"},
}

DRAWING_NOTES = "\n".join(
    (
        "1. MACHINE FROM 6.35 PLATE. PLAN VIEW: PIVOT END IS NORTH; NOTCH SIDE",
        "   IS WEST. THE CONE-AXIS LINE PASSES THROUGH THE PIVOT-HOLE CENTRE.",
        "2. FROM THE CONE AXIS, EAST/WEST EDGES ARE 12.0/9.5 AT THE NORTH",
        "   EDGE AND 20.0/37.0 AT THE SOUTH EDGE; JOIN EACH PAIR STRAIGHT.",
        "3. PIVOT HOLE <MOD-DIAM>6.756 THRU ON THE CONE AXIS, 7.0 SOUTH OF THE",
        "   NORTH EDGE. IT CLEARS THE <MOD-DIAM>6.35 PIVOT-SCREW SHOULDER.",
        "4. LOCK NOTCH IS 8.0 WIDE WITH R4.0 CLOSED END. CLOSED-END CENTRE IS",
        "   24.5 WEST AND 190.1 SOUTH OF PIVOT; NOTCH AXIS RUNS 7.35 DEG NORTH",
        "   OF WEST AND OPENS THROUGH THE WEST EDGE.",
        "5. PLAN CORNER RADII: NE R10, NW R8, SW R10, SE R12.",
    )
)
PLAN_VIEW_NOTE = "PLAN VIEW SCALE 1:2"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
