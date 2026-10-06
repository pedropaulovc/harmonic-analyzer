"""Offline contracts for the wheel-axle drawing."""

from __future__ import annotations

import build_mg_magnifying_wheel
import build_mg_wheel_axle as part
import draw_mg_wheel_axle as drawing
import mg_wheel_axle_spec
from _drawing_contract import model_toleranced_dimensions


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    marked = set().union(*mg_wheel_axle_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.END_KEEP)
    assert kept == marked


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
    assert mg_wheel_axle_spec.STUD_DIA_BAND == (-0.02, -0.05)
    assert model_toleranced_dimensions(part) == {
        ("StudProfile", "StudDia"): "*deviations(STUD_DIA_BAND)"
    }
    clearance_min = build_mg_magnifying_wheel.BORE_DIA - (mg_wheel_axle_spec.STUD_DIA - 0.02)
    clearance_max = build_mg_magnifying_wheel.BORE_DIA - (mg_wheel_axle_spec.STUD_DIA - 0.05)
    assert round(clearance_min, 2) == 0.02
    assert round(clearance_max, 2) == 0.05


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


def test_surface_finish_is_part_owned_authored_and_consumed() -> None:
    (control,) = mg_wheel_axle_spec.SURFACE_FINISHES
    assert control.key == "stud_bearing"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == mg_wheel_axle_spec.STUD_DIA
    assert control.face.contains_y_mm == (
        mg_wheel_axle_spec.FLANGE_LEN + mg_wheel_axle_spec.WHEEL_HUB_RIDE / 2.0
    )
