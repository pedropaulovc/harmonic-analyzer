"""Offline contracts for the frame-side-screw drawing.

A #10-24 cheese-head screw on the shared fastener recipe: no datums, frames,
roughness symbols or basic dimensions (cad/docs/drawing-simplicity-policy.md
rules 3-5) and three lines of note (rule 6).
"""

from __future__ import annotations

from pathlib import Path

import build_frame_side_screw as part
import draw_frame_side_screw as drawing
import frame_side_screw_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import fastener


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


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
    assert spec.THREAD_DESIGNATION == f"{catalog.thread} UNC"
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
    assert "side_keep=SIDE_KEEP" in _source()


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert max(map(len, lines)) < 80
    assert lines[0] == f"{spec.THREAD_DESIGNATION} THREADED TO THE HEAD; LAST 2 PITCHES MAY BE INCOMPLETE."
    assert f"SLOT {spec.SLOT_W:.2f} WIDE X {spec.SLOT_D:.2f} DEEP" in notes
    assert f"{spec.HEAD_DIA:.2f}" not in notes  # a dimension, not a note
    for banned in (
        "UOS",
        "DIMENSIONS IN",
        "+/-",
        "DATUM",
        "PERPENDICULAR",
        "RUNOUT",
        "ASME",
        "B18",
        "DEBURR",
        "BREAK SHARP",
        "TITLE BLOCK",
        "COMMERCIAL",
    ):
        assert banned not in notes, banned


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(spec, "SURFACE_FINISHES")
    # The view display (HLR on the tiny end view, kept deliberately) is the
    # shared recipe's, not this script's.
    assert "build_fastener_sheet(" in source
    assert drawing.RECIPE.decorate is None


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
