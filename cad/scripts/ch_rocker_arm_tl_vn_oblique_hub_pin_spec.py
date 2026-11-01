"""MHA-CH-06-TL-VN-80: purchased oblique-trammel hub pin.

Source: https://www.mcmaster.com/23065A855-23065A4/
Read live 2026-10-31: Class Z plug gauge, tool steel, NO-GO, size .4000 -.0001/0 in,
2 in long, Rockwell C60, ASME B89.1.5, accuracy certificate traceable to NIST.
Page-stated dimensions only. Bands are (upper, lower) deviations, mm. No supplier
length band is inferred. Model: nominal supplied envelope; unstated edge forms are
not invented. Frame: axis +Z; origin at the bottom face.
The cut length and the Loctite 638 bond are owner requirements, not supplier claims;
the sheet prints the cut length as its one shop dimension and the diameter as a plain
reference (the .0001 class band controls nothing the shop makes).

Issue #290: the sheet prints decimal inch. The cut length closes the inch stack:
bottom flush with the carrier underside, top TIP_SET above the riser, so the bonded
length is the whole .47 carrier (``_interference_contracts.JIG_HUB_PIN_SEAT``).
"""

from __future__ import annotations

import _config
from _package_units import drawing_unit
import ch_rocker_arm_tl_oblique_trammel_spec as trammel

UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-vn-oblique-hub-pin",
    _config.parts("ch-rocker-arm-tl-vn-oblique-hub-pin"),
)

# 23065A855 is the .2505-.5005 NO-GO size family; choosing the .4000 size makes
# the one orderable number 23065A855-23065A4 (Class Z listing, read 2026-11-01;
# the suffix changes with size: .3995 -7759N446, .4005 -7759N73).
SKU = "23065A855"
QUANTITY = 1
CONFIGURED_SKU = "23065A855-23065A4"
DIA = 10.16  # .4000
DIA_BAND = (0.0, -0.00254)  # upper, lower deviations, mm: -.0001/0
SUPPLY_LENGTH = 50.8  # page-stated 2 in
BOND = "Loctite 638"
# The factory top above the actual riser, set with a .080 gauge: inside the
# strap's thickness at both ends of its band.
TIP_SET = 2.032  # .080
TIP_SET_BAND = 0.2032  # +/-.008
CUT_PLACES = 2
# Owner-approved shop cut, not a supplier length: the carrier, the riser and
# the tip set, on the .01 grid (.79).
CUT_LENGTH = trammel.CARRIER_THICK + trammel.RISER_THICK + TIP_SET
LENGTH = CUT_LENGTH
_cut_in = CUT_LENGTH / trammel.INCH
if abs(_cut_in - round(_cut_in, CUT_PLACES)) > 1e-9:
    raise AssertionError("the hub pin cut length is off its printed .XX grid")
if not CUT_LENGTH < SUPPLY_LENGTH:
    raise AssertionError("the hub pin cut length exceeds the 2 in supply")

SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierPinDiameter", DIA, "horizontal"),
    ("SupplierCutLength", CUT_LENGTH, "vertical"),
)
# Both carriers lie on Top-view edges, so their construction lines print under
# the outline: the diameter on the z = CUT_LENGTH end face (the view's lower
# edge), the cut length on the OD silhouette. The Front (end) view shows no
# chord across the pin.
SUPPLIER_REFERENCE_STARTS = {
    "SupplierPinDiameter": (-DIA / 2.0, -CUT_LENGTH),
    "SupplierCutLength": (DIA / 2.0, -CUT_LENGTH),
}
SUPPLIER_REFERENCE_PLANES = {"SupplierPinDiameter": "Top", "SupplierCutLength": "Top"}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierPinDiameter": (4, "diameter", None, "GAUGE PIN"),
    "SupplierCutLength": (CUT_PLACES, "length", None, "CUT LENGTH"),
}
# Diameter text shelves right of its bottom lane; the cut length sits right of the Top view.
SUPPLIER_REFERENCE_SIDES = {"SupplierPinDiameter": "bottom", "SupplierCutLength": "right"}
SUPPLIER_REFERENCE_UNITS = {"SupplierPinDiameter": "in", "SupplierCutLength": "in"}
SUPPLIER_REFERENCE_TOLERANCES_MM: dict[str, tuple[float, float]] = {}
# Requirements live in the registry installation note; no supplier data lines.
SUPPLIER_DATA: tuple[str, ...] = ()
