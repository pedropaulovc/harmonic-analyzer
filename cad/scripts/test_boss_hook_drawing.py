"""Offline manufacturing boundaries for the modified purchased anchor."""

import math
from types import SimpleNamespace

import pytest

import boss_hook_spec as spec
import draw_boss_hook as drawing
from _hole_spec import TAP_DRILL_MM
from stock_anchor_geom import ANCHOR_9490T1 as anchor


def test_finished_overall_preserves_factory_thread_datum():
    cut_end = anchor.eye_od_mm / 2 - spec.FINISHED_OVERALL_MM
    assert cut_end == pytest.approx(spec.TRIM.shank_end_y_mm)
    assert spec.TRIM.shank_length_mm == pytest.approx(19.05)
    assert spec.FINISHED_OVERALL_MM == pytest.approx(36.6395)


def test_deburr_band_clears_receiver_and_retains_full_threads():
    minimum = spec.CHAMFER_WIDTH_MM - spec.CHAMFER_WIDTH_TOLERANCE_MM
    maximum = spec.CHAMFER_WIDTH_MM + spec.CHAMFER_WIDTH_TOLERANCE_MM
    assert anchor.thread_major_dia_mm - 2 * minimum < TAP_DRILL_MM[anchor.thread_size]
    # Include the adverse angular corner, not only the nominal 45-degree leg.
    maximum_axial = maximum / math.tan(math.radians(spec.CHAMFER_ANGLE_DEG - spec.CHAMFER_ANGLE_TOLERANCE_DEG))
    short_shank = spec.SHANK_LENGTH_MM - spec.FINISHED_OVERALL_TOLERANCE_MM
    assert short_shank - maximum_axial > 17.0


@pytest.mark.parametrize("fault", ["reference", "nominal", "tolerance", "missing"])
def test_drawing_rejects_lost_manufacturing_control(monkeypatch, fault):
    """A source/drawing import regression must fail before exporting a shop print."""
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, annotation: annotation.name)
    annotations = []
    for name, nominal, band in (
        ("FinishedOverall", spec.FINISHED_OVERALL_MM / 1000, spec.FINISHED_OVERALL_TOLERANCE_MM / 1000),
        ("ChamferWidth", spec.CHAMFER_WIDTH_MM / 1000, spec.CHAMFER_WIDTH_TOLERANCE_MM / 1000),
        ("ChamferAngle", math.radians(spec.CHAMFER_ANGLE_DEG), math.radians(spec.CHAMFER_ANGLE_TOLERANCE_DEG)),
    ):
        tolerance = SimpleNamespace(Type=4, GetMinValue=lambda band=band: -band, GetMaxValue=lambda band=band: band)
        dimension = SimpleNamespace(DrivenState=2, SystemValue=nominal, Tolerance=tolerance)
        display = SimpleNamespace(GetDimension2=lambda _configuration, dimension=dimension: dimension, GetText=lambda _index: "")
        annotations.append(SimpleNamespace(name=name, dimension=dimension, GetSpecificAnnotation=lambda display=display: display))
    if fault == "reference":
        annotations[0].dimension.DrivenState = 1
    elif fault == "nominal":
        annotations[0].dimension.SystemValue += 0.001
    elif fault == "tolerance":
        annotations[0].dimension.Tolerance.Type = 0
    else:
        annotations.pop()
    with pytest.raises(RuntimeError):
        drawing._verify_controls(None, annotations)
