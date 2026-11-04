"""Offline release contracts for the MHA-DT-VN-59 axial arm-to-hub seam pin."""

from __future__ import annotations

from pathlib import Path

import pytest

import _config
import dt_crank_hub_geometry as geometry
import dt_vn_crank_hub_pin_spec as pin_spec
import draw_dt_vn_crank_hub_pin as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_pin_is_the_98381a487_dowel_cut_shorter_than_the_seam() -> None:
    # McMaster-Carr 98381A487: 5/32 x 1/2 alloy-steel dowel, +.0001/+.0003.
    assert pin_spec.PIN_DIA == pytest.approx(5 / 32 * 25.4)
    assert geometry.AXIAL_PIN_DIA_STOCK_MAX == pytest.approx((5 / 32 + 0.0003) * 25.4, abs=1e-4)
    assert pin_spec.PIN_LEN < 0.5 * 25.4
    assert pin_spec.PIN_LEN < geometry.SEAM_DEPTH
    assert _config.parts("dt-vn-crank-hub-pin")["supplier_skus"] == [pin_spec.SKU]


def test_six_oclock_seam_leaves_the_u27_web_without_a_matched_check() -> None:
    assert geometry.SEAM_WEB_WORST_MM >= geometry.WALL_TARGET_MM
    assert len(pin_spec.DRAWING_NOTES.splitlines()) <= 4


def test_drawing_registry_and_native_dimensions_are_complete() -> None:
    assert DRAWINGS_BY_NAME["dt_vn_crank_hub_pin"].script == Path(drawing.__file__).resolve()
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-vn-crank-hub-pin.SLDDRW")
    assert set(drawing.RIGHT_KEEP) == set().union(*pin_spec.DRAWING_DIMENSIONS.values())
    # The bought diameter prints as the supplier's fraction; the cut length
    # at the title block's .XX.
    assert set(pin_spec.STOCK_FRACTION_DIMENSIONS) == {"PinDia"}
    assert pin_spec.DRAWING_PRECISION_BY_NAME["PinLen"] == 2
    assert pin_spec.PIN_LEN == pytest.approx(round(pin_spec.PIN_LEN / 25.4, 2) * 25.4)


def test_assembly_places_pin_axially_at_six_oclock() -> None:
    import build_dt_drive_train_assembly as assembly

    assert assembly.CRANK_HUB_PIN_ORIGIN == pytest.approx(
        (
            assembly.X_CRANK,
            assembly.Y_CRANK - geometry.AXIAL_PIN_RADIUS_FROM_AXIS,
            assembly.CRANK_FACE_Z,
        )
    )
    assert assembly.CRANK_HUB_PIN_ROWS[2] == pytest.approx((0.0, 0.0, 1.0))
