"""Offline contracts for the gooseneck-set-screw drawing."""

from __future__ import annotations

from pathlib import Path

import build_gooseneck_set_screw as part
import draw_gooseneck_set_screw as drawing
import gooseneck_set_screw_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import DriveStyle, HeadStyle, fastener


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/gooseneck-set-screw.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/gooseneck-set-screw.pdf")
    assert drawing.PNG.as_posix().endswith("/png/gooseneck-set-screw_drawing.png")
    assert DRAWINGS_BY_NAME["gooseneck_set_screw"].script == (
        Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    # The wrench-flats end view carries the across-flats width, the side view
    # the two lengths; together they cover exactly the marked set.
    assert set(drawing.END_KEEP) == set().union(*spec.END_VIEW_DIMENSIONS.values())
    assert set(drawing.SIDE_KEEP) == set().union(*spec.SIDE_VIEW_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) == marked
    assert spec.END_VIEW_DIMENSIONS.keys() | spec.SIDE_VIEW_DIMENSIONS.keys() == (
        spec.DRAWING_DIMENSIONS.keys()
    )


def test_catalog_is_the_single_source_of_the_thread() -> None:
    catalog = fastener("gooseneck-set-screw")
    assert spec.THREAD == catalog.thread == "1/4-20"
    assert spec.SHANK_DIA == catalog.model_diameter_mm
    assert spec.SHANK_LEN == catalog.length_mm
    assert spec.THREAD_DESIGNATION == f"{catalog.thread} UNC-2A"
    assert spec.THREAD_DESIGNATION in spec.DRAWING_NOTES
    assert drawing.DIMENSION_CALLOUTS == {}


def test_catalog_row_is_the_period_square_head_black_screw() -> None:
    # Book p.45 spec, reused from the deleted gooseneck-clamp's screw: square
    # head, wrench-driven, black oxide.
    catalog = fastener("gooseneck-set-screw")
    assert catalog.head is HeadStyle.SQUARE
    assert catalog.drive is DriveStyle.EXTERNAL_SQUARE
    assert catalog.finish == "black"


def test_contract_geometry_matches_the_top_frame_rederive() -> None:
    # Top-frame contract: 1/4-20 x 16 under-head, square head 10 x 10 x 6.
    assert spec.SHANK_LEN == 16.0
    assert spec.HEAD_AF == 10.0
    assert spec.HEAD_H == 6.0


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


def test_made_part_note_defines_the_square_head_without_a_slot() -> None:
    notes = spec.DRAWING_NOTES
    assert "FULL THREAD" in notes
    assert "CUSTOM SQUARE HEAD 10.00 +/-0.10 ACROSS FLATS X 6.00 +/-0.10 HIGH." in notes
    assert "B18 HEAD DIMENSIONS DO NOT APPLY." in notes
    assert "DRIVER SLOT" not in notes  # wrench-driven period square head
    assert "COMMERCIAL" not in notes
    assert "DEBURR" not in notes and "BREAK SHARP" not in notes


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("gooseneck-set-screw")
    assert config["number"] == "MHA-118"
    assert config["material"] == config["material_specification"]
    assert "black oxide" in config["finish"]
    assert int(config["quantity"]) == 1
