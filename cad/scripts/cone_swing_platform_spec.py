r"""Pure-data dimensional contract shared by the cone swing platform and drawing.

PURE DATA, no SolidWorks/COM imports: plate stock, holes, the tip-screw slot
and the surface-finish controls.  The print-only data (marked-dimension names,
decimal places, view captions) lives in ``cone_swing_platform_drawing_spec`` and
the plan outline in ``cone_swing_platform_geometry``, so the harmonic base and
the drive train, which read this module and the geometry, do not re-key when
the print changes.
"""

from __future__ import annotations

import math

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
# The sheet states the shortfall as a plain fact, worded like MHA-139's,
# over the break override it depends on: one line each.
# Named exception: MHA-142 engagement (drawing-simplicity-policy.md, "Named exceptions").
POST_MOUNT_ENGAGEMENT_NOTE = (
    f"1/4-20 THREAD ENGAGEMENT {POST_MOUNT_ENGAGEMENT_PRINTED:.2f}D MIN (MHA-142).\n"
    f"{POST_MOUNT_TAP_BREAK_NOTE}"
)


# U30 (2026-09-23): the cone tip block is held by one hidden #6-32 x 1/2
# BUTTON-head socket cap screw (McMaster 91255A148, black-oxide alloy steel;
# rule-12 audit W22, Main 2026-09-23: the low head leaves a 2.9 ledge where a
# socket head's 4.2 counterbore left 1.51) coming up from under the plate
# through a lateral slot; a counterbored slot sinks the head below the slide
# face. The slot runs across the cone axis so the block can be shifted +/-2.25
# at fit-up; a shim pack under the foot sets its height. Both slots share the
# same two end centres, TIP_SCREW_HALF_TRAVEL either side of the cone axis, at
# the tip block's station (11.0 south of the pivot, from the drive-train
# layout: PIVOT_STATION = TIP_BLOCK_STATION + 11.0).
TIP_SCREW_LOCAL_Z = -11.0
TIP_SCREW_HALF_TRAVEL = 2.0
TIP_SCREW_MAJOR = 3.505  # #6-32 basic major
# McMaster 91255A148 lists one head size, 0.262 dia x 0.073 high, taken as the
# max; the B18.3 #6 button-head minimum diameter, 0.250, bounds the bearing.
TIP_SCREW_HEAD_DIA = (0.250 * 25.4, 0.262 * 25.4)
TIP_SCREW_HEAD_H_MAX = 0.073 * 25.4
# The slot widths are cut in one pass by an end mill of that size, so they
# carry the same one-sided +0.10/0 band as the title block's DRILLED HOLES
# row: the cutter makes the size, the machinist holds nothing tight.
TIP_SLOT_W = 4.0
TIP_CBORE_W = 7.94  # a 5/16 end mill
TIP_SLOT_W_BAND = (0.0, 0.10)
TIP_CBORE_DEPTH = 2.8  # .XX
_XX = 0.51
TIP_SLOT_SCREW_CLEARANCE = TIP_SLOT_W - TIP_SCREW_MAJOR
TIP_SLOT_HEAD_BEARING = (
    TIP_SCREW_HEAD_DIA[0] - (TIP_SLOT_W + TIP_SLOT_W_BAND[1])
) / 2.0
TIP_CBORE_HEAD_CLEARANCE = TIP_CBORE_W - TIP_SCREW_HEAD_DIA[1]
TIP_HEAD_RECESS = TIP_CBORE_DEPTH - _XX - TIP_SCREW_HEAD_H_MAX
# Ledge under the head: the stock plate less the .XX counterbore depth, both
# bands (rule-12 audit W22: the first cut left out the plate's band).
TIP_LEDGE_RANGE = (
    PLATE_THICKNESS - PLATE_STOCK_BAND - TIP_CBORE_DEPTH - _XX,
    PLATE_THICKNESS + PLATE_STOCK_BAND - TIP_CBORE_DEPTH + _XX,
)
if TIP_SLOT_SCREW_CLEARANCE < 0.25:
    raise AssertionError("tip-block screw slot does not clear the #6-32 major")
if TIP_SLOT_HEAD_BEARING < 0.5:
    raise AssertionError("tip-block screw head bears on under 0.5 mm per side")
if TIP_CBORE_HEAD_CLEARANCE < 0.25:
    raise AssertionError("tip-block counterbore slot does not clear the screw head")
if TIP_HEAD_RECESS < 0.1:
    raise AssertionError("tip-block screw head can stand proud of the slide face")
if TIP_LEDGE_RANGE[0] < 2.0:
    raise AssertionError("tip-block counterbore ledge is below the U27 2.0 target")


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
