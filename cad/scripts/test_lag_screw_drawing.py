"""Offline contracts for the lag-screw drawing.

A 9/16-12 black-steel hold-down screw: no datums, frames, roughness symbols
or basic dimensions (cad/docs/drawing-simplicity-policy.md rules 3-5), three
lines of note (rule 6), hidden lines on in the profile (rule 7).
"""

from __future__ import annotations

from pathlib import Path

import build_lag_screw as part
import draw_lag_screw as drawing
import lag_screw_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import fastener


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/lag-screw.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/lag-screw.pdf")
    assert drawing.PNG.as_posix().endswith("/png/lag-screw_drawing.png")
    assert DRAWINGS_BY_NAME["lag_screw"].script == Path(drawing.__file__).resolve()


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
    catalog = fastener("lag-screw")
    assert spec.THREAD == catalog.thread
    assert spec.SHANK_DIA == catalog.model_diameter_mm
    assert spec.SHANK_LEN == catalog.length_mm
    assert spec.THREAD_DESIGNATION == f"{catalog.thread} UNC"
    assert spec.THREAD_DESIGNATION in spec.DRAWING_NOTES
    assert drawing.DIMENSION_CALLOUTS == {}


def test_head_end_cluster_is_clear_of_the_left_zone_border() -> None:
    assert drawing.END_CENTER == (0.085, 0.180)
    assert drawing.END_DIM_X == 0.043
    assert {xy[0] for xy in drawing.END_KEEP.values()} == {drawing.END_DIM_X}
    assert abs(drawing.END_CENTER[0] - drawing.END_DIM_X - 0.042) < 1e-12


def test_lengths_are_marked_extrude_depth_model_dims() -> None:
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name_dimensions(adapter, "Head", ["HeadHt"])' in part_source
    assert 'name_dimensions(adapter, "Shank", ["ShankLg"])' in part_source
    assert spec.SIDE_VIEW_DIMENSIONS == {"Head": {"HeadHt"}, "Shank": {"ShankLg"}}
    assert 'keep=SIDE_KEEP, view_label="side"' in _source()


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


def test_hidden_lines_stay_on_in_the_profile_view() -> None:
    source = _source()
    assert "set_hidden_lines_visible(adapter, side)" in source
    assert "set_hidden_lines_removed(adapter, end)" in source  # tiny end view
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("lag-screw")
    assert config["number"] == "MHA-039"
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 4
