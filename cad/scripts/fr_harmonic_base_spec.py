r"""Dimensional contract shared by the harmonic base and its drawing.

PURE DATA, no SolidWorks/COM imports (see ``dt_crank_arm_spec`` for the reference
split). ``build_fr_harmonic_base`` imports the plate nominal geometry + the
marked-dimension NAME map from here; ``draw_fr_harmonic_base`` imports the same
geometry for its view math and keeps exactly ``DRAWING_DIMENSIONS`` across its
per-view ``keep`` maps, so the part-side marks and the drawing-side keeps cannot
silently drift.
"""

from __future__ import annotations

import _config
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm
from _surface_finish import SEAT_UM, SurfaceFinishControl
from _cone_axis_constants import FRAME_FRONT_COLUMN_Z, FRAME_REAR_COLUMN_Z
from frame_column_stations import COLUMN_SOCKET_DIAMETER, COLUMN_X

# The sheet prints decimal inch (issue #290, ``drawing_unit: in``).
UNIT = drawing_unit("parts/fr-harmonic-base", _config.parts("fr-harmonic-base"))

MM_PER_IN = 25.4

# --- Two-level base envelope, centred on the part origin. ---
BOTTOM_LENGTH = 18.0 * MM_PER_IN  # 457.2 (46 cm callout)
BOTTOM_THICKNESS = 0.5 * MM_PER_IN  # 12.7
TOP_LENGTH = 17.5 * MM_PER_IN  # 444.5 (0.25 in reveal per side)
TOP_THICKNESS = 1.5 * MM_PER_IN  # 38.1
# The sockets sit at x = +/-COLUMN_X and z = +/-COLUMN_Z (7.756 / 4.410 once the
# frame column snap lands; 7.7559 / 4.4094 until then), so a pad centred on
# the part origin leaves an EQUAL socket-to-pad-edge land on all four sides at
# TOP_WIDTH = TOP_LENGTH - 2 * (COLUMN_X - COLUMN_Z) = 10.808; the pad takes
# the nearest .01 width, 10.81, so the lands differ by .001 (.0015 before the
# snap). The former 10.5 in pad left 1.6 mm of land in Z against 5.5 in X, and
# the 2026-09 blind machinist review rejected that asymmetry as a blocker: no
# tolerance stack behind the hole-table coordinate scheme can hold the minimum
# finished land off a 1.6 mm nominal. build_fr_harmonic_base asserts the lands
# equal to within half a .01 step and proves each axis's worst case.
TOP_WIDTH = 274.574  # 10.81
# The flange keeps the same 0.25 in reveal per side that it has in X.
BOTTOM_WIDTH = TOP_WIDTH + (BOTTOM_LENGTH - TOP_LENGTH)  # 11.31
BOTTOM_FRONT_Z = -BOTTOM_WIDTH / 2.0
BOTTOM_REAR_Z = BOTTOM_WIDTH / 2.0
BOTTOM_CENTER_Z = (BOTTOM_FRONT_Z + BOTTOM_REAR_Z) / 2.0
TOP_FRONT_Z = -TOP_WIDTH / 2.0
TOP_REAR_Z = TOP_WIDTH / 2.0
TOP_CENTER_Z = (TOP_FRONT_Z + TOP_REAR_Z) / 2.0
STACK_HEIGHT = BOTTOM_THICKNESS + TOP_THICKNESS  # 50.8: the deck top, overall height
# Black machined deck + green land (user ruling 2026-10-09, ch30 p002/p003/p006
# and ch26 p.71 photos): the green raised rim is gone. The black panel is a
# raised machined pad DECK_RISE proud of the green casting top, centred on the
# pad; everything on the pad top outside it is the green land at GREEN_TOP.
# The deck top stays at STACK_HEIGHT, so nothing seated on the deck moves.
DECK_RISE = 3.048  # .12
GREEN_TOP = STACK_HEIGHT - DECK_RISE  # 1.88: green land, socket mouths
DECK_LENGTH = 334.264  # 13.16 (the nameplate's west edge is .16 inside)
DECK_LAND = 7.112  # .28 green land in front of and behind the deck (z)
DECK_WIDTH = TOP_WIDTH - 2.0 * DECK_LAND  # 10.25
DECK_HALF_X = DECK_LENGTH / 2.0
DECK_HALF_Z = DECK_WIDTH / 2.0
# Plan corners 1/4 in, the casting's rounded-corner language (the photographed
# black panel reads round-cornered); the top edge takes a .03 x 45 break,
# half the plates' .06 rim break, so most of the .12 step stays square.
DECK_CORNER_R = 0.25 * MM_PER_IN  # 6.35
DECK_EDGE_BREAK = 0.762  # .03 legs

# Underside lightening (same ruling): one cored pocket from the underside
# inside a POCKET_WALL perimeter wall, its ceiling POCKET_SKIN under the deck
# top (so GREEN_SKIN under the green ends), crossed by two ribs that stop
# RIB_RELIEF above the underside. All 18 deck seats are through-tapped through
# the retained skin and exit into pocket air; no deck-seat islands remain.
# Each column socket retains its full-height boss merged into the walls.
POCKET_WALL = 11.938  # .47
POCKET_HALF_X = TOP_LENGTH / 2.0 - POCKET_WALL
POCKET_HALF_Z = TOP_WIDTH / 2.0 - POCKET_WALL
# Owner-selected through-tap section: the pocket ceiling sits POCKET_SKIN
# under the deck, so every through seat keeps 1.5D of full form at the
# printed limits without changing hardware or tolerances.
POCKET_SKIN = 12.954  # .51
POCKET_CEILING_Y = STACK_HEIGHT - POCKET_SKIN  # 1.49: also the pocket depth
GREEN_SKIN = GREEN_TOP - POCKET_CEILING_Y  # .39
RIB_THICKNESS = 9.906  # .39
# Whole-rib relocation, not local seat notches: the cross rib spans
# X=.240 to .630, still joins both end walls and the long rib at Z=0. Its native
# CrossRibX dimension (9.24) locates the west face from the common table origin.
CROSS_RIB_CENTER_X = 11.049  # .435
RIB_RELIEF = 3.048  # .12 rib bottoms clear the bench by this much
SOCKET_BOSS_DIA = 41.402  # 1.63
CROSS_TAP_LUG_BOTTOM_Y = 26.416  # 1.04
CROSS_TAP_LUG_WIDTH = 27.0
# The lugs' inner faces are fabricated stations on the .01 grid (Lug1X/Lug3X
# 1.56 / 16.44 and Lug1Y/Lug0Y 2.70 / 8.61 print them), independent of the
# column line: inner X .316 inside the snapped column line, and the unprinted
# length runs from the inner Z face to the column line.
CROSS_TAP_LUG_INNER_X = 188.976  # 7.44
CROSS_TAP_LUG_INNER_Z = 75.057  # 2.955
CROSS_TAP_LUG_LENGTH = abs(FRAME_FRONT_COLUMN_Z) - CROSS_TAP_LUG_INNER_Z
# ONE radius for every vertical reentrant pocket corner: the socket-boss
# junctions (PocketFillets) and the rib/lug corners (PocketCornerFillets)
# print as one "R.23 MAX". Smaller radii, down to sharp, are permissible;
# through-seat engagement therefore never relies on fillet-added metal.
POCKET_CORNER_FILLET_R = 5.842  # .23
# swTolMAX prints the nominal then "MAX", so the model sits at the max: any
# smaller fillet, down to sharp, keeps every wall the proof checked.
POCKET_FILLET_TOL_TYPE = 6  # swTolType_e.swTolMAX

if abs(BOTTOM_CENTER_Z) > 1e-12 or abs(TOP_CENTER_Z) > 1e-12:
    raise AssertionError("base plates are not centred")

# The deck is black in the source photographs. "deck" is the raised deck top
# alone; the green land around it is as-cast. "underside" is the perimeter
# foot the casting stands on (the socket bosses merge into it); the pocket and
# retained ribs and lugs inside it stay as-cast. Machining and black coating
# of the foot is the user's reconstruction choice, not photo evidence.
# The registry Finish field owns the paint and its masking, so each roughness
# symbol carries the grade alone; there are no locally masked feet.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "deck", SEAT_UM, PlanarFace((0, 1, 0), STACK_HEIGHT), display_unit=UNIT
    ),
    SurfaceFinishControl(
        "underside", SEAT_UM, PlanarFace((0, -1, 0), 0.0), display_unit=UNIT
    ),
)

# --- Column sockets: the frame interface this casting owns -----------------
# drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates): the four sockets LOCATE the frame on the base --
# each column tube is matched to its own bore for a close hand-slip fit, and
# the deck's Ra 125 uin stops at the deck plane -- so every bore is a seat that
# MUST be cut on a casting the title block otherwise leaves as CAST/MACHINED.
# These controls belong to the part SPEC rather than to the build recipe: a
# sheet may only take a surface-finish control from a ``*_spec`` module, so a
# symbol sourced from the build script had no part-owned provenance. The
# stations come from the leaf module frame_column_stations, not from
# fr_frame_attachment_spec, which derives its heights from STACK_HEIGHT.
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
        display_unit=UNIT,
    )
    for x, z in COLUMN_SOCKET_XZ
)
PART_SURFACE_FINISHES = (*SURFACE_FINISHES, *SOCKET_BORE_FINISHES)

# Only retained ribs and cross-tap lugs need underside location marks.
# Their ends merge into walls/socket bosses; the hidden overlapping extents
# remain model geometry, not redundant drawing dimensions.
UNDERSIDE_LOCATION_DIMENSIONS: dict[str, tuple[str, ...]] = {
    "CrossTapLugProfile": ("Lug1X", "Lug3X", "Lug1Y", "Lug0Y"),
    "LongRibProfile": ("LongRibY",),
    "CrossRibProfile": ("CrossRibX",),
}
UNDERSIDE_LOCATION_PREFIXES: dict[tuple[str, str], str] = {
    (feature, name): "2X "
    for feature, names in (
        # Each lug station is shared by its opposite-side partner.
        ("CrossTapLugProfile", ("Lug1X", "Lug3X", "Lug1Y", "Lug0Y")),
    )
    for name in names
}
# The pivot is located from the nearer transferred MHA-DT-02 seat, not the
# table origin. The model's point-only PivotSeatReference sketch owns the offsets.
PIVOT_SEAT_DIMENSIONS = ("PivotSeatX", "PivotSeatY")


def pivot_seat_step(tag: str) -> str:
    """Identify the physical pivot using its current native hole-table tag."""
    return (
        f"1. {tag} IS LOCATED TO THE MHA-DT-02 SEAT;\n"
        "DRILL AND TAP AT ASSEMBLY.\n"
        f"{tag} TABLE X/Y ARE REFERENCE."
    )

# Both heights are baselines from the same faced underside, never a chain
# through the flange thickness and deck rise (#1321). Both print the
# title block's .XX band.
HEIGHT_REFERENCE_DIMENSIONS = ("GreenTopHeight", "CrossScrewAxisHeight")
HEIGHT_REFERENCE_CALLOUTS = {
    "GreenTopHeight": "GREEN LAND\nFROM UNDERSIDE",
    "CrossScrewAxisHeight": "CROSS-SCREW AXIS\nFROM FLANGE\nUNDERSIDE",
}
CROSS_SCREW_TOP_LAND_MIN_MM = WALL_TARGET_MM


def cross_screw_top_land_worst_case_mm(
    axis_height_mm: float, spotface_diameter_mm: float, linear_band_mm: float
) -> float:
    """Green-land ligament above a spotface at the printed limits.

    Both heights start on the faced underside. Neither the independent
    flange thickness nor the deck rise adds another height-stack term.
    """
    return (
        GREEN_TOP - linear_band_mm
        - (axis_height_mm + linear_band_mm)
        - (spotface_diameter_mm + linear_band_mm) / 2.0
    )



# Mark every dimension the drawing imports. drawing-simplicity-policy.md `How the repository implements the guidelines`: a printed nominal
# whose decimal places state a tolerance is a MODEL dimension, so the deck
# extent and rise, the underside-based green-land height, the edge breaks, the
# cross-screw axis height, the spotface size and depth and the underside
# pocket's wall, depth, ribs and cross-tap lugs are authored on the part and
# imported, not reconstructed in drawing notes. Only the hole table and the
# parenthesised reference heights stay sheet-side.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BottomProfile": {"BottomLen", "BottomWid"},
    "TopProfile": {"TopLen", "TopWid"},
    "BottomPlate": {"BottomThickness"},
    "PadCorners": {"PadCornerRadius"},
    "FlangeCorners": {"FlangeCornerRadius"},
    "DeckProfile": {"DeckLen", "DeckWid"},
    "Deck": {"DeckRise"},
    "DeckCorners": {"DeckCornerRadius"},
    "DeckEdgeBreak": {"DeckEdgeChamfer"},
    "HeightReference": set(HEIGHT_REFERENCE_DIMENSIONS),
    "CrossTapReference": {"CrossTapX", "CrossTapFarX"},
    "PlanReference": {"PadX", "PadY", "DeckX", "DeckY", "PocketX", "PocketY"},
    "PivotSeatReference": set(PIVOT_SEAT_DIMENSIONS),
    "TopRimBreaks": {"TopRimChamfer"},
    "BottomEdgeBreak": {"BottomEdgeChamfer"},
    "BaseSpotFaceRearProfile": {"SpotFaceDia"},
    "BaseSpotFaceRear": {"SpotFaceDepth"},
    "PocketProfile": {"PocketLen", "PocketWid"},
    "Pocket": {"PocketDepth"},
    "SocketBossProfile": {"SocketBossDia"},
    "LongRibProfile": {
        "LongRibThickness",
        *UNDERSIDE_LOCATION_DIMENSIONS["LongRibProfile"],
    },
    "CrossRibProfile": {
        "CrossRibThickness",
        *UNDERSIDE_LOCATION_DIMENSIONS["CrossRibProfile"],
    },
    "LongRib": {"RibRelief"},
    "CrossTapLugProfile": set(UNDERSIDE_LOCATION_DIMENSIONS["CrossTapLugProfile"]),
    "CrossTapLugs": {"LugBottom"},
    "PocketFillets": {"PocketFilletRadius"},
}

# Decimal places ARE the tolerance statement (drawing-simplicity-policy.md `How the repository implements the guidelines`), so the MODEL
# owns them: build_fr_harmonic_base applies this map to the .SLDPRT and
# draw_fr_harmonic_base only reads it back. Sizes, plain chamfers and the
# underside lug/rib/pocket stations print the title block's .XX; a dimension
# prints .XXX only where its nominal is a .001-grid frame column station (the
# cross-tap Xs), where a fit needs it (the spotface) or where another
# subsystem's band reads it (the pivot seat offsets). No fabricated dimension
# prints .X.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BottomProfile": {"BottomLen": 2, "BottomWid": 2},
    "TopProfile": {"TopLen": 2, "TopWid": 2},
    "BottomPlate": {"BottomThickness": 2},
    "PadCorners": {"PadCornerRadius": 2},
    "FlangeCorners": {"FlangeCornerRadius": 2},
    "DeckProfile": {"DeckLen": 2, "DeckWid": 2},
    "Deck": {"DeckRise": 2},
    "DeckCorners": {"DeckCornerRadius": 2},
    "DeckEdgeBreak": {"DeckEdgeChamfer": 2},
    "HeightReference": dict.fromkeys(HEIGHT_REFERENCE_DIMENSIONS, 2),
    "CrossTapReference": {"CrossTapX": 3, "CrossTapFarX": 3},
    "PlanReference": {
        "PadX": 2,
        "PadY": 2,
        "DeckX": 2,
        "DeckY": 2,
        "PocketX": 2,
        "PocketY": 2,
    },
    # Flow-through offsets from the MHA-DT-02 seats, with their own band.
    "PivotSeatReference": dict.fromkeys(PIVOT_SEAT_DIMENSIONS, 3),
    "TopRimBreaks": {"TopRimChamfer": 2},
    "BottomEdgeBreak": {"BottomEdgeChamfer": 2},
    "BaseSpotFaceRearProfile": {"SpotFaceDia": 3},
    "BaseSpotFaceRear": {"SpotFaceDepth": 3},
    "PocketProfile": {"PocketLen": 2, "PocketWid": 2},
    "Pocket": {"PocketDepth": 2},
    "SocketBossProfile": {"SocketBossDia": 2},
    "LongRibProfile": {
        "LongRibThickness": 2,
        **dict.fromkeys(UNDERSIDE_LOCATION_DIMENSIONS["LongRibProfile"], 2),
    },
    "CrossRibProfile": {
        "CrossRibThickness": 2,
        **dict.fromkeys(UNDERSIDE_LOCATION_DIMENSIONS["CrossRibProfile"], 2),
    },
    "LongRib": {"RibRelief": 2},
    "CrossTapLugProfile": dict.fromkeys(
        UNDERSIDE_LOCATION_DIMENSIONS["CrossTapLugProfile"], 2
    ),
    "CrossTapLugs": {"LugBottom": 2},
    "PocketFillets": {"PocketFilletRadius": 2},
}
# The native hole table prints its X/Y LOC cells .XXX: the flow-through
# stations other subsystems own are not on the .01 grid.
HOLE_TABLE_PRECISION = 3

# The overall 2.00 (GreenTopHeight + DeckRise) and the pocket skins are pure
# REFERENCE dimensions: read-only sums/differences of model-owned heights,
# parenthesised, with no tolerance or model dimension of their own.
# Their places are therefore
# not a tolerance statement -- but they are still specification, so the PART
# owns the digit and the sheet passes it through instead of writing a literal.
DRAWING_REFERENCE_PRECISION = 2

# A spotface only has to clean the cast face under a screw head: deeper is
# harmless, shallower leaves an unfaced ring the head would rock on, so the
# general band is wrong in one direction here. The model carries the band.
SPOTFACE_DEPTH_BAND_MM = (0.508, 0.0)  # +.020/0 (upper, lower), like _fit_deviations

# The MHA-FR-01 pivot seat is located from the MHA-DT-02 pedestal seats in one
# setup (Main ruling 2026-10-10), +- this band. cone_set_stack books the same
# value as its pivot-seat-position term, so the sheet prints what the stack
# assumes.
PIVOT_SEAT_POSITION_BAND_MM = 0.0508  # .002

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
if min(DRAWING_PRECISION_BY_NAME.values()) < 2:
    raise AssertionError("a fabricated base dimension prints .X")
# Every location and size prints .XX or .XXX, so the .XX band bounds each
# term of the import-time wall, land and engagement proofs.
LINEAR_BAND_MM = printed_band_mm(2, unit=UNIT)

# No Manufacturing Notes block. The one note it carried, a minimum finished
# land between each bore and the casting edge, put a dimension in a note; the
# land is now a design guarantee that build_fr_harmonic_base proves at import
# from every tolerance the sheet prints (hb-render-4 eye pass).


# Base/frame parts carry no datums or feature-control frames under the drawing
# simplicity policy.
GEOMETRIC_TOLERANCES_IN: dict[str, str] = {}
GEOMETRIC_TOLERANCES_MM = {k: float(v) * MM_PER_IN for k, v in GEOMETRIC_TOLERANCES_IN.items()}
