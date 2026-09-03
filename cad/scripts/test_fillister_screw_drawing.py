"""Offline contracts for the fillister-screw drawing.

A brass #4-40 machine screw: no datums, frames, roughness symbols or basic
dimensions (cad/docs/drawing-simplicity-policy.md rules 3-5), three lines of
thread and head-style note (rule 6), hidden lines on in the profile (rule 7).
"""

from __future__ import annotations

from pathlib import Path

import build_fillister_screw as part
import draw_fillister_screw as drawing
import fillister_screw_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import fastener


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/fillister-screw.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/fillister-screw.pdf")
    assert drawing.PNG.as_posix().endswith("/png/fillister-screw_drawing.png")
    assert DRAWINGS_BY_NAME["fillister_screw"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) == marked


def test_catalog_is_the_single_source_of_the_thread() -> None:
    """The drawing must never invent a thread the part does not build."""
    catalog = fastener("fillister-screw")
    assert spec.THREAD == catalog.thread
    assert spec.SHANK_DIA == catalog.model_diameter_mm
    assert spec.SHANK_LEN == catalog.length_mm
    assert spec.THREAD_DESIGNATION == f"{catalog.thread} UNC"
    assert spec.THREAD_DESIGNATION in spec.DRAWING_NOTES
    assert drawing.DIMENSION_CALLOUTS == {}
    assert drawing.SIDE_DIMENSION_CALLOUTS == {"ShankLg": "UNDERHEAD LENGTH"}
    assert "THREADED TO THE" in spec.DRAWING_NOTES


def test_lengths_are_inserted_from_named_model_dimensions() -> None:
    assert set(drawing.SIDE_KEEP) == {"HeadHt", "ShankLg", "ShankDia"}
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert part_source.count("set_dimension_symmetric_tolerance(") == 3
    # The shank diameter reads as the thread designation, sourced from the
    # spec -- never a thread literal frozen in the drawing script.
    source = _source()
    assert '{"ShankDia": THREAD_DESIGNATION}' in source
    assert '"#4-40' not in source


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert max(map(len, lines)) < 80
    assert lines[0] == f"{spec.THREAD_DESIGNATION} THREADED TO THE HEAD; LAST 2 PITCHES MAY BE INCOMPLETE."
    assert f"SLOT {spec.SLOT_W:.2f} WIDE X {spec.SLOT_D:.2f} DEEP" in notes
    # Head diameter, height and under-head length are dimensions, so the
    # note never repeats them; nothing the title block already says.
    assert f"{spec.HEAD_DIA:.2f}" not in notes
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
    # policy rules 3-5: a machine screw is off the GD&T allowlist and nothing
    # runs on it.
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
    # The tiny head-end view keeps HLR on purpose: the shank-behind-head
    # circle would read as a hole.
    assert "set_hidden_lines_removed(adapter, end)" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("fillister-screw")
    assert config["number"] == "MHA-030"
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 26
