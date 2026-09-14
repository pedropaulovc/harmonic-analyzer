r"""Dimensional contract shared by the harmonic base and its drawing.

PURE DATA, no SolidWorks/COM imports (see ``crank_arm_spec`` for the reference
split). ``build_harmonic_base`` imports the plate nominal geometry + the
marked-dimension NAME map from here; ``draw_harmonic_base`` imports the same
geometry for its view math and keeps exactly ``DRAWING_DIMENSIONS`` across its
per-view ``keep`` maps, so the part-side marks and the drawing-side keeps cannot
silently drift.
"""

from __future__ import annotations

from _gtol_spec import PlanarFace
from _surface_finish import SEAT_UM, SurfaceFinishControl

MM_PER_IN = 25.4

# --- Two-level base envelope, centred on the part origin. ---
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

if abs(BOTTOM_CENTER_Z) > 1e-12 or abs(TOP_CENTER_Z) > 1e-12:
    raise AssertionError("base plates are not centred")

# The deck is black in the source photographs. Machining and black coating of
# the full underside is the user's reconstruction choice, not photo evidence.
# These whole faces are cut before painting; there are no locally masked feet.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "deck", SEAT_UM, PlanarFace((0, 1, 0), STACK_HEIGHT),
        production_method="BEFORE PAINT",
    ),
    SurfaceFinishControl(
        "underside", SEAT_UM, PlanarFace((0, -1, 0), 0.0),
        production_method="BEFORE PAINT",
    ),
)

# Mark only dimensions imported by the drawing. Hole-table dimensions and the
# exact-edge rim, root, height and underside-chamfer controls remain native.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BottomProfile": {"BottomLen", "BottomWid"},
    "TopProfile": {"TopLen", "TopWid"},
    "BottomPlate": {"BottomThickness"},
    "PadCorners": {"PadCornerRadius"},
    "FlangeCorners": {"FlangeCornerRadius"},
    "RimInnerCorners": {"RimInnerCornerRadius"},
    "TopRimBreaks": {"TopRimChamfer"},
    "BaseSpotFaceRearProfile": {"SpotFaceDia"},
}

# Keep this block to short, part-specific facts that are not already legible
# in a native dimension, hole table, or feature callout.  Finish and masking
# live in the registry's Finish field.
DRAWING_NOTES = "STAMP SERIAL IDENTIFIER AT THE INDICATED ID LOCATION."


# Base/frame parts carry no datums or feature-control frames under the drawing
# simplicity policy.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {}
