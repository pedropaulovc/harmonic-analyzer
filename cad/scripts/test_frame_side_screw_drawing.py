"""Offline contracts for the frame-side-screw drawing."""

from __future__ import annotations

from pathlib import Path

import build_frame_side_screw as part
import draw_frame_side_screw as drawing
import frame_side_screw_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import fastener


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/frame-side-screw.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/frame-side-screw.pdf")
    assert drawing.PNG.as_posix().endswith("/png/frame-side-screw_drawing.png")
    assert DRAWINGS_BY_NAME["frame_side_screw"].script == (
        Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    # The head-end view carries the head diameter, the side view the two
    # lengths; together they cover exactly the marked set.
    assert set(drawing.END_KEEP) == set().union(*spec.END_VIEW_DIMENSIONS.values())
    assert set(drawing.SIDE_KEEP) == set().union(*spec.SIDE_VIEW_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) == marked
    assert spec.END_VIEW_DIMENSIONS.keys() | spec.SIDE_VIEW_DIMENSIONS.keys() == (
        spec.DRAWING_DIMENSIONS.keys()
    )


def test_catalog_is_the_single_source_of_the_thread() -> None:
    catalog = fastener("frame-side-screw")
    assert spec.THREAD == catalog.thread == "#10-24"
    assert spec.SHANK_DIA == catalog.model_diameter_mm
    assert spec.SHANK_LEN == catalog.length_mm
    assert spec.THREAD_DESIGNATION == f"{catalog.thread} UNC-2A"
    assert spec.THREAD_DESIGNATION in spec.DRAWING_NOTES
    assert drawing.DIMENSION_CALLOUTS == {}


def test_contract_geometry_matches_the_top_frame_rederive() -> None:
    # Top-frame contract: #10-24 x 12.7 under-head, cheese head O7 x 3.
    assert spec.SHANK_LEN == 12.7
    assert spec.HEAD_DIA == 7.0
    assert spec.HEAD_H == 3.0


def test_lengths_are_marked_extrude_depth_model_dims() -> None:
    # The vertical (axis +Y) profile cannot point-select the edge-on
    # shoulder/tip silhouettes, so the two lengths ship as the head/shank
    # extrude-DEPTH model dimensions: the build names them, the drawing
    # inserts them in the side view.
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name_dimensions(adapter, "Head", ["HeadHt"])' in part_source
    assert 'name_dimensions(adapter, "Shank", ["ShankLg"])' in part_source
    assert spec.SIDE_VIEW_DIMENSIONS == {"Head": {"HeadHt"}, "Shank": {"ShankLg"}}
    draw_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "side_keep=SIDE_KEEP" in draw_source


def test_made_part_note_completely_defines_thread_and_slot() -> None:
    notes = spec.DRAWING_NOTES
    assert "FULL THREAD" in notes
    assert "DRIVER SLOT 1.40 +/-0.10 WIDE X 1.20 +/-0.10 DEEP" in notes
    assert "COMMERCIAL" not in notes
    assert "DEBURR" not in notes and "BREAK SHARP" not in notes


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("frame-side-screw")
    assert config["number"] == "MHA-117"
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    # 4 in frame.SLDASM (corner bosses) + 2 in channel.SLDASM (the fulcrum
    # keepers' foot screws into the rail top face, 2026-08-02 remount).
    assert int(config["quantity"]) == 6
