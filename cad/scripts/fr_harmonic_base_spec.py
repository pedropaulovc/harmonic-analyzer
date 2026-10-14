r"""Dimensional contract shared by the harmonic base and its drawing.

PURE DATA, no SolidWorks/COM imports (see ``dt_crank_arm_spec`` for the reference
split). ``build_fr_harmonic_base`` imports the plate nominal geometry + the
marked-dimension NAME map from here; ``draw_fr_harmonic_base`` imports the same
geometry for its view math and keeps exactly ``DRAWING_DIMENSIONS`` across its
per-view ``keep`` maps, so the part-side marks and the drawing-side keeps cannot
silently drift.
"""

from __future__ import annotations

from _inch import inch
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _surface_finish import SEAT_UM, SurfaceFinishControl
from dt_cone_pivot_post_installation import FRAME_FRONT_COLUMN_Z, FRAME_REAR_COLUMN_Z
from frame_column_stations import COLUMN_SOCKET_DIAMETER, COLUMN_X

MM_PER_IN = 25.4

# --- Two-level base envelope, centred on the part origin. ---
BOTTOM_LENGTH = 18.0 * MM_PER_IN  # 457.2 (46 cm callout)
BOTTOM_THICKNESS = 0.5 * MM_PER_IN  # 12.7
TOP_LENGTH = 17.5 * MM_PER_IN  # 444.5 (0.25 in reveal per side)
TOP_THICKNESS = 1.5 * MM_PER_IN  # 38.1
# The pad DEPTH is set by the column stations, not by the ch6 28 cm callout.
# The sockets sit at x = +/-7-3/4 in and z = +/-4-7/16 in, so a pad centred on
# the part origin leaves an EQUAL socket-to-pad-edge land (1 in) on all four
# sides only at TOP_WIDTH = TOP_LENGTH - 2 * (7-3/4 - 4-7/16) = 10-7/8 in. The
# former 10.5 in pad left 1.6 mm of land in Z against 5.5 in X, and the 2026-09
# blind machinist review rejected that asymmetry as a blocker: no tolerance
# stack behind the hole-table coordinate scheme can hold a 1.0 MIN finished
# land off a 1.6 mm nominal. build_fr_harmonic_base asserts the land is equal
# on both axes and proves its worst case -- it owns COLUMN_X and the socket
# stations, so deriving TOP_WIDTH from them here would be circular.
TOP_WIDTH = 10.875 * MM_PER_IN  # 276.225 (was 274.5)
# The flange keeps the same 0.25 in reveal per side that it has in X.
BOTTOM_WIDTH = TOP_WIDTH + (BOTTOM_LENGTH - TOP_LENGTH)  # 287.2
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
DECK_RISE = MM_PER_IN / 8.0  # 3.175 (was 3.0)
GREEN_TOP = STACK_HEIGHT - DECK_RISE  # 47.625: green land, socket mouths
DECK_LENGTH = inch(105, 8)  # 13-1/8 = 333.375 (was 334.0): x -166.69..+166.69
# 5/16, not the nearer 1/4: it keeps the deck 10-1/4 wide (was 260.5), and at
# 1/4 the deck edge would fall exactly on the cross rib's and the lock pad's
# mid-wall ends (POCKET_WALL / 2), the inference trap of the 2026-10-10 leaf.
DECK_LAND = inch(5, 16)  # 7.9375 (was 7.0): green land in front of and behind the deck (z)
DECK_WIDTH = TOP_WIDTH - 2.0 * DECK_LAND  # 10-1/4 = 260.35: z -130.175..+130.175
DECK_HALF_X = DECK_LENGTH / 2.0
DECK_HALF_Z = DECK_WIDTH / 2.0
# Plan corners 1/4 in, the casting's rounded-corner language (the photographed
# black panel reads round-cornered); the top edge takes a 1/32 in x 45 break,
# half the plates' 1/16 in rim break, so 2.38 of the 3.18 step stays square.
DECK_CORNER_R = 0.25 * MM_PER_IN  # 6.35
DECK_EDGE_BREAK = MM_PER_IN / 32.0  # 0.79375 legs

# Underside lightening (same ruling): one cored pocket from the underside
# inside a POCKET_WALL perimeter wall, its ceiling POCKET_SKIN under the deck
# top (so GREEN_SKIN under the green ends), crossed by two ribs that stop
# RIB_RELIEF above the underside and hung with bosses under every blind deck
# seat. Each column socket stands in a full-height SOCKET_BOSS_DIA boss merged
# into the walls; the casting fillets round the pocket's reentrant edges.
POCKET_WALL = inch(1, 2)  # 12.7 (was 12.0)
POCKET_HALF_X = TOP_LENGTH / 2.0 - POCKET_WALL  # 209.55
POCKET_HALF_Z = TOP_WIDTH / 2.0 - POCKET_WALL  # 125.4125
# 7/16, not the nearer 1/2: at 1/2 the ceiling (38.1) lands exactly ON the
# cross-tap axis (BASE_SCREW_Y 38.1), so the ceiling-above-axis proof in
# build_fr_harmonic_base would hang on float rounding with zero margin.
POCKET_SKIN = inch(7, 16)  # 11.1125 (was 12.0)
POCKET_CEILING_Y = STACK_HEIGHT - POCKET_SKIN  # 39.6875: also the pocket depth
GREEN_SKIN = GREEN_TOP - POCKET_CEILING_Y  # 7.9375 (5/16)
RIB_THICKNESS = inch(3, 8)  # 9.525 (was 10.0)
RIB_RELIEF = inch(1, 8)  # 3.175 (was 3.0): rib bottoms clear the bench by this much
SOCKET_BOSS_DIA = inch(13, 8)  # 1-5/8 = 41.275 (was 41.5)
HANGING_BOSS_MIN_DIA = inch(5, 8)  # 15.875 (was 16.0): max(this, 2.5 x tap drill) per seat
# Hanging bosses and lugs end on one of two cast levels above the underside:
# each seat takes the higher level that still leaves its drill tip 1.5D of
# metal (build_fr_harmonic_base proves it), so the pattern carries two boss
# lengths instead of one per seat.
# The shallow level backs the raised pinion block's seat: its #8-32 x 1-1/2
# screw's drill tip at the shortest printed block needs 1.5D (6.25) of metal
# under it, which caps the level near 26.7 -- so 1 in, not the nearer 1-1/16.
# 7/16, not the nearer 1/2: at 1/2 the cone lock's drill tip keeps 9.32 of
# metal, under its 1.5D (9.53).
DEEP_BOSS_BOTTOM_Y = inch(7, 16)  # 11.1125 (was 12.0)
SHALLOW_BOSS_BOTTOM_Y = inch(1)  # 25.4 (was 26.5)
CASTING_FILLET_R = inch(1, 4)  # 6.35 (was 6.0)

if abs(BOTTOM_CENTER_Z) > 1e-12 or abs(TOP_CENTER_Z) > 1e-12:
    raise AssertionError("base plates are not centred")

# The deck is black in the source photographs. "deck" is the raised deck top
# alone; the green land around it is as-cast. "underside" is the perimeter
# foot the casting stands on (the socket bosses merge into it); the pocket and
# the hanging bosses inside it stay as-cast. Machining and black coating of
# the foot is the user's reconstruction choice, not photo evidence.
# The registry Finish field owns the paint and its masking, so each roughness
# symbol carries the grade alone; there are no locally masked feet.
#
# The flange perimeter carries the same seat grade because it is the drawing's
# hole-table origin: every mounting coordinate is measured from the virtual
# sharp corner of two of these faces, so they LOCATE the part (simplicity
# drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates)) and cannot be left as-cast under the title block's
# CAST/MACHINED surface row. All four sides are required equally -- the corner
# arcs between them are skimmed with the sides -- and the flange keeps the
# RAL6000 body colour (only the deck and underside are blacked by the Finish
# field). The part authors one native symbol per qualified face; the sheet
# states the requirement once, as this target on the plan profile. The target
# NAMES the surface, so the one sheet symbol cannot be misread as the pad side
# face or the deck (2026-09 review clarity item: three nested plan outlines
# share the plan view). "(TABLE ORIGIN)" states the
# function: the 2026-09-25 Codex machinist review read the edges as neither
# running nor locating and asked for the symbol's removal (Main: rebutted,
# and made legible on the sheet).
FLANGE_PERIMETER_TARGET = "FLANGE EDGES, 4 SIDES (TABLE ORIGIN)"
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
# drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates): the four sockets LOCATE the frame on the base --
# each column tube is matched to its own bore for a close hand-slip fit, and
# the deck's Ra 3.2 stops at the deck plane -- so every bore is a seat that
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
    )
    for x, z in COLUMN_SOCKET_XZ
)
PART_SURFACE_FINISHES = (*SURFACE_FINISHES, *SOCKET_BORE_FINISHES)

# The underside's rect pads, cross-tap lugs, ribs and MHA-DT-024 foot boss
# stand under seats the hole table does not locate (transfer seats, cross
# taps) or under none, so their sizes and their places from the table's X0 Y0
# are model dims too (Codex P2 on #1310; machinist review of the ribs and the
# foot boss). Each pair shares its size and one coordinate, so one pad of the
# pair carries the shared dim (UNDERSIDE_PAD_PREFIXES prints it 2X) and each
# pad its own other one. Not marked: what the casting cannot show -- the lock
# pad's and the lugs' outer ends and the lugs' widths run into the wall and
# the socket bosses, the block pads' east ends into the cross rib, and the
# ribs' ends into the wall (a rib's other coordinate is its centring, shown by
# its thickness about the pocket's centre line).
UNDERSIDE_PAD_DIMENSIONS: dict[str, tuple[str, ...]] = {
    "DeepBossProfile": (
        "LockPadWidth",
        "LockPadX",
        "LockPadY",
        "PedestalPad0Width",
        "PedestalPadLength",
        "PedestalPad1X",
        "PedestalPad0Y",
        "PedestalPad1Y",
        "FootBossX",
        "FootBossY",
    ),
    "ShallowBossProfile": ("BlockPad0Width", "BlockPad1X", "BlockPad0Y", "BlockPad1Y"),
    "CrossTapLugProfile": ("Lug1X", "Lug3X", "Lug1Y", "Lug0Y"),
    "LongRibProfile": ("LongRibY",),
    "CrossRibProfile": ("CrossRibX",),
}
UNDERSIDE_PAD_PREFIXES: dict[tuple[str, str], str] = {
    (feature, name): "2X "
    for feature, names in (
        ("DeepBossProfile", ("PedestalPad0Width", "PedestalPadLength", "PedestalPad1X")),
        ("ShallowBossProfile", ("BlockPad0Width", "BlockPad1X")),
        ("CrossTapLugProfile", ("Lug1X", "Lug3X", "Lug1Y", "Lug0Y")),
    )
    for name in names
}

# Mark every dimension the drawing imports. drawing-simplicity-policy.md `How the repository implements the guidelines`: a printed nominal
# whose decimal places state a tolerance is a MODEL dimension, so the deck
# extent and rise, the flange-to-deck height, the 45-degree edge breaks, the
# cross-screw axis height, the spotface size and depth and the underside
# pocket's wall, depth, ribs and bosses are authored on the part and imported
# -- not drawn on the sheet from picked geometry. Only the hole table and the
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
    "HeightReference": {"FlangeToDeck"},
    "CrossTapReference": {"CrossTapX", "CrossTapPitch"},
    "TopRimBreaks": {"TopRimChamfer"},
    "BottomEdgeBreak": {"BottomEdgeChamfer"},
    "BaseSpotFaceRearProfile": {"SpotFaceDia", "Spot0Y"},
    "BaseSpotFaceRear": {"SpotFaceDepth"},
    "PocketProfile": {"PocketLen", "PocketWid"},
    "Pocket": {"PocketDepth"},
    "SocketBossProfile": {"SocketBossDia"},
    "LongRibProfile": {
        "LongRibThickness",
        *UNDERSIDE_PAD_DIMENSIONS["LongRibProfile"],
    },
    "CrossRibProfile": {
        "CrossRibThickness",
        *UNDERSIDE_PAD_DIMENSIONS["CrossRibProfile"],
    },
    "LongRib": {"RibRelief"},
    "DeepBossProfile": {
        "HangingBossDia",
        *UNDERSIDE_PAD_DIMENSIONS["DeepBossProfile"],
    },
    # The shallow level's round-boss diameter, on the rear-west nameplate
    # tap's boss (sheet 3 calls the level out at each diameter).
    "ShallowBossProfile": {
        "ShallowBoss4Dia",
        *UNDERSIDE_PAD_DIMENSIONS["ShallowBossProfile"],
    },
    "CrossTapLugProfile": set(UNDERSIDE_PAD_DIMENSIONS["CrossTapLugProfile"]),
    "DeepBosses": {"DeepBossBottom"},
    "ShallowBosses": {"ShallowBossBottom"},
    "PocketFillets": {"PocketFilletRadius"},
}

# Decimal places ARE the tolerance statement (drawing-simplicity-policy.md `How the repository implements the guidelines`), so the MODEL
# owns them: build_fr_harmonic_base applies this map to the .SLDPRT and
# draw_fr_harmonic_base only reads it back. Everything on this casting is held to
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
    "DeckProfile": {"DeckLen": 1, "DeckWid": 1},
    "Deck": {"DeckRise": 1},
    "DeckCorners": {"DeckCornerRadius": 1},
    "DeckEdgeBreak": {"DeckEdgeChamfer": 1},
    "HeightReference": {"FlangeToDeck": 1},
    "CrossTapReference": {"CrossTapX": 1, "CrossTapPitch": 1},
    "TopRimBreaks": {"TopRimChamfer": 1},
    "BottomEdgeBreak": {"BottomEdgeChamfer": 1},
    "BaseSpotFaceRearProfile": {"SpotFaceDia": 1, "Spot0Y": 1},
    "BaseSpotFaceRear": {"SpotFaceDepth": 2},
    "PocketProfile": {"PocketLen": 1, "PocketWid": 1},
    "Pocket": {"PocketDepth": 1},
    "SocketBossProfile": {"SocketBossDia": 1},
    "LongRibProfile": {
        "LongRibThickness": 1,
        **dict.fromkeys(UNDERSIDE_PAD_DIMENSIONS["LongRibProfile"], 1),
    },
    "CrossRibProfile": {
        "CrossRibThickness": 1,
        **dict.fromkeys(UNDERSIDE_PAD_DIMENSIONS["CrossRibProfile"], 1),
    },
    "LongRib": {"RibRelief": 1},
    "DeepBossProfile": {
        "HangingBossDia": 1,
        **dict.fromkeys(UNDERSIDE_PAD_DIMENSIONS["DeepBossProfile"], 1),
    },
    "ShallowBossProfile": {
        "ShallowBoss4Dia": 1,
        **dict.fromkeys(UNDERSIDE_PAD_DIMENSIONS["ShallowBossProfile"], 1),
    },
    "CrossTapLugProfile": dict.fromkeys(
        UNDERSIDE_PAD_DIMENSIONS["CrossTapLugProfile"], 1
    ),
    "DeepBosses": {"DeepBossBottom": 1},
    "ShallowBosses": {"ShallowBossBottom": 1},
    "PocketFillets": {"PocketFilletRadius": 1},
}

# The overall 50.8 and the pocket skins are pure REFERENCE dimensions: each
# the read-only difference or sum of model-owned heights, parenthesised,
# carrying no tolerance of its own and having no model dimension to import.
# Their places are therefore
# not a tolerance statement -- but they are still specification, so the PART
# owns the digit and the sheet passes it through instead of writing a literal.
DRAWING_REFERENCE_PRECISION = 1

# A spotface only has to clean the cast face under a screw head: deeper is
# harmless, shallower leaves an unfaced ring the head would rock on, so the
# general .X band is wrong in one direction here. The model carries the band.
SPOTFACE_DEPTH_BAND_MM = (0.5, 0.0)  # (upper, lower) deviations, like _fit_deviations

# The MHA-FR-001 pivot seat is located from the MHA-DT-002 pedestal seats in one
# setup (Main ruling 2026-10-10), +- this band. cone_set_stack books the same
# value as its pivot-seat-position term, so the sheet prints what the stack
# assumes.
PIVOT_SEAT_POSITION_BAND_MM = 0.05

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

# No Manufacturing Notes block. The one note it carried, a 1.0 MIN finished
# land between each bore and the casting edge, put a dimension in a note; the
# land is now a design guarantee that build_fr_harmonic_base proves at import
# from every tolerance the sheet prints (hb-render-4 eye pass).


# Base/frame parts carry no datums or feature-control frames under the drawing
# simplicity policy.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {}
