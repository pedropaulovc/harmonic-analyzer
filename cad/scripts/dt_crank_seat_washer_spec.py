r"""MHA-DT-036 crank-seat-washer: the turned thrust washer behind the crank collar.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  The washer rides the Ø9.525 crankshaft between the integral seat
collar's rear face (``dt_crankshaft_spec.COLLAR_REAR``) and the cone-pivot-post
crank boss's south face, and fills that gap: it is faced to fit at assembly,
so the crankshaft's only end play is the 16T's feeler gap off the boss's
north face.

It is a CUSTOM part, turned from bar, not a stock washer: it cannot pass the
collar forward, so it goes on over the shaft's rear end, which carries the
Ø11.388 outboard journal land.  A stock washer for the 3/8 in shaft (bore
10.31 at most) cannot pass that land; this bore clears it at print-worst.
The O.D. is the collar's, so the washer covers the collar's rear face.

Both faces run -- one on the collar's rear face, one on the boss -- so both
carry the running grade, as the collar's rear face does.

Part frame: axis local +Y through the origin (``Axis1``); faces at y = 0
(Top Plane, on the collar) and y = THICKNESS (toward the boss).
"""

from __future__ import annotations
import math

import dt_cone_pivot_post_spec
import dt_crank_pinion_spec
import dt_crankshaft_spec
from _gtol_spec import PlanarFace
from _printed_tolerance import printed_deviations
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from dt_crankshaft_spec import COLLAR_DIA, JOURNAL_DIA, JOURNAL_DIA_BAND

OD = COLLAR_DIA  # the collar body's Ø20.6
ID = 11.6
# Slips over the journal land, never under the bore: an Ø11.60 jobber drill
# through the blank, so the band is the title block's DRILLED HOLES row.
ID_BAND = (0.10, 0.0)  # (upper, lower) deviations
BORE_CALLOUT = "DRILL THRU"

# The smallest bore still passes the largest journal land on the way on.
JOURNAL_PASS_CLEARANCE_WORST = (ID + min(ID_BAND)) - (
    JOURNAL_DIA + max(JOURNAL_DIA_BAND)
)
if JOURNAL_PASS_CLEARANCE_WORST <= 0.0:
    raise AssertionError(
        f"MHA-DT-036 bore Ø{ID + min(ID_BAND):.2f} cannot pass the "
        f"Ø{JOURNAL_DIA + max(JOURNAL_DIA_BAND):.3f} journal land"
    )

# --- Fitted thickness ---------------------------------------------------------
# User ruling 2026-09-30 (MHA-DT-036 floor 0.5): the washer is never faced
# thinner than this, at any accepted set of parts.
THICKNESS_FLOOR = 0.5
# The gap it fills, walked north from the collar's rear face with the 16T set
# on its feeler off the boss's north face (MHA-DT-000 step 4): the printed
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
# The model is the washer as fitted to parts at their nominals.
THICKNESS = GAP_NOMINAL

# Supplied as a blank faced both sides (the two MACHINED finish symbols say
# so; the note does not repeat them), one face faced again to fit.  The
# blank is a MIN, the loosest supply spec that works: any excess is just more
# facing.  Its MIN keeps FACING_ALLOWANCE -- one finishing cut -- over the
# thickest fit, so the fitted face is always freshly cut.
FACING_ALLOWANCE = 0.10
BLANK_THICKNESS_MIN = math.ceil((GAP_MAX + FACING_ALLOWANCE - 1e-9) * 100) / 100


def check_fit_up(gap_min: float, gap_max: float, blank_min: float) -> None:
    """Refuse a faced range under the floor or a blank too thin to face to it."""
    if gap_min < THICKNESS_FLOOR - 1e-9:
        raise AssertionError(
            f"MHA-DT-036 would be faced to {gap_min:.3f}, under its "
            f"{THICKNESS_FLOOR} floor"
        )
    if blank_min < gap_max + FACING_ALLOWANCE - 1e-9:
        raise AssertionError(
            f"MHA-DT-036 blank {blank_min:.2f} MIN leaves no {FACING_ALLOWANCE} "
            f"facing allowance over the {gap_max:.3f} thickest fit"
        )


check_fit_up(GAP_MIN, GAP_MAX, BLANK_THICKNESS_MIN)

# The sheet: the modelled thickness prints as a REFERENCE; the callout under
# it is the requirement, and the blank is the make-to size.  The MHA-DT-000 step
# pointer is appended by the drawing (a part never reads the step registry).
THICKNESS_CALLOUT = f"SET AT ASSEMBLY {GAP_MIN:.2f}-{GAP_MAX:.2f}\nFACED TO FIT"
DRAWING_NOTES = "\n".join(
    (
        f"SUPPLY {BLANK_THICKNESS_MIN:.2f} MIN THICK.",
        "ONE FACE IS FACED TO FIT AT ASSEMBLY.",
    )
)

# Both faces run: MACHINED, on the exact native faces the part build resolves.
SURFACE_FINISHES = (
    SurfaceFinishControl("collar_face", MACHINED_UM, PlanarFace((0.0, -1.0, 0.0), 0.0)),
    SurfaceFinishControl(
        "boss_face", MACHINED_UM, PlanarFace((0.0, 1.0, 0.0), THICKNESS)
    ),
)

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity policy rule 2): the O.D. routine, the bore banded, and
# the thickness a one-place REFERENCE under its fit-at-assembly callout.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {"DiscDia", "BoreDia"},
    "Disc": {"DiscThick"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RingProfile": {"DiscDia": 1, "BoreDia": 2},
    "Disc": {"DiscThick": 1},
}
