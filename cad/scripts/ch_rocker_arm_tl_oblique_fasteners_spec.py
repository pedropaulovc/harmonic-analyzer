r"""Fastener table for the oblique-trammel jig (MHA-CH-06-TL-00).

Shop tooling, not a machine part (cad/docs/subsystem-identities.md). Pure
data: every screw and stud the jig consumes, one row per joint, with its
thread, head, printed length, count and the joint it makes. Each row also gives
its grip (the length under the head before the receiving thread) and the
receiving thread's depth, so ``engagement_mm`` and ``protrusion_mm`` follow.
Every value comes from the part specs and the calculator
``ch_rocker_arm_tl_oblique_trammel_spec`` (imported as ``trammel``); no
dimension is retyped here.

The table's engagement is nominal screw/receiver overlap, capped by receiver
depth, not full-thread engagement at tolerance limits. Protrusion is installed
length (bought, or cut at assembly) minus grip minus receiver depth: past the
far face for a THRU tap,
past the full thread for a blind one. A through-tip may project only into
the stated free clearance. Individual screw/washer specs own tolerance
bands, incomplete threads and neighboring geometry; the nominal table
alone does not certify worst-case fit.

Nominal engagement is at least 1.5 diameters except on two joints:

* Carriage (M4 x 20, each cut to fit its own counterbore at assembly): the
  HGH15CA's M4 x 5 holes limit it to 4.80 (1.2 D).
* Feed lever (5/16-18 x 1): nominal engagement is 10.4 (1.3 D).
  The lever-washer spec records the worst-case engagement and possible
  stand-out; the nominal table alone does not bound either.

Threads are US-customary UNC except the bought carriage's M4 holes.
The shoulder screw has its own datum-based row: treating its 1.500 shoulder
as a conventional screw grip would report a false engagement.

Only the feed lever screws use wedge-lock pairs. The four feed nut screws'
flat heads seat in 82° countersinks cut in the brass nut's flange at fit-up.
Hold-down studs retain their loaded lower ends when shortened. These nominal
fit contracts do not certify the jig.

One common screw (oblique simplification PR2): McMaster 91251A197, #8-32 x
3/4 SHCS (``COMMON_SCREW``), wherever its head and engagement fit: the rail
screws and the TL-28 bar screws, 20 in all, one BOM row
(``ch-rocker-arm-tl-vn-oblique-rail-screw``). Every other screw or stud is
in ``COMMON_SCREW_EXCEPTIONS`` with the reason it cannot be the common one.
The KP08 screws are the owner-approved second length, 91251A196 #8-32 x 5/8
(owner ruling 2026-11-06, Main, relayed on PR2): the 3/4 from the top would
meet the bar screw's tip in TL-28's shared hole.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

import ch_rocker_arm_tl_oblique_base_bar_spec as base_bar
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_feed_lever_spec as feed_lever
import ch_rocker_arm_tl_oblique_end_bracket_spec as end_bracket
import ch_rocker_arm_tl_oblique_feed_block_spec as feed_block
import ch_rocker_arm_tl_vn_oblique_leadscrew_kit_feed_nut_spec as feed_nut
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot_block
import ch_rocker_arm_tl_oblique_riser_spec as riser
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_tl_vn_oblique_pivot_screw_spec as pivot_screw
import ch_rocker_arm_tl_oblique_hub_stud_spec as hub_stud
import ch_rocker_arm_tl_oblique_hub_washer_spec as hub_washer
from _hole_spec import THREAD_MAJOR_MM
from _mcmaster_91771a112 import DIMS as _RISER_SCREW

INCH = trammel.INCH
RAILS = 2  # one rail, one base bar, one carriage, one pivot block per side
SHCS = "SHCS"
LOW_HEAD = "LOW-HEAD SHCS"
# The riser's countersinks take only the B18.6.3 machine-screw head; a B18.3
# socket flat head stands proud of them (trammel spec; Codex #1583).
FLAT_HEAD = "B18.6.3 FLAT HEAD"
# The TL-VN-71 wedge-lock pair's stack under each feed lever screw head: the
# 91812A230 band's 0.090 in maximum (the lever washer spec pins it).
LEVER_LOCK_STACK = 0.090 * INCH  # 2.286


def inch_mm(length: str) -> float:
    """Millimetres of a printed inch length: ``"3/4"``, ``"1-3/4"``, ``"3"``."""
    whole, _, fraction = length.rpartition("-") if "-" in length else ("", "", length)
    return float((int(whole or 0) + Fraction(fraction)) * Fraction(str(INCH)))


@dataclass(frozen=True)
class Fastener:
    joint: str
    thread: str  # as printed: "#8-32", "M4"
    head: str  # SHCS or FLAT HEAD
    length: str  # as printed: "3/4" (inch) or "20" (mm)
    count: int
    grip_mm: float  # under the head, before the receiving thread
    thread_depth_mm: float  # receiving full thread: part thickness if THRU
    min_engagement_d: float = 1.5  # in diameters; lower only with a reason
    note: str = ""
    # Free space past a THRU tap's far face that the tip may stand into; 0:
    # the tip stops inside the receiving thread.
    tip_clearance_mm: float = 0.0
    # Cut to fit at assembly: the installed length under the head; None when
    # the screw goes in as bought.
    cut_length_mm: float | None = None

    @property
    def metric(self) -> bool:
        return self.thread.startswith("M")

    @property
    def length_mm(self) -> float:
        return float(self.length) if self.metric else inch_mm(self.length)

    @property
    def installed_length_mm(self) -> float:
        return self.length_mm if self.cut_length_mm is None else self.cut_length_mm

    @property
    def major_mm(self) -> float:
        key = (
            f"{self.thread}x{_METRIC_PITCH[self.thread]}"
            if self.metric
            else self.thread
        )
        return THREAD_MAJOR_MM[key]

    @property
    def engagement_mm(self) -> float:
        # A tip standing past a THRU tap engages only the tap's depth.
        return min(self.installed_length_mm - self.grip_mm, self.thread_depth_mm)

    @property
    def protrusion_mm(self) -> float:
        return self.installed_length_mm - self.grip_mm - self.thread_depth_mm


@dataclass(frozen=True)
class Washer:
    """A washer under a row's heads: its stack adds to that row's grip."""

    joint: str  # the Fastener row's joint it sits in
    size: str  # the screw size it fits: "#8"
    kind: str  # as the fitter names it
    count: int  # one per screw of its row
    thickness_mm: float  # the installed stack under one head


_METRIC_PITCH = {"M4": "0.7"}  # the carriage's M4 only


def callout(fastener: Fastener) -> str:
    """The fitter's name for a screw: ``#8-32 X 3/4 SHCS``, ``M4 X 20 SHCS``."""
    return f"{fastener.thread} X {fastener.length} {fastener.head}"


# --- The table: one row per joint ---------------------------------------------------
RAIL_TO_BAR = Fastener(
    "HGR15 rail to TL-20 base bar",
    trammel.RAIL_SCREW,
    SHCS,
    "3/4",
    trammel.RAIL_HOLE_COUNT * RAILS,  # 8 rail holes x 2 rails
    trammel.RAIL_SCREW_SEAT_ABOVE_BASE,  # head on the rail's counterbore floor
    base_bar.BAR_THICK,  # tapped THRU
)
BRACKET_TO_BAR = Fastener(
    "TL-28 end bracket to TL-20 base bar (up from the underside)",
    leadscrew.BAR_SCREW,
    SHCS,
    leadscrew.BAR_SCREW_LENGTH,
    len(leadscrew.BASE_BAR_HOLES),
    leadscrew.BAR_SCREW_GRIP,  # head recessed in TL-20's 4.80 counterbore
    end_bracket.BAR_THREAD_DEPTH,  # drilled THRU, threaded .491 from the bar face
)
BLOCK_TO_CARRIAGE = Fastener(
    "TL-32 feed block / TL-22 pivot block to HGH15CA carriage",
    trammel.CARRIAGE_BOLT,
    SHCS,
    f"{pivot_block.SCREW_LENGTH:.0f}",
    4 * RAILS,  # the 26 x 26 pattern on each carriage
    pivot_block.CBORE_FLOOR,
    pivot_block.CARRIAGE_THREAD_DEPTH,  # the carriage's M4 x 5
    min_engagement_d=1.1,
    note="the HGH15CA-style carriage's M4 x 5 holes limit the engagement",
    cut_length_mm=pivot_block.SCREW_CUT_LENGTH,  # owner ruling 2026-11-01
)
KP08_TO_BRACKET = Fastener(
    "KP08 pillow block to TL-28 end bracket",
    leadscrew.KP08_SCREW,
    SHCS,
    leadscrew.KP08_SCREW_LENGTH,
    len(end_bracket.HOLE_X) * leadscrew.END_BRACKET_QUANTITY,
    leadscrew.KP08_FOOT_THICK,  # UNVERIFIED foot thickness
    end_bracket.KP08_THREAD_DEPTH,  # the same holes, threaded .436 from the KP08 face
)
NUT_TO_FEED_BLOCK = Fastener(
    "TL-VN-84 FeedNut to TL-32 feed block",
    feed_nut.SCREW_THREAD,
    FLAT_HEAD,
    feed_nut.SCREW_LENGTH_TEXT,
    feed_nut.SCREW_COUNT,
    feed_nut.SCREW_GRIP,  # head seated nominally in the flange's countersink
    feed_block.LUG_WIDTH,  # tapped THRU
)
RISER_TO_CARRIER = Fastener(
    "TL-24 riser to TL-21 carrier",
    trammel.RISER_SCREW,
    FLAT_HEAD,
    "5/8",
    len(trammel.RISER_SCREWS),
    # head seated nominally in the countersink
    riser.THICKNESS - _RISER_SCREW.seated_recess(riser.CSK_DIA, riser.CSK_ANGLE),
    carrier.THICKNESS,  # tapped THRU
)
CR_CLAMP = Fastener(
    "CR clamp: rocker-arm strap and riser to TL-21 carrier",
    carrier.CR_THREAD,
    SHCS,
    "7/8",
    1,
    trammel.RISER_THICK + trammel.STRAP_THICK,
    carrier.THICKNESS,  # tapped THRU
    # the full bought screw: its tip stands into the free space above the rail
    tip_clearance_mm=trammel.CARRIER_TO_RAIL_GAP,
)
HUB_CLAMP = Fastener(
    "hub clamp: strap to TL-33 stud nose",
    "#10-24",
    LOW_HEAD,
    "1/2",
    1,
    hub_washer.THICK + trammel.STRAP_THICK - hub_stud.TIP_SET,
    hub_stud.TAP_FULL_DEPTH,
)
LEFT_CLAMP_INSERTION = (8.40, 8.62)
LEFT_CLAMP_TIP_CHAMFER = (0.762, 0.889)  # AXIAL length, .030–.035 at the restored 45° tip
LEFT_CLAMP_CUT_LENGTH = (
    trammel.RISER_THICK + trammel.STRAP_THICK + sum(LEFT_CLAMP_INSERTION) / 2.0
)
LEFT_CLAMP = Fastener(
    "left clamp: strap and riser to TL-21 blind receiver",
    carrier.LEFT_CLAMP_THREAD,
    LOW_HEAD,
    "3/4",
    1,
    trammel.RISER_THICK + trammel.STRAP_THICK,
    carrier.LEFT_CLAMP_THREAD_DEPTH,
    tip_clearance_mm=carrier.LEFT_CLAMP_DRILL_DEPTH - carrier.LEFT_CLAMP_THREAD_DEPTH,
    cut_length_mm=LEFT_CLAMP_CUT_LENGTH,
    note="cut to actual grip plus 8.40–8.62; chamfer the cut tip 45° x .030–.035 AXIAL (0.76–0.89)",
)
LEVER_TO_CARRIER = Fastener(
    "TL-26 feed lever to TL-21 carrier",
    carrier.LEVER_THREAD,
    SHCS,
    "1",
    len(carrier.LEVER_HOLES),
    # head on the TL-VN-71 pair, on the lever's top face
    feed_lever.LEVER_THICK + LEVER_LOCK_STACK,
    carrier.THICKNESS,  # tapped THRU
    min_engagement_d=1.3,
    note="the 12 carrier limits engagement; see the lever washer's worst-case stack",
)
FASTENERS: tuple[Fastener, ...] = (
    RAIL_TO_BAR,
    BRACKET_TO_BAR,
    BLOCK_TO_CARRIAGE,
    KP08_TO_BRACKET,
    NUT_TO_FEED_BLOCK,
    RISER_TO_CARRIER,
    CR_CLAMP,
    HUB_CLAMP,
    LEFT_CLAMP,
    LEVER_TO_CARRIER,
)
LEVER_LOCK_WASHER = Washer(
    LEVER_TO_CARRIER.joint,
    "5/16",
    "WEDGE-LOCK WASHER PAIR",
    LEVER_TO_CARRIER.count,
    LEVER_LOCK_STACK,
)
HUB_WASHER = Washer(HUB_CLAMP.joint, "#10", "BRASS WASHER", 1, hub_washer.THICK)
WASHERS: tuple[Washer, ...] = (LEVER_LOCK_WASHER, HUB_WASHER)

# --- The common screw and its exceptions ---------------------------------------
# One SKU wherever its head and engagement fit (module docstring): these
# rows are its, and their count is the one BOM row's.
COMMON_SCREW = ("#8-32", "3/4", SHCS)  # McMaster 91251A197
COMMON_SCREW_ROWS: tuple[Fastener, ...] = (RAIL_TO_BAR, BRACKET_TO_BAR)
COMMON_SCREW_COUNT = sum(row.count for row in COMMON_SCREW_ROWS)  # 20
# Every other screw or stud the jig consumes, and why it is not the common
# #8-32 x 3/4 SHCS. Keys: the fitter's name for the item.
COMMON_SCREW_EXCEPTIONS: dict[str, str] = {
    "M4 SHCS, carriage": (
        "the bought HGH15CA carriage is tapped M4 x 5; its thread fixes the size, "
        "and each screw is cut to its counterbore at assembly"
    ),
    "1/4-20 SHCS, CR clamp": (
        "screws into TL-21's existing 1/4-20 THRU tap (carrier.CR_THREAD) through "
        "the strap and riser grip, the bought 7/8 standing into the free space "
        "above the rail; a #8-32 does not mate that thread"
    ),
    "5/16-18 shoulder screw, pivot": (
        "the pivot's 3/8 shoulder is the bearing journal the carrier turns on, "
        "not a clamping screw"
    ),
    "5/16-18 SHCS, feed lever": (
        "screws into TL-21's existing 5/16-18 THRU taps (carrier.LEVER_THREAD) "
        "through the TL-26 hand lever's holes and the TL-VN-71 5/16 wedge-lock "
        "pairs; a #8-32 mates neither the taps nor the washers"
    ),
    "#4-40 flat heads, riser and feed nut": (
        "flush countersunk heads into the existing #4-40 taps of TL-21 and the "
        "feed block's lug, through the riser's countersinks and the bought "
        "nut's countersunk Ø3.5 flange holes, which a #8 does not pass"
    ),
    "1/2-13 hold-down studs": (
        "the mill table's T-slots and the bought clamping kit fix the size"
    ),
    "kit set screws, handwheel and KP08": (
        "supplied in the bought handwheel and pillow blocks, tapped by their makers"
    ),
    "#8-32 x 5/8 SHCS, KP08 to TL-28": (
        "the 3/4 from the top would meet the bar screw's tip in TL-28's shared "
        "hole (end bracket spec COMMON_SCREW_TIP_GAP); the 5/8 is the "
        "owner-approved second length (owner ruling 2026-11-06, Main)"
    ),
    "#10-24 low-head SHCS, HUB and left clamp": (
        "the HUB and LEFT receivers are #10-24; low heads keep both clamps below "
        "the CR head. HUB uses 92220A163 at its purchased 1/2 length; LEFT uses "
        "92220A165 cut to the actual grip and blind-tap insertion. The common "
        "#8-32 screw mates neither receiver nor the required head/grip geometry"
    ),
}


@dataclass(frozen=True)
class ShoulderScrew:
    """Shoulder-end datum and threaded tail, not an under-head grip screw."""

    joint: str = "TL-VN-77 shoulder screw to TL-32 / TL-22 pivot receiver"
    sku: str = pivot_screw.SKU

    thread: str = pivot_screw.THREAD
    count: int = pivot_screw.QUANTITY
    shoulder_diameter_mm: float = pivot_screw.SHOULDER_DIA
    shoulder_length_mm: float = pivot_screw.SHOULDER_LENGTH
    thread_length_mm: float = pivot_screw.CUT_THREAD_LENGTH  # the shop-cut thread
    counterbore_depth_mm: float = pivot_block.BORE_DEPTH
    torque_nm: float = 4.0
    threadlocker: str = "Loctite 222"

    @property
    def engagement_mm(self) -> float:
        # Full-form thread only (rule 18): less 1.5 incomplete pitches.
        full_thread = self.thread_length_mm - 1.5 * pivot_screw.THREAD_PITCH
        return min(full_thread, pivot_block.BLOCK_HEIGHT - self.counterbore_depth_mm)


PIVOT_SCREW_TO_BLOCK = ShoulderScrew()

# Hold-down studs, reworked from the clamping-kit stock
# (fixtures.clamping-kit-pm-52pcck-14mm). Keep the loaded lower ends unchanged.
HOLD_DOWN_STUD_THREAD = "1/2-13"
HOLD_DOWN_STUD_STOCK_LENGTH = "3"
HOLD_DOWN_STUD_STOCK_LENGTH_MM = inch_mm(HOLD_DOWN_STUD_STOCK_LENGTH)
HOLD_DOWN_STUD_LENGTH_MM = 57.15  # 2.25
HOLD_DOWN_STUD_CLEARANCE_MIN = 3.0
HOLD_DOWN_STUD_COMPLETE_PROJECTION_PITCHES = 1.0
HOLD_DOWN_STUD_PITCH_MM = INCH / int(HOLD_DOWN_STUD_THREAD.rsplit("-", 1)[1])
HOLD_DOWN_STUD_COUNT = RAILS * len(trammel.HOLD_DOWN_STUDS)  # near + far a bar

# --- Import-time checks ------------------------------------------------------------
for _f in FASTENERS:
    if round(_f.engagement_mm / _f.major_mm, 2) < _f.min_engagement_d:
        raise AssertionError(f"{_f.joint}: engagement under {_f.min_engagement_d} D")
    if _f.protrusion_mm >= _f.tip_clearance_mm:
        raise AssertionError(f"{_f.joint}: the screw stands out or bottoms")
    if _f.min_engagement_d < 1.5 and not _f.note:
        raise AssertionError(f"{_f.joint}: a short engagement needs its reason")
# The joint tables already in the part specs agree with this one.
if abs(RAIL_TO_BAR.engagement_mm - base_bar.RAIL_SCREW_ENGAGEMENT) > 1e-9:
    raise AssertionError("rail screw engagement disagrees with the base bar spec")
if abs(BRACKET_TO_BAR.engagement_mm - leadscrew.BAR_SCREW_ENGAGEMENT) > 1e-9:
    raise AssertionError("bar screw engagement disagrees with the leadscrew spec")
if abs(KP08_TO_BRACKET.engagement_mm - leadscrew.KP08_SCREW_REACH) > 1e-9:
    raise AssertionError("KP08 screw engagement disagrees with the leadscrew spec")
for _row in COMMON_SCREW_ROWS:
    if (_row.thread, _row.length, _row.head) != COMMON_SCREW:
        raise AssertionError(f"{_row.joint} is not the common screw")
# Every row that is not the common screw has its reason.
if sum(
    1
    for _row in FASTENERS
    if (_row.thread, _row.length, _row.head) != COMMON_SCREW
) != len(FASTENERS) - len(COMMON_SCREW_ROWS):
    raise AssertionError("a fastener row duplicates the common screw outside its rows")
if abs(NUT_TO_FEED_BLOCK.engagement_mm - feed_nut.SCREW_ENGAGEMENT) > 1e-9:
    raise AssertionError("nut screw engagement disagrees with the feed nut spec")
if abs(BLOCK_TO_CARRIAGE.engagement_mm - pivot_block.SCREW_REACH) > 1e-9:
    raise AssertionError("carriage screw engagement disagrees with the block spec")
if abs(RAIL_TO_BAR.length_mm - trammel.RAIL_SCREW_LENGTH) > 1e-9:
    raise AssertionError("the rail screw's printed length is not the calculator's")
