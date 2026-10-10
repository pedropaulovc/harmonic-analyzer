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
top-frame rail top face with one slotted #4-40 narrow-fillister screw
(frame-side-screw, MHA-VN-022) seated flush in a counterbore. 2 required, one
per shaft end (the second is the same part flipped Ry180 by the assembly).

Part frame: +X = along the shaft, OUTBOARD (away from the lever bank); +Y up
from the seat; +Z across the width. The lug mid-plane (= set-screw axis) is
x = 0; the lug spans x -3..+3 from the seat to the crown, the foot runs
outboard from the lug's outer face to x = FOOT_TIP_X, and the whole
underside x -3..+13.5 is the flat seat.
"""

from __future__ import annotations

from math import sqrt

from _fit_limits import REAM_SLIDE
from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from dt_cone_pivot_post_installation import CHANNEL_Z0

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
# shaft. REAM_SLIDE (+0.025/+0.010) over the shaft's 0/-0.020 band gives
# 0.010-0.045 diametral clearance: the shaft slides through both lugs at
# assembly and the set screw then pulls it onto the bore wall, so the fit
# only has to locate it, not run on it. ch_fulcrum_shaft_spec pins the
# nominal to its SHAFT_DIA.
BORE_DIA = 6.35
BORE_DIA_BAND = REAM_SLIDE

# --- Foot screw: one #4 close-clearance drill + counterbore centred on the
# foot, for the #4-40 narrow fillister (MHA-VN-022). The under-head plane
# sits at FOOT_H - CBORE_DEPTH. ---
FOOT_SCREW_THREAD = "#4-40"
SCREW_X = LUG_HALF_T + FOOT_L / 2.0  # 8.25: foot centre
SCREW_FROM_LUG_FACE = SCREW_X - LUG_HALF_T  # 5.25 basic off datum B
KEEPER_SCREW_Z_OFF = KEEPER_Z_OFF + SCREW_X  # 82.25: screw off the centre
SCREW_CLEARANCE_SPEC = HoleSpec("clearance", "#4", fit="close")
HOLE_DIA_MM = blind_cut_dia_mm(SCREW_CLEARANCE_SPEC)
# Ø5.1 clears the Ø4.648 stock head; the depth is the exact stock head
# height (vn_frame_side_screw_spec.HEAD_H, pinned by the part build), so the
# head is flush.
CBORE_DIA_MM = 5.1
CBORE_DEPTH_MM = 2.7178
SCREW_HOLE_SPEC = HoleSpec(
    "counterbore_fillister",
    SCREW_CLEARANCE_SPEC.size,
    overrides_mm={
        "HoleDiameter": HOLE_DIA_MM,
        "CounterBoreDiameter": CBORE_DIA_MM,
        "CounterBoreDepth": CBORE_DEPTH_MM,
    },
)
# The frame's receiver tap (build_fr_top_frame KeeperTaps, at the fulcrum
# line x and FULCRUM_KEEPER_CENTRE_Z +- KEEPER_SCREW_Z_OFF). The 1/2 in screw enters
# 12.7 - (FOOT_H - CBORE_DEPTH_MM) = 7.42 (2.6D); 9.0 of thread keeps 0.78 at
# the .X depth minimum, and the 14.0 drill keeps a plug tap's five-pitch lead
# below the thread at the .X worst case of both depths.
KEEPER_TAP_SPEC = HoleSpec(
    "tapped",
    FOOT_SCREW_THREAD,
    end="blind",
    depth_mm=14.0,
    overrides_mm={"ThreadDepth": 9.0},
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
# the outer lug face (datum B) and the lug thickness prints separately, both
# at .XXX (user ruling: a 6.0 lug cannot hold a 1.5 web at .XX for any set
# screw), so the inner web loses both bands.
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
# Counterbore to the foot tip: the foot length prints .X off datum B, the
# hole sits at its basic station inside the position zone (radius = half the
# position tolerance) and the counterbore is a drilled diameter. The lug side
# is no wall: the foot runs on under the lug to x = -3.
_SCREW_POSITION_RADIUS = 0.25 / 2.0  # GEOMETRIC_TOLERANCES_MM screw-hole position
FOOT_TIP_WALL_MM = (
    (FOOT_L - _BAND_BY_PLACES[1])
    - (SCREW_FROM_LUG_FACE + _SCREW_POSITION_RADIUS)
    - (CBORE_DIA_MM + _DRILLED_PLUS) / 2.0
)
if FOOT_TIP_WALL_MM < 1.5:
    raise AssertionError(f"keeper counterbore tip wall {FOOT_TIP_WALL_MM:.2f} < 1.5")

# Hidden reference sketch (policy rule 2, the dt_arbor_pedestal pattern): the
# set-screw tap's station off the outer lug face is a manufacturing dimension
# no feature measures (the tap is placed on the mid-plane), so a one-line
# construction sketch on the crown-top outline carries it. The part saves it
# blanked; the drawing shows it in the front view.
REFERENCE_SKETCHES = ("SetScrewReference",)

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
}
# Decimal places ARE the tolerance statement (policy rule 2), so the MODEL
# owns them. One place is the general grade: the counterbore's tip wall and
# the crown thread are sized at the .X worst case (FOOT_TIP_WALL_MM,
# SET_SCREW_ENGAGEMENT_D). The shaft-axis height takes two (both keepers
# level the shaft the levers rock on); the reamed bore carries its own
# REAM_SLIDE band; the lug thickness and the tap station take three, the
# web's worst case (SET_SCREW_WEB_MM).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "LugProfile": {"LugRise": 2},
    "LugBody": {"LugThickness": 3},
    "FootProfile": {"FootLength": 1, "FootRise": 1},
    "Foot": {"Depth": 1},
    "LugCrownProfile": {"CrownDia": 1},
    "ShaftBoreProfile": {"BoreDia": 3},
    "SetScrewReference": {"SetScrewLocation": 3},
}
if {f: set(names) for f, names in DRAWING_PRECISION.items()} != DRAWING_DIMENSIONS:
    raise AssertionError("DRAWING_PRECISION and DRAWING_DIMENSIONS disagree")
if DRAWING_PRECISION["LugBody"]["LugThickness"] != 3 or (
    DRAWING_PRECISION["SetScrewReference"]["SetScrewLocation"] != 3
):
    raise AssertionError("the crown-tap web is sized at .XXX lug and tap station")
if DRAWING_PRECISION["FootProfile"]["FootLength"] != 1:
    raise AssertionError("the counterbore tip wall is sized at the .X foot length")
if DRAWING_PRECISION["LugCrownProfile"]["CrownDia"] != 1:
    raise AssertionError("the crown thread is sized at the .X crown diameter")

# True free-text instructions only (native dims/datums/FCFs carry the rest).
DRAWING_NOTES = "\n".join(
    (
        "1. MAKE FROM AISI 1018 BAR; BLACK OXIDE AFTER MACHINING.",
        "2. REAM THE SHAFT BORE: SLIDE FIT ON THE MHA-CH-004 FULCRUM SHAFT.",
        "3. CROWN TAP FOR THE MHA-VN-055 CUP-POINT SET SCREW; FOOT HOLE",
        "   FOR THE MHA-VN-022 #4-40 FILLISTER, HEAD FLUSH.",
        "4. 2 REQUIRED, ONE PER FULCRUM-SHAFT END (SECOND IS",
        "   THIS PART FLIPPED 180 DEG ABOUT VERTICAL).",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"

# Manufacturing GD&T limits consumed by the drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "screw-hole position": "0.25",
    "foot seating face flatness": "0.05",
}
if float(GEOMETRIC_TOLERANCES_MM["screw-hole position"]) / 2.0 != (
    _SCREW_POSITION_RADIUS
):
    raise AssertionError("the tip wall's position zone drifted from the FCF")
