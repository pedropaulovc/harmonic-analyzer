r"""The crank-seat gap the MHA-VN-071 shim pack fills, and the proof it can.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  The pack rides the Ø9.525 crankshaft between the integral seat
collar's rear face (``dt_crankshaft_spec.COLLAR_REAR``) and the cone-pivot-post
crank boss's south face.  The fitter measures that gap and stacks purchased
shims to within ``vn_crank_seat_shim_spec.FIT_RESIDUAL_MAX`` under it, so the
crankshaft's end play is the 16T's feeler gap off the boss's north face plus
that residual (MHA-DT-000 continuation sheet).

The pack cannot pass the collar forward, so it goes on over the shaft's rear
end, which carries the Ø11.388 outboard journal land: the shims' smallest
bore must clear it.
"""

from __future__ import annotations

import dt_cone_pivot_post_spec
import dt_crank_pinion_spec
import dt_crankshaft_spec
import vn_crank_seat_shim_spec as shim
from _printed_tolerance import printed_deviations
from dt_crankshaft_spec import JOURNAL_DIA, JOURNAL_DIA_BAND

# The smallest bore still passes the largest journal land on the way on.
JOURNAL_PASS_CLEARANCE_WORST = shim.ID_MIN - (JOURNAL_DIA + max(JOURNAL_DIA_BAND))
if JOURNAL_PASS_CLEARANCE_WORST <= 0.0:
    raise AssertionError(
        f"MHA-VN-071 bore Ø{shim.ID_MIN:.2f} cannot pass the "
        f"Ø{JOURNAL_DIA + max(JOURNAL_DIA_BAND):.3f} journal land"
    )

# The gap, walked north from the collar's rear face with the 16T set on its
# feeler off the boss's north face (MHA-DT-000 step 4): the printed
# CollarRearStation (rear face to the shaft's north end, the station
# build_dt_crankshaft dimensions as "ShaftLength" - "SeatCollar" - "CollarLength"),
# the shaft end's recess inside the 16T, back the 16T's overall length and the
# feeler to the boss's north face, back the boss to its south face.  Each link
# is (nominal, lower, upper): a printed length moves by its printed row, and
# the recess is set by the fitter inside the window the 16T boss was sized
# for.
COLLAR_REAR_STATION = (
    dt_crankshaft_spec.SHAFT_LENGTH
    - dt_crankshaft_spec.SEAT_COLLAR
    - dt_crankshaft_spec.COLLAR_LENGTH
)
_RECESS = dt_crankshaft_spec.SHAFT_END_RECESS
_PINION_LENGTH = dt_crank_pinion_spec.OVERALL_LENGTH
_BOSS_LENGTH = dt_cone_pivot_post_spec.CRANK_BOSS_LENGTH
_STATION_LOWER, _STATION_UPPER = printed_deviations(
    COLLAR_REAR_STATION,
    dt_crankshaft_spec.COLLAR_STATION_PLACES,
    (-dt_crankshaft_spec.COLLAR_STATION_TOL, dt_crankshaft_spec.COLLAR_STATION_TOL),
)
_PINION_LOWER, _PINION_UPPER = printed_deviations(
    _PINION_LENGTH, dt_crank_pinion_spec.OVERALL_LENGTH_PLACES
)
_BOSS_LOWER, _BOSS_UPPER = printed_deviations(
    _BOSS_LENGTH, dt_cone_pivot_post_spec.DRAWING_PRECISION_BY_NAME["CrankBossLen"]
)
GAP_LINKS: dict[str, tuple[float, float, float]] = {
    "MHA-DT-011 CollarRearStation": (
        COLLAR_REAR_STATION,
        _STATION_LOWER,
        _STATION_UPPER,
    ),
    "MHA-DT-011 end recess in MHA-DT-010": (
        _RECESS,
        dt_crank_pinion_spec.SHAFT_END_RECESS_MIN - _RECESS,
        dt_crank_pinion_spec.SHAFT_END_RECESS_MAX - _RECESS,
    ),
    "MHA-DT-010 seat feeler": (-dt_crank_pinion_spec.SEAT_FEELER_MM, 0.0, 0.0),
    "MHA-DT-010 overall length": (-_PINION_LENGTH, -_PINION_UPPER, -_PINION_LOWER),
    "MHA-DT-005 crank boss length": (-_BOSS_LENGTH, -_BOSS_UPPER, -_BOSS_LOWER),
}
GAP_NOMINAL = sum(link[0] for link in GAP_LINKS.values())
GAP_MIN = GAP_NOMINAL + sum(link[1] for link in GAP_LINKS.values())
GAP_MAX = GAP_NOMINAL + sum(link[2] for link in GAP_LINKS.values())

# Every gap an accepted set of parts can leave takes a pack of at most
# STACK_MAX shims within FIT_RESIDUAL_MAX under it.
shim.check_coverage(GAP_MIN, GAP_MAX)

# The model carries the pack selected for the nominal gap, leaving FLOAT
# between its boss face and the boss.
if shim.pack_for(GAP_NOMINAL) != shim.PACK:
    raise AssertionError(
        f"the nominal crank-seat gap {GAP_NOMINAL:.3f} takes pack "
        f"{shim.pack_for(GAP_NOMINAL)}, not the modelled MHA-VN-071 {shim.PACK}"
    )
FLOAT_NOMINAL = GAP_NOMINAL - shim.THICKNESS
if not 0.0 <= FLOAT_NOMINAL <= shim.FIT_RESIDUAL_MAX:
    raise AssertionError(
        f"MHA-VN-071 model pack leaves {FLOAT_NOMINAL:.3f}, outside "
        f"0-{shim.FIT_RESIDUAL_MAX}"
    )

# The crankshaft's end play: the 16T's feeler gap plus the pack's residual.
END_PLAY_MIN = dt_crank_pinion_spec.SEAT_FEELER_MM
END_PLAY_MAX = dt_crank_pinion_spec.SEAT_FEELER_MM + shim.FIT_RESIDUAL_MAX
