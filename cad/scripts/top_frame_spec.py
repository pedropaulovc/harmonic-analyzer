r"""Pure-data dimensional contract shared by the top-frame casting and drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_top_frame`` imports the marked-
dimension NAME map + notes from here; ``draw_top_frame`` keeps exactly
``DRAWING_DIMENSIONS`` across its per-view keep maps and imports the casting's
plan geometry (column stations, bore diameters) from ``build_top_frame`` for
its view math.

2026-08-02 rederive (ch30 px measurement anchored on the 394x224 column pitch
+ GT bundle rescale + ch19 closeups): the ring absorbed the old top-crossbar
(full-height integral bar) and the gooseneck-clamp (square-head set screw in
the east-rail hub, -X crank side), grew its rails to 34.2/38.0, gained webbed
faces, proud corner bosses, side-screw taps, hanger-stud holes and the
west-rail fulcrum-keeper taps.
"""

from __future__ import annotations


OUTER_PROFILE_TOLERANCE_MM = 0.25


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The rail outside profile and the clear window (OuterProfile
# Width/Depth + WinWidth/WinDepth) ride the plan; the corner-boss diameter
# (one boss circle of the upper boss sketch, called out 4X) and one junction
# gusset's legs (BarProfile, called out 4X) ride the plan too; the side-screw
# spot-face diameter (one circle of the front spot-face sketch, called out
# 4X) rides the front elevation, where the spot-faced boss seats are face-on.
# Rail widths, crossbar width, boss heights and the T-section are drawing
# dimensions on view edges; every hole station and size is a native hole
# table / hole callout, not a marked dimension. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "OuterProfile": {"Width", "Depth", "WinWidth", "WinDepth"},
    "BossUpProfile": {"C0Dia"},
    "SpotFaceFrontProfile": {"S0Dia"},
    "BarProfile": {"GussetRunE", "GussetRiseE"},
}

# Flag note attached to the gooseneck bore in the plan: the 1/4-20 set-screw
# tap enters the hub's east face inside the cast pocket and breaks into the
# bore, so the casting locates it -- no coordinate to print.
SET_SCREW_TAP_NOTE = "\n".join(
    (
        "1/4-20 SET-SCREW TAP",
        "AT THE CAST POCKET",
        "CENTRE, THRU TO BORE",
    )
)

# Notes: at most four lines of part-specific process fact (drawing-simplicity-
# policy.md rule 6): the casting's draft and rim breaks, which faces are
# MACHINED (Harvey #34), and which face each hole family opens from.  Every
# size and station rides the views (hole table, hole callout, marked
# dimension); the one number here is the pattern draft.
DRAWING_NOTES = "\n".join(
    (
        "GRAY IRON CASTING, 1.5 DEG MAX DRAFT, TOP-FACE RIMS C2 X 45; CAST FINISH INSIDE THE WEB PANELS.",
        "MACHINE THE RAIL BOTTOM FACE AND BOSS END LANDS; BORE COLUMN AND GOOSENECK HOLES, C1 LEAD-IN TOP END ONLY.",
        "SIDE-SCREW TAPS ON THE SPOT-FACED BOSS SEATS: FRONT PAIR FROM THE FRONT, REAR PAIR FROM THE REAR.",
        "STUD HOLES DRILLED FROM THE UNDERSIDE; KEEPER TAPS FROM THE WEST RAIL TOP; MASK BORES, LANDS AND TAPS TO COAT.",
    )
)
TOP_VIEW_NOTE = "PLAN VIEW SCALE 1:2"
FRONT_VIEW_NOTE = "FRONT VIEW SCALE 1:4"
