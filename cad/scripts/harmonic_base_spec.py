r"""Dimensional contract shared by the harmonic base and its drawing.

PURE DATA, no SolidWorks/COM imports (see ``crank_arm_spec`` for the reference
split). ``build_harmonic_base`` imports the plate nominal geometry + the
marked-dimension NAME map from here; ``draw_harmonic_base`` imports the same
geometry for its view math and keeps exactly ``DRAWING_DIMENSIONS`` across its
per-view ``keep`` maps, so the part-side marks and the drawing-side keeps cannot
silently drift.
"""

from __future__ import annotations

MM_PER_IN = 25.4

# --- Two-plate welded base (book ch. 6), centred on the part origin. ---
BOTTOM_LENGTH = 18.0 * MM_PER_IN  # 457.2 (46 cm callout)
FORMER_BOTTOM_WIDTH = 11.0 * MM_PER_IN  # 279.4 (28 cm callout)
BOTTOM_FRONT_Z = -FORMER_BOTTOM_WIDTH / 2.0
BOTTOM_REAR_Z = FORMER_BOTTOM_WIDTH / 2.0
BOTTOM_WIDTH = BOTTOM_REAR_Z - BOTTOM_FRONT_Z
BOTTOM_CENTER_Z = (BOTTOM_FRONT_Z + BOTTOM_REAR_Z) / 2.0
BOTTOM_THICKNESS = 0.5 * MM_PER_IN  # 12.7
TOP_LENGTH = 17.5 * MM_PER_IN  # 444.5 (0.25 in reveal per side)
FORMER_TOP_WIDTH = 10.5 * MM_PER_IN  # 266.7
TOP_FRONT_Z = -FORMER_TOP_WIDTH / 2.0
TOP_REAR_Z = FORMER_TOP_WIDTH / 2.0
TOP_WIDTH = TOP_REAR_Z - TOP_FRONT_Z
TOP_CENTER_Z = (TOP_FRONT_Z + TOP_REAR_Z) / 2.0
TOP_THICKNESS = 1.5 * MM_PER_IN  # 38.1
STACK_HEIGHT = BOTTOM_THICKNESS + TOP_THICKNESS  # 50.8: the deck (pad top)
LIP_W = 7.0  # raised rim width, in from the pad outline (2026-09 photo re-derive)
LIP_H = 2.5  # raised rim height above the deck
RIM_TOP = STACK_HEIGHT + LIP_H  # 53.3: the casting's overall height
REVEAL = (BOTTOM_LENGTH - TOP_LENGTH) / 2.0  # 6.35 per side, both axes

if abs(BOTTOM_CENTER_Z) > 1e-12 or abs(TOP_CENTER_Z) > 1e-12:
    raise AssertionError("base plates are not centred")
if abs((BOTTOM_WIDTH - TOP_WIDTH) / 2.0 - REVEAL) > 1e-12:
    raise AssertionError("pad reveal differs between the two plan axes")

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. ``build_harmonic_base`` marks exactly these; ``draw_harmonic_base``
# keeps exactly their union.  The plan carries both plates' footprints (the
# flange envelope + the pad outline); the front elevation carries the two
# plate thicknesses -- the extrude depths, renamed in the build from their
# auto ``D1`` so the two features cannot collide in the drawing's keep map. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BottomProfile": {"BottomLen", "BottomWid"},
    "TopProfile": {"TopLen", "TopWid"},
    "BottomPlate": {"FlangeT"},
    "TopPlate": {"PadT"},
}

# Notes: at most four lines of part-specific process fact (drawing-simplicity-
# policy.md rule 6).  Every plate size, height, reveal, rim width, corner
# radius and hole station rides the views; what stays here is process: how
# the deck is made, the all-round rim chamfer and root fillet that a 1:4
# elevation cannot carry, which side each hole opens from, and the masking.
DRAWING_NOTES = "\n".join(
    (
        "MACHINED FROM SOLID, NO DRAFT; ALL FACES MACHINED. PAD AND RIM CENTRED ON THE FLANGE.",
        "DECK IS POCKET MILLED INSIDE THE RIM, BLACK ENAMEL; RIM FLUSH WITH PAD. MASK UNDERSIDE + HOLES.",
        "RIMS 1/16 X 45 DEG; PAD ROOT R0.50; PLAN CORNERS CONCENTRIC. E1-E4 C'BORED FROM UNDERSIDE.",
        "STAMP SERIAL \"2\" 3.50 HIGH X 0.30 DEEP ON BRIGHT RIM TOP BESIDE NAMEPLATE; OTHERS BLIND TAPPED.",
    )
)
SIDE_VIEW_NOTE = "FRONT VIEW 1:4"
