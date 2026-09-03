"""Offline contracts for the pinion cam-follower-pin drawing.

A pressed stud is not on the GD&T allowlist
(cad/docs/drawing-simplicity-policy.md): the print carries no datums, frames
or roughness symbols; the press band rides the model diameter at three
decimals and the notes are two lines of process fact.
"""

from __future__ import annotations

from pathlib import Path

import pinion_cam_pin_spec
import draw_pinion_cam_pin as drawing
import build_pinion_cam_pin as pin
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-cam-pin.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-cam-pin.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-cam-pin_drawing.png")
    assert DRAWINGS_BY_NAME["pinion_cam_pin"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert pin.DRAWING_DIMENSIONS is pinion_cam_pin_spec.DRAWING_DIMENSIONS
    assert pin.SURFACE_FINISHES is pinion_cam_pin_spec.SURFACE_FINISHES
    marked = set().union(*pinion_cam_pin_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert drawing.PIN_DIA == pinion_cam_pin_spec.PIN_DIA
    assert drawing.PIN_DIA == 4.016
    assert drawing.PIN_LEN == pinion_cam_pin_spec.PIN_LEN
    assert pinion_cam_pin_spec.OVERALL_LEN == 17.8


def test_sheet_runs_at_4_to_1_with_8_to_1_end_view() -> None:
    assert drawing.SHEET_SCALE == (4.0, 1.0)
    source = _source()
    assert "scale=(8, 1)" in source  # the end-view override
    # The crown radius belongs to a sketch on the Top plane.  The equivalent
    # axisymmetric side elevation must face that plane to import CapR natively.
    assert '"*Top", *RIGHT_CENTER' in source
    assert '"*Right", *RIGHT_CENTER' not in source
    assert "crown_radial / 1000.0,\n            0.0," in source
    # The isometric renders at the sheet scale, so no separate iso-scale note.
    assert 'add_property_linked_note(adapter, "End View Note"' in source
    assert pinion_cam_pin_spec.END_VIEW_NOTE == "END VIEW SCALE 8:1"


def test_view_display_exposes_the_crown_root_edge() -> None:
    source = _source()
    assert "for view in (front, right):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source
    assert drawing._TANGENT_EDGES_VISIBLE == 2
    assert "iso.SetDisplayTangentEdges2(_TANGENT_EDGES_VISIBLE)" in source
    assert "iso.GetDisplayTangentEdges2()" in source
    assert "failed to show cam-pin crown-root edge" in source
    assert "iso.UpdateViewDisplayGeometry()" in source


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = pinion_cam_pin_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "SPHERICAL CROWN" in notes
    assert "NO CHAMFER" in notes
    for banned in ("EXEMPT", "TITLE-BLOCK", "+/-", "LINEAR", "X.XX", "DATUM", "FLATNESS"):
        assert banned not in notes, banned
    assert " BA " not in f" {notes} "
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    # The crown height is flagged from the crown, as a REF value.
    assert "({CAP_SAG:.2f}) HIGH" in source
    assert source.count("add_attached_note(") == 1


def test_print_carries_no_gdt_or_finish_symbols() -> None:
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
    assert not hasattr(pinion_cam_pin_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(pinion_cam_pin_spec, "GEOMETRIC_CONTROLS")
    assert pinion_cam_pin_spec.SURFACE_FINISHES == ()
    assert "author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)" in Path(
        pin.__file__
    ).read_text(encoding="utf-8")
    assert "add_view_centerline(" in source


def test_only_the_press_diameter_prints_three_decimals() -> None:
    source = _source()
    assert '{"PinDia": 3}' in source
    assert pinion_cam_pin_spec.PIN_DIA_BAND == (0.004, -0.004)
    assert model_toleranced_dimensions(pin) == {
        ("PinProfile", "PinDia"): "*deviations(PIN_DIA_BAND)",
        ("Pin", "Depth"): "PIN_LENGTH_TOLERANCE_MM",
        ("CapProfile", "CapR"): "CAP_RADIUS_TOLERANCE_MM",
    }
    assert "PinDia" not in drawing.DIMENSION_CALLOUTS
    assert drawing.DIMENSION_CALLOUTS["Depth"] == "TO CROWN ROOT"
    assert "CapR" in drawing.RIGHT_KEEP
    assert "+/-" not in "\n".join(drawing.DIMENSION_CALLOUTS.values())


def test_crown_reads_as_a_spherical_radius() -> None:
    # SR2.92 on the view (machinist review 2026-09-02: the note had to be
    # consulted to learn the R was a sphere): the imported radius prefix is
    # rewritten to SR and the callout beneath says SPHERICAL CROWN.
    source = _source()
    assert drawing.SPHERICAL_RADIUS_DIMENSION == "CapR"
    assert drawing.DIMENSION_CALLOUTS["CapR"] == "SPHERICAL CROWN"
    assert source.count("_spherical_radius_prefix(") == 2  # def + call
    assert 'prefix = "SR"' in source
    assert "unexpected radius prefix" in source


def test_overall_is_a_geometry_derived_view_adjacent_reference_note() -> None:
    # The shallow revolved apex proved unreliable as a selectable drawing
    # vertex.  Keep the conspicuous reference information without a geometry
    # pick: the note is formatted from OVERALL_LEN and sits left/above the
    # side view, opposite the 17.00 crown-root dimension.
    source = _source()
    assert drawing.OVERALL_NOTE == f"({pinion_cam_pin_spec.OVERALL_LEN:.2f}) OVERALL REF"
    assert "add_note(adapter, OVERALL_NOTE, *OVERALL_NOTE_XY)" in source
    assert "failed to add cam-pin overall reference note" in source
    assert "add_edge_dimension(" not in source
    assert "set_reference_dimension(" not in source
    assert "label=\"crown apex\"" not in source
    assert drawing.OVERALL_NOTE_XY[0] < drawing.RIGHT_CENTER[0]
    assert drawing.OVERALL_NOTE_XY[1] > drawing.RIGHT_CENTER[1]
    assert drawing.RIGHT_KEEP["Depth"][0] > drawing.RIGHT_CENTER[0]
    assert drawing.RIGHT_KEEP["CapR"][1] < drawing.RIGHT_CENTER[1] - 0.03
    assert drawing.RIGHT_KEEP["CapR"][0] > drawing.RIGHT_CENTER[0]


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(pin.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("pinion-cam-pin")
    assert spec["number"] == "MHA-116"
    assert spec["material"] == spec["material_specification"]
    assert spec["material_specification"]
    # The FINISH cell no longer dictates "smooth turned" (the block's Ra 3.2
    # governs); only the oil-film protection remains.
    assert spec["finish"] == "bright; ISO VG 32 oil film"
    assert "fit_class" not in spec
    assert int(spec["quantity"]) == 2
