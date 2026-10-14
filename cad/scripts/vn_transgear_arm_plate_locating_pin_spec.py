"""MHA-VN-056: live-sourced McMaster 98381A434 arm/plate locating dowel.

All-inch swap (was the metric 2 x 6 ISO 2338-m6 93600A189): alloy steel,
3/32 x 1/4, Round x Chamfer ends, diameter +0.0001..+0.0003 in over nominal
(live page 2026-10-14, https://www.mcmaster.com/98381A434/, in stock). The
page states no length tolerance; ASME B18.8.2's hardened ground dowel
+/-0.010 in is booked [INFERENCE: the 98381A family meets B18.8.2]. The same
SKU is the MHA-VN-044 crank-seat drive pin, so the stock recipe is shared.
The purchased native reference remains a nominal cylinder, with no invented
end form.

Reference frame: axis +Y, first end y=0, other end y=LENGTH. Installed
pins are pressed in the arm, not to the blind floor; screws clamp only.
"""

from __future__ import annotations

import math

from _inch import inch
from _mcmaster_98381a434 import DIA_BAND_IN, DOWEL_SIZE, MM_PER_IN

SKU = "98381A434"
PART_NUMBER = "MHA-VN-056"
PART_STEM = "vn-transgear-arm-plate-locating-pin"
ASSEMBLY_QUANTITY = 2
DIA, LENGTH = DOWEL_SIZE  # 2.38125 x 6.35
DIA_LIMITS = tuple(DIA + band * MM_PER_IN for band in DIA_BAND_IN)
# ASME B18.8.2 hardened ground dowel length tolerance, +/-0.010 in.
LENGTH_LIMITS_MM = (LENGTH - 0.010 * MM_PER_IN, LENGTH + 0.010 * MM_PER_IN)
# The pages give Round x Chamfer but no dimensions; reference only.
END_FORM_REFERENCE_MM = None
# The stock-fastener catalogue renders this SKU as "Alloy Steel" (the
# MHA-VN-044 precedent).
MATERIAL = "Alloy Steel"
MATERIAL_DENSITY_KG_M3 = 7850.0  # alloy steel engineering density, not a lot certificate
# Ream bands keep the metric design's offsets from the pin nominal:
# press 0/-0.010 below, slip +0.010/+0.020 above.
PRESS_HOLE_LIMITS_MM = (DIA - 0.010, DIA)
SLIP_HOLE_LIMITS_MM = (DIA + 0.010, DIA + 0.020)
PRESS_INTERFERENCE_MM = (
    DIA_LIMITS[0] - PRESS_HOLE_LIMITS_MM[1],
    DIA_LIMITS[1] - PRESS_HOLE_LIMITS_MM[0],
)
SLIP_DIAMETRAL_CLEARANCE_MM = (
    SLIP_HOLE_LIMITS_MM[0] - DIA_LIMITS[1],
    SLIP_HOLE_LIMITS_MM[1] - DIA_LIMITS[0],
)
PROUD_MM = inch(1, 16)
PROUD_TOLERANCE_MM = 0.03
PROUD_LIMITS_MM = (PROUD_MM - PROUD_TOLERANCE_MM, PROUD_MM + PROUD_TOLERANCE_MM)
# 7/32, not 3/16: a 3/16 blind hole is shorter than the longest insertion
# (1/4 + 0.010 in less the shortest proud) and the pin would bottom.
ARM_BLIND_DEPTH_MM = inch(7, 32)
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
if min(PRESS_INTERFERENCE_MM) <= 0.0 or min(SLIP_DIAMETRAL_CLEARANCE_MM) <= 0.0:
    raise AssertionError(f"{SKU} press/slip limits lost their fit")
if ARM_BOTTOM_AIR_MIN_MM <= 0.0:
    raise AssertionError(f"{SKU} bottoms in the arm's blind locator hole")

PURCHASED_STOCK_NOTE = "\n".join((
    f"McMASTER {SKU}",
    "3/32 x 1/4 NOMINAL; ALLOY STEEL, ROUND x CHAMFER",
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
        "model_scope": "nominal reference cylinder; catalogue end forms remove material",
    }
