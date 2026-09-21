"""Offline manufacturing boundaries for the shortened purchased stud."""

import knife_hanger_stud_spec as spec
from _hole_spec import TAP_DRILL_MM
from diagnostics.diag_build_91247A720 import GB_MAJOR_R


def test_deburr_band_clears_the_receiving_tap_drill() -> None:
    minimum = spec.CHAMFER_WIDTH_MM - spec.CHAMFER_WIDTH_TOLERANCE_MM
    tap_drill = TAP_DRILL_MM["1/2-13"]
    assert 2.0 * (GB_MAJOR_R - minimum) < tap_drill


