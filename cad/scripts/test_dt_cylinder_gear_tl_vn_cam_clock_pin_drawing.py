"""Offline contracts for the MHA-DT-12-TL-VN-51 cam fixture clock pin (cut from McMaster 23065A503)."""

from __future__ import annotations

import pytest

import _config
import _mcmaster_23065a503 as dims
import build_dt_cylinder_gear_tl_vn_cam_clock_pin as part
import draw_dt_cylinder_gear_tl_vn_cam_clock_pin as drawing
import dt_cylinder_gear_tl_cam_fixture_spec as fixture
import dt_cylinder_gear_tl_vn_cam_clock_pin_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME

STEM = "dt-cylinder-gear-tl-vn-cam-clock-pin"
IN = 25.4


def test_pin_is_the_gauge_cut_shorter_than_supplied() -> None:
    row = _config.parts(STEM)
    assert row["number"] == "MHA-DT-12-TL-VN-51"
    assert row["supplier_skus"] == [spec.SKU] == ["23065A503"]
    assert spec.PIN_DIA == pytest.approx(0.0375 * IN)
    assert dims.SIZE_RANGE[0] <= spec.PIN_DIA <= dims.SIZE_RANGE[1]
    steps = (spec.PIN_DIA - dims.SIZE_RANGE[0]) / dims.SIZE_STEP
    assert steps == pytest.approx(round(steps))
    assert spec.PIN_LEN < dims.SUPPLIED_LENGTH
    assert spec.PIN_LEN == fixture.PIN_LENGTH
    assert part.PART_NAME == STEM


def test_drawing_registry_and_native_dimensions_are_complete() -> None:
    sheet = DRAWINGS_BY_NAME["dt_cylinder_gear_tl_vn_cam_clock_pin"]
    assert sheet.script.resolve() == drawing.SPEC.script.resolve()
    assert drawing.SLDDRW.as_posix().endswith(f"/slddrw/{STEM}.SLDDRW")
    assert set(drawing.FRONT_KEEP) == set().union(*spec.DRAWING_DIMENSIONS.values())
    # The bought diameter prints as the supplier's reference; the cut length
    # at the title block's .XX.
    assert set(spec.STOCK_REFERENCE_DIMENSIONS) == {"PinDia"}
    assert spec.DRAWING_PRECISION_BY_NAME["PinLen"] == 2
    assert spec.FIXTURE_NUMBER in spec.PIN_DIA_CALLOUT
    assert len(spec.DRAWING_NOTES.splitlines()) <= 4
