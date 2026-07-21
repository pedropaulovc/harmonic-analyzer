"""Offline contracts for the clamp-screw drawing."""

from __future__ import annotations

from pathlib import Path

import build_clamp_screw as part
import clamp_screw_spec as spec
import draw_clamp_screw as drawing
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import fastener


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/clamp-screw.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/clamp-screw.pdf")
    assert drawing.PNG.as_posix().endswith("/png/clamp-screw_drawing.png")
    assert DRAWINGS_BY_NAME["clamp_screw"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) == marked


def test_catalog_is_the_single_source_of_the_thread() -> None:
    catalog = fastener("clamp-screw")
    assert spec.THREAD == catalog.thread
    assert spec.SHANK_DIA == catalog.model_diameter_mm
    assert spec.SHANK_LEN == catalog.length_mm
    assert spec.THREAD_DESIGNATION == f"{catalog.thread} UNC-2A"
    assert spec.THREAD_DESIGNATION in spec.DRAWING_NOTES
    assert drawing.DIMENSION_CALLOUTS == {}
    assert "FULL THREAD" in spec.DRAWING_NOTES


def test_lengths_are_inserted_from_named_model_dimensions() -> None:
    assert set(drawing.SIDE_KEEP) == {"HeadHt", "ShankLg"}


def test_made_part_note_states_standards_conformance() -> None:
    notes = spec.DRAWING_NOTES
    assert "ASME B1.1" in notes
    assert "1.2 WIDE X 1.0 DEEP" in notes
    assert "COMMERCIAL" not in notes
    assert "DEBURR" not in notes and "BREAK SHARP" not in notes


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "mark_dimensions=DRAWING_DIMENSIONS" in source
    assert "drawing_properties=" in source
    import _config

    config = _config.parts("clamp-screw")
    assert config["number"] == "MHA-107"
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 6
