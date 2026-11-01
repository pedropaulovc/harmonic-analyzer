r"""MHA-PD-24 transgear-rear-bushing: the brass spacer behind the disc cluster (R9-68).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  A turned brass ring on the MHA-PD-23 pin between the MHA-PD-VN-68
shims on the MHA-PD-18 arm's front face and the MHA-PD-10 sleeve's rear face.
Its length only sets the disc's end float, which the shims close at assembly
(owner ruling 2026-11-01, #2124), so it prints at the title block:
``transgear_cluster_fit.REAR_BUSHING_LENGTH`` keeps the unshimmed float over
``transgear_cluster_fit.END_FLOAT_MIN`` at the worst case.  It runs free on
the pin; both faces bear.  #290: the sheet prints decimal inch; every length
is the exact millimetre value of its inch nominal.

Part frame: axis local +Z through the origin (``Axis1``); faces at z = 0
(Front Plane, on the arm's front face) and z = LENGTH (``SleeveFace``, on
the sleeve's rear face).
"""

from __future__ import annotations

import _config
import transgear_cluster_fit as FIT
import pd_transgear_pin_spec as PIN
from _gtol_planar import PlanarFace
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl

UNIT = drawing_unit(
    "parts/pd-transgear-rear-bushing", _config.parts("pd-transgear-rear-bushing")
)

OD = 8.89  # .35
OD_PLACES = 2
BORE_DIA = PIN.DIA
BORE_DIA_BAND = FIT.BORE_DIA_BAND  # (upper, lower), the sleeve's running band
BORE_PLACES = 4
# The running fit on the pin, named on the bore callout (drawing-guidelines.md rule 4 (tighten only for function, and name the mate)).
BORE_CALLOUT = (
    "REAM THRU\n"
    f"({PIN.inch_text(FIT.BORE_DIAMETRAL_CLEARANCE[0], 4)}-"
    f"{PIN.inch_text(FIT.BORE_DIAMETRAL_CLEARANCE[1], 4)}"
    " DIAMETRAL CLEARANCE\n"
    f"ON TRANSGEAR PIN {PIN.PIN_NUMBER})"
)

WALL_NOMINAL = (OD - BORE_DIA) / 2.0
WALL_WORST = (
    OD - printed_band_mm(OD_PLACES, unit=UNIT) - BORE_DIA - BORE_DIA_BAND[0]
) / 2.0
if WALL_WORST < WALL_TARGET_MM:
    raise AssertionError(f"MHA-PD-24 wall {WALL_WORST:.3f} under {WALL_TARGET_MM}")

# --- Length: title block (owner ruling 2026-11-01, #2124) -----------------------
# The shims under it set the disc's end float, so its .XXX band only moves
# the shim count (transgear_cluster_fit.SHIM_COUNT_RANGE).
LENGTH = FIT.REAR_BUSHING_LENGTH  # .214
LENGTH_PLACES = FIT.LENGTH_PLACES

SURFACE_FINISHES = (
    SurfaceFinishControl(
        "arm_face",
        MACHINED_UM,
        PlanarFace((0.0, 0.0, -1.0), 0.0),
        display_unit=UNIT,
    ),
    SurfaceFinishControl(
        "sleeve_face",
        MACHINED_UM,
        PlanarFace((0.0, 0.0, 1.0), LENGTH),
        display_unit=UNIT,
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
