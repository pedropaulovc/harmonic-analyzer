"""Offline contracts for the keyed arbor's key (MHA-DT-03-TL-06)."""

from __future__ import annotations

import sys

import pytest

import _buildgraph as bg
import _config
import build_dt_cone_gear_tl_arbor_key as part
import cone_land_key
import draw_dt_cone_gear_tl_arbor_key as drawing
import dt_cone_gear_tl_arbor_key_spec as spec
import dt_cone_gear_tl_keyed_arbor_spec as arbor
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _machinist_review_mode import MachinistReviewMode
from _printed_tolerance import printed_band_mm

INCH = 25.4
XX = printed_band_mm(2, unit="in")


def test_registry_row_is_a_made_tooling_part_in_inch() -> None:
    row = _config.parts(spec.PART_NAME)
    assert row["number"] == spec.PART_NUMBER == "MHA-DT-03-TL-06"
    assert row["drawing_unit"] == spec.UNIT == "in"
    assert int(row["quantity"]) == 1
    assert row["process"] != "purchased"
    assert "supplier_skus" not in row
    assert spec.PART_NAME not in FASTENERS
    entry = DRAWINGS_BY_NAME["dt_cone_gear_tl_arbor_key"]
    assert entry.artifact_stem == spec.PART_NAME == part.PART_NAME
    assert entry.source_kind == "part"
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    stem = "dt_cone_gear_tl_arbor_key"
    assert bg.is_shop_fixture(stem)
    assert stem in bg.references_of("dt_cone_gear_tl_arbor")
    for machine in bg.MACHINE_ASSEMBLIES:
        assert stem not in bg.references_of(machine)


def test_section_is_the_machine_keys_stock_the_blanks_keyways_fit() -> None:
    assert (spec.SIZE, spec.SIZE_BAND) == (
        cone_land_key.KEY_SIZE_MM,
        cone_land_key.KEY_STOCK_BAND,
    )
    assert spec.SIZE == pytest.approx(INCH / 16.0)
    assert spec.SIZE_BAND[1] < spec.SIZE_BAND[0] == 0.0
    assert spec.STOCK_FRACTION_DIMENSIONS == {
        "KeyWidth": spec.SIZE,
        "KeyHeight": spec.SIZE,
    }


def test_the_cut_length_lies_on_the_seat_and_under_every_blank() -> None:
    assert spec.LENGTH_PLACES == 2
    assert spec.LENGTH / INCH == pytest.approx(round(spec.LENGTH / INCH, 2), abs=1e-9)
    near = arbor.KEY_END_SET - XX
    far = arbor.KEY_END_SET + XX + spec.LENGTH + XX
    assert near > 0.0
    assert far <= arbor.SEAT_LENGTH - XX + 1e-9
    assert far < min(blank.face[0] for blank in arbor.KEYED_GEARS)
    assert spec.LENGTH - XX >= spec.SIZE


def test_the_key_sits_on_the_keyseat_floor_in_the_arbor_frame() -> None:
    assert spec.FLOOR_OFFSET_MM == pytest.approx(arbor.KEYSEAT_S - arbor.SEAT_DIA / 2.0)
    assert spec.END_Z_MM == pytest.approx(arbor.SHOULDER_Z + arbor.KEY_END_SET)
    # More than half its height stays in the keyseat at the seat's edge.
    assert arbor.KEYSEAT_EDGE_DEPTH_MIN > spec.SIZE / 2.0


def test_the_sheet_marks_every_dimension_once() -> None:
    marked = {name for names in spec.DRAWING_DIMENSIONS.values() for name in names}
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert len(spec.DRAWING_NOTES.splitlines()) <= 4


def test_the_isometric_stands_clear_of_the_note_and_the_title_block() -> None:
    """The note's text (one line, about .0026 m a character at the sheet's
    note height) ends short of the isometric's widest reach, and the view
    stays above the title block and inside the border."""
    scale = drawing.VIEW_SCALE[0] / drawing.VIEW_SCALE[1]
    # Half the view's widest extent: its length plus two section sides.
    reach = (spec.LENGTH + 2.0 * spec.SIZE) * scale / 2000.0
    iso_x, iso_y = drawing.ISO_CENTER
    (line,) = spec.DRAWING_NOTES.splitlines()
    note_right = drawing.NOTES_XY[0] + len(line) * 0.0026
    assert note_right < iso_x - reach
    title_top, title_left, border_right = 0.069, 0.216, 0.4191
    assert iso_y - reach > title_top or iso_x + reach < title_left
    assert iso_x + reach < border_right
    # The isometric clears the side view above it.
    side_bottom = drawing.RIGHT_CENTER[1] - drawing.HALF_SIZE - 0.012
    assert iso_y + reach < side_bottom or iso_x - reach > (
        drawing.RIGHT_CENTER[0] + drawing.HALF_LENGTH
    )


def test_the_cli_takes_its_own_stem(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["draw", spec.PART_NAME])
    assert drawing._parse_args().part == spec.PART_NAME
