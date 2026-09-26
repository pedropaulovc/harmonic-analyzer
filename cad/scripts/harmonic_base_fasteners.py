"""Harmonic-base fastener seats the frame and the interference contracts read.

PURE, SolidWorks-free: the blind-seat sizing law (every seat at its printed
worst case), the #10-32 cross taps, the rocker-support hold-down seats, the
pedestal screw engagement and the nameplate seats.  The base part
drills them from these numbers; the frame assembly and
``_interference_contracts`` read them here instead of importing the base
builder, whose recipe carries the cone journal line (``cone_line``) and with it
the channel station config.  Moved verbatim out of build_harmonic_base.
"""

from __future__ import annotations

import math

import _config
import nameplate_spec
from _hole_spec import TAP_DRILL_MM, HoleSpec, blind_cut_dia_mm
from arbor_pedestal_spec import FOOT_HEIGHT as PEDESTAL_FLANGE_THICKNESS
from lag_screw_spec import (
    BEARING_OFFSET as HOLD_DOWN_BEARING_OFFSET,
    SHANK_LEN as HOLD_DOWN_SCREW_LEN,
)
from pedestal_hold_down_screw_spec import SHANK_LEN as PEDESTAL_SCREW_LEN
from rocker_arm_support_section_spec import FOOT_THICKNESS as SUPPORT_FOOT_THICKNESS
from frame_attachment_spec import CASTING_FULL_THREAD_DEPTH, CASTING_TAP_DRILL_DEPTH

IN = 25.4


def title_block_band_mm(kind: str) -> float:
    """A title-block general tolerance row's symmetric band, in mm."""
    return float(str(_config.title_block(kind)["display"]).lstrip("±"))


# Every blind-seat depth prints at two places (the hole table's thread and
# drill cells, the transfer and cross-tap callouts), so the title block's
# .XX band is its printed tolerance, and each seat is sized at that band's
# worst case, not at nominal. The 2026-09-25 Codex machinist review found
# the E seats' 9.50 thread held only 8.99 at its low limit, where the
# nominal-length screw tip already ran into the incomplete threads.
SEAT_DEPTH_BAND = title_block_band_mm("linear_2pl")
SEAT_TIP_RESERVE = 0.25
SEAT_DEPTH_STEP = 0.05  # derived depths round UP to a shop-friendly step


def _ceil_step(value: float) -> float:
    return round(math.ceil(value / SEAT_DEPTH_STEP - 1e-9) * SEAT_DEPTH_STEP, 2)


def _seat_lead_mm(size: str, kind: str) -> float:
    """The tap's lead: two pitches for a bottoming tap, five for a plug."""
    pitch = 25.4 / float(size.rsplit("-", 1)[1])
    return (2.0 if kind == "tapped_bottoming" else 5.0) * pitch


def seat_thread_depth(engagement: float) -> float:
    """Full-thread depth that keeps the screw tip SEAT_TIP_RESERVE off the
    incomplete threads when the printed depth sits at its low limit."""
    return _ceil_step(engagement + SEAT_TIP_RESERVE + SEAT_DEPTH_BAND)


def seat_drill_depth(thread_depth: float, size: str, kind: str) -> float:
    """Tap-drill depth that keeps the tap's lead past the deepest printed
    thread even when the drill sits at its low limit."""
    return _ceil_step(thread_depth + 2.0 * SEAT_DEPTH_BAND + _seat_lead_mm(size, kind))


# Frame cross screws: #10-32 bottoming taps into the base casting's sides.
BASE_CROSS_TAP_SPEC = HoleSpec(
    "tapped_bottoming",
    "#10-32",
    end="blind",
    depth_mm=CASTING_TAP_DRILL_DEPTH,
    thread_class="2B",
    overrides_mm={"ThreadDepth": CASTING_FULL_THREAD_DEPTH},
)
BASE_CROSS_TAP_DRILL_DIA = TAP_DRILL_MM[BASE_CROSS_TAP_SPEC.size]
# The drill prints as a whole-mm MIN (no lower band); the thread's .XX band
# still moves the deepest thread down towards it.
if (
    CASTING_TAP_DRILL_DEPTH - (CASTING_FULL_THREAD_DEPTH + SEAT_DEPTH_BAND)
    < _seat_lead_mm(BASE_CROSS_TAP_SPEC.size, "tapped_bottoming") - 1e-9
):
    raise AssertionError("base cross tap lacks two-pitch bottoming-tap lead")

# Rocker-support hold-down seats (machine = part-local: frame.SLDASM places the
# base unrotated at the origin). The support contract transforms its unchanged
# four-hole foot pattern through the +90-degree installation and the v2 rear
# shift. Base, support, and frame therefore cannot carry drifting copies.
#
# The selected 1/4-20 x 3/4 screw bears on the bottom of its vendor-modeled
# 0.277813 mm under-head washer transition. That physical bearing face crosses
# the 6.35 mm support foot and leaves 12.422187 mm (1.956D) of engagement in
# this base. The seat is sized at its printed worst case (seat_thread_depth /
# seat_drill_depth): full thread 13.20 keeps the tip 0.25 off the incomplete
# threads at the thread's low limit, and the 20.60 drill keeps the plug
# tap's five-pitch lead past its high limit. Keep all three lengths
# explicit; they are different assembly/manufacturing constraints.
HOLD_DOWN_THREAD = "1/4-20"
HOLD_DOWN_THREAD_CLASS = "2B"
HOLD_DOWN_PITCH = IN / 20.0
HOLD_DOWN_ENGAGEMENT = (
    HOLD_DOWN_SCREW_LEN - SUPPORT_FOOT_THICKNESS - HOLD_DOWN_BEARING_OFFSET
)
HOLD_DOWN_TIP_CLEARANCE = SEAT_TIP_RESERVE
HOLD_DOWN_THREAD_DEPTH = seat_thread_depth(HOLD_DOWN_ENGAGEMENT)
HOLD_DOWN_DRILL_DEPTH = seat_drill_depth(HOLD_DOWN_THREAD_DEPTH, HOLD_DOWN_THREAD, "tapped")
HOLD_DOWN_SEAT_SPEC = HoleSpec(
    "tapped",
    HOLD_DOWN_THREAD,
    end="blind",
    depth_mm=HOLD_DOWN_DRILL_DEPTH,
    thread_class=HOLD_DOWN_THREAD_CLASS,
    overrides_mm={"ThreadDepth": HOLD_DOWN_THREAD_DEPTH},
)
HOLD_DOWN_TAP_DRILL_DIA = blind_cut_dia_mm(HOLD_DOWN_SEAT_SPEC)

# Arbor-pedestal hold-downs: the #8-32 screw's thread past the pedestal ledge.
PEDESTAL_SCREW_ENGAGEMENT = PEDESTAL_SCREW_LEN - PEDESTAL_FLANGE_THICKNESS

# Maker's nameplate seats (2026-09-02 ch26 p.71 re-derive: four brass slotted
# fillister-head screws hold the plate at its corners), blind from the TOP face
# like the other seats. The stations are the plate's four corner screw holes
# (nameplate_spec.SCREW_XY, plate-local) carried through the plate's mount
# transform into the machine frame -- nameplate_spec.MOUNT_HOLE_XZ, the ONE
# derivation the frame assembly's screw drops read too:
# (209.75, +/-45.5) and (163.75, +/-45.5). The plate is anchored to the pad's
# east edge, not to the mechanism, so unlike the swing/rig seats no
# MECHANISM/POST shift applies (no _FORMER_ twin). The plate lies flat on the
# deck (its back face at STACK_HEIGHT, gap 0 -- asserted below), so each
# screw axis runs -Y straight from the plate's front face into the deck.
NAMEPLATE_SCREW_XZ = nameplate_spec.MOUNT_HOLE_XZ
# The stock brass fillister's 6.35-mm shank passes through the 1.5-mm plate,
# engaging 4.85 mm of the existing 6.0-mm #4-40 thread. The drill extends
# 3.0 mm deeper for the bottoming tap's two-pitch lead (1.27 mm).
NAMEPLATE_SCREW_HOLE_DEPTH = 6.0
NAMEPLATE_SCREW_DRILL_DEPTH = 9.0
