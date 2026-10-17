r"""Pure 91812A215 wedge-lock washer dimensions; isolate this SKU's cache inputs.

McMaster 91812A215: Extreme-Vibration-Resistant Wedge Lock Washer, a
two-piece lock washer (serrations outside bite the screw head and the seat,
wedges inside lock the two halves together), reusable up to fifteen times,
"comparable to NORD-LOCK". 316 stainless steel, Rockwell C51, case hardened,
for No. 8 / M4 screws.

SOURCED, https://www.mcmaster.com/91812A215/ read live 2026-10-17 from the
No. 8 wedge-lock listing's spec table (the product detail page and its 2-D
PDF are login-walled): ID 0.170 in, OD 0.300 in, thickness 0.080 to 0.100 in,
5 per package, $11.71 per package.

UNVERIFIED (the listing does not say): whether the 0.080 to 0.100 in
thickness is the pair's stack or one washer's, and whether a package of 5 is
five pairs or five single washers. The model takes the band as the pair's
stack and models the pair at its 0.100 in maximum, the worst case for the
screw's engagement and its head's stand-out. No ID/OD tolerance is listed:
the model is the nominal annulus.

No vendor model was downloaded (the product page is login-walled), so there
is no replica gate and no copy in the repo.
"""

from __future__ import annotations

PART_NO = "91812A215"
IN = 25.4
CATALOG_URL = "https://www.mcmaster.com/91812A215/"
CATALOG_CHECKED_DATE = "2026-10-17"
CATALOG_MATERIAL = "316 stainless steel, Rockwell C51, case hardened"
# The catalogue's screw size, as the C4 fastener table prints the screw.
SCREW_SIZE = "#8"
PACKAGE_QTY = 5  # UNVERIFIED: five pairs or five single washers
PACKAGE_PRICE_USD = 11.71

ID = 0.170 * IN  # 4.318
OD = 0.300 * IN  # 7.62
THICKNESS_MIN = 0.080 * IN  # 2.032, UNVERIFIED: taken as the pair's stack
THICKNESS_MAX = 0.100 * IN  # 2.54
# The modelled pair: the band's maximum (worst case for engagement).
PAIR_THICKNESS = THICKNESS_MAX
