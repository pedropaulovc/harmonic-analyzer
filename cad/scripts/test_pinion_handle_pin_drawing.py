"""Release contracts for the separate MHA-136 upper-handle retention pin."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_drive_train_assembly as assembly
import draw_pinion_handle_pin as drawing
import pinion_handle_pin_spec as spec
import pinion_handle_spec as handle_spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME


def test_part_identity_and_drawing_registry_are_complete() -> None:
    config = _config.parts("pinion-handle-pin")
    assert config["number"] == "MHA-136"
    assert "1018" in config["material_specification"]
    assert int(config["quantity"]) == 1
    registered = DRAWINGS_BY_NAME["pinion_handle_pin"]
    assert registered.artifact_stem == "pinion-handle-pin"
    assert registered.script == Path(drawing.__file__).resolve()
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_plain_pin_definition_matches_the_upper_handle_joint() -> None:
    assert spec.PIN_DIA == pytest.approx(2.0)
    assert spec.PIN_DIA == pytest.approx(handle_spec.RETENTION_PIN_DIA)
    assert spec.PIN_LEN == pytest.approx(handle_spec.TUBE_OD)
    assert spec.DRAWING_DIMENSIONS == {"PinProfile": {"PinDia", "PinLen"}}
    assert spec.DRAWING_PRECISION_BY_NAME == {"PinDia": 2, "PinLen": 1}
    assert not [name for name in vars(spec) if name.endswith("_BAND")]
    assert "MATCH-REAM" in spec.DRAWING_NOTES
    assert "FLUSH" in spec.DRAWING_NOTES


def test_assembly_places_pin_coaxial_and_flush_in_rotated_handle() -> None:
    axis = assembly.HANDLE_PIN_ROWS[2]
    assert math.sqrt(sum(component * component for component in axis)) == pytest.approx(1.0)
    expected_axis = (
        -math.sin(math.radians(assembly.HANDLE_TILT_DEG)),
        math.cos(math.radians(assembly.HANDLE_TILT_DEG)),
        0.0,
    )
    assert axis == pytest.approx(expected_axis)
    midpoint = tuple(
        assembly.HANDLE_PIN_ORIGIN[i] + spec.PIN_LEN / 2.0 * axis[i]
        for i in range(3)
    )
    assert midpoint == pytest.approx(assembly.HANDLE_PIN_CENTER)
    assert midpoint[2] == pytest.approx(
        assembly.ARBOR_Z0 + assembly.ARBOR_RETENTION_PIN_STATION
    )
    assert assembly.HANDLE_PIN_LEN == pytest.approx(handle_spec.RETENTION_PIN_LEN)
