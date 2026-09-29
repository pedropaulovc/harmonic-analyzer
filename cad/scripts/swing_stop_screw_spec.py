r"""Swing-stop screw (shared McMaster 90280A108 stock) nominals and seat check.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the thread, the stock dims, the embed/proud split and the seat-fit
check the harmonic base and the drive train read. The dims are the 90280A108
row of the shared McMaster fillister table
(``diagnostics/diag_mcmaster_fillister.py``, SolidWorks-free at import).
Consumers read them here, not from ``build_swing_stop_screw``, whose stock build
recipe would otherwise ride their cache keys (#880).

The stop shares the foot screw's #4-40 x 3/8 SKU (user decision, 2026-09-29).
Its 9.525-mm shank cannot give both one diameter of useful thread and head
clearance over a tolerance-high 6.35-mm platform, so the contract is relaxed
knowingly: the head clears the NOMINAL plate plus the underhead fillet by
0.25, and the embed keeps 0.8 D of useful thread (1.0 D gross in the base
seat, where every other seat holds 1.5 D). A platform at its +0.51
two-place high limit puts the head in the east edge's path.
"""

from __future__ import annotations

from _hole_spec import HoleSpec
from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES

THREAD = "#4-40"
SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, THREAD_PITCH = FILLISTER_SIZES["90280A108"]
EMBED_LEN = 2.85
PROUD_LEN = SHANK_LEN - EMBED_LEN
TIP_CHAMFER = 0.7 * THREAD_PITCH
UNDERHEAD_FILLET = THREAD_PITCH / 10.0
MIN_USEFUL_THREAD_D = 0.8
# The base's gross seat engagement floor (1.5D for every other seat).
MIN_SEAT_ENGAGEMENT_D = 1.0
HEAD_PLATE_CLEARANCE = 0.25


def require_seat_fit(seat: HoleSpec, plate_thickness: float) -> None:
    """Keep the stock stop clear of the moving plate without starving its tap."""
    if seat.kind != "tapped" or seat.size != THREAD or seat.end != "blind":
        raise AssertionError("swing stop requires a blind #4-40 tapped seat")
    if EMBED_LEN - TIP_CHAMFER < MIN_USEFUL_THREAD_D * SHANK_DIA - 1e-9:
        raise AssertionError(
            f"swing stop has less than {MIN_USEFUL_THREAD_D:g}D useful thread engagement"
        )
    thread_depth = seat.overrides_mm.get("ThreadDepth", seat.depth_mm)
    if thread_depth - EMBED_LEN < 0.25 - 1e-9:
        raise AssertionError("swing stop bottoms in its threaded seat")
    if seat.depth_mm - thread_depth < 5.0 * THREAD_PITCH - 1e-9:
        raise AssertionError("swing-stop drill lacks five-pitch plug-tap lead")
    # Nominal plate plus the vendor's underside fillet: the tolerance-high
    # plate is the accepted deviation named in the module docstring.
    if PROUD_LEN - plate_thickness - UNDERHEAD_FILLET < HEAD_PLATE_CLEARANCE - 1e-9:
        raise AssertionError("swing-stop head crowds the nominal platform")
