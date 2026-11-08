r"""Pure layout contract for the oblique-trammel jig's leadscrew feed (PR C4).

Shop tooling, not a machine part (cad/docs/subsystem-identities.md). The feed
adds a controlled finish feed to the TL-00 jig (MHA-CH-06-TL-00); the TL-26
feed lever stays for roughing. Values marked ⚙ are read from the calculator
``ch_rocker_arm_tl_oblique_trammel_spec`` (imported as ``trammel``) or a
sibling part spec, never retyped.

What it is: a Tr8x2 screw parallel to rail 1, on the rail's column side
(+lateral), turning in two KP08 pillow blocks. Each block stands on an
end bracket (TL-28, two off) bolted on base bar 1's top. The bought brass
flange nut, supplied with the screw and its spigot faced off, is screwed to
the integral lug of feed block TL-32 and drives carriage 1. The handwheel
(``fixtures.trammel-handwheel``) sits on the screw's outboard end, its rim
past the base bar's far end, so the wheel overhangs it.

Frames. Layout stations are rail 1's: ``s`` along the rail from the spindle
(``trammel.rail_point``) ⚙, ``lateral`` square to it (+ toward the column), and
machine Z (table top = 0). Each new part's own frame is given with its
envelope below. In base bar 1's part frame, x = s - RAIL_NEAR_S ⚙ and
y = -lateral; only base bar 1 (TL-20's ``Bar1`` configuration) carries the
bracket holes, the turned-over bar under rail 2 (``Bar2``) has none.

Why the column side: the far hold-down stud stands on the rail's front side
(lateral -1.48 ⚙ at bar station 15.35 ⚙, up to STUD_TOP_Z), away from the
feed block's travel. The near stud (column side, s 37.1 ⚙) lies short of the near
KP08 bracket, so the screw never passes a stud.

Why lateral 2.165 (54.991): the KP08 envelope (55 across the axis,
``KP08_MARGIN`` all round) must stay outside pivot block 1's side (lateral 20
⚙), which runs between the two blocks; the 1 in bracket on the faced .47 bar
lifts the axis to 52.338. The handwheel grip sweeps below the carrier
underside.
Each bracket stands wholly on bar 1 (the user's 2026-10-17 ruling A′: the
bar widened, now 5.50 wide, its column-side edge at lateral 88.9 ⚙), its outer
end flush with that edge. TL-28 has only two through holes, at the KP08's
42 bolt spacing about the screw axis, #29 drilled THRU with limited #8-32
threads from both faces. A #8-32 x 5/8 SHCS enters from each side; TL-20's
underside counterbore is .200 ±.005. TL-28's full-thread and opposed-cut
limits protect both complete physical screw reaches (owner A″).

Travel. The KP08 blocks sit at least FEED_GAP outside the feed lug's reach
over the carriage travel ``trammel.CARRIAGE_TRAVEL`` ⚙ (107.2 .. 421.4, both
passes); the screw runs NEAR_STUB past the near KP08 and on into the
handwheel's bore past its grub and its set-screw flat
(HANDWHEEL_ENGAGEMENT_MIN), short of the wheel's outer face; the hub stands
HUB_GAP past the far block: SCREW_LENGTH 410. The stations
and the screw length are fixed (the drilled parts carry them); self-checks
guard them against the bought block, so a vendor swap changes the bought
numbers only, or trips a check.

The nut remains attached to the feed block during either feed mode. Align
the KP08 blocks at both travel ends so the screw runs centred in the feed
lug's clearance before tightening their floating mounting screws; the lug's
nut taps are then transferred from the seated nut (TL-00 F2).

Thrust is taken on the KP08 inner-ring set screws gripping the screw's flats
(no journals; the uxcell block has no axial or end-play rating): a hand-fed
finish pass only.

LOAD_CASES: 1 kN hand-abuse thrust along the screw at its axis (lateral
2.165, 40.4 above the bar top), on each TL-28's 2 x #8-32 torqued to 2.8 N·m
(25 in·lbf; head bearing on TL-20's counterbore floor limits it): preload
T/(0.2 d) 3.36 kN a screw; the pair's centroid is on the screw axis (e = 0),
so the bracket slips at 1.34 kN (μ 0.2). It starts to open (F·h = n·P·w/6,
w 12.7) at 352 N. Owner ruling 2026-11-06 (Main, option B of the PR2
two-hole review, replacing the 2026-10-27 "slip governs" criterion for the
TL-28/TL-20 joint): above that slip load the bracket may slip until the
screws' threads bear on TL-20's clearance holes, a positive stop. The
owner's R4 ruling (Main, relayed by the coordinator after farm 84d5991d45)
keeps option B and accepts up to 1.06 mm lost motion on reversal (the
option-B ruling's ~.9 mm superseded). TL-20's #12 (.189) clearance holes
hold this joint's worst case to 0.876 mm (the largest drilled hole over the
#8 UNC-3A minimum major; 0.737 at its basic major), unchanged.
That bound is the TL-28-on-TL-20 joint alone; the KP08-on-TL-28 joint above
it (Ø5 holes, UNVERIFIED #2184) was never slip-checked and is not included
(``KP08_SCREW_FLOAT_MAX``, an open question). The joint must not slip under
the normal finish-feed thrust (the jig assembly spec derives it from the
cutter load), and the positive stop must carry the abuse envelope (the 1 kN
abuse or TL-00's 1361 N firm 70 N hand pull, whichever is greater) in
thread/hole bearing and screw shear (``bracket_stop_margins``).

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
from _inch_wall_limits import WALL_TARGET_MM

INCH = trammel.INCH

# --- Identities ------------------------------------------------------------------
END_BRACKET = "ch-rocker-arm-tl-oblique-end-bracket"
END_BRACKET_NUMBER = "MHA-CH-06-TL-28"
END_BRACKET_QUANTITY = 2
RAIL = 1  # the screw runs beside rail 1 and drives carriage 1

# Shop-inventory ids (cad/process/shop/inventory.toml); the inventory owns
# each item's source and SKU.
SCREW_ID = "fixtures.trammel-tr8-leadscrew"
KP08_ID = "fixtures.trammel-kp08-blocks"
HANDWHEEL_ID = "fixtures.trammel-handwheel"

# --- Bought items: every bought dimension, in one place -------------------------
# Tr8x2 leadscrew, ReliaBot (Amazon B085DDHJTW, read 2026-11-04): SUS304,
# single start, lead 2; plain thread end to end, 600 stock.
SCREW_MAJOR_DIA = 8.0
SCREW_LEAD = 2.0
SCREW_STOCK_LENGTH = 600.0
# US-customary UNC (fastener policy). Rule 18 at the worst case: the shortest
# screw (ASME B18.3, -0.03 in up to 1 in long, plus nothing) past the grip,
# less the screw tip's incomplete threads (rule 18's 1.5 pitches) and the tap
# mouth's title-block edge break.
INCH_SCREW_LENGTHS = ("1/4", "5/16", "3/8", "7/16", "1/2", "5/8", "3/4")  # SHCS
SHCS_LENGTH_TOL_MM = 0.03 * INCH  # STANDARD: ASME B18.3 (SHCS), to 1 in long
TAP_MOUTH_BREAK = float(_config.title_block("edge_break")["chamfer_max_mm"])
_TIP_INCOMPLETE_PITCHES = 1.5  # rule 18
# Default purchased-length target: 2D at nominal bought grip, leaving
# tolerance reserve above mandatory 1.5D. Owner A″ explicitly overrides
# this selection target for BAR_SCREW_LENGTH only, not the 1.5D requirement.
ENGAGEMENT_TARGET_D = 2.0


def full_thread_min(length: str, grip: float, thread: str) -> float:
    """Worst-case full-thread engagement of an inch B18.3 socket screw
    ``length`` long past ``grip`` (the grip at its worst case: the caller's)."""
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


# KP08 pillow block, uxcell 6-pack (Amazon B0D2L8M4QR, read 2026-11-04):
# "Overall Size: 55 x 13 x 28mm (L*W*H)", "Holes Centre Distance: 42mm",
# "Installation Hole Diameter: 5mm", "Bore Diameter: 8mm", "Width of
# Bearing: 12mm". The listing gives no centre height: 15 is the KP08 series'
# axis height, UNVERIFIED on this block (measure on receipt, step 7).
KP08_AXIS_HEIGHT = 15.0  # UNVERIFIED on the uxcell block: KP08 series value
KP08_BOLT_SPACING = 42.0
KP08_LENGTH = 55.0  # across the screw axis
KP08_HEIGHT = 28.0
KP08_BORE = 8.0
KP08_WIDTH = 13.0  # the listing's W: the housing's axial width
# US-customary UNC (fastener policy): the block's plain Ø5 holes, sized for
# its maker's M4, float a #8-32 (major 4.166) 0.417 a side; the #8 SHCS head
# (Ø.270) still covers the hole at that float (bracket_screw spec, TL-VN-62).
KP08_SCREW = "#8-32"
KP08_HOLE_DIA = 5.0
KP08_FOOT_THICK = 5.0  # UNVERIFIED (#2184): base (foot) thickness, not on the listing
# The nominal-foot 2D selection retains reserve above mandatory 1.5D.
# Owner A″ retains this 5/8 and bounds the receipt foot at .196–.292
# (end-bracket spec); its finite thread/seam contract excludes 3/4.
KP08_SCREW_LENGTH = _shortest_length(KP08_FOOT_THICK, KP08_SCREW)  # 5/8
KP08_SCREW_FULL_THREAD_MIN = full_thread_min(
    KP08_SCREW_LENGTH, KP08_FOOT_THICK, KP08_SCREW
)  # 8.67, 2.08 D
# The KP08 screw's reach past TL-28's top face on the nominal foot: its
# length (B18.3: no plus length tolerance) less the UNVERIFIED 5.0. A thinner
# foot reaches deeper; TL-28's spec takes its tip gap on the least foot.
KP08_SCREW_REACH = float(Fraction(KP08_SCREW_LENGTH)) * INCH - KP08_FOOT_THICK
KP08_MARGIN = 3.0  # clearance-check envelope margin, all round (Main)
# HARFINGTON handwheel (Amazon B0DJ3DZT86, read 2026-11-04), along the screw
# axis from the hub end outward: hub, rim, then the revolving handle standing
# off the rim's outer face. The listing's dimension image gives OD 50, bore
# Ø8, hub ("step") Ø26 x 14 and 27 overall over hub and rim, so the rim is
# 13. Two set screws are supplied; their size is not stated.
HANDWHEEL_HUB_DIA = 26.0
HANDWHEEL_HUB_LENGTH = 14.0
HANDWHEEL_WHEEL_DIA = 50.0
HANDWHEEL_WHEEL_LENGTH = 13.0
# The Ø8 bore is certain only through the hub: the listing's photos of the
# rim's outer face show no through hole. The screw's engagement stays inside
# this guaranteed depth.
HANDWHEEL_BORE_LENGTH = HANDWHEEL_HUB_LENGTH  # UNVERIFIED beyond the hub
# Handle: the listing publishes no handle size or offset. A conservative
# envelope that the photos' handle sits inside: Ø14 x 25 proud of the rim
# face, its axis 17 off the screw axis, so it sweeps inside the rim's 25.
HANDWHEEL_GRIP_DIA = 14.0  # UNVERIFIED envelope
HANDWHEEL_GRIP_LENGTH = 25.0  # UNVERIFIED envelope, past the rim's outer face
HANDWHEEL_GRIP_OFFSET = 17.0  # UNVERIFIED envelope: grip axis from the screw axis
HANDWHEEL_LENGTH = (
    HANDWHEEL_HUB_LENGTH + HANDWHEEL_WHEEL_LENGTH + HANDWHEEL_GRIP_LENGTH
)  # 52 overall
# The set-screw holes: the dimension image shows one at about mid-hub, with
# a hex socket the size of an M5 set screw's 2.5 key. Both UNVERIFIED.
HANDWHEEL_GRUB = "M5"  # UNVERIFIED
HANDWHEEL_GRUB_FROM_HUB = 7.0  # UNVERIFIED: grub axis from the hub end
# The rim (radius 25) governs the swept envelope; the handle sweeps inside it.
HANDWHEEL_SWEEP_R = max(
    HANDWHEEL_WHEEL_DIA / 2.0, HANDWHEEL_GRIP_OFFSET + HANDWHEEL_GRIP_DIA / 2.0
)  # 25

# --- Layout (rail-1 stations s, lateral; machine Z) -------------------------------
# Issue #290: the fabricated layout (axis lateral, the bracket's inner end and
# the bar screws' half-spans) sits on the .001 in grid, so TL-20's rows and
# TL-28's #8 stations print as modelled. The bought values stay exact: the
# KP08's 42 bolt span and 15 axis height, and the KP08 stations along the
# Tr8 screw (its millimetre sheet's flat stations read them).
SCREW_LATERAL = 54.991  # 2.165; TL-32's nut lug reads it
BRACKET_THICK = 1.0 * INCH  # OnlineMetals 1165 half-by-one bar, on edge
KP08_BASE_Z = trammel.BASE_BAR_THICK + BRACKET_THICK  # 37.338
SCREW_AXIS_Z = KP08_BASE_Z + KP08_AXIS_HEIGHT  # 52.338
# Far KP08 outer face to the handwheel's hub end: the 410 screw's far end then
# stands 13 into the wheel's bore, past the grub on its flat (which runs out
# through the cut end, leadscrew_stock.OPEN_FLAT), and 1 short of the hub's
# guaranteed bore depth.
HUB_GAP = 11.0
# The drilled parts fix the KP08 stations and the screw length; a vendor swap
# must not move them. The self-checks below guard them against the bought
# block: a swap that trips one is a redesign decision.
FEED_GAP = 2.5  # feed lug/nut to KP08 envelope at a travel stop (TL-32 checks)
NEAR_STUB = 2.0  # screw past the near KP08's outer face, as fitted (step 7)
NEAR_STUB_MIN = 1.0  # at least
# The screw's set-screw flats' length (TL-VN-84 LeadScrew): each KP08 flat's,
# centred on its set screw; the handwheel's starts half of it short of the grub
# and runs out through the cut end.
SCREW_FLAT_LENGTH = 8.0
HANDWHEEL_GRUB_MAJOR = float(HANDWHEEL_GRUB.removeprefix("M"))
# The screw in the handwheel's bore, at least: past the grub's far flank, and
# half a flat's length past the grub, so the open flat runs as far beyond it
# as toward the hub. HANDWHEEL_BORE_LENGTH caps it (the screw end stays
# inside the wheel's outer face).
HANDWHEEL_ENGAGEMENT_MIN = max(
    HANDWHEEL_GRUB_FROM_HUB + HANDWHEEL_GRUB_MAJOR / 2.0,  # 9.0
    HANDWHEEL_GRUB_FROM_HUB + SCREW_FLAT_LENGTH / 2.0,  # 10.5
)

# --- TL-28 end bracket (2 off, identical) -------------------------------
# 6061-T6511 flat 1/2 x 1 in, OnlineMetals 1165, on edge. Frame: origin on
# the bottom face at the inner end (toward the rail), mid-width; +X outward
# (machine +lateral), +Y along the screw away from the spindle, +Z up.
# Envelope X 0 .. 2.71, Y ±.25, Z 0 .. 1.00.
BRACKET_STOCK = "6061-T6511 flat 1/2 x 1 in (OnlineMetals 1165), on edge"
BRACKET_WIDTH = 0.5 * INCH  # 12.7 along the screw
BRACKET_INNER_LATERAL = 20.066  # .79: 3 clear of the carriage's side (lateral 17 ⚙)
# Ruling A′ (2026-10-17): the outer end flush with bar 1's column-side edge,
# so the bracket stands wholly on the bar (it cantilevered past the 1/2 x 4).
BRACKET_LENGTH = trammel.BASE_BAR_COLUMN_EDGE - BRACKET_INNER_LATERAL  # 2.71
# Two #29 through bores at the KP08's 42 centres. Independently limited
# #8-32 threads from both faces receive the upper and lower 5/8 screws.
# The pair's centroid stands under the thrust (LOAD_CASES: e = 0).
BRACKET_HOLES_X = tuple(
    SCREW_LATERAL + side * KP08_BOLT_SPACING / 2.0 - BRACKET_INNER_LATERAL
    for side in (-1.0, 1.0)
)  # 13.925, 55.925: the vendor span, printed exact in mm
BAR_SCREW_LATERALS = tuple(
    BRACKET_INNER_LATERAL + x for x in BRACKET_HOLES_X
)  # 33.991, 75.991
# Bar screws: #8-32 SHCS up from the bar's underside (counterbored there, the
# head recessed: ``base_bar.BRACKET_CBORE_DEPTH``) into TL-28's holes; fitted
# before the bar goes on the table. Owner 2026-11-07 A″ selects 5/8 in
# place of the normal 2D purchase target; worst full thread remains >=1.5D.
BAR_SCREW = "#8-32"
BAR_SCREW_LENGTH = "5/8"
WALL_TARGET = WALL_TARGET_MM  # drawing-guidelines rule 17 (floor base_bar.BRACKET_WALL_MIN)
SHCS_8_HEAD = 0.164 * INCH  # #8 SHCS head height (ASME B18.3)
SHCS_8_MAJOR = 0.164 * INCH  # #8 thread major diameter
BAR_SCREW_LENGTH_MM = float(Fraction(BAR_SCREW_LENGTH)) * INCH
BAR_SCREW_GRIP = base_bar.BAR_THICK - base_bar.BRACKET_CBORE_DEPTH  # 6.858
BAR_SCREW_ENGAGEMENT = BAR_SCREW_LENGTH_MM - BAR_SCREW_GRIP  # 9.017 nominal
# Geometric range at nominal screw length only: 8.636 .. 9.398.
BAR_SCREW_ENGAGEMENT_RANGE = base_bar.bracket_screw_under_head(BAR_SCREW_LENGTH_MM)
BAR_SCREW_ACTUAL_REACH_RANGE = (
    BAR_SCREW_ENGAGEMENT_RANGE[0] - SHCS_LENGTH_TOL_MM,
    BAR_SCREW_ENGAGEMENT_RANGE[1],
)  # 7.874 .. 9.398; do not subtract short-length twice in full_thread_min.
# Rule 18: the worst-case grip (the thickest bar under the shallowest
# counterbore) and the shortest screw, less its tip's incomplete threads.
BAR_SCREW_GRIP_MAX = BAR_SCREW_LENGTH_MM - BAR_SCREW_ENGAGEMENT_RANGE[0]  # 7.239
BAR_SCREW_FULL_THREAD_MIN = full_thread_min(
    BAR_SCREW_LENGTH, BAR_SCREW_GRIP_MAX, BAR_SCREW
)  # 6.433375, 1.544D

KP08_S = (72.0, 443.0)  # near, far: KP08 axial centre stations
SCREW_LENGTH = 410.0
KP08_FACE_S = (
    KP08_S[0] - KP08_WIDTH / 2.0,  # the near block's outer face
    KP08_S[1] + KP08_WIDTH / 2.0,  # the far block's outer face
)
HUB_END_S = KP08_FACE_S[1] + HUB_GAP
SCREW_NEAR_END_S = KP08_FACE_S[0] - NEAR_STUB
SCREW_FAR_END_S = SCREW_NEAR_END_S + SCREW_LENGTH
HANDWHEEL_ENGAGEMENT = SCREW_FAR_END_S - HUB_END_S  # 13
HANDWHEEL_STUB = SCREW_FAR_END_S - KP08_FACE_S[1]  # screw past the far KP08: 24
HANDWHEEL_S = (HUB_END_S, HUB_END_S + HANDWHEEL_LENGTH)
WHEEL_S = (
    HUB_END_S + HANDWHEEL_HUB_LENGTH,
    HUB_END_S + HANDWHEEL_HUB_LENGTH + HANDWHEEL_WHEEL_LENGTH,
)

# --- Additions to sibling parts -------------------------------------------------
# TL-20 base bar, its Bar1 configuration only (the Bar2 configuration under
# rail 2 is plain): 4 x #8 SHCS clearance THRU (2 under each TL-28, at the
# KP08's stations), counterbored from the bar's underside (head recessed), bar
# part frame (x from the spindle end, y = -lateral on rail 1).
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
    BRACKET_BOXES["end bracket far"][1] < trammel.BASE_BAR_FAR_S
    and BRACKET_BOXES["end bracket near"][0] > trammel.RAIL_NEAR_S
):
    raise AssertionError("an end bracket overhangs its bar's end")
# The wheel's rim overhangs the bar end; its hub clears the far KP08 envelope.
if not HUB_END_S > KP08_BOXES["KP08 far"][1]:
    raise AssertionError("the handwheel hub reaches the far KP08")
if not WHEEL_S[0] > trammel.BASE_BAR_FAR_S:
    raise AssertionError("the handwheel's rim stands over the bar instead of past its end")
_wheel_parts = HANDWHEEL_HUB_LENGTH + HANDWHEEL_WHEEL_LENGTH
if abs(_wheel_parts + HANDWHEEL_GRIP_LENGTH - HANDWHEEL_LENGTH) > 1e-6:
    raise AssertionError("the handwheel's hub, rim and grip miss its length")
if not HANDWHEEL_HUB_LENGTH <= HANDWHEEL_BORE_LENGTH <= _wheel_parts:
    raise AssertionError("the handwheel's bore is not through its hub, inside the wheel")
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
    raise AssertionError("the screw reaches past the handwheel's guaranteed bore")
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
# Rule 18 at the worst case: each screw's full thread at least 1.5 D; neither
# runs through TL-28 (its tip clears the other's: TL-28 spec).
if not (
    1.5 * SHCS_8_MAJOR
    <= BAR_SCREW_FULL_THREAD_MIN
    < BAR_SCREW_ENGAGEMENT_RANGE[0]
    <= BAR_SCREW_ENGAGEMENT
    <= BAR_SCREW_ENGAGEMENT_RANGE[1]
    < BRACKET_THICK
):
    raise AssertionError("the bar screws' engagement in the bracket")
if not 1.5 * THREAD_MAJOR_MM[KP08_SCREW] <= KP08_SCREW_FULL_THREAD_MIN:
    raise AssertionError("the KP08 screws' engagement in the end bracket")

# TL-20's counterbores stand clear of the bar's column-side edge at the .080
# target, every wall at the rule-17 floor.
_bar_walls = base_bar.bracket_hole_walls(BASE_BAR_HOLES)
if _bar_walls["-Y edge"] < WALL_TARGET:
    raise AssertionError("a TL-20 bracket counterbore is under .080 from the bar edge")
if min(_bar_walls.values()) < base_bar.BRACKET_WALL_MIN:
    raise AssertionError(f"a TL-20 bracket hole wall is under rule 17: {_bar_walls}")

# --- LOAD_CASES: one TL-28 on its 2 x #8 bar screws ---------------------------------
# The #8 bracket screws' torque: one TL-00 figure (step 1), 25 in·lbf, set by
# the head's bearing on TL-20's counterbore floor (BRACKET_HEAD_BEARING_MIN),
# printed as 2.8 N·m.
BAR_SCREW_TORQUE_IN_LBF = 25
BAR_SCREW_TORQUE_NM = round(BAR_SCREW_TORQUE_IN_LBF * 0.112984829, 1)  # 2.8
NUT_FACTOR = 0.2  # dry steel SHCS, T = K * P * d
BAR_SCREW_PRELOAD = BAR_SCREW_TORQUE_NM / (NUT_FACTOR * SHCS_8_MAJOR / 1000.0)  # N
HAND_ABUSE_THRUST = 1000.0  # N, along the screw at its axis
FRICTION_MIN = 0.2  # bracket on the bar, as-machined aluminium
SLIP_MARGIN_MIN = 1.5
_n = len(BAR_SCREW_LATERALS)
_centroid = sum(BAR_SCREW_LATERALS) / _n
_r = [abs(lateral - _centroid) for lateral in BAR_SCREW_LATERALS]
BAR_SCREW_THRUST_ECCENTRICITY = SCREW_LATERAL - _centroid  # 0: the pair centres
# The worst screw's shear per newton of thrust: direct plus the group's twist.
_worst_shear = 1.0 / _n + abs(BAR_SCREW_THRUST_ECCENTRICITY) * max(_r) / sum(
    r * r for r in _r
)
BRACKET_SLIP_THRUST = FRICTION_MIN * BAR_SCREW_PRELOAD / _worst_shear  # 1.34 kN
# Opening onset: the thrust's moment about the bracket's heel, at the screw
# axis above the bar top, against the pair's preload over the bracket width.
# Reported, not required: the heel may lift elastically (owner ruling
# 2026-10-27, #1943 review).
_thrust_height = SCREW_AXIS_Z - trammel.BASE_BAR_THICK  # 40.4
BRACKET_OPENING_THRUST = (
    _n * BAR_SCREW_PRELOAD * BRACKET_WIDTH / (6.0 * _thrust_height)
)  # 352 N

# Owner ruling 2026-11-06 (Main, option B of the PR2 two-hole review; it
# replaces the 2026-10-27 no-slip criterion for TL-28 on TL-20): "slip to
# positive thread stop acceptable above ~1344 N (handwheel abuse only)". Its
# "up to ~.9 mm reversal lost motion accepted" is superseded by the owner's
# R4 ruling (Main, relayed by the coordinator after farm 84d5991d45): option
# B retained, reversal lost motion up to 1.06 mm accepted. The #12 geometry
# is kept (a #9 would change the head-to-counterbore contact and the
# engagement). The normal finish feed must not slip
# the bracket (jig assembly spec, NORMAL_FEED_THRUST_N); above BRACKET_SLIP_THRUST
# the bracket moves on TL-20 until each bar screw's thread bears on its
# clearance hole's wall, and the abuse envelope is carried there.
# Lost motion of this lower joint alone (TL-28 on TL-20): the bracket slides
# across the whole diametral float of a bar screw in its TL-20 clearance hole
# at each reversal of the thrust. Guarded at the true worst case: the largest
# DRILLED HOLES clearance hole (the #12's .189 + .004) over the #8's minimum
# major. The bought 91251A196/91251A197 are UNC-3A, whose #8-32 minimum major
# is .1585 in (ASME B1.1, external class 3A). Disclosed beside it: the
# basic-major (.164) figures, 0.368 a side and 0.737 reversal. The upper
# joint (KP08 on TL-28, ``KP08_SCREW_FLOAT_MAX``) is not part of this bound.
SHCS_8_MAJOR_MIN = base_bar.BRACKET_SCREW_MAJOR_MIN  # 4.026
BRACKET_STOP_FLOAT_BASIC = base_bar.BRACKET_SCREW_FLOAT_MAX  # 0.368 a side
# Directly from the largest drilled hole (base bar spec, which also proves
# the counterbore keeps the head clear over this whole travel): offsetting
# the basic figure by SHCS_8_MAJOR (.164 exactly) against the table's 4.166
# basic major dropped 0.0002 of float.
BRACKET_STOP_FLOAT_MAX = base_bar.BRACKET_SCREW_FLOAT_WORST  # 0.438
BRACKET_REVERSAL_LOST_MOTION_BASIC = 2.0 * BRACKET_STOP_FLOAT_BASIC  # 0.737
BRACKET_REVERSAL_LOST_MOTION = 2.0 * BRACKET_STOP_FLOAT_MAX  # 0.876
BRACKET_REVERSAL_LOST_MOTION_ACCEPTED = 1.06  # the R4 ruling's "up to 1.06 mm"
if BRACKET_REVERSAL_LOST_MOTION > BRACKET_REVERSAL_LOST_MOTION_ACCEPTED:
    raise AssertionError(
        f"TL-28 can shift {BRACKET_REVERSAL_LOST_MOTION:.3f} on TL-20 at a reversal, "
        f"over the ruling's {BRACKET_REVERSAL_LOST_MOTION_ACCEPTED}"
    )
# The KP08 on TL-28, for position envelopes (PR4's centred blocks): the #8
# in the KP08's Ø5 hole (UNVERIFIED, #2184) at its minimum major. That joint
# was never slip-checked (an inherited open question, not certified here),
# so a conservative envelope charges this float as well.
KP08_SCREW_FLOAT_MAX = (KP08_HOLE_DIA - SHCS_8_MAJOR_MIN) / 2.0  # 0.487
# The positive stop: each bar screw's thread bears on the wall of TL-20's
# clearance hole over the bar left under the counterbore (its least printed
# length) and on TL-28's thread over its worst-case full thread, and the
# screw shears across its tensile stress area at the joint face. Materials:
# 6061-T6 yield 276 MPa (SOURCED: ASM / MatWeb 6061-T6, as the jig assembly
# spec), taken in bearing; ASTM A574 170,000 psi tensile with 0.6 of it as
# the shear ultimate (the common estimate, as the feed nut's screws); the
# #8-32 tensile stress area 0.0140 in² (ASME B1.1).
AL_YIELD_MPA = 276.0
A574_TENSILE_MPA = 170_000.0 * 0.006894757
SHCS_8_STRESS_AREA_MM2 = 0.0140 * INCH**2
STOP_MARGIN_MIN = SLIP_MARGIN_MIN


def bracket_stop_margins(thrust: float) -> dict[str, float]:
    """The positive stop's margins when one TL-28 has slipped onto its bar
    screws under ``thrust`` (N), carried by the screws alone (no friction)."""
    per_screw = thrust * _worst_shear
    return {
        "TL-20 hole wall bearing": AL_YIELD_MPA
        / (per_screw / (SHCS_8_MAJOR * base_bar.BRACKET_CBORE_FLOOR_MIN)),
        "TL-28 thread bearing": AL_YIELD_MPA
        / (per_screw / (SHCS_8_MAJOR * BAR_SCREW_FULL_THREAD_MIN)),
        "screw shear": 0.6 * A574_TENSILE_MPA / (per_screw / SHCS_8_STRESS_AREA_MM2),
    }


BRACKET_STOP_MARGINS = bracket_stop_margins(HAND_ABUSE_THRUST)
for _check, _margin in BRACKET_STOP_MARGINS.items():
    if _margin < STOP_MARGIN_MIN:
        raise AssertionError(
            f"TL-28's positive stop fails its {_check} at the "
            f"{HAND_ABUSE_THRUST:.0f} N hand-abuse thrust ({_margin:.2f})"
        )
