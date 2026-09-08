"""Offline contracts for the pen-hanger drawing."""

from __future__ import annotations

from pathlib import Path

import math

import pytest

import build_pen_hanger as part
import draw_pen_hanger as drawing
import pen_hanger_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pen-hanger.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pen-hanger.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pen-hanger_drawing.png")
    assert DRAWINGS_BY_NAME["pen_hanger"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is pen_hanger_spec.DRAWING_DIMENSIONS
    marked = set().union(*pen_hanger_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP)
    assert kept == marked




def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(2, 1)" in source
    assert "scale=(1, 1)" in source
    assert pen_hanger_spec.FRONT_VIEW_NOTE == "FRONT VIEW SCALE 2:1"
    assert pen_hanger_spec.TOP_VIEW_NOTE == "TOP VIEW SCALE 2:1"
    assert '"*Top"' in source
    assert "add_native_hole_callout" not in source


def test_part_stamps_make_critical_properties() -> None:
    import _config

    config = _config.parts("pen-hanger")
    assert config["material"] == "AISI 1018 cold-finished steel"
    assert config["material"] == config["material_specification"]
    assert "steel" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1


def test_hanger_screw_moves_without_moving_the_pen_or_bar() -> None:
    import build_magnifier_assembly as magnifier
    import build_pen_assembly as pen
    import build_wheel_bar as bar

    assert (
        magnifier.WHEEL_BAR_X0 - bar.BAR_LENGTH / 2.0,
        magnifier.WHEEL_BAR_X0 + bar.BAR_LENGTH / 2.0,
    ) == pytest.approx((-8.0, 226.0))
    assert pen.HANGER_POS == pytest.approx((3.0, 505.0, -157.0))
    assert pen.PEN_ROD_POS == pytest.approx((3.0, 368.0, -159.5))
    tap_axis = (
        pen.HANGER_POS[0] + part.SCREW_HOLE_XY[0],
        pen.HANGER_POS[1] + part.SCREW_HOLE_XY[1],
    )
    bar_axis = (
        magnifier.WHEEL_BAR_X0 + bar.SCREW_HOLE_X,
        magnifier.WHEEL_BAR_Y,
    )
    assert tap_axis == pytest.approx((-3.0, 575.7))
    assert tap_axis == pytest.approx(bar_axis)
    assert pen.HANGER_SCREW_POS == pytest.approx((*tap_axis, -129.9))

    # Receiver thickness and the rear-entry stock-screw stack are unchanged.
    assert part.STRAP_Z[1] - part.STRAP_Z[0] == pytest.approx(3.0)
    assert pen.HANGER_THREAD_PROTRUSION == pytest.approx(0.7)
    assert pen.HANGER_TIP_TO_RIM == pytest.approx(0.3)


def test_hanger_thread_envelope_fits_all_four_tapered_land_edges() -> None:
    point = part.SCREW_HOLE_XY
    vertices = (
        (part.STRAP_BOT_X[0], part.BLOCK_HALF),
        (part.STRAP_BOT_X[1], part.BLOCK_HALF),
        (part.STRAP_TOP_X[1], part.STRAP_TOP_Y),
        (part.STRAP_TOP_X[0], part.STRAP_TOP_Y),
    )
    # Signed point-to-edge distances in the CCW polygon measure the complete
    # circular thread envelope, including the top edge and inclined sides.
    walls = []
    for start, end in zip(vertices, vertices[1:] + vertices[:1]):
        dx, dy = end[0] - start[0], end[1] - start[1]
        distance = (
            dx * (point[1] - start[1]) - dy * (point[0] - start[0])
        ) / math.hypot(dx, dy)
        walls.append(distance - part.HANGER_SCREW_DIA / 2.0)
    assert min(walls) == pytest.approx(2.9172)
    assert min(walls) == pytest.approx(part.HANGER_THREAD_STRAP_WALL)
