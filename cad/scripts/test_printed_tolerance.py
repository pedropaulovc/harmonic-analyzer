"""The title block's unit-explicit general tolerances (#290): one reader that
returns physical millimetres (_printed_tolerance) and one renderer that derives
the printed text (_title_block_units)."""

from __future__ import annotations

import pytest

import _config
import _printed_tolerance as tol
import _title_block_units as units


def _rows(monkeypatch: pytest.MonkeyPatch, **rows: dict) -> None:
    """Replace the named rows on every sheet (mm and inch alike)."""
    real = _config.title_block
    monkeypatch.setattr(
        _config,
        "title_block",
        lambda kind, *, unit="mm": rows.get(kind) or real(kind, unit=unit),
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
    assert tol.printed_band_mm(2, unit="in") == pytest.approx(0.254)
    assert units.linear_band_display(2, unit="in") == "±.01"
    # The same band authored in mm prints and reads as mm on the mm sheet.
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
    assert tol.drilled_oversize_mm(unit="in") == pytest.approx(0.1016)
    assert (
        units.drilled_hole_plus_display(unit="in"),
        units.drilled_hole_minus_display(unit="in"),
    ) == ("+.004", "0")
    assert tol.edge_break_radius_mm(unit="in") == pytest.approx(0.254)
    assert (
        units.edge_break_radius_display(unit="in"),
        units.edge_break_chamfer_display(unit="in"),
    ) == ("R.010", ".010")
    assert tol.inside_corner_radius_mm(unit="in") == pytest.approx(1.016)
    assert units.inside_corner_display(unit="in") == "R.040 MAX"


@pytest.mark.parametrize(
    ("row", "sheet"),
    [
        # An inch sheet whose row fell back to (or was authored in) mm.
        ({"value_in": 0.02, "band_mm": 0.51, "digits": 2}, "in"),
        # A millimetre sheet carrying an inch band.
        ({"value_in": 0.01, "band_in": 0.01, "digits": 2}, "mm"),
    ],
)
def test_a_length_row_printed_in_another_unit_than_its_sheet_is_refused(
    monkeypatch, row, sheet
):
    _rows(monkeypatch, linear_2pl=row)
    with pytest.raises(ValueError, match=f"cannot print on a '{sheet}' sheet"):
        tol.printed_band_mm(2, unit=sheet)
    with pytest.raises(ValueError, match=f"cannot print on a '{sheet}' sheet"):
        units.linear_band_display(2, unit=sheet)


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


_TOLERANCE_ROWS = (
    "linear_1pl",
    "linear_2pl",
    "linear_3pl",
    "angular",
    "edge_break",
    "inside_corner",
    "drilled_hole",
)


@pytest.mark.parametrize("sheet", ["mm", "in"])
def test_title_block_rows_carry_no_display_strings(sheet):
    for kind in _TOLERANCE_ROWS:
        row = _config.title_block(kind, unit=sheet)
        assert not any(key.startswith("display") for key in row), kind
        assert all(not isinstance(value, str) for value in row.values()), kind


# The legacy millimetre sheet, byte for byte as #2087 stamped it: a package
# that declares no drawing_unit (and every caller that passes no unit) keeps it.
_MM_SHEET = {
    "TOL_LIN_X": "±0.8",
    "TOL_LIN_XX": "±0.51",
    "TOL_LIN_XXX": "±0.13",
    "TOL_ANG": "±1°",
    "TOL_SURFACE": "CAST/MACHINED",
    "TOL_EDGE_BREAK_R": "R0.25",
    "TOL_CHAMFER_MAX": "0.25",
    "TOL_INSIDE_CORNER": "R1.0 MAX",
    "THREAD_TYPE": "UNC/UNF",
    "THREAD_CLASS": "2A/2B",
    "TOL_HOLE_MINUS": "0",
    "TOL_HOLE_PLUS": "+0.10",
}

# The owner's decimal-inch rulings (2026-10-30).
_INCH_SHEET = {
    **_MM_SHEET,
    "TOL_LIN_X": "±.1",
    "TOL_LIN_XX": "±.01",
    "TOL_LIN_XXX": "±.005",
    "TOL_EDGE_BREAK_R": "R.010",
    "TOL_CHAMFER_MAX": ".010",
    "TOL_INSIDE_CORNER": "R.040 MAX",
    "TOL_HOLE_PLUS": "+.004",
}


def test_the_default_sheet_is_the_legacy_millimetre_sheet():
    from _part_properties import title_block_properties

    assert title_block_properties() == title_block_properties(unit="mm") == _MM_SHEET
    assert list(title_block_properties()) == list(_MM_SHEET)


def test_the_inch_sheet_prints_the_owner_rulings():
    from _part_properties import title_block_properties

    assert title_block_properties(unit="in") == _INCH_SHEET


@pytest.mark.parametrize(
    ("accessor", "mm", "inch"),
    [
        (lambda unit: tol.printed_band_mm(1, unit=unit), 0.8, 2.54),
        (lambda unit: tol.printed_band_mm(2, unit=unit), 0.51, 0.254),
        (lambda unit: tol.printed_band_mm(3, unit=unit), 0.13, 0.127),
        (lambda unit: tol.drilled_oversize_mm(unit=unit), 0.10, 0.1016),
        (lambda unit: tol.drilled_undersize_mm(unit=unit), 0.0, 0.0),
        (lambda unit: tol.edge_break_radius_mm(unit=unit), 0.25, 0.254),
        (lambda unit: tol.edge_break_chamfer_mm(unit=unit), 0.25, 0.254),
        (lambda unit: tol.inside_corner_radius_mm(unit=unit), 1.0, 1.016),
        (lambda unit: tol.angular_band_deg(unit=unit), 1.0, 1.0),
    ],
)
def test_physical_bands_stay_millimetres_on_either_sheet(accessor, mm, inch):
    assert accessor("mm") == mm
    assert accessor("in") == pytest.approx(inch, abs=1e-12)


def test_no_argument_accessors_read_the_millimetre_sheet():
    assert tol.printed_band_mm(2) == tol.printed_band_mm(2, unit="mm") == 0.51
    assert tol.drilled_oversize_mm() == 0.10
    assert tol.printed_deviations(12.345, 2) == tol.printed_deviations(
        12.345, 2, unit="mm"
    )


def test_inch_deviations_round_the_nominal_on_the_inch_grid():
    # 12.7 mm prints .50 on an inch sheet: the part is checked against
    # .50 ±.01 in = 12.446..12.954 mm.
    lower, upper = tol.printed_deviations(12.7, 2, unit="in")
    assert (lower, upper) == (pytest.approx(-0.254), pytest.approx(0.254))
    # 12.0 mm prints .47 (11.938 mm): the window shifts by the rounding.
    lower, upper = tol.printed_deviations(12.0, 2, unit="in")
    assert lower == pytest.approx(11.938 - 0.254 - 12.0)
    assert upper == pytest.approx(11.938 + 0.254 - 12.0)
    # Explicit limits (mm) qualify the inch-rounded nominal: 12.0 mm prints
    # .472 (11.9888 mm) at three places.
    lower, upper = tol.printed_deviations(12.0, 3, (-0.0254, 0.0), unit="in")
    assert lower == pytest.approx(11.9888 - 0.0254 - 12.0)
    assert upper == pytest.approx(11.9888 - 12.0)


def test_dimxpert_block_values_equal_the_printed_inch_bands():
    # apply_block_tolerances stamps value_in; on the inch sheet it is the band.
    for kind in ("linear_1pl", "linear_2pl", "linear_3pl"):
        row = _config.title_block(kind, unit="in")
        assert row["value_in"] == row["band_in"], kind


def test_the_unit_section_is_not_a_row_and_unknown_units_are_refused():
    with pytest.raises(KeyError, match="unit section"):
        _config.title_block("in")
    with pytest.raises(ValueError, match="unknown title-block unit 'cm'"):
        _config.title_block("linear_2pl", unit="cm")
    # Unit-free rows are shared between the sheets.
    for kind in ("angular", "surface", "thread"):
        assert _config.title_block(kind, unit="in") is _config.title_block(kind)


def test_every_length_row_has_an_inch_row():
    # A missing in: row would fall back to the mm band and be refused at the
    # first inch read; pin the whole sheet here instead.
    for kind in (
        "linear_1pl",
        "linear_2pl",
        "linear_3pl",
        "edge_break",
        "inside_corner",
        "drilled_hole",
    ):
        assert _config.title_block(kind, unit="in") is not _config.title_block(kind)
