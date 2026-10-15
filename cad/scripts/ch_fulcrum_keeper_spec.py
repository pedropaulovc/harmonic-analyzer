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
dome of the photo). One #1-72 cup-point set screw (MHA-VN-055), tapped down
through the crown top on the lug mid-plane, bears on the shaft's set-screw
flat and fixes the shaft axially and in rotation. The short straight foot
points OUTBOARD, away from the lever bank, and is screwed down into the
top-frame rail top face with one slotted #2-56 fillister screw
(frame-side-screw, MHA-VN-022) seated flush in a counterbore. 2 required, one
per shaft end (the second is the same part flipped Ry180 by the assembly).

Part frame: +X = along the shaft, OUTBOARD (away from the lever bank); +Y up
from the seat; +Z across the width. The lug mid-plane (= set-screw axis) is
x = 0; the lug spans x -3..+3 from the seat to the crown, the foot runs
outboard from the lug's outer face to x = FOOT_TIP_X, and the whole
underside x -3..+13.5 is the flat seat.
"""

from __future__ import annotations

from math import ceil, hypot, sqrt

from _fit_shaft_h import SHAFT_H
from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from dt_cone_pivot_post_installation import CHANNEL_Z0, FRAME_FRONT_COLUMN_Z

# --- Station (machine Z). The ONE source for build_ch_channel_assembly
# (shaft, keeper, set-screw and foot-screw placement) and build_fr_top_frame
# (its keeper taps). The shaft and both keepers centre on the lever bank's
# mid-plane: lever j sits on the cam plane, half a solid-stacked gear (half a
# pitch) south of station z_j, its hub one pitch long, so the 20-lever bank is
# centred CHANNEL_Z0 - pitch/2 + 19 pitch/2 and both lugs see the same float
# to the end hubs. Literals rather than machine config, so the frame does not
# re-key on machine/channels.yaml; build_ch_channel_assembly asserts the
# result equals rocker_bank_layout.STACK_MID_Z. ---
_STATION_PITCH = 7.0565  # machine channels.station_pitch_mm
_BANK_COUNT = 20  # the full lever bank (never follows active_count)
FULCRUM_KEEPER_CENTRE_Z = (
    CHANNEL_Z0 - _STATION_PITCH / 2.0 + _STATION_PITCH * (_BANK_COUNT - 1) / 2.0
)  # -0.504
KEEPER_Z_OFF = 74.0  # lug mid-plane off the centre: inner face at 71.0

# --- Nominal geometry (mm). Shaft axis 25.2 above the rail top face
# (y=1036.2 -> 1061.4, the 2026-08-02 top-frame contract). ---
LUG_HALF_T = 3.0  # lug half-thickness along X (lug 6.0 thick)
KEEPER_WIDTH = 14.0  # across Z (machine X when placed); extrudes symmetric
SHAFT_AXIS_H = 25.2  # shaft bore centre above the seat
CROWN_R = 7.0  # full-round lug top about the shaft axis (CROWN_R_TOL_TYPE)
FOOT_H = 8.0  # foot height; the bracket seats on y=0
FOOT_L = 10.5  # foot length outboard of the lug's outer face
FOOT_TIP_X = LUG_HALF_T + FOOT_L  # 13.5: outboard end of the foot
CROWN_TOP_Y = SHAFT_AXIS_H + CROWN_R  # 32.2: the set-screw tap's entry
# Plain reamed bore for the plain Ø6.35 (1/4 in ground, SHAFT_H) fulcrum
# shaft: the shaft slides through both lugs at assembly and the set screw
# then pulls it onto the bore wall, so the fit only has to locate it, not run
# on it. Each keeper prints LugRise at .XX, so two keepers bored apart could
# sit 2 x 0.51 out of line -- far past any slide clearance, and a reamer only
# follows the holes it is given. So the two are drilled and reamed through in
# one pass AT THEIR INSTALLED SPACING (BORE_PAIR_CALLOUT,
# ch_channel_assembly_steps.KEEPERS_PAIR_REAMED_KEY): feet outboard and down on
# one flat, inner lug faces KEEPER_INNER_FACE_SPAN_MM apart as KEEPERS_SET_KEY
# sets them, the bore axis set parallel to the flat. Both
# bores are then one straight line across the whole span, and the acceptance
# (the actual MHA-CH-004 shaft slides freely through both, still clamped)
# gauges that line itself. A setup tilt of the line to the flat costs no
# clearance -- on any one plane both bores keep it, so the shaft just lies at
# that tilt -- and a span error delta moves a bore only delta x tilt off it.
# Each crown is then rounded about its own reamed bore
# (CROWN_ABOUT_BORE_CALLOUT), keeping it concentric, which the crown thread's
# worst case below assumes. ch_fulcrum_shaft_spec pins the nominal to its
# SHAFT_DIA.
BORE_DIA = 6.35
BORE_RUNNING_MIN_CLEARANCE_MM = 0.010
BORE_DIA_BAND = (0.050, 0.035)  # (upper, lower)
KEEPER_INNER_FACE_SPAN_MM = 2.0 * (KEEPER_Z_OFF - LUG_HALF_T)  # 142.0
KEEPER_OUTER_FACE_SPAN_MM = 2.0 * (KEEPER_Z_OFF + LUG_HALF_T)  # 154.0
# The one-pass reamer: a 0.2514 in long-series chucking reamer, 12 in overall,
# made to order (Super Tool catalogue 2026 p.59, list 9458EL EDP 645808EL:
# finished to any size in .2211-.2530, solid carbide, 1-1/2 flute, .2193
# shank, 6-1/32 to 12 OAL, NAS 897 Type C; p.42: NAS 897 thru .5000 is
# +.0002/-.0000 in. L&I's LV533XL shelf range stops at .2500). The toleranced
# reamer, not its nominal, must lie inside BORE_DIA_BAND. Gripped one inch,
# its reach must carry the whole flute past the far lug's outer face, and its
# shank must pass the reamed near bore.
PAIR_REAMER_DIA_IN = 0.2514
_PAIR_REAMER_TOLERANCE_IN = (0.0, 0.0002)  # (lower, upper), over nominal
PAIR_REAMER_OAL_IN = 12.0
_PAIR_REAMER_FLUTE_IN = 1.5
_PAIR_REAMER_SHANK_MAX_IN = 0.2193
_PAIR_REAMER_GRIP_IN = 1.0
PAIR_REAMER_RANGE_MM = tuple(
    (PAIR_REAMER_DIA_IN + plus) * 25.4 - BORE_DIA for plus in _PAIR_REAMER_TOLERANCE_IN
)  # (+0.0356, +0.0406) over BORE_DIA
PAIR_REAMER_REACH_MARGIN_MM = (
    PAIR_REAMER_OAL_IN - _PAIR_REAMER_GRIP_IN - _PAIR_REAMER_FLUTE_IN
) * 25.4 - KEEPER_OUTER_FACE_SPAN_MM  # +87.3
if PAIR_REAMER_REACH_MARGIN_MM < 0.0:
    raise AssertionError("the pair reamer does not reach through both keepers")
if _PAIR_REAMER_SHANK_MAX_IN * 25.4 >= BORE_DIA:
    raise AssertionError("the pair reamer's shank does not pass the near bore")
if not (
    BORE_DIA_BAND[1] <= PAIR_REAMER_RANGE_MM[0]
    and PAIR_REAMER_RANGE_MM[1] <= BORE_DIA_BAND[0]
):
    raise AssertionError("the pair reamer's toleranced size is off the bore band")
# What the bench cannot see is the rail. Both foot seats on MHA-FR-002 lie
# within one common zone KEEPER_SEAT_FLATNESS_BUDGET_MM thick (the frame's
# machined keeper-seat note, which pins this constant). Inside it the seats
# can stand the zone apart in height, roll
# opposite ways across KEEPER_WIDTH (each lug centre SHAFT_AXIS_H x roll
# sideways) and each pitch zone/KEEPER_SEAT_LENGTH_MM along the shaft. The
# shaft takes the straight line through both lug centres, so each lug spends
# its thickness x (its pitch + that line's slope over the 2 x KEEPER_Z_OFF
# span) of diametral clearance: BORE_SEAT_ALLOWANCE_MM, on top of the running
# minimum, inside BORE_DIA_BAND's least clearance (ch_fulcrum_shaft_spec
# proves the stack, PAIRED_MIN_CLEARANCE_MM).
KEEPER_SEAT_FLATNESS_BUDGET_MM = 0.04
KEEPER_SEAT_LENGTH_MM = LUG_HALF_T + FOOT_TIP_X  # 16.5: seat along the shaft
_SEAT_ROLL = KEEPER_SEAT_FLATNESS_BUDGET_MM / KEEPER_WIDTH
_LUG_CENTRE_OFFSET = hypot(
    KEEPER_SEAT_FLATNESS_BUDGET_MM, 2.0 * SHAFT_AXIS_H * _SEAT_ROLL
)  # 0.1495
BORE_SEAT_ALLOWANCE_MM = (
    2.0
    * LUG_HALF_T
    * (
        KEEPER_SEAT_FLATNESS_BUDGET_MM / KEEPER_SEAT_LENGTH_MM
        + _LUG_CENTRE_OFFSET / (2.0 * KEEPER_Z_OFF)
    )
)  # 0.0206
if BORE_DIA_BAND[1] - SHAFT_H[0] < (
    BORE_RUNNING_MIN_CLEARANCE_MM + BORE_SEAT_ALLOWANCE_MM
):
    raise AssertionError("the keeper bore band does not cover the rail-seat budget")
# The pair-ream instruction on the bore callout, short enough to stand in one
# clear block beside the end view (machinist review r13: four 75-97 mm rows
# overprinted the crown, the bore and the width dimension). The mate is the
# OTHER keeper of the pair, which the quantity note (QUANTITY_NOTE) states.
# Machinist review r1 (MR-fleet, 991a56e) asked the supply condition: the
# keeper ships with no bore at all (the pair-ream drills it) and its crown is
# rounded only after the ream, so both callouts say so.
QUANTITY_NOTE = 2
BORE_PAIR_CALLOUT = (
    "SUPPLIED UNDRILLED; PAIR-REAM WITH\n"
    f"THE OTHER MHA-CH-007 (NOTE {QUANTITY_NOTE}) AT\n"
    "INSTALLED SPACING; THE MHA-CH-004\n"
    "SHAFT SLIDES THROUGH BOTH"
)
# The crown round meets both side faces whatever its radius above the MIN, so
# a bore off the width's centre (BoreFromSide's band) leaves no step (MR-fleet
# r5: with only "(7.0)" across the width the builder could not tell what
# lateral error the blend allows).
CROWN_ABOUT_BORE_CALLOUT = "ROUND ABOUT THE BORE AFTER\nREAMING, MEETING BOTH SIDES"

# --- Fit-up on the top frame (MHA-CH-000): the pair goes on with the shaft
# through both bores and is set by DRO, the lug centres on the fulcrum line
# and the lug INNER faces off the front column socket, each within
# KEEPER_FITUP_LOCATION_BAND_MM; the frame's keeper taps are then transferred
# from the foot holes, so no frame-tap or foot-hole station reaches the
# keeper's place. The step prints these distances to KEEPER_FITUP_PLACES;
# build_fr_top_frame reads the same names for the foot-to-boss stack. ---
KEEPER_FITUP_LOCATION_BAND_MM = 0.02
KEEPER_FITUP_PLACES = 2
# Each lug centre stands this far west (+x) of the centre of the top-frame
# rail web under it, its column's socket axis (Main's ruling: a local X
# datum on the receiving web). Restated here so the spec stays config-free;
# draw_ch_channel_assembly pins it to the fulcrum line and the column line.
KEEPER_FITUP_X_FROM_WEB_MM = 2.9
KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM = tuple(
    FULCRUM_KEEPER_CENTRE_Z + side * (KEEPER_Z_OFF - LUG_HALF_T) - FRAME_FRONT_COLUMN_Z
    for side in (-1.0, 1.0)
)  # (40.496, 182.496): front, rear

# --- Foot screw: one #2 close-clearance drill + counterbore centred on the
# foot, for the #2-56 x 7/16 fillister (MHA-VN-022, McMaster 91794A080:
# 0.14 x 0.083 head, 18-8 stainless; no #2-56 in the 90280A steel family).
# #2 rather than #4 so the frame's transferred tap, on the keeper's centre
# line 2.9 off the frame web's centre, keeps the drawing-guidelines.md rule 17 (walls and webs) ligament
# (build_fr_top_frame). The under-head plane sits at FOOT_H - CBORE_DEPTH. ---
FOOT_SCREW_THREAD = "#2-56"
FOOT_SCREW_LENGTH_MM = 11.1125  # 7/16 under the head (vn_frame_side_screw_spec)
SCREW_X = LUG_HALF_T + FOOT_L / 2.0  # 8.25: foot centre
SCREW_FROM_TIP = FOOT_TIP_X - SCREW_X  # 5.25: printed off the foot tip
SCREW_FROM_SIDE = KEEPER_WIDTH / 2.0  # 7.0: printed off a side face
BORE_FROM_SIDE = KEEPER_WIDTH / 2.0  # 7.0: the bore printed off the same side face
KEEPER_SCREW_Z_OFF = KEEPER_Z_OFF + SCREW_X  # 82.25: screw off the centre
SCREW_CLEARANCE_SPEC = HoleSpec("clearance", "#2", fit="close")
HOLE_DIA_MM = blind_cut_dia_mm(SCREW_CLEARANCE_SPEC)
# Ø3.8 clears the Ø3.556 stock head (the MHA-VN-050 #2 counterbore); the
# depth is the exact stock head height (vn_frame_side_screw_spec.HEAD_H,
# pinned by the part build), so the head is flush.
CBORE_DIA_MM = 3.8
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
# print .X; the worst-case stack is below (FOOT_SCREW_ENGAGEMENT_D and the
# tap-depth asserts).
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

# --- drawing-guidelines.md rule 17 (walls and webs) at the printed worst case (title block .X +-0.8, .XX +-0.51,
# .XXX +-0.13, DRILLED HOLES +0.10/0; DRAWING_PRECISION below). ---
_BAND_BY_PLACES = {1: 0.8, 2: 0.51, 3: 0.13}
_DRILLED_PLUS = 0.10
_THREAD_HALF_MAJOR = THREAD_MAJOR_MM[SET_SCREW_THREAD] / 2.0
_BORE_MAX_RADIUS = (BORE_DIA + BORE_DIA_BAND[0]) / 2.0


def _sag(radius: float) -> float:
    return radius - sqrt(radius**2 - _THREAD_HALF_MAJOR**2)


# The crown is a 180 deg end arc, so it prints a radius (MR-fleet r5: "Ø14.0"
# on the half round read as a boss or hole), as the single limit "R7.0 MIN"
# (Main ruling (a), 2026-10-15): at the title block's .X a radius could drop
# to 6.2, under this tap's 1.5D and ch_fulcrum_shaft's set-screw proud
# ruling. Larger only moves where the round meets the sides; the supplied
# blank's height (SUPPLY_HEIGHT_MIN) bounds it. swTolMIN prints the nominal,
# so nominal = limit (the CORNER_R_MAX recipe).
CROWN_R_PLACES = 1
CROWN_R_MIN = CROWN_R
CROWN_R_TOL_TYPE = 5  # swTolType_e.swTolMIN: prints "R7.0 MIN"


def set_screw_wall_terms(crown_r_min: float) -> dict[str, float]:
    """Named terms of the crown tap's worst-case full-thread length (mm): the
    crown at its least radius, less the metal the thread cannot use (the
    dt_arbor_pedestal_spec.set_screw_wall_terms precedent)."""
    least_crown = crown_r_min  # CrownRadius prints its single limit MIN
    return {
        "crown radius at its MIN limit": least_crown,
        "bore radius at its maximum": -_BORE_MAX_RADIUS,
        "crown sag across the thread": -_sag(least_crown),
        "bore sag across the thread": -_sag(_BORE_MAX_RADIUS),
        "one-pitch entry chamfer": -SET_SCREW_PITCH,
    }


SET_SCREW_FULL_THREAD_MM = sum(set_screw_wall_terms(CROWN_R_MIN).values())
SET_SCREW_ENGAGEMENT_D = SET_SCREW_FULL_THREAD_MM / THREAD_MAJOR_MM[SET_SCREW_THREAD]
if SET_SCREW_ENGAGEMENT_D < SET_SCREW_MIN_ENGAGEMENT_D:
    raise AssertionError(
        f"crown set screw keeps {SET_SCREW_ENGAGEMENT_D:.2f}D of full thread "
        f"at the printed worst case (< {SET_SCREW_MIN_ENGAGEMENT_D}D)"
    )
# Web from the tap's thread major to each lug face. The tap is located off
# the inner lug face (the face KEEPERS_SET_KEY sets, so the station alone puts
# the screw on its shaft flat) and the lug thickness prints separately, both
# at .XXX (user ruling: a 6.0 lug cannot hold a 1.5 web at .XX for any set
# screw), so the outer web loses both bands.
_LUG_T_BAND = _BAND_BY_PLACES[3]
_SET_SCREW_LOCATION_BAND = _BAND_BY_PLACES[3]
SET_SCREW_WEB_MM = min(
    LUG_HALF_T - _SET_SCREW_LOCATION_BAND - _THREAD_HALF_MAJOR,
    (2.0 * LUG_HALF_T - _LUG_T_BAND)
    - (LUG_HALF_T + _SET_SCREW_LOCATION_BAND)
    - _THREAD_HALF_MAJOR,
)
if SET_SCREW_WEB_MM < 1.5:
    raise AssertionError(f"crown tap web {SET_SCREW_WEB_MM:.2f} < 1.5 floor")
# Counterbore walls. The hole prints 5.25 off the foot tip at .XX and 7.000
# off a side face at .XXX (FootScrewReference / FootScrewSideReference: the
# side station is the frame tap's transverse place, transferred at fit-up);
# the foot length and width print .X and the counterbore is a drilled
# diameter. Located off the tip, the tip wall takes only the station's band.
# The lug side is no wall: the foot runs on under the lug to x = -3, so
# there the counterbore need only stay off the lug's outer face.
_CBORE_MAX_RADIUS = (CBORE_DIA_MM + _DRILLED_PLUS) / 2.0
FOOT_TIP_WALL_MM = SCREW_FROM_TIP - _BAND_BY_PLACES[2] - _CBORE_MAX_RADIUS
if FOOT_TIP_WALL_MM < 2.0:
    raise AssertionError(f"keeper counterbore tip wall {FOOT_TIP_WALL_MM:.2f} < 2.0")
FOOT_CBORE_LUG_CLEARANCE_MM = (
    (FOOT_L - _BAND_BY_PLACES[1])
    - (SCREW_FROM_TIP + _BAND_BY_PLACES[2])
    - _CBORE_MAX_RADIUS
)
if FOOT_CBORE_LUG_CLEARANCE_MM <= 0.0:
    raise AssertionError("the keeper counterbore runs into the lug's outer face")
# The foot-to-lug inside corner (drawing-guidelines.md rule 16): the largest
# radius the shop may leave there, so it can pick a rigid cutter (machinist
# review r1, MR-fleet 991a56e: the sharp corner was unstated). The
# counterbore's nearest worst-case edge stands FOOT_CBORE_LUG_CLEARANCE_MM off
# the lug's outer face, so the round's tangent line on the foot top must stop
# short of it. The part models the corner AT the limit and prints it as the
# single limit "R1.0 MAX" (swTolMAX prints the nominal, so nominal = limit;
# the band runs from sharp up to it).
CORNER_R_PLACES = 1
CORNER_R_MAX = 1.0
CORNER_R_BAND = (0.0, -CORNER_R_MAX)  # (upper, lower)
CORNER_R_TOL_TYPE = 6  # swTolType_e.swTolMAX: prints "R1.0 MAX"
if not 0.0 < CORNER_R_MAX < FOOT_CBORE_LUG_CLEARANCE_MM:
    raise AssertionError("the foot-to-lug corner round reaches the counterbore")
FOOT_SIDE_WALL_MM = min(
    SCREW_FROM_SIDE - _BAND_BY_PLACES[3] - _CBORE_MAX_RADIUS,
    (KEEPER_WIDTH - _BAND_BY_PLACES[1])
    - (SCREW_FROM_SIDE + _BAND_BY_PLACES[3])
    - _CBORE_MAX_RADIUS,
)
if FOOT_SIDE_WALL_MM < 1.5:
    raise AssertionError(f"keeper counterbore side wall {FOOT_SIDE_WALL_MM:.2f} < 1.5")
# The foot screw's thread in the frame tap (drawing-guidelines.md rule 18 (thread engagement): >= 1.5D). The screw
# enters below the under-head plane FOOT_H - CBORE_DEPTH: least with the
# foot (FootRise, .X) tall and the counterbore (native callout, printed to
# FOOT_COUNTERBORE_DEPTH_PLACES) shallow, most the other way. The thread's .X
# least depth must reach past the deepest entry, and the drill's .X least
# depth must clear the deepest thread by a plug tap's five-pitch lead.
FOOT_COUNTERBORE_DEPTH_PLACES = 2
_FOOT_SCREW_PITCH = 25.4 / 56.0
_PRINTED_CBORE_DEPTH = round(CBORE_DEPTH_MM, FOOT_COUNTERBORE_DEPTH_PLACES)  # 2.11
_SCREW_ENTRY = FOOT_SCREW_LENGTH_MM - (FOOT_H - _PRINTED_CBORE_DEPTH)  # 5.2225
_ENTRY_REACH = _BAND_BY_PLACES[1] + _BAND_BY_PLACES[FOOT_COUNTERBORE_DEPTH_PLACES]
FOOT_SCREW_ENGAGEMENT_D = (_SCREW_ENTRY - _ENTRY_REACH) / THREAD_MAJOR_MM[
    FOOT_SCREW_THREAD
]
if FOOT_SCREW_ENGAGEMENT_D < 1.5:
    raise AssertionError(
        f"foot screw engages {FOOT_SCREW_ENGAGEMENT_D:.2f}D of the frame tap (< 1.5D)"
    )
if KEEPER_TAP_THREAD_DEPTH_MM - _BAND_BY_PLACES[1] <= _SCREW_ENTRY + _ENTRY_REACH:
    raise AssertionError("the foot screw bottoms in the frame tap's thread")
if KEEPER_TAP_SPEC.depth_mm - _BAND_BY_PLACES[1] < (
    KEEPER_TAP_THREAD_DEPTH_MM + _BAND_BY_PLACES[1] + 5.0 * _FOOT_SCREW_PITCH
):
    raise AssertionError("the frame tap drill leaves no plug-tap lead")

# Hidden reference sketches (drawing-simplicity-policy.md `How the repository implements the guidelines`, the dt_arbor_pedestal pattern):
# the set-screw tap's station off the inner lug face and the foot screw's
# stations off the foot tip and a side face are manufacturing dimensions no
# feature measures (both holes are placed by point), so a one-line
# construction sketch carries each. Four more: the bore's place across the
# width (BORE_FROM_SIDE, toleranced at .X: MR-fleet r5 asked what lateral
# error the pair-ream layout may take), the finished height seat to crown top
# and the overall length lug face to foot tip (references: the bore height
# and crown, and the lug thickness and foot length, chain them) and the
# supplied blank's height (SUPPLY_HEIGHT_MIN), printed beside the finished
# one (MR-fleet r4: the supply size alone left its extension line in empty
# space above the top). The part saves them blanked; the drawing shows the
# tap's and the foot screw's stations in the plan, the heights and length in
# the front view and the bore's place in the end view.
REFERENCE_SKETCHES = (
    "SetScrewReference",
    "FootScrewReference",
    "FootScrewSideReference",
    "BoreSideReference",
    "OverallHeightReference",
    "SupplyHeightReference",
    "OverallLengthReference",
)
REFERENCE_DIMENSIONS = ("OverallHeight", "OverallLength")

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. The wizard screw hole and the crown tap ship as native hole
# callouts, not marked dims. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "LugProfile": {"LugRise"},
    "LugBody": {"LugThickness"},
    "FootProfile": {"FootLength", "FootRise"},
    "Foot": {"Depth"},
    "LugCrownProfile": {"CrownRadius"},
    "ShaftBoreProfile": {"BoreDia"},
    "SetScrewReference": {"SetScrewLocation"},
    "FootScrewReference": {"ScrewFromTip"},
    "FootScrewSideReference": {"ScrewFromSide"},
    "BoreSideReference": {"BoreFromSide"},
    "OverallHeightReference": {"OverallHeight"},
    "SupplyHeightReference": {"SupplyHeight"},
    "OverallLengthReference": {"OverallLength"},
    "CornerFillet": {"CornerRadius"},
}
# Decimal places ARE the tolerance statement (drawing-simplicity-policy.md `How the repository implements the guidelines`), so the MODEL
# owns them. One place is the general grade: the crown thread is sized at
# the crown radius's single limit MIN (SET_SCREW_ENGAGEMENT_D) and the bore's
# side walls at the .X lateral station and width (BORE_SIDE_WALL_MM). The shaft-axis height takes
# two (it sets the fulcrum height; the pair reaming lines the two bores
# up); the reamed bore carries its own BORE_DIA_BAND; the foot screw's
# station off the tip takes two (FOOT_TIP_WALL_MM). Three places each carry
# a stated function (rule 4): the tap station off the inner face puts the set
# screw on its MHA-CH-004 flat (ch_fulcrum_shaft_spec FLAT_STATION_WINDOW_MM,
# from the DRO-set inner faces), the lug thickness holds the crown tap's
# outer web (SET_SCREW_WEB_MM), and the side station centres the transferred
# MHA-FR-002 tap in its rail web (KEEPER_SCREW_TRANSVERSE_BAND_MM,
# build_fr_top_frame). The references print one place; the corner round
# prints its single limit at CORNER_R_PLACES, the crown round its own at
# CROWN_R_PLACES and the supplied height its own at SUPPLY_HEIGHT_PLACES.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "LugProfile": {"LugRise": 2},
    "LugBody": {"LugThickness": 3},
    "FootProfile": {"FootLength": 1, "FootRise": 1},
    "Foot": {"Depth": 1},
    "LugCrownProfile": {"CrownRadius": CROWN_R_PLACES},
    "ShaftBoreProfile": {"BoreDia": 3},
    "SetScrewReference": {"SetScrewLocation": 3},
    "FootScrewReference": {"ScrewFromTip": 2},
    "FootScrewSideReference": {"ScrewFromSide": 3},
    "BoreSideReference": {"BoreFromSide": 1},
    "OverallHeightReference": {"OverallHeight": 1},
    "SupplyHeightReference": {"SupplyHeight": 1},
    "OverallLengthReference": {"OverallLength": 1},
    "CornerFillet": {"CornerRadius": CORNER_R_PLACES},
}
# The function each three-place size serves, printed under it.
SET_SCREW_STATION_CALLOUT = "SETS SCREW ON\nMHA-CH-004 FLAT"
LUG_THICKNESS_CALLOUT = "HOLDS CROWN TAP\nOUTER WALL"
FOOT_SCREW_SIDE_CALLOUT = "CENTERS MHA-FR-002\nTAP IN RAIL WEB"
if {f: set(names) for f, names in DRAWING_PRECISION.items()} != DRAWING_DIMENSIONS:
    raise AssertionError("DRAWING_PRECISION and DRAWING_DIMENSIONS disagree")
if DRAWING_PRECISION["LugBody"]["LugThickness"] != 3 or (
    DRAWING_PRECISION["SetScrewReference"]["SetScrewLocation"] != 3
):
    raise AssertionError("the crown-tap web is sized at .XXX lug and tap station")
if DRAWING_PRECISION["FootScrewReference"]["ScrewFromTip"] != 2:
    raise AssertionError("the counterbore tip wall is sized at the .XX tip station")
if DRAWING_PRECISION["Foot"]["Depth"] != 1 or (
    DRAWING_PRECISION["FootScrewSideReference"]["ScrewFromSide"] != 3
):
    raise AssertionError(
        "the counterbore side walls are sized at .X width, .XXX station"
    )
if DRAWING_PRECISION["FootProfile"]["FootRise"] != 1:
    raise AssertionError("the foot screw's engagement is sized at the .X foot height")
if DRAWING_PRECISION["LugCrownProfile"]["CrownRadius"] != CROWN_R_PLACES:
    raise AssertionError("the crown thread is sized at the crown radius's MIN limit")
# Walls from the reamed bore to each side face (drawing-guidelines.md rule 17
# (walls and webs)): the bore is placed off the -Z side face and the width
# prints separately, so the far wall loses both bands.
_BORE_SIDE_BAND = _BAND_BY_PLACES[DRAWING_PRECISION["BoreSideReference"]["BoreFromSide"]]
_WIDTH_BAND = _BAND_BY_PLACES[DRAWING_PRECISION["Foot"]["Depth"]]
BORE_SIDE_WALL_MM = min(
    BORE_FROM_SIDE - _BORE_SIDE_BAND - _BORE_MAX_RADIUS,
    (KEEPER_WIDTH - _WIDTH_BAND)
    - (BORE_FROM_SIDE + _BORE_SIDE_BAND)
    - _BORE_MAX_RADIUS,
)  # 2.2
if BORE_SIDE_WALL_MM < 2.0:
    raise AssertionError(f"keeper bore side wall {BORE_SIDE_WALL_MM:.2f} < 2.0")
# The foot hole's (and so the transferred frame tap's) transverse place off
# the keeper's centre line, for build_fr_top_frame's tap-ligament stack.
KEEPER_SCREW_TRANSVERSE_BAND_MM = _BAND_BY_PLACES[
    DRAWING_PRECISION["FootScrewSideReference"]["ScrewFromSide"]
]
# The keeper is supplied square-topped (BORE_PAIR_CALLOUT: undrilled) and
# the pair-ream step rounds each crown about its own bore (MR-fleet r3,
# cb6e11e: the blank's height was printed nowhere). The blank must reach the
# crown apex of a bore at the top of its printed LugRise band; taller, the
# round cuts the rest away. The SupplyHeightReference line runs up the inner
# lug face AT the limit and prints the single limit "32.8 MIN" (swTolMIN
# prints the nominal, so nominal = limit).
SUPPLY_HEIGHT_PLACES = DRAWING_PRECISION["SupplyHeightReference"]["SupplyHeight"]
_SUPPLY_STEP = 10.0**-SUPPLY_HEIGHT_PLACES
SUPPLY_HEIGHT_MIN = round(
    ceil(
        (SHAFT_AXIS_H + _BAND_BY_PLACES[DRAWING_PRECISION["LugProfile"]["LugRise"]] + CROWN_R_MIN)
        / _SUPPLY_STEP
        - 1e-9
    )
    * _SUPPLY_STEP,
    SUPPLY_HEIGHT_PLACES,
)  # 32.8
SUPPLY_HEIGHT_TOL_TYPE = 5  # swTolType_e.swTolMIN: prints "32.8 MIN"
SUPPLY_HEIGHT_CALLOUT = "SUPPLY HEIGHT,\nSQUARE TOP"
if not CROWN_TOP_Y < SUPPLY_HEIGHT_MIN:
    raise AssertionError("the supplied blank does not reach the crown apex")
# Overall length, inner lug face to foot tip (MR-fleet r3: only the chained
# lug thickness and foot length printed it).
OVERALL_LENGTH = 2.0 * LUG_HALF_T + FOOT_L  # 16.5

# True free-text instructions only (native dims and callouts carry the rest;
# the bore's pair reaming is its callout, BORE_PAIR_CALLOUT). The material
# and finish are the title block's. Brackets carry no frames and no datums
# (policy). MR-fleet r6 (e4ef909) asked why the plan locates the crown tap
# and the foot hole from different ends (rule 10): the tap's station is the
# fit-up face's (KEEPERS_SET_KEY sets the inner faces), the foot hole's only
# its walls' (the frame tap is transferred through it), so note 3 says so.
DATUM_REASON_NOTE = 3
DRAWING_NOTES = "\n".join(
    (
        "1. CROWN TAP FOR THE MHA-VN-055 CUP-POINT SET SCREW; FOOT HOLE",
        "   FOR THE MHA-VN-022 #2-56 FILLISTER, HEAD FLUSH.",
        f"{QUANTITY_NOTE}. 2 REQUIRED, ONE PER MHA-CH-004 FULCRUM-SHAFT END (SECOND",
        "   IS THIS PART FLIPPED 180 DEG ABOUT VERTICAL).",
        f"{DATUM_REASON_NOTE}. CROWN TAP LOCATED FROM THE INNER LUG FACE (SET AT FIT-UP);",
        "   FOOT HOLE FROM THE FOOT TIP (THE FRAME TAP IS TRANSFERRED THROUGH IT).",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
