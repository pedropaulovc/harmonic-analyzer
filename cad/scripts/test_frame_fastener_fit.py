"""SolidWorks-free contracts for the frame fastener stack."""

from __future__ import annotations

import math
import runpy

import pytest

import build_frame_assembly as frame
import build_frame_side_screw as side_screw


def test_frame_side_screw_clearance_follows_selected_stock_sku() -> None:
    assert frame.SIDE_SCREW_SHANK_LEN == side_screw.SHANK_LEN
    assert math.isclose(
        frame.SIDE_SCREW_TIP_Z,
        frame.SIDE_SCREW_HEAD_Z - side_screw.SHANK_LEN,
        abs_tol=1e-9,
    )
    assert math.isclose(
        frame.SIDE_SCREW_COLUMN_CLEARANCE,
        frame.SIDE_SCREW_TIP_Z - 124.7,
        abs_tol=1e-9,
    )
    assert frame.SIDE_SCREW_COLUMN_CLEARANCE > 0.0



def test_frame_side_screw_rejects_stock_shank_that_reaches_column(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reaching_shank_len = frame.SIDE_SCREW_HEAD_Z - 124.7 + 1.0
    monkeypatch.setattr(side_screw, "SHANK_LEN", reaching_shank_len)

    with pytest.raises(
        AssertionError,
        match="frame-side screw tip reaches the column surface",
    ):
        runpy.run_path(frame.__file__)