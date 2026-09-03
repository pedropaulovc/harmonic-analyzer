"""Offline contracts for the pinion-turning-handle drawing.

A turned tee locked to its arbor is not on the GD&T allowlist
(cad/docs/drawing-simplicity-policy.md): no datums, frames, basics or
roughness symbols; only the press and ream bands ride the model dimensions,
every axial length lives on SECTION A-A (never a hidden line), and the notes
are one line of process fact.
"""

from __future__ import annotations

from pathlib import Path

import pinion_handle_spec
import draw_pinion_handle as drawing
import build_pinion_handle as handle
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-handle.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-handle.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-handle_drawing.png")
    assert DRAWINGS_BY_NAME["pinion_handle"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert handle.DRAWING_DIMENSIONS is pinion_handle_spec.DRAWING_DIMENSIONS
    assert handle.SURFACE_FINISHES is pinion_handle_spec.SURFACE_FINISHES
    marked = set().union(*pinion_handle_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.SECTION_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    # The crown is a size on the section: sphere radius + (REF) height.
    assert {"CapR", "CapSagDim"} <= set(drawing.SECTION_KEEP)
    assert drawing.RIGHT_KEEP == {}
    assert (drawing.ROD_UP, drawing.ROD_DOWN, drawing.ROD_DIA) == (
        pinion_handle_spec.ROD_UP,
        pinion_handle_spec.ROD_DOWN,
        pinion_handle_spec.ROD_DIA,
    )


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    assert drawing.SECTION_CENTER[1] >= 0.110
    source = _source()
    assert "scale=(1, 1)" in source  # the isometric override
    assert pinion_handle_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source
    # The old free-text "BODY CROSS-HOLE VIEW" caption is gone: the cross-hole
    # station lives on the labelled SECTION A-A.
    assert "BODY CROSS-HOLE VIEW" not in source
    assert 'section_label="A"' in source


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, right, section):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = pinion_handle_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "PRESS THE CROSS ROD" in notes
    # Sizes live on the views, setup mandates are not the print's business.
    for banned in (
        "ONE SETUP",
        "SR",
        "HIGH",
        "LOWER ARM",
        "SHARP",
        "DATUM",
        "BASIC",
        "FRAME",
        "+/-",
        "+0.10",
        "LINEAR",
        "X.XX",
        "RELEASE HOLD",
        "AT ASSEMBLY",
        "DOWEL",
        "BREAK ALL",
    ):
        assert banned not in notes, banned
    assert notes.isascii()
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_handle_interfaces_are_released_with_bands_on_the_model() -> None:
    assert drawing.DIMENSION_CALLOUTS["RodDia"] == "PRESS FIT"
    assert drawing.DIMENSION_CALLOUTS["RodHoleDia"] == "REAM THRU"
    assert drawing.DIMENSION_CALLOUTS["TubeId"] == "REAM"
    assert drawing.DIMENSION_CALLOUTS["TubeLen"] == "BORE DEPTH"
    assert drawing.DIMENSION_CALLOUTS["RodSpan"] == "OAL"
    assert drawing.DIMENSION_CALLOUTS["CapR"] == "SPHERICAL CROWN"
    assert "+/-" not in "\n".join(drawing.DIMENSION_CALLOUTS.values())
    assert 6.015 <= pinion_handle_spec.ROD_DIA <= 6.020
    assert 6.000 <= pinion_handle_spec.ROD_HOLE_DIA <= 6.010
    source = Path(handle.__file__).read_text(encoding="utf-8")
    assert "merge_result=False" in source
    assert 'name_last_feature(adapter, "RodHole")' in source
    # Only the fits carry a band: the turned lengths (grip, bore depth, rod
    # span) take the title-block tolerance (machinist review 2026-09-02).
    assert model_toleranced_dimensions(handle) == {
        ("TubeProfile", "TubeId"): "*deviations(TUBE_ID_BAND)",
        ("RodProfile", "RodDia"): "*deviations(ROD_PRESS_BAND)",
        ("RodHoleProfile", "RodHoleDia"): "*deviations(ROD_HOLE_REAM_BAND)",
    }
    for retired in ("GRIP_LENGTH_TOLERANCE_MM", "TUBE_LENGTH_BAND", "ROD_SPAN_TOLERANCE_MM"):
        assert not hasattr(pinion_handle_spec, retired), retired


def test_drive_train_clearance_uses_the_released_rod_diameter() -> None:
    assembly = Path(handle.__file__).with_name("build_drive_train_assembly.py")
    source = assembly.read_text(encoding="utf-8")
    assert "ROD_DIA as HANDLE_ROD_DIA" in source
    assert "HANDLE_Z - HANDLE_ROD_DIA / 2.0" in source


def test_axial_lengths_live_on_the_section_from_one_origin() -> None:
    # Every length is dimensioned on SECTION A-A (cut on the right view along
    # the arbor axis), never to the hidden bore lines; both cross-hole
    # stations share the hole axis as their origin and snap to its CENTRE.
    source = _source()
    assert source.count("create_section_view(") == 1
    assert source.count("add_edge_dimension(") == 3
    assert 'label="grip shoulder to body cross-hole axis"' in source
    assert 'label="flat hub end to body cross-hole axis"' in source
    assert 'label="bore axis to rod lower end"' in source
    assert source.count("set_arc_endpoints_to_center(") == 3
    assert "z_max / 1000.0" in source
    assert "set_reference_dimension(" not in source
    assert 'set_reference_dimensions(adapter, section_annotations, ["CapSagDim"])' in source
    # Section positions are derived from the projected axes, never assumed.
    assert "_section_frame(adapter, section" in source
    assert "orientation=along_z" in source
    assert drawing.FRONT_KEEP["RodSpan"] == (0.125, 0.245)


def test_diameter_leaders_end_at_the_circumference() -> None:
    source = _source()
    assert "_ARROWS_OUTSIDE = 1" in source
    assert source.count("_leaders_to_circumference(") >= 3  # def + two calls
    assert drawing.FRONT_DIAMETERS == ("GripDia", "TubeOd", "TubeId")
    assert drawing.SECTION_DIAMETERS == ("RodDia", "RodHoleDia")
    # The three front-view diameters fan out to one side of the grip, the rod
    # span stands outboard of them and the lower-arm station sits alone left.
    for name in drawing.FRONT_DIAMETERS:
        assert drawing.FRONT_KEEP[name][0] > drawing.FRONT_CENTER[0]
        assert drawing.FRONT_KEEP[name][0] < drawing.FRONT_KEEP["RodSpan"][0]


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "add_attached_note(",
    ):
        assert helper not in source, helper
    assert "WITHIN" not in source
    assert not hasattr(pinion_handle_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(pinion_handle_spec, "GEOMETRIC_CONTROLS")
    assert pinion_handle_spec.SURFACE_FINISHES == ()
    assert "author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)" in Path(
        handle.__file__
    ).read_text(encoding="utf-8")


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(handle.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("pinion-handle")
    assert spec["material"] == spec["material_specification"]
    assert spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 1
