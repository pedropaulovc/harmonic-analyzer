"""Offline contracts for the tube-frame manufacturing drawing."""

from __future__ import annotations

import math
from pathlib import Path

import build_tube_frame as part
import draw_tube_frame as drawing
import tube_frame_spec
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from frame_attachment_spec import (
    BASE_SCREW_Y,
    COLUMN_BOTTOM_Y,
    TOP_SCREW_Y,
    TUBE_CUT_LENGTH,
    TUBE_TOP_Y,
)
from tube_frame_cap_spec import INNER_CORNER_R


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/tube-frame.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/tube-frame.pdf")
    assert drawing.PNG.as_posix().endswith("/png/tube-frame_drawing.png")
    assert DRAWINGS_BY_NAME["tube_frame"].script == Path(drawing.__file__).resolve()
    assert DRAWINGS_BY_NAME["tube_frame"].layout is DrawingLayout.PORTRAIT


def test_drawing_keeps_every_marked_manufacturing_dimension() -> None:
    assert part.DRAWING_DIMENSIONS is tube_frame_spec.DRAWING_DIMENSIONS
    marked = set().union(*tube_frame_spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.LENGTH_KEEP) == marked
    assert marked == {
        "OuterDia",
        "Length",
        "LowerHoleY",
        "UpperHoleY",
        "CrossHoleDia",
        "TopChamfer",
    }


def test_open_tube_and_cross_holes_share_the_installed_frame_stations() -> None:
    assert tube_frame_spec.OUTER_DIA == 25.4
    assert math.isclose(tube_frame_spec.INNER_DIA, 19.304, abs_tol=1e-9)
    assert part.COLUMN_LENGTH == tube_frame_spec.COLUMN_LENGTH == TUBE_CUT_LENGTH
    assert math.isclose(
        COLUMN_BOTTOM_Y + tube_frame_spec.COLUMN_LENGTH,
        TUBE_TOP_Y,
        abs_tol=1e-9,
    )
    assert math.isclose(
        COLUMN_BOTTOM_Y + tube_frame_spec.LOWER_CROSS_HOLE_Y,
        BASE_SCREW_Y,
        abs_tol=1e-9,
    )
    assert math.isclose(
        COLUMN_BOTTOM_Y + tube_frame_spec.UPPER_CROSS_HOLE_Y,
        TOP_SCREW_Y,
        abs_tol=1e-9,
    )
    assert tube_frame_spec.CROSS_HOLE_DIAMETER > 4.826
    assert tube_frame_spec.TOP_END_CHAMFER > INNER_CORNER_R
    assert part.TOP_END_CHAMFER_BAND == (0.15, -0.10)


def test_drawing_identifies_two_wall_drilling_and_cap_fit() -> None:
    assert drawing.DIMENSION_CALLOUTS["CrossHoleDia"] == (
        "2 STATIONS; DRILL THRU BOTH WALLS"
    )
    assert "FIT MHA-133 CAP" in drawing.DIMENSION_CALLOUTS["TopChamfer"]
    assert drawing.SHEET_SCALE == (1.0, 5.0)
    assert tube_frame_spec.END_VIEW_NOTE == "END VIEW SCALE 2:1"


def test_part_registry_keeps_stock_and_finish_requirements() -> None:
    import _config

    config = _config.parts("tube-frame")
    assert config["material"] == config["material_specification"]
    assert "ASTM A513 Type 5" in str(config["material"])
    assert "SAE 1020 DOM" in str(config["material"])
    finish = str(config["finish"]).lower()
    assert "od polished ra 1.6" in finish
    assert "corrosion-preventive oil after inspection" in finish
    assert "ends faced" in finish
    assert "id as-procured" in finish
    assert int(config["quantity"]) == 4
