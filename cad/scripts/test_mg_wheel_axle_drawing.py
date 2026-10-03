"""Offline contracts for the wheel-axle drawing."""

from __future__ import annotations

from pathlib import Path

import build_mg_magnifying_wheel
import build_mg_wheel_axle as part
import draw_mg_wheel_axle as drawing
import mg_wheel_axle_spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/mg-wheel-axle.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/mg-wheel-axle.pdf")
    assert drawing.PNG.as_posix().endswith("/png/mg-wheel-axle_drawing.png")
    assert DRAWINGS_BY_NAME["mg_wheel_axle"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is mg_wheel_axle_spec.DRAWING_DIMENSIONS
    marked = set().union(*mg_wheel_axle_spec.DRAWING_DIMENSIONS.values())
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
        mg_wheel_axle_spec.FLANGE_DIA,
        mg_wheel_axle_spec.FLANGE_LEN,
        mg_wheel_axle_spec.STUD_DIA,
        mg_wheel_axle_spec.STUD_LEN,
        mg_wheel_axle_spec.COLLAR_DIA,
        mg_wheel_axle_spec.COLLAR_LEN,
    )


def test_washer_and_nut_stack_stays_at_the_wheel_hub_end() -> None:
    spec = mg_wheel_axle_spec
    assert spec.WASHER_START == spec.FLANGE_LEN + spec.WHEEL_HUB_RIDE == 13.0
    nut_start = spec.WASHER_START + spec.COLLAR_LEN
    assert nut_start == 14.0
    assert nut_start + spec.NUT_H == 17.0
    assert spec.FLANGE_LEN + spec.STUD_LEN - (nut_start + spec.NUT_H) == 3.0


def test_stud_callout_keeps_wheel_bore_running_clearance() -> None:
    # The magnifying wheel's bore is nominal-on-nominal with the stud, so the
    # running clearance comes entirely from the stud's model-owned band.
    assert build_mg_magnifying_wheel.BORE_DIA == mg_wheel_axle_spec.STUD_DIA
    assert drawing.DIMENSION_CALLOUTS == {}
    assert mg_wheel_axle_spec.STUD_DIA_BAND == (-0.02, -0.05)
    assert model_toleranced_dimensions(part) == {
        ("StudProfile", "StudDia"): "*deviations(STUD_DIA_BAND)"
    }
    clearance_min = build_mg_magnifying_wheel.BORE_DIA - (mg_wheel_axle_spec.STUD_DIA - 0.02)
    clearance_max = build_mg_magnifying_wheel.BORE_DIA - (mg_wheel_axle_spec.STUD_DIA - 0.05)
    assert round(clearance_min, 2) == 0.02
    assert round(clearance_max, 2) == 0.05
    notes = mg_wheel_axle_spec.DRAWING_NOTES
    # Deburr/edge-break is a title-block note; repeating it here would duplicate it.
    assert "DEBURR" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_native_gdt_controls_axle_orientation_coaxiality_and_finish() -> None:
    """GD&T identity lives in the spec's PMI rows; the sheet only imports it."""
    from mg_wheel_axle_spec import GEOMETRIC_CONTROLS, PART_DATUMS

    by_key = {control.key: control for control in GEOMETRIC_CONTROLS}
    assert set(by_key) == {"stud_perpendicularity", "collar_runout"}
    assert by_key["stud_perpendicularity"].characteristic == "perpendicularity"
    assert by_key["stud_perpendicularity"].tolerance == "0.05"
    assert by_key["stud_perpendicularity"].datums == ("A",)
    assert by_key["stud_perpendicularity"].tolerance_zone == "diametral"
    assert by_key["collar_runout"].characteristic == "circular_runout"
    assert by_key["collar_runout"].tolerance == "0.05"
    assert by_key["collar_runout"].datums == ("B",)
    bearing_y = mg_wheel_axle_spec.FLANGE_LEN + mg_wheel_axle_spec.WHEEL_HUB_RIDE / 2.0
    assert by_key["stud_perpendicularity"].face.contains_y_mm == bearing_y
    assert PART_DATUMS[1].face.contains_y_mm == bearing_y
    assert tuple(datum.letter for datum in PART_DATUMS) == ("A", "B")

    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "author_part_pmi(" in part_source
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "project_part_pmi(" in source
    assert "controls=GEOMETRIC_CONTROLS" in source
    assert "add_feature_control_frame(" not in source
    assert "add_datum_feature(" not in source
    assert source.count("add_surface_finish(") == 1


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (3.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(3, 1)") == 3


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("mg-wheel-axle")
    assert "1018" in str(config["material_specification"])
    assert config["finish"]
    assert int(config["quantity"]) == 1


def test_surface_finish_is_part_owned_authored_and_consumed() -> None:
    (control,) = mg_wheel_axle_spec.SURFACE_FINISHES
    assert control.key == "stud_bearing"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == mg_wheel_axle_spec.STUD_DIA
    assert control.face.contains_y_mm == (
        mg_wheel_axle_spec.FLANGE_LEN + mg_wheel_axle_spec.WHEEL_HUB_RIDE / 2.0
    )
    part_source = "".join(Path(part.__file__).read_text(encoding="utf-8").split())
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    sheet_source = "".join(Path(drawing.__file__).read_text(encoding="utf-8").split())
    assert (
        'control=surface_finish_by_key(SURFACE_FINISHES,"stud_bearing")'
        in sheet_source
    )
    assert "roughness_ra=" not in sheet_source
