"""Pure McMaster 3088A catalogue: carbon-steel ring shims, 12 mm ID x 18 mm OD.

Read on the metric round-shim family table (Carbon Steel heading) on
2026-10-15; the 3088A product pages render no spec table to a scraper and
their CAD download is refused, so the part is catalogue-only.  Every row
below shares the family's ID and OD tolerances; each carries its own
thickness tolerance.  The table's own fit-up advice: "You can stack multiple
shims to achieve your exact thickness, but stacking more than four may cause
them to shift."
"""

from _mcmaster_96659a104 import WasherDimensions

FAMILY_TABLE_URL = "https://www.mcmaster.com/products/shims/shims-1~~/"
# The filtered view that renders the 3088A006 row in full (re-read live,
# 2026-10-15): 12 mm ID x 18 mm OD, 0.1, -0.013 to 0.013, ID -0.3 to 0.3,
# OD -0.5 to 0.5, Rockwell B40, package of 5.
LIVE_ROW_URL = (
    "https://www.mcmaster.com/products/shims/shims-1~~/"
    "material~steel-2/system-of-measurement~metric/"
)
CATALOG_CHECKED_DATE = "2026-10-15"
CATALOG_MATERIAL = "Carbon steel, Rockwell B40 min"
# Family-table wording for the material.
CATALOG_MATERIAL_NOTE = (
    "Carbon Steel -- Best for dry environments since moisture will cause "
    "these shims to rust."
)
# "stacking more than four may cause them to shift"
CATALOG_STACK_MAX = 4

ID_NOMINAL = 12.0
OD_NOMINAL = 18.0
ID_TOLERANCE = (-0.3, 0.3)
OD_TOLERANCE = (-0.5, 0.5)
# SKU -> (thickness, +/- thickness tolerance), mm.
THICKNESS_ROWS: dict[str, tuple[float, float]] = {
    "3088A006": (0.1, 0.013),
    "3088A026": (0.2, 0.045),
    "3088A066": (0.5, 0.064),
    "3088A086": (1.0, 0.105),
    "3088A106": (1.5, 0.14),
    "3088A207": (2.0, 0.21),
}
SKUS = tuple(THICKNESS_ROWS)
THICKNESS_NOMINAL: dict[str, float] = {
    sku: thickness for sku, (thickness, _tol) in THICKNESS_ROWS.items()
}
SHIMS: dict[str, WasherDimensions] = {
    sku: WasherDimensions(
        part_no=sku,
        id=ID_NOMINAL,
        od=OD_NOMINAL,
        thickness_min=thickness - tol,
        thickness_max=thickness + tol,
        id_min=ID_NOMINAL + ID_TOLERANCE[0],
        id_max=ID_NOMINAL + ID_TOLERANCE[1],
        od_min=OD_NOMINAL + OD_TOLERANCE[0],
        od_max=OD_NOMINAL + OD_TOLERANCE[1],
        od_id_runout_max=0.0,  # none stated
    )
    for sku, (thickness, tol) in THICKNESS_ROWS.items()
}
# The bands are symmetric, so a model at DIMS.thickness is the catalogue
# nominal.
for _sku, _dims in SHIMS.items():
    if abs(_dims.thickness - THICKNESS_NOMINAL[_sku]) > 1e-12:
        raise AssertionError(f"{_sku} thickness band is not centred on its nominal")
