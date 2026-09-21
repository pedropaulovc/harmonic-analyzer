"""Offline contracts for the crank-pinion retention-pin drawing.

A plain straight pin under ``cad/docs/drawing-simplicity-policy.md``: two
native model dimensions whose places the PART owns, no band, no GD&T, no
roughness symbol, one stock note -- the match-drilled hole it is driven into
(``crank_pinion_spec``) is the fit.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_crank_pinion_pin as part
import crank_pinion_pin_spec as spec
import crank_pinion_spec
import draw_crank_pinion_pin as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def _build_source() -> str:
    return Path(part.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-pinion-pin.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crank-pinion-pin.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crank-pinion-pin_drawing.png")
    assert (
        DRAWINGS_BY_NAME["crank_pinion_pin"].script == Path(drawing.__file__).resolve()
    )


def test_pin_is_the_hole_it_is_cut_for() -> None:
    # The pinion owns the joint: the pin is its hole's own drill size and is
    # flush with the boss on both sides. Move the hole and the pin follows.
    assert spec.PIN_DIA is crank_pinion_spec.PIN_DIA
    assert spec.PIN_LEN == crank_pinion_spec.PIN_LENGTH == crank_pinion_spec.BOSS_DIA
    assert spec.PIN_DIA == pytest.approx(3.175)
    assert part.V_PIN == pytest.approx(math.pi * spec.PIN_DIA**2 / 4 * spec.PIN_LEN)


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked == {"PinDia", "PinLen"}
    # Turned part (rule 7): the diameter on the end view, the length on the
    # side view.
    assert set(drawing.FRONT_KEEP) == {"PinDia"}
    assert set(drawing.RIGHT_KEEP) == {"PinLen"}
    build = _build_source()
    assert 'name_dimensions(adapter, "Pin", ["PinLen"])' in build
    assert 'names=("PinCx", "PinCz", "PinDia")' in build


def test_precision_is_authored_on_the_part_and_only_read_by_the_sheet() -> None:
    # Rule 2: both sizes are routine at the title block's .XX grade -- the
    # match-drilled hole sets the fit, and flush-with-boss has no function
    # beyond "not proud" -- so two places, no band, no three-place number.
    assert spec.DRAWING_PRECISION_BY_NAME == {"PinDia": 2, "PinLen": 2}
    assert "draw_crank_pinion_pin.py" in PRECISION_MIGRATED_DRAWINGS
    source = _source()
    assert "set_dimension_precision" not in source
    assert "SetPrecision3" not in source
    assert "assert_imported_precision(" in source
    build = _build_source()
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in build
    assert "set_dimension_bilateral_tolerance" not in build
    assert "set_dimension_symmetric_tolerance" not in build
    assert [name for name in dir(spec) if name.endswith("_BAND")] == []


def test_print_carries_no_gdt_roughness_or_callouts() -> None:
    # Rules 3-5: a pin is not on the GD&T allowlist and nothing runs on it.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "add_surface_finish(",
        "set_dimension_callouts(",
        "add_native_hole_callout(",
    ):
        assert helper not in source, helper
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(spec, "SURFACE_FINISHES")
    assert "author_part_pmi" not in _build_source()
    assert (
        "for view in (front, right, iso):\n        set_hidden_lines_removed" in source
    )
    assert "add_view_centerline(" in source


def test_notes_say_where_stock_may_come_from_and_nothing_else() -> None:
    notes = spec.DRAWING_NOTES
    assert notes == "STOCK 1/8 IN DRILL ROD OK; FACE BOTH ENDS SQUARE."
    assert "\n" not in notes
    for banned in ("+/-", "MHA-", "MATCH", "PRESS", "HARDEN", "TOLERANCE"):
        assert banned not in notes, banned


def test_sheet_runs_at_8_to_1_with_every_view_at_sheet_scale() -> None:
    assert drawing.SHEET_SCALE == (8.0, 1.0)
    assert drawing.VIEW_SCALE == (8, 1)
    assert _source().count("scale=VIEW_SCALE") == 3


def test_dimension_text_lands_clear_of_the_views_and_the_title_block() -> None:
    assert drawing.HALF_DIA == pytest.approx(spec.PIN_DIA * 8 / 2000.0)
    assert drawing.HALF_LEN == pytest.approx(spec.PIN_LEN * 8 / 2000.0)
    for name, (x, y) in drawing.FRONT_KEEP.items():
        reach = math.hypot(x - drawing.FRONT_CENTER[0], y - drawing.FRONT_CENTER[1])
        assert reach > drawing.HALF_DIA + 0.010, name
    for name, (x, y) in drawing.RIGHT_KEEP.items():
        assert y < drawing.RIGHT_CENTER[1] - drawing.HALF_DIA, name
    positions = (
        *drawing.FRONT_KEEP.values(),
        *drawing.RIGHT_KEEP.values(),
        (0.016, 0.082),  # manufacturing-notes anchor
    )
    for x, y in positions:
        assert 0.012 < x < 0.420
        assert 0.012 < y < 0.267
        assert not (x > 0.216 and y < 0.070), (x, y)  # title-block keep-out
    # End view, side view, isometric, left to right without overlapping.
    assert (
        drawing.FRONT_CENTER[0] + drawing.HALF_DIA
        < drawing.RIGHT_CENTER[0] - drawing.HALF_LEN - 0.010
    )
    assert (
        drawing.RIGHT_CENTER[0] + drawing.HALF_LEN
        < drawing.ISO_CENTER[0] - drawing.HALF_LEN - 0.010
    )


def test_part_registry_row_is_a_plain_pin() -> None:
    config = _config.parts("crank-pinion-pin")
    assert config["number"] == "MHA-134"
    assert config["tolerance_class"] == "machined_block"
    assert "fit_class" not in config
    assert "drill rod" in config["process"]
    assert int(config["quantity"]) == 1
    build = _build_source()
    assert 'PART_NAME = "crank-pinion-pin"' in build
    assert "apply_drawing_properties" in build
    assert "clear_dimensions_for_drawing" in build
