r"""MHA-172 crank-seat-washer: the turned thrust washer behind the crank collar.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  The washer rides the Ø9.525 crankshaft between the integral seat
collar's rear face (``crankshaft_spec.COLLAR_REAR``) and the cone-pivot-post
crank boss's south face; its thickness plus the float closes that gap.

It is a CUSTOM part, turned from bar, not a stock washer: it cannot pass the
collar forward, so it goes on over the shaft's rear end, which carries the
Ø11.388 outboard journal land.  A stock washer for the 3/8 in shaft (bore
10.31 at most) cannot pass that land; this bore clears it at print-worst.
The O.D. is the collar's, so the washer covers the collar's rear face.

Both faces run -- one on the collar's rear face, one on the boss -- so both
carry the running grade, as the collar's rear face does.  The thickness
sits in the float stack, so it carries a held band.

Part frame: axis local +Y through the origin (``Axis1``); faces at y = 0
(Top Plane, on the collar) and y = THICKNESS (toward the boss).
"""

from __future__ import annotations

from _gtol_spec import PlanarFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from crankshaft_spec import COLLAR_DIA, JOURNAL_DIA, JOURNAL_DIA_BAND

OD = COLLAR_DIA  # the collar body's Ø20.6
ID = 11.6
THICKNESS = 1.5
# Slips over the journal land, never under the bore (drilled/bored class).
ID_BAND = (0.10, 0.0)  # (upper, lower) deviations
# The thickness eats the 0.26 nominal float to the post boss, so the title
# block's .XX +/-0.51 would close it; held at .XX with a micrometer.
THICKNESS_TOL = 0.05
THICKNESS_BAND = (THICKNESS_TOL, -THICKNESS_TOL)  # (upper, lower) deviations

# The smallest bore still passes the largest journal land on the way on.
JOURNAL_PASS_CLEARANCE_WORST = (ID + min(ID_BAND)) - (
    JOURNAL_DIA + max(JOURNAL_DIA_BAND)
)
if JOURNAL_PASS_CLEARANCE_WORST <= 0.0:
    raise AssertionError(
        f"MHA-172 bore Ø{ID + min(ID_BAND):.2f} cannot pass the "
        f"Ø{JOURNAL_DIA + max(JOURNAL_DIA_BAND):.3f} journal land"
    )

# Both faces run: MACHINED, on the exact native faces the part build resolves.
SURFACE_FINISHES = (
    SurfaceFinishControl("collar_face", MACHINED_UM, PlanarFace((0.0, -1.0, 0.0), 0.0)),
    SurfaceFinishControl(
        "boss_face", MACHINED_UM, PlanarFace((0.0, 1.0, 0.0), THICKNESS)
    ),
)

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity policy rule 2): the O.D. routine, the bore and the
# thickness banded.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {"DiscDia", "BoreDia"},
    "Disc": {"DiscThick"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RingProfile": {"DiscDia": 1, "BoreDia": 2},
    "Disc": {"DiscThick": 2},
}
