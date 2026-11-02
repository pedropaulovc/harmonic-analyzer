"""Pure McMaster 94773A606 catalogue: 18-8 stainless shim, 1/8 ID x 1/4 OD x .005."""

from _mcmaster_96659a104 import WasherDimensions

MM_PER_IN = 25.4

CATALOG_URL = "https://www.mcmaster.com/94773A606/"
# Read live on the public family table ("Shims for Shortening Screw
# Shoulders", 18-8 stainless, for 1/8" diameter shoulder; owner-directed
# headed read, #2124); the product page is behind McMaster's login wall.
FAMILY_TABLE_URL = (
    "https://www.mcmaster.com/products/arbor-shims/shoulder-diameter~1-8/"
)
CATALOG_CHECKED_DATE = "2026-11-01"
CATALOG_MATERIAL = "18-8 stainless steel, Rockwell B70 min"
CATALOG_PACKAGE_QTY = 10
# Catalogue row: thickness 0.005 +/-0.0005 in; ID 1/8 in 0/+0.012; OD 1/4 in
# -0.005/+0.002; for No. 4 screw. No OD-to-ID runout is stated.
THICKNESS_NOMINAL = 0.005 * MM_PER_IN  # 0.127
DIMS = WasherDimensions(
    part_no="94773A606",
    # The model's bore is the band's middle: the catalogue's 1/8 is its floor,
    # line-on-line with the Ø.125 pin.
    id=(0.125 + 0.012 / 2.0) * MM_PER_IN,  # 3.3274
    od=0.25 * MM_PER_IN,  # 6.35
    thickness_min=0.0045 * MM_PER_IN,  # 0.1143
    thickness_max=0.0055 * MM_PER_IN,  # 0.1397
    id_min=0.125 * MM_PER_IN,  # 3.175
    id_max=0.137 * MM_PER_IN,  # 3.4798
    od_min=0.245 * MM_PER_IN,  # 6.223
    od_max=0.252 * MM_PER_IN,  # 6.4008
    od_id_runout_max=0.0,
)
if abs(DIMS.thickness - THICKNESS_NOMINAL) > 1e-9:
    raise AssertionError("94773A606's thickness band is not centred on .005 in")
