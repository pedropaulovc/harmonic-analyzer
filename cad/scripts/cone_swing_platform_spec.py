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
from _hole_spec import Countersink, HoleSpec, blind_cut_dia_mm
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
# and finished plate; do not invent a numerical axial-clearance band.  The
# wording is the user's; only its prefix names the feature as the sheet's
# leadered ID does ("TOP RELIEF", MHA-091 round 6 -- the Fable review's
# request for a numeric axial band is answered by this decision).
PIVOT_RELIEF_FIT_REQUIREMENT = (
    "TOP RELIEF: MATCH DEPTH TO FINISHED PLATE\n"
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
POST_MOUNT_THREAD_DIA = 0.25 * 25.4
# The title block's R0.25/0.25 edge break would take up to 0.25 of thread off
# each end of the through tap (0.85D worst case, under the floor), so each
# end of both taps is broken by a native Hole Wizard countersink, 90 deg, just
# wide enough to take POST_MOUNT_TAP_EDGE_BREAK of full thread (Main,
# 2026-09-24; model-owned since #917 S1 -- rule 6 forbids the old "DEBURR
# ONLY" note).  Its diameter is banded MAX, so the tap callout prints the
# limit from the part; no note or sheet dimension restates it.
POST_MOUNT_TAP_EDGE_BREAK = 0.1
POST_MOUNT_TAP_CSK_ANGLE_DEG = 90.0
POST_MOUNT_TAP_CSK = Countersink(
    round(
        POST_MOUNT_THREAD_DIA
        + 2.0
        * POST_MOUNT_TAP_EDGE_BREAK
        * math.tan(math.radians(POST_MOUNT_TAP_CSK_ANGLE_DEG / 2.0)),
        6,
    ),
    POST_MOUNT_TAP_CSK_ANGLE_DEG,
    max_limit=True,
)
# The callout prints the MAX at two places; the diameter must be exact there.
if round(POST_MOUNT_TAP_CSK.dia_mm, 2) != POST_MOUNT_TAP_CSK.dia_mm:
    raise AssertionError(
        f"tap countersink {POST_MOUNT_TAP_CSK.dia_mm} does not print at two places"
    )
POST_MOUNT_SPEC = HoleSpec(
    "tapped",
    "1/4-20",
    near_countersink=POST_MOUNT_TAP_CSK,
    far_countersink=POST_MOUNT_TAP_CSK,
)
POST_MOUNT_TAP_DIA = blind_cut_dia_mm(POST_MOUNT_SPEC)
# The MHA-142 post screws (MSC 40923898, 1/4-20 fillister, cut to fit, U37c)
# thread through the plate, flush to this much short of its underside.
POST_SCREW_CUT_TO_FIT_SHORT = 0.3
# The screw's cut end is deburred to this break at most
# (post_mount_screw_spec.CUT_END_BREAK_MAX_MM, mirrored: the platform may not
# import the screw's builder; the stack's cross-check test compares them).
POST_SCREW_CUT_END_BREAK_MAX = 0.1


def post_mount_engagement_worst(
    plate_t: float,
    stock_band: float,
    tap_entry_break: float,
    tap_exit_break: float,
    cut_to_fit_short: float,
    cut_end_break: float,
) -> float:
    """MHA-142's worst-case thread in the plate, post_mount_screw_spec's stack:
    the thinnest plate, less the tap's entry break (the screw comes in from
    the top), less the deeper of the tap's exit break and the screw's
    cut-to-fit short plus its cut-end break (whichever ends the thread first
    at the underside)."""
    return (
        plate_t
        - stock_band
        - tap_entry_break
        - max(tap_exit_break, cut_to_fit_short + cut_end_break)
    )


# U37 (2026-09-23): the user accepted short engagement for MHA-142 as a named
# exception to rule 12's 1.5D; the plate slides on the deck, so no boss can
# add thread.  Worst case: the thinnest stock plate (U41) through the stack
# above; the tap's break is the same at both ends.  A MIN never rounds up, so
# the print floors to two places.
POST_MOUNT_ENGAGEMENT_WORST = round(
    post_mount_engagement_worst(
        PLATE_THICKNESS,
        PLATE_STOCK_BAND,
        POST_MOUNT_TAP_EDGE_BREAK,
        POST_MOUNT_TAP_EDGE_BREAK,
        POST_SCREW_CUT_TO_FIT_SHORT,
        POST_SCREW_CUT_END_BREAK_MAX,
    ),
    6,
)
POST_MOUNT_ENGAGEMENT_WORST_DIAMETERS = (
    POST_MOUNT_ENGAGEMENT_WORST / POST_MOUNT_THREAD_DIA
)
POST_MOUNT_ENGAGEMENT_PRINTED = (
    math.floor(POST_MOUNT_ENGAGEMENT_WORST_DIAMETERS * 100.0) / 100.0
)
# One floor for the joint: the user's U37c/U41 named exception, 0.90D
# (post_mount_screw_spec.MIN_ENGAGEMENT_DIAMETERS, mirrored; the stack's
# cross-check test compares them).  It replaced the rule-12 audit's looser E7
# floor (#846), which only the platform carried (Main, #917 S1).
POST_MOUNT_ENGAGEMENT_MIN_DIAMETERS = 0.90
if POST_MOUNT_ENGAGEMENT_PRINTED < POST_MOUNT_ENGAGEMENT_MIN_DIAMETERS:
    raise AssertionError(
        f"MHA-142 engagement fell below the user's "
        f"{POST_MOUNT_ENGAGEMENT_MIN_DIAMETERS:.2f}D floor"
    )


# The title block's location bands by decimal places.
TITLE_BLOCK_BAND_BY_PLACES = {1: 0.8, 2: 0.51}


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
# cone_tip_block_spec.  In the #917 stack, build_drive_train_assembly asserts
# each mirror equal to the block spec's from conegear's (b) (7ab69742b)
# upward; below it nothing checks them.  The block centre stands 11.0 south
# of the pivot (the drive-train layout: PIVOT_STATION = TIP_BLOCK_STATION +
# 11.0).
TIP_BLOCK_LOCAL_Z = -11.0
TIP_BLOCK_HALF_DEPTH = 6.0  # BLOCK_Z / 2
TIP_BLOCK_HALF_WIDTH = 7.5  # BLOCK_X / 2
# FLANGE_SLOT_X: the flange slot's centre from the block's +X face, which is
# its west face (the block and the plate share the inclined frame).
TIP_FLANGE_SLOT_X = 7.5
TIP_FLANGE_SLOT_Z = 10.7  # FLANGE_SLOT_Z, from the block's south face
# FLANGE_SLOT_FLOAT: the screw's float across the 5/32 +0.10/0 flange slot.
TIP_FLANGE_SLOT_FLOAT = (5.0 / 32.0 * 25.4 + 0.10 - 3.505) / 2.0
# How far north the shaft tip can set the block's north face (#917 S1: the
# shaft is located by its collar against the post's cone boss, and the post by
# transfer at fit-up):
#   - the tip from the collar face, the shaft's Sec4End at .X (the heel-relief
#     check's HEEL_TIP_TRAVEL; a literal, the plate may not import the shaft
#     spec);
#   - the post's cone-boss face-to-face (ConeBossLen) at its printed grade,
#     read from the post's own precision;
#   - the post's transfer at fit-up (the plan's T-A TRANSFER_POST_LATERAL).
_TIP_FROM_COLLAR_BAND = 0.8
_POST_CONE_BOSS_BAND = TITLE_BLOCK_BAND_BY_PLACES[
    cone_pivot_post_spec.DRAWING_PRECISION_BY_NAME["ConeBossLen"]
]
_POST_TRANSFER = 0.05
TIP_BLOCK_NORTH_TRAVEL = _TIP_FROM_COLLAR_BAND + _POST_CONE_BOSS_BAND + _POST_TRANSFER
if round(TIP_BLOCK_NORTH_TRAVEL, 2) != 1.65:
    raise AssertionError(
        f"tip block north travel reads {TIP_BLOCK_NORTH_TRAVEL:.3f}, not the ruled 1.65"
    )
# The lateral slot sits under the flange slot's centre.
TIP_SCREW_LOCAL_Z = TIP_BLOCK_LOCAL_Z - (TIP_BLOCK_HALF_DEPTH + TIP_FLANGE_SLOT_Z)
# Both slots share two end centres TIP_SCREW_HALF_TRAVEL either side of the
# cone axis.  #917 S1 (plan A1, Main/user ruling 2026-09-26): +/-2.0 -> +/-2.5,
# so the fit-up (tip block sets T006 with the post screws finger-tight) has
# +/-0.906 of worst-case lateral reach after the slot ends' and the block's
# location bands; at +/-2.0 it had 0.427.
TIP_SCREW_HALF_TRAVEL = 2.5
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
_XX = TITLE_BLOCK_BAND_BY_PLACES[2]
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
# the screw's float in the narrowest slot, which is the nominal 4.0 (+/-2.75),
# and with the .XX centres at their short limit (+/-2.24).
TIP_LATERAL_TRAVEL = TIP_SCREW_HALF_TRAVEL + TIP_SLOT_SCREW_CLEARANCE / 2.0
TIP_LATERAL_TRAVEL_WORST = TIP_LATERAL_TRAVEL - _XX
if (round(TIP_LATERAL_TRAVEL, 2), round(TIP_LATERAL_TRAVEL_WORST, 2)) != (2.75, 2.24):
    raise AssertionError("tip-block lateral travel no longer reads +/-2.75 (2.24 worst)")
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


# #917 S1: the post dowel pair, match-drilled through the plate into the post
# foot after fit-up.  Owned by the leaf cone_post_dowel_spec (the post reads it
# too, and this module already imports the post's spec); re-exported here under
# the names conegear's fit-up budget imports.
from cone_post_dowel_spec import (  # noqa: E402
    POST_DOWEL_BLIND_DEPTH as POST_DOWEL_BLIND_DEPTH,
    POST_DOWEL_DIA as POST_DOWEL_DIA,
    POST_DOWEL_PLATE_XZ as POST_DOWEL_PLATE_XZ,
    POST_DOWEL_RECESS as POST_DOWEL_RECESS,
)


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
# print shows.  The pivot-hole centre is the layout origin: every plan corner
# and the lock notch are located from it in the plate's own axes (station along
# the cone axis, offset across it), so a shop lays the whole plate out from one
# scribed centre.  Corner radii come off their fillets.  The two post-mount taps
# and the dowel pair print no station: #917 (user ruling via Main, 2026-09-26)
# transfers the taps from MHA-016 at assembly, as #837 does on the base, and
# match-drills the dowels through the fitted post. ---
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
    # The closed-end cap locates the notch; the run angle gives its rails a
    # direction (the chord the lock stud follows).  Without it the sheet
    # defines where the notch starts but not which way it runs.
    # The notch is a slot: one width across its rails (NotchW) and a full
    # radius at the closed end, located at that radius's centre (rule 7).
    # The cap's diameter is SlotW by equation and prints as "R" only, so the
    # 8.00 is stated once (MHA-091 Fable review, 63fb3bd2d; Main round 6).
    "LockNotchProfile": {"NotchMouthAngle", "NotchW"},
    "LockNotchCapEProfile": {"CapECx", "CapECz"},
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
# at this band.  Relief diameter and notch stay at the .XX grade.  Relief
# depth is a reference nominal governed by the matched fit above.  The Hole
# Wizard owns the pivot-hole size/callout.
#
# The tapped pair prints no station: neither .XX (+/-1.22 of pitch) nor .X
# closed it against the post's 0.79 of screw clearance, and the #833 direct
# pitch never landed.  #917 transfers the pair from MHA-016 at assembly
# instead, so it always fits whatever the post's own pitch.
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
    # The mouth angle is authored at a whole degree and prints as one (the
    # title block's flat +/-1 deg); NotchW carries its end-mill band natively
    # (NOTCH_W_BAND); the cap centre stays .XX -- at .X the stud-in-cap stack
    # fails (below).
    "LockNotchProfile": {"NotchMouthAngle": 0, "NotchW": 2},
    "LockNotchCapEProfile": {"CapECx": 2, "CapECz": 2},
    # The slot ends are .XX so the +/-2.75 fit-up travel keeps >= +/-2.24
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


# --- Lock notch: the cone-lock-knob stud in the notch -----------------------
# The notch is cut in one pass by an end mill of its width, so the width
# carries the tip slots' one-sided band: the cutter makes the size.  At the
# title block's .XX (+/-0.51) the narrowest notch (7.49) left the stud 0.552
# of radial room against 0.721 of cap-centre error: the stack failed as
# printed until 63fb3bd2d (Main, MHA-091 round 6).
NOTCH_W = 8.0
NOTCH_W_BAND = (0.10, 0.0)
# #917 S1 (plan A2): the closed end runs on this far past the engaged stud
# seat, along the cut.  The fit-up sets the engaged swing by T120 backlash,
# not against the cap, and may need the platform up to 1.11 deeper than the
# seat -- more than the stud's 0.825 of radial room in the full R alone.  The
# seat (build_cone_swing_platform.SLOT_E_X/Z) and the base stud do not move.
NOTCH_ENGAGE_OVERTRAVEL = 0.30
_NOTCH_W_LOWER, _NOTCH_W_UPPER = deviations(NOTCH_W_BAND)
NOTCH_W_MIN = NOTCH_W + _NOTCH_W_LOWER
# McMaster 91882A425 (the cone lock knob): a 1/4-20 stud, basic major 6.35;
# build_cone_swing_platform asserts it equals build_cone_lock_knob.STUD_DIA.
LOCK_STUD_MAJOR = 0.25 * 25.4
# The title block's flat angular band (its location bands are above).
TITLE_BLOCK_ANGLE_BAND_DEG = 1.0
# The notch's run is set on the print by its angle to the plate's WEST edge
# at the mouth -- both legs drawn, the vertex the real mouth corner, a
# protractor check (Main, MHA-091 round 6; the old angle ran from a hidden
# east-west construction ray).  The stud's own path is the chord tangent to
# its swing arc, 87.38 deg off that edge (the edge leans 6.53 deg off the
# plate axis, the chord 9.11 deg off east-west); build_cone_swing_platform
# derives it.  The angle is not critical (the channel keeps ~0.2 of slack,
# some 4.6 deg over the 2.78 exit travel), so the notch is authored at the
# whole degree and cut along it: the 0.38 deg offset joins the title block's
# band in the stud stack below.  #917 S1's wider north-west (WEST_HALF_N
# 11.0 -> 11.6, for the +/-2.5 tip slot and the block's 1.65 north travel)
# tilted the edge 0.15 deg, taking the chord from 87.53 to 87.38 deg: the
# whole degree went 88 -> 87.
NOTCH_MOUTH_ANGLE_DEG = 87.0


def notch_stud_stack(
    run_deg: float,
    exit_travel: float,
    run_radius: float,
    angle_offset_deg: float,
    edge_angle_error_deg: float,
) -> dict[str, float]:
    """The stud's worst case in the notch, from the notch's own geometry.

    The stud is fixed on the base; the notch must take it at the engaged
    seat (the closed end's full radius) and let it run out along the chord
    to the mouth.  Terms, all worst case: the cap centre off by its printed
    band on BOTH axes (CapECx, CapECz: radial at the seat, projected across
    the run in the channel); the cut's angle off the stud's chord -- the
    whole-degree rounding (``angle_offset_deg``), the title block's band, and
    the reference edge's own tilt within the outline's band
    (``edge_angle_error_deg``) -- over the exit travel; the chord's sagitta
    against the stud's true arc.  Room is the narrowest notch less the
    stud's major, a side.
    """
    band = TITLE_BLOCK_BAND_BY_PLACES[
        min(DRAWING_PRECISION_BY_NAME["CapECx"], DRAWING_PRECISION_BY_NAME["CapECz"])
    ]
    run = math.radians(run_deg)
    room = (NOTCH_W_MIN - LOCK_STUD_MAJOR) / 2.0
    seat_error = math.hypot(band, band)
    across_error = band * (abs(math.sin(run)) + abs(math.cos(run)))
    angle_error = exit_travel * math.tan(
        math.radians(
            abs(angle_offset_deg) + TITLE_BLOCK_ANGLE_BAND_DEG + abs(edge_angle_error_deg)
        )
    )
    sagitta = exit_travel**2 / (2.0 * run_radius)
    return {
        "location band": band,
        "room at the seat": room,
        "cap centre error at the seat": seat_error,
        "room in the channel": room - sagitta,
        "cap centre error across the run": across_error,
        "run angle error at the mouth": angle_error,
    }


def assert_notch_stud_stack(
    run_deg: float,
    exit_travel: float,
    run_radius: float,
    angle_offset_deg: float,
    edge_angle_error_deg: float,
) -> dict[str, float]:
    """Raise unless the stud seats and runs out at the printed bands.

    build_cone_swing_platform calls this at import with its notch geometry
    (this module cannot import the part back).  At .X the seat term alone
    is 1.13 against 0.825 -- why the cap centre stays .XX."""
    terms = notch_stud_stack(
        run_deg, exit_travel, run_radius, angle_offset_deg, edge_angle_error_deg
    )
    seat = terms["room at the seat"] - terms["cap centre error at the seat"]
    channel = terms["room in the channel"] - (
        terms["cap centre error across the run"] + terms["run angle error at the mouth"]
    )
    if seat < 0.0 or channel < 0.0:
        raise AssertionError(
            f"lock stud does not fit the notch (seat {seat:+.3f}, channel {channel:+.3f}): "
            + "; ".join(f"{name} {value:.3f}" for name, value in terms.items())
        )
    return terms


# View scales differ from the sheet scale and therefore remain property-linked
# labels.  The split plans are named so each dimension set has an unambiguous
# owner; these are view captions, not manufacturing notes.
PROFILE_VIEW_NOTE = "PLATE PROFILE — SCALE 1:2"
FEATURE_VIEW_NOTE = "HOLES — SCALE 1:2"
NOTCH_VIEW_NOTE = "LOCK NOTCH — SCALE 1:2"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:3"
