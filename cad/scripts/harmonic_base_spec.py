r"""Dimensional contract shared by the harmonic base and its drawing.

PURE DATA, no SolidWorks/COM imports (see ``crank_arm_spec`` for the reference
split). ``build_harmonic_base`` imports the plate nominal geometry + the
marked-dimension NAME map from here; ``draw_harmonic_base`` imports the same
geometry for its view math and keeps exactly ``DRAWING_DIMENSIONS`` across its
per-view ``keep`` maps, so the part-side marks and the drawing-side keeps cannot
silently drift.
"""

from __future__ import annotations

from _gtol_spec import CylinderFace, PlanarFace
from _surface_finish import SEAT_UM, SurfaceFinishControl
from cone_pivot_post_installation import FRAME_FRONT_COLUMN_Z, FRAME_REAR_COLUMN_Z
from frame_column_stations import COLUMN_SOCKET_DIAMETER, COLUMN_X

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

# --- Column sockets: the frame interface this casting owns -----------------
# Simplicity-policy rule 5: the four sockets LOCATE the frame on the base --
# each column tube is matched to its own bore for a close hand-slip fit, and
# the deck's Ra 3.2 stops at the deck plane -- so every bore is a seat that
# MUST be cut on a casting the title block otherwise leaves as CAST/MACHINED.
# These controls belong to the part SPEC rather than to the build recipe: a
# sheet may only take a surface-finish control from a ``*_spec`` module, so a
# symbol sourced from the build script had no part-owned provenance. The
# stations come from the leaf module frame_column_stations, not from
# frame_attachment_spec, which derives its heights from STACK_HEIGHT.
COLUMN_SOCKET_XZ = tuple(
    (sx * COLUMN_X, z)
    for sx in (-1.0, 1.0)
    for z in (FRAME_FRONT_COLUMN_Z, FRAME_REAR_COLUMN_Z)
)


def socket_bore_finish_key(x_mm: float, z_mm: float) -> str:
    """Stable surface-finish key for the column socket at one station.

    Keys name the STATION, not the hole-table tag: SOLIDWORKS assigns A1-A4 by
    table order, so a tag-shaped key would silently point at another bore if
    the table ever reorders. The sheet keeps the tag language in its target.
    """
    return (
        f"socket_{'west' if x_mm < 0.0 else 'east'}"
        f"_{'front' if z_mm < 0.0 else 'rear'}"
    )


SOCKET_BORE_TARGET = "A1-A4 BORES"
SOCKET_BORE_FINISHES = tuple(
    SurfaceFinishControl(
        socket_bore_finish_key(x, z),
        SEAT_UM,
        CylinderFace(COLUMN_SOCKET_DIAMETER, contains_x_mm=x, contains_z_mm=z),
        production_method=SOCKET_BORE_TARGET,
    )
    for x, z in COLUMN_SOCKET_XZ
)
PART_SURFACE_FINISHES = (*SURFACE_FINISHES, *SOCKET_BORE_FINISHES)

# Mark every dimension the drawing imports. Policy rule 2: a printed nominal
# whose decimal places state a tolerance is a MODEL dimension, so the rim
# step, the rim width, the flange-to-rim height, both 45-degree edge breaks,
# the cross-screw axis height and the spotface size and depth are authored on
# the part and imported -- not drawn on the sheet from picked geometry. Only
# the hole table and the parenthesised overall height stay sheet-side.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BottomProfile": {"BottomLen", "BottomWid"},
    "TopProfile": {"TopLen", "TopWid"},
    "BottomPlate": {"BottomThickness"},
    "PadCorners": {"PadCornerRadius"},
    "FlangeCorners": {"FlangeCornerRadius"},
    "RimInnerCorners": {"RimInnerCornerRadius"},
    "Rim": {"RimHeight"},
    "RimWidthReference": {"RimWidth"},
    "HeightReference": {"FlangeToRim"},
    "TopRimBreaks": {"TopRimChamfer"},
    "BottomEdgeBreak": {"BottomEdgeChamfer"},
    "BaseSpotFaceRearProfile": {"SpotFaceDia", "Spot0Y"},
    "BaseSpotFaceRear": {"SpotFaceDepth"},
}

# Decimal places ARE the tolerance statement (policy rule 2), so the MODEL
# owns them: build_harmonic_base applies this map to the .SLDPRT and
# draw_harmonic_base only reads it back. Everything on this casting is held to
# the title block's general .X band, so every imported dimension prints ONE
# place; the drawing document's two-place default would silently ask the shop
# for .XX on a sand casting. The one exception is the spotface depth: it
# carries its OWN bilateral band (SPOTFACE_DEPTH_BAND_MM), so its places state
# no band and must print the modelled plane exactly -- 4.25, two places.
# Rounded to 4.3 the printed nominal would put the model's own plane outside
# the band the sheet prints; rounded to 4.2 it would misstate the model.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BottomProfile": {"BottomLen": 1, "BottomWid": 1},
    "TopProfile": {"TopLen": 1, "TopWid": 1},
    "BottomPlate": {"BottomThickness": 1},
    "PadCorners": {"PadCornerRadius": 1},
    "FlangeCorners": {"FlangeCornerRadius": 1},
    "RimInnerCorners": {"RimInnerCornerRadius": 1},
    "Rim": {"RimHeight": 1},
    "RimWidthReference": {"RimWidth": 1},
    "HeightReference": {"FlangeToRim": 1},
    "TopRimBreaks": {"TopRimChamfer": 1},
    "BottomEdgeBreak": {"BottomEdgeChamfer": 1},
    "BaseSpotFaceRearProfile": {"SpotFaceDia": 1, "Spot0Y": 1},
    "BaseSpotFaceRear": {"SpotFaceDepth": 2},
}

# The overall 53.3 is a pure REFERENCE dimension: the read-only sum of the
# three model-owned heights below it, parenthesised, carrying no tolerance of
# its own and having no model dimension to import. Its places are therefore
# not a tolerance statement -- but they are still specification, so the PART
# owns the digit and the sheet passes it through instead of writing a literal.
DRAWING_REFERENCE_PRECISION = 1

# A spotface only has to clean the cast face under a screw head: deeper is
# harmless, shallower leaves an unfaced ring the head would rock on, so the
# general .X band is wrong in one direction here. The model carries the band.
SPOTFACE_DEPTH_BAND_MM = (0.0, 0.5)  # (lower, upper) deviation

_PRECISION_NAMES = [
    (feature, name) for feature, names in DRAWING_PRECISION.items() for name in names
]
if any(
    name not in DRAWING_DIMENSIONS.get(feature, frozenset())
    for feature, name in _PRECISION_NAMES
):
    raise AssertionError("DRAWING_PRECISION names a dimension the part never marks")
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: DRAWING_PRECISION[feature][name] for feature, name in _PRECISION_NAMES
}
if len(DRAWING_PRECISION_BY_NAME) != len(_PRECISION_NAMES):
    raise AssertionError("DRAWING_PRECISION repeats a dimension name across features")

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
