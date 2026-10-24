r"""Knife-mount dimensional contract -- the single source of truth shared by the
part build (``build_sm_knife_mount.py``) and its manufacturing drawing
(``draw_sm_knife_mount.py``).

PURE DATA, no SolidWorks/COM imports.  Nothing else consumes this part's
nominals (no assembly imports ``build_sm_knife_mount``), so one ``_spec`` module is
right here.  The block/bore geometry is derived in the build from the summing-
assembly layout; the fixed values are mirrored here for the drawing's view math,
and the offline lockstep test asserts the part marks and the drawing keeps
EXACTLY ``DRAWING_DIMENSIONS``.

NOTE on the "knife edge": this hardened-steel BEARING BLOCK (ch18 p.42,
2026-09-02 user re-read: unpainted heat-treated steel, not brass) carries a
circular bore CLOSE around the mating hex trunnion (Ø12 over the 8.080 x 10.268
hex), so only the trunnion's TOP VERTEX LINE nears the bore's upper inner wall
-- the true knife-edge line contact.  The sharp ridge is on the LEVER trunnion
(``build_sm_summing_lever``), NOT on this part; this part's critical surface is the
bore's upper inner wall, the knife SEAT: it carries ``MACHINED_UM`` (1.6, policy
drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates) -- ``GROUND_UM`` 0.8 is reserved for knife edges and pivot-screw
shoulders).
"""

from __future__ import annotations

import math

import _config
import sm_vn_knife_mount_dowel_spec as DOWEL
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM, HoleSpec
from _printed_tolerance import angular_band_deg, drilled_oversize_mm
from _surface_finish import MACHINED_UM, SEAT_UM, SurfaceFinishControl
from sm_summing_lever_spec import HEX_H, HEX_W

# --- fixed geometry for the drawing's view math (mirrors build_sm_knife_mount) ----
R_BORE = 6.0  # Ø12 knife-bearing bore (2026-09-02 ch18 p.42 re-read: close bore)
# Block half-width, owned here (the build reads it): 25.4 across, the .X
# width that keeps the -X dowel's far-side web at 2.0 round the 15.264 span
# (PIN_HOLE_FAR_SIDE_WEB below; 25.319 is the least).
BLK_HALF_X = 12.7
SUPPORT_Z_THICK = 14.0  # axial depth straddling the trunnion mid
BLK_TOP = 14.87  # local block top (clamped to the top-frame casting underside)
BLK_BOT = -14.75  # local block bottom (BORE_CY - R_BORE - 3.0 wall)
BORE_CY = -5.75  # bore centre below the ridge origin (TopClear 0.25 - R_BORE)

# The knife bore's reamed seat, Ra 1.6; the top seat (datum A), which the
# screw clamps to the casting underside and the dowels key, Ra 3.2: a static
# mating face, nothing runs on it (SEAT_UM, drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates); 2026-10-10 ruling).
SURFACE_FINISHES = (
    SurfaceFinishControl("knife_bore", MACHINED_UM, CylinderFace(2.0 * R_BORE)),
    SurfaceFinishControl("top_seat", SEAT_UM, PlanarFace((0.0, 1.0, 0.0), BLK_TOP)),
)

# --- Knife-hanger screw tap and anti-rotation dowel holes (top seat) ---------
# General tolerances the printed places claim (title block, drawing-guidelines.md rule 3 (decimal places carry the tolerance)).
_X = float(str(_config.title_block("linear_1pl")["display"]).lstrip("\u00b1"))
_XX = float(str(_config.title_block("linear_2pl")["display"]).lstrip("\u00b1"))
_XXX = float(str(_config.title_block("linear_3pl")["display"]).lstrip("\u00b1"))
# The Ø12 bore is REAMED through (Ra 1.6 on its knife seat is a reamed
# finish, not a drilled one) to an explicit +0.03/0 band (the MHA-DT-16
# arbor-pedestal running-bore precedent, ``dt_arbor_pedestal_spec``): the
# rock budget takes the smallest bore, the webs the largest.
BORE_DIA_BAND = (0.03, 0.0)
BORE_DIA_PLACES = 2
BORE_R_MIN = R_BORE + min(BORE_DIA_BAND) / 2.0  # 6.000
BORE_R_MAX = R_BORE + max(BORE_DIA_BAND) / 2.0  # 6.015
# The band's mate, named on the bore's callout (drawing-guidelines.md rule
# 4): the summing lever's hex trunnion, whose top ridge rocks on the bore's
# crown, the knife seat.
LEVER_NUMBER = str(_config.parts("sm-summing-lever")["number"])
BORE_CALLOUT = "\n".join(("REAM THRU", "KNIFE SEAT FOR", f"{LEVER_NUMBER} TRUNNION"))
# The block's overall sizes print one place (.X, drawing-guidelines.md rule 17 (walls and webs): every web below
# holds at that band); the stacks judge the block at those limits.
BLOCK_SIZE_PLACES = 1
BLOCK_SIZE_TOL = _X  # 0.8
BLOCK_HEIGHT_PRINTED = round(BLK_TOP - BLK_BOT, BLOCK_SIZE_PLACES)  # 29.6
# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "knife-bore position": "0.20",
    "knife-bore perpendicularity": "0.05",
    "knife-hanger tap position": "0.15",
    "dowel hole pattern position": "0.13",
}
# The bore (drawing-guidelines.md rule 5 (avoid excessive GD&T), knife-edge system): ⌖Ø0.20 locates it to the top
# seat (datum A) and the dowel pattern (datum B); a stacked ⊥Ø0.05|B holds
# its axis square to the plane of the dowel axes.  That one Ø zone bounds
# both the yaw off the dowel line (the rock budget's far-end offset) and the
# tilt; a ∥ to A would bound the tilt only, in a two-plane zone, leaving the
# yaw free.
KNIFE_BORE_POSITION_TOL = float(GEOMETRIC_TOLERANCES_MM["knife-bore position"])
KNIFE_BORE_ORIENTATION_TOL = float(
    GEOMETRIC_TOLERANCES_MM["knife-bore perpendicularity"]
)
# The #10-24 tap's position to the top seat and the dowel pattern (A|B): the
# bolt axis the crossbar's #10 clearance hole must float round
# (``build_sm_summing_assembly``'s knife-hanger stack).  Its 0.075 zone radius
# is one term of HANGER_SCREW_MISMATCH (hypot(0.316, 0.264) = 0.412) inside
# the hole's 0.6095 radial float with the drill drift's 0.194 over the
# printed grip's thickest 37.01, 0.0039 spare.
# A screw through a clearance hole needs no tighter zone than that float
# admits (drawing-guidelines.md rule 5), and Ø0.15 is the largest two-place
# zone it admits: the float closes at Ø0.1556; Ø0.16 leaves -0.0031 and
# Ø0.25 -0.067.  Plain face dimensions instead, even at .XXX (+/-0.13 each
# way, not 0.075), give hypot(0.371, 0.319) = 0.489 and -0.074: the frame is
# functional.
STUD_TAP_POSITION_TOL = float(GEOMETRIC_TOLERANCES_MM["knife-hanger tap position"])


def free_rock_deg(
    far_end_offset: float,
    *,
    hex_w: float = HEX_W,
    hex_h: float = HEX_H,
    r_bore: float = R_BORE,
    shoulder_drop: float | None = None,
) -> float:
    """The summing lever's free rock, degrees, before a hex shoulder touches
    this bore, the bore axis ``far_end_offset`` off the ridge line across the
    block's depth (tolerance-gdt-assessment §5.4: the knife mount's bore is
    controlled to its mounting face and its key).

    The hex trunnion (``sm_summing_lever_spec`` HEX_W x HEX_H, vertex up)
    rocks about its top vertex on the bore crown; its upper shoulder sits at
    (hex_w/2, -shoulder_drop) from the ridge, ``shoulder_drop`` hex_h/4 on
    the nominal profile (a flank at its angle-band limit raises it).
    Conservatively the ridge bears at one end of the bore and the whole
    offset acts at the other, shifting the bore centre sideways by
    ``far_end_offset`` toward the shoulder's swing.  The rock is where that
    rotated shoulder reaches the bore wall (radius ``r_bore``); the keywords
    judge the trunnion and bore at a band limit.
    """
    drop = hex_h / 4.0 if shoulder_drop is None else shoulder_drop
    shoulder_r = math.hypot(hex_w / 2.0, drop)
    phi0 = math.atan2(-drop, hex_w / 2.0)

    def inside(phi: float) -> bool:
        x = shoulder_r * math.cos(phi) + far_end_offset
        y = shoulder_r * math.sin(phi) + r_bore
        return x * x + y * y < r_bore * r_bore

    if not inside(phi0):
        return 0.0
    low, high = phi0, phi0 + math.pi / 2.0
    for _ in range(80):
        mid = (low + high) / 2.0
        low, high = (mid, high) if inside(mid) else (low, mid)
    return math.degrees(low - phi0)


# Why Ø0.05 (2026-10-09 ruling): a yawed bore steals rock.  Free rock of the
# nominal 8.080 x 10.268 trunnion in the nominal Ø12 against the far-end
# offset t across the 14 deep bore: t 0 -> 8.92 deg, 0.05 -> 8.44, 0.10 ->
# 7.96, 0.18 -> 7.17.  The drawing-guidelines.md rule 17 (walls and webs) budget -- the trunnion's ridge-to-side and flank-to-side limits and
# the bore's .XX size at its band limit, t the ⊥Ø0.05 zone plus the dowel
# yaw across the deepest .X block -- is
# ``build_sm_summing_assembly.KNIFE_FREE_ROCK_WORST_DEG`` (>= 5.0, 6.64 in
# the reamed bore), which owns the
# crossbar's slip terms.  The top seat clamps to the frame's faced Ra 3.2
# underside plane (MHA-FR-02, user ruling 2026-10-12), so no bedding term
# enters: seat form tilts the block, it cannot yaw the bore off the dowel
# line.
KNIFE_FREE_ROCK_DEG = free_rock_deg(0.0)
# The bore crown (its upper inner wall) below the top seat: 14.62.
BORE_CROWN_DEPTH = BLK_TOP - (BORE_CY + R_BORE)
# MHA-SM-VN-52, a #10-24 plain hex bolt cut from stock at MHA-SM-00 to its
# hole's measured stack plus the 8.92 +/-0.15 fit-up reach
# (``sm_summing_assembly_spec.HANGER_FIT_REACH``), drops through a washer on
# the crossbar's faced top and its #10 clearance hole and threads into a
# bottoming tap on the bore's vertical centreline at mid-depth.  The full
# thread's shallowest limit, 9.52, must take the bolt's longest reach, 9.07
# (``build_sm_summing_assembly.HANGER_TIP_CLEARANCE``), and hold 1.5 D of
# full thread (below).  It prints 9.65 with an explicit native +/-0.13 on the
# hole callout: the band the earlier 9.650 took from the title block's .XXX
# row, held unchanged.  Bare, two places would claim the .XX row's +/-0.51
# (drawing-guidelines.md rule 3 (decimal places carry the tolerance)), a
# 10.16 deepest thread the drill's shallowest limit, 11.19, would clear by
# only 1.03, under one pitch of runout; the band's mate and function are the
# callout's reason row (rule 4).  The drill runs 1.5 P
# past that nominal thread (9.65 + 1.5875 = 11.2375, printed 11.24), yet its
# deepest limit, with the pilot the web charges ground to the sharpest
# accepted point (below), must still leave the 2.0 crown web: so the drill
# prints 11.24 with an explicit +/-0.05 band on the sheet's hole callout (the
# MHA-SM-03 bracket-tap precedent).  Both depths print at two places.
STUD_THREAD = "#10-24"
STUD_TAP_DRILL_DEPTH = 11.24
STUD_TAP_DRILL_DEPTH_PLACES = 2
STUD_TAP_DRILL_DEPTH_BAND = 0.05  # explicit, functional (above)
STUD_TAP_THREAD_DEPTH = 9.65
STUD_TAP_THREAD_DEPTH_PLACES = 2
STUD_TAP_THREAD_DEPTH_BAND = _XXX  # explicit, native: the 9.650's .XXX, kept
STUD_TAP_SPEC = HoleSpec(
    "tapped_bottoming",
    STUD_THREAD,
    end="blind",
    depth_mm=STUD_TAP_DRILL_DEPTH,
    overrides_mm={"ThreadDepth": STUD_TAP_THREAD_DEPTH},
)
STUD_TAP_DIA = TAP_DRILL_MM[STUD_THREAD]  # #25 drill, 3.797
# The callout names the pilot by its drill, #25 (0.1495 in, the #10-24 tap
# drill the Hole Wizard cuts), not by a printed Ø: at three places Ø3.797
# claims a precision the drill does not hold, and at two places Ø3.80 under
# the DRILLED HOLES row would reject the #25 drill itself.  The drawing reads
# the Hole Wizard's native drill Ø back against the #25 before it writes the
# designation in its place (draw_sm_knife_mount._prove_tap_drill).
STUD_TAP_DRILL = "#25"
STUD_TAP_DRILL_IN = 0.1495
if round(STUD_TAP_DRILL_IN * DOWEL.MM_PER_IN, 3) != STUD_TAP_DIA:
    raise AssertionError(
        f"the {STUD_TAP_DRILL} drill is not the {STUD_THREAD} tap drill Ø{STUD_TAP_DIA}"
    )
# The pilot the shop may drill.  A named drill with no band of its own is
# toleranced by the title block's DRILLED HOLES row, +0.10/0, on the drill's
# size (drawing-guidelines.md rule 3 (decimal places carry the tolerance);
# rule 2 (the title block is the general specification): no callout restates
# it).  This constant is that row, indexed for the limits, not printed.  The
# row reads on the #25's true size, 0.1495 in = 3.7973, not the rounded
# 3.797 the wizard table carries: the pilot accepted is Ø3.7973-3.8973.
STUD_TAP_DRILL_DIA = STUD_TAP_DRILL_IN * DOWEL.MM_PER_IN  # 3.7973
STUD_TAP_DIA_BAND = (drilled_oversize_mm(), 0.0)  # (upper, lower), title block
STUD_TAP_DIA_ACCEPTED = (
    STUD_TAP_DRILL_DIA + min(STUD_TAP_DIA_BAND),
    STUD_TAP_DRILL_DIA + max(STUD_TAP_DIA_BAND),
)  # (3.7973, 3.8973)
# CHARGED, NOT ACCEPTED: the crown web below charges a wider pilot than the
# sheet accepts, Ø3.927 -- the wizard's Ø3.797 plus the larger of the
# DRILLED HOLES plus and the general .XXX (+/-0.13) -- a conservative
# envelope 0.0297 over the accepted Ø3.8973 that keeps the web and every
# stack built on it where they stood.  No pilot is drilled, inspected or
# passed to it.
STUD_TAP_DIA_MAX = STUD_TAP_DIA + max(max(STUD_TAP_DIA_BAND), _XXX)  # 3.927
if STUD_TAP_DIA_MAX < max(STUD_TAP_DIA_ACCEPTED):
    raise AssertionError(
        f"knife-mount crown web charges Ø{STUD_TAP_DIA_MAX:.3f}, under the"
        f" accepted pilot Ø{max(STUD_TAP_DIA_ACCEPTED):.3f}"
    )
STUD_TAP_DIA_OVERSIZE = STUD_TAP_DIA_MAX - STUD_TAP_DIA  # 0.13, charged
# The drill's point.  The Hole Wizard cuts a 118 deg point (``_holes``' blind
# drill angle, 2.0594885 rad), but a ground twist-drill point is not exact
# and an undimensioned point takes no band from the title block.  So the
# callout's drill row states the point natively -- SolidWorks' drill-angle
# variable reading the feature, ``X 118°`` -- with no band of its own: the
# title block's general angular +/-1 deg governs that printed angle.  The
# crown web charges the sharpest accepted point, 117 deg, whose cone over the
# charged pilot stands tallest.
STUD_TAP_POINT_ANGLE_DEG = 118.0
STUD_TAP_POINT_ANGLE_PLACES = 0
STUD_TAP_POINT_ANGLE_TOL_DEG = angular_band_deg()  # 1.0
STUD_TAP_POINT_ANGLE_MIN_DEG = STUD_TAP_POINT_ANGLE_DEG - STUD_TAP_POINT_ANGLE_TOL_DEG
STUD_THREAD_MAJOR = THREAD_MAJOR_MM[STUD_THREAD]  # 4.826
STUD_PITCH = DOWEL.MM_PER_IN / int(STUD_THREAD.rsplit("-", 1)[1])  # 1.058
STUD_TAP_RUNOUT = STUD_TAP_DRILL_DEPTH - STUD_TAP_THREAD_DEPTH
if STUD_TAP_RUNOUT < 1.5 * STUD_PITCH:
    raise AssertionError(
        f"knife-mount tap drill runs {STUD_TAP_RUNOUT:.3f} past the thread,"
        f" under 1.5 P ({1.5 * STUD_PITCH:.3f})"
    )
# At the bands' adverse limits the drill still runs past the deepest full
# thread by at least one pitch, the bottoming tap's lead: 11.19 - 9.78 = 1.41.
STUD_TAP_RUNOUT_MIN = (STUD_TAP_DRILL_DEPTH - STUD_TAP_DRILL_DEPTH_BAND) - (
    STUD_TAP_THREAD_DEPTH + STUD_TAP_THREAD_DEPTH_BAND
)
if STUD_TAP_RUNOUT_MIN < STUD_PITCH:
    raise AssertionError(
        f"knife-mount tap drill runs {STUD_TAP_RUNOUT_MIN:.3f} past the thread at"
        f" worst case, under one pitch ({STUD_PITCH:.3f})"
    )


def drill_point_height(drill_dia: float, point_angle_deg: float) -> float:
    """The cone a ``drill_dia`` drill ground to ``point_angle_deg`` included
    leaves past its full-diameter depth."""
    return drill_dia / 2.0 / math.tan(math.radians(point_angle_deg / 2.0))


# The metal the tap's drill point leaves over the bore crown, every band at
# its worst (the drill depth's band, the charged pilot envelope at its
# sharpest accepted point, the largest reamed bore, the bore's position zone
# KNIFE_BORE_POSITION_TOL): 14.62 - 0.10 - 0.015 - 11.29 - 1.2032 = 2.0118
# (2.0078 at the build's unrounded 14.866 top).
STUD_TAP_WEB_MIN = 2.0
STUD_TAP_POINT_H = drill_point_height(
    STUD_TAP_DIA_MAX, STUD_TAP_POINT_ANGLE_MIN_DEG
)  # 1.2032
STUD_TAP_DRILL_DEPTH_MAX = STUD_TAP_DRILL_DEPTH + STUD_TAP_DRILL_DEPTH_BAND  # 11.29
BORE_CROWN_DEPTH_MIN = (
    BORE_CROWN_DEPTH - KNIFE_BORE_POSITION_TOL / 2.0 - max(BORE_DIA_BAND) / 2.0
)


def tap_web_worst(
    blk_top: float,
    drill_depth: float,
    tap_drill_dia: float,
    *,
    drill_band: float = STUD_TAP_DRILL_DEPTH_BAND,
    bore_oversize: float = max(BORE_DIA_BAND),
    drill_dia_oversize: float = STUD_TAP_DIA_OVERSIZE,
    point_angle_deg: float = STUD_TAP_POINT_ANGLE_MIN_DEG,
) -> float:
    """Worst-case metal between a top-seat tap's drill point and the bore
    crown, the seat at local ``blk_top``: the deepest drill (its depth
    ``drill_band`` over), the charged pilot (``drill_dia_oversize`` over
    ``tap_drill_dia``, by default the envelope past the accepted band)
    ground to the sharpest point (``point_angle_deg`` included), the
    largest bore (``bore_oversize`` over its nominal Ø), the bore at the top
    of its position zone.  The build calls it with its derived (unrounded)
    top; the regression tests pass the retired 1/2-13 tap's .XX bands, and
    the nominal pilot at an exact 118 deg point an undercharged proof
    assumed."""
    crown_min = (
        blk_top
        - (BORE_CY + R_BORE)
        - KNIFE_BORE_POSITION_TOL / 2.0
        - bore_oversize / 2.0
    )
    return (
        crown_min
        - (drill_depth + drill_band)
        - drill_point_height(tap_drill_dia + drill_dia_oversize, point_angle_deg)
    )


STUD_TAP_WEB_WORST = tap_web_worst(BLK_TOP, STUD_TAP_DRILL_DEPTH, STUD_TAP_DIA)
if STUD_TAP_WEB_WORST < STUD_TAP_WEB_MIN:
    raise AssertionError(
        f"knife-mount tap point leaves {STUD_TAP_WEB_WORST:.3f} over the bore"
        f" crown at worst case, under {STUD_TAP_WEB_MIN}"
    )
# The full thread the bolt can use, at the shallowest printed thread depth.
STUD_TAP_THREAD_DEPTH_MIN = STUD_TAP_THREAD_DEPTH - STUD_TAP_THREAD_DEPTH_BAND  # 9.52
# Rule 12: that shallowest full thread holds 1.5 D of the bolt (7.239), so the
# tap never caps the engagement the knife-hanger stack charges.
STUD_TAP_ENGAGEMENT_MIN_D = 1.5
if STUD_TAP_THREAD_DEPTH_MIN < STUD_TAP_ENGAGEMENT_MIN_D * STUD_THREAD_MAJOR:
    raise AssertionError(
        f"knife-mount tap's shallowest full thread {STUD_TAP_THREAD_DEPTH_MIN:.3f}"
        f" is under {STUD_TAP_ENGAGEMENT_MIN_D:g} D"
        f" ({STUD_TAP_ENGAGEMENT_MIN_D * STUD_THREAD_MAJOR:.3f})"
    )
# The full thread holds the bolt, so the tap's callout says why its explicit
# +/-0.13 is there and names the mate (drawing-guidelines.md rule 4 (tighten
# only for function, and name the mate)) on one reason row under the native
# thread row: the bolt's tip clearance.  The callout names no tap tool (rule
# 7: the thread row's depth is its full thread, ASME Y14.6, and the shop
# picks the tap that reaches it).  The drill row names the #25 drill in the
# native size token's place.  Three rows -- drill, thread, reason -- keep the
# callout inside the layout audit's four-row limit (tall-block, farm build
# 20261013T225639.450330Z: five rows failed it).
BOLT_NUMBER = "MHA-SM-VN-52"
TAP_DRILL_CALLOUT = f"{STUD_TAP_DRILL} DRILL"
TAP_CALLOUT_REASON = f"SETS {BOLT_NUMBER} TIP CLEARANCE"

# MHA-SM-VN-53 dowels: two blind flat-bottom reamed holes in the top seat at
# DOWEL.HANGER_OFFSET either side of the tap axis along local X, at mid-depth.
# The pair is the sheet's datum B (the orientation that keys the block against
# turning about its screw); the crossbar takes one in a round slip hole, the
# other in a slot along the dowel line, so the pattern never overconstrains.
# The reamed holes hold the press of the stock dowel, as the MHA-PD-18
# latch-pin hole holds the same 1/8 series' (``pd_transgear_arm_geometry``).
PIN_HOLE_X = DOWEL.HANGER_OFFSET  # 7.632
PIN_HOLE_XS = (-PIN_HOLE_X, PIN_HOLE_X)
PIN_HOLE_COUNT = len(PIN_HOLE_XS)
if PIN_HOLE_COUNT != DOWEL.PER_MOUNT:
    raise AssertionError("the knife mount reams one hole per MHA-SM-VN-53 dowel")
# The pair's 2X ream carries ⌖Ø0.13 to the top seat (datum A) and names the
# pattern datum B (the datum feature symbol on that frame; drawing-guidelines.md rule 5 (avoid excessive GD&T)); the
# frame itself prints 2X under it too, so B is plainly the two-hole pattern,
# not one hole.  The sheet
# prints its span BASIC between the two hole axes, centred on the block, and
# positions the tap and the bore to A|B.  Each hole's station from the
# pattern centre varies by the zone's radius, and from the tap axis by that
# plus the tap's zone radius.
PIN_HOLE_POSITION_TOL = float(GEOMETRIC_TOLERANCES_MM["dowel hole pattern position"])
PIN_HOLE_SPAN = DOWEL.SPAN  # 15.264 BASIC
PIN_HOLE_SPAN_PLACES = DOWEL.SPAN_PLACES
PIN_HOLE_SPAN_TOL = PIN_HOLE_POSITION_TOL  # 0.13: the span's worst variation
PIN_HOLE_HALF_SPAN_TOL = PIN_HOLE_SPAN_TOL / 2.0  # 0.065
PIN_HOLE_X_TOL = PIN_HOLE_HALF_SPAN_TOL + STUD_TAP_POSITION_TOL / 2.0  # 0.14
PIN_HOLE_DIA = DOWEL.DIA  # 3.175
PIN_HOLE_DIA_BAND = (0.0, -0.010)
PIN_HOLE_DIA_PLACES = 3
PIN_HOLE_DEPTH = DOWEL.PRESS_DEPTH  # 9.5
PIN_HOLE_DEPTH_PLACES = DOWEL.PRESS_DEPTH_PLACES
DOWEL_NUMBER = "MHA-SM-VN-53"
if PIN_HOLE_SPAN_TOL != DOWEL.SPAN_TOL or PIN_HOLE_SPAN_PLACES != 3:
    raise AssertionError(
        "the dowel pattern's zone must be the span variation the stacks take"
    )
# (loosest, tightest) press from the ream band and the catalogue band:
# 0.00254..0.01762, printed rounded outward to four places.
PIN_PRESS_INTERFERENCE = (
    round(DOWEL.DIA_MIN - (PIN_HOLE_DIA + max(PIN_HOLE_DIA_BAND)), 6),
    round(DOWEL.DIA_MAX - (PIN_HOLE_DIA + min(PIN_HOLE_DIA_BAND)), 6),
)
if PIN_PRESS_INTERFERENCE[0] <= 0.0:
    raise AssertionError("the knife-mount dowel ream loses MHA-SM-VN-53's press")
# The press the sheet prints, rounded outward to four places (the MHA-PD-18
# latch-pin precedent, ``pd_transgear_arm_spec.LATCH_PIN_PRESS_PRINTED``).
PIN_PRESS_PRINTED = (
    math.floor(PIN_PRESS_INTERFERENCE[0] * 1e4 + 1e-6) / 1e4,
    math.ceil(PIN_PRESS_INTERFERENCE[1] * 1e4 - 1e-6) / 1e4,
)
if PIN_PRESS_PRINTED != (0.0025, 0.0177):
    raise AssertionError(f"knife-mount dowel press prints {PIN_PRESS_PRINTED}")
# Worst-case webs round each dowel hole (largest ream, station off by its
# band).
_PIN_R_MAX = (PIN_HOLE_DIA + max(PIN_HOLE_DIA_BAND)) / 2.0
# The pattern is located on the block's outside faces at general tolerance
# (blind machinist review, 2026-10-09: nothing tied the dowel/tap/bore family
# to the faces), both in the top view: the +X dowel hole's axis from the +X
# side face (.XX, the BASIC span chains on to the -X hole) and the -X hole's
# axis from the front face (.X).  The row's square to the front face is the
# title block's angular tolerance.
PIN_HOLE_SIDE_DISTANCE = BLK_HALF_X - PIN_HOLE_X  # 5.068, prints 5.07
PIN_HOLE_SIDE_PLACES = 2
PIN_HOLE_SIDE_TOL = _XX  # 0.51
HOLE_ROW_FACE_DISTANCE = SUPPORT_Z_THICK / 2.0  # 7.0
HOLE_ROW_FACE_PLACES = 1
HOLE_ROW_FACE_TOL = _X  # 0.8
_ANGULAR_TOL_DEG = float(_config.title_block("angular")["value_deg"])  # 1.0
# To the +X side face: 5.068 - 0.51 - 1.5875 = 2.97.
PIN_HOLE_SIDE_WEB = PIN_HOLE_SIDE_DISTANCE - PIN_HOLE_SIDE_TOL - _PIN_R_MAX
# The -X hole to the -X face, the narrowest .X block and the hole a full span
# variation out: 24.6 - (5.578 + 15.394) - 1.5875 = 2.04.
PIN_HOLE_FAR_SIDE_WEB = (
    (2.0 * BLK_HALF_X - BLOCK_SIZE_TOL)
    - (PIN_HOLE_SIDE_DISTANCE + PIN_HOLE_SIDE_TOL + PIN_HOLE_SPAN + PIN_HOLE_SPAN_TOL)
    - _PIN_R_MAX
)
# Front and back faces: the -X hole off its .X band, the block at its
# thinnest .X depth, the row skewed by the angular tolerance.  The +X hole
# stands a full pattern variation and the longest span's skew off it, 0.13 +
# 15.394 tan 1 deg = 0.399; the tap the half-span band, its zone radius and
# half that skew, 0.274.  Back (the binding side) 13.2 - 7.8 = 5.4 from the
# -X axis: dowel 5.4 - 0.399 - 1.5875 = 3.41, tap thread 5.4 - 0.274 -
# 2.413 = 2.71.
_ROW_Z_MIN = min(
    HOLE_ROW_FACE_DISTANCE - HOLE_ROW_FACE_TOL,
    (2.0 * HOLE_ROW_FACE_DISTANCE - BLOCK_SIZE_TOL)
    - (HOLE_ROW_FACE_DISTANCE + HOLE_ROW_FACE_TOL),
)
_ROW_SKEW = (PIN_HOLE_SPAN + PIN_HOLE_SPAN_TOL) * math.tan(
    math.radians(_ANGULAR_TOL_DEG)
)
PIN_HOLE_Z_WEB = _ROW_Z_MIN - (PIN_HOLE_SPAN_TOL + _ROW_SKEW) - _PIN_R_MAX
STUD_TAP_Z_WALL = (
    _ROW_Z_MIN - (PIN_HOLE_X_TOL + _ROW_SKEW / 2.0) - STUD_THREAD_MAJOR / 2.0
)
# The bore's flanks, its axis off the pattern centre by its zone radius and
# the pattern centre off the side face by the +X hole's band and the span's
# half variation: near 12.7 - 0.575 - 0.10 - 6.015 = 6.01, far 24.6 - 13.275
# - 0.10 - 6.015 = 5.21.
_PATTERN_X_MAX = BLK_HALF_X + PIN_HOLE_SIDE_TOL + PIN_HOLE_HALF_SPAN_TOL
BORE_SIDE_WEB = (
    (2.0 * BLK_HALF_X - BLOCK_SIZE_TOL)
    - _PATTERN_X_MAX
    - KNIFE_BORE_POSITION_TOL / 2.0
    - BORE_R_MAX
)
# Under the bore: the shortest .X block below the BASIC bore centre, the bore
# at the bottom of its zone and at its largest: 28.8 - 20.62 - 0.10 - 6.015
# = 2.07 (the build's exact 20.616 leaves 0.004 more).
BORE_BOTTOM_WALL = (
    (BLOCK_HEIGHT_PRINTED - BLOCK_SIZE_TOL)
    - (BLK_TOP - BORE_CY)
    - KNIFE_BORE_POSITION_TOL / 2.0
    - BORE_R_MAX
)
# To the tap's thread major: 7.492 - 1.5875 - 2.413 = 3.4915.
PIN_HOLE_TAP_WEB = (PIN_HOLE_X - PIN_HOLE_X_TOL) - _PIN_R_MAX - STUD_THREAD_MAJOR / 2.0
# The hole floor's inner corner to the bore, the floor at its deepest and the
# bore at its largest, highest position, its axis also off the pattern
# centre toward the hole by its zone radius: 5.78.
_PIN_FLOOR_Y_MIN = BLK_TOP - (PIN_HOLE_DEPTH + DOWEL.PRESS_DEPTH_TOL)
PIN_HOLE_BORE_WEB = (
    (PIN_HOLE_X - PIN_HOLE_HALF_SPAN_TOL - KNIFE_BORE_POSITION_TOL / 2.0 - _PIN_R_MAX)
    ** 2
    + (_PIN_FLOOR_Y_MIN - (BORE_CY + KNIFE_BORE_POSITION_TOL / 2.0)) ** 2
) ** 0.5 - BORE_R_MAX
for _label, _web in (
    ("dowel to the +X side face", PIN_HOLE_SIDE_WEB),
    ("dowel to the -X side face", PIN_HOLE_FAR_SIDE_WEB),
    ("dowel to the tap thread", PIN_HOLE_TAP_WEB),
    ("dowel to the bore", PIN_HOLE_BORE_WEB),
    ("dowel to the front/back face", PIN_HOLE_Z_WEB),
    ("tap thread to the front/back face", STUD_TAP_Z_WALL),
    ("bore to the side face", BORE_SIDE_WEB),
    ("bore to the bottom face", BORE_BOTTOM_WALL),
):
    if _web < STUD_TAP_WEB_MIN:
        raise AssertionError(
            f"knife-mount {_label} leaves {_web:.3f} at worst case,"
            f" under {STUD_TAP_WEB_MIN}"
        )

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The block depth (14) is added on the sheet across the right-view
# section. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"BlockWidth", "BlockHeight"},
    # BoreCz was dropped from the print: the sketch dim measures the centre
    # from the invisible part origin, which sits 0.25 above the bore top -- on
    # the sheet it read as a (wrong) 12.45 bore radius (blind review round 2).
    # The centre height is a sheet-added BASIC from the datum-A top seat.
    "BoreProfile": {"BoreDia"},
    # The dowel holes: their reamed Ø and flat-floor depth.  Their span is a
    # sheet-added dimension between the two hole axes (the model locates
    # each from the tap axis, which the sheet positions to the pair).
    "PinHoleProfile": {"PinHoleDia"},
    "PinHole": {"PinHoleDepth"},
}
# Places the part authors on the marked dimensions (drawing-simplicity
# drawing-simplicity-policy.md `How the repository implements the guidelines`): the block's sizes at .X, the reamed bore at its band's two.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlockProfile": {"BlockWidth": BLOCK_SIZE_PLACES, "BlockHeight": BLOCK_SIZE_PLACES},
    "BoreProfile": {"BoreDia": BORE_DIA_PLACES},
    "PinHoleProfile": {"PinHoleDia": PIN_HOLE_DIA_PLACES},
    "PinHole": {"PinHoleDepth": PIN_HOLE_DEPTH_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
# Places of the dimensions the sheet adds between two model features (no
# model dimension carries them; the fr_top_frame_spec precedent): the dowel
# pair's BASIC span, the tap axis's BASIC station from a dowel axis (the tap
# and bore frames reference B), the bore centre's BASIC height under the
# datum-A top seat, the block's depth, and the pattern's two face
# locations.  A BASIC
# states the model's exact value, so its places must print it unrounded: the
# height is the build's 14.866 + 5.75 = 20.616
# (``build_sm_knife_mount.BORE_CENTRE_DEPTH``), not this module's 14.87
# mirror.
DRAWING_REFERENCE_PRECISION: dict[str, int] = {
    "dowel hole span": PIN_HOLE_SPAN_PLACES,
    "dowel hole from tap axis": PIN_HOLE_SPAN_PLACES,
    "knife-bore centre from top seat": 3,
    "block-depth overall": BLOCK_SIZE_PLACES,
    "dowel hole from side face": PIN_HOLE_SIDE_PLACES,
    "hole row from front face": HOLE_ROW_FACE_PLACES,
}
# The pair's count above the dowel holes' Ø and three short lines under it
# (the MHA-PD-18 PIN_HOLE_CALLOUT precedent): the operation, the mating
# dowel, the press.  The pair is datum B.
PIN_HOLE_PAIR_CALLOUT = f"{PIN_HOLE_COUNT}X"
PIN_HOLE_CALLOUT = "\n".join(
    (
        "BLIND FLAT-BOTTOM REAM",
        f"PRESS {DOWEL_NUMBER} DOWEL TO FLOOR",
        f"{PIN_PRESS_PRINTED[0]:.4f}/{PIN_PRESS_PRINTED[1]:.4f} INTERFERENCE",
    )
)

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
