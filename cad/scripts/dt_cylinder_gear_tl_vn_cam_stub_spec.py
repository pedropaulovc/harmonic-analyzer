r"""MHA-DT-12-TL-VN-50 cam fixture stub: McMaster 97175A344 pull-out dowel.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure. Shop fixture hardware (cad/docs/subsystem-identities.md), modelled
so the MHA-DT-12-TL-00 kit can place it: pressed through the MHA-DT-12-TL-01
body's .3745 ream at the cam throw, tapped end out. Each cylinder gear's
Ø.3760 bore slides on its standing end, and the -VN-52 clamp screw threads
into its 10-32 tap. The press, the stand-out and the engagement are the
fixture's (``dt_cylinder_gear_tl_cam_fixture_spec``).

Catalogue (``_mcmaster_97175a344``, read live 2026-11-12): 4140 alloy
steel, 3/8 x 3/4, tapped 10-32, diameter +.0001/+.0003 over nominal,
Rockwell C47 minimum, ASME B18.8.2, $3.81 each. No vendor model was fetched;
the recipe is ``diagnostics/diag_build_97175A344.py`` (catalog-only).

Part frame: axis local +Y through the origin; the plain (pressed) end face
at y = 0, the tapped end face at y = LENGTH.
"""

from __future__ import annotations

import _config
from _mcmaster_97175a344 import DIA, DIA_BAND_IN, LENGTH, PART_NO
from _package_units import drawing_unit
from _supplier_pin_data import SupplierPinReference

PART_NAME = "dt-cylinder-gear-tl-vn-cam-stub"
UNIT = drawing_unit(
    "parts/dt-cylinder-gear-tl-vn-cam-stub",
    _config.parts("dt-cylinder-gear-tl-vn-cam-stub"),
)
SKU = PART_NO
QUANTITY = 1
if int(_config.parts("dt-cylinder-gear-tl-vn-cam-stub")["quantity"]) != QUANTITY:
    raise AssertionError(f"{SKU}: one stub per fixture")
DIA_LIMITS_MM = (DIA + DIA_BAND_IN[0] * 25.4, DIA + DIA_BAND_IN[1] * 25.4)

# Catalogue sizes print as untoleranced REF (#2147): the catalogue tolerance
# governs; the fixture's press window is the fit control.
SUPPLIER_REFERENCE = SupplierPinReference(
    sku=SKU,
    units="in",
    diameter_mm=DIA,
    length_mm=LENGTH,
    diameter_precision=4,
    length_precision=3,
    sheet_unit=UNIT,
)
