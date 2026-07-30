"""Offline contracts for the pinion cam-follower-pin drawing."""

from __future__ import annotations

from pathlib import Path

import pinion_cam_pin_spec
import draw_pinion_cam_pin as drawing
import build_pinion_cam_pin as pin
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-cam-pin.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-cam-pin.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-cam-pin_drawing.png")
    assert DRAWINGS_BY_NAME["pinion_cam_pin"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert pin.DRAWING_DIMENSIONS is pinion_cam_pin_spec.DRAWING_DIMENSIONS
    assert pin.SURFACE_FINISHES is pinion_cam_pin_spec.SURFACE_FINISHES
    assert drawing.SURFACE_FINISHES is pinion_cam_pin_spec.SURFACE_FINISHES
    marked = set().union(*pinion_cam_pin_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert drawing.PIN_DIA == pinion_cam_pin_spec.PIN_DIA
    assert drawing.PIN_DIA == 4.016
    assert drawing.PIN_LEN == pinion_cam_pin_spec.PIN_LEN


def test_sheet_runs_at_4_to_1_with_8_to_1_end_view() -> None:
    assert drawing.SHEET_SCALE == (4.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(8, 1)" in source  # the end-view override
    # The crown radius belongs to a sketch on the Top plane.  The equivalent
    # axisymmetric side elevation must face that plane to import CapR natively.
    assert '"*Top", *RIGHT_CENTER' in source
    assert '"*Right", *RIGHT_CENTER' not in source
    assert "(PIN_DIA / 2000.0, 0.0, 0.0)" in source
    assert "crown_radial / 1000.0,\n            0.0," in source
    # The isometric renders at the sheet scale, so no separate iso-scale note.
    assert 'add_property_linked_note(adapter, "End View Note"' in source
    assert pinion_cam_pin_spec.END_VIEW_NOTE == "END VIEW SCALE 8:1"


def test_linked_notes_are_functional_and_carry_no_general_tolerance() -> None:
    notes = pinion_cam_pin_spec.DRAWING_NOTES
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "({CAP_SAG:.2f}) REF AXIAL HEIGHT" in source
    assert "SPHERICAL" in notes
    assert "LINEAR +/-" not in notes
    assert " BA " not in f" {notes} "
    assert "X.XX" not in notes
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_direct_limits_replace_ambiguous_gdt() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 1
    assert "add_feature_control_frame(" in source
    assert "add_view_centerline(" in source
    assert (
        "        edge_xy=(FRONT_CENTER[0] + end_radius, FRONT_CENTER[1]),\n"
        "        symbol_xy=(0.105, 0.228),\n"
        '        datum="A",\n'
        '        label="cam-pin cylindrical-shank datum axis",\n'
        "        position_tolerance_m=0.0065," in source
    )
    assert source.count("position_tolerance_m=0.0065") == 1
    assert source.count("add_surface_finish(") == 1
    assert 'surface_finish_by_key(SURFACE_FINISHES, "finished_shank")' in source
    assert "author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)" in Path(
        pin.__file__
    ).read_text(encoding="utf-8")
    assert model_toleranced_dimensions(pin) == {
        ("PinProfile", "PinDia"): "*deviations(PIN_DIA_BAND)",
        ("Pin", "Depth"): "PIN_LENGTH_TOLERANCE_MM",
        ("CapProfile", "CapR"): "CAP_RADIUS_TOLERANCE_MM",
    }
    assert drawing.DIMENSION_CALLOUTS["PinDia"] == "FINAL SIZE"
    assert "NOMINAL REF ONLY" not in drawing.DIMENSION_CALLOUTS["PinDia"]
    assert "set_reference_dimension(" in source
    assert 'characteristic="flatness"' in source
    assert "datums=()," in source  # crown profile is FORM ONLY (machinist round 1)
    assert "NO CHAMFER" in pinion_cam_pin_spec.DRAWING_NOTES
    assert "ISO 286-2" not in drawing.DIMENSION_CALLOUTS["PinDia"]
    assert "SEATED FLAT END TO CROWN ROOT" in drawing.DIMENSION_CALLOUTS["Depth"]
    assert "CapR" in drawing.RIGHT_KEEP
    assert "SR{CAP_RADIUS:.2f}+/-0.05" not in source
    assert "ONE SPHERICAL CROWN" in pinion_cam_pin_spec.DRAWING_NOTES
    assert "BOTH SPHERICAL CROWNS" not in pinion_cam_pin_spec.DRAWING_NOTES
    assert "EXEMPT FROM TITLE-BLOCK EDGE-BREAK" in pinion_cam_pin_spec.DRAWING_NOTES


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(pin.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("pinion-cam-pin")
    assert spec["number"] == "MHA-116"
    assert spec["material"] == spec["material_specification"]
    assert spec["material_specification"]
    assert spec["finish"]
    assert "fit_class" not in spec
    assert int(spec["quantity"]) == 2
