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
BOTTOM_THICKNESS = 0.5 * MM_PER_IN  # 12.7
TOP_LENGTH = 17.5 * MM_PER_IN  # 444.5 (0.25 in reveal per side)
TOP_THICKNESS = 1.5 * MM_PER_IN  # 38.1
# The pad DEPTH is set by the column stations, not by the ch6 28 cm callout.
# The sockets sit at x = +/-197 and z = +/-112, so a pad centred on the part
# origin leaves an EQUAL socket-to-rim deck land on all four sides only at
# TOP_WIDTH = TOP_LENGTH - 2 * (197 - 112) = 274.5. The former 10.5 in pad
# (266.7) left 1.6 mm of land in Z against 5.5 in X, and the 2026-09 blind
# machinist review rejected that asymmetry as a blocker: no tolerance stack
# behind the hole-table coordinate scheme can hold the 1.0 MIN finished land
# DRAWING_NOTES demands off a 1.6 mm nominal. build_harmonic_base asserts the
# land is equal on both axes -- it owns COLUMN_X and the socket stations, so
# deriving TOP_WIDTH from them here would be circular.
TOP_WIDTH = 274.5
# The flange keeps the same 0.25 in reveal per side that it has in X.
BOTTOM_WIDTH = TOP_WIDTH + (BOTTOM_LENGTH - TOP_LENGTH)  # 287.2
BOTTOM_FRONT_Z = -BOTTOM_WIDTH / 2.0
BOTTOM_REAR_Z = BOTTOM_WIDTH / 2.0
BOTTOM_CENTER_Z = (BOTTOM_FRONT_Z + BOTTOM_REAR_Z) / 2.0
TOP_FRONT_Z = -TOP_WIDTH / 2.0
TOP_REAR_Z = TOP_WIDTH / 2.0
TOP_CENTER_Z = (TOP_FRONT_Z + TOP_REAR_Z) / 2.0
STACK_HEIGHT = BOTTOM_THICKNESS + TOP_THICKNESS  # 50.8: the deck (pad top)
LIP_W = 7.0  # raised rim width, in from the pad outline (2026-09 photo re-derive)
LIP_H = 2.5  # raised rim height above the deck
RIM_TOP = STACK_HEIGHT + LIP_H  # 53.3: the casting's overall height

if abs(BOTTOM_CENTER_Z) > 1e-12 or abs(TOP_CENTER_Z) > 1e-12:
    raise AssertionError("base plates are not centred")

# The deck is black in the source photographs. Machining and black coating of
# the full underside is the user's reconstruction choice, not photo evidence.
# The registry Finish field owns the paint and its masking, so each roughness
# symbol carries the grade alone; there are no locally masked feet.
#
# The flange perimeter carries the same seat grade because it is the drawing's
# hole-table origin: every mounting coordinate is measured from the virtual
# sharp corner of two of these faces, so they LOCATE the part (simplicity
# policy rule 5) and cannot be left as-cast under the title block's
# CAST/MACHINED surface row. All four sides are required equally -- the corner
# arcs between them are skimmed with the sides -- and the flange keeps the
# RAL6000 body colour (only the deck and underside are blacked by the Finish
# field). The part authors one native symbol per qualified face; the sheet
# states the requirement once, as this target on the plan profile. The target
# NAMES the surface, so the one sheet symbol cannot be misread as the pad side
# face or the rim (2026-09 review clarity item: three nested plan outlines sit
# within a few millimetres of each other).
FLANGE_PERIMETER_TARGET = "FLANGE EDGES, 4 SIDES"
SURFACE_FINISHES = (
    SurfaceFinishControl("deck", SEAT_UM, PlanarFace((0, 1, 0), STACK_HEIGHT)),
    SurfaceFinishControl("underside", SEAT_UM, PlanarFace((0, -1, 0), 0.0)),
    SurfaceFinishControl(
        "flange_west", SEAT_UM, PlanarFace((-1, 0, 0), BOTTOM_LENGTH / 2.0),
        production_method=FLANGE_PERIMETER_TARGET,
    ),
    SurfaceFinishControl(
        "flange_east", SEAT_UM, PlanarFace((1, 0, 0), BOTTOM_LENGTH / 2.0),
        production_method=FLANGE_PERIMETER_TARGET,
    ),
    SurfaceFinishControl(
        "flange_rear", SEAT_UM, PlanarFace((0, 0, 1), BOTTOM_WIDTH / 2.0),
        production_method=FLANGE_PERIMETER_TARGET,
    ),
    SurfaceFinishControl(
        "flange_front", SEAT_UM, PlanarFace((0, 0, -1), BOTTOM_WIDTH / 2.0),
        production_method=FLANGE_PERIMETER_TARGET,
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
    "BaseSpotFaceRearProfile": {"SpotFaceDia"},
}

# Keep this block to short, part-specific facts that are not already legible
# in a native dimension, hole table, or feature callout.  Finish and masking
# live in the registry's Finish field.
# Finished-part acceptance couples the otherwise independent dimensional
# limits. This does not change nominal CAD geometry or the assigned-tube fit.
# The requirement only: inspection, coordination and "limits still apply" are
# what a MIN callout plus the title block already mean.
DRAWING_NOTES = (
    "A1-A4: 1.0 MIN CONTINUOUS FINISHED DECK LAND\n"
    "BETWEEN EACH BORE AND RIM INNER FACE\n"
    "AFTER MATCHING AND EDGE BREAK."
)


# Base/frame parts carry no datums or feature-control frames under the drawing
# simplicity policy.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {}
