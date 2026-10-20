"""MHA-PD-VN-64: live-sourced McMaster 93600A189 arm/plate locating dowel.

316 stainless steel, passivated, ISO 2338-m6, both ends chamfered. The
supplier specifies diameter 2.002..2.008 and nominal length 6 mm.
ISO 2338:1997 Table 1 gives length 5.75..6.25; end c≈0.35 is only
a reference, NOT a maximum or a full-cylinder guarantee. The purchased
native reference remains a nominal cylinder, with no invented end form.

Reference frame: axis +Y, first end y=0, other end y=LENGTH. Installed
pins are pressed in the arm, not to the blind floor; screws clamp only.
"""

from __future__ import annotations

import math

import _transgear_arm_plate_locating_interface as INTERFACE

SKU = "93600A189"
PART_NUMBER = "MHA-PD-VN-64"
PART_STEM = "pd-vn-transgear-arm-plate-locating-pin"
ASSEMBLY_QUANTITY = 2
DIA = 2.0
DIA_LIMITS = (2.002, 2.008)
LENGTH = 6.0
# Published ISO 2338:1997 Table 1, not an incoming acceptance band.
# https://cdn.standards.iteh.ai/samples/20001/5b26cece48c448b782c0de1eccb5b16c/ISO-2338-1997.pdf
LENGTH_LIMITS_MM = (5.75, 6.25)
END_FORM_REFERENCE_MM = 0.35  # c≈, explicitly NOT a maximum
# The purchased pin remains 316 stainless. As with the 17-7 PH spring,
# the repository's valid "AISI 304" library entry is the native stand-in;
# plain "AISI 316" is not a SolidWorks library material name.
MATERIAL = "AISI 304"
MATERIAL_DENSITY_KG_M3 = 8000.0  # purchased 316 engineering density, not a lot certificate
PRESS_INTERFERENCE_MM = (
    DIA_LIMITS[0] - INTERFACE.PRESS_HOLE_LIMITS_MM[1],
    DIA_LIMITS[1] - INTERFACE.PRESS_HOLE_LIMITS_MM[0],
)
SLIP_DIAMETRAL_CLEARANCE_MM = (
    INTERFACE.SLIP_HOLE_LIMITS_MM[0] - DIA_LIMITS[1],
    INTERFACE.SLIP_HOLE_LIMITS_MM[1] - DIA_LIMITS[0],
)
INSERTION_LIMITS_MM = (
    LENGTH_LIMITS_MM[0] - INTERFACE.PROUD_LIMITS_MM[1],
    LENGTH_LIMITS_MM[1] - INTERFACE.PROUD_LIMITS_MM[0],
)
ARM_BOTTOM_AIR_MIN_MM = (
    INTERFACE.ARM_BLIND_DEPTH_MM - INTERFACE.ARM_BLIND_DEPTH_TOLERANCE_MM - INSERTION_LIMITS_MM[1]
)

PURCHASED_STOCK_NOTE = "\n".join((
    "INSTALLATION - TWO PER MHA-PD-18 ARM: PRESS INTO THE ARM, NOT TO THE",
    "BLIND FLOOR. THE MHA-PD-19 PLATE SLIPS ON; ITS SCREWS CLAMP ONLY,",
    "THE PINS LOCATE IT (MHA-PD-00).",
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
