"""Offline contracts for the slotted-screw drawing."""

from __future__ import annotations

from pathlib import Path

import build_slotted_screw as part
import draw_slotted_screw as drawing
import slotted_screw_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import fastener


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/slotted-screw.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/slotted-screw.pdf")
    assert drawing.PNG.as_posix().endswith("/png/slotted-screw_drawing.png")
    assert DRAWINGS_BY_NAME["slotted_screw"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    # Head-end view carries the diameters, side view the two lengths.
    assert set(drawing.END_KEEP) == set().union(*spec.END_VIEW_DIMENSIONS.values())
    assert set(drawing.SIDE_KEEP) == set().union(*spec.SIDE_VIEW_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) == marked
    assert spec.END_VIEW_DIMENSIONS.keys() | spec.SIDE_VIEW_DIMENSIONS.keys() == (
        spec.DRAWING_DIMENSIONS.keys()
    )


def test_catalog_is_the_single_source_of_the_thread() -> None:
    catalog = fastener("slotted-screw")
    assert spec.THREAD == catalog.thread
    assert spec.SHANK_DIA == catalog.model_diameter_mm
    assert spec.SHANK_LEN == catalog.length_mm
    assert spec.THREAD_DESIGNATION == f"{catalog.thread} UNC-2A"
    assert spec.THREAD_DESIGNATION in spec.DRAWING_NOTES
    assert drawing.DIMENSION_CALLOUTS == {}


def test_lengths_are_marked_extrude_depth_model_dims() -> None:
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name_dimensions(adapter, "Head", ["HeadHt"])' in part_source
    assert 'name_dimensions(adapter, "Shank", ["ShankLg"])' in part_source
    assert spec.SIDE_VIEW_DIMENSIONS == {"Head": {"HeadHt"}, "Shank": {"ShankLg"}}
    draw_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'keep=SIDE_KEEP, view_label="side"' in draw_source


def test_made_part_note_completely_defines_thread_and_slot() -> None:
    notes = spec.DRAWING_NOTES
    assert "FULL THREAD" in notes
    assert "1.2 WIDE X 1.0 DEEP" in notes
    assert "COMMERCIAL" not in notes
    assert "DEBURR" not in notes and "BREAK SHARP" not in notes


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("slotted-screw")
    assert config["number"] == "MHA-101"
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 4
