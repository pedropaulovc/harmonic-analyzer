r"""Knife-mount dimensional contract -- the single source of truth shared by the
part build (``build_sm_knife_mount.py``) and its manufacturing drawing
(``draw_sm_knife_mount.py``).

PURE DATA, no SolidWorks/COM imports.  Nothing else consumes this part's
nominals (no assembly imports ``build_sm_knife_mount``), so one ``_spec`` module is
right here.  The block/bore geometry is derived in the build from the summing-
assembly layout; the fixed values are mirrored here for the drawing's view math,
and the offline lockstep test asserts the part marks and the drawing keeps
EXACTLY ``DRAWING_DIMENSIONS``.

NOTE on the "knife edge": this heat-treated steel BEARING BLOCK (ch18 p.42,
2026-09-02 user re-read: unpainted heat-treated steel, not brass) carries a
circular bore CLOSE around the mating hex trunnion (Ø.472 over the 8.080 x
10.268 hex), so only the trunnion's TOP VERTEX LINE nears the bore's upper
inner wall -- the true knife-edge line contact.  The sharp ridge is on the
LEVER trunnion (``build_sm_summing_lever``), NOT on this part; this part's
critical surface is the bore's upper inner wall, the knife SEAT: it carries
``MACHINED_UM`` (63 µin, policy drawing-guidelines.md rule 6 (roughness
symbols only where a surface runs, slides or locates) -- ``GROUND_UM`` 32 µin
is reserved for knife edges and pivot-screw shoulders).

Issue #290: the sheet prints decimal inch (``drawing_unit: in``).  Lengths
stay physical millimetres, each the exact decimal of its printed inch value;
the knife-edge station (the block top to the ridge, 14.866) is the summing
assembly's and stays as built.

Owner ruling 2026-10-24 (T+H3), from this sheet's machinist ENFORCE review
(rule 16: a dowel pressed into a blind hole needs a way out; rule 4/16: the
press reams could not be cut before through-hardening): the MHA-SM-VN-53
dowel presses into the MHA-FR-02 crossbar, knocked out from its faced top,
and slips into this block's round hole (datum B).  Owner ruling 2026-11-08
(Pedro), #2144 item 11.3 (scheme S1): one dowel and the screw hang the
block; datum C, its slot open to the -X face and every slot control are
deleted, and the block's yaw about the dowel is set at MHA-SM-00 by a
Ø.4720 gauge bar slid through both mounts' bores while the screws are
tightened.  Owner ruling 2026-11-10 (Pedro), #2334 option B1 with S1 and
S2, superseding the 2026-11-08 SM-02 harden-less ruling (O1 drawn back to
40-45 HRC, fit sizes cut after hardening): the block is cut complete from
AISI 4140/4142 HT bar as supplied, 28-32 HRC, with no heat treatment in the
shop, so every printed band is cut once, in its final condition, with HSS;
the finish says so.  No check here or in the summing assembly charges the
seat's hardness (no contact-stress or wear model reads it): the seat need
only out-rank the lever's soft parent-metal knife (#1611), and the error
budget's knife rolling resistance stays an assumption to measure.
"""

from __future__ import annotations

import math

import _config
import sm_vn_knife_mount_dowel_spec as DOWEL
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM, HoleSpec
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import (
    angular_band_deg,
    drilled_oversize_mm,
    inside_corner_radius_mm,
    printed_band_mm,
)
from _surface_finish import MACHINED_UM, SEAT_UM, SurfaceFinishControl
from sm_summing_lever_spec import HEX_H, HEX_W

# #290: the registry row's drawing_unit (in) is this sheet's unit; the bands,
# places and roughness below are authored for it.
UNIT = drawing_unit("parts/sm-knife-mount", _config.parts("sm-knife-mount"))

# --- fixed geometry for the drawing's view math (mirrors build_sm_knife_mount) ----
R_BORE = 5.9944  # Ø.472 knife-bearing bore (2026-09-02 ch18 p.42 re-read: close bore)
# Block half-width, owned here (the build reads it): 1.00 across, the width
# set for the former -X dowel and then its slot (owner ruling 2026-10-24,
# T+H3).  Owner ruling 2026-11-08 (Pedro), #2144 item 11.3 deletes that
# slot; nothing forces a change, so the width stands: it keeps the bore's
# side webs (BORE_SIDE_WEB) and the full top seat the screw clamps.
BLK_HALF_X = 12.7
SUPPORT_Z_THICK = 13.97  # .55 axial depth straddling the trunnion mid
# Local block top (clamped to the top-frame casting underside): the summing
# assembly's knife-edge station, 20.0 - HEX_H / 2 under it (top_frame_plane), exact.
BLK_TOP = 14.866
BLK_BOT = -14.852  # local block bottom: 1.17 tall (BORE_CY - R_BORE - 3.1242 wall)
BORE_CY = -5.7334  # bore centre below the ridge origin (TopClear 0.261 - R_BORE)

# The knife bore's bored seat, Ra 63 µin; the top seat (datum A), which the
# screw clamps to the casting underside and the dowel locates, Ra 125 µin: a
# static mating face, nothing runs on it (SEAT_UM, drawing-guidelines.md rule
# 6 (roughness symbols only where a surface runs, slides or locates);
# 2026-10-10 ruling).
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "knife_bore", MACHINED_UM, CylinderFace(2.0 * R_BORE), display_unit=UNIT
    ),
    SurfaceFinishControl(
        "top_seat",
        SEAT_UM,
        PlanarFace((0.0, 1.0, 0.0), BLK_TOP),
        display_unit=UNIT,
    ),
)

# --- Knife-hanger screw tap and anti-rotation dowel holes (top seat) ---------
# General tolerances the printed places claim (title block, drawing-guidelines.md rule 3 (decimal places carry the tolerance)).
_XX = printed_band_mm(2, unit=UNIT)
_XXX = printed_band_mm(3, unit=UNIT)
# The Ø.472 bore is REAMED through in the supplied 28-32 HRC condition
# (Owner ruling 2026-11-10 (Pedro), #2334 option B1; formerly bored, as no
# .472 reamer is owned): a 12 mm H7 HSS reamer cuts .4724-.4731 inside
# the explicit .4720 +.0015/.0000 band, Ra 63 µin on its knife seat: the rock
# budget takes the smallest bore, the webs the largest.  A plain inch step
# (rule 4; machinist review round 4, farm run 20261107T161739921Z: the
# former +.0012 read as converted millimetres), loosened rather than
# tightened (fan-out L2): every web still holds at the largest bore.
BORE_DIA_BAND = (0.0381, 0.0)  # +.0015/.0000 in
BORE_DIA_PLACES = 4
BORE_R_MIN = R_BORE + min(BORE_DIA_BAND) / 2.0  # 5.9944
BORE_R_MAX = R_BORE + max(BORE_DIA_BAND) / 2.0  # 6.01345
# The block's overall sizes print two places (.XX): every stack below reads
# them, so none takes the .X row.
BLOCK_SIZE_PLACES = 2
BLOCK_SIZE_TOL = _XX  # 0.254
BLOCK_HEIGHT_PRINTED = BLK_TOP - BLK_BOT  # 29.718, 1.17 exactly
# Manufacturing GD&T limits consumed by the part's drawing projection.  Owner
# ruling 2026-10-24 (T+H3): datum A is the top seat and datum B the
# MHA-SM-VN-53 round slip hole (+X).  Owner ruling 2026-11-08 (Pedro), #2144
# item 11.3 (scheme S1): datum C (the slot open to the -X face) and the
# slot's position and perpendicularity are deleted; the hole's ⊥ stands at
# its shop row (delegated ruling sm Q1, 2026-11-07 (Main)).
GEOMETRIC_TOLERANCES_IN: dict[str, str] = {
    "knife-bore position": ".008",
    "knife-bore parallelism": ".002",
    "dowel hole perpendicularity": ".001",
    "knife-hanger tap position": ".008",
}
GEOMETRIC_TOLERANCES_MM: dict[str, float] = {
    key: float(value) * DOWEL.MM_PER_IN
    for key, value in GEOMETRIC_TOLERANCES_IN.items()
}
# The bore (drawing-guidelines.md rule 5 (avoid excessive GD&T), knife-edge
# system), Owner ruling 2026-11-08 (Pedro), #2144 item 11.3: ⌖Ø.008|A|B
# locates it (its BASIC height under A and its BASIC .300 from B's axis to
# its vertical centre plane), for the webs and the tap's crown, and a
# separate ∥.002|A holds its axis parallel to the top seat (its pitch).  A|B
# leaves the bore's yaw about B free: the part no longer sets it.  At
# MHA-SM-00 a Ø.4720 gauge bar slid through both mounts' bores with the
# screws finger-tight sets the yaw before they are tightened, and must slide
# out after (``build_sm_summing_assembly``'s rock budget charges the bar's
# clearance, not this frame; pitch does not enter the lateral rock model).
# The former composite ⌖ to A|B|C (owner ruling 2026-10-27, #2016) went
# with the slot; the bore is now itself datum C, the tap's clocking datum
# (below).
KNIFE_BORE_POSITION_TOL = GEOMETRIC_TOLERANCES_MM["knife-bore position"]
KNIFE_BORE_PARALLELISM_TOL = GEOMETRIC_TOLERANCES_MM["knife-bore parallelism"]
# The #10-24 tap is drilled and tapped on the part, located from datum B
# (Owner ruling 2026-11-10 (Pedro), #2334 option B1, S1, superseding
# delegated ruling sm Q3's spot through MHA-FR-02): ⌖Ø.008|A|B|C▷, its axis
# BASIC PIN_HOLE_X from B's on the bore's vertical centre plane (the
# section A-A BASIC the bore's frame shares).  A|B alone would leave the
# tap's turn about B free relative to the bore, whose yaw inside its own
# Ø.008 zone (0.85 deg over the shortest bore) the gauge bar turns the block
# by at MHA-SM-00, swinging the tap 0.11 across its bolt hole; so the bore,
# datum C, clocks the tap, and C's translation modifier lets C's simulator
# centre in the bore while it only fixes that turn.  Then
# ``build_sm_summing_assembly``'s HANGER_SCREW_MISMATCH charges the zone's
# radius alone, and Ø.008 closes inside MHA-FR-02's C-drill hole (machinist
# exception RV-06: under the drilled-hole row, by that ruling).
STUD_TAP_POSITION_TOL = GEOMETRIC_TOLERANCES_MM["knife-hanger tap position"]
# Datum B's round slip hole stands square to the datum-A top seat, so the
# MHA-SM-VN-53 dowel, pressed square into the crossbar, enters it without
# binding (owner ruling 2026-10-27, #2016, option A): ⊥Ø.001|A, a
# cylindrical zone round its axis, at the shop's perpendicularity row
# (delegated ruling sm Q1).  ``build_sm_summing_assembly``'s slip-tilt proof
# charges it (KNIFE_DOWEL_TILT_CHARGED_DEG < KNIFE_DOWEL_TILT_ALLOWED_DEG).
DOWEL_HOLE_PERPENDICULARITY_TOL = GEOMETRIC_TOLERANCES_MM["dowel hole perpendicularity"]


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
    block's depth (tolerance-gdt-assessment §5.4; Owner ruling 2026-11-08
    (Pedro), #2144 item 11.3: the MHA-SM-00 gauge bar sets the bore's yaw).

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


# Why the bore's yaw is budgeted (2026-10-09 ruling): a yawed bore steals
# rock.  Free rock of the nominal 8.080 x 10.268 trunnion in the nominal
# Ø.472 against the far-end offset t across the deep bore: t 0 -> 8.90 deg,
# falling about 1 deg each 0.1 of t.  The drawing-guidelines.md rule 17
# (walls and webs) budget -- the trunnion's ridge-to-side and flank-to-side
# limits and the bore's size at its band limit, t the MHA-SM-00 gauge bar's
# diametral clearance in the largest bore plus the ridge's yaw that
# clearance allows between the two bores (Owner ruling 2026-11-08 (Pedro),
# #2144 item 11.3) -- is ``build_sm_summing_assembly.KNIFE_FREE_ROCK_WORST_DEG``
# (>= 5.0).  The bore's ∥.002|A sets its pitch, which the lateral rock model
# does not read.  The top seat clamps to the frame's faced Ra 125 µin
# underside plane (MHA-FR-02, user ruling 2026-10-12), so no bedding term
# enters: seat form tilts the block, it cannot yaw the bore.
KNIFE_FREE_ROCK_DEG = free_rock_deg(0.0)
# The bore crown (its upper inner wall) below the top seat: 14.605.
BORE_CROWN_DEPTH = BLK_TOP - (BORE_CY + R_BORE)
# MHA-SM-VN-52, a #10-24 plain hex bolt cut from stock at MHA-SM-00 to its
# hole's measured stack plus the .351 (8.9154, title block +/-.005) fit-up reach
# (``sm_summing_assembly_spec.HANGER_FIT_REACH``), drops through a washer on
# the crossbar's faced top and its #10 clearance hole and threads into a
# bottoming tap on the bore's vertical centreline at mid-depth.  The full
# thread's shallowest limit, 9.398, must take the bolt's longest reach, 9.068
# (``build_sm_summing_assembly.HANGER_TIP_CLEARANCE``), and hold 1.5 D of
# full thread (below).  It prints .375 with an explicit native +/-.005 on the
# hole callout (the band's mate and function are the callout's reason row,
# rule 4).  The drill runs 1.5 P past that nominal thread (.375 + .0625,
# printed .438), yet its deepest limit, with the pilot the web charges ground
# to the sharpest accepted point (below), must still leave the .080 crown
# web: so the drill prints .438 with an explicit +/-.002 band on the sheet's
# hole callout (the MHA-SM-03 bracket-tap precedent).  Both depths print at
# three places; the .380 thread the 9.65 mm rounds to would push the drill
# to .443 and leave 1.99 over the crown.
STUD_THREAD = "#10-24"
STUD_TAP_DRILL_DEPTH = 11.1252  # .438
STUD_TAP_DRILL_DEPTH_PLACES = 3
STUD_TAP_DRILL_DEPTH_BAND = 0.0508  # +/-.002, explicit, functional (above)
STUD_TAP_THREAD_DEPTH = 9.525  # .375
STUD_TAP_THREAD_DEPTH_PLACES = 3
STUD_TAP_THREAD_DEPTH_BAND = _XXX  # +/-.005, explicit, native
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
# toleranced by the title block's DRILLED HOLES row, +.004/0, on the drill's
# size (drawing-guidelines.md rule 3 (decimal places carry the tolerance);
# rule 2 (the title block is the general specification): no callout restates
# it).  This constant is that row, indexed for the limits, not printed.  The
# row reads on the #25's true size, 0.1495 in = 3.7973, not the rounded
# 3.797 the wizard table carries: the pilot accepted is Ø3.7973-3.8989.
STUD_TAP_DRILL_DIA = STUD_TAP_DRILL_IN * DOWEL.MM_PER_IN  # 3.7973
STUD_TAP_DIA_BAND = (drilled_oversize_mm(unit=UNIT), 0.0)  # (upper, lower), title block
STUD_TAP_DIA_ACCEPTED = (
    STUD_TAP_DRILL_DIA + min(STUD_TAP_DIA_BAND),
    STUD_TAP_DRILL_DIA + max(STUD_TAP_DIA_BAND),
)  # (3.7973, 3.8989)
# CHARGED, NOT ACCEPTED: the crown web below charges a wider pilot than the
# sheet accepts, Ø3.924 -- the wizard's Ø3.797 plus the larger of the
# DRILLED HOLES plus and the general .XXX (+/-.005) -- a conservative
# envelope 0.025 over the accepted Ø3.8989.  No pilot is drilled, inspected
# or passed to it.
STUD_TAP_DIA_MAX = STUD_TAP_DIA + max(max(STUD_TAP_DIA_BAND), _XXX)  # 3.924
if STUD_TAP_DIA_MAX < max(STUD_TAP_DIA_ACCEPTED):
    raise AssertionError(
        f"knife-mount crown web charges Ø{STUD_TAP_DIA_MAX:.3f}, under the"
        f" accepted pilot Ø{max(STUD_TAP_DIA_ACCEPTED):.3f}"
    )
STUD_TAP_DIA_OVERSIZE = STUD_TAP_DIA_MAX - STUD_TAP_DIA  # 0.127, charged
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
STUD_TAP_POINT_ANGLE_TOL_DEG = angular_band_deg(unit=UNIT)  # 1.0
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
# thread by at least one pitch, the bottoming tap's lead: 11.074 - 9.652 = 1.422.
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
# sharpest accepted point, the largest bored bore, the bore's position zone
# KNIFE_BORE_POSITION_TOL): 14.605 - 0.1016 - 0.0191 - 11.176 - 1.2023 =
# 2.106, over the rule-17 .080 target.
STUD_TAP_WEB_MIN = WALL_TARGET_MM
STUD_TAP_POINT_H = drill_point_height(
    STUD_TAP_DIA_MAX, STUD_TAP_POINT_ANGLE_MIN_DEG
)  # 1.2023
STUD_TAP_DRILL_DEPTH_MAX = STUD_TAP_DRILL_DEPTH + STUD_TAP_DRILL_DEPTH_BAND  # 11.176
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
STUD_TAP_THREAD_DEPTH_MIN = STUD_TAP_THREAD_DEPTH - STUD_TAP_THREAD_DEPTH_BAND  # 9.398
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
# +/-.005 is there and names the mate (drawing-guidelines.md rule 4 (tighten
# only for function, and name the mate)) on one reason row under the native
# thread row: the bolt's tip clearance.  The tap's location is its own
# position frame (STUD_TAP_POSITION_TOL above), not a callout row.  The
# callout names no tap tool (rule 7: the thread row's depth is its full
# thread, ASME Y14.6, and the shop picks the tap that reaches it).  The drill
# row names the #25 drill in the native size token's place.  Three rows --
# drill, thread, reason -- stay inside the layout audit's four-row limit
# (tall-block, farm build 20261013T225639.450330Z: five rows failed it).
BOLT_NUMBER = "MHA-SM-VN-52"
TAP_DRILL_CALLOUT = f"{STUD_TAP_DRILL} DRILL"
TAP_CALLOUT_REASON = f"SETS {BOLT_NUMBER} TIP CLEARANCE"

# MHA-SM-VN-53 dowel (owner ruling 2026-10-24, T+H3; machinist ENFORCE
# review of this sheet, rules 16 and 4): the pin presses into the MHA-FR-02
# crossbar, which carries its knockout, and SLIPS into this block, which so
# carries no press band of its own: a blind
# round slip hole, datum B, cut from the top seat to a flat floor.  Owner
# ruling 2026-11-08 (Pedro), #2144 item 11.3 (scheme S1): one dowel per
# mount; the -X pin's slot (datum C) is deleted.
PIN_HOLE_X = DOWEL.HANGER_OFFSET  # 7.62 (.300), datum B's station from the tap axis
if DOWEL.PER_MOUNT != 1:
    raise AssertionError("the knife mount slips onto one dowel, in datum B")
PIN_HOLE_DIA = DOWEL.SLIP_HOLE_DIA  # 3.2512 (.1280)
PIN_HOLE_DIA_BAND = DOWEL.SLIP_HOLE_DIA_BAND
PIN_HOLE_DIA_PLACES = DOWEL.SLIP_HOLE_DIA_PLACES
PIN_HOLE_DEPTH = DOWEL.SLIP_DEPTH  # 9.398 (.37), the hole's floor
PIN_HOLE_DEPTH_PLACES = DOWEL.SLIP_DEPTH_PLACES
DOWEL_NUMBER = "MHA-SM-VN-53"

# --- Locations and worst-case webs ------------------------------------------
_PIN_R_MAX = (PIN_HOLE_DIA + max(PIN_HOLE_DIA_BAND)) / 2.0  # 1.6345
# B is located on the block's outside faces (blind machinist review,
# 2026-10-09: nothing tied the dowel/tap/bore family to the faces), both in
# the top view: its axis from the +X side face (.XX) and from the front/back
# face (the block's mid-plane).  The line's square to the front face is the
# title block's angular tolerance.
PIN_HOLE_SIDE_DISTANCE = BLK_HALF_X - PIN_HOLE_X  # 5.08, prints .20
PIN_HOLE_SIDE_PLACES = 2
PIN_HOLE_SIDE_TOL = _XX  # 0.254
# Half the .55 block, so it prints .275 at three places, exactly.  No stack
# needs the row nearer the mid-plane than the .XX class, so the part authors
# that band on the row's model dimension, .275 +/-.010, rather than letting
# the three places put it on the title block's .XXX +/-.005 (blind machinist
# review, 2026-11-03).
HOLE_ROW_FACE_DISTANCE = SUPPORT_Z_THICK / 2.0  # 6.985
HOLE_ROW_FACE_PLACES = 3
HOLE_ROW_FACE_TOL = _XX  # 0.254
_ANGULAR_TOL_DEG = angular_band_deg(unit=UNIT)  # 1.0
_TAN_ANGULAR = math.tan(math.radians(_ANGULAR_TOL_DEG))
# The B row's nearer front/back face at its worst: the face location's .XX
# band, or the thinnest .XX block measured from the far face.
_ROW_Z_MIN = min(
    HOLE_ROW_FACE_DISTANCE - HOLE_ROW_FACE_TOL,
    (2.0 * HOLE_ROW_FACE_DISTANCE - BLOCK_SIZE_TOL)
    - (HOLE_ROW_FACE_DISTANCE + HOLE_ROW_FACE_TOL),
)  # 6.477
# B to the +X side face: 5.08 - 0.254 - 1.634 = 3.19.
PIN_HOLE_SIDE_WEB = PIN_HOLE_SIDE_DISTANCE - PIN_HOLE_SIDE_TOL - _PIN_R_MAX
# B to the front/back face: 6.477 - 1.634 = 4.84.
PIN_HOLE_Z_WEB = _ROW_Z_MIN - _PIN_R_MAX
# The tap axis stands PIN_HOLE_X from B, within its position zone's radius.
_TAP_FROM_B_MIN = PIN_HOLE_X - STUD_TAP_POSITION_TOL / 2.0
# B to the tap's thread major: 7.518 - 1.634 - 2.413 = 3.47.
PIN_HOLE_TAP_WEB = _TAP_FROM_B_MIN - _PIN_R_MAX - STUD_THREAD_MAJOR / 2.0
# The tap's thread to the front/back face: its zone radius and the line's
# skew over its BASIC station from B, 6.477 - 0.102 - 0.133 - 2.413 = 3.83.
STUD_TAP_Z_WALL = (
    _ROW_Z_MIN
    - STUD_TAP_POSITION_TOL / 2.0
    - PIN_HOLE_X * _TAN_ANGULAR
    - STUD_THREAD_MAJOR / 2.0
)
# The bore's flanks: its axis BASIC PIN_HOLE_X from B within its zone
# radius, B off the +X face by its .XX band: near 12.7 - 0.254 - 0.102 -
# 6.013 = 6.331, far 25.146 - 13.056 - 6.013 = 6.077.  ⌖|A|B leaves the
# bore's yaw about B free (Owner ruling 2026-11-08 (Pedro), #2144 item
# 11.3), so each flank also charges the title block's angular tolerance on
# the bore's implied square to the front face, over half the deepest .XX
# block: 7.112 * tan(1 deg) = 0.124, leaving 6.077 - 0.124 = 5.953.
_BORE_FROM_PLUS_X_FACE_MAX = (
    BLK_HALF_X + PIN_HOLE_SIDE_TOL + KNIFE_BORE_POSITION_TOL / 2.0
)
_BORE_YAW_AT_FACE = (SUPPORT_Z_THICK + BLOCK_SIZE_TOL) / 2.0 * _TAN_ANGULAR
BORE_SIDE_WEB = (
    min(
        BLK_HALF_X - PIN_HOLE_SIDE_TOL - KNIFE_BORE_POSITION_TOL / 2.0 - BORE_R_MAX,
        (2.0 * BLK_HALF_X - BLOCK_SIZE_TOL) - _BORE_FROM_PLUS_X_FACE_MAX - BORE_R_MAX,
    )
    - _BORE_YAW_AT_FACE
)
# Under the bore: the shortest .XX block below the BASIC bore centre, the
# bore at the bottom of its zone and at its largest: 29.464 - 20.599 -
# 0.102 - 6.010 = 2.75.
BORE_BOTTOM_WALL = (
    (BLOCK_HEIGHT_PRINTED - BLOCK_SIZE_TOL)
    - (BLK_TOP - BORE_CY)
    - KNIFE_BORE_POSITION_TOL / 2.0
    - BORE_R_MAX
)
# The floors at their deepest over the bore at its largest and highest.
_PIN_FLOOR_Y_MIN = BLK_TOP - (PIN_HOLE_DEPTH + DOWEL.SLIP_DEPTH_TOL)
_BORE_CY_MAX = BORE_CY + KNIFE_BORE_POSITION_TOL / 2.0
# B's floor corner, B toward the bore by the bore's zone radius: 6.33.
PIN_HOLE_BORE_WEB = (
    (PIN_HOLE_X - KNIFE_BORE_POSITION_TOL / 2.0 - _PIN_R_MAX) ** 2
    + (_PIN_FLOOR_Y_MIN - _BORE_CY_MAX) ** 2
) ** 0.5 - BORE_R_MAX
for _label, _web in (
    ("dowel hole B to the +X side face", PIN_HOLE_SIDE_WEB),
    ("dowel hole B to the front/back face", PIN_HOLE_Z_WEB),
    ("dowel hole B to the tap thread", PIN_HOLE_TAP_WEB),
    ("dowel hole B to the bore", PIN_HOLE_BORE_WEB),
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
# print shows.  The block depth (.55) is added on the sheet across the right-view
# section. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"BlockWidth", "BlockHeight"},
    # BoreCz was dropped from the print: the sketch dim measures the centre
    # from the invisible part origin, which sits 0.261 above the bore top -- on
    # the sheet it read as a (wrong) 12.45 bore radius (blind review round 2).
    # The centre height is a sheet-added BASIC from the datum-A top seat.
    "BoreProfile": {"BoreDia"},
    # Datum B, the round slip hole: its Ø, in the hole sketch, and its floor
    # depth (Owner ruling 2026-11-08 (Pedro), #2144 item 11.3: the datum-C
    # slot and its width and end station are deleted).
    "PinHoleProfile": {"PinHoleDia"},
    "PinHole": {"PinHoleDepth"},
    # B's row from the front face, on a hidden reference line along B's axis
    # (build_sm_knife_mount.hole_row_reference), carrying its band.
    "HoleRowReference": {"HoleRowFace"},
}
# Places the part authors on the marked dimensions (drawing-simplicity
# drawing-simplicity-policy.md `How the repository implements the guidelines`): the block's sizes at .XX, the bored bore at its band's four.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlockProfile": {"BlockWidth": BLOCK_SIZE_PLACES, "BlockHeight": BLOCK_SIZE_PLACES},
    "BoreProfile": {"BoreDia": BORE_DIA_PLACES},
    "PinHoleProfile": {"PinHoleDia": PIN_HOLE_DIA_PLACES},
    "PinHole": {"PinHoleDepth": PIN_HOLE_DEPTH_PLACES},
    "HoleRowReference": {"HoleRowFace": HOLE_ROW_FACE_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
# Places of the dimensions the sheet adds between two model features (no
# model dimension carries them; the fr_top_frame_spec precedent): the tap
# axis's BASIC station from B (the bore frame's BASIC to its vertical centre
# plane, |A|B), the bore centre's BASIC height under the datum-A top seat,
# the block's depth, and B's side-face location.  A BASIC states the model's
# exact value, so its places must print it unrounded: the height is the
# build's 14.866 + 5.7334 = 20.5994, .811
# (``build_sm_knife_mount.BORE_CENTRE_DEPTH``).
DRAWING_REFERENCE_PRECISION: dict[str, int] = {
    "dowel hole from tap axis": DOWEL.HANGER_OFFSET_PLACES,
    "knife-bore centre from top seat": 3,
    "block-depth overall": BLOCK_SIZE_PLACES,
    "dowel hole from side face": PIN_HOLE_SIDE_PLACES,
}
# Rule 4: the slip hole is cut to suit the dowel; the clearance it sets,
# in inches printed outward to four places, is its acceptance
# (draw_sm_knife_mount).
PIN_SLIP_PRINTED = (
    math.floor(DOWEL.SLIP_CLEARANCE_MIN / DOWEL.MM_PER_IN * 1e4 + 1e-6) / 1e4,
    math.ceil(DOWEL.SLIP_CLEARANCE_MAX / DOWEL.MM_PER_IN * 1e4 - 1e-6) / 1e4,
)  # (.0020, .0036)
# The hole's floor depth prints its value alone: the slip hole's callout
# already reads "REAM ↧ (.37) FLAT BOTTOM", so a second "FLAT BOTTOM" under
# the section's controlling .37 was a note on a location dimension
# (machinist review, farm run 20261109T083029873Z, rule 7).  Nothing seats on
# the floor (the longest proud pin stands SLIP_DEPTH_CLEARANCE_MIN off the
# shallowest), so its corner takes the title block's INSIDE CORNERS R.040
# MAX and the row prints no limit of its own (machinist review, farm run
# 20261027T233328148Z: a local CORNER R0.1 MAX named no function, rule 1).
# The angular-fit proof (build_sm_summing_assembly) charges the hole's
# straight wall short of that corner, 9.398 - 0.254 - 1.016 - 0.5 = 7.628.
DOWEL_HOLE_FLOOR_CORNER_R_MAX = inside_corner_radius_mm(unit=UNIT)  # 1.016
# The longest proud pin's crowned end stays above the shallowest straight
# wall's end (its crown centre 7.707 deep, the corner's 8.128): pushed against
# the wall there, the crown meets no corner arc (DOWEL_HOLE_CORNER_RECESS 0),
# inside half the tightest slip, so the corner neither bottoms nor binds the
# pin.
_CROWN_CENTRE_DEPTH = DOWEL.PROUD_MAX - DOWEL.FREE_END_LEN
_CORNER_CENTRE_DEPTH = (
    DOWEL.SLIP_DEPTH - DOWEL.SLIP_DEPTH_TOL - DOWEL_HOLE_FLOOR_CORNER_R_MAX
)
DOWEL_HOLE_CORNER_RECESS = (
    math.hypot(
        DOWEL_HOLE_FLOOR_CORNER_R_MAX - DOWEL.FREE_END_LEN,
        max(_CROWN_CENTRE_DEPTH - _CORNER_CENTRE_DEPTH, 0.0),
    )
    + DOWEL.FREE_END_LEN
    - DOWEL_HOLE_FLOOR_CORNER_R_MAX
)
if DOWEL_HOLE_CORNER_RECESS >= DOWEL.SLIP_CLEARANCE_MIN / 2.0:
    raise AssertionError(
        f"the slip hole's floor corner reaches the proud pin's crown "
        f"({DOWEL_HOLE_CORNER_RECESS:.4f} >= half the tightest slip)"
    )

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
