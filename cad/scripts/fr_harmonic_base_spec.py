r"""Dimensional contract shared by the harmonic base and its drawing.

PURE DATA, no SolidWorks/COM imports (see ``dt_crank_arm_spec`` for the reference
split). ``build_fr_harmonic_base`` imports the plate nominal geometry + the
marked-dimension NAME map from here; ``draw_fr_harmonic_base`` imports the same
geometry for its view math and keeps exactly ``DRAWING_DIMENSIONS`` across its
per-view ``keep`` maps, so the part-side marks and the drawing-side keeps cannot
silently drift.
"""

from __future__ import annotations

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
# The sockets sit at x = +/-197 and z = +/-112, so a pad centred on the part
# origin leaves an EQUAL socket-to-pad-edge land on all four sides only at
# TOP_WIDTH = TOP_LENGTH - 2 * (197 - 112) = 274.5. The former 10.5 in pad
# (266.7) left 1.6 mm of land in Z against 5.5 in X, and the 2026-09 blind
# machinist review rejected that asymmetry as a blocker: no tolerance stack
# behind the hole-table coordinate scheme can hold a 1.0 MIN finished land
# off a 1.6 mm nominal. build_fr_harmonic_base asserts the land is equal on
# both axes and proves its worst case -- it owns COLUMN_X and the socket
# stations, so
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
STACK_HEIGHT = BOTTOM_THICKNESS + TOP_THICKNESS  # 50.8: the deck top, overall height
# Black machined deck + green land (user ruling 2026-10-09, ch30 p002/p003/p006
# and ch26 p.71 photos): the green raised rim is gone. The black panel is a
# raised machined pad DECK_RISE proud of the green casting top, centred on the
# pad; everything on the pad top outside it is the green land at GREEN_TOP.
# The deck top stays at STACK_HEIGHT, so nothing seated on the deck moves.
DECK_RISE = 3.0
GREEN_TOP = STACK_HEIGHT - DECK_RISE  # 47.8: green land, socket mouths
DECK_LENGTH = 334.0  # x -167.0..+167.0 (the nameplate's west edge is 4.0 inside)
DECK_LAND = 7.0  # green land in front of and behind the deck (z)
DECK_WIDTH = TOP_WIDTH - 2.0 * DECK_LAND  # 260.5: z -130.25..+130.25
DECK_HALF_X = DECK_LENGTH / 2.0
DECK_HALF_Z = DECK_WIDTH / 2.0
# Plan corners 1/4 in, the casting's rounded-corner language (the photographed
# black panel reads round-cornered); the top edge takes a 1/32 in x 45 break,
# half the plates' 1/16 in rim break, so 2.2 of the 3.0 step stays square.
DECK_CORNER_R = 0.25 * MM_PER_IN  # 6.35
DECK_EDGE_BREAK = MM_PER_IN / 32.0  # 0.79375 legs

# Underside lightening (same ruling): one cored pocket from the underside
# inside a POCKET_WALL perimeter wall, its ceiling POCKET_SKIN under the deck
# top (so GREEN_SKIN under the green ends), crossed by two ribs that stop
# RIB_RELIEF above the underside and hung with bosses under every blind deck
# seat. Each column socket stands in a full-height SOCKET_BOSS_DIA boss merged
# into the walls; the casting fillets round the pocket's reentrant edges.
POCKET_WALL = 12.0
POCKET_HALF_X = TOP_LENGTH / 2.0 - POCKET_WALL  # 210.25
POCKET_HALF_Z = TOP_WIDTH / 2.0 - POCKET_WALL  # 125.25
POCKET_SKIN = 12.0
POCKET_CEILING_Y = STACK_HEIGHT - POCKET_SKIN  # 38.8: also the pocket depth
GREEN_SKIN = GREEN_TOP - POCKET_CEILING_Y  # 9.0
RIB_THICKNESS = 10.0
RIB_RELIEF = 3.0  # rib bottoms clear the bench by this much
SOCKET_BOSS_DIA = 41.5
HANGING_BOSS_MIN_DIA = 16.0  # max(this, 2.5 x tap drill) per seat
# Hanging bosses and lugs end on one of two cast levels above the underside:
# each seat takes the higher level that still leaves its drill tip 1.5D of
# metal (build_fr_harmonic_base proves it), so the pattern carries two boss
# lengths instead of one per seat.
# The shallow level backs the raised pinion block's seat: its #8-32 x 1-1/2
# screw runs 13.38 deep at the shortest printed block, so the 16.8 drill's
# tip stands 32.96 up and needs 1.5D (6.25) under it: 26.71 at most.
DEEP_BOSS_BOTTOM_Y = 12.0
SHALLOW_BOSS_BOTTOM_Y = 26.5
# ONE radius for every vertical reentrant pocket corner: the socket-boss
# junctions (PocketFillets) and the rib, pad, lug and boss corners
# (PocketCornerFillets) print as one "R6.0 MAX" (machinist review rule 16).
# R6 is the largest standard value that keeps rule 17's 1.5 wall from every
# seat, socket and cross tap at the worst case
# (test_fr_harmonic_base_pocket_fillets_drawing).
POCKET_CORNER_FILLET_R = 6.0
# swTolMAX prints the nominal then "MAX", so the model sits at the max: any
# smaller fillet, down to sharp, keeps every wall the proof checked.
POCKET_FILLET_TOL_TYPE = 6  # swTolType_e.swTolMAX

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

# The underside's rect pads, cross-tap lugs, ribs, MHA-DT-24 foot boss and
# MHA-FR-04 nameplate bosses stand under seats the hole table does not
# locate (transfer seats, cross taps, nameplate taps) or under none, so their
# sizes and their places from the table's X0 Y0
# are model dims too (Codex P2 on #1310; machinist review of the ribs and the
# foot boss). Each pair shares its size and one coordinate, so one pad of the
# pair carries the shared dim (UNDERSIDE_PAD_PREFIXES prints it 2X) and each
# pad its own other one. Not marked: what the casting cannot show -- the lock
# pad's and the lugs' outer ends and the lugs' widths run into the wall and
# the socket bosses, the block pads' east ends into the cross rib, and the
# ribs' ends into the wall (a rib's other coordinate is its centring, shown by
# its thickness about the pocket's centre line).
#
# The four nameplate taps stand on a rectangle, so each boss X and each boss Y
# is shared by two bosses and prints 2X. build_fr_harmonic_base names boss
# ``k`` of fr_nameplate_spec.MOUNT_HOLE_XZ ``NameplateBoss{k}X``/``Y``: k 0
# east-rear, 1 east-front, 2 west-rear, 3 west-front (pinned by
# test_fr_harmonic_base_drawing). Sheet 4 hangs the X rows above the rear and
# the Y columns west of the view, so the X stations come off the two REAR
# bosses and the Y stations off the two WEST ones: no witness line crosses
# its twin boss.
NAMEPLATE_BOSS_LOCATION_DIMENSIONS = (
    "NameplateBoss2X",
    "NameplateBoss2Y",
    "NameplateBoss0X",
    "NameplateBoss3Y",
)
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
    "ShallowBossProfile": (
        "BlockPad0Width",
        "BlockPad1X",
        "BlockPad0Y",
        "BlockPad1Y",
        *NAMEPLATE_BOSS_LOCATION_DIMENSIONS,
    ),
    "CrossTapLugProfile": ("Lug1X", "Lug3X", "Lug1Y", "Lug0Y"),
    "LongRibProfile": ("LongRibY",),
    "CrossRibProfile": ("CrossRibX",),
}
UNDERSIDE_PAD_PREFIXES: dict[tuple[str, str], str] = {
    (feature, name): "2X "
    for feature, names in (
        ("DeepBossProfile", ("PedestalPad0Width", "PedestalPadLength", "PedestalPad1X")),
        (
            "ShallowBossProfile",
            ("BlockPad0Width", "BlockPad1X", *NAMEPLATE_BOSS_LOCATION_DIMENSIONS),
        ),
        ("CrossTapLugProfile", ("Lug1X", "Lug3X", "Lug1Y", "Lug0Y")),
    )
    for name in names
}
# D1 is located from the nearer transferred MHA-DT-002 seat, not the table
# origin. The model's point-only PivotSeatReference sketch owns these offsets.
PIVOT_SEAT_DIMENSIONS = ("PivotSeatX", "PivotSeatY")
PIVOT_SEAT_TAG = "D1"
PIVOT_SEAT_STEP = (
    f"{PIVOT_SEAT_TAG} PIVOT SEAT: DRILL AND TAP AT ASSEMBLY, AFTER\n"
    "THE MHA-DT-002 SEATS, IN ONE SETUP WITH THEM;\n"
    "OFFSETS SHOWN GOVERN; TABLE X/Y ARE REFERENCE."
)

# Both heights are baselines from the same faced underside, never a chain
# through the flange thickness and deck rise (#1321). Their ordinary .X
# title-block bands stay unchanged.
HEIGHT_REFERENCE_DIMENSIONS = ("GreenTopHeight", "CrossScrewAxisHeight")
HEIGHT_REFERENCE_CALLOUTS = {
    "GreenTopHeight": "GREEN LAND\nFROM UNDERSIDE",
    "CrossScrewAxisHeight": "CROSS-SCREW AXIS\nFROM FLANGE\nUNDERSIDE",
}
CROSS_SCREW_TOP_LAND_MIN_MM = 2.0


def cross_screw_top_land_worst_case_mm(
    axis_height_mm: float, spotface_diameter_mm: float, linear_band_mm: float
) -> float:
    """Green-land ligament above a spotface at the printed .X limits.

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
# the title block's general .X band, except the explicitly banded dimensions.
# The spotface depth prints the modelled plane exactly -- 4.25, two places;
# rounding it would misstate its limits. The pedestal-to-pivot offsets also
# retain the two-place nominal formerly printed in the setup note, with their
# own PIVOT_SEAT_POSITION_BAND_MM on each model dimension.
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
    "HeightReference": dict.fromkeys(HEIGHT_REFERENCE_DIMENSIONS, 1),
    "CrossTapReference": {"CrossTapX": 1, "CrossTapFarX": 1},
    # The plan stations from X0 Y0 print their modelled nominal: the 1/4 in
    # flange reveal makes 6.35, 13.35 and 18.35, which one place would misstate.
    "PlanReference": {
        "PadX": 2,
        "PadY": 2,
        "DeckX": 1,
        "DeckY": 2,
        "PocketX": 2,
        "PocketY": 2,
    },
    "PivotSeatReference": dict.fromkeys(PIVOT_SEAT_DIMENSIONS, 2),
    "TopRimBreaks": {"TopRimChamfer": 1},
    "BottomEdgeBreak": {"BottomEdgeChamfer": 1},
    "BaseSpotFaceRearProfile": {"SpotFaceDia": 1},
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

# The overall 50.8 (GreenTopHeight + DeckRise) and the pocket skins are pure
# REFERENCE dimensions: read-only sums/differences of model-owned heights,
# parenthesised, with no tolerance or model dimension of their own.
# Their places are therefore
# not a tolerance statement -- but they are still specification, so the PART
# owns the digit and the sheet passes it through instead of writing a literal.
DRAWING_REFERENCE_PRECISION = 1

# A spotface only has to clean the cast face under a screw head: deeper is
# harmless, shallower leaves an unfaced ring the head would rock on, so the
# general .X band is wrong in one direction here. The model carries the band.
SPOTFACE_DEPTH_BAND_MM = (0.5, 0.0)  # (upper, lower) deviations, like _fit_deviations

# The MHA-FR-01 pivot seat is located from the MHA-DT-02 pedestal seats in one
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
