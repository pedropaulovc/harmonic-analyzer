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
        "1. ASYMMETRIC WEDGE ABOUT THE CONE-AXIS LINE: EAST HALF-WIDTH TAPERS",
        "   12 -> 20, WEST HALF-WIDTH FLARES 9.5 -> 37 (SEE PLAN).",
        "2. PIVOT HOLE <MOD-DIAM>6.76 (1/4 CLEARANCE) THRU AT THE NORTH TIP,",
        "   7 FROM THE NORTH EDGE; PLATE SWINGS ON THE Ø6.35 PIVOT SCREW.",
        "3. LOCK NOTCH 8 WIDE OPENS THROUGH THE WEST EDGE FOR THE LOCK KNOB.",
        "4. PLAN CORNERS ROUNDED R8 - R12 AS MODELLED.",
    )
)
PLAN_VIEW_NOTE = "PLAN VIEW SCALE 1:2"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
