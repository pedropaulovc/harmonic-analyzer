"""Pure McMaster 3088A429 catalogue: carbon-steel ring shim, 1/4 ID x 3/8 OD x 0.031."""

from _mcmaster_96659a104 import WasherDimensions

MM_PER_IN = 25.4

CATALOG_URL = "https://www.mcmaster.com/3088A429/"
# Read live on the family table (round shims, carbon steel, 1/4" ID x 3/8"
# OD rows): the product page renders no spec table to a scraper.
FAMILY_TABLE_URL = "https://www.mcmaster.com/products/shims/shims-1~~/"
CATALOG_CHECKED_DATE = "2026-10-15"
CATALOG_MATERIAL = "Carbon steel, Rockwell B65 min"
CATALOG_PACKAGE_QTY = 10
# Catalogue row: thickness 0.031 +/-0.002 in; ID 1/4 in 0/+0.011; OD 3/8 in
# +/-0.002. No OD-to-ID runout is stated.
ID_NOMINAL = 0.25 * MM_PER_IN  # 6.35, the floor of the ID band
THICKNESS_NOMINAL = 0.031 * MM_PER_IN  # 0.7874
DIMS = WasherDimensions(
    part_no="3088A429",
    # The model's bore is the band's middle: the catalogue's 1/4 is its floor,
    # which would sit line-on-line with the Ø6.35 shaft.
    id=(0.25 + 0.011 / 2.0) * MM_PER_IN,  # 6.48970
    od=0.375 * MM_PER_IN,  # 9.525
    thickness_min=0.029 * MM_PER_IN,  # 0.7366
    thickness_max=0.033 * MM_PER_IN,  # 0.8382
    id_min=0.25 * MM_PER_IN,  # 6.350
    id_max=0.261 * MM_PER_IN,  # 6.6294
    od_min=0.373 * MM_PER_IN,  # 9.4742
    od_max=0.377 * MM_PER_IN,  # 9.5758
    od_id_runout_max=0.0,
)
if abs(DIMS.thickness - THICKNESS_NOMINAL) > 1e-9:
    raise AssertionError("3088A429's thickness band is not centred on 0.031 in")
