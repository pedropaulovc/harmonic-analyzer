r"""Purchased cone lock knob (McMaster 91882A425) nominals and seat check.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the thread, the stud/collar/head dims and the seat-fit check the
harmonic base, the swing-platform geometry and the drive train read. The
dims come from the 91882A425 entry of the McMaster thumb-screw table
(``diagnostics/diag_mcmaster_thumb.py``, SolidWorks-free at import). Consumers
read them here, not from ``build_cone_lock_knob``, whose stock build recipe
would otherwise ride their cache keys (#880).
"""

from __future__ import annotations

from _hole_spec import HoleSpec
from diagnostics.diag_mcmaster_thumb import THUMB_SPECS

THREAD = "1/4-20"
_LOCK = THUMB_SPECS["91882A425"]
COLLAR_DIA = 2.0 * _LOCK["collar_r"]
HEAD_DIA = 2.0 * _LOCK["head_r"]
HEAD_H = _LOCK["collar_h"] + _LOCK["head_h"]
SHANK_DIA = 2.0 * _LOCK["major_r"]
SHANK_LEN = _LOCK["length"]
STUD_DIA = 2.0 * _LOCK["major_r"]
STUD_LEN = _LOCK["length"]
WASHER_DIA = 2.0 * _LOCK["collar_r"]
THREAD_PITCH = _LOCK["pitch"]
TIP_CHAMFER = THREAD_PITCH * 0.75
MIN_USEFUL_ENGAGEMENT = 1.5 * STUD_DIA
STUD_BOTTOM_CLEARANCE = 0.25
PLUG_TAP_LEAD = 5.0 * THREAD_PITCH


def require_seat_fit(
    seat: HoleSpec, plate_thickness: float, stud_length: float
) -> None:
    """Check plate-clamping and collar-on-bare-base poses of this stock screw."""
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
    # misses the bottoming that prevents the collar fencing the parked notch.
    for insertion in (stud_length - plate_thickness, stud_length):
        if thread_depth - insertion < STUD_BOTTOM_CLEARANCE - 1e-9:
            raise AssertionError("cone lock bottoms before its collar seats")
    if seat.depth_mm - thread_depth < PLUG_TAP_LEAD - 1e-9:
        raise AssertionError("cone lock drill lacks five-pitch plug-tap lead")
