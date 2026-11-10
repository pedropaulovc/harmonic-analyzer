r"""Pure-data dimensional contract shared by the cone-tip-block part and drawing.

The sheet prints decimal inch (#290): every nominal it states is authored as
exact millimetres on its printed grid, with the inch value in a comment.
"""

from __future__ import annotations

import math
from typing import Literal

import _config
import _mcmaster_91794a558 as end_screw_stock
import _printed_tolerance
import cone_tip_cluster
import dt_vn_locating_pin_spec as locating_pin
from _fit_deviations import deviations
from _gtol_planar import PlanarFace
from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _surface_finish import SEAT_UM, SurfaceFinishControl
from _title_block_units import LENGTH_UNITS, render_number
from _cone_axis_constants import CONE_AXIS_HEIGHT_MM, PLATFORM_THICKNESS_MM
from cone_stack_end_play import SHAFT_END_PLAY
from cone_stations import PIVOT_STATION, T006_NORTH_FACE

# The sheet unit the registry row declares; every band below is read for it.
UNIT = drawing_unit("parts/dt-cone-tip-block", _config.parts("dt-cone-tip-block"))


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
# U24b (2026-09-23): the adjuster thread's side walls keep the wall target at
# the printed width and passage-centre bands.
# r3 (user ruling, Main option (a), 2026-09-25): the narrowest width whose
# lower limit keeps the 5/8 pinch screw (McMaster 91794A112)
# PINCH_SCREW_RECESS_MM short of the -X face (asserted with the screw below).
BLOCK_X = 17.018  # .67 plan width across the shaft
# Plan depth along the shaft: cone_tip_cluster's BLOCK_DEPTH_MM, deep enough
# for 1.5 D of the 1/4-28 end screw's full thread past both mouth
# countersinks at the printed limits (END_SCREW_EMBED_WINDOW below; owner
# decision C1 keyed, 2026-11-09, PR #1992).  It prints .XX: the window holds
# at the title block's +/-.01 (machinist review of PR 2's farm proof, rule 3:
# engagement is no clearance, wall or floor, and rule 19: no band tightened
# to rescue a thread).  Its half, the pinch hole's and the foot tap's
# station, is .215, off the .01 grid, so both print .XXX.
BLOCK_Z = cone_tip_cluster.BLOCK_DEPTH_MM  # .430

# Owner decision C1 keyed (2026-11-09, PR #1992): MHA-DT-04 now ends inside
# T024, so the block moved south to keep the end screw on T006's pivot (the
# research put its south face .300 off the layout T006 north face).  It stays
# a straight prism held by one screw in a fixed platform hole under its
# centre (user ruling 2026-09-29), so the platform's HoldDownZ prints the
# centre's offset from the pivot, on the .001 in grid so it prints exactly.
# Owner ruling 2026-11-09 (relayed by ImplementC1KeyedOpus): .738, .033 south
# of the research's station, so the end screw reaches the bushing with its
# head clear at every limit of the tip's axial stack
# (build_dt_drive_train_assembly's END_SCREW_EMBED_WORST_MM); the shallow
# side's 1.39D engagement there is an owner exception (ruling 2026-11-09,
# dt-drive-train DT-07).  The realized
# south face stands TIP_BLOCK_GAP_MM (.26747) north of the layout T006 north
# face.  Every consumer reads the block's stations from here.
TIP_BLOCK_PIVOT_OFFSET = 18.7452  # .738
TIP_BLOCK_STATION = PIVOT_STATION - TIP_BLOCK_PIVOT_OFFSET
TIP_BLOCK_NORTH_FACE = TIP_BLOCK_STATION + BLOCK_Z / 2.0
TIP_BLOCK_SOUTH_FACE = TIP_BLOCK_STATION - BLOCK_Z / 2.0
TIP_BLOCK_NORTH_FACE_PIVOT_OFFSET = PIVOT_STATION - TIP_BLOCK_NORTH_FACE  # .523
TIP_BLOCK_GAP_MM = TIP_BLOCK_SOUTH_FACE - T006_NORTH_FACE  # .26747

# The adjuster and cone journal share one height above the platform top.
# Free material above the slit floor and the pinch screw's rise stay fixed.
ADJUSTER_AXIS_HEIGHT = CONE_AXIS_HEIGHT_MM
# User ruling U24b (2026-09-23, W-target): the pinch screw sits about 8.9 mm
# above the adjuster axis and the top about 14.5 mm above it, so the slit-mouth
# web between the pinch clearance hole and the adjuster thread root, and the
# ligament over the pinch hole, both keep the wall target after edge breaks at
# the printed limits.
# r3 (codex FIX review of 72ab, 2026-09-25): the print locates the pinch hole
# straight from the foot (PinchHeight, .XX) rather than chaining it off the
# adjuster axis.  PINCH_RISE stays the design offset; it no longer prints.
BLOCK_HEIGHT = 52.578  # 2.07
TOP_ABOVE_AXIS = BLOCK_HEIGHT - ADJUSTER_AXIS_HEIGHT
PINCH_HEIGHT = 46.99  # 1.85
PINCH_RISE = PINCH_HEIGHT - ADJUSTER_AXIS_HEIGHT
# The printed grade of every dimension a stack reads; DRAWING_PRECISION must
# carry the same (checked at the end of this module).  Every dimension prints
# the title block's general band for its places (machinist review of
# d84a42ca7: the former explicit +/-0.10 on the axis height and the tap's
# stations had no fit the reader could see; the stacks close at .XX and .XXX).
# The width's band lands on the +X face (PassageCenter and FootTapX locate
# from the -X face), which stands over the plate's narrow west edge
# (build_dt_drive_train_assembly's print-worst containment).  Machinist
# review of 83e3370f9 (rules 4 and 19, gating): a symmetric .XXX band bought
# that containment with a tight band on a size that only has to stay inside
# an edge.  The face may only come in, so the width carries a one-sided band
# under its nominal (rule 3: the band tolerances it, its places only
# spell it): containment holds at the nominal and the -X-face webs and the
# pinch screw's tip recess hold at its lower limit.
BLOCK_WIDTH_BAND = (0.0, -0.508)  # +.000/-.020
BLOCK_WIDTH_PLACES = 2
BLOCK_DEPTH_PLACES = 2
BLOCK_HEIGHT_PLACES = 2
# .XX: the tip's vertical alignment with the post journal
# (build_dt_drive_train_assembly's vertical take-up) reads this band.
AXIS_HEIGHT_PLACES = 2
PINCH_HEIGHT_PLACES = 2
PASSAGE_CENTER_PLACES = 3
# The pinch hole stands .22 from the north face, on the .01 grid at .XX
# (machinist review of PR 2's farm proof, rule 3: no function needs the
# .XXX its old half-depth station .215 printed), .005 south of the block's
# half depth; PINCH_Z is its centre off the half depth (model +Z north).
PINCH_DEPTH_CENTER = 5.588  # .22
PINCH_DEPTH_PLACES = 2
PINCH_Z = BLOCK_Z / 2.0 - PINCH_DEPTH_CENTER
SLIT_W_PLACES = 2
# The slit depth does not print: its modelled floor stands wholly inside the
# adjuster tap drill (checked below), so the print says SLOT INTO BORE on the
# slit width instead.  The floor stays 0.65 under the axis: inside the 1/4-28
# tap drill by the margins checked below.
SLIT_FLOOR = ADJUSTER_AXIS_HEIGHT - 0.65
SLIT_W = 1.27  # .05
SLIT_DEPTH = BLOCK_HEIGHT - SLIT_FLOOR
# Owner decision C1 keyed (2026-11-09, PR #1992): the end screw, McMaster
# 91794A558 (1/4-28 x 5/8 slotted fillister, 18-8; MHA-DT-39 with its reamed
# pivot hole), threads through the block from the north face; its end bears
# on the brass bushing pressed on T006's pivot and sets the shaft's end play
# (cone_stack_end_play.SHAFT_END_PLAY); the pinch slit locks it.  The thread
# is tapped THROUGH with a 90-degree countersink at both mouths (rule 18 E11/W1,
# Main 2026-09-24: no floor to break out, no tap lead to deduct).
ADJUSTER_THREAD = cone_tip_cluster.ADJUSTER_THREAD
if end_screw_stock.THREAD != ADJUSTER_THREAD or (
    end_screw_stock.SKU != cone_tip_cluster.END_SCREW_SKU
):
    raise AssertionError("the end screw stock is not the tip cluster's 1/4-28 screw")
ADJUSTER_BORE_SPEC = HoleSpec("tapped", ADJUSTER_THREAD)
ADJUSTER_BORE_DIA = blind_cut_dia_mm(ADJUSTER_BORE_SPEC)
_ADJ_MAJOR_MM = THREAD_MAJOR_MM[ADJUSTER_THREAD]
_ADJ_TPI = int(ADJUSTER_THREAD.rsplit("-", 1)[1])
ADJUSTER_PITCH_MM = 25.4 / _ADJ_TPI
# ASME B1.1 unified-inch thread data, derived from the size and pitch (in
# inches): the 2B minimum minor is the basic minor D - 1.082532 P and the 2B
# minimum pitch diameter the basic D - 0.649519 P; the 2B pitch-diameter
# tolerance is 1.30 x the 2A one, 0.0015 D^(1/3) + 0.0015 (9P)^(1/2)
# + 0.015 P^(2/3) (length of engagement 9P).  The formula reads .0001 over
# the 1/4-28 table (.0043), the conservative side for every wall and float.
_D_IN, _P_IN = _ADJ_MAJOR_MM / 25.4, 1.0 / _ADJ_TPI
ADJUSTER_MINOR_MIN_DIA = (_D_IN - 1.082532 * _P_IN) * 25.4
if ADJUSTER_BORE_DIA < ADJUSTER_MINOR_MIN_DIA:
    raise AssertionError("the adjuster tap drill cuts under the 2B minimum minor")
_ADJ_PD_2B_TOL_IN = 1.30 * (
    0.0015 * _D_IN ** (1.0 / 3.0) + 0.0015 * math.sqrt(9.0 * _P_IN) + 0.015 * _P_IN ** (2.0 / 3.0)
)
ADJUSTER_PITCH_DIA_LIMITS_MM = (
    (_D_IN - 0.649519 * _P_IN) * 25.4,
    (_D_IN - 0.649519 * _P_IN + _ADJ_PD_2B_TOL_IN) * 25.4,
)
# 90-degree countersink on each mouth to .007 in over the major, so the first
# thread starts full rather than on a feather edge (Main, 2026-09-24).  Its
# depth is the 45-degree break on the tap drill;
# the callout prints its diameter .XXX, so the engagement books the deepest
# countersink that band allows.
ADJUSTER_CSK_DIA = _ADJ_MAJOR_MM + 0.007 * 25.4  # .257
ADJUSTER_CSK = (ADJUSTER_CSK_DIA - ADJUSTER_BORE_DIA) / 2.0
if ADJUSTER_CSK_DIA < _ADJ_MAJOR_MM:
    raise AssertionError("adjuster countersink ends inside the thread major")
PINCH_THREAD = "#4-40"  # cross-bore tapped hole that squeezes the top slit
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

# Prove every web against what the PRINT permits, not just nominal CAD (the
# wall target at the worst case of the printed bands).
_DRILLED_HOLE_PLUS_MM = _printed_tolerance.drilled_oversize_mm(unit=UNIT)


def _printed_limits(nominal: float, places: int) -> tuple[float, float]:
    """(min, max) the print allows a general-tolerance dimension."""
    lower, upper = _printed_tolerance.printed_deviations(nominal, places, unit=UNIT)
    return nominal + lower, nominal + upper


# (min, max) of the width, which carries its own band rather than a grade.
_width_lower, _width_upper = deviations(BLOCK_WIDTH_BAND)
BLOCK_WIDTH_LIMITS = (BLOCK_X + _width_lower, BLOCK_X + _width_upper)


def printed_band_mm(places: int) -> float:
    """Half-width of the title block's general band at ``places`` decimals."""
    return _printed_tolerance.printed_band_mm(places, unit=UNIT)


AXIS_HEIGHT_TOL_MM = printed_band_mm(AXIS_HEIGHT_PLACES)


# r3 (Main, 2026-09-25): PassageCenter prints from the -X face, which the
# plate frame puts on the east.  The +X (west) face carries only the pinch
# screw's head, so the width's band lands on that side, where the swing
# platform's trimmed west edge bounds it (BLOCK_WIDTH_BAND;
# build_dt_drive_train_assembly asserts the print-worst containment).
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
    width = BLOCK_WIDTH_LIMITS
    far = width[1] - passage[0]
    if datum == "-X":
        return {"-X": passage[1], "+X": far}
    return {"+X": passage[1], "-X": far}


WORST_HALF_WIDTH_MM = worst_half_widths_mm(PASSAGE_CENTER_DATUM)

# Title block: REMOVE BURRS AND BREAK SHARP EDGES.  Where a web ends in two
# exposed edges (the slit mouth, the pinch-hole mouth under the top face) both
# breaks come off the same web.
EDGE_BREAK_MAX_MM = max(
    _printed_tolerance.edge_break_radius_mm(unit=UNIT),
    _printed_tolerance.edge_break_chamfer_mm(unit=UNIT),
)
MIN_WEB_MM = WALL_TARGET_MM
# ASME B1.1 UNF-2B has no specified maximum major diameter; its section
# 5.8.2(a) reference envelope (basic major + 0.14433757P + the 2B
# pitch-diameter tolerance) stands in for the finished thread root.
ADJUSTER_ROOT_REF_DIA = (
    _ADJ_MAJOR_MM + 0.14433757 * ADJUSTER_PITCH_MM + _ADJ_PD_2B_TOL_IN * 25.4
)
_root_r = ADJUSTER_ROOT_REF_DIA / 2.0
_worst_clearance_radius = (PINCH_CLEARANCE_DIA + _DRILLED_HOLE_PLUS_MM) / 2.0
_min_slit_half = _printed_limits(SLIT_W, SLIT_W_PLACES)[0] / 2.0
_adjuster_major_radius = _ADJ_MAJOR_MM / 2.0
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
# PinchHeight prints .XX for this ligament.
WORST_TOP_LIGAMENT_MM = (
    _height_limits[0]
    - _pinch_limits[1]
    - _worst_clearance_radius
    - 2.0 * EDGE_BREAK_MAX_MM
)
_width_limits = BLOCK_WIDTH_LIMITS
_depth_limits = _printed_limits(BLOCK_Z, BLOCK_DEPTH_PLACES)
WORST_ADJUSTER_SIDE_LIGAMENT_MM = (
    _width_limits[0]
    - _printed_limits(BLOCK_X / 2.0, PASSAGE_CENTER_PLACES)[1]
    - _root_r
)
# The thinner (south) side of the pinch hole: it stands south of half depth.
WORST_PINCH_DEPTH_LIGAMENT_MM = (
    _depth_limits[0]
    - _printed_limits(PINCH_DEPTH_CENTER, PINCH_DEPTH_PLACES)[1]
    - _worst_clearance_radius
)
if PINCH_Z > 0.0:
    raise AssertionError("the pinch hole's thinner side is no longer its south side")
for _name, _web in (
    ("slit-mouth web", WORST_SLIT_MOUTH_WEB_MM),
    ("top ligament", WORST_TOP_LIGAMENT_MM),
    ("adjuster side wall", WORST_ADJUSTER_SIDE_LIGAMENT_MM),
    ("pinch-depth ligament", WORST_PINCH_DEPTH_LIGAMENT_MM),
):
    if round(_web, 6) < MIN_WEB_MM:
        raise AssertionError(
            f"{_name} is {_web:.3f} at the printed limits (< the .080 in wall target)"
        )
if WORST_SCREW_ENVELOPE_GAP_MM <= 0.0:
    raise AssertionError("pinch screw can collide with the installed adjuster")
# The slit must open into the adjuster thread or its jaws never grip it.  The
# print states that extent (SLOT INTO BORE) rather than a depth: the model's
# floor (SlitDepth down from the top) stands wholly inside the tap drill, so
# the cut leaves no floor face to measure to.  WORST_SLIT_BREAKTHROUGH_MM is
# how far that modelled floor stands under the tap-drill crown.  Below the
# crown the slit may run on: the jaws only lengthen.
SLIT_BREAKTHROUGH_MARGIN_MM = 0.25
WORST_SLIT_BREAKTHROUGH_MM = ADJUSTER_AXIS_HEIGHT + ADJUSTER_BORE_DIA / 2.0 - SLIT_FLOOR
if WORST_SLIT_BREAKTHROUGH_MM < SLIT_BREAKTHROUGH_MARGIN_MM - 1e-9:
    raise AssertionError(
        f"slit floor stops {WORST_SLIT_BREAKTHROUGH_MM:.3f} short of breaking "
        f"into the adjuster thread (< {SLIT_BREAKTHROUGH_MARGIN_MM})"
    )
if (
    math.hypot(SLIT_FLOOR - ADJUSTER_AXIS_HEIGHT, SLIT_W / 2.0)
    >= ADJUSTER_BORE_DIA / 2.0
):
    raise AssertionError(
        "the slit floor leaves a face outside the adjuster tap drill; "
        "SLOT INTO BORE no longer describes it"
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
# drawing-guidelines.md rule 18 (thread engagement) E1 (user ruling, Main option (a), 2026-09-25): a #4-40 x 5/8 18-8
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
# --- the end screw (owner decision C1 keyed, 2026-11-09, PR #1992) ----------
# MHA-DT-00 runs the end screw in until the shaft just stops shuttling, then
# backs it off for SHAFT_END_PLAY; the model sets it at the play's middle.
# Its end face then stands on T006's pivot at the layout T006 north face plus
# the tip set's shift (cone_tip_cluster.TIP_SET_SHIFT_MM, the shaft pushed onto
# the MHA-DT-05 boss), the bushing's length and that play.
END_SCREW_SKU = cone_tip_cluster.END_SCREW_SKU
END_SCREW_LENGTH = end_screw_stock.SHANK_LEN  # 5/8 under the head
# ASME B18.6.3 (cited, the build_pd_platen_clip precedent): length +0/-0.03 in
# through 1 in; a point chamfer of at most 2P; on lengths of three diameters
# and shorter, full form thread to within 1P of the head's bearing surface
# (2P only past 3 D; B18.6.3 as tabled in Machinery's Handbook, 26th ed.,
# Machine Screws).
END_SCREW_LENGTH_MIN = END_SCREW_LENGTH - 0.03 * 25.4
END_SCREW_POINT_MAX_MM = 2.0 * ADJUSTER_PITCH_MM
END_SCREW_HEAD_RUNOUT_MM = ADJUSTER_PITCH_MM
if END_SCREW_LENGTH > 3.0 * _ADJ_MAJOR_MM:
    raise AssertionError("the end screw is past 3 D: B18.6.3's head runout is longer")
END_SCREW_MODEL_END_PLAY_MM = (SHAFT_END_PLAY[0] + SHAFT_END_PLAY[1]) / 2.0  # 0.15
END_SCREW_END_STATION = (
    T006_NORTH_FACE
    + cone_tip_cluster.TIP_SET_SHIFT_MM
    + cone_tip_cluster.BUSHING_LENGTH_MM
    + END_SCREW_MODEL_END_PLAY_MM
)
# The screw's end face measured in from the block's north face (the screw's
# end stands END_SCREW_EMBED - BLOCK_Z proud of the south face toward the
# cone, its head END_SCREW_LENGTH - END_SCREW_EMBED off the north face).
END_SCREW_EMBED = TIP_BLOCK_NORTH_FACE - END_SCREW_END_STATION
# drawing-guidelines.md rule 18: 1.5 D of full thread past both mouth
# countersinks (the deepest the callout's .XXX diameter allows).  The block's
# full thread is its depth less both; the screw's runs from 1P under its
# head to 2P short of its end.  The depth prints .XX (rule 19: no band is
# tightened to rescue a thread), so at its shallowest the block holds
# END_SCREW_ENGAGEMENT_MIN_MM, 1.48 D: the engagement floor is that or 1.5 D,
# whichever is less.  The tip's engagement at the printed limits is
# build_dt_drive_train_assembly's END_SCREW_ENGAGEMENT_WORST_D (1.39 D at the
# stack's shallow end, owner ruling 2026-11-09 via PR #1992), stated there.
# In embed (from the north face, south positive) the window is: shallow, the
# screw's full thread ends the floor past the north countersink; deep, the
# shortest screw's head runout leaves the floor above the south countersink
# of the shallowest block, and its head stands END_SCREW_HEAD_AIR_MM off the
# north face.  The screw's full thread (L - 3P) is longer than 1.5 D, so
# inside the window the engagement is never under the floor.
END_SCREW_MIN_ENGAGEMENT_D = 1.5
END_SCREW_HEAD_AIR_MM = 0.25
_csk_dia_max = _printed_limits(ADJUSTER_CSK_DIA, 3)[1]
ADJUSTER_CSK_MAX = (_csk_dia_max - ADJUSTER_BORE_DIA) / 2.0
END_SCREW_ENGAGEMENT_MIN_MM = _depth_limits[0] - 2.0 * ADJUSTER_CSK_MAX
_ENGAGEMENT_FLOOR_MM = min(
    END_SCREW_MIN_ENGAGEMENT_D * _ADJ_MAJOR_MM, END_SCREW_ENGAGEMENT_MIN_MM
)
if END_SCREW_LENGTH_MIN - END_SCREW_POINT_MAX_MM - END_SCREW_HEAD_RUNOUT_MM < (
    END_SCREW_MIN_ENGAGEMENT_D * _ADJ_MAJOR_MM
):
    raise AssertionError("the end screw's own full thread is under 1.5 D")
# The deepest the shortest screw can reach before its head comes within
# END_SCREW_HEAD_AIR_MM of the north face.
END_SCREW_REACH_MAX_EMBED_MM = END_SCREW_LENGTH_MIN - END_SCREW_HEAD_AIR_MM


def end_screw_full_thread_mm(embed_mm: float) -> float:
    """Least full thread the end screw shares with the block at ``embed_mm``
    (its end face that far in from the north face): the screw's full thread
    from its 2P point back, or the shortest screw's from 1P under its head,
    whichever ends first, against the shallowest block's thread between its
    deepest countersinks."""
    return min(
        embed_mm - ADJUSTER_CSK_MAX - END_SCREW_POINT_MAX_MM,
        END_SCREW_LENGTH_MIN
        - END_SCREW_HEAD_RUNOUT_MM
        + _depth_limits[0]
        - ADJUSTER_CSK_MAX
        - embed_mm,
        END_SCREW_ENGAGEMENT_MIN_MM,
    )


END_SCREW_EMBED_WINDOW = (
    ADJUSTER_CSK_MAX + _ENGAGEMENT_FLOOR_MM + END_SCREW_POINT_MAX_MM,
    min(
        END_SCREW_LENGTH_MIN
        - END_SCREW_HEAD_RUNOUT_MM
        + _depth_limits[0]
        - ADJUSTER_CSK_MAX
        - _ENGAGEMENT_FLOOR_MM,
        END_SCREW_REACH_MAX_EMBED_MM,
    ),
)
for _edge in END_SCREW_EMBED_WINDOW:
    if end_screw_full_thread_mm(_edge) < _ENGAGEMENT_FLOOR_MM - 1e-9:
        raise AssertionError("the end screw's window edge leaves under its floor")
# At the block's printed limits the screw must reach the bushing over the
# whole set end play: the model's end play less the least lies at the deep
# end, the most at the shallow end.
END_SCREW_EMBED_RANGE_MM = (
    END_SCREW_EMBED - (SHAFT_END_PLAY[1] - END_SCREW_MODEL_END_PLAY_MM),
    END_SCREW_EMBED + (END_SCREW_MODEL_END_PLAY_MM - SHAFT_END_PLAY[0]),
)
if not (
    END_SCREW_EMBED_WINDOW[0] <= END_SCREW_EMBED_RANGE_MM[0]
    and END_SCREW_EMBED_RANGE_MM[1] <= END_SCREW_EMBED_WINDOW[1]
):
    raise AssertionError(
        f"end screw embed {END_SCREW_EMBED_RANGE_MM[0]:.3f}..{END_SCREW_EMBED_RANGE_MM[1]:.3f} "
        f"over the set end play leaves its engagement window {END_SCREW_EMBED_WINDOW[0]:.3f}.."
        f"{END_SCREW_EMBED_WINDOW[1]:.3f}"
    )
# The nominal screw end proud of the south face, and head off the north face.
END_SCREW_END_PROUD_MM = END_SCREW_EMBED - BLOCK_Z
END_SCREW_HEAD_GAP_MM = END_SCREW_LENGTH - END_SCREW_EMBED
if END_SCREW_END_PROUD_MM <= 0.0 or END_SCREW_HEAD_GAP_MM <= END_SCREW_HEAD_AIR_MM:
    raise AssertionError("the end screw does not stand proud at both faces")
# The end screw's radial float in the 1/4-28 thread: the 2B internal pitch
# diameter (ADJUSTER_PITCH_DIA_LIMITS_MM) over the 2A external one (B1.1:
# maximum = basic less the 0.300 x Td2 allowance; the stock row's minimum).
_td2_2a_in = _ADJ_PD_2B_TOL_IN / 1.30
_external_pd_max = ADJUSTER_PITCH_DIA_LIMITS_MM[0] - 0.300 * _td2_2a_in * 25.4
END_SCREW_THREAD_FLOAT_MM = (
    (ADJUSTER_PITCH_DIA_LIMITS_MM[0] - _external_pd_max) / 2.0,
    (ADJUSTER_PITCH_DIA_LIMITS_MM[1] - end_screw_stock.EXTERNAL_PITCH_DIA_MIN_MM) / 2.0,
)
if END_SCREW_THREAD_FLOAT_MM[0] <= 0.0:
    raise AssertionError("the 1/4-28 2A/2B fit leaves the end screw no float")
# The vertical take-up (owner decision 2026-11-09 via ImplementC1KeyedOpus,
# rule 19 matched fit): T006's pivot runs in the end screw's reamed hole, so
# the end screw's axis must stand at the MHA-DT-05 journal's height.  The
# post's .XX journal height and this block's .XX AxisHeight would leave the
# tip +/-.020 off; instead AxisHeight is made to the measured MHA-DT-05
# journal-axis height above MHA-DT-20 (its general band still bounds the
# absolute value) within this match residual.  build_dt_drive_train_assembly
# books it against the shaft's tilt in the journal, the screw's float in its
# thread and the pivot's running clearance.  ASSUMPTION: the pinch locks the
# screw where the seated pivot holds it (MHA-DT-00 steps 4N/4T turn MHA-DT-07
# a full turn after locking: it never binds).
AXIS_HEIGHT_MATCH_RESIDUAL_MM = 0.0762  # +/-.003
AXIS_HEIGHT_MATCH_MATE = "MHA-DT-05"

# --- hold-down (user ruling 2026-09-29) --------------------------------------
# One McMaster 91251A108 #4-40 x 3/8 black-oxide alloy socket head cap screw
# (MHA-DT-VN-60) rises from the swing platform's underside counterbore through a
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
# plate's stock band and its .XXX counterbore depth
# (dt_cone_swing_platform_spec.HOLDDOWN_LEDGE_RANGE, asserted equal in
# build_dt_drive_train_assembly; a copy so this part does not re-key on the
# platform's print).
HOLDDOWN_LEDGE_RANGE_MM = (2.5908, 3.0988)
# The block's foot sits on the platform top, so the screw reaches past the
# ledge straight into the tap.
WORST_HOLDDOWN_ENGAGEMENT_MM = HOLDDOWN_SCREW_LENGTH_MIN - HOLDDOWN_LEDGE_RANGE_MM[1]
WORST_HOLDDOWN_REACH_MM = HOLDDOWN_SCREW_LENGTH - HOLDDOWN_LEDGE_RANGE_MM[0]
if WORST_HOLDDOWN_ENGAGEMENT_MM < 1.5 * _HOLDDOWN_MAJOR_MM:
    raise AssertionError(
        f"hold-down engagement {WORST_HOLDDOWN_ENGAGEMENT_MM:.3f} < 1.5D at the "
        "thickest ledge and shortest screw"
    )
# Full-thread depth keeps the longest reach FOOT_TAP_MARGIN_MM clear of
# the tap's incomplete lead; the tap drill runs 1.5P past the deepest
# full thread so a plug tap's lead never eats it.  Both print on the
# tap's Hole Wizard callout at .XX: the reach and lead checks pass at
# the two-place band (machinist review: nothing reads the depths finer).
FOOT_TAP_MARGIN_MM = 0.25
FOOT_THREAD_DEPTH = 8.636  # .34
FOOT_DEPTH = 11.176  # .44
FOOT_DEPTH_PLACES = 2
_FOOT_DEPTH_BAND_MM = printed_band_mm(FOOT_DEPTH_PLACES)
if WORST_HOLDDOWN_REACH_MM > FOOT_THREAD_DEPTH - _FOOT_DEPTH_BAND_MM - FOOT_TAP_MARGIN_MM:
    raise AssertionError("hold-down screw can reach the foot tap's incomplete threads")
if (FOOT_DEPTH - _FOOT_DEPTH_BAND_MM) - (FOOT_THREAD_DEPTH + _FOOT_DEPTH_BAND_MM) < (
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
# The tap's two stations, each .XXX on the title block's band: across the
# block from the -X face (the PassageCenter datum), and along the axis from
# the NORTH face, the face the pivot screw's head gap is measured to
# (build_dt_drive_train_assembly's pivot-head, embed and lateral stacks read
# this band; at .XX the pivot head's air and the post's lateral take-up
# fail).  The tap sits FOOT_TAP_OFFSET_X off the adjuster axis, the
# same offset as the platform's hold-down hole off the cone line
# (dt_cone_swing_platform_spec.HOLDDOWN_LOCAL_X, which says why), so the block
# body stands centred on the cone line.  Toward -X because the width's band
# falls on the +X side: there the tap's web is the thinner one.
FOOT_TAP_OFFSET_X = -1.016  # -.04
FOOT_TAP_X = BLOCK_X / 2.0 + FOOT_TAP_OFFSET_X
FOOT_TAP_Z = BLOCK_Z / 2.0
FOOT_TAP_X_PLACES = 3
FOOT_TAP_Z_PLACES = 3
if FOOT_TAP_X_PLACES != FOOT_TAP_Z_PLACES:
    raise AssertionError("the stacks read one band for both foot tap stations")
FOOT_TAP_STATION_TOL_MM = printed_band_mm(FOOT_TAP_X_PLACES)
_tap_r = _HOLDDOWN_MAJOR_MM / 2.0
_tap_drill_top_max = (
    FOOT_DEPTH
    + _FOOT_DEPTH_BAND_MM
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
            f"foot tap {_name} web is {_web:.3f} at the printed limits "
            "(< the .080 in wall target)"
        )

# --- locating dowel ------------------------------------------------------------
# Rule-23 retention, owner ruling 2026-11-07 (MHA-DT-00 rubric sample, PR
# #2248).  One hold-down screw alone lets the adjuster's thrust,
# acting off the screw, turn the block on the plate (rule 23: retain every
# fixed joint).  A 1/16 x 3/8 dowel (MHA-DT-VN-69, dt_vn_locating_pin_spec)
# stands on the hold-down line beside the screw, pressed into a blind ream in
# this foot and slipping through MHA-DT-20.  At MHA-DT-00 step
# post-and-tip-block, with the block squared and snug on its screw, the fitter
# drills and reams up through MHA-DT-20 into the foot to the pin's press size
# (this hole's callout), opens the MHA-DT-20 hole to its slip size from below
# (its callout; the block stays on), then presses the pin up through
# MHA-DT-20 to this hole's floor (the step says so; machinist review of round
# 6, #1: not this sheet).  Block and pin are a permanent pair (round 6, #0):
# the pin stays pressed in the foot, slips in the plate, and the two lift off
# MHA-DT-20 together, so the blind ream needs no knockout or extraction thread.
#
# Its station: on the foot tap's line (the block's mid-depth), DOWEL_FROM_TAP
# toward +X from the tap, the same centre distance the platform prints from
# its hold-down hole (dt_cone_swing_platform_spec.TIP_DOWEL_FROM_HOLDDOWN).
# The value centres the window the two print-worst webs leave on the .001 in
# grid: the platform's web to its hold-down counterbore and this foot's web to
# the +X face at the width's lower limit (both checked below and in
# dt_cone_swing_platform_checks).  DOWEL_FROM_TAP stays the internal
# relation; the print states DOWEL_X, a baseline from the -X face (the
# FootTapX datum), as a REFERENCE dimension (machinist review of round 6, #9):
# the hole is match-drilled from MHA-DT-20, so it is wherever the plate puts
# it, and the sheet gives the fitter the nominal to check against.
DOWEL_FROM_TAP = 5.7912  # .228
DOWEL_X = FOOT_TAP_X + DOWEL_FROM_TAP  # .523 from the -X face, FOOT_TAP_X's frame
DOWEL_Z = FOOT_TAP_Z
DOWEL_X_PLACES = 3
# The hole is drilled from the platform, so where it lands from the tap is the
# platform's station band (+/-.004 from its hold-down hole) plus the hold-down
# screw's float in its .120 close-clearance hole (.006): the webs below take
# that sum (dt_cone_swing_platform_spec asserts it covers both).  It does not
# print: the REF station carries no band.
DOWEL_X_TOL_MM = 0.254  # +/-.010
# Off the tap's line the same float applies, plus the general .XX band of the
# platform's in-line relation to its hold-down hole.
DOWEL_Z_TOL_MM = DOWEL_X_TOL_MM + printed_band_mm(2)
# The pin's press: the shared .0620 REAM_H7 light-press contract
# (dt_vn_locating_pin_spec.PRESS_HOLE_DIA/BAND, interference checked there).
DOWEL_HOLE_DIA = locating_pin.PRESS_HOLE_DIA  # 1.5748, .0620
DOWEL_HOLE_BAND = locating_pin.PRESS_HOLE_BAND  # +.0005/-.0000
DOWEL_HOLE_PLACES = 4
_dowel_hole_lower, _dowel_hole_upper = deviations(DOWEL_HOLE_BAND)
DOWEL_HOLE_LIMITS = (
    DOWEL_HOLE_DIA + _dowel_hole_lower,
    DOWEL_HOLE_DIA + _dowel_hole_upper,
)
DOWEL_PRESS_INTERFERENCE_MM = locating_pin.PRESS_INTERFERENCE_MM
# Reamed full diameter to a flat floor this deep from the foot (.XX); the pin
# is pressed up to the floor, so the depth is its stand above the plate top
# and its grip in the foot.  The depth's lower limit keeps the longest pin's
# lower end inside the thinnest plate (the underside slides on the base deck),
# and grips 1.5 pin diameters.
DOWEL_HOLE_DEPTH = 4.064  # .16
DOWEL_HOLE_DEPTH_PLACES = 2
DOWEL_HOLE_DEPTH_LIMITS = (
    DOWEL_HOLE_DEPTH - printed_band_mm(DOWEL_HOLE_DEPTH_PLACES),
    DOWEL_HOLE_DEPTH + printed_band_mm(DOWEL_HOLE_DEPTH_PLACES),
)  # (.15, .17)
if DOWEL_HOLE_DEPTH_LIMITS[0] < 1.5 * locating_pin.DIA:
    raise AssertionError("MHA-DT-VN-69 grips under 1.5D in the foot's press ream")
# The pin's lower end above the plate's underside: the plate less the pin's
# reach below the plate top (its length less the depth it stands in the
# foot).  The range takes the pin's +/-.010 length grade, this depth's .XX
# and the plate's mill band (a copy of dt_cone_swing_platform_spec.
# PLATE_STOCK_BAND, asserted equal there, so this part does not re-key on the
# platform's print).
PLATE_STOCK_BAND_MM = 0.127  # +/-.005
DOWEL_END_ABOVE_UNDERSIDE = (
    PLATFORM_THICKNESS_MM + DOWEL_HOLE_DEPTH - locating_pin.LENGTH
)  # .035
DOWEL_END_ABOVE_UNDERSIDE_RANGE_MM = (
    PLATFORM_THICKNESS_MM
    - PLATE_STOCK_BAND_MM
    + DOWEL_HOLE_DEPTH_LIMITS[0]
    - locating_pin.LENGTH_LIMITS_MM[1],
    PLATFORM_THICKNESS_MM
    + PLATE_STOCK_BAND_MM
    + DOWEL_HOLE_DEPTH_LIMITS[1]
    - locating_pin.LENGTH_LIMITS_MM[0],
)  # (.010, .060)
if DOWEL_END_ABOVE_UNDERSIDE_RANGE_MM[0] < 0.0:
    raise AssertionError("MHA-DT-VN-69 can stand proud of MHA-DT-20's underside")
# Its length in the plate's slip hole, which locates the block: the shortest
# pin less the deepest ream, at least 1.5 pin diameters.
DOWEL_IN_PLATE_MIN_MM = locating_pin.LENGTH_LIMITS_MM[0] - DOWEL_HOLE_DEPTH_LIMITS[1]
if DOWEL_IN_PLATE_MIN_MM < 1.5 * locating_pin.DIA:
    raise AssertionError("MHA-DT-VN-69 engages MHA-DT-20 under 1.5D")
# Webs round the hole at the printed limits: its station band from the tap,
# the tap's own band from the faces, the width's lower limit, the depth's
# .XX, the hole at its upper limit; the drill's 118-degree point past the
# deepest ream stays far under the adjuster thread.
_dowel_r = DOWEL_HOLE_LIMITS[1] / 2.0
_dowel_top_max = DOWEL_HOLE_DEPTH_LIMITS[1] + _dowel_r / math.tan(
    math.radians(DRILL_POINT_ANGLE_DEG / 2.0)
)
WORST_DOWEL_WEBS_MM = {
    "+X face": _width_limits[0]
    - (FOOT_TAP_X + FOOT_TAP_STATION_TOL_MM)
    - (DOWEL_FROM_TAP + DOWEL_X_TOL_MM)
    - _dowel_r,
    "foot tap": DOWEL_FROM_TAP - DOWEL_X_TOL_MM - _tap_r - _dowel_r,
    "north face": DOWEL_Z - FOOT_TAP_STATION_TOL_MM - DOWEL_Z_TOL_MM - _dowel_r,
    "south face": _depth_limits[0]
    - (DOWEL_Z + FOOT_TAP_STATION_TOL_MM + DOWEL_Z_TOL_MM)
    - _dowel_r,
    "adjuster thread": _axis_limits[0] - ADJUSTER_ROOT_REF_DIA / 2.0 - _dowel_top_max,
}
for _name, _web in WORST_DOWEL_WEBS_MM.items():
    if round(_web, 6) < MIN_WEB_MM:
        raise AssertionError(
            f"locating dowel {_name} web is {_web:.3f} at the printed limits "
            "(< the .080 in wall target)"
        )

SURFACE_FINISHES = (
    # This face locates the adjuster block on the swing platform. Everything
    # else remains governed by the title-block CAST/MACHINED process row.
    SurfaceFinishControl(
        "foot_seat", SEAT_UM, PlanarFace((0, -1, 0), 0.0), display_unit=UNIT
    ),
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
    # 2026-09-29: the hold-down tap's stations on the foot (hidden reference
    # sketches; the tap's size and depths print on its Hole Wizard callout).
    "FootTapXReference": {"FootTapX"},
    "FootTapZReference": {"FootTapZ"},
    # Rule-23 retention, owner ruling 2026-11-07 (MHA-DT-00 rubric sample, PR
    # #2248): the locating dowel's press ream on the bottom
    # view, its size on the cut's sketch and its REF station from the -X face
    # on a hidden reference sketch.
    "DowelProfile": {"DowelHoleDia"},
    "DowelXReference": {"DowelX"},
}

# Decimal places carry the general tolerance and therefore live on the model.
# U24b: the webs close at the title-block bands.  Still .XX: the pinch-hole
# height (the top ligament closes at 1.92 at .X if 46.95 prints 47.0) and the
# slit width (the drill-to-slot point reaches past the far jaw's tap drill at .X).  2026-09-29:
# with the block fixed by its hold-down, the depth, the passage centre and
# the tap's stations print .XXX, and the axis height .XX (the end screw's
# embed window, the pivot head's air and the lateral stack;
# build_dt_drive_train_assembly proves each looser grade fails).  C1 keyed
# (2026-11-09): the pinch hole's depth station, the block's half depth .215,
# prints .XXX.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlockProfile": {"Width": BLOCK_WIDTH_PLACES, "Depth": BLOCK_DEPTH_PLACES},
    "Block": {"BlockHt": BLOCK_HEIGHT_PLACES},
    "AxisHeightReference": {"AxisHeight": AXIS_HEIGHT_PLACES},
    "PassageCenterReference": {"PassageCenter": PASSAGE_CENTER_PLACES},
    "PinchDepthReference": {"PinchDepthCenter": PINCH_DEPTH_PLACES},
    "PinchHeightReference": {"PinchHeight": PINCH_HEIGHT_PLACES},
    "SlitProfile": {"SlitW": SLIT_W_PLACES},
    "FootTapXReference": {"FootTapX": FOOT_TAP_X_PLACES},
    "FootTapZReference": {"FootTapZ": FOOT_TAP_Z_PLACES},
    "DowelProfile": {"DowelHoleDia": DOWEL_HOLE_PLACES},
    "DowelXReference": {"DowelX": DOWEL_X_PLACES},
}
# The stacks above read these grades; the print must carry exactly them.  The
# width's stacks read its own band (BLOCK_WIDTH_LIMITS), not a grade.
_STACK_GRADES = {
    ("BlockProfile", "Depth"): BLOCK_DEPTH_PLACES,
    ("Block", "BlockHt"): BLOCK_HEIGHT_PLACES,
    ("AxisHeightReference", "AxisHeight"): AXIS_HEIGHT_PLACES,
    ("PassageCenterReference", "PassageCenter"): PASSAGE_CENTER_PLACES,
    ("PinchDepthReference", "PinchDepthCenter"): PINCH_DEPTH_PLACES,
    ("PinchHeightReference", "PinchHeight"): PINCH_HEIGHT_PLACES,
    ("SlitProfile", "SlitW"): SLIT_W_PLACES,
    ("FootTapXReference", "FootTapX"): FOOT_TAP_X_PLACES,
    ("FootTapZReference", "FootTapZ"): FOOT_TAP_Z_PLACES,
}
for (_feature, _dimension), _places in _STACK_GRADES.items():
    if DRAWING_PRECISION[_feature][_dimension] != _places:
        raise AssertionError(
            f"a stack reads {_dimension} at {_places} places; the print carries "
            f"{DRAWING_PRECISION[_feature][_dimension]}"
        )
# VIEW B's two sheet-added stations locate the far-jaw tap in its own view
# (fan-out review: located nowhere in VIEW B), at the tap stations' places.
# Sheet-added dimensions take their places from the spec (rule 3; the
# drawing-purity contract).
DRAWING_REFERENCE_PRECISION: dict[str, int] = {
    "ViewBPinchDepth": PINCH_DEPTH_PLACES,
    "ViewBPinchHeight": PINCH_HEIGHT_PLACES,
}
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


def length_text(value_mm: float, places: int) -> str:
    """A length as the sheet prints it at ``places``, in its unit."""
    return render_number(round(value_mm / LENGTH_UNITS[UNIT], places), UNIT, places)


def printed_value_text(name: str, nominal: float) -> str:
    """The text a marked dimension prints: the value at its model places."""
    return length_text(nominal, DRAWING_PRECISION_BY_NAME[name])


# The two dowel values as the bottom view prints them, for the sheet's ink
# estimate: the station in its reference parentheses, and the ream's size
# with its stacked band's upper row beside it.
DOWEL_X_PRINTED_TEXT = f"({printed_value_text('DowelX', DOWEL_X)})"
DOWEL_HOLE_PRINTED_TEXT = (
    f"Ø{printed_value_text('DowelHoleDia', DOWEL_HOLE_DIA)} "
    f"+{length_text(max(DOWEL_HOLE_BAND), DOWEL_HOLE_PLACES)}"
)
# The matched AxisHeight's requirement, as the sheet's numbered note states
# it (the mate and the residual are this spec's; the drawing only wraps and
# places it).
AXIS_HEIGHT_MATCH_REQUIREMENT = (
    f"AXIS HEIGHT MADE TO THE MEASURED {AXIS_HEIGHT_MATCH_MATE} JOURNAL AXIS "
    f"HEIGHT ABOVE {_config.parts('dt-cone-swing-platform')['number']}, WITHIN "
    f"\u00b1{length_text(AXIS_HEIGHT_MATCH_RESIDUAL_MM, 3)}."
)
