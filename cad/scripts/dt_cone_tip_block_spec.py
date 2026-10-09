r"""Pure-data dimensional contract shared by the cone-tip-block part and drawing."""

from __future__ import annotations

import math
from typing import Literal

import _config
from _fit_limits import deviations
from _gtol_spec import PlanarFace
from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from _surface_finish import SEAT_UM, SurfaceFinishControl
from dt_post_mount_stack import CONE_AXIS_HEIGHT_MM


# Small black-steel clamp block on the swing platform that carries the axial
# end-play adjuster. See build_dt_cone_tip_block.py for the derivation; this module
# is the drawing's single source of the marked dimensions.
#
# User ruling (2026-09-29, eight-views-4.png lower right: a plain black
# rectangular block standing directly on the swing platform, a round-head
# pinch screw on its side face, the shaft tip entering it): the block is a
# STRAIGHT PRISM standing on the platform top, held by one #4-40 socket head
# cap screw rising from under the platform into a blind tapped hole in the
# foot.  Its station is fixed by that hole, so every fit closes by print
# tolerance (build_dt_drive_train_assembly proves the cross-part stacks against
# the bands exported here).
# U24b (2026-09-23): the adjuster thread's side walls keep 2.0 at the printed
# width (.X) and passage-centre bands.
# r3 (user ruling, Main option (a), 2026-09-25): 17 wide, the narrowest .X
# width whose lower limit keeps the 5/8 pinch screw (McMaster 91794A112)
# PINCH_SCREW_RECESS_MM short of the -X face (asserted with the screw below).
BLOCK_X = 17.0  # plan width across the shaft
# Plan depth along the shaft, printed .XXX.  The north face stands the pivot
# screw's head gap off the pivot (cone_line.TIP_BLOCK_NORTH_FACE_PIVOT_OFFSET)
# and the block grows SOUTH (user ruling 2026-09-29): the depth must hold the
# adjuster's embed window (below) open over the tip's axial stack, and stay
# short enough that the MHA-VN-016 stack collar never reaches the south face
# (build_dt_drive_train_assembly's collar-to-block air).  9.75 sits between the
# two at print-worst.
BLOCK_Z = 9.75
# The adjuster and cone journal share one height above the platform top.
# Free material above the slit floor and the pinch screw's rise stay fixed.
ADJUSTER_AXIS_HEIGHT = CONE_AXIS_HEIGHT_MM
# User ruling U24b (2026-09-23, W-target): the pinch screw sits 8.85 above the
# adjuster axis and the top 14.56 above it, so the slit-mouth web between the
# pinch clearance hole and the adjuster thread root, and the ligament over the
# pinch hole, both keep 2.0 after edge breaks at the printed limits.
# r3 (codex FIX review of 72ab, 2026-09-25): the print locates the pinch hole
# straight from the foot (PinchHeight, .XX) rather than chaining it off the
# adjuster axis.  PINCH_RISE stays the design offset; it no longer prints.
TOP_ABOVE_AXIS = 14.56
BLOCK_HEIGHT = ADJUSTER_AXIS_HEIGHT + TOP_ABOVE_AXIS
PINCH_RISE = 8.85
PINCH_HEIGHT = ADJUSTER_AXIS_HEIGHT + PINCH_RISE
# The printed grade of every dimension a stack reads; DRAWING_PRECISION must
# carry the same (checked at the end of this module).  Two dimensions carry
# an explicit band instead of the title block's: the axis height (the tip's
# vertical capture in the adjuster cup, build_dt_drive_train_assembly) and the
# hold-down tap's two stations (the pivot-head, embed and lateral stacks).
# The width prints .XXX: PassageCenter and FootTapX locate from the -X face,
# so the width's band lands on the +X face, which stands over the plate's
# narrow west edge; at .X that face could overhang it at the printed limits
# (build_dt_drive_train_assembly's print-worst containment), at .XX it keeps
# only 0.27 of the 0.50 it needs.
BLOCK_WIDTH_PLACES = 3
BLOCK_DEPTH_PLACES = 3
BLOCK_HEIGHT_PLACES = 1
AXIS_HEIGHT_PLACES = 3
AXIS_HEIGHT_TOL_MM = 0.10
PINCH_HEIGHT_PLACES = 2
PASSAGE_CENTER_PLACES = 3
PINCH_DEPTH_PLACES = 1
SLIT_W_PLACES = 2
SLIT_DEPTH_PLACES = 1
SLIT_FLOOR = ADJUSTER_AXIS_HEIGHT - 0.65
SLIT_W = 1.2
SLIT_DEPTH = BLOCK_HEIGHT - SLIT_FLOOR
# Rule-12 E11/W1 (Main, 2026-09-24): a #10-32 x 3/8 cup set screw (McMaster
# 94025A164) in a thread tapped THROUGH the block, a 90-degree countersink at
# both mouths, and no block growth.  A through tap has no floor to break out
# and no tap lead to deduct; the shaft tip enters through the same thread.
# ADJUSTER_EMBED is the depth from the north face at which the cup's apex
# would meet the tip; the tip's flat end seats on the cup wall one seat depth
# (stub radius / tan 45 deg) short of the apex, so the rim, and the thread
# engagement, sit that much shallower.  User ruling 2026-09-29: the block is
# fixed by its hold-down, so the tip's axial scatter lands on that
# engagement; build_dt_drive_train_assembly sums the stack and asserts it stays
# inside ADJUSTER_EMBED_WINDOW.  The value centres the engagement there.
ADJUSTER_THREAD = "#10-32"
ADJUSTER_SCREW_LENGTH = 9.525
ADJUSTER_EMBED = 8.17
# 90-degree countersink on each mouth to Ø5.0, just over the 4.826 major, so
# the first thread starts full rather than on a feather edge (Main,
# 2026-09-24).  Its depth is the 45-degree break on the tap drill.
ADJUSTER_CSK_DIA = 5.0
# ASME B1.1 #10-32 UNF-2B minimum minor diameter (0.1560 in): the tightest
# envelope the shaft tip passes through.
ADJUSTER_MINOR_MIN_DIA = 0.1560 * 25.4
SHAFT_PASSAGE_DIA = ADJUSTER_MINOR_MIN_DIA
PINCH_THREAD = "#4-40"  # cross-bore tapped hole that squeezes the top slit
ADJUSTER_BORE_SPEC = HoleSpec("tapped", ADJUSTER_THREAD)
ADJUSTER_BORE_DIA = blind_cut_dia_mm(ADJUSTER_BORE_SPEC)
ADJUSTER_CSK = (ADJUSTER_CSK_DIA - ADJUSTER_BORE_DIA) / 2.0
if ADJUSTER_CSK_DIA < THREAD_MAJOR_MM[ADJUSTER_THREAD]:
    raise AssertionError("adjuster countersink ends inside the thread major")
PINCH_BORE_SPEC = HoleSpec("tapped", PINCH_THREAD)
PINCH_BORE_DIA = blind_cut_dia_mm(PINCH_BORE_SPEC)
PINCH_CLEARANCE_SPEC = HoleSpec(
    "clearance",
    "#4",
    fit="normal",
    end="blind",
    depth_mm=(BLOCK_X - SLIT_W) / 2.0,
)
PINCH_CLEARANCE_DIA = blind_cut_dia_mm(PINCH_CLEARANCE_SPEC)

# Prove every web against what the PRINT permits, not just nominal CAD (U27:
# 2.0 target, 1.5 floor, at the worst case of the printed bands).
_GENERAL_1PL_MM = float(str(_config.title_block("linear_1pl")["display"]).lstrip("±"))
_GENERAL_2PL_MM = float(str(_config.title_block("linear_2pl")["display"]).lstrip("±"))
_GENERAL_3PL_MM = float(str(_config.title_block("linear_3pl")["display"]).lstrip("±"))
_DRILLED_HOLE_PLUS_MM = float(
    str(_config.title_block("drilled_hole")["display_plus"]).lstrip("+")
)
_BAND_BY_PLACES = {1: _GENERAL_1PL_MM, 2: _GENERAL_2PL_MM, 3: _GENERAL_3PL_MM}
# The title block's general bands as (upper, lower) fit bands, so every stack
# below reads its limits through _fit_limits.deviations like any other band.
GENERAL_BAND_BY_PLACES = {
    places: (band, -band) for places, band in _BAND_BY_PLACES.items()
}


def _printed_limits(nominal: float, places: int) -> tuple[float, float]:
    """(min, max) the print allows a general-tolerance dimension."""
    printed = round(nominal, places)
    lower, upper = deviations(GENERAL_BAND_BY_PLACES[places])
    return printed + lower, printed + upper


def printed_band_mm(places: int) -> float:
    """Half-width of the title block's general band at ``places`` decimals."""
    return _BAND_BY_PLACES[places]


# r3 (Main, 2026-09-25): PassageCenter prints from the -X face, which the
# plate frame puts on the east.  The +X (west) face carries only the pinch
# screw's head, so the width's band lands on that side; it prints .XXX
# because the swing platform's trimmed west edge bounds it there
# (build_dt_drive_train_assembly asserts the print-worst containment).
XDatumFace = Literal["-X", "+X"]
PASSAGE_CENTER_DATUM: XDatumFace = "-X"


def worst_half_widths_mm(datum: XDatumFace) -> dict[XDatumFace, float]:
    """Farthest each side face can stand from the adjuster axis at the
    printed limits, with PassageCenter measured from ``datum``: that side is
    PassageCenter's upper limit, the other the width's upper limit less
    PassageCenter's lower."""
    if datum not in ("-X", "+X"):
        raise ValueError(f"unknown PassageCenter datum face {datum!r}")
    passage = _printed_limits(BLOCK_X / 2.0, PASSAGE_CENTER_PLACES)
    width = _printed_limits(BLOCK_X, BLOCK_WIDTH_PLACES)
    far = width[1] - passage[0]
    if datum == "-X":
        return {"-X": passage[1], "+X": far}
    return {"+X": passage[1], "-X": far}


WORST_HALF_WIDTH_MM = worst_half_widths_mm(PASSAGE_CENTER_DATUM)

# Title block: REMOVE BURRS AND BREAK SHARP EDGES R0.25 OR CHAMFER 0.25 MAX.
# Where a web ends in two exposed edges (the slit mouth, the pinch-hole mouth
# under the top face) both breaks come off the same web.
EDGE_BREAK_MAX_MM = 0.25
MIN_WEB_MM = 2.0
# ASME B1.1 #10-32 UNF-2B has no specified maximum major diameter; its
# section 5.8.2(a) reference envelope (basic major + 0.14433757P + the 2B
# pitch-diameter tolerance, 0.1736 - 0.1697 in) stands in for the finished
# thread root.
_ADJ_PITCH_MM = 25.4 / 32.0
ADJUSTER_ROOT_REF_DIA = (
    THREAD_MAJOR_MM[ADJUSTER_THREAD] + 0.14433757 * _ADJ_PITCH_MM + 0.0039 * 25.4
)
_root_r = ADJUSTER_ROOT_REF_DIA / 2.0
_worst_clearance_radius = (
    round(PINCH_CLEARANCE_DIA, 2) + _DRILLED_HOLE_PLUS_MM
) / 2.0
_min_slit_half = _printed_limits(SLIT_W, SLIT_W_PLACES)[0] / 2.0
_adjuster_major_radius = THREAD_MAJOR_MM[ADJUSTER_THREAD] / 2.0
_pinch_major_radius = THREAD_MAJOR_MM[PINCH_THREAD] / 2.0
_axis_limits = (
    ADJUSTER_AXIS_HEIGHT - AXIS_HEIGHT_TOL_MM,
    ADJUSTER_AXIS_HEIGHT + AXIS_HEIGHT_TOL_MM,
)
_pinch_limits = _printed_limits(PINCH_HEIGHT, PINCH_HEIGHT_PLACES)
_height_limits = _printed_limits(BLOCK_HEIGHT, BLOCK_HEIGHT_PLACES)
# Both stations are located from the foot, so the pinch centre can sit as low
# as its own lower limit over an axis at its upper one.
_worst_rise = _pinch_limits[0] - _axis_limits[1]
# On the slit wall the pinch clearance hole and the adjuster thread root come
# closest where the wall is narrowest (the minimum slot width).
WORST_SLIT_MOUTH_WEB_MM = (
    _worst_rise
    - _worst_clearance_radius
    - (_root_r**2 - _min_slit_half**2) ** 0.5
    - 2.0 * EDGE_BREAK_MAX_MM
)
WORST_SCREW_ENVELOPE_GAP_MM = (
    _worst_rise - _pinch_major_radius - _adjuster_major_radius
)
# PinchHeight keeps .XX for this ligament: at .X it closes at 1.92.
WORST_TOP_LIGAMENT_MM = (
    _height_limits[0]
    - _pinch_limits[1]
    - _worst_clearance_radius
    - 2.0 * EDGE_BREAK_MAX_MM
)
_width_limits = _printed_limits(BLOCK_X, BLOCK_WIDTH_PLACES)
_depth_limits = _printed_limits(BLOCK_Z, BLOCK_DEPTH_PLACES)
WORST_ADJUSTER_SIDE_LIGAMENT_MM = (
    _width_limits[0]
    - _printed_limits(BLOCK_X / 2.0, PASSAGE_CENTER_PLACES)[1]
    - _root_r
)
WORST_PINCH_DEPTH_LIGAMENT_MM = (
    _depth_limits[0]
    - _printed_limits(BLOCK_Z / 2.0, PINCH_DEPTH_PLACES)[1]
    - _worst_clearance_radius
)
for _name, _web in (
    ("slit-mouth web", WORST_SLIT_MOUTH_WEB_MM),
    ("top ligament", WORST_TOP_LIGAMENT_MM),
    ("adjuster side wall", WORST_ADJUSTER_SIDE_LIGAMENT_MM),
    ("pinch-depth ligament", WORST_PINCH_DEPTH_LIGAMENT_MM),
):
    if round(_web, 6) < MIN_WEB_MM:
        raise AssertionError(f"{_name} is {_web:.3f} at the printed limits (< 2.0, U27)")
if WORST_SCREW_ENVELOPE_GAP_MM <= 0.0:
    raise AssertionError("pinch screw can collide with the installed adjuster")
# The slit must open into the adjuster thread or its jaws never grip it: the
# slit floor (SlitDepth down from the top) stays under the tap-drill crown
# (AxisHeight up from the foot) at the printed extremes.  Below the thread the
# slit may run on: the jaws only lengthen.
SLIT_BREAKTHROUGH_MARGIN_MM = 0.25
WORST_SLIT_BREAKTHROUGH_MM = (_axis_limits[0] + ADJUSTER_BORE_DIA / 2.0) - (
    _height_limits[1] - _printed_limits(SLIT_DEPTH, SLIT_DEPTH_PLACES)[0]
)
if WORST_SLIT_BREAKTHROUGH_MM < SLIT_BREAKTHROUGH_MARGIN_MM - 1e-9:
    raise AssertionError(
        f"slit floor can stop {WORST_SLIT_BREAKTHROUGH_MM:.3f} short of breaking "
        f"into the adjuster thread (< {SLIT_BREAKTHROUGH_MARGIN_MM})"
    )
# r3 blocker (codex FIX review of 72ab): the Ø3.26 near-jaw clearance printed
# 6.9 blind, a .X depth whose 6.1 floor stops short of a near jaw the print
# lets reach 8.47, so the screw could thread-lock in the near jaw and never
# pinch.  It now prints DRILL TO SLOT: full diameter until it opens into the
# slit.  The model keeps its blind depth exactly to the nominal near wall,
# where the drill point ends in the slit, so the solid is the same.
#
# The near wall's worst station from the +X (drilling) face, taking the
# deeper of the two datums PassageCenter could print from -- the width's band
# on that side under the -X datum the print uses -- less half the narrowest
# slit.  Drilled full diameter PINCH_BREAKTHROUGH_MARGIN_MM past it, the
# 118-degree point must meet the far jaw (the narrowest slit's width on)
# inside the tap drill already through it.
PINCH_BREAKTHROUGH_MARGIN_MM = 0.25
DRILL_POINT_ANGLE_DEG = 118.0
WORST_PINCH_NEAR_WALL_MM = (
    max(worst_half_widths_mm(datum)["+X"] for datum in ("-X", "+X"))
    - _min_slit_half
)
PINCH_TO_SLOT_DEPTH_MM = WORST_PINCH_NEAR_WALL_MM + PINCH_BREAKTHROUGH_MARGIN_MM
_clearance_max_dia = 2.0 * _worst_clearance_radius
PINCH_DRILL_POINT_MM = _worst_clearance_radius / math.tan(
    math.radians(DRILL_POINT_ANGLE_DEG / 2.0)
)
_point_past_far_wall = (
    PINCH_BREAKTHROUGH_MARGIN_MM + PINCH_DRILL_POINT_MM - 2.0 * _min_slit_half
)
WORST_PINCH_POINT_DIA_AT_FAR_JAW_MM = max(
    0.0, _clearance_max_dia * _point_past_far_wall / PINCH_DRILL_POINT_MM
)
if WORST_PINCH_POINT_DIA_AT_FAR_JAW_MM > PINCH_BORE_DIA:
    raise AssertionError(
        "drilling the pinch clearance to the slot scars the far jaw outside its "
        f"tap drill (point Ø{WORST_PINCH_POINT_DIA_AT_FAR_JAW_MM:.3f} at its face)"
    )
_nominal_point = (PINCH_CLEARANCE_DIA / 2.0) / math.tan(
    math.radians(DRILL_POINT_ANGLE_DEG / 2.0)
)
if (
    PINCH_CLEARANCE_SPEC.end != "blind"
    or abs(PINCH_CLEARANCE_SPEC.depth_mm - (BLOCK_X - SLIT_W) / 2.0) > 1e-9
    or _nominal_point >= SLIT_W
):
    raise AssertionError("the modelled pinch clearance is not the drilled-to-slot solid")
# The far jaw is tapped through (a through Hole Wizard thread, TO SLOT on the
# print), and the Ø3.26 opposite passes the tap, so the tap's lead runs on into
# the slit and every far-jaw thread is full.
if (
    PINCH_BORE_SPEC.end != "through_all"
    or PINCH_CLEARANCE_DIA <= THREAD_MAJOR_MM[PINCH_THREAD]
):
    raise AssertionError("the far jaw is not tapped full-thread through to the slit")
# Rule-12 E1 (user ruling, Main option (a), 2026-09-25): a #4-40 x 5/8 18-8
# stainless fillister screw (McMaster 91794A112, 15.875 under the head) seats
# on the +X face and threads only into the far jaw, whose thread starts at the
# slit's far wall.  From the head face that wall stands at most the +X half
# (its worst under the print's datum) plus half the widest slit, so the far
# jaw keeps >= 1.5D of thread there; and at the width's lower limit the tip
# stays PINCH_SCREW_RECESS_MM inside the -X face.  (72ab measured the
# engagement to the NEAR wall, crediting the slit's width as thread.)
PINCH_SCREW_SKU = "91794A112"
PINCH_SCREW_LENGTH = 15.875
PINCH_SCREW_RECESS_MM = 0.25
WORST_PINCH_FAR_WALL_MM = (
    WORST_HALF_WIDTH_MM["+X"] + _printed_limits(SLIT_W, SLIT_W_PLACES)[1] / 2.0
)
WORST_PINCH_ENGAGEMENT_MM = PINCH_SCREW_LENGTH - WORST_PINCH_FAR_WALL_MM
if WORST_PINCH_ENGAGEMENT_MM < 1.5 * THREAD_MAJOR_MM[PINCH_THREAD]:
    raise AssertionError(
        f"pinch screw far-jaw engagement {WORST_PINCH_ENGAGEMENT_MM:.3f} < 1.5D "
        "at the printed worst case"
    )
WORST_PINCH_TIP_RECESS_MM = _width_limits[0] - PINCH_SCREW_LENGTH
if WORST_PINCH_TIP_RECESS_MM < PINCH_SCREW_RECESS_MM - 1e-9:
    raise AssertionError(
        f"pinch screw tip can stand {WORST_PINCH_TIP_RECESS_MM:.3f} inside the -X "
        f"face at the printed width minimum (< {PINCH_SCREW_RECESS_MM})"
    )
# The adjuster's working window, cup rim measured in from the north face:
# shallow end = ADJUSTER_MIN_ENGAGEMENT_D of full thread under the north
# countersink; deep end = the cup rim still on full thread above the south
# countersink with the block at its .XXX-short depth.  The screw is longer
# than the window's deep end, so its head always stands proud and the rim's
# depth is the engagement.  The tip's axial stack (shaft, post, platform,
# hold-down and this block's tap station) moves the cup's seat about
# ADJUSTER_EMBED; build_dt_drive_train_assembly asserts that band stays inside
# this window.
#
# Named exception to the drawing policy's 1.5D thread-engagement rule (user
# ruling 2026-09-29, option (a); the policy's Named exceptions row for
# MHA-VN-017): the cup adjuster engages 1.0D at the worst case.  It carries only
# the shaft's end-play thrust -- the cone set's running push, no clamp load;
# the pinch screw across the slit locks it -- and 1.5D would need a block deep
# enough to push the MHA-VN-016 stack collar into the block's south face at
# print-worst (the collar-to-block air in build_dt_drive_train_assembly).
ADJUSTER_MIN_ENGAGEMENT_D = 1.0
ADJUSTER_EMBED_WINDOW = (
    ADJUSTER_MIN_ENGAGEMENT_D * THREAD_MAJOR_MM[ADJUSTER_THREAD] + ADJUSTER_CSK,
    _depth_limits[0] - ADJUSTER_CSK,
)
if ADJUSTER_MIN_ENGAGEMENT_D != 1.0:
    raise AssertionError(
        "the MHA-VN-017 1.0D engagement is a named exception (user ruling "
        "2026-09-29); any other value is a new ruling"
    )
if not (
    ADJUSTER_EMBED_WINDOW[0] < ADJUSTER_EMBED < ADJUSTER_EMBED_WINDOW[1]
    and ADJUSTER_SCREW_LENGTH >= ADJUSTER_EMBED_WINDOW[1]
):
    raise AssertionError("adjuster embed leaves its working window")
# The worst-case full-thread engagement the window guarantees, floored to the
# printed places so the sheet never states more than the stack delivers.
ADJUSTER_ENGAGEMENT_MIN_MM = (
    math.floor(ADJUSTER_MIN_ENGAGEMENT_D * THREAD_MAJOR_MM[ADJUSTER_THREAD] * 100.0)
    / 100.0
)
# The assembly sheet states the shortfall as a plain fact at the step that
# sets the adjuster, worded like MHA-VN-031's.
# Named exception: MHA-VN-017 engagement (drawing-simplicity-policy.md, "Named exceptions").
ADJUSTER_ENGAGEMENT_ASSEMBLY_FACT = (
    f"ENGAGEMENT {ADJUSTER_ENGAGEMENT_MIN_MM:.2f} MIN ({ADJUSTER_MIN_ENGAGEMENT_D:.1f}D)."
)

# --- hold-down (user ruling 2026-09-29) --------------------------------------
# One McMaster 91251A108 #4-40 x 3/8 black-oxide alloy socket head cap screw
# (MHA-VN-030) rises from the swing platform's underside counterbore through a
# #4 close-clearance hole into a blind #4-40 tap in the foot, on the block's
# centre (under the adjuster axis, at mid-depth).  A #4 rather than a #6: the
# #6 head's counterbore would leave a 1.59 ledge in the 1/4 plate.
HOLDDOWN_THREAD = "#4-40"
HOLDDOWN_SCREW_LENGTH = 0.375 * 25.4
# ASME B18.3 socket head cap screw length tolerance, nominal lengths to 1 in:
# +0 / -0.03 in.
HOLDDOWN_SCREW_LENGTH_MIN = HOLDDOWN_SCREW_LENGTH - 0.03 * 25.4
_HOLDDOWN_MAJOR_MM = THREAD_MAJOR_MM[HOLDDOWN_THREAD]
_HOLDDOWN_PITCH_MM = 25.4 / 40.0
# The ledge the head bears on, counterbore floor to platform top, at the
# plate's stock band and its .XX counterbore depth
# (dt_cone_swing_platform_spec.HOLDDOWN_LEDGE_RANGE, asserted equal in
# build_dt_drive_train_assembly; a copy so this part does not re-key on the
# platform's print).
HOLDDOWN_LEDGE_RANGE_MM = (2.21, 3.49)
# The block's foot sits on the platform top, so the screw reaches past the
# ledge straight into the tap.
WORST_HOLDDOWN_ENGAGEMENT_MM = HOLDDOWN_SCREW_LENGTH_MIN - HOLDDOWN_LEDGE_RANGE_MM[1]
WORST_HOLDDOWN_REACH_MM = HOLDDOWN_SCREW_LENGTH - HOLDDOWN_LEDGE_RANGE_MM[0]
if WORST_HOLDDOWN_ENGAGEMENT_MM < 1.5 * _HOLDDOWN_MAJOR_MM:
    raise AssertionError(
        f"hold-down engagement {WORST_HOLDDOWN_ENGAGEMENT_MM:.3f} < 1.5D at the "
        "thickest ledge and shortest screw"
    )
# Full-thread depth (.X) keeps the longest reach FOOT_TAP_MARGIN_MM clear of
# the tap's incomplete lead; the tap drill (.X) runs 1.5P past the deepest
# full thread so a plug tap's lead never eats it.
FOOT_TAP_MARGIN_MM = 0.25
FOOT_THREAD_DEPTH = 8.5
FOOT_DEPTH = 11.1
FOOT_DEPTH_PLACES = 1
if WORST_HOLDDOWN_REACH_MM > FOOT_THREAD_DEPTH - _GENERAL_1PL_MM - FOOT_TAP_MARGIN_MM:
    raise AssertionError("hold-down screw can reach the foot tap's incomplete threads")
if (FOOT_DEPTH - _GENERAL_1PL_MM) - (FOOT_THREAD_DEPTH + _GENERAL_1PL_MM) < (
    1.5 * _HOLDDOWN_PITCH_MM
):
    raise AssertionError("foot tap drill leaves no lead room past the full thread")
FOOT_BORE_SPEC = HoleSpec(
    "tapped",
    HOLDDOWN_THREAD,
    end="blind",
    depth_mm=FOOT_DEPTH,
    overrides_mm={"ThreadDepth": FOOT_THREAD_DEPTH},
)
FOOT_BORE_DIA = blind_cut_dia_mm(FOOT_BORE_SPEC)
# The tap's two stations, each with an explicit +/-FOOT_TAP_STATION_TOL_MM:
# across the block from the -X face (the PassageCenter datum), and along the
# axis from the NORTH face, the face the pivot screw's head gap is measured
# to (build_dt_drive_train_assembly's pivot-head, embed and lateral stacks read
# this band).  The tap sits FOOT_TAP_OFFSET_X off the adjuster axis, the
# same offset as the platform's hold-down hole off the cone line
# (dt_cone_swing_platform_spec.HOLDDOWN_LOCAL_X, which says why), so the block
# body stands centred on the cone line.  Toward -X because the width's band
# falls on the +X side: there the tap's web is the thinner one.
FOOT_TAP_OFFSET_X = -1.0
FOOT_TAP_X = BLOCK_X / 2.0 + FOOT_TAP_OFFSET_X
FOOT_TAP_Z = BLOCK_Z / 2.0
FOOT_TAP_STATION_TOL_MM = 0.10
FOOT_TAP_X_PLACES = 2
FOOT_TAP_Z_PLACES = 3
_tap_r = _HOLDDOWN_MAJOR_MM / 2.0
_tap_drill_top_max = (
    FOOT_DEPTH
    + _GENERAL_1PL_MM
    + (FOOT_BORE_DIA / 2.0) / math.tan(math.radians(DRILL_POINT_ANGLE_DEG / 2.0))
)
WORST_FOOT_TAP_WEBS_MM = {
    "-X side": FOOT_TAP_X - FOOT_TAP_STATION_TOL_MM - _tap_r,
    "+X side": _width_limits[0] - (FOOT_TAP_X + FOOT_TAP_STATION_TOL_MM) - _tap_r,
    "north face": FOOT_TAP_Z - FOOT_TAP_STATION_TOL_MM - _tap_r,
    "south face": _depth_limits[0] - (FOOT_TAP_Z + FOOT_TAP_STATION_TOL_MM) - _tap_r,
    "adjuster thread": (
        _axis_limits[0] - ADJUSTER_ROOT_REF_DIA / 2.0 - _tap_drill_top_max
    ),
}
for _name, _web in WORST_FOOT_TAP_WEBS_MM.items():
    if round(_web, 6) < MIN_WEB_MM:
        raise AssertionError(
            f"foot tap {_name} web is {_web:.3f} at the printed limits (< 2.0, U27)"
        )

SURFACE_FINISHES = (
    # This face locates the adjuster block on the swing platform. Everything
    # else remains governed by the title-block CAST/MACHINED process row.
    SurfaceFinishControl("foot_seat", SEAT_UM, PlanarFace((0, -1, 0), 0.0)),
)


DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"Width", "Depth"},
    "Block": {"BlockHt"},
    # E11/W1: the through thread replaced the passage sketch that used to
    # carry the axis height; a construction reference owns it now.
    "AxisHeightReference": {"AxisHeight"},
    "PassageCenterReference": {"PassageCenter"},
    "PinchDepthReference": {"PinchDepthCenter"},
    # r3: the pinch-hole centre from the foot, no longer chained off the axis.
    "PinchHeightReference": {"PinchHeight"},
    "SlitProfile": {"SlitW"},
    "TopSlit": {"SlitDepth"},
    # 2026-09-29: the hold-down tap's stations on the foot (hidden reference
    # sketches; the tap's size and depths print on its Hole Wizard callout).
    "FootTapXReference": {"FootTapX"},
    "FootTapZReference": {"FootTapZ"},
}

# Decimal places carry the general tolerance and therefore live on the model.
# U24b: the webs close at the title-block bands.  Still .XX: the pinch-hole
# height (the top ligament closes at 1.92 at .X) and the slit width (the
# drill-to-slot point reaches past the far jaw's tap drill at .X).  2026-09-29:
# with the block fixed by its hold-down, the depth and the passage centre
# print .XXX (the embed window, the collar-to-block air and the lateral
# stack; build_dt_drive_train_assembly proves each looser grade fails), and the
# axis height and the tap's stations carry an explicit +/-0.10 (set on the
# model, AXIS_HEIGHT_TOL_MM / FOOT_TAP_STATION_TOL_MM).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlockProfile": {"Width": BLOCK_WIDTH_PLACES, "Depth": BLOCK_DEPTH_PLACES},
    "Block": {"BlockHt": BLOCK_HEIGHT_PLACES},
    "AxisHeightReference": {"AxisHeight": AXIS_HEIGHT_PLACES},
    "PassageCenterReference": {"PassageCenter": PASSAGE_CENTER_PLACES},
    "PinchDepthReference": {"PinchDepthCenter": PINCH_DEPTH_PLACES},
    "PinchHeightReference": {"PinchHeight": PINCH_HEIGHT_PLACES},
    "SlitProfile": {"SlitW": SLIT_W_PLACES},
    "TopSlit": {"SlitDepth": SLIT_DEPTH_PLACES},
    "FootTapXReference": {"FootTapX": FOOT_TAP_X_PLACES},
    "FootTapZReference": {"FootTapZ": FOOT_TAP_Z_PLACES},
}
# The stacks above read these grades; the print must carry exactly them.
_STACK_GRADES = {
    ("BlockProfile", "Width"): BLOCK_WIDTH_PLACES,
    ("BlockProfile", "Depth"): BLOCK_DEPTH_PLACES,
    ("Block", "BlockHt"): BLOCK_HEIGHT_PLACES,
    ("AxisHeightReference", "AxisHeight"): AXIS_HEIGHT_PLACES,
    ("PassageCenterReference", "PassageCenter"): PASSAGE_CENTER_PLACES,
    ("PinchDepthReference", "PinchDepthCenter"): PINCH_DEPTH_PLACES,
    ("PinchHeightReference", "PinchHeight"): PINCH_HEIGHT_PLACES,
    ("SlitProfile", "SlitW"): SLIT_W_PLACES,
    ("TopSlit", "SlitDepth"): SLIT_DEPTH_PLACES,
    ("FootTapXReference", "FootTapX"): FOOT_TAP_X_PLACES,
    ("FootTapZReference", "FootTapZ"): FOOT_TAP_Z_PLACES,
}
# Explicit symmetric bands the model sets on these dimensions; every other
# marked dimension prints the title block's general band for its places.
EXPLICIT_SYMMETRIC_TOLERANCES_MM: dict[tuple[str, str], float] = {
    ("AxisHeightReference", "AxisHeight"): AXIS_HEIGHT_TOL_MM,
    ("FootTapXReference", "FootTapX"): FOOT_TAP_STATION_TOL_MM,
    ("FootTapZReference", "FootTapZ"): FOOT_TAP_STATION_TOL_MM,
}
for (_feature, _dimension), _places in _STACK_GRADES.items():
    if DRAWING_PRECISION[_feature][_dimension] != _places:
        raise AssertionError(
            f"a stack reads {_dimension} at {_places} places; the print carries "
            f"{DRAWING_PRECISION[_feature][_dimension]}"
        )
DRAWING_PRECISION_BY_NAME = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if len(DRAWING_PRECISION_BY_NAME) != sum(
    len(dimensions) for dimensions in DRAWING_PRECISION.values()
):
    raise AssertionError("two features share a cone-tip-block drawing dimension name")
for _feature, _dimensions in DRAWING_PRECISION.items():
    _unmarked = sorted(set(_dimensions) - DRAWING_DIMENSIONS.get(_feature, set()))
    if _unmarked:
        raise AssertionError(
            f"DRAWING_PRECISION names unmarked {_feature} dimensions: {_unmarked}"
        )
_EXPLICIT_BAND_BY_NAME = {
    dimension: band for (_feature, dimension), band in EXPLICIT_SYMMETRIC_TOLERANCES_MM.items()
}


def printed_value_text(name: str, nominal: float) -> str:
    """The text a marked dimension prints: the value at its model places,
    then the explicit symmetric band where the model sets one."""
    text = f"{nominal:.{DRAWING_PRECISION_BY_NAME[name]}f}"
    band = _EXPLICIT_BAND_BY_NAME.get(name)
    return text if band is None else f"{text}\u00b1{band:.2f}"
