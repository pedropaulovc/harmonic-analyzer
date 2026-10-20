r"""Fastener table for the oblique-trammel jig (MHA-CH-06-TL-00).

Shop tooling, not a machine part (cad/docs/subsystem-identities.md). Pure
data: every screw and stud the jig consumes, one row per joint, with its
thread, head, printed length, count and the joint it makes. Each row also gives
its grip (the length under the head before the receiving thread) and the
receiving thread's depth, so ``engagement_mm`` and ``protrusion_mm`` follow.
Every value comes from the part specs and the calculator
``ch_rocker_arm_tl_oblique_trammel_spec`` (imported as ``trammel``); no
dimension is retyped here.

Engagement is length minus grip. Protrusion is engagement minus the receiving
thread's depth: past the far face for a THRU tap, past the full thread for a
blind one. Every row has protrusion below zero, so no screw stands out of the
part it threads into or bottoms in its hole.

Engagement is at least 1.5 diameters, except on two joints, each recorded in
the row:

* Carriage (M4 x 20): the HGH15CA's M4 x 5 holes limit it to 4.4 (1.1 D).
* Feed lever (5/16-18 x 1): the 12 carrier limits it to 10.4 (1.3 D) with
  nothing below the carrier; the screw ends inside the plate (a 1-1/8 in
  screw would stand 1.6 out of the underside).

Washers: a wedge-lock pair under each head of two joints (``WASHERS``), each
screw carrying a reversing load, so rule 23 wants a mechanical lock: the two
TL-29 block screws (the leadscrew's reversing thrust, TL-VN-70) and the two
feed lever screws (the operator's push and pull on the lever, TL-VN-71). Each
pair's stack adds to its row's grip. Every other head seats in a counterbore
or countersink, or on a flat face. Hold-down studs: 1/2-13 x 3 in only, from
the clamping kit. A longer stud reaches the swinging carrier (the jig spec's
``STUD_LENGTH_MAX``).

Each joint's screw is its own bought part and BOM row (TL-VN-61 to TL-VN-69, the
wedge-lock pairs TL-VN-70 and TL-VN-71); the assembly steps name each by its
callout (``callout``) and its item number.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

import ch_rocker_arm_tl_oblique_base_bar_spec as base_bar
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_feed_lever_spec as feed_lever
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot_block
import ch_rocker_arm_tl_oblique_riser_spec as riser
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
from _hole_spec import THREAD_MAJOR_MM

INCH = trammel.INCH
RAILS = 2  # one rail, one base bar, one carriage, one pivot block per side
SHCS = "SHCS"
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

    @property
    def metric(self) -> bool:
        return self.thread.startswith("M")

    @property
    def length_mm(self) -> float:
        return float(self.length) if self.metric else inch_mm(self.length)

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
        return self.length_mm - self.grip_mm

    @property
    def protrusion_mm(self) -> float:
        return self.engagement_mm - self.thread_depth_mm


@dataclass(frozen=True)
class Washer:
    """A washer under a row's heads: its stack adds to that row's grip."""

    joint: str  # the Fastener row's joint it sits in
    size: str  # the screw size it fits: "#8"
    kind: str  # as the fitter names it
    count: int  # one per screw of its row
    thickness_mm: float  # the installed stack under one head


_METRIC_PITCH = {"M3": "0.5", "M4": "0.7"}


def callout(fastener: Fastener) -> str:
    """The fitter's name for a screw: ``#8-32 X 3/4 SHCS``, ``M4 X 20 SHCS``."""
    return f"{fastener.thread} X {fastener.length} {fastener.head}"


# --- The table: one row per joint ---------------------------------------------------
RAIL_TO_BAR = Fastener(
    "HGR15R rail to TL-20 base bar",
    trammel.RAIL_SCREW,
    SHCS,
    "3/4",
    trammel.RAIL_HOLE_COUNT * RAILS,  # 7 rail holes x 2 rails
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
    leadscrew.BRACKET_THICK,  # tapped THRU
)
NUT_BRACKET_TO_BLOCK = Fastener(
    "TL-29 nut bracket to TL-22 pivot block 1",
    leadscrew.BLOCK_SCREW,
    SHCS,
    leadscrew.BLOCK_SCREW_LENGTH,
    len(leadscrew.PIVOT_BLOCK_HOLES),
    # head on the TL-VN-70 pair, on TL-22's 4.40 counterbore floor
    leadscrew.BLOCK_SCREW_GRIP + leadscrew.BLOCK_SCREW_LOCK_STACK,
    leadscrew.NUT_BRACKET_TAP_DEPTH,  # blind
)
BLOCK_TO_CARRIAGE = Fastener(
    "TL-22 pivot block to HGH15CA carriage",
    trammel.CARRIAGE_BOLT,
    SHCS,
    f"{pivot_block.SCREW_LENGTH:.0f}",
    4 * RAILS,  # the 26 x 26 pattern on each carriage
    pivot_block.UNDER_HEAD,  # head on TL-22's c'bore floor, from the carriage face
    pivot_block.CARRIAGE_THREAD_DEPTH,  # the carriage's M4 x 5
    min_engagement_d=1.1,
    note="the carriage maker's M4 x 5 holes limit the engagement",
)
KP08_TO_BRACKET = Fastener(
    "KP08 pillow block to TL-28 end bracket",
    leadscrew.KP08_SCREW,
    SHCS,
    "12",
    2 * leadscrew.END_BRACKET_QUANTITY,
    leadscrew.KP08_FOOT_THICK,  # UNVERIFIED foot thickness
    leadscrew.BRACKET_THICK,  # tapped THRU
    note="KP08 foot thickness unverified: verify the length on receipt",
)
NUT_TO_NUT_BRACKET = Fastener(
    "Tr8 flanged nut to TL-29 nut bracket",
    leadscrew.NUT_SCREW,
    SHCS,
    f"{leadscrew.NUT_SCREW_LENGTH:.0f}",
    len(leadscrew.NUT_HOLE_ANGLES_DEG),
    leadscrew.NUT_FLANGE_THICK,
    leadscrew.NUT_SCREW_TAP_DEPTH,  # blind
)
RISER_TO_CARRIER = Fastener(
    "TL-24 riser to TL-21 carrier",
    trammel.RISER_SCREW,
    FLAT_HEAD,
    "1/2",
    len(trammel.RISER_SCREWS),
    riser.THICKNESS,  # head flush in the countersink
    carrier.THICKNESS,  # tapped THRU
)
CR_CLAMP = Fastener(
    "CR clamp: rocker-arm strap and riser to TL-21 carrier",
    carrier.CR_THREAD,
    SHCS,
    "3/4",
    1,
    trammel.RISER_THICK + trammel.STRAP_THICK,
    carrier.THICKNESS,  # tapped THRU
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
    note="the 12 carrier limits the engagement; nothing stands below it",
)
FASTENERS: tuple[Fastener, ...] = (
    RAIL_TO_BAR,
    BRACKET_TO_BAR,
    NUT_BRACKET_TO_BLOCK,
    BLOCK_TO_CARRIAGE,
    KP08_TO_BRACKET,
    NUT_TO_NUT_BRACKET,
    RISER_TO_CARRIER,
    CR_CLAMP,
    LEVER_TO_CARRIER,
)
BLOCK_LOCK_WASHER = Washer(
    NUT_BRACKET_TO_BLOCK.joint,
    "#8",
    "WEDGE-LOCK WASHER PAIR",
    NUT_BRACKET_TO_BLOCK.count,
    leadscrew.BLOCK_SCREW_LOCK_STACK,
)
LEVER_LOCK_WASHER = Washer(
    LEVER_TO_CARRIER.joint,
    "5/16",
    "WEDGE-LOCK WASHER PAIR",
    LEVER_TO_CARRIER.count,
    LEVER_LOCK_STACK,
)
WASHERS: tuple[Washer, ...] = (BLOCK_LOCK_WASHER, LEVER_LOCK_WASHER)

# Hold-down studs, from the clamping kit (fixtures.clamping-kit-pm-52pcck-14mm).
HOLD_DOWN_STUD_THREAD = "1/2-13"
HOLD_DOWN_STUD_LENGTH = "3"
HOLD_DOWN_STUD_LENGTH_MM = inch_mm(HOLD_DOWN_STUD_LENGTH)  # 76.2
HOLD_DOWN_STUD_COUNT = RAILS * len(trammel.HOLD_DOWN_STUDS)  # near + far a bar

# --- Import-time checks ------------------------------------------------------------
for _f in FASTENERS:
    if round(_f.engagement_mm / _f.major_mm, 2) < _f.min_engagement_d:
        raise AssertionError(f"{_f.joint}: engagement under {_f.min_engagement_d} D")
    if _f.protrusion_mm >= 0.0:
        raise AssertionError(f"{_f.joint}: the screw stands out or bottoms")
    if _f.min_engagement_d < 1.5 and not _f.note:
        raise AssertionError(f"{_f.joint}: a short engagement needs its reason")
# The joint tables already in the part specs agree with this one.
if abs(RAIL_TO_BAR.engagement_mm - base_bar.RAIL_SCREW_ENGAGEMENT) > 1e-9:
    raise AssertionError("rail screw engagement disagrees with the base bar spec")
if abs(BRACKET_TO_BAR.engagement_mm - leadscrew.BAR_SCREW_ENGAGEMENT) > 1e-9:
    raise AssertionError("bar screw engagement disagrees with the leadscrew spec")
if abs(NUT_BRACKET_TO_BLOCK.engagement_mm - leadscrew.BLOCK_SCREW_ENGAGEMENT) > 1e-9:
    raise AssertionError("block screw engagement disagrees with the leadscrew spec")
if abs(NUT_TO_NUT_BRACKET.engagement_mm - leadscrew.NUT_SCREW_ENGAGEMENT) > 1e-9:
    raise AssertionError("nut screw engagement disagrees with the leadscrew spec")
if abs(BLOCK_TO_CARRIAGE.engagement_mm - pivot_block.THREAD_IN_CARRIAGE) > 1e-9:
    raise AssertionError("carriage screw engagement disagrees with the block spec")
if abs(RAIL_TO_BAR.length_mm - trammel.RAIL_SCREW_LENGTH) > 1e-9:
    raise AssertionError("the rail screw's printed length is not the calculator's")
