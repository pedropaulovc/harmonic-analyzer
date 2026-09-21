"""Offline release contracts for the MHA-138 axial arm-to-hub seam pin."""

from __future__ import annotations

from pathlib import Path

import pytest

import crank_hub_geometry as geometry
import crank_hub_pin_spec as pin_spec
import draw_crank_hub_pin as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_pin_length_is_half_the_shared_arm_thickness() -> None:
    assert pin_spec.PIN_LEN == geometry.ARM_THICKNESS / 2.0 == 4.0


def test_six_oclock_seam_pin_cannot_reach_hub_bore() -> None:
    inner_pin_radius = geometry.AXIAL_PIN_RADIUS_FROM_AXIS - pin_spec.PIN_DIA / 2.0
    largest_bore_radius = (
        geometry.HUB_BORE_DIA + geometry.HUB_BORE_BAND[0]
    ) / 2.0
    assert inner_pin_radius - largest_bore_radius >= 0.75


def test_drawing_registry_and_native_dimensions_are_complete() -> None:
    assert DRAWINGS_BY_NAME["crank_hub_pin"].script == Path(drawing.__file__).resolve()
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-hub-pin.SLDDRW")
    assert set(drawing.RIGHT_KEEP) == set().union(*pin_spec.DRAWING_DIMENSIONS.values())
    assert pin_spec.DRAWING_PRECISION_BY_NAME == {"PinDia": 1, "PinLen": 1}


def test_assembly_places_pin_axially_at_six_oclock() -> None:
    import build_drive_train_assembly as assembly

    assert assembly.CRANK_HUB_PIN_ORIGIN == pytest.approx(
        (
            assembly.X_CRANK,
            assembly.Y_CRANK - geometry.AXIAL_PIN_RADIUS_FROM_AXIS,
            assembly.CRANK_FACE_Z,
        )
    )
    assert assembly.CRANK_HUB_PIN_ROWS[2] == pytest.approx((0.0, 0.0, 1.0))
