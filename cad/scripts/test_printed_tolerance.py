"""The title block's unit-explicit general tolerances (#290): one reader that
returns physical millimetres (_printed_tolerance) and one renderer that derives
the printed text (_title_block_units)."""

from __future__ import annotations

import pytest

import _config
import _printed_tolerance as tol
import _title_block_units as units


def _rows(monkeypatch: pytest.MonkeyPatch, **rows: dict) -> None:
    real = _config.title_block
    monkeypatch.setattr(
        _config, "title_block", lambda kind: rows.get(kind) or real(kind)
    )


@pytest.mark.parametrize(
    ("value", "unit", "digits", "text", "per_unit"),
    [
        (0.51, "mm", 2, "0.51", 1.0),
        (0.8, "mm", 1, "0.8", 1.0),
        (0.10, "mm", 2, "0.10", 1.0),
        (1.0, "mm", 1, "1.0", 1.0),
        (0.01, "in", 2, ".01", 25.4),
        (0.005, "in", 3, ".005", 25.4),
        (0.010, "in", 3, ".010", 25.4),
        (1.25, "in", 2, "1.25", 25.4),
        (1.0, "deg", 0, "1°", 1.0),
    ],
)
def test_render_number_round_trips_in_its_own_unit(value, unit, digits, text, per_unit):
    rendered = units.render_number(value, unit, digits)
    assert rendered == text
    # Read back in the unit it was printed in, the text is the same physical size.
    assert float(rendered.removesuffix("°")) * per_unit == pytest.approx(
        value * per_unit
    )


def test_render_number_refuses_an_unknown_unit_and_a_signed_magnitude():
    with pytest.raises(ValueError, match="unknown display unit"):
        units.render_number(0.5, "cm", 1)
    with pytest.raises(ValueError, match="non-negative"):
        units.render_number(-0.5, "mm", 1)


def test_inch_band_converts_to_millimetres_and_prints_inch_style(monkeypatch):
    _rows(monkeypatch, linear_2pl={"value_in": 0.01, "band_in": 0.01, "digits": 2})
    assert tol.printed_band_mm(2) == pytest.approx(0.254)
    assert units.linear_band_display(2) == "±.01"
    # The same band authored in mm prints and reads as mm.
    _rows(monkeypatch, linear_2pl={"value_in": 0.01, "band_mm": 0.254, "digits": 3})
    assert tol.printed_band_mm(2) == 0.254
    assert units.linear_band_display(2) == "±0.254"


def test_inch_drilled_and_edge_rows_convert_and_render(monkeypatch):
    _rows(
        monkeypatch,
        drilled_hole={"minus_in": 0.0, "plus_in": 0.004, "digits": 3},
        edge_break={"radius_in": 0.010, "chamfer_max_in": 0.010, "digits": 3},
        inside_corner={"radius_in": 0.040, "digits": 3},
    )
    assert tol.drilled_oversize_mm() == pytest.approx(0.1016)
    assert (units.drilled_hole_plus_display(), units.drilled_hole_minus_display()) == (
        "+.004",
        "0",
    )
    assert tol.edge_break_radius_mm() == pytest.approx(0.254)
    assert (units.edge_break_radius_display(), units.edge_break_chamfer_display()) == (
        "R.010",
        ".010",
    )
    assert tol.inside_corner_radius_mm() == pytest.approx(1.016)
    assert units.inside_corner_display() == "R.040 MAX"


@pytest.mark.parametrize(
    ("row", "error", "match"),
    [
        ({"band": 0.8, "digits": 1}, ValueError, "has no unit"),
        ({"band_cm": 0.08, "digits": 1}, ValueError, "unknown unit 'cm'"),
        ({"band_mm": 0.8, "band_in": 0.03, "digits": 1}, ValueError, "exactly one"),
        ({"value_in": 0.03, "digits": 1}, ValueError, "exactly one"),
        # A display string is never a band: "±.02" must not read as 0.02 mm.
        ({"band_mm": "±.02", "digits": 2}, TypeError, "must be a number"),
        ({"band_in": ".02", "digits": 2}, TypeError, "must be a number"),
        ({"band_mm": True, "digits": 2}, TypeError, "must be a number"),
    ],
)
def test_reader_refuses_unitless_unknown_and_non_numeric_bands(
    monkeypatch, row, error, match
):
    _rows(monkeypatch, linear_2pl=row)
    with pytest.raises(error, match=match):
        tol.printed_band_mm(2)


def test_a_row_without_a_digit_count_is_refused(monkeypatch):
    _rows(monkeypatch, linear_1pl={"band_mm": 0.8})
    with pytest.raises(ValueError, match="digits"):
        tol.printed_band_mm(1)
    with pytest.raises(ValueError, match="digits"):
        units.linear_band_display(1)


def test_a_band_the_sheet_cannot_print_exactly_is_refused(monkeypatch):
    # .009 at two places would print ".01" while the stacks used 0.2286 mm.
    _rows(monkeypatch, linear_2pl={"band_in": 0.009, "digits": 2})
    with pytest.raises(ValueError, match="does not print exactly at 2 digits"):
        tol.printed_band_mm(2)
    with pytest.raises(ValueError, match="does not print exactly at 2 digits"):
        units.linear_band_display(2)
    with pytest.raises(ValueError, match="does not print exactly"):
        units.render_number(0.009, "in", 2)


def test_angular_row_must_be_degrees(monkeypatch):
    _rows(monkeypatch, angular={"value_rad": 0.01745, "digits": 0})
    with pytest.raises(ValueError, match="unknown unit 'rad'"):
        tol.angular_band_deg()


def test_title_block_rows_carry_no_display_strings():
    for kind in (
        "linear_1pl",
        "linear_2pl",
        "linear_3pl",
        "angular",
        "edge_break",
        "inside_corner",
        "drilled_hole",
    ):
        row = _config.title_block(kind)
        assert not any(key.startswith("display") for key in row), kind
        assert all(not isinstance(value, str) for value in row.values()), kind
