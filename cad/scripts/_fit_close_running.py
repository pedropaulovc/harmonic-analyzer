"""Measured close-running H7/g6 fit class, separate so retunes re-key only its users."""

from _fit_deviations import deviations
from _fit_ream_h7 import REAM_H7

# Fit classes: (upper, lower) offsets in mm, added to the nominal.
# ISO g6 ground shaft, 3-6 mm size range: -0.004 / -0.012.
# Source: Mitsubishi Materials shaft-fit table, >3 through 6 mm row (micrometres).
# https://www.mitsubishicarbide.net/contents/mhg/enuk/html/product/technical_information/information/pdf/fit_tolerance_table_shaft.pdf
SHAFT_G6_3_TO_6_MM = (-0.004, -0.012)


def measured_close_running_clearance_mm() -> tuple[float, float]:
    """H7/g6-equivalent diametral clearance for a bore matched to its shaft.

    This is a clearance class, not permission to replace a supplied shaft's
    size band. The owning part must measure that shaft and accept the bore
    between the measured size plus these limits; a model nominal is REF.
    """
    hole_lower, hole_upper = deviations(REAM_H7)
    shaft_lower, shaft_upper = deviations(SHAFT_G6_3_TO_6_MM)
    return hole_lower - shaft_upper, hole_upper - shaft_lower
