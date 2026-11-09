r"""Pure-data dimensional contract shared by the cone swing platform and drawing.

PURE DATA, no SolidWorks/COM imports: plate stock, holes, the tip-block
hold-down hole and the surface-finish controls.  The print-only data
(marked-dimension names, decimal places, view captions) lives in
``dt_cone_swing_platform_drawing_spec`` and
the plan outline in ``dt_cone_swing_platform_geometry``, so the harmonic base and
the drive train, which read this module and the geometry, do not re-key when
the print changes.

The engaged swing angle is set at assembly (tightest cone against a
feeler/backlash, then lock the cone-lock-knob); the swing stop screw only
limits the disengaged swing.
"""

from __future__ import annotations

import math

import _config
from _fit_deviations import deviations
from _fit_ream_h7 import REAM_H7
from _gtol_planar import PlanarFace
from _hole_spec import CLEARANCE_MM, THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import (
    angular_band_deg,
    drilled_oversize_mm,
    printed_band_mm,
    printed_deviations,
)
from _surface_finish import MACHINED_UM, SEAT_UM, SurfaceFinishControl
from _title_block_units import render_number

import _cone_axis_constants as cone_axis
import dt_cone_post_envelope as post_envelope
import dt_cone_tip_block_spec
import dt_vn_locating_pin_spec as locating_pin
import dt_cone_gear_shaft_spec as cone_shaft
import dt_cone_pivot_post_spec
import dt_crank_drive_gear_spec as gear64
import dt_post_mount_stack as post_mount
from cone_stack_end_play import CONE_FLOAT_NORTH
from gear_seat_fit import GEAR_SEAT_CLEARANCE

# The sheet unit the registry row declares (#290); every band below is read
# for it.
UNIT = drawing_unit("parts/dt-cone-swing-platform", _config.parts("dt-cone-swing-platform"))

POST_ATTACHMENT_SPACING = dt_cone_pivot_post_spec.ATTACHMENT_SPACING
POST_BLOCK_DIA = post_envelope.BLOCK_DIA
POST_CONE_BORE_HEIGHT = dt_cone_pivot_post_spec.BORE_HEIGHT


PLATE_THICKNESS = cone_axis.PLATFORM_THICKNESS_MM
# User ruling U41 (2026-09-23): the thickness is the stock's, printed as a
# reference "(.25)" with "1/4 PLATE AS SUPPLIED" -- no machined thickness
# band.  drawing-guidelines.md rule 19 (absorb stacks at fit-up, not with tighter bands) stacks through the plate use the stock's mill tolerance.
PLATE_STOCK_BAND = 0.127  # +/-.005
# Two lines: on one, the text hung 49.5 mm left of section A-A into the
# notch plan's 7.0 and 205.81 (81788ce9 render).  Broken after "AS" so the
# last line, beside the dimension's top arrowhead, is the short one and sits
# back from it (aa9766da: "AS SUPPLIED" ran its D into the arrow).
PLATE_STOCK_CALLOUT = "1/4 PLATE AS\nSUPPLIED"
# The top relief is .42 wide, round-ended about the pivot and OPEN through
# the north edge (drawing-guidelines.md rule 17 (walls and webs) W18, Main 2026-09-23, option (d)): as a closed
# spotface 7.0 mm from that edge it left a 1.75 mm web.  The width keeps the
# stock 3/8 head's radial clearance (BDT reads it as the relief diameter):
# .41, the nearer .XX, would not.
PIVOT_BEARING_RELIEF_DIAMETER = 10.668  # .42
# A reference nominal (the finished matched fit governs) the pivot screw's
# 0.25 mm axial plate clearance is booked on; it prints (.010).
PIVOT_BEARING_RELIEF_DEPTH = 0.25
PIVOT_HEAD_RADIAL_CLEARANCE = 0.4875
PIVOT_BEARING_THICKNESS = PLATE_THICKNESS - PIVOT_BEARING_RELIEF_DEPTH
# User decision relayed by Main, 2026-09-22: fit the actual purchased shoulder
# and finished plate; do not invent a numerical axial-clearance band.  The
# sheet flags this on a leader to the relief in section A-A, names the mate
# by part number, and states an acceptance a machinist can check by hand
# (machinist review r1: unflagged under section C-C, "MINIMAL AXIAL PLAY"
# uncheckable).  Four lines (the layout audit's tall-block limit; r3's six
# gated) of at most 23 characters: the note stands between the 213.56
# dimension line and the bore gap it leads into, and its leader (from the
# note's right end) must pass left of A-A's Ra 1.6 leader.  The plate is
# the part being fitted, so the mate is the one thing the depth fits to.
# r16: screw locking belongs to assembly installation, not plate acceptance.
PIVOT_RELIEF_FIT_REQUIREMENT = (
    "TOP RELIEF: FIT DEPTH\n"
    "TO MHA-DT-VN-52\n"
    "SHOULDER; SWINGS FREE,\n"
    "NO AXIAL SHAKE."
)


_DRILL_OVERSIZE = drilled_oversize_mm(unit=UNIT)
_XXX = printed_band_mm(3, unit=UNIT)

def crank_gear_platform_budget() -> dict[str, float]:
    """Full rotating 64T envelope above the unrelieved platform, in mm.

    Heights are measured from the seated post foot, so base elevation and
    common plate thickness cancel. Opposite local stock limits still spend
    twice the mill band. Mount-hole float and yaw translate/rotate in the
    plate plane and cannot reduce distance to this infinite-plane bound.
    The retained title-row-sized and relative-crank-FCF deductions are EXTRA
    conservative air reserves, not tolerances on the BASIC cone incline or
    independent whole-post pose. Boss length and collar width spend their
    actual general grades; north float and the far 64T face maximize overhang.
    """
    post = dt_cone_pivot_post_spec

    def upper(nominal: float, places: int, unit: str) -> float:
        return nominal + printed_deviations(nominal, places, unit=unit)[1]

    boss_half_max = upper(
        post.CONE_BOSS_LENGTH, post.DRAWING_PRECISION_BY_NAME["ConeBossLen"], post.UNIT
    ) / 2.0
    overhang = (
        upper(
            cone_shaft.COLLAR_THICKNESS,
            cone_shaft.DRAWING_PRECISION_BY_NAME["CollarWidth"],
            cone_shaft.UNIT,
        )
        + gear64.FACE_WIDTH
        + gear64.FACE_WIDTH_BAND[0]
        + CONE_FLOAT_NORTH
    )
    running = cone_shaft.JOURNAL_DIAMETRAL_CLEARANCE_MM[1]
    angular_air_reserve = math.radians(angular_band_deg(unit=post.UNIT))
    height = post.BORE_HEIGHT + sum(
        printed_deviations(
            post.BORE_HEIGHT, post.DRAWING_PRECISION_BY_NAME["JournalAxisY"], unit=post.UNIT
        )
    ) / 2.0
    tip_radius = (
        gear64.OUTSIDE_DIA
        + printed_deviations(
            gear64.OUTSIDE_DIA,
            gear64.DRAWING_PRECISION_BY_NAME["OutsideDia"],
            (-gear64.OUTSIDE_DIA_TOLERANCE_MM, gear64.OUTSIDE_DIA_TOLERANCE_MM),
            unit=gear64.UNIT,
        )[1]
    ) / 2.0
    return {
        "printed journal height": height,
        "journal height lower band": -post.JOURNAL_AXIS_HEIGHT_TOLERANCE_MM,
        "printed maximum tip radius": -tip_radius,
        "gear seat eccentricity": -GEAR_SEAT_CLEARANCE[1] / 2.0,
        "shaft running float and tilt": -(
            running / 2.0
            + running / cone_shaft.JOURNAL_SUPPORT_SPAN_MIN_MM * overhang
        ),
        "relative-crank FCF air reserve (not a cone-axis grade)": -(boss_half_max + overhang) * math.tan(
            math.radians(post.CRANK_BORE_ANGLE_LIMIT_DEG)
        ),
        "conservative angular air reserve (not a BASIC-angle grade)": -(
            (boss_half_max + overhang) * math.tan(angular_air_reserve)
            + height * (1.0 - math.cos(angular_air_reserve))
        ),
        "tooth cutting runout": -gear64.TOOTH_RUNOUT_TIR_MM / 2.0,
        "local platform stock variation": -2.0 * PLATE_STOCK_BAND,
    }


def crank_gear_platform_clearance() -> float:
    """Worst full-turn plate air; the tip cylinder overbounds every tooth."""
    return sum(crank_gear_platform_budget().values())


if crank_gear_platform_clearance() < 0.5:
    raise AssertionError("64T unrelieved platform air is below 0.5 mm at print/service worst")


# The post's 1/4-in fillister clearance bores mate to these platform threads.
# The pitch is imported from the post spec; the tapped-hole size is the
# counterpart required by that purchased screw family.
POST_MOUNT_SPEC = HoleSpec("tapped", "1/4-20")
POST_MOUNT_TAP_DIA = blind_cut_dia_mm(POST_MOUNT_SPEC)
# The MHA-DT-VN-61 post screws (MSC 40923906, 1/4-20 fillister, cut to fit, U37c)
# thread through the plate, flush to this much short of its underside.
POST_SCREW_CUT_TO_FIT_SHORT = post_mount.CUT_TO_FIT_SHORT_MM
POST_MOUNT_THREAD_DIA = 0.25 * 25.4
# The taps take the title block's edge break; rule 4 forbids tightening it to rescue thread (machinist review, Main 2026-11-01).
POST_MOUNT_TAP_EDGE_BREAK = post_mount.PLATE_TAP_EDGE_BREAK_MM  # title block .010 edge break
# U37 (2026-09-23): the user accepted short engagement for MHA-DT-VN-61 as a named
# exception to drawing-guidelines.md rule 18 (thread engagement)'s 1.5D; the plate slides on the deck, so no boss can
# add thread.  Worst case: the thinnest stock plate (U41) less the tap's entry
# break at the top and, at the underside, whichever reaches further: the tap's
# exit break, or the cut-to-fit allowance plus the screw's own cut-end break.
# A MIN never rounds up, so the print floors to two places.
POST_MOUNT_ENGAGEMENT_WORST = round(
    PLATE_THICKNESS
    - PLATE_STOCK_BAND
    - POST_MOUNT_TAP_EDGE_BREAK
    - max(
        POST_MOUNT_TAP_EDGE_BREAK,
        POST_SCREW_CUT_TO_FIT_SHORT + post_mount.SCREW_CUT_END_BREAK_MM,
    ),
    6,
)
POST_MOUNT_ENGAGEMENT_WORST_DIAMETERS = (
    POST_MOUNT_ENGAGEMENT_WORST / POST_MOUNT_THREAD_DIA
)
POST_MOUNT_ENGAGEMENT_PRINTED = (
    math.floor(POST_MOUNT_ENGAGEMENT_WORST_DIAMETERS * 100.0) / 100.0
)
# The drawing-guidelines.md rule 18 (thread engagement) audit's E7 floor (0.87D, at the old .XX plate band): the stock
# band must not print below it without a new ruling.
if POST_MOUNT_ENGAGEMENT_PRINTED < 0.87:
    raise AssertionError("MHA-DT-VN-61 engagement fell below the audited 0.87D floor")
# The sheet states the shortfall as a plain fact, worded like MHA-DT-32's.
# The taps' callout names the post they mount, so the line names no screw
# (machinist review r1). Owner-accepted 2026-11-01: MHA-DT-VN-61's RV-01.
POST_MOUNT_ENGAGEMENT_NOTE = (
    f"1/4-20 THREAD ENGAGEMENT {POST_MOUNT_ENGAGEMENT_PRINTED:.2f}D MIN."
)

# Owner-accepted 2026-11-01 (MHA-DT-VN-61's RV-01).  A MIN never rounds up:
# the length floors to three inch places on MHA-DT-00's decimal-inch sheet.
_POST_MOUNT_ENGAGEMENT_FLOOR_IN = (
    math.floor(POST_MOUNT_ENGAGEMENT_WORST / 25.4 * 1000.0 + 1e-9) / 1000.0
)
POST_MOUNT_ENGAGEMENT_ASSEMBLY_FACT = (
    f"ENGAGEMENT {render_number(_POST_MOUNT_ENGAGEMENT_FLOOR_IN, 'in', 3)} MIN "
    f"({POST_MOUNT_ENGAGEMENT_PRINTED:.2f}D)."
)


# User ruling 2026-09-29 (photo eight-views-4.png, lower right): the cone tip
# block is a plain prism standing straight on this plate, held by ONE #4-40
# socket head cap screw (MHA-DT-VN-60, McMaster 91251A108) rising from under the
# plate into a blind tap in the block's bottom face.  The plate carries one
# counterbored close-clearance hole; the counterbore is on the UNDERSIDE, which
# slides on the base deck, so the head must sit below that face.
# Pivot bore centre to tip-block centre, dt_cone_tip_block_spec.TIP_BLOCK_PIVOT_OFFSET
# (asserted equal by build_dt_drive_train_assembly).  Same frame and sign as the
# pivot-origin plate: -z runs south from the pivot along the cone axis.
HOLDDOWN_LOCAL_Z = -dt_cone_tip_block_spec.TIP_BLOCK_PIVOT_OFFSET
# .04 in to -x of the cone-axis line, with the block's foot tap the same .04
# to -x of its adjuster axis (dt_cone_tip_block_spec.FOOT_TAP_OFFSET_X), so the
# block body still stands centred on the cone line.  The offset exists only
# so the hole's lateral station is a real dimension (HoldDownX): on the line
# it was a zero-valued placement, which a sketch can hold only as a relation,
# and so it printed at the general .XX band the tip block's containment and
# lateral stacks cannot absorb (user ruling 2026-09-29: HoldDownX +/-0.10
# from the pivot bore, now +/-.004).  -x (east) rather than +x because it
# leaves the larger webs on both parts: the hole's web to the narrow west edge
# grows on that side, and the block's foot tap moves off its +X side, where
# the width's band sits.
HOLDDOWN_LOCAL_X = -1.016  # -.04
# The explicit band on both printed stations from the pivot bore (HoldDownX,
# HoldDownZ): the block's lateral and axial stacks need it rather than the
# general .XX grade.  The shop's +/-.005 drilled-hole row (delegated ruling
# 2026-11-07 (Main), no precedent; owner review #2144: was +/-.004 with a
# spot from MHA-DT-21; a sheet cannot print an imported banded station as
# REF, so the band went to the row).  build_dt_drive_train_assembly proves
# the pivot-head air, the tip lateral take-up, the end screw's embed window
# (C1 keyed, 2026-11-09) and the hold-down webs at +/-.005, with the post
# taps also at +/-.005.
HOLDDOWN_STATION_TOL_MM = 0.127  # +/-.005
# The same stacks run through the post-mount taps, whose placement dimensions
# (PostMountWestX/WestZ/EastX/EastZ) carry this band instead of the grade:
# the shop's +/-.005 drilled-hole row. Owner ruling 2026-11-08 (Pedro), #2144 item 9.1
# (was +/-.004; the end screw's embed, tip lateral
# take-up and the hold-down webs still close at +/-.005).
POST_MOUNT_STATION_TOL_MM = 0.127  # +/-.005
# McMaster 91251A108 product page (read 2026-09-29): #4-40 x 3/8 black-oxide
# alloy steel socket head screw, head 0.183 dia x 0.112 high.  Held here as
# numbers so this pure-data module never imports a SolidWorks builder;
# build_dt_drive_train_assembly asserts them equal to the MHA-DT-VN-60 part.
HOLDDOWN_SCREW_HEAD_DIA = 0.183 * 25.4
HOLDDOWN_SCREW_HEAD_H = 0.112 * 25.4
# #4 CLOSE clearance, drilled: the title block's DRILLED HOLES row.
HOLDDOWN_CLEARANCE_DIA = CLEARANCE_MM[("#4", "close")]
# The counterbore's sizes print three places on its Hole Wizard callout.
HOLDDOWN_CBORE_DIA = 5.5626  # .219
HOLDDOWN_CBORE_DEPTH = 3.5052  # .138, from the underside
HOLDDOWN_HOLE_SPEC = HoleSpec(
    "counterbore_socket",
    "#4",
    overrides_mm={
        "HoleDiameter": HOLDDOWN_CLEARANCE_DIA,
        "CounterBoreDiameter": HOLDDOWN_CBORE_DIA,
        "CounterBoreDepth": HOLDDOWN_CBORE_DEPTH,
    },
)
# Print-worst checks (drawing-guidelines.md rule 17 (walls and webs)): .XXX counterbore sizes, drilled-hole oversize,
# the stock plate's mill band.
HOLDDOWN_HEAD_RECESS = HOLDDOWN_CBORE_DEPTH - _XXX - HOLDDOWN_SCREW_HEAD_H
HOLDDOWN_CBORE_HEAD_CLEARANCE = HOLDDOWN_CBORE_DIA - _XXX - HOLDDOWN_SCREW_HEAD_DIA
HOLDDOWN_HEAD_BEARING = (
    HOLDDOWN_SCREW_HEAD_DIA - (HOLDDOWN_CLEARANCE_DIA + _DRILL_OVERSIZE)
) / 2.0
# Ledge from the counterbore floor to the top face, both bands.
HOLDDOWN_LEDGE_RANGE = (
    PLATE_THICKNESS - PLATE_STOCK_BAND - (HOLDDOWN_CBORE_DEPTH + _XXX),
    PLATE_THICKNESS + PLATE_STOCK_BAND - (HOLDDOWN_CBORE_DEPTH - _XXX),
)
if HOLDDOWN_HEAD_RECESS < 0.1:
    raise AssertionError("hold-down screw head can stand proud of the slide face")
if HOLDDOWN_CBORE_HEAD_CLEARANCE < 0.25:
    raise AssertionError("hold-down counterbore does not clear the screw head")
if HOLDDOWN_HEAD_BEARING < 0.5:
    raise AssertionError("hold-down screw head bears on under 0.5 mm per side")
if HOLDDOWN_LEDGE_RANGE[0] < WALL_TARGET_MM:
    raise AssertionError("hold-down counterbore ledge is below the .080 in wall target")
# The webs from this hole to the pivot bore/relief, the post taps and the plate
# outline are asserted in dt_cone_swing_platform_geometry, which owns the outline.


# --- tip-block locating dowel -------------------------------------------------
# Rule-23 retention, owner ruling 2026-11-07 (MHA-DT-00 rubric sample, PR
# #2248).  The one hold-down screw lets the adjuster's thrust turn
# the block on the plate, so a 1/16 x 3/8 dowel (MHA-DT-VN-69) locates it:
# pressed into a blind ream in the block's foot, it slips through this plate.
# At MHA-DT-00 step post-and-tip-block, with the block squared and snug, the
# fitter drills and reams up through this plate into the foot to the pin's
# press size (dt_cone_tip_block_spec.DOWEL_HOLE_*), opens this hole to the
# slip size below from underneath with the block still on, then presses the
# pin up through it to the foot's hole floor.
#
# On the hold-down line (the block's mid-depth), TIP_DOWEL_FROM_HOLDDOWN
# toward +x (machine west) of the hold-down hole: the block's own c-c from its
# foot tap, since the screw is that tap's axis.  Same plate-local frame as
# HOLDDOWN_LOCAL_X/Z.  The station prints from the hold-down hole with its
# own +/-.004 band, tighter than the hole's +/-.005 drilled row
# (HOLDDOWN_STATION_TOL_MM), which the webs to the counterbore here and to
# the block's +X face need (neither the general .XXX band nor the drilled
# row closes them at the .080 wall target).
#
# Why the controlling station stays chained to the hold-down hole, with the
# pivot-bore axis station printed only as a REF (machinist review of round
# 6, #6; delegated ruling 2026-11-07, option A): the two webs that close on
# the dowel-to-hold-down distance have almost no margin.  At print-worst
# with the chained +/-.004, the plate's web to the Ø.219 hold-down
# counterbore clears the .080 wall target by +.0003 in, and MHA-DT-21's web
# from the foot ream to its +X face by +.0008 in (the foot's hole lands
# within this band plus the screw's .006 float, .010, from its tap).
# Located from the pivot at +/-.004 instead, with HoldDownX also +/-.004 from
# the pivot, the dowel-to-hold-down distance takes both bands (+/-.008): the
# counterbore web falls to -.0037 in, and the foot's landing band grows to
# .014, its +X face web to about -.0032 in.  No DOWEL_FROM_TAP closes both
# (the window is short by about .007 in), so the pivot-axis station prints
# as a reference, TIP_DOWEL_LOCAL_X, and the chained station controls.
TIP_DOWEL_FROM_HOLDDOWN = dt_cone_tip_block_spec.DOWEL_FROM_TAP  # .228
TIP_DOWEL_LOCAL_X = HOLDDOWN_LOCAL_X + TIP_DOWEL_FROM_HOLDDOWN  # .188 REF
TIP_DOWEL_LOCAL_Z = HOLDDOWN_LOCAL_Z
TIP_DOWEL_STATION_TOL_MM = 0.1016  # +/-.004
# Slip fit over the pin, reamed: .0630 REAM_H7 (.0630/.0635) over the pin's
# .0626/.0628 (dt_vn_locating_pin_spec.DIA_BAND_IN).
TIP_DOWEL_HOLE_DIA = 0.0630 * 25.4  # 1.6002
TIP_DOWEL_HOLE_BAND = REAM_H7  # +.0005/-.0000
_tip_dowel_lower, _tip_dowel_upper = deviations(TIP_DOWEL_HOLE_BAND)
TIP_DOWEL_HOLE_LIMITS = (
    TIP_DOWEL_HOLE_DIA + _tip_dowel_lower,
    TIP_DOWEL_HOLE_DIA + _tip_dowel_upper,
)
_pin_dia_limits = tuple(
    locating_pin.DIA + band * locating_pin.MM_PER_IN for band in locating_pin.DIA_BAND_IN
)
TIP_DOWEL_SLIP_CLEARANCE_MM = (
    TIP_DOWEL_HOLE_LIMITS[0] - max(_pin_dia_limits),
    TIP_DOWEL_HOLE_LIMITS[1] - min(_pin_dia_limits),
)  # (.0002, .0009) in
if TIP_DOWEL_SLIP_CLEARANCE_MM[0] <= 0.0:
    raise AssertionError("the plate's dowel ream grips MHA-DT-VN-69 at its extremes")
if TIP_DOWEL_HOLE_LIMITS[0] <= dt_cone_tip_block_spec.DOWEL_HOLE_LIMITS[1]:
    raise AssertionError("the plate's slip ream does not open the foot's press ream")
# The pin's lower end above this plate's underside (its range never proud of
# the sliding underside): the block's press depth owns them, and its copy of
# this plate's mill band must agree.
TIP_DOWEL_END_ABOVE_UNDERSIDE = dt_cone_tip_block_spec.DOWEL_END_ABOVE_UNDERSIDE
TIP_DOWEL_END_ABOVE_UNDERSIDE_RANGE_MM = (
    dt_cone_tip_block_spec.DOWEL_END_ABOVE_UNDERSIDE_RANGE_MM
)
if dt_cone_tip_block_spec.PLATE_STOCK_BAND_MM != PLATE_STOCK_BAND:
    raise AssertionError("MHA-DT-21's copy of the plate's mill band drifted")
# The foot's hole is drilled from this one with the block on its screw, so
# it lands from the foot tap within this hole's station band plus the
# screw's float in its close-clearance hole: MHA-DT-21 prints that sum.
TIP_HOLDDOWN_SCREW_FLOAT_MM = (
    HOLDDOWN_CLEARANCE_DIA
    + _DRILL_OVERSIZE
    - THREAD_MAJOR_MM[dt_cone_tip_block_spec.HOLDDOWN_THREAD]
) / 2.0
if (
    TIP_DOWEL_STATION_TOL_MM + TIP_HOLDDOWN_SCREW_FLOAT_MM
    > dt_cone_tip_block_spec.DOWEL_X_TOL_MM + 1e-9
):
    raise AssertionError(
        "MHA-DT-21's dowel station band does not cover this plate's station "
        "band and the hold-down screw's float"
    )
# Its webs to the hold-down counterbore, the pivot relief/bore and the
# outline are asserted in dt_cone_swing_platform_checks with the hold-down's.


# Only functional sliding/locating surfaces carry roughness.  The existing
# close-clearance pivot hole needs no bearing-finish control; the top locates
# the post and tip block, and the underside slides on the harmonic-base deck.
# The slide face's symbol says why it carries Ra 1.6 (machinist review r7:
# nothing on the sheet said the underside runs, so the finish read as meant
# for the bore), as fr_harmonic_base and dt_pinion_cam name their targets.
BASE_SLIDE_FINISH_TARGET = "SLIDING FACE"
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "post_seat", SEAT_UM, PlanarFace((0, 1, 0), PLATE_THICKNESS), display_unit=UNIT
    ),
    SurfaceFinishControl(
        "base_slide",
        MACHINED_UM,
        PlanarFace((0, -1, 0), 0.0),
        production_method=BASE_SLIDE_FINISH_TARGET,
        display_unit=UNIT,
    ),
)
