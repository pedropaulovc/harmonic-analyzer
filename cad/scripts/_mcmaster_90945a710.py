r"""Pure 90945A710 flat washer dimensions; isolate this SKU's cache inputs.

McMaster 90945A710: 18-8 stainless steel flat washer to military
specification NAS620C4L, for No. 4 screws.

SOURCED, https://www.mcmaster.com/products/washers/screw-size~no-4/mil-spec-washers-2~~/
read live 2026-10-19 from the No. 4 Mil. Spec. listing's 18-8 stainless steel
row (the product detail page is login-walled): No. 4 screw size, ID 0.115 in,
OD 0.209 in, thickness 0.015 to 0.018 in, Mil. Spec. NAS620C4L, material
certificate, 500 per package, $21.94 per package. It is the smallest-OD steel
No. 4 washer the No. 4 washer listings offer (the next, 98029A024, is 0.250
in OD).

No ID/OD tolerance is listed: the model is the nominal annulus at the
thickness band's maximum, the worst case for the screw's engagement. No
vendor model was downloaded (the product page is login-walled), so there is
no replica gate and no copy in the repo.
"""

from __future__ import annotations

PART_NO = "90945A710"
IN = 25.4
CATALOG_URL = "https://www.mcmaster.com/90945A710/"
CATALOG_CHECKED_DATE = "2026-10-19"
CATALOG_MATERIAL = "18-8 stainless steel"
MIL_SPEC = "NAS620C4L"
# The catalogue's screw size, as the C4 fastener table prints the screw.
SCREW_SIZE = "#4"
PACKAGE_QTY = 500
PACKAGE_PRICE_USD = 21.94

ID = 0.115 * IN  # 2.921
OD = 0.209 * IN  # 5.3086
THICKNESS_MIN = 0.015 * IN  # 0.381
THICKNESS_MAX = 0.018 * IN  # 0.4572
