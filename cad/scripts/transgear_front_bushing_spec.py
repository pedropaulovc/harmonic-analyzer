r"""MHA-181 transgear-front-bushing: the brass thrust ring in front of the cluster (R9-68).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  A turned brass ring on the MHA-179 pin between the MHA-110
sleeve's nose (steel: the hub never thrusts, R9-5) and the MHA-182 retaining
ring.  It is faced to fit at assembly, after the MHA-159 hub's front face is
faced to stand ``transgear_cluster_fit.HUB_NOSE_WINDOW`` behind the nose,
until m reads ``transgear_cluster_fit.FIT_WINDOW`` with the cluster, hub and
disc pushed forward (step 1 of the fit-up there).  It runs free on the pin;
both faces bear.  Its Ø12 rear face reaches over the hub's front face, so the
bushing, held by the ring, traps hub and disc against the sleeve's step
face (the hub's spigot seats on it).  The ring's Ø7.16 O.D. bears inside
the front face; the front O.D. edge is chamfered.

Part frame: axis local +Z through the origin (``Axis1``); faces at z = 0
(Front Plane, on the sleeve's nose) and z = LENGTH (``RingFace``, on the
retaining ring); the chamfer is on the z = LENGTH edge.
"""

from __future__ import annotations

import transgear_cluster_fit as FIT
import transgear_disc_hub_spec as HUB
import transgear_pin_spec as PIN
import transgear_retaining_ring_spec as RING
from _gtol_spec import CylinderFace, PlanarFace
from _printed_tolerance import printed_band_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl

OD = 12.0
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
# 45 deg, on the ring face's O.D. edge: a single MAX limit (the MHA-160
# precedent).  Only its largest size matters: it must leave the MHA-182
# ring a full bearing flat (checked below).
FRONT_CHAMFER = 0.5
FRONT_CHAMFER_BAND = (0.0, -0.3)  # (upper, lower)
FRONT_CHAMFER_TOL_TYPE = 6  # swTolType_e.swTolMAX
FRONT_CHAMFER_PLACES = 1
CHAMFER_CALLOUT = " X 45 DEG"

WALL_TARGET = 2.0
WALL_NOMINAL = (OD - BORE_DIA) / 2.0
WALL_WORST = (OD - printed_band_mm(OD_PLACES) - BORE_DIA - BORE_DIA_BAND[0]) / 2.0
if WALL_WORST < WALL_TARGET:
    raise AssertionError(f"MHA-181 wall {WALL_WORST:.3f} under {WALL_TARGET}")
# The retaining ring bears wholly on the flat of the front face.
if RING.OD >= OD - printed_band_mm(OD_PLACES) - 2.0 * FRONT_CHAMFER:
    raise AssertionError("MHA-182 ring overhangs the front bushing's chamfer")
# The rear face reaches over the hub's front face, past the largest bore, by
# at least a millimetre at the smallest O.D. (R9-68), so the bushing, held
# by the ring, traps hub and disc against the sleeve's step.
HUB_FACE_OVERLAP_MIN = 1.0
HUB_FACE_OVERLAP_WORST = (OD - printed_band_mm(OD_PLACES)) / 2.0 - (
    HUB.BORE_DIA + HUB.BORE_BAND[0]
) / 2.0  # 1.0925
if HUB_FACE_OVERLAP_WORST < HUB_FACE_OVERLAP_MIN:
    raise AssertionError(
        f"MHA-181 covers the MHA-159 front face by {HUB_FACE_OVERLAP_WORST:.3f} "
        f"past its bore, under {HUB_FACE_OVERLAP_MIN}"
    )

# --- Fitted length ---------------------------------------------------------------
GAP_MIN = FIT.FRONT_BUSHING_FITTED_MIN
GAP_MAX = FIT.FRONT_BUSHING_FITTED_MAX
LENGTH = FIT.FRONT_BUSHING_MODEL

FACING_ALLOWANCE = 0.10
BLANK_LENGTH_MIN = 6.10
if BLANK_LENGTH_MIN < GAP_MAX + FACING_ALLOWANCE - 1e-9:
    raise AssertionError(
        f"MHA-181 blank {BLANK_LENGTH_MIN:.2f} MIN leaves no {FACING_ALLOWANCE} "
        f"facing allowance over the {GAP_MAX:.3f} longest fit"
    )

LENGTH_CALLOUT = f"SET AT ASSEMBLY {GAP_MIN:.2f}-{GAP_MAX:.2f}\nFACED TO FIT"
DRAWING_NOTES = "\n".join(
    (
        f"SUPPLY {BLANK_LENGTH_MIN:.2f} MIN LONG.",
        "THE REAR FACE IS FACED TO FIT AT ASSEMBLY.",
    )
)

# Rule 5: the bore runs on the pin and both faces bear, so all three carry
# the machined grade, the bore as the sleeve's bore on the same pin does.
SURFACE_FINISHES = (
    SurfaceFinishControl("bore", MACHINED_UM, CylinderFace(BORE_DIA)),
    SurfaceFinishControl("nose_face", MACHINED_UM, PlanarFace((0.0, 0.0, -1.0), 0.0)),
    SurfaceFinishControl("ring_face", MACHINED_UM, PlanarFace((0.0, 0.0, 1.0), LENGTH)),
)

# The chamfer is a native chamfer feature on the O.D. edge; its one leg
# prints with the 45 deg suffix.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {"RingOd", "BoreDia"},
    "Ring": {"RingLength"},
    "FrontChamfer": {"FrontChamferSize"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RingProfile": {"RingOd": OD_PLACES, "BoreDia": BORE_PLACES},
    "Ring": {"RingLength": 1},
    "FrontChamfer": {"FrontChamferSize": FRONT_CHAMFER_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-181 dimension needs authored places")
REFERENCE_DIMENSIONS = frozenset({"RingLength"})

ISOMETRIC_VIEW_SCALE = (4, 1)
ISOMETRIC_VIEW_NOTE = (
    f"ISOMETRIC VIEW SCALE {ISOMETRIC_VIEW_SCALE[0]}:{ISOMETRIC_VIEW_SCALE[1]}"
)
