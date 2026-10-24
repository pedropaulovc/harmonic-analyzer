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

Owner ruling 2026-10-24 (T+H3), from this sheet's machinist ENFORCE review
(rule 16: a dowel pressed into a blind hole needs a way out; rule 4/16: the
press reams could not be cut before through-hardening): the two
MHA-SM-VN-53 dowels press into the MHA-FR-02 crossbar, knocked out from its
faced top, and slip into this block's round hole (datum B) and its slot
(datum C, open to the -X face).  The block's finish states that its sizes
apply after heat treatment; O1's growth (<= 0.012 on the Ø12 bore, <= 0.003
on the slip sizes) stays inside the remaining bands.
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
# width set for the former pressed -X dowel's far-side web; with the slot
# open to that face (owner ruling 2026-10-24, T+H3) it keeps the slot's pin
# inside the mouth and the half-round end inboard of it (SLOT_* below).
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
# Manufacturing GD&T limits consumed by the part's drawing projection.  Owner
# ruling 2026-10-24 (T+H3): the datum reference frame is A (the top seat), B
# (the MHA-SM-VN-53 round slip hole, +X) and C (the dowel slot open to the -X
# face, its width positioned to A|B, the crossbar's former slot frame).
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "knife-bore position": "0.20",
    "knife-hanger tap position": "0.15",
    "dowel slot position": "0.05",
}
# The bore (drawing-guidelines.md rule 5 (avoid excessive GD&T), knife-edge
# system): ⌖Ø0.20 to A|B|C.  Its Ø zone over the 14 deep bore bounds both the
# yaw off the dowel line, B to the slot, and the tilt: the rock budget charges
# the whole 0.20 as the far end's offset (5.14 deg worst, over the 5.0 floor
# of the 2026-10-09 ruling), so no stacked orientation frame is needed.
KNIFE_BORE_POSITION_TOL = float(GEOMETRIC_TOLERANCES_MM["knife-bore position"])
KNIFE_BORE_ORIENTATION_TOL = KNIFE_BORE_POSITION_TOL
# The #10-24 tap's position to A|B|C: the bolt axis the crossbar's #10
# clearance hole must float round (``build_sm_summing_assembly``'s knife-hanger
# stack).  Its 0.075 zone radius is one term of HANGER_SCREW_MISMATCH inside
# the hole's 0.6095 radial float with the drill drift's 0.194 over the
# printed grip's thickest 37.01.  A screw through a clearance hole needs no
# tighter zone than that float admits (drawing-guidelines.md rule 5); plain
# face dimensions instead, even at .XXX (+/-0.13 each way, not 0.075), spend
# the float: the frame is functional.
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


# Why the bore's orientation is budgeted (2026-10-09 ruling): a yawed bore
# steals rock.  Free rock of the nominal 8.080 x 10.268 trunnion in the
# nominal Ø12 against the far-end offset t across the 14 deep bore: t 0 ->
# 8.92 deg, 0.05 -> 8.44, 0.10 -> 7.96, 0.18 -> 7.17.  The drawing-guidelines.md
# rule 17 (walls and webs) budget -- the trunnion's ridge-to-side and
# flank-to-side limits and the bore's .XX size at its band limit, t the
# bore's whole Ø0.20 position zone to A|B|C (owner ruling 2026-10-24, T+H3:
# no stacked ⊥ frame) plus the dowel yaw across the deepest .X block -- is
# ``build_sm_summing_assembly.KNIFE_FREE_ROCK_WORST_DEG`` (>= 5.0, 5.14 in
# the reamed bore), which owns the slip terms.  The top seat clamps to the
# frame's faced Ra 3.2 underside plane (MHA-FR-02, user ruling 2026-10-12),
# so no bedding term enters: seat form tilts the block, it cannot yaw the
# bore off the dowel line.
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

# MHA-SM-VN-53 dowels (owner ruling 2026-10-24, T+H3; machinist ENFORCE
# review of this sheet, rules 16 and 4): the pins press into the MHA-FR-02
# crossbar, which carries their knockouts, and SLIP into this hardened block,
# which so carries no press band to hold through heat treatment.  The +X pin
# enters a blind round slip hole, datum B; the -X pin a slot along the dowel
# line, datum C, open to the block's -X face (a closed 3.95 slot left a 1.59
# worst web to that face of the 25.4 block; open, it leaves none), its width
# positioned to A|B.  Both are cut from the top seat to one flat floor.
PIN_HOLE_X = DOWEL.HANGER_OFFSET  # 7.632, datum B's station from the tap axis
SLOT_X = -PIN_HOLE_X  # the -X pin's station: datum C, the slot
if DOWEL.PER_MOUNT != 2:
    raise AssertionError("the knife mount keys on one hole and one slot")
PIN_HOLE_DIA = DOWEL.SLIP_HOLE_DIA  # 3.24
PIN_HOLE_DIA_BAND = DOWEL.SLIP_HOLE_DIA_BAND
PIN_HOLE_DIA_PLACES = DOWEL.SLIP_HOLE_DIA_PLACES
PIN_HOLE_DEPTH = DOWEL.SLIP_DEPTH  # 9.5, the hole's and the slot's floor
PIN_HOLE_DEPTH_PLACES = DOWEL.SLIP_DEPTH_PLACES
SLOT_WIDTH = DOWEL.SLIP_HOLE_DIA
SLOT_WIDTH_BAND = DOWEL.SLIP_HOLE_DIA_BAND
SLOT_WIDTH_PLACES = DOWEL.SLIP_HOLE_DIA_PLACES
DOWEL_NUMBER = "MHA-SM-VN-53"
# The slot's width: ⌖0.05 to A|B, at an implied basic zero across the line
# from B (the crossbar's former slot frame, moved with the slot).
SLOT_POSITION_TOL = float(GEOMETRIC_TOLERANCES_MM["dowel slot position"])
# The slot's inner end: its half-round end's centre stands SLOT_END_FROM_B
# from B's axis along the line, printed .XX.  Its shortest limit keeps the
# end clear of the tap's thread (below); its longest still puts the slot's
# pin, at the crossbar's shortest span (each ream .XXX from its screw axis)
# and B's slip, wholly between the slot's straight walls, so the walls bound
# the pin across the line (clocking) at every limit.  The slot runs straight
# out through the -X face.  The block may go on either way round: the pins
# are one pair, the same either way.
SLOT_END_FROM_B = 14.40
SLOT_END_PLACES = 2
SLOT_END_TOL = _XX  # 0.51
_SLIP_HALF = DOWEL.SLIP_CLEARANCE_MAX / 2.0  # B's float on its pin, 0.046
# The slot's pin's axis from B's axis along the line, (nearest, farthest).
SLOT_PIN_FROM_B = (
    DOWEL.SPAN - DOWEL.SPAN_TOL - _SLIP_HALF,
    DOWEL.SPAN + DOWEL.SPAN_TOL + _SLIP_HALF,
)  # (14.958, 15.570)
# Clocking: the pin's centre stands past the end's centre at the end's
# longest limit, so the pin's full diameter bears on the straight walls:
# 14.958 - 14.91 = 0.048.
SLOT_PIN_LOCATION_MARGIN = SLOT_PIN_FROM_B[0] - (SLOT_END_FROM_B + SLOT_END_TOL)
if SLOT_PIN_LOCATION_MARGIN <= 0.0:
    raise AssertionError(
        f"the -X dowel can reach the slot's half-round end "
        f"({SLOT_PIN_LOCATION_MARGIN:.3f}): its walls no longer clock the block"
    )
# The -X face from B's axis at its nearest: the narrowest .X block less B's
# farthest .XX station from the +X face, 24.6 - 5.578 = 19.022.
# (PIN_HOLE_SIDE_* below.)

# --- Locations and worst-case webs ------------------------------------------
_PIN_R_MAX = (PIN_HOLE_DIA + max(PIN_HOLE_DIA_BAND)) / 2.0  # 1.635
_SLOT_HALF_W_MAX = (SLOT_WIDTH + max(SLOT_WIDTH_BAND)) / 2.0  # 1.635
# B is located on the block's outside faces at general tolerance (blind
# machinist review, 2026-10-09: nothing tied the dowel/tap/bore family to the
# faces), both in the top view: its axis from the +X side face (.XX) and
# from the front/back face (.X, the block's mid-plane).  The line's square to
# the front face is the title block's angular tolerance.
PIN_HOLE_SIDE_DISTANCE = BLK_HALF_X - PIN_HOLE_X  # 5.068, prints 5.07
PIN_HOLE_SIDE_PLACES = 2
PIN_HOLE_SIDE_TOL = _XX  # 0.51
HOLE_ROW_FACE_DISTANCE = SUPPORT_Z_THICK / 2.0  # 7.0
HOLE_ROW_FACE_PLACES = 1
HOLE_ROW_FACE_TOL = _X  # 0.8
_ANGULAR_TOL_DEG = float(_config.title_block("angular")["value_deg"])  # 1.0
_TAN_ANGULAR = math.tan(math.radians(_ANGULAR_TOL_DEG))
_FACE_FROM_B_MIN = (2.0 * BLK_HALF_X - BLOCK_SIZE_TOL) - (
    PIN_HOLE_SIDE_DISTANCE + PIN_HOLE_SIDE_TOL
)  # 19.022
_FACE_FROM_B_MAX = (2.0 * BLK_HALF_X + BLOCK_SIZE_TOL) - (
    PIN_HOLE_SIDE_DISTANCE - PIN_HOLE_SIDE_TOL
)  # 21.642
# The mouth: the slot's pin bears wholly inside the block, its far side short
# of the -X face: 19.022 - 15.570 - 1.591 = 1.86.
SLOT_MOUTH_PIN_MARGIN = _FACE_FROM_B_MIN - SLOT_PIN_FROM_B[1] - DOWEL.DIA_MAX / 2.0
if SLOT_MOUTH_PIN_MARGIN <= 0.0:
    raise AssertionError(
        f"the -X dowel overhangs the slot's open mouth ({SLOT_MOUTH_PIN_MARGIN:.3f})"
    )
# The slot's half-round end stands well inboard of the mouth, so its straight
# walls run square out through the -X face (no part-round lip or feather edge
# to trap a burr there): 19.022 - 14.91 - 1.635 = 2.48.
SLOT_END_TO_MOUTH = (
    _FACE_FROM_B_MIN - (SLOT_END_FROM_B + SLOT_END_TOL) - _SLOT_HALF_W_MAX
)
if SLOT_END_TO_MOUTH < STUD_TAP_WEB_MIN:
    raise AssertionError(
        f"the dowel slot's half-round end stands {SLOT_END_TO_MOUTH:.3f} inside"
        " its mouth: its walls do not run straight out through the -X face"
    )
# The B row's nearer front/back face at its worst: the face location's .X
# band, or the thinnest .X block measured from the far face.
_ROW_Z_MIN = min(
    HOLE_ROW_FACE_DISTANCE - HOLE_ROW_FACE_TOL,
    (2.0 * HOLE_ROW_FACE_DISTANCE - BLOCK_SIZE_TOL)
    - (HOLE_ROW_FACE_DISTANCE + HOLE_ROW_FACE_TOL),
)  # 5.4
# B to the +X side face: 5.068 - 0.51 - 1.635 = 2.92.
PIN_HOLE_SIDE_WEB = PIN_HOLE_SIDE_DISTANCE - PIN_HOLE_SIDE_TOL - _PIN_R_MAX
# B to the front/back face: 5.4 - 1.635 = 3.77.
PIN_HOLE_Z_WEB = _ROW_Z_MIN - _PIN_R_MAX
# The slot's two cheeks (no thin finger at the mouth): its centre plane off
# B's line by half its zone, the line skewed by the angular tolerance out to
# the -X face at its farthest, 5.4 - 0.025 - 0.378 - 1.635 = 3.36.
SLOT_CHEEK_WEB = (
    _ROW_Z_MIN
    - SLOT_POSITION_TOL / 2.0
    - _FACE_FROM_B_MAX * _TAN_ANGULAR
    - _SLOT_HALF_W_MAX
)
# The tap axis stands BASIC PIN_HOLE_X from B, within its zone radius.
_TAP_FROM_B_MIN = PIN_HOLE_X - STUD_TAP_POSITION_TOL / 2.0
# B to the tap's thread major: 7.557 - 1.635 - 2.413 = 3.51.
PIN_HOLE_TAP_WEB = _TAP_FROM_B_MIN - _PIN_R_MAX - STUD_THREAD_MAJOR / 2.0
# The slot's half-round end to the tap's thread major, the end at its
# nearest: 13.89 - 1.635 - 7.707 - 2.413 = 2.135.
_SLOT_TIP_FROM_B_MIN = SLOT_END_FROM_B - SLOT_END_TOL - _SLOT_HALF_W_MAX
SLOT_TAP_WEB = (
    _SLOT_TIP_FROM_B_MIN
    - (PIN_HOLE_X + STUD_TAP_POSITION_TOL / 2.0)
    - STUD_THREAD_MAJOR / 2.0
)
# The tap's thread to the front/back face: its zone radius and the line's
# skew over its BASIC station from B, 5.4 - 0.075 - 0.133 - 2.413 = 2.78.
STUD_TAP_Z_WALL = (
    _ROW_Z_MIN
    - STUD_TAP_POSITION_TOL / 2.0
    - PIN_HOLE_X * _TAN_ANGULAR
    - STUD_THREAD_MAJOR / 2.0
)
# The bore's flanks: its axis BASIC PIN_HOLE_X from B within its zone
# radius, B off the +X face by its .XX band: near 12.7 - 0.51 - 0.10 -
# 6.015 = 6.075, far 24.6 - 13.31 - 6.015 = 5.275.
_BORE_FROM_PLUS_X_FACE_MAX = (
    BLK_HALF_X + PIN_HOLE_SIDE_TOL + KNIFE_BORE_POSITION_TOL / 2.0
)
BORE_SIDE_WEB = min(
    BLK_HALF_X - PIN_HOLE_SIDE_TOL - KNIFE_BORE_POSITION_TOL / 2.0 - BORE_R_MAX,
    (2.0 * BLK_HALF_X - BLOCK_SIZE_TOL) - _BORE_FROM_PLUS_X_FACE_MAX - BORE_R_MAX,
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
# The floors at their deepest over the bore at its largest and highest.
_PIN_FLOOR_Y_MIN = BLK_TOP - (PIN_HOLE_DEPTH + DOWEL.SLIP_DEPTH_TOL)
_BORE_CY_MAX = BORE_CY + KNIFE_BORE_POSITION_TOL / 2.0
# B's floor corner, B toward the bore by the bore's zone radius: 5.78.
PIN_HOLE_BORE_WEB = (
    (PIN_HOLE_X - KNIFE_BORE_POSITION_TOL / 2.0 - _PIN_R_MAX) ** 2
    + (_PIN_FLOOR_Y_MIN - _BORE_CY_MAX) ** 2
) ** 0.5 - BORE_R_MAX
# The slot floor's nearest corner, its half-round end at its nearest: 5.16.
SLOT_BORE_WEB = (
    (_SLOT_TIP_FROM_B_MIN - PIN_HOLE_X - KNIFE_BORE_POSITION_TOL / 2.0) ** 2
    + (_PIN_FLOOR_Y_MIN - _BORE_CY_MAX) ** 2
) ** 0.5 - BORE_R_MAX
for _label, _web in (
    ("dowel hole B to the +X side face", PIN_HOLE_SIDE_WEB),
    ("dowel hole B to the front/back face", PIN_HOLE_Z_WEB),
    ("dowel slot cheek to the front/back face", SLOT_CHEEK_WEB),
    ("dowel hole B to the tap thread", PIN_HOLE_TAP_WEB),
    ("dowel slot end to the tap thread", SLOT_TAP_WEB),
    ("dowel hole B to the bore", PIN_HOLE_BORE_WEB),
    ("dowel slot to the bore", SLOT_BORE_WEB),
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
    # Datum B, the round slip hole: its Ø and the floor depth it shares with
    # the slot (one cut).  Datum C, the slot: its width and its half-round
    # end's centre from B's axis, both in the hole sketch.
    "PinHoleProfile": {"PinHoleDia", "SlotWidth", "SlotEndFromB"},
    "PinHole": {"PinHoleDepth"},
}
# Places the part authors on the marked dimensions (drawing-simplicity
# drawing-simplicity-policy.md `How the repository implements the guidelines`): the block's sizes at .X, the reamed bore at its band's two.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlockProfile": {"BlockWidth": BLOCK_SIZE_PLACES, "BlockHeight": BLOCK_SIZE_PLACES},
    "BoreProfile": {"BoreDia": BORE_DIA_PLACES},
    "PinHoleProfile": {
        "PinHoleDia": PIN_HOLE_DIA_PLACES,
        "SlotWidth": SLOT_WIDTH_PLACES,
        "SlotEndFromB": SLOT_END_PLACES,
    },
    "PinHole": {"PinHoleDepth": PIN_HOLE_DEPTH_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
# Places of the dimensions the sheet adds between two model features (no
# model dimension carries them; the fr_top_frame_spec precedent): the tap
# axis's BASIC station from B (the tap and bore frames reference A|B|C),
# the bore centre's BASIC height under the datum-A top seat, the block's
# depth, and B's two face locations.  A BASIC states the model's exact
# value, so its places must print it unrounded: the height is the build's
# 14.866 + 5.75 = 20.616 (``build_sm_knife_mount.BORE_CENTRE_DEPTH``), not
# this module's 14.87 mirror.
DRAWING_REFERENCE_PRECISION: dict[str, int] = {
    "dowel hole from tap axis": DOWEL.HANGER_OFFSET_PLACES,
    "knife-bore centre from top seat": 3,
    "block-depth overall": BLOCK_SIZE_PLACES,
    "dowel hole from side face": PIN_HOLE_SIDE_PLACES,
    "hole row from front face": HOLE_ROW_FACE_PLACES,
}
# Rule 4: each slip band names its mate and the clearance it sets, printed
# outward to three places.
PIN_SLIP_PRINTED = (
    math.floor(DOWEL.SLIP_CLEARANCE_MIN * 1e3 + 1e-6) / 1e3,
    math.ceil(DOWEL.SLIP_CLEARANCE_MAX * 1e3 - 1e-6) / 1e3,
)  # (0.027, 0.093)
_SLIP_MATE = (
    f"{PIN_SLIP_PRINTED[0]:.3f}-{PIN_SLIP_PRINTED[1]:.3f} DIAMETRAL CLEARANCE",
    f"ON {DOWEL_NUMBER} DOWEL",
)
PIN_HOLE_CALLOUT = "\n".join(("BLIND FLAT-BOTTOM REAM", *_SLIP_MATE))
SLOT_WIDTH_CALLOUT = "\n".join(("OPEN-END SLOT", f"SLIP FIT ON {DOWEL_NUMBER}"))
# One depth for the hole and the slot (one cut to one floor), the
# fr_top_frame HANGER_PIN_DEPTH_CALLOUT precedent.
PIN_DEPTH_CALLOUT = "2X FLAT BOTTOM"

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
