"""Offline contracts for retained alignment-pinion manufacturing data."""

from __future__ import annotations

import pytest

import _config
import alignment_pinion_spec as spec
import pinion_arbor_spec as arbor


def test_gear_data_block_preserves_the_tooth_system() -> None:
    data = spec.GEAR_DATA
    assert spec.TEETH == 42
    assert "42" in data
    for field in (
        "NUMBER OF TEETH",
        "DIAMETRAL PITCH",
        "MODULE",
        "PRESSURE ANGLE",
        "PITCH DIAMETER",
        "WHOLE DEPTH",
        "TOOTH FORM",
    ):
        assert field in data, field
    assert "INVOLUTE" in data
    assert "FULL DEPTH" in data
    assert "X.XX" not in data


def test_bore_has_the_single_machined_finish_contract() -> None:
    assert len(spec.SURFACE_FINISHES) == 1
    (finish,) = spec.SURFACE_FINISHES
    assert finish.key == "drum_bore"
    assert finish.roughness_um == 1.6
    assert finish.face.diameter_mm == 8.0


def test_mha102_fit_band_has_a_valid_intersection_at_both_shaft_limits() -> None:
    shaft_limits = (
        arbor.SHAFT_DIA + arbor.SHAFT_DIA_BAND[1],
        arbor.SHAFT_DIA + arbor.SHAFT_DIA_BAND[0],
    )
    bore_limits = (
        spec.BORE_DIA + spec.ARBOR_BORE_BAND[1],
        spec.BORE_DIA + spec.ARBOR_BORE_BAND[0],
    )
    assert shaft_limits == pytest.approx((7.98, 8.00))
    assert bore_limits == pytest.approx((7.96, 7.98))

    minimum_interference, maximum_interference = (
        spec.ARBOR_DIAMETRAL_INTERFERENCE_MM
    )
    assert (minimum_interference, maximum_interference) == pytest.approx(
        (0.010, 0.030)
    )
    assert 0.0 < minimum_interference < maximum_interference

    for shaft_dia in shaft_limits:
        bore_for_max_interference = shaft_dia - maximum_interference
        bore_for_min_interference = shaft_dia - minimum_interference
        overlap_low = max(bore_limits[0], bore_for_max_interference)
        overlap_high = min(bore_limits[1], bore_for_min_interference)
        assert overlap_low < overlap_high


def test_part_metadata_preserves_material_finish_quantity() -> None:
    config = _config.parts("alignment-pinion")
    assert config["material_specification"] == "C36000 free-machining brass"
    assert config["finish"] == "polished brass; tooth surfaces as cut"
    assert int(config["quantity"]) == 1
