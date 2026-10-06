r"""Pure-data dimensional contract shared by the cone swing platform and drawing.

PURE DATA, no SolidWorks/COM imports: plate stock, holes, the tip-block
hold-down hole and the surface-finish controls.  The print-only data
(marked-dimension names, decimal places, view captions) lives in
``dt_cone_swing_platform_drawing_spec`` and
the plan outline in ``dt_cone_swing_platform_geometry``, so the harmonic base and
the drive train, which read this module and the geometry, do not re-key when
the print changes.
"""

from __future__ import annotations

import math

import _config
from _gtol_spec import PlanarFace
from _hole_spec import CLEARANCE_MM, HoleSpec, blind_cut_dia_mm
from _surface_finish import MACHINED_UM, SEAT_UM, SurfaceFinishControl

import dt_cone_pivot_post_spec
from dt_crank_drive_gear_spec import OUTSIDE_DIA as CRANK_GEAR_OUTSIDE_DIA

POST_ATTACHMENT_SPACING = dt_cone_pivot_post_spec.ATTACHMENT_SPACING
POST_BLOCK_DIA = dt_cone_pivot_post_spec.BLOCK_DIA
POST_CONE_BORE_HEIGHT = dt_cone_pivot_post_spec.BORE_HEIGHT


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
# The MHA-VN-031 post screws (MSC 40923898, 1/4-20 fillister, cut to fit, U37c)
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
# U37 (2026-09-23): the user accepted short engagement for MHA-VN-031 as a named
# exception to rule 12's 1.5D; the plate slides on the deck, so no boss can
# add thread.  Worst case: the thinnest stock plate (U41) less the cut-to-fit
# allowance and the break at both ends of the tap, counted as MHA-DT-032 counts
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
    raise AssertionError("MHA-VN-031 engagement fell below the audited 0.87D floor")
# The sheet states the shortfall as a plain fact, worded like MHA-DT-032's,
# over the break override it depends on: one line each.
# Named exception: MHA-VN-031 engagement (drawing-simplicity-policy.md, "Named exceptions").
POST_MOUNT_ENGAGEMENT_NOTE = (
    f"1/4-20 THREAD ENGAGEMENT {POST_MOUNT_ENGAGEMENT_PRINTED:.2f}D MIN (MHA-VN-031).\n"
    f"{POST_MOUNT_TAP_BREAK_NOTE}"
)

# Named exception: MHA-VN-031 engagement (drawing-simplicity-policy.md, "Named exceptions").
POST_MOUNT_ENGAGEMENT_ASSEMBLY_FACT = (
    f"ENGAGEMENT {POST_MOUNT_ENGAGEMENT_WORST:.2f} MIN "
    f"({POST_MOUNT_ENGAGEMENT_PRINTED:.2f}D)."
)


# User ruling 2026-09-29 (photo eight-views-4.png, lower right): the cone tip
# block is a plain prism standing straight on this plate, held by ONE #4-40
# socket head cap screw (MHA-VN-030, McMaster 91251A108) rising from under the
# plate into a blind tap in the block's bottom face.  The plate carries one
# counterbored close-clearance hole; the counterbore is on the UNDERSIDE, which
# slides on the base deck, so the head must sit below that face.
# Pivot bore centre to tip-block centre, cone_line.TIP_BLOCK_PIVOT_OFFSET
# (asserted equal by build_dt_drive_train_assembly).  Same frame and sign as the
# pivot-origin plate: -z runs south from the pivot along the cone axis.
HOLDDOWN_LOCAL_Z = -10.45
# 1.00 to -x of the cone-axis line, with the block's foot tap the same 1.00
# to -x of its adjuster axis (dt_cone_tip_block_spec.FOOT_TAP_OFFSET_X), so the
# block body still stands centred on the cone line.  The offset exists only
# so the hole's lateral station is a real dimension (HoldDownX): on the line
# it was a zero-valued placement, which a sketch can hold only as a relation,
# and so it printed at the .XX +/-0.51 the tip block's containment and
# lateral stacks cannot absorb (user ruling 2026-09-29: HoldDownX +/-0.10
# from the pivot bore).  -x (east) rather than +x because it leaves the larger
# webs on both parts: the hole's web to the narrow west edge grows from 6.3
# on the line to 7.3 (5.3 at +x), and the block's foot tap moves off its +X
# side, where the width's band sits, keeping a 5.98 least web (5.85 at +x).
HOLDDOWN_LOCAL_X = -1.0
# The explicit band on both printed stations from the pivot bore (HoldDownX,
# HoldDownZ): the block's lateral and axial stacks need +/-0.10 rather than
# the .XX +/-0.51.
HOLDDOWN_STATION_TOL_MM = 0.10
# The same stacks run through the post-mount taps, whose placement dimensions
# (PostMountWestX/WestZ/EastX/EastZ) carry this band instead of .XX.
POST_MOUNT_STATION_TOL_MM = 0.10
# McMaster 91251A108 product page (read 2026-09-29): #4-40 x 3/8 black-oxide
# alloy steel socket head screw, head 0.183 dia x 0.112 high.  Held here as
# numbers so this pure-data module never imports a SolidWorks builder;
# build_dt_drive_train_assembly asserts them equal to the MHA-VN-030 part.
HOLDDOWN_SCREW_HEAD_DIA = 0.183 * 25.4
HOLDDOWN_SCREW_HEAD_H = 0.112 * 25.4
_XX = float(str(_config.title_block("linear_2pl")["display"]).lstrip("±"))
_DRILL_OVERSIZE = float(_config.title_block("drilled_hole")["plus_mm"])
# #4 CLOSE clearance, drilled: the title block's DRILLED HOLES +0.10/0 row.
HOLDDOWN_CLEARANCE_DIA = CLEARANCE_MM[("#4", "close")]
HOLDDOWN_CBORE_DIA = 5.56  # .XX
HOLDDOWN_CBORE_DEPTH = 3.50  # .XX, from the underside
HOLDDOWN_HOLE_SPEC = HoleSpec(
    "counterbore_socket",
    "#4",
    overrides_mm={
        "HoleDiameter": HOLDDOWN_CLEARANCE_DIA,
        "CounterBoreDiameter": HOLDDOWN_CBORE_DIA,
        "CounterBoreDepth": HOLDDOWN_CBORE_DEPTH,
    },
)
# Print-worst checks (rule 12): .XX counterbore sizes, drilled-hole oversize,
# the stock plate's mill band.
HOLDDOWN_HEAD_RECESS = HOLDDOWN_CBORE_DEPTH - _XX - HOLDDOWN_SCREW_HEAD_H
HOLDDOWN_CBORE_HEAD_CLEARANCE = HOLDDOWN_CBORE_DIA - _XX - HOLDDOWN_SCREW_HEAD_DIA
HOLDDOWN_HEAD_BEARING = (
    HOLDDOWN_SCREW_HEAD_DIA - (HOLDDOWN_CLEARANCE_DIA + _DRILL_OVERSIZE)
) / 2.0
# Ledge from the counterbore floor to the top face, both bands.
HOLDDOWN_LEDGE_RANGE = (
    PLATE_THICKNESS - PLATE_STOCK_BAND - (HOLDDOWN_CBORE_DEPTH + _XX),
    PLATE_THICKNESS + PLATE_STOCK_BAND - (HOLDDOWN_CBORE_DEPTH - _XX),
)
if HOLDDOWN_HEAD_RECESS < 0.1:
    raise AssertionError("hold-down screw head can stand proud of the slide face")
if HOLDDOWN_CBORE_HEAD_CLEARANCE < 0.25:
    raise AssertionError("hold-down counterbore does not clear the screw head")
if HOLDDOWN_HEAD_BEARING < 0.5:
    raise AssertionError("hold-down screw head bears on under 0.5 mm per side")
if HOLDDOWN_LEDGE_RANGE[0] < 2.0:
    raise AssertionError("hold-down counterbore ledge is below the U27 2.0 target")
# The webs from this hole to the pivot bore/relief, the post taps and the plate
# outline are asserted in dt_cone_swing_platform_geometry, which owns the outline.


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
