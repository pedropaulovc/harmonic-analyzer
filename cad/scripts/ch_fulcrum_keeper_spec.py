r"""Fulcrum-keeper dimensional contract -- the single source of truth shared by
the part build (``build_ch_fulcrum_keeper.py``), its manufacturing drawing
(``draw_ch_fulcrum_keeper.py``), the channel assembly that places it and the
top frame that carries its foot-screw taps.

PURE DATA, no SolidWorks/COM imports: the nominal geometry (the "editable
knobs"), the keeper's station on the fulcrum shaft, the hole layout the
drawing needs for its view math, the drawing-guidelines.md rule 17 (walls and webs) worst-case wall and thread
terms, and the marked-dimension -> kept-dimension NAME map (see
``pd_guide_lock_spec.py`` for the pattern's build-graph rationale).

The keeper is the black shaft-end bracket of the top-lever fulcrum bank
(book ch. 17 p. 40 bottom-left closeup and ch. 17 p. 2 img08; ch. 30 top view
+ p008): a stubby straight L. Its upright round-topped lug sits right against
the outermost lever hub and carries the plain Ø6.35 fulcrum shaft in a reamed
bore; the shaft's domed end stands proud of the lug's outer face (the bright
dome of the photo). One #1-72 cup-point set screw (MHA-CH-VN-55), tapped down
through the crown top on the lug mid-plane, bears on the shaft's set-screw
flat and fixes the shaft axially and in rotation. The short straight foot
points OUTBOARD, away from the lever bank, and is screwed down into the
top-frame rail top face with one slotted #2-56 fillister screw
(frame-side-screw, MHA-CH-VN-52) seated flush in a counterbore. 2 required, one
per shaft end (the second is the same part flipped Ry180 by the assembly).

Part frame: +X = along the shaft, OUTBOARD (away from the lever bank); +Y up
from the seat; +Z across the width. The lug mid-plane (= set-screw axis) is
x = 0; the lug spans x -4..+4 from the seat to the crown, the foot runs
outboard from the lug's outer face to x = FOOT_TIP_X, and the whole
underside x -4..+12.5 is the flat seat.
"""

from __future__ import annotations

from math import floor, radians, sqrt, tan

import _config
from _fit_shaft_h import SHAFT_H
from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import (
    drilled_oversize_mm,
    edge_break_radius_mm,
    printed_band_mm,
)
from _cone_axis_constants import CHANNEL_Z0, FRAME_FRONT_COLUMN_Z

# #290: the keeper sheet prints decimal inch (its row's ``drawing_unit``).
# Lengths stay millimetres, each fabricated one the exact decimal of its
# printed inch value; the shaft-axis height is the fulcrum's closure and stays
# exact. The frame's receiver tap (KEEPER_TAP_SPEC) prints on MHA-FR-02's
# sheet, still millimetres.
UNIT = drawing_unit("parts/ch-fulcrum-keeper", _config.parts("ch-fulcrum-keeper"))

# --- Station (machine Z). The ONE source for build_ch_channel_assembly
# (shaft, keeper, set-screw and foot-screw placement) and build_fr_top_frame
# (its keeper taps). The shaft and both keepers centre on the lever bank's
# mid-plane: lever j sits on the cam plane, half a solid-stacked gear (half a
# pitch) south of station z_j, its hub one pitch long, so the 20-lever bank is
# centred CHANNEL_Z0 - pitch/2 + 19 pitch/2 and both lugs see the same float
# to the end hubs. Literals rather than machine config, so the frame does not
# re-key on machine/channels.yaml; build_ch_channel_assembly asserts the
# result equals rocker_bank_layout.STACK_MID_Z. ---
_STATION_PITCH = 7.62  # machine channels.station_pitch_mm, .300
_BANK_COUNT = 20  # the full lever bank (never follows active_count)
FULCRUM_KEEPER_CENTRE_Z = (
    CHANNEL_Z0 - _STATION_PITCH / 2.0 + _STATION_PITCH * (_BANK_COUNT - 1) / 2.0
)  # -0.504
# Lug mid-plane off the centre, on the .005 in grid so the shaft's flat
# stations (2 x this apart) print .XX: 3.180 in, inner face at 76.708. The
# least grid value whose inner faces, each at the -.001 edge of its fit-up
# band, leave twenty levers at the top of their +.001 hub band a .010 feeler
# leaf of end play (draw_ch_channel_assembly) and each lug >= 0.25 of float
# (build_ch_channel_assembly): KEEPER_Z_OFF >= 10P + LUG_HALF_T + 10 x .001
# + .001 + .005, i.e. 80.645 at P 7.62 gives .0080 in of play, under a leaf;
# 80.772 (3.180) gives .0180, a .010 leaf, 0.508 nominal float per lug.
KEEPER_Z_OFF = 80.772  # 3.180 in (#1038 re-pitch; was 2.955 at the 7.0565 pitch)

# --- Nominal geometry (mm; inch in the comments). Shaft axis 25.2 above the
# rail top face (y=1036.2 -> 1061.4, the 2026-08-02 top-frame contract). ---
# Owner ruling Q11-B (2026-10-16): the lug grows outward from 6.0 to 8.0
# about the fixed inner face, so the crown tap keeps its web at title-block
# .XX lug and station bands (SET_SCREW_WEB_MM). #290: .32, so the tap's
# station off the inner face (the half) prints .16 on the same grid.
LUG_HALF_T = 4.064  # .16: lug half-thickness along X (lug .32 thick)
KEEPER_WIDTH = 13.97  # .55 across Z (machine X when placed); extrudes symmetric
SHAFT_AXIS_H = 25.2  # shaft bore centre above the seat (exact: the fulcrum height)
CROWN_R = KEEPER_WIDTH / 2.0  # 6.985 (.275): full-round lug top about the shaft axis
FOOT_H = 7.874  # .31 foot height; the bracket seats on y=0
# Owner ruling Q11-B' (2026-10-16): the foot shortens 10.5 -> 8.5 so the
# thicker lug leaves its tip where it was, clear of MHA-FR-02's corner
# bosses (build_fr_top_frame KEEPER_FOOT_PRINTED_BOSS_MARGINS). Owner ruling
# 2026-10-28 (option D, ENFORCE review eecbf88: the 8.00 + 8.50 chain left
# the overall a reference): the front view baselines the 8.00 lug and the
# overall length off the inner lug face, the overall a real size at .XX
# (OVERALL_LENGTH_PLACES), so the foot length prints nowhere.
FOOT_L = 8.382  # .33 foot length outboard of the lug's outer face
OVERALL_LENGTH_PLACES = 2
FOOT_TIP_X = LUG_HALF_T + FOOT_L  # 12.446 (.49): outboard end of the foot
OVERALL_LENGTH = 2.0 * LUG_HALF_T + FOOT_L  # 16.51 (.65): inner lug face to foot tip
CROWN_TOP_Y = SHAFT_AXIS_H + CROWN_R  # 32.185: the set-screw tap's entry
# Plain reamed bore for the plain .250 (1/4 in ground, SHAFT_H) fulcrum
# shaft: the shaft slides through both lugs at assembly and the set screw
# then pulls it onto the bore wall, so the fit only has to let it slide in
# and locate it, not run on it (the dt_pinion_cam slip bore's case). Each
# keeper is finished alone, as a detail, to its own print (#2338: the
# at-assembly pair ream needed a made-to-order 12 in reamer and an undrawn
# setup). Two bores reamed apart sit out of line by their bore-height bands,
# so the bore is a stock .2525 chucking reamer's size (shop-equipment.toml
# tools.reamer-2525), BORE_DIA_BAND +.0010/.0000: its least clearance on the
# shaft covers the slip minimum plus BORE_ALIGNMENT_ALLOWANCE_MM below.
# The crown is a full round tangent to both side faces, centred on the bore
# (ch_fulcrum_keeper_notes.CROWN_CALLOUT). The bore keeps within
# BORE_CENTRE_BAND_MM of the width's centre plane, so the crown thread's
# worst case below spends that offset under the round.
BORE_DIA = 0.2525 * 25.4  # 6.4135
BORE_RUNNING_MIN_CLEARANCE_MM = 0.010
BORE_DIA_BAND = (0.0254, 0.0)  # (upper, lower): .2525 +.0010/.0000 in
KEEPER_INNER_FACE_SPAN_MM = 2.0 * (KEEPER_Z_OFF - LUG_HALF_T)  # 153.416
# The rail under the two feet: both foot seats lie on MHA-FR-02's one faced
# top plane (its note B, faced in one setup; no flatness frame is printed,
# #1659). The stack allows them KEEPER_SEAT_FLATNESS_BUDGET_MM: inside it the
# seats can stand that far apart in height and each pitch zone /
# KEEPER_SEAT_LENGTH_MM along the shaft (a roll across the width only moves
# a lug sideways, which the fit-up takes up: the pair is set with the shaft
# through both bores). The fit-up step's slide check accepts the result.
KEEPER_SEAT_FLATNESS_BUDGET_MM = 0.04
KEEPER_SEAT_LENGTH_MM = LUG_HALF_T + FOOT_TIP_X  # 16.5: seat along the shaft
# --- Fit-up on the top frame (MHA-CH-00): the pair goes on with the shaft
# through both bores and is set by DRO, the lug centres on the fulcrum line
# within KEEPER_FITUP_X_BAND_MM and the lug INNER faces off the front column
# socket each within KEEPER_FITUP_LOCATION_BAND_MM; the frame's keeper taps
# are then transferred from the foot holes, so no frame-tap or foot-hole
# station reaches the keeper's place. The step prints these distances to
# KEEPER_FITUP_PLACES; build_fr_top_frame reads the same names for the
# foot-to-boss stack. ---
KEEPER_FITUP_LOCATION_BAND_MM = 0.0254  # ±.001 in on the inch assembly sheet
KEEPER_FITUP_PLACES = 2
# Each lug centre stands this far west (+x) of the centre of the top-frame
# rail web under it, its column's socket axis (Main's ruling: a local X
# datum on the receiving web): the kinematic fulcrum line off the frame's
# column line. A literal, so the frame's recipe does not read the channel
# kinematics; draw_ch_channel_assembly checks it against both.
KEEPER_FITUP_X_FROM_WEB_MM = 2.8976  # fulcrum 199.9 - column 197.0024
# The lug centre's own band (owner ruling X-A, 2026-10-18, on the 5d5245a48
# machinist review): no mate needs the lateral X held tight -- the pair is
# set with the shaft through both bores, the fulcrum's gain
# sensitivity is ~0.04 %/mm and common to every channel -- so it carries a
# looser band than the inner faces (KEEPER_FITUP_LOCATION_BAND_MM, which the
# shaft flats need). build_fr_top_frame reads it for its X-side stacks.
KEEPER_FITUP_X_BAND_MM = 0.1016  # ±.004 in
KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM = tuple(
    FULCRUM_KEEPER_CENTRE_Z + side * (KEEPER_Z_OFF - LUG_HALF_T) - FRAME_FRONT_COLUMN_Z
    for side in (-1.0, 1.0)
)  # (34.802, 188.218): front, rear (1.3702, 7.4102 in)

# --- Foot screw: one #2 close-clearance drill + counterbore on the foot's
# centre line, SCREW_FROM_TIP off its tip, for the #2-56 x 7/16 fillister
# (MHA-CH-VN-52, McMaster 91794A080: .140 x .083 head, 18-8 stainless; no
# #2-56 in the 90280A steel family). #2 rather than #4 so the frame's
# transferred tap, on the keeper's centre line KEEPER_FITUP_X_FROM_WEB_MM off the web's
# centre, keeps the drawing-guidelines.md rule 17 (walls and webs) ligament
# (build_fr_top_frame). The under-head plane sits at FOOT_H - CBORE_DEPTH.
# The station off the tip is the least that keeps the tip wall at the .080
# target (FOOT_TIP_WALL_MM); the rest of the short foot goes to the lug side. ---
FOOT_SCREW_THREAD = "#2-56"
FOOT_SCREW_LENGTH_MM = 11.1125  # 7/16 under the head (ch_vn_frame_side_screw_spec)
SCREW_FROM_TIP = 4.572  # .18, printed off the foot tip
SCREW_X = FOOT_TIP_X - SCREW_FROM_TIP  # 7.874 (.31)
SCREW_FROM_SIDE = KEEPER_WIDTH / 2.0  # 6.985 (.275): printed off a side face
BORE_FROM_SIDE = KEEPER_WIDTH / 2.0  # 6.985: the bore's reference station off that face
KEEPER_SCREW_Z_OFF = KEEPER_Z_OFF + SCREW_X  # 88.646: screw off the centre
SCREW_CLEARANCE_SPEC = HoleSpec("clearance", "#2", fit="close")
HOLE_DIA_MM = blind_cut_dia_mm(SCREW_CLEARANCE_SPEC)
# Ø.150 clears the Ø.140 stock head; the depth is the exact stock head
# height (.083, ch_vn_frame_side_screw_spec.HEAD_H, pinned by the part
# build), so the head is flush.
CBORE_DIA_MM = 3.81  # .150
CBORE_DEPTH_MM = 2.1082
SCREW_HOLE_SPEC = HoleSpec(
    "counterbore_fillister",
    SCREW_CLEARANCE_SPEC.size,
    overrides_mm={
        "HoleDiameter": HOLE_DIA_MM,
        "CounterBoreDiameter": CBORE_DIA_MM,
        "CounterBoreDepth": CBORE_DEPTH_MM,
    },
)
# The frame's receiver tap (build_fr_top_frame KeeperTaps, transferred from
# the foot hole at fit-up; modelled at the fulcrum line x and
# FULCRUM_KEEPER_CENTRE_Z +- KEEPER_SCREW_Z_OFF). Thread and drill depths
# print .X on MHA-FR-02's millimetre sheet (_FRAME_TAP_BAND); the worst-case
# stack is below (FOOT_SCREW_ENGAGEMENT_D and the tap-depth asserts).
KEEPER_TAP_THREAD_DEPTH_MM = 7.6
KEEPER_TAP_SPEC = HoleSpec(
    "tapped",
    FOOT_SCREW_THREAD,
    end="blind",
    depth_mm=11.5,
    overrides_mm={"ThreadDepth": KEEPER_TAP_THREAD_DEPTH_MM},
)

# --- Set-screw tap: #1-72 down through the crown top on the lug mid-plane
# (x = 0, z = 0), stopped at the next surface -- the shaft bore -- so it
# never runs on through the lug (the dt_arbor_pedestal apex-tap idiom). ---
SET_SCREW_THREAD = "#1-72"
SET_SCREW_HOLE_SPEC = HoleSpec("tapped", SET_SCREW_THREAD, end="through_next")
SET_SCREW_PITCH = 25.4 / 72.0
SET_SCREW_MIN_ENGAGEMENT_D = 1.5  # drawing-guidelines.md rule 18 (thread engagement): >= 1.5D of full thread

# --- drawing-guidelines.md rule 17 (walls and webs) at the printed worst
# case (inch title block .X +-.1, .XX +-.01, .XXX +-.005, DRILLED HOLES
# +.004/0; DRAWING_PRECISION below) against the .080 target. ---
_BAND_BY_PLACES = {places: printed_band_mm(places, unit=UNIT) for places in (1, 2, 3)}
_DRILLED_PLUS = drilled_oversize_mm(unit=UNIT)
_FRAME_TAP_BAND = printed_band_mm(1)  # MHA-FR-02's .X tap depths, millimetres
_THREAD_HALF_MAJOR = THREAD_MAJOR_MM[SET_SCREW_THREAD] / 2.0
_BORE_MAX_RADIUS = (BORE_DIA + BORE_DIA_BAND[0]) / 2.0


def _sag(radius: float) -> float:
    return radius - sqrt(radius**2 - _THREAD_HALF_MAJOR**2)


# The crown is a 180 deg end arc, so it prints a radius (MR-fleet r5: "Ø14.0"
# on the half round read as a boss or hole). A full round tangent to both
# side faces carries no band of its own (Main ruling B+, 2026-10-15): it
# prints as the radial reference "(R.275)" and follows the width's .XX band,
# so it runs CROWN_LEAST_R..CROWN_MOST_R (.270-.280) -- not what an
# independent radius could drop to, under this tap's 1.5D.
KEEPER_WIDTH_PLACES = 2
_CROWN_R_HALF_BAND = _BAND_BY_PLACES[KEEPER_WIDTH_PLACES] / 2.0
CROWN_LEAST_R = CROWN_R - _CROWN_R_HALF_BAND  # 6.858 (.270)
CROWN_MOST_R = CROWN_R + _CROWN_R_HALF_BAND  # 7.112 (.280)

# The bore's place across the width (owner ruling Q10-B, 2026-10-15). The
# full round is centred on the width's centre plane, so a bore off that plane
# sits under a lower crown that slopes across the tap. A station off a side
# face carries the width's half band on top of its own, so the print holds
# the bore on the width's centre plane, within +-BORE_CENTRE_BAND_MM
# (BORE_CENTRE_CALLOUT on the (.275) reference station, naming the
# MHA-CH-VN-55 set screw whose full thread the band keeps: MR-fleet r10 read a
# bare "crown tap depth" as no mate), and the crown tap's stack below spends
# exactly that offset.
BORE_CENTRE_BAND_MM = 0.3048  # +/-.012
BORE_CENTRE_CALLOUT = (
    f"ON WIDTH CENTER \u00b1{BORE_CENTRE_BAND_MM / 25.4:.3f}".replace("0.", ".")
    + ",\nHOLDS MHA-CH-VN-55\nTHREAD ENGAGEMENT"
)


def _crown_height(crown_r: float, lateral: float) -> float:
    """Height of a full round of ``crown_r`` above its centre's level,
    ``lateral`` off its centre plane."""
    return sqrt(crown_r**2 - lateral**2)


def crown_least_height(lateral: float) -> float:
    """Least crown height above the bore axis (mm), ``lateral`` off the bore
    axis away from the width's centre plane: the least full round with the
    bore BORE_CENTRE_BAND_MM off its centre (ch_fulcrum_shaft_spec's set-screw
    engagement and proud stacks)."""
    return _crown_height(CROWN_LEAST_R, BORE_CENTRE_BAND_MM + lateral)


def set_screw_wall_terms(crown_least_r: float, bore_offset: float) -> dict[str, float]:
    """Named terms of the crown tap's worst-case full-thread length (mm): the
    crown at its least radius over the tap on the bore axis, ``bore_offset``
    off the round's centre plane, less the metal the thread cannot use (the
    dt_arbor_pedestal_spec.set_screw_wall_terms precedent). The thread is full
    only below the crown's lowest point across its major diameter, on the far
    side from the round's centre."""
    over_axis = _crown_height(crown_least_r, bore_offset)
    thread_top = _crown_height(crown_least_r, bore_offset + _THREAD_HALF_MAJOR)
    return {
        "least crown over the bore axis": over_axis,
        "bore radius at its maximum": -_BORE_MAX_RADIUS,
        "crown fall across the thread": thread_top - over_axis,
        "bore sag across the thread": -_sag(_BORE_MAX_RADIUS),
        "one-pitch entry chamfer": -SET_SCREW_PITCH,
    }


SET_SCREW_FULL_THREAD_MM = sum(
    set_screw_wall_terms(CROWN_LEAST_R, BORE_CENTRE_BAND_MM).values()
)
SET_SCREW_ENGAGEMENT_D = SET_SCREW_FULL_THREAD_MM / THREAD_MAJOR_MM[SET_SCREW_THREAD]
if SET_SCREW_ENGAGEMENT_D < SET_SCREW_MIN_ENGAGEMENT_D:
    raise AssertionError(
        f"crown set screw keeps {SET_SCREW_ENGAGEMENT_D:.2f}D of full thread "
        f"at the printed worst case (< {SET_SCREW_MIN_ENGAGEMENT_D}D)"
    )
# Web from the tap's thread major to each lug face. The tap is located off
# the inner lug face (the face KEEPERS_SET_KEY sets, so the station alone puts
# the screw on its shaft flat) and the lug thickness prints separately, both
# at title-block .XX (owner ruling Q11-B: the lug holds the web at .XX), so
# the outer web loses both bands.
_LUG_T_BAND = _BAND_BY_PLACES[2]
_SET_SCREW_LOCATION_BAND = _BAND_BY_PLACES[2]
SET_SCREW_WEB_MM = min(
    LUG_HALF_T - _SET_SCREW_LOCATION_BAND - _THREAD_HALF_MAJOR,
    (2.0 * LUG_HALF_T - _LUG_T_BAND)
    - (LUG_HALF_T + _SET_SCREW_LOCATION_BAND)
    - _THREAD_HALF_MAJOR,
)  # 2.63
if SET_SCREW_WEB_MM < WALL_TARGET_MM:
    raise AssertionError(f"crown tap web {SET_SCREW_WEB_MM:.3f} < {WALL_TARGET_MM}")
# Counterbore walls. The hole prints .18 off the foot tip at .XX and .275
# off a side face at .XXX (FootScrewReference / FootScrewSideReference: the
# side station is the frame tap's transverse place, transferred at fit-up);
# the lug thickness and the overall length print .XX off the inner lug face,
# the width .XX, and the counterbore is a drilled diameter. Located off the
# tip, the tip wall takes only the station's band: .093 here, .0726 at the
# full worst case (less two .010 title-block edge breaks, the counterbore rim
# and the tip's top edge, and 0.3 deg run-off over its .083 depth), between
# the .060 floor and the .080 target. Off the inner lug face (.47) the .65's
# band would join the station's and leave .0626 at the full worst case, so
# the plan keeps the hole off the tip: owner ruling 2026-10-28 (option D),
# review exception RV-03 (cad/config/parts/ch-fulcrum-keeper.yaml).
# The lug side is no wall: the foot runs on under the lug to the inner face,
# so there the counterbore need only stay off the lug's outer face, which
# sits .65 - .32 off the tip (both bands).
_CBORE_MAX_RADIUS = (CBORE_DIA_MM + _DRILLED_PLUS) / 2.0
FOOT_TIP_WALL_MM = SCREW_FROM_TIP - _BAND_BY_PLACES[2] - _CBORE_MAX_RADIUS
if FOOT_TIP_WALL_MM < WALL_TARGET_MM:
    raise AssertionError(
        f"keeper counterbore tip wall {FOOT_TIP_WALL_MM:.3f} < {WALL_TARGET_MM}"
    )
# The full worst case the sheet states as a plain fact (rule 20; review
# exception RV-04): the band-and-oversize wall less two title-block edge
# breaks and the 0.3 deg drill run-off over the counterbore depth, floored to
# .001 so the MIN never overstates it.
FOOT_TIP_WALL_WORST_MM = (
    FOOT_TIP_WALL_MM
    - 2.0 * edge_break_radius_mm(unit=UNIT)
    - CBORE_DEPTH_MM * tan(radians(0.3))
)  # 1.843 (.0726)
FOOT_TIP_WALL_TEXT = (
    f"{floor(FOOT_TIP_WALL_WORST_MM / 25.4 * 1000 + 1e-9) / 1000:.3f}".removeprefix("0")
)  # .072
FOOT_CBORE_LUG_CLEARANCE_MM = (
    (OVERALL_LENGTH - _BAND_BY_PLACES[OVERALL_LENGTH_PLACES])
    - (2.0 * LUG_HALF_T + _LUG_T_BAND)
    - (SCREW_FROM_TIP + _BAND_BY_PLACES[2])
    - _CBORE_MAX_RADIUS
)  # 1.09
if FOOT_CBORE_LUG_CLEARANCE_MM <= 0.0:
    raise AssertionError("the keeper counterbore runs into the lug's outer face")
# The foot-to-lug inside corner (drawing-guidelines.md rule 16; machinist
# review r1, MR-fleet 991a56e: the sharp corner was unstated). The title
# block's INSIDE CORNERS R.040 MAX governs it, so the sheet prints no local
# limit (ENFORCE review 2026-10-24: a local "R1.0 MAX" restated that row,
# rule 2). The part models the round at that ceiling. The counterbore's
# nearest worst-case edge stands FOOT_CBORE_LUG_CLEARANCE_MM (1.09) off the
# lug's outer face, outside a round at that ceiling, and it never reaches the
# lug face (the assert above).
CORNER_R = 1.016  # .040
if not 0.0 < CORNER_R:
    raise AssertionError("the foot-to-lug corner round has no radius")
FOOT_SIDE_WALL_MM = min(
    SCREW_FROM_SIDE - _BAND_BY_PLACES[3] - _CBORE_MAX_RADIUS,
    (KEEPER_WIDTH - _BAND_BY_PLACES[KEEPER_WIDTH_PLACES])
    - (SCREW_FROM_SIDE + _BAND_BY_PLACES[3])
    - _CBORE_MAX_RADIUS,
)
if FOOT_SIDE_WALL_MM < WALL_TARGET_MM:
    raise AssertionError(
        f"keeper counterbore side wall {FOOT_SIDE_WALL_MM:.3f} < {WALL_TARGET_MM}"
    )
# The foot screw's thread in the frame tap (drawing-guidelines.md rule 18
# (thread engagement): >= 1.5D). The screw enters below the under-head plane
# FOOT_H - CBORE_DEPTH: least with the foot (FootRise, .XX) tall and the
# counterbore (native callout, printed to FOOT_COUNTERBORE_DEPTH_PLACES; its
# .083 lies on that grid) shallow, most the other way. The frame thread's .X
# least depth must reach past the deepest entry, and the drill's .X least
# depth must clear the deepest thread by a plug tap's five-pitch lead.
FOOT_COUNTERBORE_DEPTH_PLACES = 3
FOOT_HOLE_CALLOUT_PRECISION = dict.fromkeys(
    ("hw-thruholedia", "hw-cbdia", "hw-cbdepth"), FOOT_COUNTERBORE_DEPTH_PLACES
)
_FOOT_SCREW_PITCH = 25.4 / 56.0
_SCREW_ENTRY = FOOT_SCREW_LENGTH_MM - (FOOT_H - CBORE_DEPTH_MM)  # 5.3467
_ENTRY_REACH = _BAND_BY_PLACES[2] + _BAND_BY_PLACES[FOOT_COUNTERBORE_DEPTH_PLACES]
FOOT_SCREW_ENGAGEMENT_D = (_SCREW_ENTRY - _ENTRY_REACH) / THREAD_MAJOR_MM[
    FOOT_SCREW_THREAD
]
if FOOT_SCREW_ENGAGEMENT_D < 1.5:
    raise AssertionError(
        f"foot screw engages {FOOT_SCREW_ENGAGEMENT_D:.2f}D of the frame tap (< 1.5D)"
    )
if KEEPER_TAP_THREAD_DEPTH_MM - _FRAME_TAP_BAND <= _SCREW_ENTRY + _ENTRY_REACH:
    raise AssertionError("the foot screw bottoms in the frame tap's thread")
if KEEPER_TAP_SPEC.depth_mm - _FRAME_TAP_BAND < (
    KEEPER_TAP_THREAD_DEPTH_MM + _FRAME_TAP_BAND + 5.0 * _FOOT_SCREW_PITCH
):
    raise AssertionError("the frame tap drill leaves no plug-tap lead")

# Hidden reference sketches (drawing-simplicity-policy.md `How the repository implements the guidelines`, the dt_arbor_pedestal pattern):
# the set-screw tap's station off the inner lug face and the foot screw's
# stations off the foot tip and a side face are manufacturing dimensions no
# feature measures (both holes are placed by point), so a one-line
# construction sketch carries each. Three more: the bore's place across the
# width (BORE_FROM_SIDE, a reference carrying the centre-plane band
# BORE_CENTRE_CALLOUT: MR-fleet r5 asked what lateral error the bore's
# layout may take; owner ruling Q10-B), the finished height seat to crown top
# (a reference: the bore height and crown chain it) and the overall length
# lug face to foot tip (a real size, the front view's baseline beside the lug
# thickness; owner ruling 2026-10-28).
# The part saves them blanked; the drawing shows the tap's and the foot
# screw's stations in the plan, the height and length in the front view and
# the bore's place in the end view.
REFERENCE_SKETCHES = (
    "SetScrewReference",
    "FootScrewReference",
    "FootScrewSideReference",
    "BoreSideReference",
    "OverallHeightReference",
    "OverallLengthReference",
)
REFERENCE_DIMENSIONS = ("OverallHeight", "BoreFromSide")

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. The wizard screw hole and the crown tap ship as native hole
# callouts, not marked dims. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "LugProfile": {"LugRise"},
    "LugBody": {"LugThickness"},
    "FootProfile": {"FootRise"},
    "Foot": {"Depth"},
    "LugCrownProfile": {"CrownRadius"},
    "ShaftBoreProfile": {"BoreDia"},
    "SetScrewReference": {"SetScrewLocation"},
    "FootScrewReference": {"ScrewFromTip"},
    "FootScrewSideReference": {"ScrewFromSide"},
    "BoreSideReference": {"BoreFromSide"},
    "OverallHeightReference": {"OverallHeight"},
    "OverallLengthReference": {"OverallLength"},
}
# Decimal places ARE the tolerance statement (drawing-simplicity-policy.md `How the repository implements the guidelines`), so the MODEL
# owns them, in inches. Two places are the general grade (every size here
# feeds a wall, thread or stack, so none prints .X): the crown thread is sized
# at the full round's least radius, half the .XX width's least, over a bore
# BORE_CENTRE_BAND_MM off the width's centre plane (SET_SCREW_ENGAGEMENT_D),
# and the bore's side walls at the same (BORE_SIDE_WALL_MM). The shaft-axis
# height (it sets the fulcrum height; both keepers' bands at .XX stay inside
# the bore's alignment allowance) prints its exact 25.2 rounded to .99; the
# reamed bore carries its own BORE_DIA_BAND at four places; the foot screw's
# station off the tip
# (FOOT_TIP_WALL_MM), the tap station off the inner face and the lug
# thickness hold the crown tap's web at both title-block .XX bands
# (SET_SCREW_WEB_MM, owner ruling Q11-B) and the shaft's flat window
# (ch_fulcrum_shaft_spec FLAT_STATION_WINDOW_MM). The overall length takes two
# (OVERALL_LENGTH_PLACES: the frame's foot-to-boss stack, owner rulings Q11-B'
# and 2026-10-28). Three places carry a stated function (rule 4): the side
# station centres the transferred MHA-FR-02 tap in its rail web
# (KEEPER_SCREW_TRANSVERSE_BAND_MM, build_fr_top_frame). The .275 radial and
# side references print three places (their exact value), the finished
# height two.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "LugProfile": {"LugRise": 2},
    "LugBody": {"LugThickness": 2},
    "FootProfile": {"FootRise": 2},
    "Foot": {"Depth": KEEPER_WIDTH_PLACES},
    "LugCrownProfile": {"CrownRadius": 3},
    "ShaftBoreProfile": {"BoreDia": 4},
    "SetScrewReference": {"SetScrewLocation": 2},
    "FootScrewReference": {"ScrewFromTip": 2},
    "FootScrewSideReference": {"ScrewFromSide": 3},
    "BoreSideReference": {"BoreFromSide": 3},
    "OverallHeightReference": {"OverallHeight": 2},
    "OverallLengthReference": {"OverallLength": OVERALL_LENGTH_PLACES},
}
if {f: set(names) for f, names in DRAWING_PRECISION.items()} != DRAWING_DIMENSIONS:
    raise AssertionError("DRAWING_PRECISION and DRAWING_DIMENSIONS disagree")
if DRAWING_PRECISION["LugBody"]["LugThickness"] != 2 or (
    DRAWING_PRECISION["SetScrewReference"]["SetScrewLocation"] != 2
):
    raise AssertionError("the crown-tap web is sized at .XX lug and tap station")
if DRAWING_PRECISION["FootScrewReference"]["ScrewFromTip"] != 2:
    raise AssertionError("the counterbore tip wall is sized at the .XX tip station")
if DRAWING_PRECISION["Foot"]["Depth"] != 2 or (
    DRAWING_PRECISION["FootScrewSideReference"]["ScrewFromSide"] != 3
):
    raise AssertionError(
        "the counterbore side walls are sized at .XX width, .XXX station"
    )
if DRAWING_PRECISION["FootProfile"]["FootRise"] != 2:
    raise AssertionError("the foot screw's engagement is sized at the .XX foot height")
if DRAWING_PRECISION["Foot"]["Depth"] != KEEPER_WIDTH_PLACES:
    raise AssertionError("the crown thread is sized at half the width's .XX least")
# Walls from the reamed bore to each side face (drawing-guidelines.md rule 17
# (walls and webs)): the bore stands within BORE_CENTRE_BAND_MM of the width's
# centre plane, so each wall is half the least width less that band.
_WIDTH_BAND = _BAND_BY_PLACES[DRAWING_PRECISION["Foot"]["Depth"]]
BORE_SIDE_WALL_MM = (
    (KEEPER_WIDTH - _WIDTH_BAND) / 2.0 - BORE_CENTRE_BAND_MM - _BORE_MAX_RADIUS
)  # 3.35
if BORE_SIDE_WALL_MM < WALL_TARGET_MM:
    raise AssertionError(f"keeper bore side wall {BORE_SIDE_WALL_MM:.3f} < {WALL_TARGET_MM}")
# The foot hole's (and so the transferred frame tap's) transverse place off
# the keeper's centre line, for build_fr_top_frame's tap-ligament stack.
KEEPER_SCREW_TRANSVERSE_BAND_MM = _BAND_BY_PLACES[
    DRAWING_PRECISION["FootScrewSideReference"]["ScrewFromSide"]
]
# The two bores, each reamed alone, line up on the straight shaft through
# both: each keeper's bore height may stand anywhere in its printed LugRise
# band and the two seats KEEPER_SEAT_FLATNESS_BUDGET_MM apart, so the bore
# axes stand up to BORE_HEIGHT_MISMATCH_MM apart in height over the
# 2 x KEEPER_Z_OFF lug span, and each seat may pitch its zone over its
# length. The shaft takes the straight line through both lug centres, so
# each .32 lug spends its thickness x (its seat's pitch + that line's slope)
# of diametral clearance: BORE_ALIGNMENT_ALLOWANCE_MM. The bore band's least
# clearance on the largest shaft keeps the slip minimum on top of it
# (ch_fulcrum_shaft_spec states the result, ALIGNED_MIN_CLEARANCE_MM).
BORE_HEIGHT_MISMATCH_MM = (
    2.0 * _BAND_BY_PLACES[DRAWING_PRECISION["LugProfile"]["LugRise"]]
    + KEEPER_SEAT_FLATNESS_BUDGET_MM
)  # 0.548
BORE_ALIGNMENT_ALLOWANCE_MM = (
    2.0
    * LUG_HALF_T
    * (
        KEEPER_SEAT_FLATNESS_BUDGET_MM / KEEPER_SEAT_LENGTH_MM
        + BORE_HEIGHT_MISMATCH_MM / (2.0 * KEEPER_Z_OFF)
    )
)  # 0.0473
_SHAFT_MAX_DIA = 0.25 * 25.4 + SHAFT_H[0]  # MHA-CH-04 at the top of its band
BORE_LEAST_CLEARANCE_MM = BORE_DIA + BORE_DIA_BAND[1] - _SHAFT_MAX_DIA  # .0025 in
if (
    BORE_LEAST_CLEARANCE_MM
    < BORE_RUNNING_MIN_CLEARANCE_MM + BORE_ALIGNMENT_ALLOWANCE_MM
):
    raise AssertionError("the keeper bore band does not cover the bore alignment")
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
