"""Pure McMaster 90231A116 catalogue and conforming washer size bounds.

Brass SAE washer for No. 8 screw size, read live 2026-11-13 on the product
page and its SAE-washer family table: ID 0.188 in, OD 0.438 in, thickness
0.036 to 0.065 in, washer designation SAE, $10.52 per pack of 50. The page
gives no ID or OD tolerance rows. Its SAE claim matches ASME B18.21.1-2009
Table 11's No. 8 Type A plain washer (same basic ID, OD and thickness range),
whose tolerances bound the sizes here. Section 4.5 caps OD-to-ID runout at the
ID tolerance; like 96659A104 it is taken as a FULL radial offset.

The product page's STEP (SHA-256
``f7576b1941ead483c984bd6fec843654a92f03275068c16c1808a40413ac15d1``),
downloaded 2026-11-13 and measured headlessly with OCP, is one solid: a
Ø0.1880 x Ø0.4380 in annulus 0.0650 in thick (the range's maximum) with
torus-rounded rims. It is evidence only; no copy is kept in the repo.
"""

from _mcmaster_96659a104 import WasherDimensions

MM_PER_IN = 25.4

CATALOG_URL = "https://www.mcmaster.com/90231A116/"
CATALOG_CHECKED_DATE = "2026-11-13"
CATALOG_PRICE = "$10.52 per pack of 50"
CATALOG_PACKAGE_QTY = 50
CATALOG_STANDARD = "SAE"
CATALOG_DIAMETER_TOLERANCES = None  # Separate ID/OD bands omitted in SKU table.
BOUND_SOURCE_URL = "https://ssmalloys.com/wp-content/uploads/2024/10/ASME-B18.21.1.pdf"
BOUND_SOURCE = "ASME B18.21.1-2009 Table 11, No. 8 Type A; section 4.5"
# Table 11: ID .188 +.008/-.005, OD .438 +.015/-.005, thickness .036..065 in.
DIMS = WasherDimensions(
    part_no="90231A116",
    id=0.188 * MM_PER_IN,  # 4.7752
    od=0.438 * MM_PER_IN,  # 11.1252
    thickness_min=0.036 * MM_PER_IN,  # 0.9144
    thickness_max=0.065 * MM_PER_IN,  # 1.651
    id_min=0.183 * MM_PER_IN,  # 4.6482
    id_max=0.196 * MM_PER_IN,  # 4.9784
    od_min=0.433 * MM_PER_IN,  # 10.9982
    od_max=0.453 * MM_PER_IN,  # 11.5062
    od_id_runout_max=0.013 * MM_PER_IN,  # 0.3302
)
