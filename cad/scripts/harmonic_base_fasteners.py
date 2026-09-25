"""Harmonic-base fastener seats the frame and the interference contracts read.

PURE, SolidWorks-free: the #10-32 cross taps, the rocker-support hold-down
seats, the pedestal screw engagement and the nameplate seats.  The base part
drills them from these numbers; the frame assembly and
``_interference_contracts`` read them here instead of importing the base
builder, whose recipe carries the cone journal line (``cone_line``) and with it
the channel station config.  Moved verbatim out of build_harmonic_base.
"""

from __future__ import annotations

import nameplate_spec
from _hole_spec import TAP_DRILL_MM, HoleSpec, blind_cut_dia_mm
from arbor_pedestal_spec import FOOT_HEIGHT as PEDESTAL_FLANGE_THICKNESS
from build_lag_screw import (
    BEARING_OFFSET as HOLD_DOWN_BEARING_OFFSET,
    SHANK_LEN as HOLD_DOWN_SCREW_LEN,
)
from build_pedestal_hold_down_screw import SHANK_LEN as PEDESTAL_SCREW_LEN
from build_rocker_arm_support import FOOT_THICKNESS as SUPPORT_FOOT_THICKNESS
from frame_attachment_spec import CASTING_FULL_THREAD_DEPTH, CASTING_TAP_DRILL_DEPTH

IN = 25.4

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
if CASTING_TAP_DRILL_DEPTH - CASTING_FULL_THREAD_DEPTH < 2.0 * 25.4 / 32.0:
    raise AssertionError("base cross tap lacks two-pitch bottoming-tap lead")

# Rocker-support hold-down seats (machine = part-local: frame.SLDASM places the
# base unrotated at the origin). The support contract transforms its unchanged
# four-hole foot pattern through the +90-degree installation and the v2 rear
# shift. Base, support, and frame therefore cannot carry drifting copies.
#
# The selected 1/4-20 x 5/8 screw bears on the bottom of its vendor-modeled
# 0.277813 mm under-head washer transition. That physical bearing face crosses
# the 6.35 mm support foot and leaves 9.247187 mm (1.456D) of engagement in
# this base. Usable full thread extends 0.25 mm beyond the screw tip so it
# cannot bottom before the head seats. A machine plug tap then needs four lead
# threads plus one pitch of margin: cylindrical tap-drill depth = full-thread
# depth + 5P = 15.847187 mm. Keep all three lengths explicit; they are
# different assembly/manufacturing constraints.
HOLD_DOWN_THREAD = "1/4-20"
HOLD_DOWN_THREAD_CLASS = "2B"
HOLD_DOWN_PITCH = IN / 20.0
HOLD_DOWN_ENGAGEMENT = (
    HOLD_DOWN_SCREW_LEN - SUPPORT_FOOT_THICKNESS - HOLD_DOWN_BEARING_OFFSET
)
HOLD_DOWN_TIP_CLEARANCE = 0.25
HOLD_DOWN_THREAD_DEPTH = HOLD_DOWN_ENGAGEMENT + HOLD_DOWN_TIP_CLEARANCE
HOLD_DOWN_DRILL_DEPTH = HOLD_DOWN_THREAD_DEPTH + 5.0 * HOLD_DOWN_PITCH
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
