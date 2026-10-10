r"""Pure-data dimensional contract shared by the top-frame casting and drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_fr_top_frame`` imports the marked-
dimension NAME map, notes and the machined-surface geometry from here;
``draw_fr_top_frame`` keeps exactly ``DRAWING_DIMENSIONS`` and imports the rest of
the casting's plan geometry from ``build_fr_top_frame`` for its view math.

2026-08-02 rederive (ch30 px measurement anchored on the 394x224 column pitch
+ GT bundle rescale + ch19 closeups): the ring absorbed the old top-crossbar
(full-height integral bar) and the gooseneck-clamp (square-head set screw in
the east-rail hub, -X crank side), grew its rails to 34.2/38.0, gained webbed
faces, proud corner bosses, side-screw taps, hanger-stud holes and the
west-rail fulcrum-keeper taps.
"""

from __future__ import annotations

import _config
import vn_knife_hanger_stud_spec as HANGER_SCREW
import vn_knife_mount_dowel_spec as KNIFE_DOWEL
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from _gtol_spec import CylinderFace, PlanarFace
from _hole_spec import CLEARANCE_MM, HoleSpec
from _surface_finish import SEAT_UM, SurfaceFinishControl
from dt_cone_pivot_post_installation import FRAME_FRONT_COLUMN_Z, FRAME_REAR_COLUMN_Z
from fr_frame_attachment_spec import CAP_RECESS_DEPTH, COLUMN_SOCKET_DIAMETER
from ch_fulcrum_keeper_spec import (
    FOOT_TIP_X,
    FULCRUM_KEEPER_CENTRE_Z,
    KEEPER_FITUP_X_FROM_WEB_MM,
    KEEPER_SEAT_FLATNESS_BUDGET_MM,
    KEEPER_SEAT_LENGTH_MM as KEEPER_CONTACT_LENGTH_MM,
    KEEPER_WIDTH,
    KEEPER_Z_OFF,
    LUG_HALF_T,
)

# --- Machined-surface geometry ------------------------------------------------
#
# The stations and diameters the cut surfaces sit at. They live in the spec (not
# in ``build_fr_top_frame``) because a surface-finish symbol on the sheet has to be
# provenance-checked against the very face spec the casting authors -- see
# ``_drawing_contract``'s drawing-surface-finish-provenance rule. Everything
# else about the plan geometry stays in the build script.
COLUMN_X = 197.0  # column stations (fr-frame.SLDASM)
FRONT_COLUMN_Z = FRAME_FRONT_COLUMN_Z  # -112
REAR_COLUMN_Z = FRAME_REAR_COLUMN_Z  # +112
RING_HEIGHT = 36.5  # rail band (ch30 p002 36.7 / p006 37.0 / ch19 img03 35.6)
HALF_H = RING_HEIGHT / 2.0  # 18.25; band local y -18.25..+18.25
BOSS_ABOVE = 4.5  # boss proud of the rail top (corner-crop step)
BOSS_DIA = (
    45.0  # user ruling: all four upper/lower bosses clear the outward keeper feet
)
BORE_DIA = COLUMN_SOCKET_DIAMETER
CAP_RECESS_FLOOR_Y = HALF_H + BOSS_ABOVE - CAP_RECESS_DEPTH  # 6.45
GOOSENECK_X = -COLUMN_X  # east rail, -X crank side (summing's post station)
GOOSENECK_BORE_DIA = 17.0  # O16 post slides through

# Two faced regions on the existing top flange, not raised pads or pockets.
# Native split lines bound the NOMINAL contact plus its edge allowance;
# machining matches the actual keeper contacts in the single setup below.
# The 16.5 contact length includes the lug underside as well as the foot.
KEEPER_SEAT_EDGE_MARGIN_MM = 0.10
KEEPER_SEAT_WIDTH_MM = KEEPER_WIDTH + 2.0 * KEEPER_SEAT_EDGE_MARGIN_MM
KEEPER_SEAT_LENGTH_MM = KEEPER_CONTACT_LENGTH_MM + 2.0 * KEEPER_SEAT_EDGE_MARGIN_MM
KEEPER_SEAT_HEIGHT_MM = HALF_H - CAP_RECESS_FLOOR_Y
KEEPER_SEAT_CENTRES_XZ = tuple(
    (
        COLUMN_X + KEEPER_FITUP_X_FROM_WEB_MM,
        FULCRUM_KEEPER_CENTRE_Z
        + side * (KEEPER_Z_OFF + (FOOT_TIP_X - LUG_HALF_T) / 2.0),
    )
    for side in (-1.0, 1.0)
)
KEEPER_SEAT_BOUNDS_XZ = tuple(
    (
        x - KEEPER_SEAT_WIDTH_MM / 2.0,
        x + KEEPER_SEAT_WIDTH_MM / 2.0,
        z - KEEPER_SEAT_LENGTH_MM / 2.0,
        z + KEEPER_SEAT_LENGTH_MM / 2.0,
    )
    for x, z in KEEPER_SEAT_CENTRES_XZ
)


# --- Knife-hanger screw counterbores and dowel slip holes (crossbar) ---------
#
# Each MHA-SM-002 knife mount hangs under the integral crossbar on one stock
# #6-32 socket head cap screw (MHA-VN-024) dropped through a counterbore from
# the crossbar top; the screw clamps the block's top seat to the crossbar
# underside.  The two MHA-VN-051 dowels pressed in the block's top seat,
# HANGER_PIN_X either side of the screw axis along X, key the block against
# turning about the screw: the +X dowel slips into a round blind hole (the
# block's locator), the -X dowel into a blind slot of the same slip width
# whose length absorbs the pair's spacing mismatch (rule 12).
_X = float(str(_config.title_block("linear_1pl")["display"]).lstrip("\u00b1"))
_XX = float(str(_config.title_block("linear_2pl")["display"]).lstrip("\u00b1"))
_XXX = float(str(_config.title_block("linear_3pl")["display"]).lstrip("\u00b1"))
# The title block's DRILLED HOLES row: a drilled hole cuts up to this oversize.
DRILL_OVERSIZE = float(_config.title_block("drilled_hole")["plus_mm"])
HANGER_CLEARANCE_DIA = CLEARANCE_MM[("#6", "normal")]  # 4.318
HANGER_CBORE_DIA = 7.0  # .XX
HANGER_CBORE_DEPTH = 6.5  # .XX, from the crossbar top
HANGER_HOLE_SPEC = HoleSpec(
    "counterbore_socket",
    "#6",
    overrides_mm={
        "HoleDiameter": HANGER_CLEARANCE_DIA,
        "CounterBoreDiameter": HANGER_CBORE_DIA,
        "CounterBoreDepth": HANGER_CBORE_DEPTH,
    },
)
# The counterbore floor (the screw's bearing face) above the crossbar
# underside: the screw's grip.  The sheet dimensions it from the underside as
# a sheet-derived reference at one place, so the reach stack in
# ``build_sm_summing_assembly`` judges it at the .X band.
HANGER_GRIP = RING_HEIGHT - HANGER_CBORE_DEPTH  # 30.0
HANGER_GRIP_PLACES = 1
HANGER_GRIP_TOL = _X  # 0.8
# Print-worst checks (rule 12), the dt_cone_swing_platform hold-down's: the
# head clears the smallest counterbore and stays under the crossbar top, and
# bears beyond the largest drilled clearance hole.
HANGER_CBORE_HEAD_CLEARANCE = HANGER_CBORE_DIA - _XX - HANGER_SCREW.HEAD_DIA  # 0.75
HANGER_HEAD_RECESS = HANGER_CBORE_DEPTH - _XX - HANGER_SCREW.HEAD_H  # 2.48
HANGER_HEAD_BEARING = (
    HANGER_SCREW.HEAD_DIA - (HANGER_CLEARANCE_DIA + DRILL_OVERSIZE)
) / 2.0  # 0.66
for _label, _value in (
    ("head in counterbore", HANGER_CBORE_HEAD_CLEARANCE),
    ("head recess", HANGER_HEAD_RECESS),
    ("head bearing", HANGER_HEAD_BEARING),
):
    if _value <= 0.0:
        raise AssertionError(f"knife-hanger counterbore {_label}: {_value:.3f}")
# The dowel slip hole: a slip on the pin's catalogue diameter at 0.02..0.10
# diametral clearance (the dt_pinion_cam_spec slip band), reamed to an
# explicit +/-0.03 band and printed .XXX: 0.0274..0.0925.
HANGER_PIN_X = KNIFE_DOWEL.HANGER_OFFSET  # 6.350 either side of the screw axis
# The pair's stations from the screw axis in the dowel spec's order: the -X
# slot, then the +X round hole.
HANGER_PIN_XS = (-HANGER_PIN_X, HANGER_PIN_X)
HANGER_SLOT_X, HANGER_ROUND_X = HANGER_PIN_XS
HANGER_PIN_X_PLACES = KNIFE_DOWEL.HANGER_OFFSET_PLACES
HANGER_PIN_X_TOL = KNIFE_DOWEL.HANGER_OFFSET_TOL  # 0.13
HANGER_PIN_HOLE_DIA = 3.24
HANGER_PIN_HOLE_DIA_BAND = (0.03, -0.03)
HANGER_PIN_HOLE_DIA_PLACES = 3
HANGER_PIN_HOLE_DEPTH = KNIFE_DOWEL.SLIP_DEPTH  # 12.0, from the underside
HANGER_PIN_HOLE_DEPTH_PLACES = KNIFE_DOWEL.SLIP_DEPTH_PLACES
HANGER_PIN_SLIP_CLEARANCE_MIN = round(
    HANGER_PIN_HOLE_DIA + HANGER_PIN_HOLE_DIA_BAND[1] - KNIFE_DOWEL.DIA_MAX, 6
)
HANGER_PIN_SLIP_CLEARANCE_MAX = round(
    HANGER_PIN_HOLE_DIA + HANGER_PIN_HOLE_DIA_BAND[0] - KNIFE_DOWEL.DIA_MIN, 6
)
if HANGER_PIN_SLIP_CLEARANCE_MIN < 0.02 or HANGER_PIN_SLIP_CLEARANCE_MAX > 0.10:
    raise AssertionError(
        f"knife-mount dowel slip clearance {HANGER_PIN_SLIP_CLEARANCE_MIN}-"
        f"{HANGER_PIN_SLIP_CLEARANCE_MAX} is outside 0.02-0.10"
    )
# Manufacturing GD&T limits consumed by the part's drawing projection: each
# slot to the round hole beside it (datum B front, C rear) at the BASIC
# 12.700 between them, oriented by the other round hole with its location
# released (translation modifier), so the two mounts' dowel lines stay square
# to the B-C line.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {"knife-hanger slot position": "0.05"}
HANGER_SLOT_POSITION_TOL = float(GEOMETRIC_TOLERANCES_MM["knife-hanger slot position"])
# The slot's station from its round hole, BASIC (the frame's zone holds it),
# so the crossbar's .XXX round-hole station never opens the slot-to-hole
# spacing; from the screw axis it sits at the round hole's .XXX band plus
# the zone radius: 0.155.
HANGER_SLOT_FROM_ROUND = HANGER_ROUND_X - HANGER_SLOT_X  # 12.700, BASIC
HANGER_SLOT_FROM_ROUND_PLACES = 3
HANGER_SLOT_STATION_TOL = HANGER_PIN_X_TOL + HANGER_SLOT_POSITION_TOL / 2.0
# The -X dowel's blind slot: the round hole's reamed slip width (so the pin
# keeps the same 0.0274..0.0925 slip across it), held to the round hole
# beside it by the position frame above, and its length (along X, the dowel
# line) printed .XX.  The slot takes up the spacing mismatch: its zone
# radius (0.025), the knife mount's .XXX span (0.13) and the round-hole pin
# across its loosest slip (0.046), either way: 3.183 + 2 x 0.201 = 3.585
# under the 3.790 shortest.
HANGER_SLOT_WIDTH = HANGER_PIN_HOLE_DIA
HANGER_SLOT_WIDTH_BAND = HANGER_PIN_HOLE_DIA_BAND
HANGER_SLOT_WIDTH_PLACES = HANGER_PIN_HOLE_DIA_PLACES
HANGER_SLOT_LENGTH = 4.30
HANGER_SLOT_LENGTH_PLACES = 2
HANGER_SLOT_LENGTH_TOL = _XX  # 0.51
HANGER_SLOT_DEPTH = HANGER_PIN_HOLE_DEPTH
HANGER_SLOT_TRAVEL = (
    HANGER_SLOT_POSITION_TOL / 2.0
    + KNIFE_DOWEL.SPAN_TOL
    + HANGER_PIN_SLIP_CLEARANCE_MAX / 2.0
)  # 0.201
HANGER_SLOT_LENGTH_REQUIRED = KNIFE_DOWEL.DIA_MAX + 2.0 * HANGER_SLOT_TRAVEL  # 3.585
if HANGER_SLOT_LENGTH - HANGER_SLOT_LENGTH_TOL < HANGER_SLOT_LENGTH_REQUIRED:
    raise AssertionError(
        f"knife-hanger slot {HANGER_SLOT_LENGTH - HANGER_SLOT_LENGTH_TOL:.3f} long"
        f" at its shortest does not take the dowel's"
        f" {HANGER_SLOT_LENGTH_REQUIRED:.3f} travel"
    )
# The drilled #6 hole's float about the screw shank: (4.318 - 3.505) / 2.  The
# knife-hanger stack in ``build_sm_summing_assembly`` (which owns the knife
# mount's tap position term) proves the dowel stations' mismatch stays inside.
HANGER_SCREW_FLOAT = (HANGER_CLEARANCE_DIA - HANGER_SCREW.SHANK_DIA) / 2.0  # 0.41
# Suffixes on the model's own slip-hole and slot sizes and the depth they
# share (rules 6 and 7: count, process and purpose; the size and its band
# print natively): section F-F carries the round holes' size, the depth of
# all four (both holes and both slots floor at one height) and the slots'
# length; the underside locator the slots' width.
HANGER_PIN_HOLE_CALLOUT = "2X BLIND FLAT-BOTTOM REAM\nSLIP FIT MHA-VN-051"
HANGER_PIN_DEPTH_CALLOUT = "4X"
HANGER_SLOT_WIDTH_CALLOUT = "2X BLIND SLOT\nREAMED WIDTH\nSLIP FIT MHA-VN-051"
HANGER_SLOT_LENGTH_CALLOUT = "2X SLOT LENGTH"


# --- Machining-required surfaces ---------------------------------------------
#
# These nine faces own native finish controls. The two keeper-seat regions
# instead carry the bounded facing/common-zone instruction below: existing
# PlanarFace bounding-box selectors cannot distinguish those coplanar patches
# from the residual rail top. No finish is silently assigned to that whole face.
#
# * The four tube-socket bores take the MHA-FR-003 columns on a match-fitted close
#   hand-slip; a cast bore wall cannot hold that fit and would score the tube.
# * The four cap-recess floors are the axial seats the MHA-VN-028 caps land on --
#   they set the columns' shoulder height, so their roughness is a fit surface,
#   not cosmetic.
# * The gooseneck bore guides the O16 counter-spring post through the hub and
#   is pinched by the set screw against it.
#
# SEAT grade throughout: nothing runs on these surfaces continuously, so the
# commercial machine finish is what the fit needs. The part authors one native
# symbol per qualified face; each sheet states the requirement ONCE, and the
# target text names the family so a single symbol cannot be misread as one
# instance (harmonic-base FLANGE_PERIMETER_TARGET precedent).
SOCKET_BORE_TARGET = "TUBE SOCKET BORES, 4X"
CAP_SEAT_TARGET = "CAP SEAT FLOORS, 4X"
SURFACE_FINISHES = tuple(
    control
    for rail, x in (("east", GOOSENECK_X), ("west", COLUMN_X))
    for end, z in (("front", FRONT_COLUMN_Z), ("rear", REAR_COLUMN_Z))
    for control in (
        SurfaceFinishControl(
            f"socket_{rail}_{end}",
            SEAT_UM,
            CylinderFace(BORE_DIA, contains_x_mm=x, contains_z_mm=z),
            production_method=SOCKET_BORE_TARGET,
        ),
        SurfaceFinishControl(
            f"cap_seat_{rail}_{end}",
            SEAT_UM,
            PlanarFace(
                (0.0, 1.0, 0.0),
                CAP_RECESS_FLOOR_Y,
                contains_x_mm=x,
                contains_z_mm=z,
            ),
            production_method=CAP_SEAT_TARGET,
        ),
    )
) + (
    SurfaceFinishControl(
        "hub_bore",
        SEAT_UM,
        CylinderFace(GOOSENECK_BORE_DIA, contains_x_mm=GOOSENECK_X),
    ),
)


# --- Marked-dimension contract -------------------------------------------------
#
# The hole sizes remain associative callouts; named Hole Wizard placement
# dimensions expose the stations without duplicating those sizes.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "OuterProfile": {"Width", "Depth", "WinWidth", "WinDepth"},
    "WebProfile": {
        "WebOuterWidth",
        "WebOuterDepth",
        "WebInnerWidth",
        "WebInnerDepth",
    },
    "WebRing": {"RingHeight"},
    "BossUpProfile": {"C0Dia"},
    "BossesUpper": {"BossTopExtent"},
    "BossesLower": {"BossBottomExtent"},
    "BoreProfile": {"B0X", "B0Z", "B0Dia"},
    "SpotFaceRearProfile": {"S1Dia"},
    "BarProfile": {
        "BarAnchorX",
        "BarAnchorZ",
        "BarFootSpan",
        "GussetRunE",
        "BarSideE",
    },
    "HubBossProfile": {"HubDia"},
    "HubBoss": {"HubBossExtent"},
    "RibProfile": {"RibWidth"},
    "SetPocketProfile": {"PocketRun", "PocketRise"},
    "GooseneckTap": {"SetTapZ"},
    "GooseneckProfile": {"GnDia", "GnX", "GnZ"},
    # The hanger-counterbore and keeper-tap placement dims (StudFrontX ...,
    # KeeperFrontX ...) are NOT marked: a Hole Wizard placement sketch
    # measures from the origin -- mid-air on the print -- so sheet 3
    # dimensions those stations from the socket bore axes with sheet-derived
    # dimensions (DRAWING_REFERENCE_PRECISION below, policy rule 7).  The
    # dowel slip holes' and slots' stations from the screw axis and the slot
    # length are sheet-derived the same way; the round hole's size and depth
    # are the model's, printed on section F-F, and the slot's width the
    # model's, printed on the underside locator.
    "CapRecessProfile": {"CapRecessDia"},
    "CapRecesses": {"CapRecessDepth"},
    "HangerPinProfile": {"HangerPinHoleDia"},
    "HangerPinHoles": {"HangerPinHoleDepth"},
    "HangerSlotProfile": {"HangerSlotWidth"},
}


# --- Decimal places, authored ON THE PART -------------------------------------
#
# Policy rule 2: the places a dimension prints are part of the tolerance it
# claims, and the model owns both.  ``build_fr_top_frame`` applies this table
# natively (``_drawing_marks.apply_drawing_precision``) right after the drawing
# marks, so ``draw_fr_top_frame`` imports each dimension verbatim and only reads
# ``GetPrimaryPrecision2()`` back off the sheet.
#
# One place is this casting's routine band. Hanger positions are clearance
# features drilled under .X (+/-0.8). Keeper positions are model-nominal
# references only: the frame taps are transferred from the bench-pair-reamed,
# fit-up-located keeper feet, not independently located to the general band.
# More places appear only where a fit lives there -- the cap recess diameter
# and depth carry the bilateral bands above, the gooseneck bore prints the
# clearance a purchased post is set into, and the dowel slip hole and slot
# width are reamed to their own +/-0.03 band at three places.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "OuterProfile": {"Width": 1, "Depth": 1, "WinWidth": 1, "WinDepth": 1},
    "WebRing": {"RingHeight": 1},
    "BossUpProfile": {"C0Dia": 1},
    "BoreProfile": {"B0Dia": 1},
    "SpotFaceRearProfile": {"S1Dia": 1},
    "BarProfile": {"GussetRunE": 1},
    "HubBossProfile": {"HubDia": 1},
    "RibProfile": {"RibWidth": 1},
    "SetPocketProfile": {"PocketRise": 1},
    "GooseneckProfile": {"GnDia": 2},
    "CapRecessProfile": {"CapRecessDia": 2},
    "CapRecesses": {"CapRecessDepth": 2},
    "HangerPinProfile": {"HangerPinHoleDia": HANGER_PIN_HOLE_DIA_PLACES},
    "HangerPinHoles": {"HangerPinHoleDepth": HANGER_PIN_HOLE_DEPTH_PLACES},
    "HangerSlotProfile": {"HangerSlotWidth": HANGER_SLOT_WIDTH_PLACES},
}

# The drawing reads this flat view back off the sheet: a dimension name is
# unique across the features that expose one, and a marked dimension nobody
# authored places for would otherwise print SolidWorks' template default.
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: decimals
    for dimensions in DRAWING_PRECISION.values()
    for name, decimals in dimensions.items()
}
if len(DRAWING_PRECISION_BY_NAME) != sum(
    len(dimensions) for dimensions in DRAWING_PRECISION.values()
):
    raise AssertionError("two features share a drawing-precision dimension name")
for _feature, _dimensions in DRAWING_PRECISION.items():
    _unmarked = sorted(set(_dimensions) - DRAWING_DIMENSIONS.get(_feature, set()))
    if _unmarked:
        raise AssertionError(
            f"{_feature}: precision authored for unmarked dimensions {_unmarked}"
        )


# --- Decimal places for the dimensions the SHEET derives ----------------------
#
# Rule 2's one exception.  Some numbers on this print are distances between two
# model faces that no single model dimension expresses: a web thickness that is
# the difference of two profile offsets, a flange thickness between two extrude
# extents, a boss stack that sums three, a chamfer leg, a spotface-floor
# separation, a ramp angle.  Their VALUE is still the model's -- every one is
# measured in the view and the build fails if the geometry moved -- but there is
# no model dimension to carry the places, so the places live here, in the part's
# own contract, instead of as a literal in the drawing script.  Keyed by the
# recipe's own dimension label.
DRAWING_REFERENCE_PRECISION: dict[str, int] = {
    # Sheet 1, GEOMETRY: envelope, windows, T-rail section B-B and side
    # section E-E -- cast stock under the title block's general band.
    "overall casting width": 1,
    "overall casting depth": 1,
    "side flange width": 1,
    "left window clear width": 1,
    "right window clear width": 1,
    "central web width": 1,
    "rail web thickness": 1,
    "front rear flange width": 1,
    "top flange thickness": 1,
    "top rim chamfer": 1,
    "T rail root radius": 1,
    "side rail web thickness": 1,
    # Sheet 2, HOLES-SOCKETS: the socket pitches are the setup datums the
    # column plan is drilled from, and MHA-FR-001 states them to 0.01, so they
    # are the one pair of sheet-derived numbers that earns a second place.
    "socket horizontal pitch": 2,
    "socket vertical pitch": 2,
    # Hole stations baseline from socket axes (X from the left pair, Z from
    # the upper pair). Hangers are drilled under the general band; keeper
    # coordinates are reference-only guides to assembly-transferred taps.
    "hanger x from left sockets": 1,
    "front hanger z from upper sockets": 1,
    "rear hanger z from upper sockets": 1,
    "keeper x from left sockets": 1,
    "front keeper z from upper sockets": 1,
    "rear keeper z from upper sockets": 1,
    # Sheet 3, CROSS-TAPS: boss stack, cap-mouth chamfer, opposed spotface
    # floors and the tap axis below the boss top.
    "socket boss overall height": 1,
    "boss top above rail top": 1,
    "top bore mouth chamfer": 1,
    "opposed spotface floor separation": 1,
    "cross screw axis from boss top": 1,
    "spotface floor from socket axis": 1,
    # Sheet 4, HUB-SET-SCREW: hub station, set-tap axis, gusset ramp and the
    # cropped set-pocket section D-D.
    "hub from left front socket": 1,
    "set screw axis from rail top": 1,
    "hub boss underside drop": 1,
    "hub gusset feather span": 1,
    "hub gusset ramp angle": 1,
    "set-pocket depth from outer rail face": 1,
    # Sheet 6, UNDERSIDE: the junction lands and the knife-hanger section F-F
    # -- the counterbore floor (the screw's grip) above the crossbar underside,
    # the dowel slip hole's station from the screw axis, the slot's BASIC
    # station from the round hole, and the slot's length.
    "crossbar junction land": 1,
    "underside gusset thickness": 1,
    "hanger counterbore floor from underside": HANGER_GRIP_PLACES,
    "dowel hole from hanger axis": HANGER_PIN_X_PLACES,
    "dowel slot from dowel hole": HANGER_SLOT_FROM_ROUND_PLACES,
    "dowel slot length": HANGER_SLOT_LENGTH_PLACES,
    # Keeper facing: actual contacts set the region size; nominal split-line
    # footprints are reference only. Height uses the cap-seat precision.
    "keeper seat width": 1,
    "keeper seat length": 1,
    "keeper seat inner edge from socket": 1,
    "keeper seat end from socket": 1,
    "keeper seat height above cap floors": DRAWING_PRECISION["CapRecesses"][
        "CapRecessDepth"
    ],
}

# Use the canonical printed-band reader, not the unrounded inch grades.
PRINTED_LINEAR_BAND_MM = {places: printed_band_mm(places) for places in (1, 2, 3)}
PRINTED_DRILLED_HOLE_PLUS_MM = drilled_oversize_mm()
# Native Hole Wizard variables: diameters retain .XX, blind depths use .X.
KEEPER_TAP_CALLOUT_PRECISION = {
    "hw-tapdrldia": 2,
    "hw-tapdrldepth": 1,
    "hw-threaddepth": 1,
}
# Rule 12 receiver-wall stack: realistic angular drift through the FULL
# printed cylindrical pilot depth, without relying on a precision drill jig.
KEEPER_TAP_DRILL_WANDER_DEG = 0.3

# The nominal socket geometry stays fixed; the assigned actual tube governs fit.
DRAWING_NOTES = (
    "MATCH EACH SOCKET TO ITS ASSIGNED ACTUAL MHA-FR-003 TUBE.\n"
    "CLOSE HAND-SLIP; NO PERCEPTIBLE ROCK.\n"
    "RETAIN CORNER AND ORIENTATION MATCH MARKS."
)
DRAWING_NOTES_B = (
    "FACE BOTH KEEPER SEATS IN ONE SETUP.\n"
    f"BOTH SEATS WITHIN ONE COMMON {KEEPER_SEAT_FLATNESS_BUDGET_MM:.2f} FLATNESS ZONE.\n"
    f"SIZE TO ACTUAL KEEPER CONTACTS PLUS {KEEPER_SEAT_EDGE_MARGIN_MM:.2f} EACH EDGE.\n"
    "SPLIT-LINE FOOTPRINT DIMENSIONS ARE NOMINAL REFERENCES."
)
