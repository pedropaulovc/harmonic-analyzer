r"""Pure-data dimensional contract shared by the cone swing platform and drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_cone_swing_platform`` imports the
marked-dimension NAME map, the decimal places and the surface-finish controls
from here; ``draw_cone_swing_platform`` keeps exactly ``DRAWING_DIMENSIONS`` and
imports the plate's plan geometry from ``build_cone_swing_platform`` for its
view math.
"""

from __future__ import annotations

import math

from _fit_limits import deviations
from _gtol_spec import PlanarFace
from _hole_spec import HoleSpec, blind_cut_dia_mm
from _surface_finish import MACHINED_UM, SEAT_UM, SurfaceFinishControl

import cone_pivot_post_spec
from crank_drive_gear_spec import OUTSIDE_DIA as CRANK_GEAR_OUTSIDE_DIA

POST_ATTACHMENT_SPACING = cone_pivot_post_spec.ATTACHMENT_SPACING
POST_BLOCK_DIA = cone_pivot_post_spec.BLOCK_DIA
POST_CONE_BORE_HEIGHT = cone_pivot_post_spec.BORE_HEIGHT


PLATE_THICKNESS = 6.35
# User ruling U41 (2026-09-23): the thickness is the stock's, printed as a
# reference "(6.35)" with "1/4 PLATE AS SUPPLIED" -- no machined thickness
# band.  Rule-12 stacks through the plate use the stock's mill tolerance.
PLATE_STOCK_BAND = 0.13
# Two lines: on one, the text hung 49.5 mm left of section A-A into the
# notch plan's 7.0 and 205.81 (81788ce9 render).  Broken after "AS" so the
# last line, beside the dimension's top arrowhead, is the short one and sits
# back from it (aa9766da: "AS SUPPLIED" ran its D into the arrow).
PLATE_STOCK_CALLOUT = "1/4 PLATE AS\nSUPPLIED"
# The top relief is 10.50 wide, round-ended about the pivot and OPEN through
# the north edge (rule-12 W18, Main 2026-09-23, option (d)): as a closed
# Ø10.50 spotface 7.0 from that edge it left a 1.75 web.  The width keeps the
# stock 3/8 head's radial clearance (BDT reads it as the relief diameter).
PIVOT_BEARING_RELIEF_DIAMETER = 10.50
PIVOT_BEARING_RELIEF_DEPTH = 0.25  # Reference nominal; the finished matched fit governs.
PIVOT_HEAD_RADIAL_CLEARANCE = 0.4875
PIVOT_BEARING_THICKNESS = PLATE_THICKNESS - PIVOT_BEARING_RELIEF_DEPTH
# User decision relayed by Main, 2026-09-22: fit the actual purchased shoulder
# and finished plate; do not invent a numerical axial-clearance band.
PIVOT_RELIEF_FIT_REQUIREMENT = (
    "TOP PIVOT RELIEF: MATCH DEPTH TO FINISHED PLATE\n"
    "AND McMASTER 91829A560 CONE-PIVOT-SCREW.\n"
    "WITH SHOULDER SEATED ON BASE, LOCK KNOB RELEASED:\n"
    "PLATFORM SWINGS FREELY WITH MINIMAL AXIAL PLAY."
)
# The platform swings on the stock 1/4-in shoulder, but this occasional setup
# pivot has no measured need for a close running bearing fit.  Preserve the
# established native Hole Wizard close-clearance feature and its table size.
PIVOT_HOLE_SPEC = HoleSpec("clearance", "1/4", fit="close")
PIVOT_HOLE_DIA = blind_cut_dia_mm(PIVOT_HOLE_SPEC)


# The recentered DP25.731 gear is smaller than the intermediate DP24.74 gear;
# its complete swept OD now clears the platform top, so the obsolete scallop is
# removed and the plate remains full thickness beneath the mesh.
CRANK_GEAR_PLATFORM_CLEARANCE = POST_CONE_BORE_HEIGHT - CRANK_GEAR_OUTSIDE_DIA / 2.0
if CRANK_GEAR_PLATFORM_CLEARANCE < 0.5:
    raise AssertionError("recentered crank gear has under 0.5 mm platform air")


# The post's 1/4-in fillister clearance bores mate to these platform threads.
# The pitch is imported from the post spec; the tapped-hole size is the
# counterpart required by that purchased screw family.
POST_MOUNT_SPEC = HoleSpec("tapped", "1/4-20")
POST_MOUNT_TAP_DIA = blind_cut_dia_mm(POST_MOUNT_SPEC)
# The MHA-142 post screws (MSC 40923898, 1/4-20 fillister, cut to fit, U37c)
# thread through the plate, flush to this much short of its underside.
POST_SCREW_CUT_TO_FIT_SHORT = 0.3
POST_MOUNT_THREAD_DIA = 0.25 * 25.4
# The title block's R0.25/0.25 edge break would take up to 0.25 of thread off
# each end of the through tap (0.85D worst case, under the audit floor), so the
# two tapped holes carry a local override: deburr only (Main, 2026-09-24).
POST_MOUNT_TAP_EDGE_BREAK = 0.1
POST_MOUNT_TAP_BREAK_NOTE = (
    f"1/4-20 TAPPED HOLES: DEBURR ONLY, {POST_MOUNT_TAP_EDGE_BREAK:.1f} MAX BREAK EACH END."
)
# U37 (2026-09-23): the user accepted short engagement for MHA-142 as a named
# exception to rule 12's 1.5D; the plate slides on the deck, so no boss can
# add thread.  Worst case: the thinnest stock plate (U41) less the cut-to-fit
# allowance and the break at both ends of the tap, counted as MHA-139 counts
# its exit break.  A MIN never rounds up, so the print floors to two places.
POST_MOUNT_ENGAGEMENT_WORST = round(
    PLATE_THICKNESS
    - PLATE_STOCK_BAND
    - POST_SCREW_CUT_TO_FIT_SHORT
    - 2.0 * POST_MOUNT_TAP_EDGE_BREAK,
    6,
)
POST_MOUNT_ENGAGEMENT_WORST_DIAMETERS = (
    POST_MOUNT_ENGAGEMENT_WORST / POST_MOUNT_THREAD_DIA
)
POST_MOUNT_ENGAGEMENT_PRINTED = (
    math.floor(POST_MOUNT_ENGAGEMENT_WORST_DIAMETERS * 100.0) / 100.0
)
# The rule-12 audit's E7 floor (0.87D, at the old .XX plate band): the stock
# band must not print below it without a new ruling.
if POST_MOUNT_ENGAGEMENT_PRINTED < 0.87:
    raise AssertionError("MHA-142 engagement fell below the audited 0.87D floor")
# The sheet states the named exception, worded like MHA-139's, over the
# break override it depends on: one line each.
POST_MOUNT_ENGAGEMENT_NOTE = (
    f"1/4-20 THREAD ENGAGEMENT {POST_MOUNT_ENGAGEMENT_PRINTED:.2f}D MIN (MHA-142): "
    "NAMED EXCEPTION TO RULE 12.\n"
    f"{POST_MOUNT_TAP_BREAK_NOTE}"
)


# I31 option 1 (Main, 2026-09-25): the cone tip block is held down by one
# #6-32 x 5/8 hex head screw (McMaster 93075A150, low-strength zinc-plated
# steel) rising from under the plate through a lateral slot, through the shim
# pack and the block's south foot flange (an axial slot), into a nylon-insert
# locknut on the flange top.  The plate slot lets the block move across the
# cone axis, the flange slot along it.  The head sits in a counterbored slot
# one hex width across, so its walls stop the head turning while the nut is
# tightened from above.
#
# The block's own geometry, mirrored here because the plate may not import
# cone_tip_block_spec; build_drive_train_assembly asserts each one equal to
# the block spec's.  The block centre stands 11.0 south of the pivot (the
# drive-train layout: PIVOT_STATION = TIP_BLOCK_STATION + 11.0).
TIP_BLOCK_LOCAL_Z = -11.0
TIP_BLOCK_HALF_DEPTH = 6.0  # BLOCK_Z / 2
TIP_BLOCK_HALF_WIDTH = 7.5  # BLOCK_X / 2
# FLANGE_SLOT_X: the flange slot's centre from the block's +X face, which is
# its west face (the block and the plate share the inclined frame).
TIP_FLANGE_SLOT_X = 7.5
TIP_FLANGE_SLOT_Z = 10.7  # FLANGE_SLOT_Z, from the block's south face
# FLANGE_SLOT_FLOAT: the screw's float across the 5/32 +0.10/0 flange slot.
TIP_FLANGE_SLOT_FLOAT = (5.0 / 32.0 * 25.4 + 0.10 - 3.505) / 2.0
# How far north the shaft tip can set the block's north face: the shaft's
# overall length Sec4End at .X (the heel-relief check's HEEL_TIP_TRAVEL).
TIP_BLOCK_NORTH_TRAVEL = 0.8
# The lateral slot sits under the flange slot's centre.
TIP_SCREW_LOCAL_Z = TIP_BLOCK_LOCAL_Z - (TIP_BLOCK_HALF_DEPTH + TIP_FLANGE_SLOT_Z)
# Both slots share two end centres TIP_SCREW_HALF_TRAVEL either side of the
# cone axis.
TIP_SCREW_HALF_TRAVEL = 2.0
TIP_SCREW_MAJOR = 3.505  # #6-32 basic major
# McMaster 93075A150 (product page read 2026-09-25): head 1/4 wide x 3/32
# high.  ASME B18.6.3 bounds the #6 hex head at 0.244-0.250 across the flats
# and 0.272 min across the corners; the catalogue height is taken as the max.
TIP_SCREW_HEAD_AF = (0.244 * 25.4, 0.250 * 25.4)
TIP_SCREW_HEAD_AC_MIN = 0.272 * 25.4
TIP_SCREW_HEAD_H_MAX = 3.0 / 32.0 * 25.4
# The slot widths are cut in one pass by an end mill of that size, so they
# carry the same one-sided +0.10/0 band as the title block's DRILLED HOLES
# row: the cutter makes the size, the machinist holds nothing tight.  Each
# band is written (upper, lower) like every _fit_limits band and is only ever
# read through _fit_limits.deviations -- here and on the model -- never by
# index: a raw [1] read the flipped band's lower deviation as its upper and
# made the head bearing 0.05 a side too generous with no failure (dtscout).
TIP_SLOT_W = 4.0
# I31 (Main, 2026-09-25): a 6.5 end mill, not the 1/4 one the head's across
# flats would need line to line: the widest head runs in the narrowest slot
# and the smallest head's corners still cannot turn in the widest one.
TIP_CBORE_W = 6.5
TIP_SLOT_W_BAND = (0.10, 0.0)
TIP_CBORE_W_BAND = (0.10, 0.0)
TIP_CBORE_DEPTH = 3.00  # .XX
_XX = 0.51
_TIP_SLOT_W_LOWER, _TIP_SLOT_W_UPPER = deviations(TIP_SLOT_W_BAND)
_TIP_CBORE_W_LOWER, _TIP_CBORE_W_UPPER = deviations(TIP_CBORE_W_BAND)
TIP_SLOT_W_MIN = TIP_SLOT_W + _TIP_SLOT_W_LOWER
TIP_SLOT_W_MAX = TIP_SLOT_W + _TIP_SLOT_W_UPPER
TIP_CBORE_W_MIN = TIP_CBORE_W + _TIP_CBORE_W_LOWER
TIP_CBORE_W_MAX = TIP_CBORE_W + _TIP_CBORE_W_UPPER
TIP_SLOT_SCREW_CLEARANCE = TIP_SLOT_W_MIN - TIP_SCREW_MAJOR
TIP_SLOT_FLOAT_MAX = (TIP_SLOT_W_MAX - TIP_SCREW_MAJOR) / 2.0
TIP_SLOT_HEAD_BEARING = (TIP_SCREW_HEAD_AF[0] - TIP_SLOT_W_MAX) / 2.0
# The head runs in the counterbored slot at its narrowest against the widest
# head, and cannot turn in it at its widest against the smallest head.
TIP_CBORE_HEAD_ENTRY = TIP_CBORE_W_MIN - TIP_SCREW_HEAD_AF[1]
TIP_CBORE_ANTI_TURN_MIN = 0.25
TIP_CBORE_HEAD_TURN_MARGIN = TIP_SCREW_HEAD_AC_MIN - TIP_CBORE_W_MAX
TIP_HEAD_RECESS = TIP_CBORE_DEPTH - _XX - TIP_SCREW_HEAD_H_MAX
# Ledge under the head: the stock plate less the .XX counterbore depth, both
# bands (rule-12 audit W22: the first cut left out the plate's band).
TIP_LEDGE_RANGE = (
    PLATE_THICKNESS - PLATE_STOCK_BAND - TIP_CBORE_DEPTH - _XX,
    PLATE_THICKNESS + PLATE_STOCK_BAND - TIP_CBORE_DEPTH + _XX,
)
# Lateral fit-up travel either side of the cone axis: the end centres plus
# the screw's float in the narrowest slot, which is the nominal 4.0 (+/-2.25),
# and with the .XX centres at their short limit (+/-1.74).
TIP_LATERAL_TRAVEL = TIP_SCREW_HALF_TRAVEL + TIP_SLOT_SCREW_CLEARANCE / 2.0
TIP_LATERAL_TRAVEL_WORST = TIP_LATERAL_TRAVEL - _XX
if (round(TIP_LATERAL_TRAVEL, 2), round(TIP_LATERAL_TRAVEL_WORST, 2)) != (2.25, 1.74):
    raise AssertionError("tip-block lateral travel no longer reads +/-2.25 (1.74 worst)")
if TIP_SLOT_SCREW_CLEARANCE < 0.25:
    raise AssertionError("tip-block screw slot does not clear the #6-32 major")
if TIP_SLOT_HEAD_BEARING < 0.5:
    raise AssertionError("tip-block screw head bears on under 0.5 mm per side")
if TIP_CBORE_HEAD_ENTRY <= 0.0:
    raise AssertionError("the widest hex head has no running clearance in the counterbored slot")
if TIP_CBORE_HEAD_TURN_MARGIN < TIP_CBORE_ANTI_TURN_MIN:
    raise AssertionError(
        "the smallest hex head's corners overlap the widest counterbored slot "
        f"by {TIP_CBORE_HEAD_TURN_MARGIN:.3f} (< {TIP_CBORE_ANTI_TURN_MIN})"
    )
if TIP_HEAD_RECESS < 0.1:
    raise AssertionError("tip-block screw head can stand proud of the slide face")
if TIP_LEDGE_RANGE[0] < 2.0:
    raise AssertionError("tip-block counterbore ledge is below the U27 2.0 target")
# The block's farthest reach west of the cone axis, at full west travel with
# every float and location band taken up: the plate slot's west end centre
# (TipSlotWestCx, .XX), the screw's float in the widest plate slot, its float
# in the widest flange slot, and the flange slot's location from the block's
# west face (FlangeSlotX, .XX on the block).  Its north face stands
# TIP_BLOCK_NORTH_TRAVEL north, set by the shaft tip.  build_cone_swing_platform
# derives the plate's north-west half-width from it with the outline's own
# bands (Main, I31 item 8: the U30 slot let the block hang 0.19 over the west
# edge; 2026-09-25: the location bands belong in the stack).
TIP_BLOCK_WEST_REACH = (
    (TIP_SCREW_HALF_TRAVEL + _XX)
    + TIP_SLOT_FLOAT_MAX
    + TIP_FLANGE_SLOT_FLOAT
    + (TIP_FLANGE_SLOT_X + _XX)
)
TIP_BLOCK_NORTH_REACH_Z = TIP_BLOCK_LOCAL_Z + TIP_BLOCK_HALF_DEPTH + TIP_BLOCK_NORTH_TRAVEL
TIP_BLOCK_EDGE_MARGIN = 0.25


# Only functional sliding/locating surfaces carry roughness.  The existing
# close-clearance pivot hole needs no bearing-finish control; the top locates
# the post and tip block, and the underside slides on the harmonic-base deck.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "post_seat", SEAT_UM, PlanarFace((0, 1, 0), PLATE_THICKNESS)
    ),
    SurfaceFinishControl(
        "base_slide", MACHINED_UM, PlanarFace((0, -1, 0), 0.0)
    ),
)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The pivot-hole centre is the layout origin: every plan corner,
# both post-mount taps and the lock notch are located from it in the plate's own
# axes (station along the cone axis, offset across it), so a shop lays the whole
# plate out from one scribed centre.  Corner radii come off their fillets. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {
        "NorthEastX",
        "NorthEdgeZ",
        "NorthWestX",
        "SouthWestX",
        "PlateLenDim",
        "SouthEastX",
    },
    "Plate": {"PlateThk"},
    "PivotBearingReliefProfile": {"PivotBearingReliefDia"},
    "PivotBearingRelief": {"PivotBearingReliefDepth"},
    "PostMountHoles": {
        "PostMountWestX",
        "PostMountWestZ",
        "PostMountEastX",
        "PostMountEastZ",
    },
    "LockNotchCapEProfile": {"CapECx", "CapECz", "CapEDia"},
    "TipScrewSlotProfile": {"TipSlotEastCx", "TipSlotWestCx", "TipSlotZ", "TipSlotW"},
    "TipScrewCboreProfile": {"TipCboreW"},
    "TipScrewCbore": {"TipCboreDepth"},
    "CornerNE": {"CornerNER"},
    "CornerNW": {"CornerNWR"},
    "CornerSW": {"CornerSWR"},
    "CornerSE": {"CornerSER"},
}

# Decimal places ARE the tolerance statement (drawing-simplicity policy rule
# 2), so the MODEL owns them: build_cone_swing_platform applies this map to the
# .SLDPRT and draw_cone_swing_platform only reads it back. The whole plate
# outline prints one place (+/-0.8): the east edge at the swing stop and the
# west edge at the notch mouth spend the disengaged lock-collar margin, which
# build_cone_swing_platform.DISENGAGE_COLLAR_MARGIN sizes to keep >= 2.0 mm
# at this band.  Relief diameter, tapped-hole pattern and notch stay at the
# .XX grade. Relief
# depth is a reference nominal governed by the matched fit above. The Hole
# Wizard owns the pivot-hole size/callout.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PlateProfile": {
        "NorthEastX": 1,
        "NorthEdgeZ": 1,
        "NorthWestX": 1,
        "SouthWestX": 1,
        "PlateLenDim": 1,
        "SouthEastX": 1,
    },
    "Plate": {"PlateThk": 2},
    "PivotBearingReliefProfile": {"PivotBearingReliefDia": 2},
    "PivotBearingRelief": {"PivotBearingReliefDepth": 2},
    "PostMountHoles": {
        "PostMountWestX": 2,
        "PostMountWestZ": 2,
        "PostMountEastX": 2,
        "PostMountEastZ": 2,
    },
    "LockNotchCapEProfile": {"CapECx": 2, "CapECz": 2, "CapEDia": 2},
    # The slot ends are .XX so the +/-2.25 fit-up travel keeps >= +/-1.74
    # (TIP_LATERAL_TRAVEL, TIP_LATERAL_TRAVEL_WORST).
    "TipScrewSlotProfile": {
        "TipSlotEastCx": 2,
        "TipSlotWestCx": 2,
        "TipSlotZ": 2,
        "TipSlotW": 1,
    },
    "TipScrewCboreProfile": {"TipCboreW": 2},
    "TipScrewCbore": {"TipCboreDepth": 2},
    "CornerNE": {"CornerNER": 1},
    "CornerNW": {"CornerNWR": 1},
    "CornerSW": {"CornerSWR": 1},
    "CornerSE": {"CornerSER": 1},
}


_PRECISION_NAMES = [
    (feature, name) for feature, names in DRAWING_PRECISION.items() for name in names
]
if any(
    name not in DRAWING_DIMENSIONS.get(feature, frozenset())
    for feature, name in _PRECISION_NAMES
):
    raise AssertionError("DRAWING_PRECISION names a dimension the part never marks")
if any(
    name not in {name for names in DRAWING_PRECISION.values() for name in names}
    for names in DRAWING_DIMENSIONS.values()
    for name in names
):
    raise AssertionError("a marked dimension prints without part-authored places")
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: DRAWING_PRECISION[feature][name] for feature, name in _PRECISION_NAMES
}
if len(DRAWING_PRECISION_BY_NAME) != len(_PRECISION_NAMES):
    raise AssertionError("DRAWING_PRECISION repeats a dimension name across features")


# View scales differ from the sheet scale and therefore remain property-linked
# labels.  The split plans are named so each dimension set has an unambiguous
# owner; these are view captions, not manufacturing notes.
PROFILE_VIEW_NOTE = "PLATE PROFILE — SCALE 1:2"
FEATURE_VIEW_NOTE = "HOLE LOCATIONS — SCALE 1:2"
NOTCH_VIEW_NOTE = "LOCK NOTCH — SCALE 1:2"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:3"
