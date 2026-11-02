r"""Pure 91812A230 wedge-lock washer dimensions; isolate this SKU's cache inputs.

McMaster 91812A230: Extreme-Vibration-Resistant Wedge Lock Washer, a
two-piece lock washer (serrations outside bite the screw head and the seat,
wedges inside lock the two halves together), reusable up to fifteen times,
"comparable to NORD-LOCK". 316 stainless steel, Rockwell C51, case hardened,
for 5/16" / M8 screws.

SOURCED, https://www.mcmaster.com/products/washers/washer-type~wedge/ read
live 2026-10-17 and again 2026-11-01 from the wedge-lock listing's spec table
(the product detail page is login-walled): 5/16" / M8 screw size, ID 0.340
in, OD 0.530 in, thickness 0.070 to 0.090 in, package quantity 5, $17.39 per
package on 2026-11-01 ($12.40 on 2026-10-17). (The listing's other 5/16" row,
91812A430, is the 0.650 in OD wide version: Ø16.51 over the two lever screws'
16 pitch, the pairs would overlap.)

PAIR AND PACKAGE, read 2026-11-01: the listing sells "these two-piece lock
washers", one item being the two-piece washer, so a package of 5 is five
pairs. The 91812A230 engineering drawing (CAD2/20260617/385104C2, public)
dimensions the thickness 0.09/0.07 across the assembled two-piece stack, so
the thickness band is the pair's stack. The model takes the stack at its
0.090 in maximum, the worst case for the screw's engagement and its head's
height. No ID/OD tolerance is listed: the model is the nominal annulus.

No vendor model was downloaded (the product page is login-walled), so there
is no replica gate and no copy in the repo.
"""

from __future__ import annotations

PART_NO = "91812A230"
IN = 25.4
CATALOG_URL = "https://www.mcmaster.com/91812A230/"
CATALOG_CHECKED_DATE = "2026-11-01"
CATALOG_MATERIAL = "316 stainless steel, Rockwell C51, case hardened"
# The catalogue's screw size, as the C4 fastener table prints the screw.
SCREW_SIZE = "5/16"
PACKAGE_QTY = 5  # two-piece pairs per package
PACKAGE_PRICE_USD = 17.39

ID = 0.340 * IN  # 8.636
OD = 0.530 * IN  # 13.462
THICKNESS_MIN = 0.070 * IN  # 1.778, the pair's stack
THICKNESS_MAX = 0.090 * IN  # 2.286
# The modelled pair: the band's maximum (worst case for engagement).
PAIR_THICKNESS = THICKNESS_MAX
