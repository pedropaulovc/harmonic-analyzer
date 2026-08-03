r"""Fulcrum-keeper dimensional contract -- the single source of truth shared by
the part build (``build_fulcrum_keeper.py``) and its manufacturing drawing
(``draw_fulcrum_keeper.py``).

PURE DATA, no SolidWorks/COM imports: the nominal geometry (the "editable
knobs"), the screw-hole layout the drawing needs for its view math, and the
marked-dimension -> kept-dimension NAME map (see ``guide_lock_spec.py`` for
the pattern's build-graph rationale).

The keeper is the black shaft-end bracket of the top-lever fulcrum bank
(book ch. 17 p. 40 bottom-left closeup; ch. 30 top view + p008): an upright
round-topped lug sockets a bright steel ball on the fulcrum-shaft end, and
the bracket's foot is screwed down into the top-frame rail top face with one
slotted #10-24 cheese-head screw (frame-side-screw, MHA-117) in a
counterbore. 2 required, one per shaft end (the second is the same part
flipped Ry180 by the assembly).

Part frame: +X = along the shaft, OUTBOARD (toward the near shaft end);
+Y up from the foot seat; +Z across the width. The lug mid-plane (= ball
centre) is x = 0; the foot reaches inboard (-X).
"""

from __future__ import annotations


# --- Nominal geometry (mm). Derived against the 2026-08-02 top-frame
# contract: rail top face y=1036.2, fulcrum shaft axis y=1061.4 (+25.2),
# corner boss Ø52.2 proud +4.5 of the face. ---
FOOT_REACH = 23.0  # lug mid-plane -> inboard end of the foot (-X extent)
PAD_END_X = 6.5  # on-face pad stops here (x -23..-6.5); outboard of this the
# underside is relieved so nothing lands on the frame's proud corner-boss land
FOOT_H = 8.0  # foot/pad height; the bracket seats on y=0
RELIEF_H = 4.8  # relieved underside plane: 0.3 above the 4.5-proud boss land
LUG_HALF_T = 3.0  # lug half-thickness along X (lug 6.0 thick)
KEEPER_WIDTH = 14.0  # across Z (machine X when placed); extrudes symmetric
SHAFT_AXIS_H = 25.2  # ball/socket/bore centre above the foot seat
CROWN_DIA = 14.0  # full-round lug top, concentric with the shaft axis
BALL_DIA = 9.5  # bright steel ball pressed in the lug's through-socket
BORE_DIA = 6.5  # shaft clearance bore through the ball (shaft is Ø6.35)

# Screw hole: one #10 clearance drill + cheese-head counterbore in the pad
# centre. The under-head plane sits at FOOT_H - CBORE_DEPTH.
SCREW_X = -14.75  # pad centre: (-23 + -6.5) / 2
HOLE_DIA_MM = 5.105  # #10 close-clearance drill (0.201 in)
CBORE_DIA_MM = 9.5  # seats the MHA-117 slotted cheese head (Ø7 x 3), flush
CBORE_DEPTH_MM = 3.0

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. The ball/socket/bore stack and the wizard screw hole ship as
# notes + the native hole callout, not marked dims (measuring-stick
# precedent: the envelope is dimensioned, the fussy internals are prose). ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "FootProfile": {"FootReach", "PadLen"},
    "Foot": {"Depth"},
    "LugCrownProfile": {"ShaftAxisH", "CrownDia"},
}

# True free-text instructions only (native dims/datums/FCFs carry the rest).
DRAWING_NOTES = "\n".join(
    (
        "1. MAKE FROM AISI 1018 BAR; BLACK OXIDE AFTER MACHINING",
        "   (BALL STAYS BRIGHT: PRESS AFTER FINISH).",
        "2. SPHERICAL SEAT: BORE THE LUG Ø9.50 THRU ON THE SHAFT",
        "   AXIS 25.20 ABOVE THE FOOT SEAT; PRESS A Ø9.50 STEEL",
        "   BALL FLUSH-CENTERED (PROUD 1.75 EACH FACE); REAM THE",
        "   BALL Ø6.50 THRU FOR THE Ø6.35 FULCRUM-SHAFT END.",
        "3. SCREW HOLE PER CALLOUT: FOR THE #10-24 SLOTTED",
        "   CHEESE-HEAD FRAME-SIDE SCREW (MHA-117); HEAD SEATS",
        "   FLUSH IN THE CBORE.",
        "4. UNDERSIDE OUTBOARD OF THE PAD RELIEVED TO 4.80:",
        "   CLEARS THE TOP-FRAME CORNER-BOSS LAND (4.5 PROUD).",
        "5. 2 REQUIRED, ONE PER FULCRUM-SHAFT END (SECOND IS",
        "   THIS PART FLIPPED 180 DEG ABOUT VERTICAL).",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"

# Manufacturing GD&T limits consumed by the drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "screw-hole position": "0.25",
    "foot seating face flatness": "0.05",
}
