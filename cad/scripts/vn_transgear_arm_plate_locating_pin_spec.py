"""MHA-VN-051: live-sourced McMaster 93600A189 arm/plate locating dowel.

316 stainless steel, passivated, ISO 2338-m6, both ends chamfered. The
supplier specifies diameter2.002..2.008 and nominal length6mm.
ISO2338:1997 Table1 gives length5.75..6.25; endc≈0.35 is only
a reference, NOT a maximum or a full-cylinder guarantee. The purchased
native reference remains a nominal cylinder, with no invented end form.

Reference frame: axis +Y, first end y=0, other end y=LENGTH. Installed
pins are pressed in the arm, not to the blind floor; screws clamp only.
"""

from __future__ import annotations

import math

SKU = "93600A189"
PART_NUMBER = "MHA-VN-051"
PART_STEM = "vn-transgear-arm-plate-locating-pin"
ASSEMBLY_QUANTITY = 2
DIA = 2.0
DIA_LIMITS = (2.002, 2.008)
LENGTH = 6.0
# Published ISO2338:1997 Table1, not an incoming acceptance band.
# https://cdn.standards.iteh.ai/samples/20001/5b26cece48c448b782c0de1eccb5b16c/ISO-2338-1997.pdf
LENGTH_LIMITS_MM = (5.75, 6.25)
END_FORM_REFERENCE_MM = 0.35  # c≈, explicitly NOT a maximum
# The purchased pin remains 316 stainless. As with the 17-7 PH spring,
# the repository's valid "AISI 304" library entry is the native stand-in;
# plain "AISI 316" is not a SolidWorks library material name.
MATERIAL = "AISI 304"
MATERIAL_DENSITY_KG_M3 = 8000.0  # purchased 316 engineering density, not a lot certificate
PRESS_HOLE_LIMITS_MM = (1.990, 2.000)
SLIP_HOLE_LIMITS_MM = (2.010, 2.020)
PRESS_INTERFERENCE_MM = (
    DIA_LIMITS[0] - PRESS_HOLE_LIMITS_MM[1],
    DIA_LIMITS[1] - PRESS_HOLE_LIMITS_MM[0],
)
SLIP_DIAMETRAL_CLEARANCE_MM = (
    SLIP_HOLE_LIMITS_MM[0] - DIA_LIMITS[1],
    SLIP_HOLE_LIMITS_MM[1] - DIA_LIMITS[0],
)
PROUD_MM = 1.70
PROUD_TOLERANCE_MM = 0.03
PROUD_LIMITS_MM = (PROUD_MM - PROUD_TOLERANCE_MM, PROUD_MM + PROUD_TOLERANCE_MM)
ARM_BLIND_DEPTH_MM = 4.80
ARM_BLIND_DEPTH_TOLERANCE_MM = 0.05
HOLE_MOUTH_BREAK_AXIAL_MAX_MM = 0.05
HOLE_MOUTH_BREAK_RADIAL_MAX_MM = 0.05
INSERTION_LIMITS_MM = (
    LENGTH_LIMITS_MM[0] - PROUD_LIMITS_MM[1],
    LENGTH_LIMITS_MM[1] - PROUD_LIMITS_MM[0],
)
ARM_BOTTOM_AIR_MIN_MM = (
    ARM_BLIND_DEPTH_MM - ARM_BLIND_DEPTH_TOLERANCE_MM - INSERTION_LIMITS_MM[1]
)

PURCHASED_STOCK_NOTE = "\n".join((
    f"McMASTER {SKU} / 316 SS / PASSIVATED",
    "2 x 6 NOMINAL; ISO2338-m6, BOTH ENDS CHAMFERED",
    "TWO MATCHED LOCATORS / PRESS ARM; SLIP PLATE",
    "SCREWS CLAMP ONLY; DO NOT BOTTOM IN ARM",
))


def nominal_material_properties() -> dict[str, object]:
    """Nominal reference-cylinder mass/CG, not an end-form certificate."""
    volume = math.pi * (DIA / 2.0)**2 * LENGTH
    return {
        "volume_mm3": volume,
        "mass_kg": volume * MATERIAL_DENSITY_KG_M3 * 1e-9,
        "centre_of_mass_local_mm": (0.0, LENGTH / 2.0, 0.0),
        "model_scope": "nominal reference cylinder; catalogue chamfers remove material",
    }
