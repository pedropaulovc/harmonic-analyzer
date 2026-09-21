"""Offline contracts for the through-hub crankshaft drawing."""

from __future__ import annotations

from pathlib import Path

import pytest

import build_crankshaft as part
import crank_hub_geometry as geometry
import crankshaft_spec as spec
import draw_crankshaft as drawing
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crankshaft.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crankshaft.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crankshaft_drawing.png")
    assert DRAWINGS_BY_NAME["crankshaft"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert marked == {
        "ShaftDiaDim",
        "Depth",
        "DomeHeight",
        "JournalStart",
        "JournalDiaDim",
        "JournalLength",
    }
    assert drawing.DIMENSION_CALLOUTS == {}


def test_face_shift_preserves_every_inboard_world_station() -> None:
    assert spec.SHAFT_LENGTH == 130.0
    assert spec.JOURNAL_START == pytest.approx(40.755105572)
    assert spec.JOURNAL_END == pytest.approx(112.789505572)
    assert spec.JOURNAL_LENGTH == pytest.approx(72.0344)
    assert -183.0 + spec.JOURNAL_START == pytest.approx(-142.244894428)
    assert -183.0 + spec.JOURNAL_END == pytest.approx(-70.210494428)
    assert part.SEAT_T12 == pytest.approx(25.5)
    assert part.SEAT_PINION == pytest.approx(113.039505572)
    assert not hasattr(part, "SEAT_ARM")
    assert -183.0 + part.SEAT_T12 == pytest.approx(-157.5)
    assert -183.0 + part.SEAT_PINION == pytest.approx(-69.960494428)
    assert -183.0 + spec.SHAFT_LENGTH == pytest.approx(-53.0)


def test_integral_dome_is_the_only_outboard_shaft_projection() -> None:
    assert spec.SHAFT_DIA == geometry.SHAFT_DIA == 9.525
    assert spec.SHAFT_DOME_HEIGHT == geometry.SHAFT_DOME_HEIGHT == 2.0
    assert geometry.SHAFT_DIA + geometry.SHAFT_DIA_BAND[0] < (
        geometry.HUB_BORE_DIA + geometry.HUB_BORE_BAND[1]
    )
    assert "ONLY INTEGRAL DOME PROJECTS" in spec.CRANK_END_NOTE
    assert "MHA-020/MHA-137" in spec.CRANK_END_NOTE


def test_mha024_station_and_notes_belong_to_hub_and_shaft() -> None:
    assert part.PIN_HOLE_SPEC is spec.PIN_HOLE_SPEC
    assert drawing.PIN_HOLE_SPEC is spec.PIN_HOLE_SPEC
    assert drawing._PIN_HOLE_DIA == blind_cut_dia_mm(spec.PIN_HOLE_SPEC)
    assert spec.PIN_HOLE_HEIGHT == geometry.SERVICE_PIN_STATION == 12.0
    notes = spec.DRAWING_NOTES
    assert "CRANK HUB MHA-137" in notes
    assert "MHA-024" in notes
    assert "FINISHED SIZE FOR THIS PART" in notes
    assert "CRANK ARM MHA-020" not in notes


def test_shaft_end_fiducial_is_a_simple_punch_not_a_dimensioned_dimple() -> None:
    assert spec.FIDUCIAL_MODEL_DIA == geometry.FIDUCIAL_MODEL_DIA == 0.8
    assert spec.FIDUCIAL_MODEL_DEPTH == geometry.FIDUCIAL_MODEL_DEPTH == 0.2
    assert spec.SHAFT_FIDUCIAL_RADIUS == geometry.SHAFT_FIDUCIAL_RADIUS == 2.5
    assert "PUNCH FIDUCIAL MARK" in spec.DRAWING_NOTES
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert all("Fiducial" not in name for name in marked)
    assert "DIMPLE" not in spec.DRAWING_NOTES


def test_side_view_references_stations_from_cylinder_face_not_dome_tip() -> None:
    expected_tip = drawing.RIGHT_CENTER[1] - (
        spec.SHAFT_LENGTH + spec.SHAFT_DOME_HEIGHT
    ) / 2000.0
    assert drawing._OUTBOARD_TIP_Y == pytest.approx(expected_tip)
    assert drawing._CYLINDER_FACE_Y == pytest.approx(
        expected_tip + spec.SHAFT_DOME_HEIGHT / 1000.0
    )
    assert drawing._PIN_CENTER[1] == pytest.approx(
        drawing._CYLINDER_FACE_Y + spec.PIN_HOLE_HEIGHT / 1000.0
    )


def test_journal_fit_and_surface_finish_remain_unchanged() -> None:
    assert spec.JOURNAL_BORE_DIA == 11.438
    assert spec.JOURNAL_CLEARANCE == 0.05
    assert spec.JOURNAL_DIA == 11.388
    assert spec.JOURNAL_DIA_BAND == (0.0, -0.02)
    assert spec.SURFACE_FINISHES[0].production_method == "BEARING JOURNAL"
    assert "0.05 DIAMETRAL CLEARANCE" in spec.DRAWING_NOTES
    assert "KEEP DIA 9.525" in spec.DRAWING_NOTES


def test_view_scales_and_linked_notes_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    assert drawing.END_VIEW_SCALE == 2.0
    assert drawing.ISO_CENTER == (0.345, 0.197)
    assert spec.END_VIEW_NOTE == "CRANK-END VIEW SCALE 2:1"


def test_part_registry_retains_make_critical_properties() -> None:
    import _config

    config = _config.parts("crankshaft")
    assert config["material"] == config["material_specification"]
    assert "1018" in str(config["material_specification"])
    assert config["finish"]
    assert int(config["quantity"]) == 1
