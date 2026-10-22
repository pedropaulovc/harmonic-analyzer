"""Purchased-data contract for McMaster-Carr 1330K524.

Catalogue geometry comes from the verified supplier-geometry module.  The
illustrated installed length is the actual reference mount pose.  Every length
is the catalogue inside-loop measurement; the supplier display model's coil
count is never used to infer force or spring rate.
"""

from __future__ import annotations

import sm_vn_counter_spring_stock_geom as stock
from spring_mount_geom import (
    COUNTER_INITIAL_TENSION_N,
    COUNTER_MAXIMUM_LOAD_N,
    COUNTER_RATE_N_PER_MM,
    COUNTER_REFERENCE_POSE,
)


FREE_LENGTH_MM = stock.FREE_LENGTH_MM
MAX_LENGTH_MM = stock.MAX_LENGTH_MM
INSTALLED_LENGTH_MM = stock.validate_length_mm(COUNTER_REFERENCE_POSE.length_mm)
SPRING_RATE_N_PER_MM = COUNTER_RATE_N_PER_MM
INITIAL_TENSION_N = COUNTER_INITIAL_TENSION_N
MAXIMUM_LOAD_N = COUNTER_MAXIMUM_LOAD_N

# Source native maximum stays 421.6146 mm (16.599 in); only the print rounds to 16.60.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260501/24CCF480/"
    "1330K524_Extension%20SpringX.GIF"
)
SUPPLIER_PRECISION = {
    "SupplierFreeLength": 2,
    "SupplierMaximumLength": 2,
    "SupplierCoilOD": 3,
    "SupplierWireDiameter": 3,
}
SUPPLIER_COIL_OD_MM = stock.COIL_OD_MM
SUPPLIER_WIRE_DIA_MM = stock.WIRE_DIA_MM
