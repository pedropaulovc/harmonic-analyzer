r"""Fulcrum-keeper dimensional contract -- the single source of truth shared by
the part build (``build_ch_fulcrum_keeper.py``), its manufacturing drawing
(``draw_ch_fulcrum_keeper.py``), the channel assembly that places it and the
top frame that carries its foot-screw taps.

PURE DATA, no SolidWorks/COM imports: the nominal geometry (the "editable
knobs"), the keeper's station on the fulcrum shaft, the hole layout the
drawing needs for its view math, the rule-12 worst-case wall and thread
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

from math import radians, sqrt, tan

from _fit_limits import SHAFT_H
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
CROWN_DIA = 14.0  # full-round lug top, concentric with the shaft axis
FOOT_H = 8.0  # foot height; the bracket seats on y=0
FOOT_L = 10.5  # foot length outboard of the lug's outer face
FOOT_TIP_X = LUG_HALF_T + FOOT_L  # 13.5: outboard end of the foot
CROWN_TOP_Y = SHAFT_AXIS_H + CROWN_DIA / 2.0  # 32.2: the set-screw tap's entry
# Plain reamed bore for the plain Ø6.35 (1/4 in ground, SHAFT_H) fulcrum
# shaft: the shaft slides through both lugs at assembly and the set screw
# then pulls it onto the bore wall, so the fit only has to locate it, not run
# on it. Each keeper prints LugRise at .XX, so two keepers bored apart could
# sit 2 x 0.51 out of line -- far past any slide clearance, and a reamer only
# follows the holes it is given. So the two are drilled and reamed as a pair
# in one setup (BORE_PAIR_CALLOUT, MHA-CH-000): one axis, one height off one
# seat flat. Pairing does not square that axis to the seat, though: a common
# inclination passes the bench slide test (the bores 6 apart) and then, with
# the keepers 2 x KEEPER_Z_OFF apart on the flat rail, each bore crosses the
# straight shaft at that angle. The shaft's best line runs through both lug
# centres (tilting it costs the 148 span, not the 6 lug), so each lug costs
# its thickness x tan(inclination) of diametral clearance. With a budget of
# BORE_INCLINATION_BUDGET_DEG that allowance rides on top of the running
# minimum, and BORE_DIA_BAND (+0.035/+0.050, a 0.2515 in over-size reamer)
# keeps both over the shaft's 0/-0.020 band (ch_fulcrum_shaft_spec proves the
# stack, PAIRED_MIN_CLEARANCE_MM). Each crown is then rounded about its own
# reamed bore (CROWN_ABOUT_BORE_CALLOUT), keeping it concentric, which the
# crown thread's worst case below assumes. ch_fulcrum_shaft_spec pins the
# nominal to its SHAFT_DIA.
BORE_DIA = 6.35
BORE_RUNNING_MIN_CLEARANCE_MM = 0.010
BORE_INCLINATION_BUDGET_DEG = 0.2
BORE_INCLINATION_ALLOWANCE_MM = (
    2.0 * LUG_HALF_T * tan(radians(BORE_INCLINATION_BUDGET_DEG))
)  # 0.0209
BORE_DIA_BAND = (0.050, 0.035)  # (upper, lower)
if KEEPER_Z_OFF <= LUG_HALF_T:
    raise AssertionError("the keeper span no longer exceeds a lug thickness")
if BORE_DIA_BAND[1] - SHAFT_H[0] < (
    BORE_RUNNING_MIN_CLEARANCE_MM + BORE_INCLINATION_ALLOWANCE_MM
):
    raise AssertionError("the keeper bore band does not cover the inclination")
BORE_PAIR_CALLOUT = (
    "DRILL AND REAM AS A PAIR WITH THE\n"
    "MATING MHA-CH-007, INNER LUG FACES\n"
    "TOGETHER, SEATS ON ONE FLAT: THE\n"
    "MHA-CH-004 SHAFT SLIDES THROUGH BOTH"
)
CROWN_ABOUT_BORE_CALLOUT = "ROUND ABOUT THE REAMED BORE"

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
# line 2.9 off the frame web's centre, keeps the rule-12 ligament
# (build_fr_top_frame). The under-head plane sits at FOOT_H - CBORE_DEPTH. ---
FOOT_SCREW_THREAD = "#2-56"
FOOT_SCREW_LENGTH_MM = 11.1125  # 7/16 under the head (vn_frame_side_screw_spec)
SCREW_X = LUG_HALF_T + FOOT_L / 2.0  # 8.25: foot centre
SCREW_FROM_LUG_FACE = SCREW_X - LUG_HALF_T  # 5.25: printed off the outer lug face
SCREW_FROM_SIDE = KEEPER_WIDTH / 2.0  # 7.0: printed off a side face
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
SET_SCREW_MIN_ENGAGEMENT_D = 1.5  # rule 12: >= 1.5D of full thread

# --- Rule 12 at the printed worst case (title block .X +-0.8, .XX +-0.51,
# .XXX +-0.13, DRILLED HOLES +0.10/0; DRAWING_PRECISION below). ---
_BAND_BY_PLACES = {1: 0.8, 2: 0.51, 3: 0.13}
_DRILLED_PLUS = 0.10
_THREAD_HALF_MAJOR = THREAD_MAJOR_MM[SET_SCREW_THREAD] / 2.0
_BORE_MAX_RADIUS = (BORE_DIA + BORE_DIA_BAND[0]) / 2.0


def _sag(radius: float) -> float:
    return radius - sqrt(radius**2 - _THREAD_HALF_MAJOR**2)


def set_screw_wall_terms(crown_dia: float) -> dict[str, float]:
    """Named terms of the crown tap's worst-case full-thread length (mm): the
    crown at its least radius, less the metal the thread cannot use (the
    dt_arbor_pedestal_spec.set_screw_wall_terms precedent)."""
    least_crown = (crown_dia - _BAND_BY_PLACES[1]) / 2.0  # CrownDia prints .X
    return {
        "crown radius at .X minimum": least_crown,
        "bore radius at its maximum": -_BORE_MAX_RADIUS,
        "crown sag across the thread": -_sag(least_crown),
        "bore sag across the thread": -_sag(_BORE_MAX_RADIUS),
        "one-pitch entry chamfer": -SET_SCREW_PITCH,
    }


SET_SCREW_FULL_THREAD_MM = sum(set_screw_wall_terms(CROWN_DIA).values())
SET_SCREW_ENGAGEMENT_D = SET_SCREW_FULL_THREAD_MM / THREAD_MAJOR_MM[SET_SCREW_THREAD]
if SET_SCREW_ENGAGEMENT_D < SET_SCREW_MIN_ENGAGEMENT_D:
    raise AssertionError(
        f"crown set screw keeps {SET_SCREW_ENGAGEMENT_D:.2f}D of full thread "
        f"at the printed worst case (< {SET_SCREW_MIN_ENGAGEMENT_D}D)"
    )
# Web from the tap's thread major to each lug face. The tap is located off
# the outer lug face and the lug thickness prints separately, both at .XXX
# (user ruling: a 6.0 lug cannot hold a 1.5 web at .XX for any set screw),
# so the inner web loses both bands.
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
# Counterbore walls. The hole prints 5.25 off the outer lug face and 7.0 off
# a side face, both at .XXX (FootScrewReference / FootScrewSideReference:
# the side station is also the frame tap's transverse place, transferred at
# fit-up); the foot length and width print .X and the counterbore is a
# drilled diameter. The lug side is no wall: the foot runs on under the lug
# to x = -3.
_CBORE_MAX_RADIUS = (CBORE_DIA_MM + _DRILLED_PLUS) / 2.0
FOOT_TIP_WALL_MM = (
    (FOOT_L - _BAND_BY_PLACES[1])
    - (SCREW_FROM_LUG_FACE + _BAND_BY_PLACES[3])
    - _CBORE_MAX_RADIUS
)
if FOOT_TIP_WALL_MM < 1.5:
    raise AssertionError(f"keeper counterbore tip wall {FOOT_TIP_WALL_MM:.2f} < 1.5")
FOOT_SIDE_WALL_MM = min(
    SCREW_FROM_SIDE - _BAND_BY_PLACES[3] - _CBORE_MAX_RADIUS,
    (KEEPER_WIDTH - _BAND_BY_PLACES[1])
    - (SCREW_FROM_SIDE + _BAND_BY_PLACES[3])
    - _CBORE_MAX_RADIUS,
)
if FOOT_SIDE_WALL_MM < 1.5:
    raise AssertionError(f"keeper counterbore side wall {FOOT_SIDE_WALL_MM:.2f} < 1.5")
# The foot screw's thread in the frame tap (rule 12: >= 1.5D). The screw
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

# Hidden reference sketches (policy rule 2, the dt_arbor_pedestal pattern):
# the set-screw tap's station off the outer lug face and the foot screw's
# stations off the outer lug face and a side face are manufacturing
# dimensions no feature measures (both holes are placed by point), so a
# one-line construction sketch carries each. The part saves them blanked;
# the drawing shows the tap's in the front view and the foot screw's in the
# plan.
REFERENCE_SKETCHES = (
    "SetScrewReference",
    "FootScrewReference",
    "FootScrewSideReference",
)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. The wizard screw hole and the crown tap ship as native hole
# callouts, not marked dims. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "LugProfile": {"LugRise"},
    "LugBody": {"LugThickness"},
    "FootProfile": {"FootLength", "FootRise"},
    "Foot": {"Depth"},
    "LugCrownProfile": {"CrownDia"},
    "ShaftBoreProfile": {"BoreDia"},
    "SetScrewReference": {"SetScrewLocation"},
    "FootScrewReference": {"ScrewFromLug"},
    "FootScrewSideReference": {"ScrewFromSide"},
}
# Decimal places ARE the tolerance statement (policy rule 2), so the MODEL
# owns them. One place is the general grade: the crown thread is sized at
# the .X worst case (SET_SCREW_ENGAGEMENT_D). The shaft-axis height takes
# two (it sets the fulcrum height; the pair reaming lines the two bores
# up); the reamed bore carries its own BORE_DIA_BAND; the lug thickness
# and the tap station take three, the web's worst case (SET_SCREW_WEB_MM),
# and so do the foot screw's stations: off the lug for the tip wall
# (FOOT_TIP_WALL_MM), off the side for the frame tap's ligament
# (KEEPER_SCREW_TRANSVERSE_BAND_MM, build_fr_top_frame).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "LugProfile": {"LugRise": 2},
    "LugBody": {"LugThickness": 3},
    "FootProfile": {"FootLength": 1, "FootRise": 1},
    "Foot": {"Depth": 1},
    "LugCrownProfile": {"CrownDia": 1},
    "ShaftBoreProfile": {"BoreDia": 3},
    "SetScrewReference": {"SetScrewLocation": 3},
    "FootScrewReference": {"ScrewFromLug": 3},
    "FootScrewSideReference": {"ScrewFromSide": 3},
}
if {f: set(names) for f, names in DRAWING_PRECISION.items()} != DRAWING_DIMENSIONS:
    raise AssertionError("DRAWING_PRECISION and DRAWING_DIMENSIONS disagree")
if DRAWING_PRECISION["LugBody"]["LugThickness"] != 3 or (
    DRAWING_PRECISION["SetScrewReference"]["SetScrewLocation"] != 3
):
    raise AssertionError("the crown-tap web is sized at .XXX lug and tap station")
if DRAWING_PRECISION["FootProfile"]["FootLength"] != 1 or (
    DRAWING_PRECISION["FootScrewReference"]["ScrewFromLug"] != 3
):
    raise AssertionError("the counterbore tip wall is sized at .X foot, .XXX station")
if DRAWING_PRECISION["Foot"]["Depth"] != 1 or (
    DRAWING_PRECISION["FootScrewSideReference"]["ScrewFromSide"] != 3
):
    raise AssertionError(
        "the counterbore side walls are sized at .X width, .XXX station"
    )
if DRAWING_PRECISION["FootProfile"]["FootRise"] != 1:
    raise AssertionError("the foot screw's engagement is sized at the .X foot height")
if DRAWING_PRECISION["LugCrownProfile"]["CrownDia"] != 1:
    raise AssertionError("the crown thread is sized at the .X crown diameter")
# The foot hole's (and so the transferred frame tap's) transverse place off
# the keeper's centre line, for build_fr_top_frame's tap-ligament stack.
KEEPER_SCREW_TRANSVERSE_BAND_MM = _BAND_BY_PLACES[
    DRAWING_PRECISION["FootScrewSideReference"]["ScrewFromSide"]
]

# True free-text instructions only (native dims and callouts carry the rest;
# the bore's pair reaming is its callout, BORE_PAIR_CALLOUT). Brackets carry
# no frames and no datums (policy).
DRAWING_NOTES = "\n".join(
    (
        "1. MAKE FROM AISI 1018 BAR; BLACK OXIDE AFTER MACHINING.",
        "2. CROWN TAP FOR THE MHA-VN-055 CUP-POINT SET SCREW; FOOT HOLE",
        "   FOR THE MHA-VN-022 #2-56 FILLISTER, HEAD FLUSH.",
        "3. 2 REQUIRED, ONE PER MHA-CH-004 FULCRUM-SHAFT END (SECOND",
        "   IS THIS PART FLIPPED 180 DEG ABOUT VERTICAL).",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
