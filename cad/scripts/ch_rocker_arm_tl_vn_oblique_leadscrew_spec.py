r"""Pure layout contract for the oblique-trammel jig's leadscrew feed (PR C4).

Shop tooling, not a machine part (cad/docs/subsystem-identities.md). The feed
adds a controlled finish feed to the TL-00 jig (MHA-CH-06-TL-00); the TL-26
feed lever stays for roughing. Values marked ⚙ are read from the calculator
``ch_rocker_arm_tl_oblique_trammel_spec`` (imported as ``trammel``) or a
sibling part spec, never retyped.

What it is: a Tr8x2 screw parallel to rail 1, on the rail's column side
(+lateral), turning in two KP08 pillow blocks. Each block stands on an
end bracket (TL-28, two off) bolted on base bar 1's top. A flanged brass
nut, screwed directly to the integral lug of feed block TL-32, drives
carriage 1. The handwheel
(``fixtures.trammel-handwheel``) sits on the screw's outboard end, past the
base bar's far end, so the wheel overhangs it.

Frames. Layout stations are rail 1's: ``s`` along the rail from the spindle
(``trammel.rail_point``) ⚙, ``lateral`` square to it (+ toward the column), and
machine Z (table top = 0). Each new part's own frame is given with its
envelope below. In base bar 1's part frame, x = s - RAIL_NEAR_S ⚙ and
y = -lateral; the turned-over bar under rail 2 carries the same holes, unused.

Why the column side: the far hold-down stud stands on the rail's front side
(lateral -37.5 ⚙ at s 405 ⚙, up to STUD_TOP_Z), away from the feed
block's travel. The near stud (column side, s 35.9 ⚙) lies short of the near
KP08 bracket, so the screw never passes a stud.

Why lateral 55: the KP08 envelope (55 across the axis, ``KP08_MARGIN`` all
round) must stay outside pivot block 1's side (lateral 20 ⚙), which runs
between the two blocks; the 25.4-high bracket lifts the axis to 53.1.
The handwheel grip sweeps to Z74.6, below the carrier underside at Z80.2.
Each bracket stands wholly on bar 1 (the user's 2026-10-17 ruling A′: the
bar widened to 1/2 x 6, its column-side edge at lateral 88.9 ⚙), its outer
end flush with that edge, on 4 x #8 screws in one row: two pairs symmetric
about the screw axis, the inner at ±11, the outer at ±27.5, the round
half-span inside the rule-17 window (below) between the #8 tap's wall to the
KP08's outer #6-32 tap in TL-28 and TL-20's counterbore wall to the bar's edge.

Travel. The KP08 blocks sit at least FEED_GAP outside the feed lug's reach
over the carriage travel ``trammel.CARRIAGE_TRAVEL`` ⚙ (107.2 .. 421.4, both
passes); the screw runs NEAR_STUB past the near KP08 and on into the
handwheel's bore past its grub and its set-screw flat
(HANDWHEEL_ENGAGEMENT_MIN), short of the wheel's outer face; the hub stands
HUB_GAP past the far block: SCREW_LENGTH 410. The stations
and the screw length are fixed (the drilled parts carry them); self-checks
guard them against the bought block, so a vendor swap changes the bought
numbers and TL-32's nut interface only, or trips a check.

The nut remains attached to the feed block during either feed mode. Align
the KP08 blocks to the nut at both travel ends before tightening their
floating mounting screws; no transfer spotting is required.

Thrust is taken on the KP08 inner-ring set screws gripping the plain thread
(no journals; the AMPEC block has no axial or end-play rating): a hand-fed
finish pass only.

LOAD_CASES (ruling A′): 1 kN hand-abuse thrust along the screw at its axis
(lateral 55, 40.4 above the bar top), on each TL-28's 4 x #8-32 torqued to
2.8 N·m (25 in·lbf; head bearing on TL-20's counterbore floor limits it):
preload T/(0.2 d) 3.36 kN a screw; the row's centroid is on the screw axis
(e = 0), so the bracket slips at 2.69 kN (μ 0.2, margin 2.69). It starts to
open (F·h = n·P·w/6, w 12.7) at 704 N. Owner ruling 2026-10-23: the
hand-cranked Tr8 cannot reach 1 kN, so the no-opening requirement is 700 N
(``NO_OPENING_THRUST``); the slip requirement stays 1.5 x 1 kN.

Bought dimensions live in one block below (``# --- Bought items``). Items
marked UNVERIFIED are assumed until verified on receipt.
"""

from __future__ import annotations

import math
from fractions import Fraction

import _config
import ch_rocker_arm_tl_oblique_base_bar_spec as base_bar
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
from _hole_spec import THREAD_MAJOR_MM, HoleSpec
from _printed_tolerance import printed_band_mm

INCH = trammel.INCH

# --- Identities ------------------------------------------------------------------
END_BRACKET = "ch-rocker-arm-tl-oblique-end-bracket"
END_BRACKET_NUMBER = "MHA-CH-06-TL-28"
END_BRACKET_QUANTITY = 2
RAIL = 1  # the screw runs beside rail 1 and drives carriage 1

# Shop-inventory ids (cad/process/shop/inventory.toml); the inventory owns
# each item's source and SKU.
SCREW_ID = "fixtures.trammel-tr8-leadscrew"
NUT_ID = "fixtures.trammel-tr8-flange-nut"
KP08_ID = "fixtures.trammel-kp08-blocks"
HANDWHEEL_ID = "fixtures.trammel-handwheel"

# --- Bought items: every bought dimension, in one place -------------------------
# Tr8x2 leadscrew, Zyltech, single start, lead 2; plain thread end to end,
# 600 stock.
SCREW_MAJOR_DIA = 8.0
SCREW_LEAD = 2.0
SCREW_STOCK_LENGTH = 600.0
# Flanged brass nut, Zyltech HW-SC-T8x2: flange Ø22 x 3.5, 4 x Ø3.5 THRU on
# a Ø16 circle at 45°; body Ø10.2, axially a 1.5 spigot, the flange and a 10
# body: 15 overall.
NUT_FLANGE_DIA = 22.0
NUT_FLANGE_THICK = 3.5
NUT_HOLE_DIA = 3.5
NUT_HOLE_PCD = 16.0
NUT_HOLE_ANGLES_DEG = (45.0, 135.0, 225.0, 315.0)
NUT_BODY_DIA = 10.2
NUT_LENGTH = 15.0
NUT_BODY_SHORT = 1.5  # the spigot, in TL-32's -X counterbore
NUT_BODY_LONG = NUT_LENGTH - NUT_FLANGE_THICK - NUT_BODY_SHORT  # 10, proud on -X
# US-customary UNC (fastener policy): the flange's Ø3.5 plain holes float a
# #4-40 (major 2.845) 0.33 a side. Each button head (MHA-CH-06-TL-VN-66)
# bears directly on the brass flange, no washer (owner ruling 2026-10-20).
NUT_SCREW = "#4-40"
# Derived from the nut above, so a vendor swap changes numbers only.
NUT_SCREW_MAJOR = THREAD_MAJOR_MM[NUT_SCREW]
INCH_SCREW_LENGTHS = ("1/4", "5/16", "3/8", "7/16", "1/2", "5/8", "3/4")  # SHCS
# Rule 18 at the worst case: the shortest screw (ASME B18.3, -0.03 in up to
# 1 in long, plus nothing) past the grip, less the screw tip's incomplete
# threads (rule 18's 1.5 pitches) and the tap mouth's title-block edge break.
SHCS_LENGTH_TOL_MM = 0.03 * INCH  # STANDARD: ASME B18.3 (SHCS, BHCS), to 1 in long
TAP_MOUTH_BREAK = float(_config.title_block("edge_break")["chamfer_max_mm"])
_TIP_INCOMPLETE_PITCHES = 1.5  # rule 18
# Each bought screw is the shortest stock length whose worst-case full thread
# reaches 2 D: rule 18's 1.5 D and half a diameter more, so a bought flange or
# foot thicker than its unbanded catalogue nominal still leaves 1.5 D.
ENGAGEMENT_TARGET_D = 2.0


def full_thread_min(length: str, grip: float, thread: str) -> float:
    """Worst-case full-thread engagement of an inch B18.3 socket screw
    ``length`` long past ``grip`` (the grip at its nominal: the bought parts
    state no band)."""
    pitch = INCH / float(thread.rsplit("-", 1)[1])
    return (
        float(Fraction(length)) * INCH
        - SHCS_LENGTH_TOL_MM
        - grip
        - _TIP_INCOMPLETE_PITCHES * pitch
        - TAP_MOUTH_BREAK
    )


def _shortest_length(grip: float, thread: str) -> str:
    return min(
        (
            length
            for length in INCH_SCREW_LENGTHS
            if full_thread_min(length, grip, thread)
            >= ENGAGEMENT_TARGET_D * THREAD_MAJOR_MM[thread]
        ),
        key=Fraction,
    )


# UNVERIFIED: the vendor gives the flange's 3.5 with no band; a thicker flange
# takes engagement off one for one (ENGAGEMENT_TARGET_D's half diameter).
NUT_SCREW_GRIP = NUT_FLANGE_THICK  # the head on the flange: 3.5
NUT_SCREW_LENGTH = _shortest_length(NUT_SCREW_GRIP, NUT_SCREW)  # 1/2
NUT_SCREW_LENGTH_MM = float(Fraction(NUT_SCREW_LENGTH)) * INCH  # 12.7
NUT_SCREW_ENGAGEMENT = NUT_SCREW_LENGTH_MM - NUT_SCREW_GRIP  # 9.2 nominal
NUT_SCREW_FULL_THREAD_MIN = full_thread_min(
    NUT_SCREW_LENGTH, NUT_SCREW_GRIP, NUT_SCREW
)  # 7.236, 2.54 D
# The longest screw (B18.3: never long) on the flange's nominal stops 0.8
# inside TL-32's full thread.
NUT_SCREW_TAP_DEPTH = NUT_SCREW_ENGAGEMENT + 0.8  # full thread: 10.0
# KP08 pillow block. Verified: axis height, bolt spacing, length, height, bore.
KP08_AXIS_HEIGHT = 15.0
KP08_BOLT_SPACING = 42.0
KP08_LENGTH = 55.0  # across the screw axis
KP08_HEIGHT = 29.0
KP08_BORE = 8.0
KP08_WIDTH = 13.0  # UNVERIFIED: axial width, verify on receipt
# US-customary UNC (fastener policy): the block's plain holes, sized for its
# maker's M4, float a #6-32 (major 3.505).
KP08_SCREW = "#6-32"
KP08_HOLE_DIA = 4.5  # UNVERIFIED: the smaller of the 4.5 / 4.8 M4 holes
KP08_FOOT_THICK = 5.0  # UNVERIFIED: base (foot) thickness
# Rule 18 through the foot at its unverified nominal (a thicker foot takes
# engagement off one for one: ENGAGEMENT_TARGET_D's half diameter). The 5/8
# tip stops inside TL-28's 25.4 THRU tap.
KP08_SCREW_LENGTH = _shortest_length(KP08_FOOT_THICK, KP08_SCREW)  # 5/8
KP08_SCREW_FULL_THREAD_MIN = full_thread_min(
    KP08_SCREW_LENGTH, KP08_FOOT_THICK, KP08_SCREW
)  # 8.67, 2.47 D
KP08_MARGIN = 3.0  # clearance-check envelope margin, all round (Main)
# Misumi HOK40-HC8 handwheel, along the screw axis from the hub end outward:
# hub, rim, then the grip standing off the rim's outer face. Source: the
# vendor STEP HOK40-HC8.step (sha256 a9c2c04c...a7af), measured by JigBought;
# the hub, rim, bore, grip offset and set-screw station agree with the
# catalogue, the grip does not (the catalogue's 18.8 projection and Ø13 are
# the STEP's 21.0 and Ø14). Bore Ø8 H8 THRU, through hub and rim; 2 x M5
# radial holes in the hub, one set screw supplied.
HANDWHEEL_HUB_DIA = 22.0
HANDWHEEL_HUB_LENGTH = 13.0
HANDWHEEL_WHEEL_DIA = 40.0
HANDWHEEL_WHEEL_LENGTH = 12.0
HANDWHEEL_BORE_LENGTH = 25.0
# Grip: a Ø10 x 5 collar, a taper Ø12 to Ø14, Ø14 to an R2 end; Ø14 is its max.
HANDWHEEL_GRIP_DIA = 14.0
HANDWHEEL_GRIP_LENGTH = 21.0  # past the rim's outer face
HANDWHEEL_GRIP_OFFSET = 14.5  # grip axis from the screw axis
HANDWHEEL_LENGTH = 46.0  # overall
HANDWHEEL_GRUB = "M5"
HANDWHEEL_GRUB_FROM_HUB = 6.5  # grub axis from the hub end
# The grip sweeps radius 21.5 as the wheel turns, past the rim's 20: the
# envelope is that swept Ø43 over the handwheel's whole length (conservative).
HANDWHEEL_SWEEP_R = max(
    HANDWHEEL_WHEEL_DIA / 2.0, HANDWHEEL_GRIP_OFFSET + HANDWHEEL_GRIP_DIA / 2.0
)  # 21.5

# --- Layout (rail-1 stations s, lateral; machine Z) -------------------------------
SCREW_LATERAL = 55.0
BRACKET_THICK = 1.0 * INCH  # OnlineMetals 1165 half-by-one bar, on edge
KP08_BASE_Z = trammel.BASE_BAR_THICK + BRACKET_THICK  # 38.1
SCREW_AXIS_Z = KP08_BASE_Z + KP08_AXIS_HEIGHT  # 53.1
HUB_GAP = 6.0  # far KP08 outer face to the handwheel's hub end
# The drilled parts fix the KP08 stations and the screw length; a vendor swap
# must not move them. The self-checks below guard them against the bought
# block: a swap that trips one is a redesign decision.
FEED_GAP = 2.5  # feed lug/nut to KP08 envelope at a travel stop (TL-32 checks)
NEAR_STUB = 2.0  # screw past the near KP08's outer face, as fitted (step 7)
NEAR_STUB_MIN = 1.0  # at least
# The screw's set-screw flat, centred on the handwheel's grub (TL-VN-54).
SCREW_FLAT_LENGTH = 8.0
HANDWHEEL_GRUB_MAJOR = float(HANDWHEEL_GRUB.removeprefix("M"))
# The screw in the handwheel's bore, at least: past the grub's far flank and
# the flat's far end. HANDWHEEL_BORE_LENGTH caps it (the screw end stays
# inside the wheel's outer face).
HANDWHEEL_ENGAGEMENT_MIN = max(
    HANDWHEEL_GRUB_FROM_HUB + HANDWHEEL_GRUB_MAJOR / 2.0,  # 9.0
    HANDWHEEL_GRUB_FROM_HUB + SCREW_FLAT_LENGTH / 2.0,  # 10.5
)

# --- TL-28 end bracket (2 off, identical) -------------------------------
# 6061-T6511 flat 1/2 x 1 in, OnlineMetals 1165, on edge. Frame: origin on
# the bottom face at the inner end (toward the rail), mid-width; +X outward
# (machine +lateral), +Y along the screw away from the spindle, +Z up.
# Envelope X 0 .. 68.9, Y ±6.35, Z 0 .. 25.4.
BRACKET_STOCK = "6061-T6511 flat 1/2 x 1 in (OnlineMetals 1165), on edge"
BRACKET_WIDTH = 0.5 * INCH  # 12.7 along the screw
BRACKET_INNER_LATERAL = 20.0  # 3 clear of the carriage's side (lateral 17 ⚙)
# Ruling A′ (2026-10-17): the outer end flush with bar 1's column-side edge,
# so the bracket stands wholly on the bar (it cantilevered past the 1/2 x 4).
BRACKET_LENGTH = trammel.BASE_BAR_COLUMN_EDGE - BRACKET_INNER_LATERAL  # 68.9
# KP08 screws: #6-32 tapped (through) at 42 centres about the screw axis.
BRACKET_KP08_HOLES_X = tuple(
    SCREW_LATERAL + side * KP08_BOLT_SPACING / 2.0 - BRACKET_INNER_LATERAL
    for side in (-1.0, 1.0)
)  # 14, 56
# Bar screws: #8-32 SHCS up from the bar's underside (counterbored there, the
# head recessed: ``base_bar.BRACKET_CBORE_DEPTH``) into #8-32 tapped THRU holes
# in the bracket; fitted before the bar goes on the table. Top-down
# counterbores leave no wall to the KP08 #6-32 taps.
BAR_SCREW = "#8-32"
BAR_SCREW_LENGTH = "5/8"
# Ruling A′: four in one row, two pairs symmetric about the screw axis, so the
# row's centroid stands under the thrust (LOAD_CASES: e = 0). The inner pair
# keeps C4's 44 (between the KP08's #6-32s); the outer half-span is the round
# value inside the rule-17 window, worst case at the printed bands: its #8 tap
# clear of TL-28's outer #6-32 tap, its TL-20 counterbore clear of the bar's
# column-side edge, both at the 2.0 target.
WALL_TARGET = 2.0  # drawing-guidelines rule 17 (floor base_bar.BRACKET_WALL_MIN)
BAR_SCREW_INNER_HALF_SPAN = SCREW_LATERAL - 44.0  # 11
_TL28_BAND = printed_band_mm(3)  # TL-28's stations print at .XXX
_BAR_SCREW_R = THREAD_MAJOR_MM[BAR_SCREW] / 2.0
_KP08_SCREW_R = THREAD_MAJOR_MM[KP08_SCREW] / 2.0
BAR_SCREW_OUTER_HALF_SPAN_MIN = (
    KP08_BOLT_SPACING / 2.0 + 2.0 * _TL28_BAND + _BAR_SCREW_R + _KP08_SCREW_R
) + WALL_TARGET  # 27.10
BAR_SCREW_OUTER_HALF_SPAN_MAX = (
    trammel.BASE_BAR_COLUMN_EDGE
    - SCREW_LATERAL
    - base_bar.BRACKET_HOLE_BAND
    - base_bar.BRACKET_CBORE_RADIUS_MAX
) - WALL_TARGET  # 27.545
BAR_SCREW_OUTER_HALF_SPAN = math.floor(2.0 * BAR_SCREW_OUTER_HALF_SPAN_MAX) / 2.0
if not (
    BAR_SCREW_OUTER_HALF_SPAN_MIN
    <= BAR_SCREW_OUTER_HALF_SPAN
    <= BAR_SCREW_OUTER_HALF_SPAN_MAX
):
    raise AssertionError("the outer bar screws' half-span leaves its rule-17 window")
BAR_SCREW_LATERALS = tuple(
    SCREW_LATERAL + side * half
    for side, half in (
        (-1.0, BAR_SCREW_OUTER_HALF_SPAN),
        (-1.0, BAR_SCREW_INNER_HALF_SPAN),
        (1.0, BAR_SCREW_INNER_HALF_SPAN),
        (1.0, BAR_SCREW_OUTER_HALF_SPAN),
    )
)  # 27.5, 44, 66, 82.5
BRACKET_BAR_HOLES_X = tuple(
    lateral - BRACKET_INNER_LATERAL for lateral in BAR_SCREW_LATERALS
)  # 7.5, 24, 46, 62.5
SHCS_8_HEAD = 0.164 * INCH  # #8 SHCS head height (ASME B18.3)
SHCS_8_MAJOR = 0.164 * INCH  # #8 thread major diameter
BAR_SCREW_LENGTH_MM = 0.625 * INCH
BAR_SCREW_GRIP = base_bar.BAR_THICK - base_bar.BRACKET_CBORE_DEPTH  # 7.9
BAR_SCREW_ENGAGEMENT = BAR_SCREW_LENGTH_MM - BAR_SCREW_GRIP  # 7.975 nominal
# Worst case at TL-20's printed bands (6.955 .. 8.995).
BAR_SCREW_ENGAGEMENT_RANGE = base_bar.bracket_screw_under_head(BAR_SCREW_LENGTH_MM)

KP08_S = (72.0, 443.0)  # near, far: KP08 axial centre stations
SCREW_LENGTH = 410.0
KP08_FACE_S = (
    KP08_S[0] - KP08_WIDTH / 2.0,  # the near block's outer face
    KP08_S[1] + KP08_WIDTH / 2.0,  # the far block's outer face
)
HUB_END_S = KP08_FACE_S[1] + HUB_GAP
SCREW_NEAR_END_S = KP08_FACE_S[0] - NEAR_STUB
SCREW_FAR_END_S = SCREW_NEAR_END_S + SCREW_LENGTH
HANDWHEEL_ENGAGEMENT = SCREW_FAR_END_S - HUB_END_S  # 18
HANDWHEEL_STUB = SCREW_FAR_END_S - KP08_FACE_S[1]  # screw past the far KP08: 24
HANDWHEEL_S = (HUB_END_S, HUB_END_S + HANDWHEEL_LENGTH)
WHEEL_S = (
    HUB_END_S + HANDWHEEL_HUB_LENGTH,
    HUB_END_S + HANDWHEEL_HUB_LENGTH + HANDWHEEL_WHEEL_LENGTH,
)

# --- Additions to sibling parts -------------------------------------------------
# TL-20 base bar (both bars, single configuration): 8 x #8 SHCS clearance
# THRU (4 at each KP08 station, ruling A′), counterbored from the bar's underside (head flush), bar part frame (x
# from the spindle end, y = -lateral on rail 1). The turned-over bar 2 shows
# them on top, unused.
BASE_BAR_HOLES: tuple[tuple[float, float], ...] = tuple(
    (s - trammel.RAIL_NEAR_S, -lateral)
    for s in KP08_S
    for lateral in BAR_SCREW_LATERALS
)
BASE_BAR_HOLE_SPEC = HoleSpec("counterbore_socket", "#8")  # normal fit


# --- Machine-frame helpers ------------------------------------------------------
def point(s: float, lateral: float) -> tuple[float, float]:
    """Machine XY of a rail-1 station."""
    return trammel.rail_point(RAIL, s, lateral)


def rect(s0: float, s1: float, lat0: float, lat1: float) -> list[tuple[float, float]]:
    """Machine-XY plan polygon of a rail-1-aligned box."""
    return [
        point(s, lat) for s, lat in ((s0, lat0), (s1, lat0), (s1, lat1), (s0, lat1))
    ]


# Stationary plan boxes (s0, s1, lateral0, lateral1) and their Z spans.
KP08_BOXES = {
    f"KP08 {which}": (
        s - KP08_WIDTH / 2.0 - KP08_MARGIN,
        s + KP08_WIDTH / 2.0 + KP08_MARGIN,
        SCREW_LATERAL - KP08_LENGTH / 2.0 - KP08_MARGIN,
        SCREW_LATERAL + KP08_LENGTH / 2.0 + KP08_MARGIN,
    )
    for which, s in zip(("near", "far"), KP08_S)
}
KP08_Z = (KP08_BASE_Z, KP08_BASE_Z + KP08_HEIGHT + KP08_MARGIN)
BRACKET_BOXES = {
    f"end bracket {which}": (
        s - BRACKET_WIDTH / 2.0,
        s + BRACKET_WIDTH / 2.0,
        BRACKET_INNER_LATERAL,
        BRACKET_INNER_LATERAL + BRACKET_LENGTH,
    )
    for which, s in zip(("near", "far"), KP08_S)
}
BRACKET_Z = (trammel.BASE_BAR_THICK, KP08_BASE_Z)
_SCREW_R = SCREW_MAJOR_DIA / 2.0
SCREW_BOX = (
    SCREW_NEAR_END_S,
    SCREW_FAR_END_S,
    SCREW_LATERAL - _SCREW_R,
    SCREW_LATERAL + _SCREW_R,
)
SCREW_Z = (SCREW_AXIS_Z - _SCREW_R, SCREW_AXIS_Z + _SCREW_R)
HANDWHEEL_BOX = (
    HANDWHEEL_S[0],
    HANDWHEEL_S[1],
    SCREW_LATERAL - HANDWHEEL_SWEEP_R,
    SCREW_LATERAL + HANDWHEEL_SWEEP_R,
)
HANDWHEEL_Z = (SCREW_AXIS_Z - HANDWHEEL_SWEEP_R, SCREW_AXIS_Z + HANDWHEEL_SWEEP_R)

# Vertical envelopes remain below the unchanged carrier at every pose.
if not max(KP08_Z[1], HANDWHEEL_Z[1], SCREW_Z[1]) < trammel.CARRIER_UNDERSIDE_Z:
    raise AssertionError("the raised leadscrew system reaches the carrier underside")

# TL-26 sits flat on the carrier's top face; its full swept plan is clear
# in Z without a pose-dependent XY exemption.
FEED_LEVER_CLEARANCE = trammel.CARRIER_TOP_Z - max(
    KP08_Z[1], HANDWHEEL_Z[1], SCREW_Z[1], BRACKET_Z[1]
)
if not FEED_LEVER_CLEARANCE > 0.0:
    raise AssertionError("the raised leadscrew system reaches the feed lever")

# Hold-downs are disjoint in rail coordinates regardless of their fitted Z.
for _stud_s, _stud_lat in trammel.HOLD_DOWN_STUDS:
    for _box in (*KP08_BOXES.values(), *BRACKET_BOXES.values(), SCREW_BOX, HANDWHEEL_BOX):
        if (
            _box[0] - 14.0 <= _stud_s <= _box[1] + 14.0
            and _box[2] - 14.0 <= _stud_lat <= _box[3] + 14.0
        ):
            raise AssertionError("the raised feed system reaches a hold-down envelope")

# --- Self-checks ---------------------------------------------------------------


# Every bracket and the near KP08 stand clear of the near hold-down.
_near_stud_s = trammel.HOLD_DOWN_STUDS[0][0]
if not BRACKET_BOXES["end bracket near"][0] > _near_stud_s + 14.0:
    raise AssertionError("the near bracket reaches the near hold-down's nut")
# Both brackets stand on the bar, inside its ends; the far bracket's screws too.
if not (
    BRACKET_BOXES["end bracket far"][1] < trammel.RAIL_FAR_S
    and BRACKET_BOXES["end bracket near"][0] > trammel.RAIL_NEAR_S
):
    raise AssertionError("an end bracket overhangs its bar's end")
# The wheel overhangs the bar end; its hub clears the far KP08 envelope.
if not HUB_END_S > KP08_BOXES["KP08 far"][1]:
    raise AssertionError("the handwheel hub reaches the far KP08")
_wheel_parts = HANDWHEEL_HUB_LENGTH + HANDWHEEL_WHEEL_LENGTH
if abs(_wheel_parts + HANDWHEEL_GRIP_LENGTH - HANDWHEEL_LENGTH) > 1e-6:
    raise AssertionError("the handwheel's hub, rim and grip miss its length")
if abs(_wheel_parts - HANDWHEEL_BORE_LENGTH) > 1e-6:
    raise AssertionError("the handwheel's bore is not through hub and rim")
if not HANDWHEEL_Z[0] > trammel.BASE_BAR_THICK:
    raise AssertionError("the handwheel's swept grip reaches the bar top")
# The screw: cut from the stock, past both KP08s, past the hub's grub and the
# screw's flat under it, and short of the wheel's outer face, where the hand
# turns it.
if not SCREW_LENGTH <= SCREW_STOCK_LENGTH:
    raise AssertionError("the screw is longer than its stock")
if not NEAR_STUB >= NEAR_STUB_MIN:
    raise AssertionError("the screw stops short of the near KP08")
if not HANDWHEEL_ENGAGEMENT >= HANDWHEEL_ENGAGEMENT_MIN:
    raise AssertionError("the screw stops short of the handwheel's grub or its flat")
if not HANDWHEEL_ENGAGEMENT < HANDWHEEL_BORE_LENGTH:
    raise AssertionError("the screw stands proud of the wheel's outer face")
# The bracket's screws land in the bar between the rail and the bar edge,
# clear of the hold-down slots, rail holes and bar ends.
for _x, _y in BASE_BAR_HOLES:
    if not (trammel.RAIL_WIDTH / 2.0 < abs(_y) < trammel.BASE_BAR_COLUMN_EDGE - 4.0):
        raise AssertionError("a bracket screw hole leaves the bar's free band")
    if not 10.0 < _x < base_bar.BAR_LENGTH - 10.0:
        raise AssertionError("a bracket screw hole is too near a bar end")
    for _sx, _sy in (
        (base_bar.NEAR_SLOT_X, base_bar.NEAR_SLOT_Y),
        (base_bar.FAR_SLOT_X, base_bar.FAR_SLOT_Y),
    ):
        if math.hypot(_x - _sx, _y - _sy) < 20.0:
            raise AssertionError("a bracket screw hole is near a hold-down slot")
# Screw engagement: at least 1.5 diameters, never through the part it enters.
if not (
    1.5 * SHCS_8_MAJOR
    <= BAR_SCREW_ENGAGEMENT_RANGE[0]
    <= BAR_SCREW_ENGAGEMENT
    <= BAR_SCREW_ENGAGEMENT_RANGE[1]
    < BRACKET_THICK
):
    raise AssertionError("the bar screws' engagement in the bracket")
if not (
    1.5 * NUT_SCREW_MAJOR
    <= NUT_SCREW_FULL_THREAD_MIN
    < NUT_SCREW_ENGAGEMENT
    < NUT_SCREW_TAP_DEPTH
):
    raise AssertionError("the nut flange screws' engagement in the feed block")
if not 1.5 * THREAD_MAJOR_MM[KP08_SCREW] <= KP08_SCREW_FULL_THREAD_MIN:
    raise AssertionError("the KP08 screws' engagement in the end bracket")

# TL-20's counterbores stand clear of the bar's column-side edge at the 2.0
# target (ruling A′: the outer screws sit 6.4 in from it), every wall at the
# rule-17 floor.
_bar_walls = base_bar.bracket_hole_walls(BASE_BAR_HOLES)
if _bar_walls["-Y edge"] < WALL_TARGET:
    raise AssertionError("a TL-20 bracket counterbore is under 2.0 from the bar edge")
if min(_bar_walls.values()) < base_bar.BRACKET_WALL_MIN:
    raise AssertionError(f"a TL-20 bracket hole wall is under rule 17: {_bar_walls}")

# --- LOAD_CASES (ruling A′): one TL-28 on its 4 x #8, hand-abuse thrust --------
# The #8 bracket screws' torque: one TL-00 figure (step 1), 25 in·lbf, set by
# the head's bearing on TL-20's counterbore floor (BRACKET_HEAD_BEARING_MIN),
# printed as 2.8 N·m.
BAR_SCREW_TORQUE_IN_LBF = 25
BAR_SCREW_TORQUE_NM = round(BAR_SCREW_TORQUE_IN_LBF * 0.112984829, 1)  # 2.8
NUT_FACTOR = 0.2  # dry steel SHCS, T = K * P * d
BAR_SCREW_PRELOAD = BAR_SCREW_TORQUE_NM / (NUT_FACTOR * SHCS_8_MAJOR / 1000.0)  # N
HAND_ABUSE_THRUST = 1000.0  # N, along the screw at its axis
# Owner ruling 2026-10-23: the hand-cranked Tr8 cannot reach 1 kN; TL-28
# must not open below 700 N (the slip requirement stays on 1 kN).
NO_OPENING_THRUST = 700.0  # N
FRICTION_MIN = 0.2  # bracket on the bar, as-machined aluminium
SLIP_MARGIN_MIN = 1.5
_n = len(BAR_SCREW_LATERALS)
_centroid = sum(BAR_SCREW_LATERALS) / _n
_r = [abs(lateral - _centroid) for lateral in BAR_SCREW_LATERALS]
BAR_SCREW_THRUST_ECCENTRICITY = SCREW_LATERAL - _centroid  # 0: the pairs centre
# The worst screw's shear per newton of thrust: direct plus the group's twist.
_worst_shear = 1.0 / _n + abs(BAR_SCREW_THRUST_ECCENTRICITY) * max(_r) / sum(
    r * r for r in _r
)
BRACKET_SLIP_THRUST = FRICTION_MIN * BAR_SCREW_PRELOAD / _worst_shear  # 2.69 kN
# Opening onset: the thrust's moment about the bracket's heel, at the screw
# axis above the bar top, against the row's preload over the bracket width.
_thrust_height = SCREW_AXIS_Z - trammel.BASE_BAR_THICK  # 40.4
BRACKET_OPENING_THRUST = (
    _n * BAR_SCREW_PRELOAD * BRACKET_WIDTH / (6.0 * _thrust_height)
)  # 704 N
if BRACKET_SLIP_THRUST < SLIP_MARGIN_MIN * HAND_ABUSE_THRUST:
    raise AssertionError(
        f"TL-28 slips at {BRACKET_SLIP_THRUST:.0f} N, under "
        f"{SLIP_MARGIN_MIN} x the {HAND_ABUSE_THRUST:.0f} N hand-abuse thrust"
    )
if not BRACKET_OPENING_THRUST > NO_OPENING_THRUST:
    raise AssertionError(
        f"TL-28 opens at {BRACKET_OPENING_THRUST:.0f} N, under the "
        f"{NO_OPENING_THRUST:.0f} N no-opening requirement"
    )
