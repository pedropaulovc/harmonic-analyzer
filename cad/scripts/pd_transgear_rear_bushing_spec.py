r"""MHA-PD-024 transgear-rear-bushing: the brass spacer behind the disc cluster (R9-68).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  A turned brass ring on the MHA-PD-023 pin between the MHA-PD-018 arm's
front face and the MHA-PD-010 sleeve's rear face.  It is faced to fit at
assembly, after the front bushing, until the cluster's float reads
``transgear_cluster_fit.FLOAT_WINDOW`` (step 2 of the fit-up there).  It runs
free on the pin; both faces bear.

Part frame: axis local +Z through the origin (``Axis1``); faces at z = 0
(Front Plane, on the arm's front face) and z = LENGTH (``SleeveFace``, on
the sleeve's rear face).
"""

from __future__ import annotations

import math

import transgear_cluster_fit as FIT
import pd_transgear_pin_spec as PIN
from _gtol_spec import PlanarFace
from _printed_tolerance import printed_band_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl

OD = 9.0
OD_PLACES = 1
BORE_DIA = PIN.DIA
BORE_DIA_BAND = FIT.BORE_DIA_BAND  # (upper, lower), the sleeve's running band
BORE_PLACES = 3
# The running fit on the pin, named on the bore callout (policy rule 2).
BORE_CALLOUT = (
    "REAM THRU\n"
    f"({FIT.BORE_DIAMETRAL_CLEARANCE[0]:.3f}-{FIT.BORE_DIAMETRAL_CLEARANCE[1]:.3f}"
    " DIAMETRAL CLEARANCE\n"
    f"ON TRANSGEAR PIN {PIN.PIN_NUMBER})"
)

WALL_TARGET = 2.0
WALL_NOMINAL = (OD - BORE_DIA) / 2.0
WALL_WORST = (OD - printed_band_mm(OD_PLACES) - BORE_DIA - BORE_DIA_BAND[0]) / 2.0
if WALL_WORST < WALL_TARGET:
    raise AssertionError(f"MHA-PD-024 wall {WALL_WORST:.3f} under {WALL_TARGET}")

# --- Fitted length ---------------------------------------------------------------
GAP_MIN = FIT.REAR_BUSHING_FITTED_MIN
GAP_MAX = FIT.REAR_BUSHING_FITTED_MAX
# The model is the bushing as fitted to parts at their nominals.
LENGTH = FIT.REAR_BUSHING_MODEL

# Supplied as a blank faced both sides, one face faced again to fit.  The
# blank is a MIN: FACING_ALLOWANCE (one finishing cut) over the longest fit.
FACING_ALLOWANCE = 0.10
BLANK_LENGTH_MIN = 6.85
if BLANK_LENGTH_MIN < GAP_MAX + FACING_ALLOWANCE - 1e-9:
    raise AssertionError(
        f"MHA-PD-024 blank {BLANK_LENGTH_MIN:.2f} MIN leaves no {FACING_ALLOWANCE} "
        f"facing allowance over the {GAP_MAX:.3f} longest fit"
    )
if not math.isclose(LENGTH, 6.0, abs_tol=1e-6):
    raise AssertionError(f"MHA-PD-024 model length {LENGTH} left the rev 5 B 6.0")

# The sheet: the modelled length prints as a REFERENCE; the callout under it
# is the requirement, and the blank is the make-to size.  The MHA-PD-000 step
# pointer is appended by the drawing (a part never reads the step registry).
LENGTH_CALLOUT = f"SET AT ASSEMBLY {GAP_MIN:.2f}-{GAP_MAX:.2f}\nFACED TO FIT"
DRAWING_NOTES = "\n".join(
    (
        f"SUPPLY {BLANK_LENGTH_MIN:.2f} MIN LONG.",
        "ONE FACE IS FACED TO FIT AT ASSEMBLY.",
    )
)

SURFACE_FINISHES = (
    SurfaceFinishControl("arm_face", MACHINED_UM, PlanarFace((0.0, 0.0, -1.0), 0.0)),
    SurfaceFinishControl(
        "sleeve_face", MACHINED_UM, PlanarFace((0.0, 0.0, 1.0), LENGTH)
    ),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {"RingOd", "BoreDia"},
    "Ring": {"RingLength"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RingProfile": {"RingOd": OD_PLACES, "BoreDia": BORE_PLACES},
    "Ring": {"RingLength": 1},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-PD-024 dimension needs authored places")
REFERENCE_DIMENSIONS = frozenset({"RingLength"})

ISOMETRIC_VIEW_SCALE = (4, 1)
ISOMETRIC_VIEW_NOTE = (
    f"ISOMETRIC VIEW SCALE {ISOMETRIC_VIEW_SCALE[0]}:{ISOMETRIC_VIEW_SCALE[1]}"
)
