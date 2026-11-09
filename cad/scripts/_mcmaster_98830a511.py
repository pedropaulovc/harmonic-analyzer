"""Pure 98830A511 key-stock dimensions; isolate this SKU's cache inputs.

McMaster "1008-1045 Carbon Steel Machine Key Stock, 12" Long, 1/16" High x
1/16" Wide, Undersized", read live from the product page
(https://www.mcmaster.com/98830A511/) and its family table
(https://www.mcmaster.com/products/keys/width~1-16-1/) on 2026-11-09:
straight key stock, 1008-1045 carbon steel, 12 in long, 1/16 x 1/16 in,
tolerance rating Undersized: height and width -0.002 to 0.000 in, length
-0.125 to 0.000 in; Rockwell B50 minimum; $0.47 each.  The page states no
edge form; no vendor model was fetched, so the recipe is the plain nominal
square bar.
"""

PART_NO = "98830A511"
IN = 25.4

# Height = width: the square section, and its (upper, lower) deviations.
SIZE = IN / 16.0
SIZE_BAND = (0.0, -0.002 * IN)
# The supplied bar, cut to length at assembly.
LENGTH = 12.0 * IN
LENGTH_BAND = (0.0, -0.125 * IN)
