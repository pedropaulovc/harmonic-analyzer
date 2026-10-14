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

from math import radians, sqrt, tan

import _config
import vn_knife_hanger_stud_spec as HANGER_SCREW
import vn_knife_hanger_washer_spec as HANGER_WASHER
import vn_knife_mount_dowel_spec as KNIFE_DOWEL
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _hole_spec import CLEARANCE_MM, THREAD_MAJOR_MM, HoleSpec
from _surface_finish import SEAT_UM, SurfaceFinishControl
from dt_cone_pivot_post_installation import (
    FRAME_FRONT_COLUMN_Z,
    FRAME_REAR_COLUMN_Z,
)
from fr_frame_attachment_spec import CAP_RECESS_DEPTH, COLUMN_SOCKET_DIAMETER
from ch_fulcrum_keeper_spec import KEEPER_SEAT_FLATNESS_BUDGET_MM

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
HANGER_CROSSBAR_WIDTH = 25.0
HANGER_CROSSBAR_WIDTH_PLACES = 1
FLANGE_THICKNESS_MM = 8.0  # final top flange, including the faced right rail top
FLANGE_THICKNESS_PLACES = 1
BOSS_ABOVE = 4.5  # boss proud of the rail top (corner-crop step)
BOSS_DIA = (
    45.0  # user ruling: all four upper/lower bosses clear the outward keeper feet
)
BORE_DIA = COLUMN_SOCKET_DIAMETER
CAP_RECESS_FLOOR_Y = HALF_H + BOSS_ABOVE - CAP_RECESS_DEPTH  # 6.45
GOOSENECK_X = -COLUMN_X  # east rail, -X crank side (summing's post station)
GOOSENECK_BORE_DIA = 17.0  # O16 post slides through

# --- Gooseneck set-screw boss (east-rail hub) ---------------------------------
#
# User ruling 2026-10-12 (option (a), no jam nut): the MHA-VN-023 square-head
# cup-point set screw that pinches the O16 post enters the hub through a cast
# boss on the hub pad's outer face -- square-sided and blended into the rail
# under the top flange, as the ch19 img04 hub shows it -- spot-faced square
# to the tap. The spot face starts the thread square on a machined face (the
# head stands proud of it: the cup point bites the post first); it prints .X
# from the bore axis the screw pinches across.
HUB_SET_SPOT_FROM_AXIS = 21.0  # .X
HUB_SET_SPOT_PLACES = 1
HUB_SET_BOSS_FROM_AXIS = 22.0  # cast face: 1.0 stock over the spot face
HUB_SET_SPOT_DIA = 10.0  # clears the 1/4 square head's 8.98 diagonal at its .X minimum
HUB_SET_BOSS_W = 18.0  # along the rail, centred on the tap (spot land: build)
SET_SCREW_THREAD = "1/4-20"
SET_SCREW_MAJOR_DIA = THREAD_MAJOR_MM[SET_SCREW_THREAD]  # 6.350
SET_SCREW_PITCH = 25.4 / 20.0
SET_SCREW_MIN_ENGAGEMENT_D = 1.5  # drawing-guidelines.md rule 18 (thread engagement): >= 1.5D of full thread


def _sag(radius: float) -> float:
    """A circle's sag across the set screw's major diameter."""
    return radius - sqrt(radius**2 - (SET_SCREW_MAJOR_DIA / 2.0) ** 2)


# --- Knife-hanger hex-bolt clearance holes and dowel slip holes (crossbar) ----
#
# Each MHA-SM-002 knife mount hangs under the integral crossbar on one
# cut-to-length #10-24 plain hex bolt (MHA-VN-024). Its SAE washer bears on
# the FACED top plane; the block's top seat bears on the FINISHED
# underside. The two MHA-VN-051 dowels retain their round-hole/slot scheme:
# +X locates in a round blind slip hole, -X in a blind slip-width slot.
# Slot travel absorbs the pair's spacing mismatch (drawing-guidelines.md
# rule 19 (absorb stacks at fit-up, not with tighter bands)).
_X = float(str(_config.title_block("linear_1pl")["display"]).lstrip("\u00b1"))
_XX = float(str(_config.title_block("linear_2pl")["display"]).lstrip("\u00b1"))
_XXX = float(str(_config.title_block("linear_3pl")["display"]).lstrip("\u00b1"))
# The title block's DRILLED HOLES row: a drilled hole cuts up to this oversize.
DRILL_OVERSIZE = float(_config.title_block("drilled_hole")["plus_mm"])
# ASME B18.2.8 Table 2: #10 loose, .238 in = 6.0452 mm, rounded to the
# repository's three-place clearance-table precision.
HANGER_CLEARANCE_DIA = CLEARANCE_MM[("#10", "loose")]  # 6.045
HANGER_CLEARANCE_DIA_PLACES = 3
# Explicit manufactured acceptance: never undersize the ANSI loose minimum.
HANGER_CLEARANCE_DIA_BAND = (0.13, 0.0)  # (upper, lower), not a supplier guarantee
HANGER_CLEARANCE_DIA_MIN = HANGER_CLEARANCE_DIA + min(HANGER_CLEARANCE_DIA_BAND)
HANGER_CLEARANCE_DIA_MAX = HANGER_CLEARANCE_DIA + max(HANGER_CLEARANCE_DIA_BAND)
# The finished top-to-underside grip controls the bolt reach. User ruling
# 2026-10-14: the whole top except the four corner bosses is faced on the
# plane the model already carries, so the grip is the crossbar's own
# full-height extrude, HangerGrip@Crossbar. It is driven by the "RingHeight"
# global, carries the +/-0.05 band, and the sheet imports it in section F-F.
HANGER_GRIP = RING_HEIGHT
HANGER_GRIP_PLACES = 2
HANGER_GRIP_TOL = 0.05
# The band sets the bolt's reach into the knife mount's tap
# (build_sm_summing_assembly HANGER_REACH_MIN/MAX), so the callout names it.
HANGER_GRIP_CALLOUT = (
    "FINISHED TOP AND\nUNDERSIDE SEATS;\nSETS MHA-VN-024\nTHREAD ENGAGEMENT"
)
# A plain native Hole Wizard clearance row, drilled through from the faced
# underside. A plain hole ignores HoleFit, so _holes.wizard_holes writes the
# pinned #10 loose 6.045 to both diameter knobs whenever the table seeds
# another size; the build reads the exact cut diameter back.
HANGER_HOLE_SPEC = HoleSpec("clearance", "#10", fit="loose")
# Washer bounds are ASME B18.21.1 Table 11, owned by the purchased-part spec.
# Full washer float uses the sourced UNC 2A minimum shank diameter, not
# nominal thread-major geometry, charging the full washer eccentricity.
HANGER_WASHER_FLOAT_MAX = (HANGER_WASHER.ID_MAX - HANGER_SCREW.SHANK_DIA_MIN) / 2.0
HANGER_WASHER_CONCENTRIC_ANNULUS_MIN = (
    HANGER_WASHER.OD_MIN - HANGER_CLEARANCE_DIA_MAX
) / 2.0
if HANGER_WASHER_CONCENTRIC_ANNULUS_MIN <= 0.0:
    raise AssertionError("knife-hanger washer lacks a bearing annulus round its hole")
# The dowel slip hole: a slip on the pin's catalogue diameter at 0.02..0.10
# diametral clearance (the dt_pinion_cam_spec slip band), reamed to an
# explicit +/-0.03 band and printed .XXX: 0.0274..0.0925.
HANGER_PIN_X = KNIFE_DOWEL.HANGER_OFFSET  # 7.632 either side of the bolt axis
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
# slot to its round hole (datum B front, C rear), at their BASIC span,
# oriented by the other round hole with its location released (translation
# modifier), so the two mounts' dowel lines stay square to the B-C line.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "knife-hanger slot position": "0.05",
    "knife-hanger crossbar centring": "0.10",
}
HANGER_CROSSBAR_CENTER_ZONE = float(
    GEOMETRIC_TOLERANCES_MM["knife-hanger crossbar centring"]
)
HANGER_CROSSBAR_CENTER_TOL = HANGER_CROSSBAR_CENTER_ZONE / 2.0
HANGER_SLOT_POSITION_TOL = float(GEOMETRIC_TOLERANCES_MM["knife-hanger slot position"])
# The slot's station from its round hole, BASIC (codex review of 080fda97:
# the frames need a basic location): the frame's zone holds the slot's width
# (across the dowel line), and the note holds its centre along the slot from
# the BASIC at the title block's .XXX band (a slot's plain position frame does
# not reach that direction, codex review of 0bb6ba81; +-0.025 there read as
# over-specification, 50fe7633).  From the screw axis it sits at the round
# hole's .XXX band plus its own: 0.26.
HANGER_SLOT_FROM_ROUND = HANGER_ROUND_X - HANGER_SLOT_X  # 15.264, BASIC
HANGER_SLOT_FROM_ROUND_PLACES = 3
HANGER_SLOT_ALONG_TOL = _XXX  # 0.13
HANGER_SLOT_ALONG_CALLOUT = f"CENTRE \u00b1{HANGER_SLOT_ALONG_TOL:g} ALONG SLOT"
HANGER_SLOT_STATION_TOL = HANGER_PIN_X_TOL + HANGER_SLOT_ALONG_TOL
# The -X dowel's blind slot retains the round hole's slip width and depth.
# Its shortest 3.820 takes the required 3.79508 travel. The functional .XXX
# length limits the longest slot to 4.080; together with the spread dowels
# and 25.0 crossbar, this retains the 2.0 wall guards at the printed bands
# (drawing-guidelines.md rule 17 (walls and webs)).
HANGER_SLOT_WIDTH = HANGER_PIN_HOLE_DIA
HANGER_SLOT_WIDTH_BAND = HANGER_PIN_HOLE_DIA_BAND
HANGER_SLOT_WIDTH_PLACES = HANGER_PIN_HOLE_DIA_PLACES
HANGER_SLOT_LENGTH = 3.95
HANGER_SLOT_LENGTH_PLACES = 3
HANGER_SLOT_LENGTH_TOL = _XXX  # 0.13, functional (above)
HANGER_SLOT_DEPTH = HANGER_PIN_HOLE_DEPTH
HANGER_SLOT_TRAVEL = (
    HANGER_SLOT_ALONG_TOL + KNIFE_DOWEL.SPAN_TOL + HANGER_PIN_SLIP_CLEARANCE_MAX / 2.0
)  # 0.306
HANGER_SLOT_LENGTH_REQUIRED = KNIFE_DOWEL.DIA_MAX + 2.0 * HANGER_SLOT_TRAVEL  # 3.795
if HANGER_SLOT_LENGTH - HANGER_SLOT_LENGTH_TOL < HANGER_SLOT_LENGTH_REQUIRED:
    raise AssertionError(
        f"knife-hanger slot {HANGER_SLOT_LENGTH - HANGER_SLOT_LENGTH_TOL:.3f} long"
        f" at its shortest does not take the dowel's"
        f" {HANGER_SLOT_LENGTH_REQUIRED:.3f} travel"
    )
# The drilled #10 hole's float about the bolt shank is 0.6095 radial.
# The assembly proves the tap/dowel mismatch plus underside-entry drill
# drift stays inside that float.
HANGER_SCREW_FLOAT = (HANGER_CLEARANCE_DIA - HANGER_SCREW.SHANK_DIA) / 2.0
# Suffixes on the model's own slip-hole and slot sizes and the depth they
# share (drawing-guidelines.md rule 7 (notes: few, flagged, never a method) and drawing-guidelines.md rule 12 (hole and slot callouts say what to do): count, process and purpose; the size and its band
# print natively): section F-F carries the round holes' size, the depth of
# all four (both holes and both slots floor at one height) and the slots'
# length; the underside locator the slots' width.  Each names its mate by
# number and name (codex review of 59f405ab).
HANGER_PIN_HOLE_CALLOUT = "2X BLIND FLAT-BOTTOM REAM\nSLIP FIT MHA-VN-051 DOWEL"
HANGER_PIN_DEPTH_CALLOUT = "4X"
HANGER_SLOT_WIDTH_CALLOUT = "2X BLIND SLOT\nREAMED WIDTH, SLIP FIT\nMHA-VN-051 DOWEL"
HANGER_SLOT_LENGTH_CALLOUT = "2X SLOT LENGTH"

# Full thread in the hub at the printed worst case (dt_arbor_pedestal_spec's
# terms): the thread is full only where its major circle lies wholly in metal,
# so the bore's sag across the hole is lost, and so is the one-pitch entry
# chamfer; the flat spot face loses none. The spot face sits at the near end
# of its .X band, the bore at the larger of its printed .XX band and the title
# block's drilled row.
_GOOSENECK_BORE_RADIUS_MAX = (GOOSENECK_BORE_DIA + max(_XX, DRILL_OVERSIZE)) / 2.0
SET_SCREW_THREAD_TERMS = {
    "spot face from bore axis at its minimum": HUB_SET_SPOT_FROM_AXIS - _X,
    "bore radius at its maximum": -_GOOSENECK_BORE_RADIUS_MAX,
    "bore sag across the thread": -_sag(_GOOSENECK_BORE_RADIUS_MAX),
    "one-pitch entry chamfer": -SET_SCREW_PITCH,
}
SET_SCREW_FULL_THREAD_MIN = sum(SET_SCREW_THREAD_TERMS.values())  # 9.58
SET_SCREW_FULL_THREAD_NOMINAL = (
    HUB_SET_SPOT_FROM_AXIS
    - GOOSENECK_BORE_DIA / 2.0
    - _sag(GOOSENECK_BORE_DIA / 2.0)
    - SET_SCREW_PITCH
)  # 10.61
SET_SCREW_ENGAGEMENT_D = SET_SCREW_FULL_THREAD_MIN / SET_SCREW_MAJOR_DIA  # 1.51D
if SET_SCREW_ENGAGEMENT_D < SET_SCREW_MIN_ENGAGEMENT_D:
    raise AssertionError(
        f"hub set screw keeps {SET_SCREW_ENGAGEMENT_D:.2f}D of full thread "
        f"at the printed worst case (< {SET_SCREW_MIN_ENGAGEMENT_D}D)"
    )


# --- Machining-required surfaces ---------------------------------------------
#
# These six faces own native finish controls. The top plane between the
# corner bosses, which seats both MHA-CH-007 keepers on the right (west) rail
# and both MHA-VN-060 washers on the crossbar, and the underside plane between
# the bosses, which seats both MHA-SM-002 knife mounts, carry SEAT_UM in the
# linked facing notes below: each is one plane, so its note names the extent
# instead of a split-line region. The locating-seat finish is not a general
# grade.
#
# * The four tube-socket bores take the MHA-FR-003 columns on a match-fitted close
#   hand-slip; a cast bore wall cannot hold that fit and would score the tube.
# * The four cap-recess floors carry no finish: each MHA-VN-028 cap seats on
#   its tube end (build_fr_frame_assembly asserts it), 1.5 mm above the floor,
#   so the recess only clears the cap skirt.
# * The gooseneck bore guides the O16 counter-spring post through the hub and
#   is pinched by the set screw against it.
# * The set-screw boss's spot face is the machined face the set tap starts
#   square from, so the cup point bears on the post along the tap axis.
#
# SEAT grade throughout: nothing runs on these surfaces continuously, so the
# commercial machine finish is what the fit needs. Each controlled face has
# a native model symbol; each drawing family appears once with a target label.
SOCKET_BORE_TARGET = "TUBE SOCKET BORES, 4X"
SURFACE_FINISHES = tuple(
    SurfaceFinishControl(
        f"socket_{rail}_{end}",
        SEAT_UM,
        CylinderFace(BORE_DIA, contains_x_mm=x, contains_z_mm=z),
        production_method=SOCKET_BORE_TARGET,
    )
    for rail, x in (("east", GOOSENECK_X), ("west", COLUMN_X))
    for end, z in (("front", FRONT_COLUMN_Z), ("rear", REAR_COLUMN_Z))
) + (
    SurfaceFinishControl(
        "hub_bore",
        SEAT_UM,
        CylinderFace(GOOSENECK_BORE_DIA, contains_x_mm=GOOSENECK_X),
    ),
    SurfaceFinishControl(
        "hub_set_spot_face",
        SEAT_UM,
        PlanarFace((-1.0, 0.0, 0.0), HUB_SET_SPOT_FROM_AXIS - GOOSENECK_X),
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
    "Crossbar": {"HangerGrip"},
    "BossUpProfile": {"C0Dia"},
    "BossesUpper": {"BossTopExtent"},
    "BossesLower": {"BossBottomExtent"},
    "BoreProfile": {"B0X", "B0Z", "B0Dia"},
    "CounterboreRearProfile": {"CB1Dia"},
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
    "SetBossProfile": {"SetBossWidth"},
    "SetSpotProfile": {"SetSpotDia"},
    "GooseneckTap": {"SetTapZ"},
    "GooseneckProfile": {"GnDia", "GnX", "GnZ"},
    # The hanger-hole and keeper-tap placement dims (StudFrontX ...,
    # KeeperFrontX ...) are NOT marked: a Hole Wizard placement sketch
    # measures from the origin -- mid-air on the print -- so sheet 3
    # dimensions those stations from the socket bore axes with sheet-derived
    # dimensions (DRAWING_REFERENCE_PRECISION below, drawing-guidelines.md rule 10 (dimension from a real feature)).  The
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
# drawing-simplicity-policy.md `How the repository implements the guidelines`: the places a dimension prints are part of the tolerance it
# claims, and the model owns both.  ``build_fr_top_frame`` applies this table
# natively (``_drawing_precision.apply_drawing_precision``) right after the drawing
# marks, so ``draw_fr_top_frame`` imports each dimension verbatim and only reads
# ``GetPrimaryPrecision2()`` back off the sheet.
#
# One place is this casting's routine band. Hanger positions are clearance
# features drilled under .X (+/-0.8). Keeper positions are model-nominal
# references only: the frame taps are transferred from the bench-pair-reamed,
# fit-up-located keeper feet, not independently located to the general band.
# More places appear only where a fit lives there -- the cap recess diameter
# and depth carry the bilateral bands above, the gooseneck bore prints the
# clearance a purchased post is set into, the finished grip sets the hanger
# bolt's thread engagement, and the dowel slip hole and slot width are reamed
# to their own +/-0.03 band at three places.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "OuterProfile": {"Width": 1, "Depth": 1, "WinWidth": 1, "WinDepth": 1},
    "Crossbar": {"HangerGrip": HANGER_GRIP_PLACES},
    "BossUpProfile": {"C0Dia": 1},
    "BoreProfile": {"B0Dia": 1},
    "CounterboreRearProfile": {"CB1Dia": 1},
    "BarProfile": {"GussetRunE": 1},
    "HubBossProfile": {"HubDia": 1},
    "RibProfile": {"RibWidth": 1},
    "SetBossProfile": {"SetBossWidth": 1},
    "SetSpotProfile": {"SetSpotDia": 1},
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
# drawing-simplicity-policy.md `How the repository implements the guidelines`'s one exception.  Some numbers on this print are distances between two
# model faces that no single model dimension expresses: a web thickness that is
# the difference of two profile offsets, a flange thickness between two extrude
# extents, a boss stack that sums three, a chamfer leg, a counterbore-floor
# separation, a ramp angle.  Their VALUE is still the model's -- every one is
# measured in the view and the build fails if the geometry moved -- but there is
# no model dimension to carry the places, so the places live here, in the part's
# own contract, instead of as a literal in the drawing script.  Keyed by the
# recipe's own dimension label.
DRAWING_REFERENCE_PRECISION: dict[str, int] = {
    # Sheet 1, GEOMETRY: envelope, windows, T-rail section B-B and side
    # section E-E with the crossbar T and its pockets -- cast stock under the
    # title block's general band.
    "overall casting width": 1,
    "overall casting depth": 1,
    "side flange width": 1,
    "left window clear width": 1,
    "right window clear width": 1,
    "crossbar flange width": 1,
    "rail web thickness": 1,
    "front rear flange width": 1,
    "top flange thickness": FLANGE_THICKNESS_PLACES,
    "top rim chamfer": 1,
    "T rail root radius": 1,
    "side rail web thickness": 1,
    "crossbar web thickness": 1,
    "crossbar flange thickness": FLANGE_THICKNESS_PLACES,
    "crossbar pocket depth": 1,
    # Sheet 2, HOLES-SOCKETS: the socket pitches are the setup datums the
    # column plan is drilled from, and MHA-FR-001 states them to 0.01, so they
    # are the one pair of sheet-derived numbers that earns a second place.
    "socket horizontal pitch": 2,
    "socket vertical pitch": 2,
    # Hole stations baseline from socket axes (X from the left pair, Z from
    # the upper pair). Hanger Z stations are drilled under the general band;
    # "hanger x" locates datum D (the crossbar median) under the same band,
    # and the position frame holds the hanger axes BASIC zero on D; keeper
    # coordinates are reference-only guides to assembly-transferred taps.
    "hanger x from left sockets": 1,
    "front hanger z from upper sockets": 1,
    "rear hanger z from upper sockets": 1,
    "keeper x from left sockets": 1,
    "front keeper z from upper sockets": 1,
    "rear keeper z from upper sockets": 1,
    # Sheet 3, CROSS-TAPS: boss stack, cap-mouth chamfer, opposed counterbore
    # floors and the tap axis below the boss top.
    "socket boss overall height": 1,
    "boss top above rail top": 1,
    "top bore mouth chamfer": 1,
    "opposed counterbore floor separation": 1,
    "cross screw axis from boss top": 1,
    # .XX, the floor at 16.35 (fr_frame_attachment_spec.TOP_SCREW_SEAT_Z):
    # 2.04 to the cap recess at every printed corner
    # (build_fr_top_frame.COUNTERBORE_PRINTED_CAP_LIGAMENT).
    "counterbore floor from socket axis": 2,
    # Sheet 5, HUB-SET-SCREW: hub station, set-tap axis, gusset ramp and the
    # cropped set-screw boss section D-D (spot face, boss face, thread run).
    "hub from left front socket": 1,
    "set screw axis from rail top": 1,
    "hub boss underside drop": 1,
    "hub gusset feather span": 1,
    "hub gusset ramp angle": 1,
    "set-screw spot face from bore axis": HUB_SET_SPOT_PLACES,
    "set-screw thread length": 1,
    "set-screw boss face from bore axis": 1,
    # Sheet 6, UNDERSIDE: the junction lands and the knife-hanger section F-F
    # -- the native finished-top grip is imported, while dowel stations and slot
    # length are measured associatively from their visible model features.
    "crossbar junction land": 1,
    "crossbar pocket length": 1,
    "underside gusset thickness": 1,
    "dowel hole from hanger axis": HANGER_PIN_X_PLACES,
    "dowel slot from dowel hole": HANGER_SLOT_FROM_ROUND_PLACES,
    "dowel slot length": HANGER_SLOT_LENGTH_PLACES,
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
# drawing-guidelines.md rule 17 (walls and webs) receiver-wall stack: realistic angular drift through the FULL
# printed cylindrical pilot depth, without relying on a precision drill jig.
KEEPER_TAP_DRILL_WANDER_DEG = 0.3
# The same allowance as a lateral drift per mm from a hole's entry face: the
# knife-hanger holes, drilled from the faced underside, charge it
# at the depth each wall is judged (``build_fr_top_frame``).
DRILL_DRIFT_PER_MM = tan(radians(KEEPER_TAP_DRILL_WANDER_DEG))  # 0.00524

# The nominal socket geometry stays fixed; the assigned actual tube governs fit.
# The C2 general break overrides the title block's 0.25 max break on the
# convex casting edges the model chamfers; hole, bore, counterbore, tap and
# slot mouths keep the title-block break (the counterbore and tap walls are
# proved without a chamfer).  The edges too short, too close to a feature or
# under a knife seat for C2 (build_fr_top_frame._external_edge_breaks) are
# the "UNLESS NOTED": section E-E's note names the crossbar flange underside,
# the hub side view's note the hub rib bottoms and V-gussets, the underside
# locator's the bar and gusset bottoms at the knife seats; they keep the
# title block break.  drawing-guidelines.md rule 7 (notes: few, flagged, never a method) caps this block at four lines of at most 70
# characters.
DRAWING_NOTES = (
    "MATCH EACH SOCKET TO ITS ASSIGNED ACTUAL MHA-FR-003 TUBE.\n"
    "CLOSE HAND-SLIP; NO PERCEPTIBLE ROCK.\n"
    "RETAIN CORNER AND ORIENTATION MATCH MARKS.\n"
    "CONVEX CASTING EDGES C2 X 45 UNLESS NOTED; HOLE EDGES PER TITLE BLOCK."
)
# User rulings 2026-10-11 and 2026-10-14: the whole top plane between the four
# corner bosses is faced, so both keeper feet land on one flat right-rail face
# wherever fit-up puts them and both washers bear on the crossbar's faced top;
# no split-line regions and no geometry change: the model's top is the
# finished plane.  Its own property, placed beside the keeper callout on
# HOLES-SOCKETS.  The flatness stays on the keeper rail and the last row
# states why it is held: the two keepers' lug bores carry one fulcrum shaft
# in a running fit (blind machinist review, farm 0fbfc4d75).
DRAWING_NOTES_B = (
    "WHOLE TOP EXCEPT 4 BOSSES:\n"
    f"Ra {SEAT_UM:.1f} UM; RIGHT RAIL FLAT\n"
    f"WITHIN {KEEPER_SEAT_FLATNESS_BUDGET_MM:.2f} SO BOTH KEEPER\n"
    "(MHA-CH-007) BORES ALIGN."
)
# User ruling 2026-10-12 (reading (i)): every face on the 999.7 underside
# plane between the bosses is faced at the seat finish -- the rail web
# bottoms, the junction lands and plan gussets, and the crossbar's full-depth
# ends that seat both MHA-SM-002 knife mounts.  The 4X corner-boss bottoms
# (6.3 below the plane) and the hub boss and its V-gussets (8.0 below) stay
# off it.  No flatness zone (both knife seats lie on the one faced plane; no
# stack spends a form budget on it) and no geometry change: the model's
# underside is the finished plane.  Its own property, on the UNDERSIDE sheet
# beside the enlarged detail of the hub boss and gussets it excludes.
DRAWING_NOTES_C = (
    "UNDERSIDE PLANE BETWEEN BOSSES\n"
    "(MHA-SM-002 KNIFE-MOUNT SEATS):\n"
    f"Ra {SEAT_UM:.1f} UM; BOSS BOTTOMS AND\n"
    "HUB GUSSETS EXCLUDED."
)
