"""Offline contracts for the MHA-VN-048 knob-cup pin (McMaster 98296A031)."""

from __future__ import annotations

import math
import re
from fractions import Fraction

import pytest

import _config
import build_vn_transgear_knob_cup_pin as part
import vn_transgear_knob_cup_pin_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_fastener import STOCK_RECIPES
from diagnostics import diag_build_98296A031 as recipe

STEM = "vn-transgear-knob-cup-pin"


def _catalogue_size_mm() -> tuple[float, float]:
    """Diameter and length the parts registry names ("1/16 x 5/8")."""
    text = _config.parts(STEM)["material_specification"]
    match = re.search(r"(\d+/\d+) x (\d+/\d+)", text)
    assert match, text
    dia, length = (float(Fraction(size)) * spec.INCH for size in match.groups())
    return dia, length


def test_catalogue_row_is_the_registered_mcmaster_spring_pin() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert row["number"] == "MHA-VN-048"
    assert row["quantity"] == 1
    assert spec.SKU in row["material_specification"]
    metadata = STOCK_RECIPES[spec.SKU]
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_98296A031
    assert metadata.threaded is False


def test_fleet_diagnostic_driver_builds_the_new_sku() -> None:
    from diagnostics.diag_build_mcmaster import REGISTRY

    assert REGISTRY[spec.SKU] is recipe.build_98296A031


def test_recipe_is_the_named_size_as_an_installed_tube() -> None:
    dia, length = _catalogue_size_mm()
    assert recipe.PIN_OD == pytest.approx(dia)
    assert recipe.PIN_LEN == pytest.approx(length)
    assert spec.PIN_LEN == pytest.approx(length)
    bore = dia - 2.0 * spec.WALL_T
    tube = math.pi / 4.0 * (dia**2 - bore**2) * length
    assert recipe.V_PIN == pytest.approx(tube)
    assert 0.0 < recipe.PIN_ID < recipe.PIN_OD


def test_recipe_section_matches_the_retained_catalogue_authority() -> None:
    """98296A031 retains its own catalogue section and 5/8-in length."""
    from diagnostics.diag_mcmaster_spring_pin import SPRING_PIN_SIZES, WALL_T

    dia, length = SPRING_PIN_SIZES[spec.SKU]
    assert spec.PIN_DIA == pytest.approx(dia)
    assert spec.PIN_LEN == pytest.approx(length)
    assert spec.WALL_T == pytest.approx(WALL_T)
    assert recipe.PIN_OD == pytest.approx(dia)
    assert recipe.PIN_ID == pytest.approx(dia - 2.0 * WALL_T)


def test_match_drilled_hole_band_grips_the_pin() -> None:
    """The hole is printed +0.05/0, inside the 0.062-0.065 in window the pin
    is sold to grip and under its free diameter; the title block's drilled
    row would leave the window."""
    low, high = spec.HOLE_WINDOW
    assert low <= spec.HOLE_DIA and spec.HOLE_MAX <= high
    assert low <= spec.PIN_DIA <= high
    assert spec.HOLE_MAX < spec.FREE_DIA_MIN
    drilled = _config.title_block("drilled_hole")
    assert spec.HOLE_DIA + drilled["plus_mm"] > high


def test_pin_ends_stay_inside_the_cup_od() -> None:
    """The pin crosses the Ø19 cup diametrally; even the longest pin in the
    smallest cup keeps both ends under the O.D."""
    import pd_transgear_knob_cup_spec as cup

    worst = (cup.OD_MIN - spec.PIN_LEN_MAX) / 2.0
    assert worst > 0.0
    assert cup.PIN_END_INSIDE_OD_WORST == pytest.approx(worst)
    assert (cup.OD - spec.PIN_LEN) / 2.0 == pytest.approx(1.5625)
    # Negative control: a 3/4 pin stands proud of the smallest cup.
    three_quarters = 0.75 * spec.INCH
    assert (cup.OD_MIN - three_quarters - spec.PIN_LEN_BAND) / 2.0 < 0.0


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_vn_transgear_knob_cup_pin as drawing

    sheet = DRAWINGS_BY_NAME["vn_transgear_knob_cup_pin"]
    assert drawing.SPEC is sheet
    assert sheet.script.name == "draw_vn_transgear_knob_cup_pin.py"
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
