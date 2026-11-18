r"""Pure 23065A503 gauge-pin dimensions; isolate this SKU's cache inputs.

McMaster 23065A503: Class Z plug gauge, tool steel, no-go (minus), any size
from 0.0110 to 0.0605 in in 0.0005 in increments, size tolerance -0.0001 to 0
in, 2 in long, 8 uin RMS, Rockwell C60, ASME B89.1.5, $7.50 each
(https://www.mcmaster.com/23065A503/, read live 2026-11-12). The size ordered
is ``SIZE``; the 2 in pin is cut to ``CUT_LENGTH`` (a cut-to-length bought
item stays a vendor part). No vendor model was fetched.
"""

MM_PER_IN = 25.4

PART_NO = "23065A503"
SIZE_STEP = 0.0005 * MM_PER_IN
SIZE_RANGE = (0.0110 * MM_PER_IN, 0.0605 * MM_PER_IN)
SIZE = 0.0375 * MM_PER_IN  # the size ordered
SIZE_BAND_IN = (-0.0001, 0.0)  # minus pin, the catalogue's
SUPPLIED_LENGTH = 2.0 * MM_PER_IN
CUT_LENGTH = 0.28 * MM_PER_IN
PRICE_EACH_USD = 7.50
