r"""Pure-data dimensional contract shared by the cone-tip-block part and drawing."""

from __future__ import annotations

import math
from typing import Literal

import _config
from _fit_limits import deviations
from _gtol_spec import PlanarFace
from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from _surface_finish import SEAT_UM, SurfaceFinishControl


# Small black-steel clamp block on the swing platform that carries the axial
# end-play adjuster. See build_cone_tip_block.py for the derivation; this module
# is the drawing's single source of the marked dimensions.
# U24b (2026-09-23): 15 wide so the adjuster thread's side walls keep 2.05 at
# the printed width (.X) and passage-centre (.XX) bands.
# r3 (user ruling, Main option (a), 2026-09-25): 17 wide, the narrowest .X
# width whose lower limit keeps the 5/8 pinch screw (McMaster 91794A112)
# PINCH_SCREW_RECESS_MM short of the -X face (asserted with the screw below).
BLOCK_X = 17.0  # plan width across the shaft
BLOCK_Z = 12.0  # plan depth along the shaft
# User ruling U30 (2026-09-23): the block stands on a blackened shim pack
# (1.10 nominal, set at fit-up) and is held by one hidden #6-32 screw from
# under the swing platform. The whole block therefore drops 1.10 below the
# cone axis: every feature keeps its place relative to the adjuster axis, and
# the shim restores the drive height in the assembly. The 2026-09-21 DFM
# correction still stands relative to that axis: free material above the
# slit floor, and the pinch screw located from the adjuster axis.
SHIM_NOMINAL = 1.10
ADJUSTER_AXIS_HEIGHT = 33.368 - SHIM_NOMINAL  # 32.268 above the foot
# User ruling U24b (2026-09-23, W-target): the pinch screw sits 8.85 above the
# adjuster axis and the top 14.56 above it, so the slit-mouth web between the
# pinch clearance hole and the adjuster thread root, and the ligament over the
# pinch hole, both keep 2.0 after edge breaks at the printed limits.
# r3 (codex FIX review of 72ab, 2026-09-25): the print locates the pinch hole
# straight from the foot (PinchHeight, .XX) rather than chaining it off the
# adjuster axis, and the axis height and the overall height drop to the .X
# envelope grade: the fit-up shim takes up the axis band, and every web below
# closes on those grades.  PINCH_RISE stays the design offset; it no longer
# prints.
TOP_ABOVE_AXIS = 14.56
BLOCK_HEIGHT = ADJUSTER_AXIS_HEIGHT + TOP_ABOVE_AXIS  # 46.828
PINCH_RISE = 8.85
PINCH_HEIGHT = ADJUSTER_AXIS_HEIGHT + PINCH_RISE  # 41.118 above the foot
# The printed grade of every dimension a stack below reads; DRAWING_PRECISION
# must carry the same (checked at the end of this module).
BLOCK_WIDTH_PLACES = 1
BLOCK_HEIGHT_PLACES = 1
AXIS_HEIGHT_PLACES = 1
PINCH_HEIGHT_PLACES = 2
PASSAGE_CENTER_PLACES = 2
SLIT_W_PLACES = 2
SLIT_DEPTH_PLACES = 1
SLIT_FLOOR = ADJUSTER_AXIS_HEIGHT - 0.65
SLIT_W = 1.2
SLIT_DEPTH = BLOCK_HEIGHT - SLIT_FLOOR
# Rule-12 E11/W1 (Main, 2026-09-24): a #10-32 x 3/8 cup set screw (McMaster
# 94025A164) in a thread tapped THROUGH the block, a 90-degree countersink at
# both mouths, and no block growth.  A through tap has no floor to break out
# and no tap lead to deduct; the shaft tip enters through the same thread.
# The cup rim sits ADJUSTER_EMBED in from the north face (the 3/8 screw stands
# 0.03 proud).  Worst case at the printed bands: the tip station can come
# 0.8 north (the shaft's .X overall length), and the north countersink eats
# its depth, so engagement is min(L, embed - 0.8) - countersink >= 1.5D.  The
# block's own axial location is set at fit-up (integration item "tip-block
# axial fit-up slot"), not stacked.
ADJUSTER_THREAD = "#10-32"
ADJUSTER_SCREW_LENGTH = 9.525
ADJUSTER_EMBED = 9.5
# 90-degree countersink on each mouth to Ø5.0, just over the 4.826 major, so
# the first thread starts full rather than on a feather edge (Main,
# 2026-09-24).  Its depth is the 45-degree break on the tap drill.
ADJUSTER_CSK_DIA = 5.0
# ASME B1.1 #10-32 UNF-2B minimum minor diameter (0.1560 in): the tightest
# envelope the shaft tip passes through.
ADJUSTER_MINOR_MIN_DIA = 0.1560 * 25.4
SHAFT_PASSAGE_DIA = ADJUSTER_MINOR_MIN_DIA
# I31 option 1 (Main, 2026-09-25): the block is held down through a south
# foot flange.  One #6-32 x 5/8 hex-head screw (McMaster 93075A150) rises from
# the swing platform's counterbored lateral slot, through the fit-up shim pack
# and an axial slot in the flange, into a #6-32 nylon-insert locknut
# (McMaster 90631A007) on the flange top.  The plate slot lets the block move
# across the cone axis, the flange slot along it, so the block sits wherever
# the shaft tip puts it and the screw clamps it there; the counterbore slot's
# walls hold the hex head, so the nut is turned from above alone.
FOOT_THREAD = "#6-32"
FOOT_SHIM_RANGE_MM = (0.05, 2.20)
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
# 2.0 target, 1.5 floor, at the worst case of the printed bands).  Relative
# stations chain from the adjuster axis: axis, rise and height all print .XX.
_GENERAL_1PL_MM = float(str(_config.title_block("linear_1pl")["display"]).lstrip("±"))
_GENERAL_2PL_MM = float(str(_config.title_block("linear_2pl")["display"]).lstrip("±"))
_DRILLED_HOLE_PLUS_MM = float(
    str(_config.title_block("drilled_hole")["display_plus"]).lstrip("+")
)
_BAND_BY_PLACES = {1: _GENERAL_1PL_MM, 2: _GENERAL_2PL_MM}
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


# r3 (Main, 2026-09-25): PassageCenter -- and FlangeSlotX with it -- prints
# from the -X (west) face.  The +X (east) face carries only the pinch screw's
# head, so the width's .X band lands on that side, and the west half, which
# the swing platform's trimmed north-west corner bounds, keeps the .XX band
# (build_drive_train_assembly asserts the print-worst containment).
XDatumFace = Literal["-X", "+X"]
PASSAGE_CENTER_DATUM: XDatumFace = "-X"


def worst_half_widths_mm(datum: XDatumFace) -> dict[XDatumFace, float]:
    """Farthest each side face can stand from the adjuster axis at the
    printed limits, with PassageCenter (.XX) measured from ``datum``: that
    side is PassageCenter's upper limit, the other the width's upper limit
    less PassageCenter's lower."""
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
_axis_limits = _printed_limits(ADJUSTER_AXIS_HEIGHT, AXIS_HEIGHT_PLACES)
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
WORST_ADJUSTER_SIDE_LIGAMENT_MM = (
    round(BLOCK_X, 1)
    - _GENERAL_1PL_MM
    - (round(BLOCK_X / 2.0, 2) + _GENERAL_2PL_MM)
    - _root_r
)
WORST_PINCH_DEPTH_LIGAMENT_MM = (
    round(BLOCK_Z, 1)
    - _GENERAL_1PL_MM
    - (round(BLOCK_Z / 2.0, 1) + _GENERAL_1PL_MM)
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
# Fit-up: the shim pack sets the adjuster axis on the shaft axis, so its range
# takes up the printed AxisHeight band either way, plus FIT_UP_SHIM_MARGIN_MM
# for the platform-side terms (build_drive_train_assembly asserts the pivot
# post's journal position tolerance fits inside it).
FIT_UP_SHIM_MARGIN_MM = 0.25
FIT_UP_SHIM_NEEDED_MM = (
    SHIM_NOMINAL - (ADJUSTER_AXIS_HEIGHT - _axis_limits[0]) - FIT_UP_SHIM_MARGIN_MM,
    SHIM_NOMINAL + (_axis_limits[1] - ADJUSTER_AXIS_HEIGHT) + FIT_UP_SHIM_MARGIN_MM,
)
if (
    FIT_UP_SHIM_NEEDED_MM[0] < FOOT_SHIM_RANGE_MM[0] - 1e-9
    or FIT_UP_SHIM_NEEDED_MM[1] > FOOT_SHIM_RANGE_MM[1] + 1e-9
):
    raise AssertionError(
        f"shim range {FOOT_SHIM_RANGE_MM} cannot take up the printed axis "
        f"height band: needs {FIT_UP_SHIM_NEEDED_MM[0]:.3f}..{FIT_UP_SHIM_NEEDED_MM[1]:.3f}"
    )
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
_width_limits = _printed_limits(BLOCK_X, BLOCK_WIDTH_PLACES)
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
# E11/W1: the through thread is the whole block, so the screw is the limit.
WORST_ADJUSTER_ENGAGEMENT_MM = (
    min(ADJUSTER_SCREW_LENGTH, ADJUSTER_EMBED - _GENERAL_1PL_MM) - ADJUSTER_CSK
)
if WORST_ADJUSTER_ENGAGEMENT_MM < 1.5 * THREAD_MAJOR_MM[ADJUSTER_THREAD]:
    raise AssertionError(
        f"adjuster engagement {WORST_ADJUSTER_ENGAGEMENT_MM:.2f} < 1.5D at the "
        "printed worst case"
    )
# The adjuster's working window, cup rim measured in from the north face:
# shallow end = 1.5D of full thread under the north countersink; deep end = the
# cup rim still on full thread above the south countersink with the block at
# its .X-short depth.  Fit-up sets the block so the cup seats at
# ADJUSTER_EMBED; end-play turns (1/8 turn = 0.099) move it inside the window.
ADJUSTER_EMBED_WINDOW = (
    1.5 * THREAD_MAJOR_MM[ADJUSTER_THREAD] + ADJUSTER_CSK,
    round(BLOCK_Z, 1) - _GENERAL_1PL_MM - ADJUSTER_CSK,
)
if not (
    ADJUSTER_EMBED_WINDOW[0]
    <= ADJUSTER_EMBED - _GENERAL_1PL_MM
    <= ADJUSTER_EMBED + _GENERAL_1PL_MM
    <= ADJUSTER_EMBED_WINDOW[1]
):
    raise AssertionError("adjuster embed band leaves its working window")

# I31 heel relief (Main, 2026-09-25): the cone pivot screw's head (McMaster
# 91829A560, Ø9.525 x 4.7625) stands on the platform top 11.0 north of the
# block centre, only 0.2375 off the block's north face at nominal, and the
# block's north face moves north with the shaft tip (Sec4End, .X) at fit-up.
# A rectangular step along the whole north-bottom edge clears the head: the
# drive-train builder derives the required depth (tip travel + head float in
# the pivot hole + 0.20 air - nominal gap) and height (head top above the
# lowest foot) from the live parts and asserts these printed .XX values cover
# them (build_drive_train_assembly, "heel relief").
HEEL_RELIEF_DEPTH = 1.53
HEEL_RELIEF_HEIGHT = 5.56
# --- I31 foot flange and its axial slot --------------------------------------
# The purchased hardware the flange is sized for, from the McMaster product
# pages (read 2026-09-25): 93075A150 is a 6-32 x 5/8 low-strength zinc-plated
# steel hex head screw, head 1/4 wide x 3/32 high (ASME B18.6.3); 90631A007 is
# a 6-32 zinc-plated steel nylon-insert locknut, 5/16 wide x 11/64 high.  The
# catalogue gives no insert height, so the whole 11/64 counts as nut and the
# screw must stand a full pitch past its top face.
HOLDDOWN_SCREW_LENGTH = 0.625 * 25.4
HOLDDOWN_NUT_AF = 5.0 / 16.0 * 25.4
HOLDDOWN_NUT_H = 11.0 / 64.0 * 25.4
# Sharp corners: the largest the nut can sweep.
HOLDDOWN_NUT_AC = HOLDDOWN_NUT_AF / (3.0**0.5 / 2.0)
HOLDDOWN_PITCH_MM = 25.4 / 32.0
_HOLDDOWN_MAJOR_MM = THREAD_MAJOR_MM[FOOT_THREAD]
# The flange slot is one pass of a 5/32 end mill, so its width carries the
# cutter's one-sided +0.10/0 band (the title block's drilled-hole row),
# written (upper, lower) like every _fit_limits band and only ever read
# through _fit_limits.deviations, here and on the model -- never by index.
FLANGE_SLOT_W = 5.0 / 32.0 * 25.4
FLANGE_SLOT_W_BAND = (_DRILLED_HOLE_PLUS_MM, 0.0)
_FLANGE_SLOT_W_LOWER, _FLANGE_SLOT_W_UPPER = deviations(FLANGE_SLOT_W_BAND)
FLANGE_SLOT_W_MIN = FLANGE_SLOT_W + _FLANGE_SLOT_W_LOWER
FLANGE_SLOT_W_MAX = FLANGE_SLOT_W + _FLANGE_SLOT_W_UPPER
FLANGE_SLOT_FLOAT = (FLANGE_SLOT_W_MAX - _HOLDDOWN_MAJOR_MM) / 2.0
FLANGE_SLOT_FLOAT_MIN = (FLANGE_SLOT_W_MIN - _HOLDDOWN_MAJOR_MM) / 2.0
# Why the width keeps that band (Main's ruled fit, r3): under the title
# block's general .XX band the slot could come out 3.46, under the #6-32
# major, and the hold-down screw would not pass; rule 12 lets the one-pass
# cutter's band stand as the loose grade.  The reason lives here, not in a
# sheet note (rule 6).  Should the .XX band ever clear the major, the fit is
# no longer needed and the slot prints .XX like the rest.
if FLANGE_SLOT_W - _GENERAL_2PL_MM >= _HOLDDOWN_MAJOR_MM:
    raise AssertionError("the flange slot's +0.10/0 fit is no longer needed; print it .XX")
# Fit-up chain: how far the screw can sit from where the block needs it,
# along the axis.  The block's north face follows the shaft tip (the cup seats
# at ADJUSTER_EMBED), so the chain runs tip -> north face -> south face ->
# screw -> plate slot centre: the shaft's overall length Sec4End (.X; asserted
# against the shaft spec in build_drive_train_assembly), the block Depth (.X),
# the plate's TipSlotZ station (.XX; asserted against the platform spec there
# too) and the screw's float across the plate's 4.0 +0.10 slot.  The flange
# slot's two ends carry their own bands below.
SHAFT_OVERALL_LENGTH_PLACES = 1
BLOCK_DEPTH_PLACES = 1
PLATE_TIP_SLOT_Z_PLACES = 2
PLATE_TIP_SLOT_W = 4.0
PLATE_TIP_SLOT_W_PLUS = _DRILLED_HOLE_PLUS_MM
PLATE_TIP_SLOT_FLOAT = (
    PLATE_TIP_SLOT_W + PLATE_TIP_SLOT_W_PLUS - _HOLDDOWN_MAJOR_MM
) / 2.0
FIT_UP_CHAIN_MM = (
    _BAND_BY_PLACES[SHAFT_OVERALL_LENGTH_PLACES]
    + _BAND_BY_PLACES[BLOCK_DEPTH_PLACES]
    + _BAND_BY_PLACES[PLATE_TIP_SLOT_Z_PLACES]
    + PLATE_TIP_SLOT_FLOAT
)
FIT_UP_MARGIN_MM = 1.0
# The screw's nominal station south of the body's south face: the slot's
# midpoint, where the plate's TipSlotZ puts it.
FLANGE_SLOT_Z = 10.7
# r3 (codex FIX review of 72ab, option A): each arc centre is baselined from
# the body's south face -- a face the shop can reach -- at .X, so the print
# carries neither the .XX spacing (the old 8.42) nor a location from the
# slot's own midpoint (the old 10.7).  With its own band and the screw's float
# in the slot, each end still passes the screw FIT_UP_MARGIN_MM beyond the
# fit-up chain.
FLANGE_SLOT_END_PLACES = 1
FLANGE_SLOT_NORTH_Z = 6.5
FLANGE_SLOT_SOUTH_Z = 14.9
FLANGE_SLOT_CTOC = FLANGE_SLOT_SOUTH_Z - FLANGE_SLOT_NORTH_Z
_north_end_limits = _printed_limits(FLANGE_SLOT_NORTH_Z, FLANGE_SLOT_END_PLACES)
_south_end_limits = _printed_limits(FLANGE_SLOT_SOUTH_Z, FLANGE_SLOT_END_PLACES)
if abs((FLANGE_SLOT_NORTH_Z + FLANGE_SLOT_SOUTH_Z) / 2.0 - FLANGE_SLOT_Z) > 1e-9:
    raise AssertionError("the flange slot's ends are not centred on the screw station")
FIT_UP_NORTH_MARGIN_MM = (FLANGE_SLOT_Z - FIT_UP_CHAIN_MM) - (
    _north_end_limits[1] - FLANGE_SLOT_FLOAT
)
FIT_UP_SOUTH_MARGIN_MM = (_south_end_limits[0] + FLANGE_SLOT_FLOAT) - (
    FLANGE_SLOT_Z + FIT_UP_CHAIN_MM
)
if min(FIT_UP_NORTH_MARGIN_MM, FIT_UP_SOUTH_MARGIN_MM) < FIT_UP_MARGIN_MM - 1e-9:
    raise AssertionError(
        "flange slot no longer covers the fit-up chain with its margin: "
        f"north {FIT_UP_NORTH_MARGIN_MM:.3f}, south {FIT_UP_SOUTH_MARGIN_MM:.3f}"
    )
FLANGE_SLOT_LEN = FLANGE_SLOT_CTOC + FLANGE_SLOT_W
# The nut sits on the flange top next to the body's south wall.  At the
# slot's north end (that end short, the screw floating north) its corners
# keep NUT_WALL_AIR off the wall.
NUT_WALL_AIR = 0.5
# From the south face; the flange's own length is .X like the body's plan.
# The rule -- the slot's south edge at its printed limits, plus MIN_WEB_MM,
# plus the length's own .X band, rounded up to .X -- gives 20.6.  The flange
# end locates nothing, so it takes FLANGE_END_ALLOWANCE_MM more: the end web
# is then 2.27 at the printed limits, not 2.07, room a first-time machinist
# can spend on a rough saw cut.  The drive train's clearances read FLANGE_LEN.
_SLOT_SOUTH_EDGE_MAX = _south_end_limits[1] + FLANGE_SLOT_W_MAX / 2.0
_FLANGE_LEN_BY_RULE = (
    math.ceil((_SLOT_SOUTH_EDGE_MAX + MIN_WEB_MM + _GENERAL_1PL_MM) * 10.0 - 1e-6) / 10.0
)
FLANGE_END_ALLOWANCE_MM = 0.2
FLANGE_LEN = round(_FLANGE_LEN_BY_RULE + FLANGE_END_ALLOWANCE_MM, 1)
# The slot is on the block's centre plane, located from the -X face (the
# PassageCenter datum); the flange is the block's full width (.X).  r3 (Main,
# 2026-09-25): no stack needs the slot's location at .XX, so it prints .X --
# the side webs below and the lateral take-up after them both close there.
FLANGE_SLOT_X = BLOCK_X / 2.0
FLANGE_SLOT_X_PLACES = 1
_slot_x_limits = _printed_limits(FLANGE_SLOT_X, FLANGE_SLOT_X_PLACES)
WORST_FLANGE_SIDE_WEB_MM = min(
    _slot_x_limits[0],
    _width_limits[0] - _slot_x_limits[1],
) - (FLANGE_SLOT_W_MAX) / 2.0
# Lateral fit-up: the shaft sets the adjuster axis (PassageCenter) and the
# hold-down screw stands at the flange slot's centre (FlangeSlotX), both from
# the -X face, so the two disagree by at most their two bands.  The screw's
# float in the narrowest flange slot and the swing platform's cross slot take
# that up with HOLDDOWN_LATERAL_MARGIN_MM to spare.
#
# The platform's worst lateral travel either side of the cone axis is owned by
# cone_swing_platform_spec.TIP_LATERAL_TRAVEL_WORST (PR #830, branch
# drawings/dt-cone-swing-platform): 2.2475 - 0.51 = 1.7375, which the platform
# asserts rounds to 1.74.  That symbol is not on this branch's base yet, so its
# exact value is held here as a named copy and
# test_platform_lateral_travel_lockstep compares the two once the import
# resolves.  MERGE RIDER (#838): when #830 is on the base, replace this
# constant with the import and delete the lockstep test's skip.
PLATE_TIP_LATERAL_TRAVEL_WORST_MM = 1.7375
HOLDDOWN_LATERAL_MARGIN_MM = 0.25
_passage_x_limits = _printed_limits(BLOCK_X / 2.0, PASSAGE_CENTER_PLACES)
WORST_HOLDDOWN_LATERAL_OFFSET_MM = max(
    _slot_x_limits[1] - _passage_x_limits[0],
    _passage_x_limits[1] - _slot_x_limits[0],
)
HOLDDOWN_LATERAL_TAKE_UP_MM = PLATE_TIP_LATERAL_TRAVEL_WORST_MM + FLANGE_SLOT_FLOAT_MIN
if (
    WORST_HOLDDOWN_LATERAL_OFFSET_MM + HOLDDOWN_LATERAL_MARGIN_MM
    > HOLDDOWN_LATERAL_TAKE_UP_MM + 1e-9
):
    raise AssertionError(
        f"the hold-down screw can sit {WORST_HOLDDOWN_LATERAL_OFFSET_MM:.3f} off the "
        f"adjuster axis; the slots take up {HOLDDOWN_LATERAL_TAKE_UP_MM:.3f}"
    )
WORST_FLANGE_END_WEB_MM = FLANGE_LEN - _GENERAL_1PL_MM - _SLOT_SOUTH_EDGE_MAX
WORST_FLANGE_ROOT_WEB_MM = _north_end_limits[0] - FLANGE_SLOT_W_MAX / 2.0
WORST_NUT_WALL_AIR_MM = (
    _north_end_limits[0] - FLANGE_SLOT_FLOAT - HOLDDOWN_NUT_AC / 2.0
)
# The nut bears on the flange beside the slot without a washer.
NUT_BEARING_MM = (HOLDDOWN_NUT_AF - (FLANGE_SLOT_W_MAX)) / 2.0
for _name, _web in (
    ("flange side web", WORST_FLANGE_SIDE_WEB_MM),
    ("flange end web", WORST_FLANGE_END_WEB_MM),
    ("flange root web", WORST_FLANGE_ROOT_WEB_MM),
):
    if round(_web, 6) < MIN_WEB_MM:
        raise AssertionError(f"{_name} is {_web:.3f} at the printed limits (< 2.0, U27)")
if WORST_NUT_WALL_AIR_MM < NUT_WALL_AIR - 1e-9:
    raise AssertionError("the hold-down nut can reach the block's south wall")
if NUT_BEARING_MM < 1.0:
    raise AssertionError("the hold-down nut bears on under 1.0 beside the flange slot")
if FLANGE_SLOT_W_MIN - _HOLDDOWN_MAJOR_MM < 0.25:
    raise AssertionError("flange slot does not clear the #6-32 major")
# Flange thickness (.XX): with the thickest ledge under the head (the
# platform's stock-plate and counterbore bands, cone_swing_platform_spec
# TIP_LEDGE_RANGE, asserted equal in build_drive_train_assembly) and the
# thickest shim stack, the 5/8 screw still stands a pitch past the nut.
FLANGE_T = 3.50
HOLDDOWN_LEDGE_RANGE_MM = (2.71, 3.99)
HOLDDOWN_PROTRUSION_MM = (
    HOLDDOWN_SCREW_LENGTH
    - (
        HOLDDOWN_LEDGE_RANGE_MM[1]
        + FOOT_SHIM_RANGE_MM[1]
        + FLANGE_T
        + _GENERAL_2PL_MM
        + HOLDDOWN_NUT_H
    ),
    HOLDDOWN_SCREW_LENGTH
    - (
        HOLDDOWN_LEDGE_RANGE_MM[0]
        + FOOT_SHIM_RANGE_MM[0]
        + FLANGE_T
        - _GENERAL_2PL_MM
        + HOLDDOWN_NUT_H
    ),
)
if HOLDDOWN_PROTRUSION_MM[0] < HOLDDOWN_PITCH_MM:
    raise AssertionError(
        f"hold-down screw stands {HOLDDOWN_PROTRUSION_MM[0]:.3f} past the nut at "
        "the thickest stack (< one pitch past the nylon insert)"
    )
# The relief stays in the foot, well under the adjuster thread and its
# countersink.
if (
    HEEL_RELIEF_HEIGHT + _GENERAL_2PL_MM
    > _axis_limits[0] - ADJUSTER_CSK_DIA / 2.0 - MIN_WEB_MM
):
    raise AssertionError("heel relief rises into the adjuster countersink")

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
    # I31 heel relief: depth from the north face, height from the foot.
    "HeelReliefProfile": {"HeelReliefDepth", "HeelReliefHt"},
    # I31 foot flange: its length past the south face and its thickness; the
    # axial slot's width, located from the +X face, and (r3, option A) each
    # arc centre baselined from the south face (hidden reference sketches).
    "FlangeProfile": {"FlangeLen"},
    "Flange": {"FlangeT"},
    "FlangeSlotProfile": {"FlangeSlotW"},
    "FlangeSlotXReference": {"FlangeSlotX"},
    "FlangeSlotNorthReference": {"FlangeSlotNorthZ"},
    "FlangeSlotSouthReference": {"FlangeSlotSouthZ"},
}

# Decimal places carry the general tolerance and therefore live on the model.
# U24b: the webs close at the title-block bands, so no dimension carries its
# own band.  r3 dropped the four .XX the codex review named (46.83, 32.27,
# 8.42, 8.85) to .X or off the print.  Still .XX: the pinch-hole height (the
# top ligament closes at 1.92 at .X), the slit width (the drill-to-slot point
# reaches past the far jaw's tap drill at .X), the heel relief (asserted
# against the pivot-screw head in build_drive_train_assembly), the flange
# thickness (the hold-down protrusion stack) and the flange slot's cutter
# fit, and PassageCenter (at .X the west half could reach 9.3 against the
# platform's 9.558 there; build_drive_train_assembly's print-worst
# containment).  FlangeSlotX dropped to .X in r3: no stack needed I31's .XX.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlockProfile": {"Width": BLOCK_WIDTH_PLACES, "Depth": BLOCK_DEPTH_PLACES},
    "Block": {"BlockHt": BLOCK_HEIGHT_PLACES},
    "AxisHeightReference": {"AxisHeight": AXIS_HEIGHT_PLACES},
    "PassageCenterReference": {"PassageCenter": PASSAGE_CENTER_PLACES},
    "PinchDepthReference": {"PinchDepthCenter": 1},
    "PinchHeightReference": {"PinchHeight": PINCH_HEIGHT_PLACES},
    "SlitProfile": {"SlitW": SLIT_W_PLACES},
    "TopSlit": {"SlitDepth": SLIT_DEPTH_PLACES},
    "HeelReliefProfile": {"HeelReliefDepth": 2, "HeelReliefHt": 2},
    "FlangeProfile": {"FlangeLen": 1},
    "Flange": {"FlangeT": 2},
    # The width is the 5/32 cutter's (+0.10/0, set on the model).
    "FlangeSlotProfile": {"FlangeSlotW": 2},
    "FlangeSlotXReference": {"FlangeSlotX": FLANGE_SLOT_X_PLACES},
    "FlangeSlotNorthReference": {"FlangeSlotNorthZ": FLANGE_SLOT_END_PLACES},
    "FlangeSlotSouthReference": {"FlangeSlotSouthZ": FLANGE_SLOT_END_PLACES},
}
# The stacks above read these grades; the print must carry exactly them.
_STACK_GRADES = {
    ("BlockProfile", "Width"): BLOCK_WIDTH_PLACES,
    ("BlockProfile", "Depth"): BLOCK_DEPTH_PLACES,
    ("Block", "BlockHt"): BLOCK_HEIGHT_PLACES,
    ("AxisHeightReference", "AxisHeight"): AXIS_HEIGHT_PLACES,
    ("PassageCenterReference", "PassageCenter"): PASSAGE_CENTER_PLACES,
    ("FlangeSlotXReference", "FlangeSlotX"): FLANGE_SLOT_X_PLACES,
    ("PinchHeightReference", "PinchHeight"): PINCH_HEIGHT_PLACES,
    ("SlitProfile", "SlitW"): SLIT_W_PLACES,
    ("TopSlit", "SlitDepth"): SLIT_DEPTH_PLACES,
    ("FlangeSlotNorthReference", "FlangeSlotNorthZ"): FLANGE_SLOT_END_PLACES,
    ("FlangeSlotSouthReference", "FlangeSlotSouthZ"): FLANGE_SLOT_END_PLACES,
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

