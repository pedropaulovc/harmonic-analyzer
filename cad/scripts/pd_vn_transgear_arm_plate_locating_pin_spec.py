"""MHA-PD-VN-64: McMaster 98381A216 arm/plate locating dowel.

Alloy steel, 1/8 x 5/16, Round x Chamfer ends, ASME B18.8.2; the supplier
specifies diameter +.0001/+.0003 over nominal.  Fit audit 2026-11-23
(pending owner confirmation; owner, 2026-11-23: "can the holes not be
reamed in the first place"): the pair is 1/8, so the arm's press and the
plate's slip are the .1240 and .1260 members of the over/under reamer set
and no reamer is bought for these two holes.  It replaces the 3/32 x 5/16
98381A435 of #290 (owner ruling 2026-10-30, metric dowels to inch).  The
SKU is in no other assembly, so it stays a PD identity (AGENTS.md).  The
purchased native reference remains a nominal cylinder, with no invented
end form.

Reference frame: axis +Y, first end y=0, other end y=LENGTH. Installed
pins are pressed into the arm's through holes from the rear, to the proud
set, and punched out from the front; screws clamp only.
"""

from __future__ import annotations

import math

import _config
import _transgear_arm_plate_locating_interface as INTERFACE
from _mcmaster_98381a216 import DIA_BAND_IN, DOWEL_SIZE, MM_PER_IN
from _package_units import drawing_unit
from _sprocket_seat_geometry import DRIVE_PIN_LENGTH_GRADE
from _supplier_pin_data import SupplierPinReference

SKU = "98381A216"
PART_NUMBER = "MHA-PD-VN-64"
PART_STEM = "pd-vn-transgear-arm-plate-locating-pin"
ASSEMBLY_QUANTITY = 2
DIA, LENGTH = DOWEL_SIZE  # 3.175 x 7.9375
DIA_LIMITS = tuple(DIA + band * MM_PER_IN for band in DIA_BAND_IN)
# The 98381A family's +/-.010 length grade (the seat's drive dowels' too).
LENGTH_LIMITS_MM = (LENGTH - DRIVE_PIN_LENGTH_GRADE, LENGTH + DRIVE_PIN_LENGTH_GRADE)
MATERIAL_DENSITY_KG_M3 = 7850.0  # alloy steel engineering density, not a lot certificate
# The fits the two set reamers are modelled to give on the catalogue dowel
# (analysis, not printed limits: the sheets print each reamer's size and the
# dowel is the gauge).  The plate must come back to the knob-axis setting of
# MHA-PD-00 step 12 after every refit, which is why one hole grips and the
# other is a close slip.
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
if min(PRESS_INTERFERENCE_MM) <= 0.0 or min(SLIP_DIAMETRAL_CLEARANCE_MM) <= 0.0:
    raise AssertionError(f"{SKU} loses the arm's press or the plate's slip")
# A dowel that slides into the arm by hand is bonded (MHA-PD-00's bond
# note): at worst the arm's hole was cut as large as the plate's, and that
# gap stays inside the retaining compound's limit.
BOND_GAP_MAX_MM = INTERFACE.SLIP_HOLE_LIMITS_MM[1] - DIA_LIMITS[0]
if BOND_GAP_MAX_MM > INTERFACE.BOND_GAP_LIMIT_MM:
    raise AssertionError(f"{SKU} bonded in an oversize arm hole exceeds the compound's gap")


def nominal_material_properties() -> dict[str, object]:
    """Nominal reference-cylinder mass/CG, not an end-form certificate."""
    volume = math.pi * (DIA / 2.0)**2 * LENGTH
    return {
        "volume_mm3": volume,
        "mass_kg": volume * MATERIAL_DENSITY_KG_M3 * 1e-9,
        "centre_of_mass_local_mm": (0.0, LENGTH / 2.0, 0.0),
        "model_scope": "nominal reference cylinder; catalogue chamfers remove material",
    }


# McMaster family table, read 2026-11-23 (cad/references/mcmaster/README.md).
# Exact 1/8 x 5/16 geometry, printed as untoleranced supplier REF (#2147);
# the catalogue's +.0001/+.0003 band stays in DIA_LIMITS for the fits.
SUPPLIER_REFERENCE = SupplierPinReference(
    sku=SKU,
    units="in",
    diameter_mm=DIA,
    length_mm=LENGTH,
    diameter_precision=4,
    length_precision=4,
    sheet_unit=drawing_unit(
        "parts/pd-vn-transgear-arm-plate-locating-pin",
        _config.parts("pd-vn-transgear-arm-plate-locating-pin"),
    ),
)
