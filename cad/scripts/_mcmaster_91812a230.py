r"""Pure 91812A230 wedge-lock washer dimensions; isolate this SKU's cache inputs.

McMaster 91812A230: Extreme-Vibration-Resistant Wedge Lock Washer, a
two-piece lock washer (serrations outside bite the screw head and the seat,
wedges inside lock the two halves together), reusable up to fifteen times,
"comparable to NORD-LOCK". 316 stainless steel, Rockwell C51, case hardened,
for 5/16" / M8 screws.

SOURCED, https://www.mcmaster.com/91812A230/ read live 2026-10-22:
5/16" / M8 screw size, ID 0.340 in, OD 0.530 in, thickness 0.070 to
0.090 in, 316 stainless steel, Rockwell C51, case hardened; $12.40 per
pack of 5. The product's explicit two-piece lock-washer definition makes
one supplied unit one complete pair, so the pack contains five pairs, not
five separate halves. The immutable product-text capture is recorded in
the McMaster reference README. The listing's other 5/16" row, 91812A430,
is the 0.650 in OD wide version: Ø16.51 over the two lever screws' 16
pitch, the pairs would overlap.

The engineering drawing inspected 2026-10-21 spans the complete two-piece
stack. The model keeps that stack at its 0.090 in maximum, the worst case
for the screw's engagement and its head's height. No ID/OD tolerance is
listed: the model is the nominal plain annulus, without the split, cams
or serrations.

No vendor model was downloaded, so there is no replica gate and no copy
in the repo.
"""

from __future__ import annotations

PART_NO = "91812A230"
IN = 25.4
CATALOG_URL = "https://www.mcmaster.com/91812A230/"
CATALOG_CHECKED_DATE = "2026-10-22"
CATALOG_MATERIAL = "316 stainless steel, Rockwell C51, case hardened"
# The catalogue's screw size, as the C4 fastener table prints the screw.
SCREW_SIZE = "5/16"
PACKAGE_QTY = 5  # complete two-piece washer pairs, not individual halves
PACKAGE_PRICE_USD = 12.40

ID = 0.340 * IN  # 8.636
OD = 0.530 * IN  # 13.462
THICKNESS_MIN = 0.070 * IN  # 1.778, complete pair's stack
THICKNESS_MAX = 0.090 * IN  # 2.286
# The modelled pair: the band's maximum (worst case for engagement).
PAIR_THICKNESS = THICKNESS_MAX
