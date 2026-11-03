r"""MHA-CH-06-TL-VN-81 oblique-trammel feed nut dowel: McMaster 98381A438.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture (cad/docs/subsystem-identities.md): one 3/32 x 1/2 in
alloy-steel dowel, bought as a pack of 100.  It is the TL-27 brass feed nut's
positive anti-rotation key (Main ruling 2026-11-03): a slip fit in the nut's
reamed hole and pressed into the MHA-CH-06-TL-32 feed-block lug.  The holes,
their sizes and the fitting procedure belong to TL-27, TL-32 and the jig
assembly MHA-CH-06-TL-00, not to this sheet.

Sources:

* SOURCED, McMaster 98381A438 (https://www.mcmaster.com/98381A438/, read live
  2026-11-03): alloy steel, 3/32 in diameter, diameter tolerance 0.0001 to
  0.0003 in (.0939-.0941), 1/2 in long (length tolerance not stated),
  Rockwell C47 min, ASME B18.8.2, end shape "Round x Chamfer", pack of 100.
* NO VENDOR MODEL: the recipe ``diagnostics/diag_build_98381A438.py`` (the
  shared ``diag_mcmaster_dowel`` section) draws the plain nominal cylinder
  (``ENDS`` is None, the 98381A433 rule); it is not replica-gated and its
  standalone run is catalog-only.

Part frame: pin axis local +Y through the origin, published as ``ScrewAxis``
(Front ∩ Right); one end face at y = 0 (the Top Plane), the other at
y = LENGTH.
"""

from __future__ import annotations

import _config
from _mcmaster_98381a438 import DIA_BAND_IN, DOWEL_SIZE, ENDS, MM_PER_IN
from _package_units import drawing_unit

__all__ = [
    "DIA",
    "DIA_BAND",
    "DIA_MAX",
    "DIA_MIN",
    "ENDS",
    "LENGTH",
    "NUMBER",
    "PACK_QUANTITY",
    "PART_NAME",
    "QUANTITY",
    "SKU",
]

PART_NAME = "ch-rocker-arm-tl-vn-oblique-nut-dowel"
_ROW = _config.parts("ch-rocker-arm-tl-vn-oblique-nut-dowel")
NUMBER = _ROW["number"]
UNIT = drawing_unit("parts/ch-rocker-arm-tl-vn-oblique-nut-dowel", _ROW)

SKU = "98381A438"
QUANTITY = 1
PACK_QUANTITY = 100  # McMaster sells 98381A438 in packs of 100

DIA, LENGTH = DOWEL_SIZE  # 3/32, 1/2 in nominal, mm
DIA_BAND = tuple(band * MM_PER_IN for band in DIA_BAND_IN)  # +.0001/+.0003
DIA_MIN = DIA + min(DIA_BAND)  # .0939
DIA_MAX = DIA + max(DIA_BAND)  # .0941

# The supplier table's nominal 3/32 and 1/2 print as untoleranced references;
# its diameter band is quoted in the supplier data. Both carriers lie on
# Front-view edges, so their construction lines print under the outline: the
# diameter on the y = 0 end face's edge, the length on the left silhouette.
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierDowelDiameter", DIA, "horizontal"),
    ("SupplierDowelLength", LENGTH, "vertical"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierDowelDiameter": (-DIA / 2.0, 0.0),
    "SupplierDowelLength": (-DIA / 2.0, 0.0),
}
SUPPLIER_REFERENCE_PLANES = {
    "SupplierDowelDiameter": "Front",
    "SupplierDowelLength": "Front",
}
SUPPLIER_REFERENCE_SIDES = {
    "SupplierDowelDiameter": "bottom",
    "SupplierDowelLength": "left",
}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierDowelDiameter": (0, "diameter", 32, "NOMINAL PIN DIAMETER"),
    "SupplierDowelLength": (0, "length", 2, "NOMINAL LENGTH"),
}
SUPPLIER_REFERENCE_UNITS = {
    "SupplierDowelDiameter": "in",
    "SupplierDowelLength": "in",
}
SUPPLIER_DATA = (
    "NOMINAL SUPPLIER REFERENCES; DIAMETER +.0001/+.0003 (.0939-.0941).",
    "ONE END ROUND, ONE END CHAMFERED; LENGTH TOLERANCE NOT STATED.",
)
