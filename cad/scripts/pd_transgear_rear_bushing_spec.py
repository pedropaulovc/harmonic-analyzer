r"""MHA-PD-24 transgear-rear-bushing: the brass spacer behind the disc cluster (R9-68).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  A turned brass ring on the MHA-PD-23 pin between the MHA-PD-18 arm's
front face and the MHA-PD-10 sleeve's rear face.  Its length is printed (#2038
owner ruling 2026-10-28: nothing in the disc cluster is faced to fit):
``transgear_cluster_fit.REAR_BUSHING_LENGTH`` holds the disc's end float at
``transgear_cluster_fit.END_FLOAT_MIN`` at the worst case and places the
disc's rear face to the platen (``pd_cluster_air``).  It runs free on the
pin; both faces bear.

Part frame: axis local +Z through the origin (``Axis1``); faces at z = 0
(Front Plane, on the arm's front face) and z = LENGTH (``SleeveFace``, on
the sleeve's rear face).
"""

from __future__ import annotations

import transgear_cluster_fit as FIT
from pd_cluster_stack_band import STACK_NAME
import pd_transgear_pin_spec as PIN
from _gtol_planar import PlanarFace
from _printed_tolerance import printed_band_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl

OD = 9.0
OD_PLACES = 1
BORE_DIA = PIN.DIA
BORE_DIA_BAND = FIT.BORE_DIA_BAND  # (upper, lower), the sleeve's running band
BORE_PLACES = 3
# The running fit on the pin, named on the bore callout (drawing-guidelines.md rule 4 (tighten only for function, and name the mate)).
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
    raise AssertionError(f"MHA-PD-24 wall {WALL_WORST:.3f} under {WALL_TARGET}")

# --- Length: printed (#2038 owner ruling 2026-10-28, option A) --------------------
# It sets the disc's end float (worst case) and, cluster rearward, where the
# disc's rear face stands to the platen: a term of the disc cluster's
# printed stack.
LENGTH = FIT.REAR_BUSHING_LENGTH  # 5.69
LENGTH_BAND = FIT.LENGTH_BAND
LENGTH_PLACES = FIT.LENGTH_PLACES
# Rule 4: the band names the stack it serves and what it sets.
LENGTH_CALLOUT = f"{STACK_NAME},\nSETS DISC END FLOAT"

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
    "Ring": {"RingLength": LENGTH_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-PD-24 dimension needs authored places")
REFERENCE_DIMENSIONS: frozenset[str] = frozenset()

ISOMETRIC_VIEW_SCALE = (4, 1)
ISOMETRIC_VIEW_NOTE = (
    f"ISOMETRIC VIEW SCALE {ISOMETRIC_VIEW_SCALE[0]}:{ISOMETRIC_VIEW_SCALE[1]}"
)
