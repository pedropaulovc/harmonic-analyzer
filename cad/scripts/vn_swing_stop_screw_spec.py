r"""Swing-stop screw (shared McMaster 90280A108 stock) nominals and seat check.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the thread, the stock dims, the embed/proud split and the seat-fit
check the harmonic base and the drive train read. The dims are the 90280A108
row of the shared McMaster fillister table
(``diagnostics/diag_mcmaster_fillister.py``, SolidWorks-free at import); the
plate allowance is the title block's two-place linear tolerance. Consumers read
them here, not from ``build_vn_swing_stop_screw``, whose stock build recipe would
otherwise ride their cache keys (#880).

The stop shares the foot screw's #4-40 x 3/8 SKU (user decision, 2026-09-29)
and is screwed fully home: the head seats on the base top, and the platform's
edge bears on the head's full height, so the head is the stop.
"""

from __future__ import annotations

import _config
from _hole_spec import HoleSpec
from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES

THREAD = "#4-40"
SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, THREAD_PITCH = FILLISTER_SIZES["90280A108"]
EMBED_LEN = SHANK_LEN
PROUD_LEN = SHANK_LEN - EMBED_LEN
CONTACT_DIA = HEAD_DIA
TIP_CHAMFER = 0.7 * THREAD_PITCH
PLATE_THICKNESS_ALLOWANCE = 25.4 * float(_config.title_block("linear_2pl")["value_in"])


def require_seat_fit(seat: HoleSpec, plate_thickness: float) -> None:
    """Seat the stock stop fully home with its head inside the platform edge."""
    if seat.kind != "tapped" or seat.size != THREAD or seat.end != "blind":
        raise AssertionError("swing stop requires a blind #4-40 tapped seat")
    if EMBED_LEN - TIP_CHAMFER < SHANK_DIA:
        raise AssertionError("swing stop has less than 1D useful thread engagement")
    thread_depth = seat.overrides_mm.get("ThreadDepth", seat.depth_mm)
    if thread_depth - EMBED_LEN < 0.25 - 1e-9:
        raise AssertionError("swing stop bottoms in its threaded seat")
    if seat.depth_mm - thread_depth < 5.0 * THREAD_PITCH - 1e-9:
        raise AssertionError("swing-stop drill lacks five-pitch plug-tap lead")
    # The whole head must bear on the edge of a tolerance-low platform.
    if PROUD_LEN + HEAD_H > plate_thickness - PLATE_THICKNESS_ALLOWANCE + 1e-9:
        raise AssertionError("swing-stop head stands above the tolerance-low platform")
