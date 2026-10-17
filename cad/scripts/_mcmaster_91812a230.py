r"""Pure 91812A230 wedge-lock washer dimensions; isolate this SKU's cache inputs.

McMaster 91812A230: Extreme-Vibration-Resistant Wedge Lock Washer, a
two-piece lock washer (serrations outside bite the screw head and the seat,
wedges inside lock the two halves together), reusable up to fifteen times,
"comparable to NORD-LOCK". 316 stainless steel, Rockwell C51, case hardened,
for 5/16" / M8 screws.

SOURCED, https://www.mcmaster.com/products/washers/washer-type~wedge/ read
live 2026-10-17 from the wedge-lock listing's spec table (the product detail
page and its 2-D PDF are login-walled): 5/16" / M8 screw size, ID 0.340 in,
OD 0.530 in, thickness 0.070 to 0.090 in, 5 per package, $12.40 per
package. (The listing's other 5/16" row, 91812A430, is the 0.650 in OD
wide version: Ø16.51 over the two lever screws' 16 pitch, the pairs would
overlap.)

UNVERIFIED (the listing does not say): whether the 0.070 to 0.090 in
thickness is the pair's stack or one washer's, and whether a package of 5 is
five pairs or five single washers. The model takes the band as the pair's
stack and models the pair at its 0.090 in maximum, the worst case for the
screw's engagement and its head's height. No ID/OD tolerance is listed: the
model is the nominal annulus.

No vendor model was downloaded (the product page is login-walled), so there
is no replica gate and no copy in the repo.
"""

from __future__ import annotations

PART_NO = "91812A230"
IN = 25.4
CATALOG_URL = "https://www.mcmaster.com/91812A230/"
CATALOG_CHECKED_DATE = "2026-10-17"
CATALOG_MATERIAL = "316 stainless steel, Rockwell C51, case hardened"
# The catalogue's screw size, as the C4 fastener table prints the screw.
SCREW_SIZE = "5/16"
PACKAGE_QTY = 5  # UNVERIFIED: five pairs or five single washers
PACKAGE_PRICE_USD = 12.40

ID = 0.340 * IN  # 8.636
OD = 0.530 * IN  # 13.462
THICKNESS_MIN = 0.070 * IN  # 1.778, UNVERIFIED: taken as the pair's stack
THICKNESS_MAX = 0.090 * IN  # 2.286
# The modelled pair: the band's maximum (worst case for engagement).
PAIR_THICKNESS = THICKNESS_MAX
