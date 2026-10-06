r"""Purchased cone lock knob (McMaster 93585A190) nominals and seat check.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the thread, the stud/head dims and the seat-fit check the harmonic
base, the swing-platform geometry and the drive train read. The dims come from
the constants of the 93585A190 replica recipe
(``diagnostics/diag_build_93585A190.py``, SolidWorks-free at import).
Consumers read them here, not from ``build_vn_cone_lock_knob``, whose stock build
recipe would otherwise ride their cache keys (#880).

The high-profile head has no collar: its chamfered underside bears directly
on the plate (or, disengaged, on the bare base), so the full knurled head is
what stands at plate height when the knob fences the notch mouth.
"""

from __future__ import annotations

from _hole_spec import HoleSpec
from diagnostics.diag_build_93585A190 import (
    HEAD_H as _HEAD_H,
    HEAD_R as _HEAD_R,
    LENGTH as _LENGTH,
    MAJOR_R as _MAJOR_R,
    PITCH as _PITCH,
)

THREAD = "1/4-20"
HEAD_DIA = 2.0 * _HEAD_R
HEAD_H = _HEAD_H
STUD_DIA = 2.0 * _MAJOR_R
STUD_LEN = _LENGTH
THREAD_PITCH = _PITCH
TIP_CHAMFER = THREAD_PITCH * 0.75
MIN_USEFUL_ENGAGEMENT = 1.5 * STUD_DIA
STUD_BOTTOM_CLEARANCE = 0.25
PLUG_TAP_LEAD = 5.0 * THREAD_PITCH


def require_seat_fit(
    seat: HoleSpec, plate_thickness: float, stud_length: float
) -> None:
    """Check plate-clamping and head-on-bare-base poses of this stock screw."""
    if (
        seat.kind != "tapped"
        or seat.size != THREAD
        or seat.thread_class != "2B"
        or seat.end != "blind"
    ):
        raise AssertionError("cone lock requires a blind 1/4-20 UNC-2B seat")
    useful_engagement = stud_length - plate_thickness - TIP_CHAMFER
    if useful_engagement < MIN_USEFUL_ENGAGEMENT - 1e-9:
        raise AssertionError("cone lock has less than 1.5D useful thread engagement")
    thread_depth = seat.overrides_mm.get("ThreadDepth", seat.depth_mm)
    # The bare-base pose is deepest; checking only the plate-clamping pose
    # misses the bottoming that prevents the head fencing the parked notch.
    for insertion in (stud_length - plate_thickness, stud_length):
        if thread_depth - insertion < STUD_BOTTOM_CLEARANCE - 1e-9:
            raise AssertionError("cone lock bottoms before its head seats")
    if seat.depth_mm - thread_depth < PLUG_TAP_LEAD - 1e-9:
        raise AssertionError("cone lock drill lacks five-pitch plug-tap lead")
