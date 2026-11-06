"""Frame cross-screw joint: near-wall clearance and far-wall engagement.

Owner ruling 2026-11-05: every MHA-FR-VN-53 (McMaster 90280A837) cross-screw
path -- four in MHA-FR-01, four in MHA-FR-02 -- clears the near casting wall
with a #10 close clearance (#5 drill, .206) and is threaded in the far casting
wall only, so a standard-shank 10-32 tap reaches the far wall through the
clearance and no long-reach reduced-shank tap is needed. Each casting owns its
seat-to-socket stack (fr_harmonic_base_fasteners, build_fr_top_frame); this
module owns what both share: the clearance, the stock screw's print-worst
reach, the socket and far-mouth terms, and the 1.5D floor with the installed
check MHA-FR-00 states.
"""

from __future__ import annotations

import math

from _hole_spec import CLEARANCE_MM
from _mcmaster_90280a837 import (
    PITCH as CROSS_SCREW_PITCH,
    SHANK_DIA as CROSS_SCREW_MAJOR,
    SHANK_LEN as CROSS_SCREW_LENGTH,
)
from _printed_tolerance import edge_break_chamfer_mm, edge_break_radius_mm
from fr_frame_attachment_spec import TUBE_CROSS_HOLE_DIAMETER
from frame_column_stations import COLUMN_SOCKET_DIAMETER, COLUMN_SOCKET_MATCH_BORE_MAX

IN = 25.4

# Near-wall clearance (#5 drill, .206). It passes the standard 10-32 tap's
# .194 shank, so a standard long-shank tap reaches the far wall through it,
# and it is no smaller than the tube's .197 match drill it guides at
# assembly (MHA-FR-00 steps 2 and 5).
NEAR_WALL_CLEARANCE_SIZE = "#10"
NEAR_WALL_CLEARANCE_FIT = "close"
NEAR_WALL_CLEARANCE_DIAMETER = CLEARANCE_MM[
    (NEAR_WALL_CLEARANCE_SIZE, NEAR_WALL_CLEARANCE_FIT)
]
STANDARD_10_32_TAP_SHANK_DIAMETER = 0.194 * IN
if not (
    NEAR_WALL_CLEARANCE_DIAMETER > STANDARD_10_32_TAP_SHANK_DIAMETER
    and NEAR_WALL_CLEARANCE_DIAMETER >= TUBE_CROSS_HOLE_DIAMETER
    and NEAR_WALL_CLEARANCE_DIAMETER > CROSS_SCREW_MAJOR
):
    raise AssertionError(
        "near-wall clearance must pass the tap shank, tube drill and screw"
    )

# Far-wall engagement (drawing-guidelines.md rule 18), in the convention of
# fr_harmonic_base_fasteners.require_through_seat_fit: the stock screw's least
# length and tip loss against the deepest guaranteed start of full female
# thread. ASME B18.6.3 machine screws, sizes 0-12 over 1 to 2 in long, are
# -.06 on length. The tip allowance is the nominal 0.7-pitch chamfer the
# swing-stop joint books (dt_swing_stop_screw_spec.TIP_CHAMFER), not a
# qualified supplier bound: as there, the installed joint is accepted by
# inspection. MHA-FR-00 check 2 (CROSS_SCREW_ENGAGEMENT_CHECK) asks for
# full-form far-wall engagement of at least 1.5 screw diameters with the head
# fully seated -- a ratio of the purchased screw, so no dimension lives in the
# note -- and so catches a short-tipped screw.
CROSS_SCREW_LENGTH_SHORT_ALLOWANCE_MM = 0.06 * IN
CROSS_SCREW_TIP_LOSS_MM = 0.7 * CROSS_SCREW_PITCH
CROSS_SCREW_ENGAGEMENT_DIAMETERS = 1.5
FAR_WALL_ENGAGEMENT_FLOOR_MM = CROSS_SCREW_ENGAGEMENT_DIAMETERS * CROSS_SCREW_MAJOR
CROSS_SCREW_ENGAGEMENT_CHECK = (
    "FULL-FORM THREAD ENGAGEMENT OF AT LEAST "
    f"{CROSS_SCREW_ENGAGEMENT_DIAMETERS:g} SCREW DIAMETERS"
)


def far_wall_start_max_mm(seat_to_axis_max_mm: float, *, unit: str) -> float:
    """Deepest start of full far-wall thread below the screw seat.

    ``seat_to_axis_max_mm`` is the casting's own print-worst seat-to-socket-
    axis stack. Either socket may be match-bored to its Ø26.0 ceiling, and
    the far wall's mouth takes the sheet's title-block edge break.
    """
    edge_break = max(edge_break_radius_mm(unit=unit), edge_break_chamfer_mm(unit=unit))
    return seat_to_axis_max_mm + COLUMN_SOCKET_MATCH_BORE_MAX / 2.0 + edge_break


def far_wall_full_thread_min_mm(
    far_wall_start_max_mm: float, *, tip_loss_mm: float = CROSS_SCREW_TIP_LOSS_MM
) -> float:
    """Least full-thread overlap in the far wall, measured from the seat.

    ``far_wall_start_max_mm`` is the deepest the far wall's full female
    thread can start below the seat at the printed limits (the socket wall
    plus its mouth's edge break). The screw seats on the face every tap
    depth runs from; the printed full thread reaches past its tip.
    ``tip_loss_mm`` is the booked tip chamfer, exposed for sensitivity.
    """
    external_end = (
        CROSS_SCREW_LENGTH - CROSS_SCREW_LENGTH_SHORT_ALLOWANCE_MM - tip_loss_mm
    )
    return external_end - far_wall_start_max_mm


def near_wall_hole_volume_mm3(hole_dia_mm: float, seat_to_axis_mm: float) -> float:
    """Casting a cross hole of ``hole_dia_mm`` removes between its flat seat
    and the nominal column socket, ``seat_to_axis_mm`` off the socket's axis."""
    hole_r = hole_dia_mm / 2.0
    socket_r = COLUMN_SOCKET_DIAMETER / 2.0
    step = 0.001
    volume = 0.0
    x = -hole_r + step / 2.0
    while x < hole_r:
        chord = 2.0 * math.sqrt(max(0.0, hole_r * hole_r - x * x))
        volume += (
            chord * (seat_to_axis_mm - math.sqrt(socket_r * socket_r - x * x)) * step
        )
        x += step
    return volume
