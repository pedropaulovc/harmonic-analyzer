"""Offline contracts for the wheel-axle drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a flanged stud turned
in one setting carries no datums or frames; the stud's running fit is the band
on the model diameter, plus one Ra on the OD the wheel spins on.
"""

from __future__ import annotations

from pathlib import Path

import build_magnifying_wheel
import build_wheel_axle as part
import draw_wheel_axle as drawing
import wheel_axle_spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/wheel-axle.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/wheel-axle.pdf")
    assert drawing.PNG.as_posix().endswith("/png/wheel-axle_drawing.png")
    assert DRAWINGS_BY_NAME["wheel_axle"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is wheel_axle_spec.DRAWING_DIMENSIONS
    marked = set().union(*wheel_axle_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.END_KEEP)
    assert kept == marked
    assert (
        drawing.FLANGE_DIA,
        drawing.FLANGE_LEN,
        drawing.STUD_DIA,
        drawing.STUD_LEN,
        drawing.COLLAR_DIA,
        drawing.COLLAR_LEN,
    ) == (
        wheel_axle_spec.FLANGE_DIA,
        wheel_axle_spec.FLANGE_LEN,
        wheel_axle_spec.STUD_DIA,
        wheel_axle_spec.STUD_LEN,
        wheel_axle_spec.COLLAR_DIA,
        wheel_axle_spec.COLLAR_LEN,
    )


def test_stud_band_keeps_wheel_bore_running_clearance() -> None:
    # The magnifying wheel's bore is nominal-on-nominal with the stud, so the
    # running clearance comes entirely from the stud's model-owned band.
    assert build_magnifying_wheel.BORE_DIA == wheel_axle_spec.STUD_DIA
    assert drawing.DIMENSION_CALLOUTS == {}
    assert wheel_axle_spec.STUD_DIA_BAND == (-0.02, -0.05)
    assert model_toleranced_dimensions(part) == {
        ("StudProfile", "StudDia"): "*deviations(STUD_DIA_BAND)"
    }
    clearance_min = build_magnifying_wheel.BORE_DIA - (wheel_axle_spec.STUD_DIA - 0.02)
    clearance_max = build_magnifying_wheel.BORE_DIA - (wheel_axle_spec.STUD_DIA - 0.05)
    assert round(clearance_min, 2) == 0.02
    assert round(clearance_max, 2) == 0.05


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = wheel_axle_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "ONE SETUP" in notes
    # Deburr/edge-break is a title-block row; "no tool marks" is what the Ra
    # symbol says; the bearing role is design intent, not a process fact.
    for banned in ("DEBURR", "BEARING", "TOOL MARKS", "WITHIN", "+/-", "UOS", "X.XX"):
        assert banned not in notes, banned
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_print_carries_no_gdt_and_one_running_finish() -> None:
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "find_edge_near(",
    ):
        assert helper not in source, helper
    assert wheel_axle_spec.PART_DATUMS == ()
    assert wheel_axle_spec.GEOMETRIC_CONTROLS == ()
    assert not hasattr(wheel_axle_spec, "GEOMETRIC_TOLERANCES_MM")
    # The wheel spins on the stud, so its OD alone carries a roughness symbol.
    (control,) = wheel_axle_spec.SURFACE_FINISHES
    assert control.key == "stud_bearing"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == wheel_axle_spec.STUD_DIA
    assert source.count("add_surface_finish(") == 1
    sheet_source = "".join(source.split())
    assert (
        'control=surface_finish_by_key(SURFACE_FINISHES,"stud_bearing")'
        in sheet_source
    )
    assert "roughness_ra=" not in source
    # The part build keeps its author_part_pmi call shape on the empty tuples.
    part_source = "".join(Path(part.__file__).read_text(encoding="utf-8").split())
    assert "author_part_pmi(" in part_source
    assert "datums=PART_DATUMS" in part_source
    assert "controls=GEOMETRIC_CONTROLS" in part_source
    assert "surface_finishes=SURFACE_FINISHES" in part_source


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, end):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (3.0, 1.0)
    assert _source().count("scale=(3, 1)") == 3


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("wheel-axle")
    assert "1018" in str(config["material_specification"])
    assert config["finish"]
    assert int(config["quantity"]) == 1
