r"""Swing-stop screw (shared McMaster 90280A199 stock) nominals and seat check.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the thread, the stock dims, the embed/proud split and the seat-fit
check the harmonic base and the drive train read. The dims are the 90280A199
row of the shared McMaster fillister table
(``diagnostics/diag_mcmaster_fillister.py``, SolidWorks-free at import); the
plate allowance is the title block's two-place linear tolerance. Consumers read
them here, not from ``build_swing_stop_screw``, whose stock build recipe would
otherwise ride their cache keys (#880).
"""

from __future__ import annotations

import _config
from _hole_spec import HoleSpec
from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES

THREAD = "#8-32"
SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, THREAD_PITCH = FILLISTER_SIZES["90280A199"]
EMBED_LEN = 15.525
PROUD_LEN = SHANK_LEN - EMBED_LEN
TIP_CHAMFER = 0.7 * THREAD_PITCH
UNDERHEAD_FILLET = THREAD_PITCH / 10.0
PLATE_THICKNESS_ALLOWANCE = 25.4 * float(_config.title_block("linear_2pl")["value_in"])


def require_seat_fit(seat: HoleSpec, plate_thickness: float) -> None:
    """Keep the stock stop clear of the moving plate without starving its tap."""
    if seat.kind != "tapped" or seat.size != THREAD or seat.end != "blind":
        raise AssertionError("swing stop requires a blind #8-32 tapped seat")
    if EMBED_LEN - TIP_CHAMFER < SHANK_DIA:
        raise AssertionError("swing stop has less than 1D useful thread engagement")
    thread_depth = seat.overrides_mm.get("ThreadDepth", seat.depth_mm)
    if thread_depth - EMBED_LEN < 0.25 - 1e-9:
        raise AssertionError("swing stop bottoms in its threaded seat")
    if seat.depth_mm - thread_depth < 5.0 * THREAD_PITCH - 1e-9:
        raise AssertionError("swing-stop drill lacks five-pitch plug-tap lead")
    # Include the plate's two-place drawing allowance and the vendor's
    # underside fillet, not only the nominal flat head plane.
    if PROUD_LEN - plate_thickness - PLATE_THICKNESS_ALLOWANCE - UNDERHEAD_FILLET < 1.0:
        raise AssertionError("swing-stop head crowds the tolerance-high platform")
