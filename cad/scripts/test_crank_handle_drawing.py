"""Offline contracts for the crank-handle drawing.

A turned wooden grip is not on the GD&T allowlist
(cad/docs/drawing-simplicity-policy.md): no datums, frames, basics or
roughness symbols; the reamed bore's band rides the model dimension and the
notes are a four-line turning schedule.
"""

from __future__ import annotations

from pathlib import Path

import crank_handle_spec
import draw_crank_handle as drawing
import build_crank_handle as handle
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-handle.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crank-handle.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crank-handle_drawing.png")
    assert (
        DRAWINGS_BY_NAME["crank_handle"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert handle.DRAWING_DIMENSIONS is crank_handle_spec.DRAWING_DIMENSIONS
    marked = set().union(*crank_handle_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    # The build re-imports its primitive nominals from the spec.
    assert (handle.HANDLE_LENGTH, handle.COLLAR_LENGTH, handle.PEAK_X) == (
        crank_handle_spec.HANDLE_LENGTH,
        crank_handle_spec.COLLAR_LENGTH,
        crank_handle_spec.PEAK_X,
    )
    assert drawing.HANDLE_LENGTH == crank_handle_spec.HANDLE_LENGTH


def test_diameters_are_a_turning_schedule_not_marked_dims() -> None:
    # The pear arcs derive the diameters, so only the axial stations are marked;
    # the diameters live in the turning-schedule note.
    marked = set().union(*crank_handle_spec.DRAWING_DIMENSIONS.values())
    assert marked == {"HandleLength", "CollarLength", "PeakStation", "PivotBoreDia"}
    notes = crank_handle_spec.DRAWING_NOTES
    assert f"<MOD-DIAM>{crank_handle_spec.COLLAR_DIA:.2f}" in notes
    assert f"<MOD-DIAM>{2.0 * crank_handle_spec.NECK_R:.2f} NECK" in notes
    assert f"<MOD-DIAM>{crank_handle_spec.HANDLE_MAX_DIA:.2f} SWELL" in notes
    assert f"<MOD-DIAM>{2.0 * crank_handle_spec.CAP_R:.2f} CAP" in notes
    assert f"R{crank_handle_spec.FRONT_PROFILE_R:.2f}" in notes
    assert f"R{crank_handle_spec.REAR_PROFILE_R:.2f}" in notes


def test_peak_station_uses_visible_construction_geometry() -> None:
    build_source = Path(handle.__file__).read_text(encoding="utf-8")
    drawing_source = _source()
    assert 'profile.record("PeakStation",' in build_source
    assert 'profile.record("FrontArcCx",' in build_source
    assert '"PeakStation":' in drawing_source
    assert '"FrontArcCx":' not in drawing_source
    assert "peak station construction line" in build_source


def test_bored_profile_has_end_view_center_marks() -> None:
    source = _source()
    assert "auto_center_marks" in source
    assert "add_view_centerline" in source


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = _source()
    assert "scale=(1, 1)" in source  # the isometric override
    assert crank_handle_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, right):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = crank_handle_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "TURN COLLAR INTEGRAL" in notes
    assert "STRAIGHT GRAIN" in notes
    for banned in (
        "DATUM",
        "BASIC",
        "PROFILE 0.",
        "+/-",
        "+0.00",
        "LINEAR",
        "X.XX",
        "COIL",
        "CDA 260",
        "BRASS",
        "Ra ",
    ):
        assert banned not in notes, banned
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


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
    assert "WITHIN" not in source
    assert not hasattr(crank_handle_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(crank_handle_spec, "GEOMETRIC_CONTROLS")
    assert not hasattr(crank_handle_spec, "SURFACE_FINISHES")


def test_bore_and_length_bands_ride_the_model_dimensions() -> None:
    assert drawing.DIMENSION_CALLOUTS["PivotBoreDia"] == "REAM THRU"
    assert crank_handle_spec.PIVOT_BORE_BAND == (0.025, -0.025)
    assert crank_handle_spec.HANDLE_LENGTH_BAND == (0.000, -0.250)
    build_source = Path(handle.__file__).read_text(encoding="utf-8")
    assert build_source.count("set_dimension_bilateral_tolerance(") == 2


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(handle.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("crank-handle")
    assert handle.MATERIAL == "Oak"
    assert "white oak" in spec["material_specification"]
    assert "6-8% MC" in spec["material_specification"]
    assert spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 1
