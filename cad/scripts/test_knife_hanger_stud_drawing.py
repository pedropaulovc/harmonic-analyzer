"""Offline manufacturing boundaries for the shortened purchased stud."""

import knife_hanger_stud_spec as spec
from _hole_spec import TAP_DRILL_MM
from diagnostics.diag_build_91247A720 import GB_MAJOR_R


def test_root_chamfer_flat_clears_the_receiving_tap_drill() -> None:
    tap_drill = TAP_DRILL_MM["1/2-13"]
    flat_diameter = 2.0 * (GB_MAJOR_R - spec.CHAMFER_WIDTH_MM)
    assert flat_diameter < tap_drill


