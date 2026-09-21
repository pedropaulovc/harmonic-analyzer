"""Offline release contracts for separate through hub MHA-137."""

from __future__ import annotations

from pathlib import Path

import pytest

import _config
import crank_hub_geometry as geometry
import crank_hub_spec
import draw_crank_hub as drawing
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_outboard_proportions_are_scaled_not_millimetre_literals() -> None:
    scale = geometry.SHAFT_DIA / 1.65
    assert geometry.ARM_WIDTH == pytest.approx(3.14 * scale, abs=0.05)
    assert geometry.HUB_SEAT_DIA == pytest.approx(2.60 * scale, abs=0.02)
    assert geometry.AXIAL_PIN_DIA == pytest.approx(0.59 * scale, abs=0.01)


def test_named_shaft_fit_class_bounds_the_through_bore() -> None:
    shaft_limits = (
        geometry.SHAFT_DIA + geometry.SHAFT_DIA_BAND[1],
        geometry.SHAFT_DIA + geometry.SHAFT_DIA_BAND[0],
    )
    bore_limits = (
        geometry.HUB_BORE_DIA + geometry.HUB_BORE_BAND[1],
        geometry.HUB_BORE_DIA + geometry.HUB_BORE_BAND[0],
    )
    clearances = (bore_limits[0] - shaft_limits[1], bore_limits[1] - shaft_limits[0])
    assert clearances == pytest.approx(
        tuple(_config.fit("shaft_in_bushing", "diametral_clearance_mm"))
    )


def test_hub_shoulder_and_pin_stations_preserve_removal_topology() -> None:
    assert geometry.HUB_SEAT_LENGTH == geometry.ARM_THICKNESS
    assert geometry.HUB_SHOULDER_STATION < geometry.SERVICE_PIN_STATION
    assert geometry.SERVICE_PIN_STATION < geometry.HUB_LENGTH
    assert geometry.AXIAL_PIN_LENGTH == geometry.ARM_THICKNESS / 2.0


def test_drawing_registry_marks_and_model_fit_band_are_complete() -> None:
    assert DRAWINGS_BY_NAME["crank_hub"].script == Path(drawing.__file__).resolve()
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-hub.SLDDRW")
    marked = set().union(*crank_hub_spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= marked
    import build_crank_hub as hub

    assert model_toleranced_dimensions(hub) == {
        ("BoreProfile", "BoreDia"): geometry.HUB_BORE_BAND
    }


def test_matched_fit_and_distinct_pins_are_unambiguous() -> None:
    notes = crank_hub_spec.DRAWING_NOTES
    assert "MATCHED ASSEMBLY" in notes
    assert "MHA-138" in notes and "SIX O'CLOCK" in notes
    assert "MHA-024" in notes and "MHA-026" in notes
    assert "RADIAL" not in notes
    assert "SHOULDER SEATED" in notes and "FACES FLUSH" in notes
    assert "0.50 MIN HUB WALL" in notes and "AFTER EDGE BREAK" in notes
