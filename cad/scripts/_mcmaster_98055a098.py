"""Pure McMaster 98055A098 catalogue: DIN 988 spring-steel shim, 5 x 10 x 0.5."""

from _mcmaster_96659a104 import WasherDimensions

CATALOG_URL = "https://www.mcmaster.com/98055A098/"
# Read live on the family table (DIN 988 shims, 0.5 mm, stress-resistant
# spring steel): https://www.mcmaster.com/products/din-988-shims/
# thickness~0-5-mm/shims-1~~/shims-4~performance~stress-resistant/
CATALOG_CHECKED_DATE = "2026-10-15"
CATALOG_STANDARD = "DIN 988"
CATALOG_MATERIAL = "Stress-resistant spring steel, Rockwell B85 min"
CATALOG_PACKAGE_QTY = 50
# Catalogue row: thickness 0.5 -0.05/0; ID 5 +0.03/+0.4; OD 10 -0.47/-0.04.
DIMS = WasherDimensions(
    part_no="98055A098",
    id=5.0,
    od=10.0,
    thickness_min=0.45,
    thickness_max=0.50,
    id_min=5.03,
    id_max=5.40,
    od_min=9.53,
    od_max=9.96,
    od_id_runout_max=0.0,
)
# The catalogue nominal (the thickness the stack is laid out on); DIMS.thickness
# is the band's middle.
THICKNESS_NOMINAL = 0.5
