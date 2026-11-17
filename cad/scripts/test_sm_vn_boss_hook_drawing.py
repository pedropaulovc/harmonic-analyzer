"""Offline manufacturing boundaries for the modified purchased anchor."""

import math

import pytest

from _printed_tolerance import printed_band_mm
import sm_vn_boss_hook_spec as spec
from _hole_spec import TAP_DRILL_MM
from stock_anchor_geom import ANCHOR_9490T1 as anchor


def test_finished_overall_preserves_factory_thread_datum():
    cut_end = anchor.eye_od_mm / 2 - spec.FINISHED_OVERALL_MM
    assert cut_end == pytest.approx(spec.TRIM.shank_end_y_mm)
    # The full 19.05 boss plus the eye's stand-off above it, the calibrated
    # counter seat's station (#1189, #2326): nothing moved with the nut.
    assert spec.TRIM.shank_length_mm == pytest.approx(22.886)
    assert spec.TRIM.shank_length_mm - 19.05 == pytest.approx(spec.EYE_STANDOFF_MM)
    assert spec.FINISHED_OVERALL_MM == pytest.approx(40.4755)


def test_deburr_band_clears_receiver_and_retains_full_threads():
    # The lead-in is a two-place inch chamfer under the printed .XX title-block
    # band, never a tighter one; the governing stack below must hold across it.
    band = printed_band_mm(2, unit="in")
    assert spec.CHAMFER_WIDTH_DEVIATIONS == pytest.approx((-band, band))
    assert spec.DIMENSION_PRECISION["ChamferWidth"] == 2
    assert spec.CHAMFER_WIDTH_MM / 25.4 == pytest.approx(
        round(spec.CHAMFER_WIDTH_MM / 25.4, 2)
    )
    assert spec.DIMENSION_TOLERANCE_TYPES["ChamferWidth"] == 11  # swTolGeneral
    minimum = spec.CHAMFER_WIDTH_MM + spec.CHAMFER_WIDTH_DEVIATIONS[0]
    maximum = spec.CHAMFER_WIDTH_MM + spec.CHAMFER_WIDTH_DEVIATIONS[1]
    assert anchor.thread_major_dia_mm - 2 * minimum < TAP_DRILL_MM[anchor.thread_size]
    # The next two-place nominal down would put the short leg's end over the drill.
    assert (
        anchor.thread_major_dia_mm - 2 * (minimum - 0.254)
        >= TAP_DRILL_MM[anchor.thread_size]
    )
    # The long leg still leaves an end flat: the deburr cannot reach the axis.
    assert anchor.thread_major_radius_mm - maximum > 0.2
    # Include the adverse angular corner, not only the nominal 45-degree leg.
    maximum_axial = maximum / math.tan(
        math.radians(spec.CHAMFER_ANGLE_DEG - spec.CHAMFER_ANGLE_TOLERANCE_DEG)
    )
    short_shank = spec.SHANK_LENGTH_MM + spec.FINISHED_OVERALL_DEVIATIONS[0]
    assert short_shank - maximum_axial > 17.0


def test_finished_overall_prints_its_model_inside_the_xx_band():
    lower, upper = spec.FINISHED_OVERALL_DEVIATIONS
    assert spec.DIMENSION_PRECISION["FinishedOverall"] == 2
    assert lower < 0.0 < upper
    assert upper - lower == pytest.approx(2 * printed_band_mm(2, unit="in"))
