r"""MHA-178 transgear-stud-shim: the turned washer under the MHA-082 stud's collar.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  The shim rides the stud's #10-32 rear thread between the stud's
Ø12 collar and the MHA-164 arm's front face, and is faced to fit at
assembly (R9-65): it carries the whole stud fit-up (``transgear_stud_fit``),
so the stud is made to size and its rear thread relief always stands inside
the shim, never in the arm's tapped hole.

It is a CUSTOM part, turned from bar, not a stock washer: the fitted range
runs 1.58 to 4.52 thick.  The O.D. is the stud collar's, so the shim covers
the collar's rear face; the bore is drilled to pass the #10-32 major.

Both faces bear -- one on the collar, one on the arm -- so both carry the
running grade.

Part frame: axis local +Z through the origin (``Axis1``); faces at z = 0
(Front Plane, on the stud's collar) and z = THICKNESS (``ArmFace``, on the
arm).
"""

from __future__ import annotations

import transgear_stub_spec as STUB
import transgear_stud_fit as FIT
from _gtol_spec import PlanarFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

OD = STUB.COLLAR_DIA  # the stud collar's Ø12
ID = 5.1
# Passes the #10-32 major, never under the bore: a Ø5.10 jobber drill
# through the blank, so the band is the title block's DRILLED HOLES row.
ID_BAND = (0.10, 0.0)  # (upper, lower) deviations
BORE_CALLOUT = "DRILL THRU"
THREAD_PASS_CLEARANCE_WORST = ID + min(ID_BAND) - STUB.REAR_THREAD_MAJOR
if THREAD_PASS_CLEARANCE_WORST <= 0.0:
    raise AssertionError(
        f"MHA-178 bore Ø{ID} does not pass the #10-32 major {STUB.REAR_THREAD_MAJOR}"
    )

# --- Fitted thickness ---------------------------------------------------------
# Never faced thinner than the stud's rear relief plus full thread before the
# arm (R9-65), at any accepted set of parts.
THICKNESS_FLOOR = FIT.SHIM_THICKNESS_FLOOR
GAP_MIN = FIT.SHIM_THICKNESS_FITTED_MIN
GAP_MAX = FIT.SHIM_THICKNESS_FITTED_MAX
# The model is the shim as fitted to parts at their nominals.
THICKNESS = FIT.MODEL_SHIM_THICKNESS

# Supplied as a blank faced both sides (the two MACHINED finish symbols say
# so; the note does not repeat them), one face faced again to fit.  The
# blank is a MIN, the loosest supply spec that works: any excess is just more
# facing.  Its MIN keeps FACING_ALLOWANCE -- one finishing cut -- over the
# thickest fit, so the fitted face is always freshly cut.
FACING_ALLOWANCE = 0.10
BLANK_THICKNESS_MIN = 4.70


def check_fit_up(gap_min: float, gap_max: float, blank_min: float) -> None:
    """Refuse a faced range under the floor or a blank too thin to face to it."""
    if gap_min < THICKNESS_FLOOR - 1e-9:
        raise AssertionError(
            f"MHA-178 would be faced to {gap_min:.3f}, under its "
            f"{THICKNESS_FLOOR} floor"
        )
    if blank_min < gap_max + FACING_ALLOWANCE - 1e-9:
        raise AssertionError(
            f"MHA-178 blank {blank_min:.2f} MIN leaves no {FACING_ALLOWANCE} "
            f"facing allowance over the {gap_max:.3f} thickest fit"
        )


check_fit_up(GAP_MIN, GAP_MAX, BLANK_THICKNESS_MIN)

# The sheet: the modelled thickness prints as a REFERENCE; the callout under
# it is the requirement, and the blank is the make-to size.  The MHA-A06 step
# pointer is appended by the drawing (a part never reads the step registry).
THICKNESS_CALLOUT = f"SET AT ASSEMBLY {GAP_MIN:.2f}-{GAP_MAX:.2f}\nFACED TO FIT"
DRAWING_NOTES = "\n".join(
    (
        f"SUPPLY {BLANK_THICKNESS_MIN:.2f} MIN THICK.",
        "ONE FACE IS FACED TO FIT AT ASSEMBLY.",
    )
)

# Both faces bear: MACHINED, on the exact native faces the part build resolves.
SURFACE_FINISHES = (
    SurfaceFinishControl("collar_face", MACHINED_UM, PlanarFace((0.0, 0.0, -1.0), 0.0)),
    SurfaceFinishControl(
        "arm_face", MACHINED_UM, PlanarFace((0.0, 0.0, 1.0), THICKNESS)
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
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-178 dimension needs authored places")
REFERENCE_DIMENSIONS = frozenset({"DiscThick"})
