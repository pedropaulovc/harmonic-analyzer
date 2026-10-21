"""Purchased-data contract for McMaster-Carr 9432K31.

This module is pure Python data: catalogue geometry comes from the verified
supplier-geometry module, the installed length comes from the actual mount
pose, and force values come from the purchased part row.  Lengths are catalogue
inside-hook measurements, never coil-body or eye-centre distances.
"""

from __future__ import annotations

import _config
import ch_vn_channel_spring_stock_geom as stock
from spring_mount_geom import (
    CHANNEL_INITIAL_TENSION_N,
    CHANNEL_NOMINAL_POSE,
    CHANNEL_RATE_N_PER_MM,
)


_PART = _config.parts("ch-vn-channel-spring-installed")

FREE_LENGTH_MM = stock.FREE_LENGTH_MM
MAX_LENGTH_MM = stock.MAX_LENGTH_MM
INSTALLED_LENGTH_MM = stock.check_length_mm(CHANNEL_NOMINAL_POSE.length_mm)
SPRING_RATE_N_PER_MM = CHANNEL_RATE_N_PER_MM
INITIAL_TENSION_N = CHANNEL_INITIAL_TENSION_N
MAXIMUM_LOAD_N = float(_PART["maximum_load_n"])

# Supplier-stated scatter.  This is catalogue acceptance data, not the tighter
# 20-spring common-set matching requirement used by the analyzer.
SPRING_RATE_TOLERANCE_FRACTION = float(_PART["spring_rate_tolerance_fraction"])
INITIAL_TENSION_TOLERANCE_N = float(_PART["initial_tension_tolerance_n"])

# Inspected supplier drawing; these nominal gauges do not measure the installed pose.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260617/4210389D/"
    "9432K31_Music-Wire%20Steel%20Extension%20Springs%20with%20Hook%20EndsX.GIF"
)
SUPPLIER_PRECISION = {
    "SupplierFreeLength": 3,
    "SupplierMaximumLength": 3,
    "SupplierCoilOD": 2,
    "SupplierWireDiameter": 3,
}
SUPPLIER_COIL_OD_MM = stock.COIL_OD_MM
SUPPLIER_WIRE_DIA_MM = stock.WIRE_DIA_MM
SUPPLIER_COIL_OD_TOLERANCE_MM = 0.008 * 25.4
SUPPLIER_COIL_OD_TOLERANCE_PRECISION = 3
