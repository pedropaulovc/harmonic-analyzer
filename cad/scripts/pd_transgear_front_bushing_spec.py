r"""MHA-PD-25 transgear-front-bushing: the brass thrust ring in front of the cluster (R9-68).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  A turned brass ring on the MHA-PD-23 pin between the MHA-PD-10
sleeve's nose (steel: the hub never thrusts, R9-5) and the MHA-PD-VN-61 retaining
ring.  Its length is printed (#2038 owner ruling 2026-10-28: nothing in the
disc cluster is faced to fit): ``transgear_cluster_fit.FRONT_BUSHING_LENGTH``
sets, with the cluster forward, the collar-to-disc air (``pd_cluster_air``).
It runs free on the pin;
both faces bear.  Its Ø.47 rear face reaches over the hub's front face, so the
bushing, held by the ring, traps hub and disc against the sleeve's step
face (the hub's spigot seats on it).  The ring's Ø.230 O.D. bears inside
the front face; the front O.D. edge is chamfered.  #290: the sheet prints
decimal inch; every length is the exact millimetre value of its inch
nominal.

Part frame: axis local +Z through the origin (``Axis1``); faces at z = 0
(Front Plane, on the sleeve's nose) and z = LENGTH (``RingFace``, on the
retaining ring); the chamfer is on the z = LENGTH edge.
"""

from __future__ import annotations

import _config
import transgear_cluster_fit as FIT
from pd_cluster_stack_band import STACK_NAME
import pd_transgear_disc_hub_spec as HUB
import pd_transgear_pin_spec as PIN
import pd_vn_transgear_retaining_ring_spec as RING
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl

UNIT = drawing_unit(
    "parts/pd-transgear-front-bushing", _config.parts("pd-transgear-front-bushing")
)

OD = 11.938  # .47
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
# 45 deg, on the ring face's O.D. edge: a single MAX limit (the MHA-160
# precedent).  Only its largest size matters: it must leave the MHA-PD-VN-61
# ring a full bearing flat (checked below).  The part authors " MAX" as the
# size's suffix: SolidWorks' native swTolMAX prints a lowercase "max." that
# reads unlike every other callout (machinist review round 2).
FRONT_CHAMFER = 0.508  # .02 MAX
FRONT_CHAMFER_PLACES = 2
CHAMFER_SUFFIX = " MAX"
CHAMFER_CALLOUT = "X 45\u00b0"

WALL_NOMINAL = (OD - BORE_DIA) / 2.0
WALL_WORST = (
    OD - printed_band_mm(OD_PLACES, unit=UNIT) - BORE_DIA - BORE_DIA_BAND[0]
) / 2.0
if WALL_WORST < WALL_TARGET_MM:
    raise AssertionError(f"MHA-PD-25 wall {WALL_WORST:.3f} under {WALL_TARGET_MM}")
# The retaining ring bears wholly on the flat of the front face.
if RING.OD >= OD - printed_band_mm(OD_PLACES, unit=UNIT) - 2.0 * FRONT_CHAMFER:
    raise AssertionError("MHA-PD-VN-61 ring overhangs the front bushing's chamfer")
# The rear face reaches over the hub's front face, past the largest bore, by
# at least a millimetre at the smallest O.D. (R9-68), so the bushing, held
# by the ring, traps hub and disc against the sleeve's step.
HUB_FACE_OVERLAP_MIN = 1.0
HUB_FACE_OVERLAP_WORST = (OD - printed_band_mm(OD_PLACES, unit=UNIT)) / 2.0 - (
    HUB.BORE_DIA + HUB.BORE_BAND[0]
) / 2.0
if HUB_FACE_OVERLAP_WORST < HUB_FACE_OVERLAP_MIN:
    raise AssertionError(
        f"MHA-PD-25 covers the MHA-PD-17 front face by {HUB_FACE_OVERLAP_WORST:.3f} "
        f"past its bore, under {HUB_FACE_OVERLAP_MIN}"
    )

# --- Length: printed (#2038 owner ruling 2026-10-28, option A) --------------------
# With the cluster forward it sets F to the disc's front face (m), so the
# drive collar's air to the disc: a term of the disc cluster's printed stack.
LENGTH = FIT.FRONT_BUSHING_LENGTH  # .222
LENGTH_BAND = FIT.LENGTH_BAND
LENGTH_PLACES = FIT.LENGTH_PLACES
# Rule 4: the band names the stack it serves and what it sets.
LENGTH_CALLOUT = f"{STACK_NAME},\nSETS COLLAR TO DISC AIR"

# drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates): the bore runs on the pin and both faces bear, so all three carry
# the machined grade, the bore as the sleeve's bore on the same pin does.
# The bushing runs free between the turning MHA-PD-10 sleeve's nose and the
# MHA-PD-VN-61 ring on the pin, so either face may slip under the cluster's
# thrust: each face's symbol names its mate (rule 7, say why).
REAR_FACE_TARGET = f"THRUST ON {HUB.SLEEVE_NUMBER}"
FRONT_FACE_TARGET = f"THRUST ON {PIN.RING_NUMBER}"
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "bore", MACHINED_UM, CylinderFace(BORE_DIA), display_unit=UNIT
    ),
    SurfaceFinishControl(
        "nose_face",
        MACHINED_UM,
        PlanarFace((0.0, 0.0, -1.0), 0.0),
        production_method=REAR_FACE_TARGET,
        display_unit=UNIT,
    ),
    SurfaceFinishControl(
        "ring_face",
        MACHINED_UM,
        PlanarFace((0.0, 0.0, 1.0), LENGTH),
        production_method=FRONT_FACE_TARGET,
        display_unit=UNIT,
    ),
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
    "Ring": {"RingLength": LENGTH_PLACES},
    "FrontChamfer": {"FrontChamferSize": FRONT_CHAMFER_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-PD-25 dimension needs authored places")
REFERENCE_DIMENSIONS: frozenset[str] = frozenset()

ISOMETRIC_VIEW_SCALE = (4, 1)
ISOMETRIC_VIEW_NOTE = (
    f"ISOMETRIC VIEW SCALE {ISOMETRIC_VIEW_SCALE[0]}:{ISOMETRIC_VIEW_SCALE[1]}"
)
