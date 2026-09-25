"""Purchased-data contract for McMaster-Carr 9432K31.

This module is pure Python data: catalogue geometry comes from the verified
supplier-geometry module, the installed length comes from the actual mount
pose, and force values come from the purchased part row.  Lengths are catalogue
inside-hook measurements, never coil-body or eye-centre distances.
"""

from __future__ import annotations

import _config
import channel_spring_stock_geom as stock
from spring_mount_geom import (
    CHANNEL_INITIAL_TENSION_N,
    CHANNEL_NOMINAL_POSE,
    CHANNEL_RATE_N_PER_MM,
)


_PART = _config.parts("channel-spring-installed")

FREE_LENGTH_MM = stock.FREE_LENGTH_MM
MAX_LENGTH_MM = stock.MAX_LENGTH_MM
INSTALLED_LENGTH_MM = stock.check_length_mm(CHANNEL_NOMINAL_POSE.length_mm)
SPRING_RATE_N_PER_MM = CHANNEL_RATE_N_PER_MM
INITIAL_TENSION_N = CHANNEL_INITIAL_TENSION_N
MAXIMUM_LOAD_N = float(_PART["maximum_load_n"])

# Supplier-stated scatter.  This is catalogue acceptance data, not the tighter
# 20-spring common-set matching requirement used by the analyzer.
SPRING_RATE_TOLERANCE_FRACTION = float(_PART["spring_rate_tolerance_fraction"])
# The SET QC matching limit: each spring's rate within this percentage of the
# common set mean.  It is also the error budget's spring_rate allocation, read
# from here by error_budget.load_budget, so there is one source.  It lives in
# this module, not in parts/channel-spring-installed.yaml: counter_spring reads
# that yaml too, so a budget-driven edit there would re-key it as well.
MATCHED_SET_RATE_TOLERANCE_PCT = 1.25
INITIAL_TENSION_TOLERANCE_N = float(_PART["initial_tension_tolerance_n"])
