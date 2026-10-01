"""Offline contracts for the MHA-154 drive-collar cross pin (McMaster 98296A026)."""

from __future__ import annotations

import math
import re
from fractions import Fraction

import pytest

import _config
import build_transgear_collar_cross_pin as part
import transgear_collar_cross_pin_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_fastener import STOCK_RECIPES
from diagnostics import diag_build_98296A027 as strap_pin_recipe
from diagnostics import diag_build_98296A026 as recipe

STEM = "transgear-collar-cross-pin"


def _catalogue_size_mm() -> tuple[float, float]:
    """Diameter and length the parts registry names ("1/16 x 9/16")."""
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
    assert row["number"] == "MHA-154"
    assert spec.SKU in row["material_specification"]
    metadata = STOCK_RECIPES[spec.SKU]
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_98296A026
    assert metadata.threaded is False


def test_fleet_diagnostic_driver_builds_the_new_sku() -> None:
    from diagnostics.diag_build_mcmaster import REGISTRY

    assert REGISTRY[spec.SKU] is recipe.build_98296A026


def test_recipe_is_the_named_size_as_an_installed_tube() -> None:
    dia, length = _catalogue_size_mm()
    assert recipe.PIN_OD == pytest.approx(dia)
    assert recipe.PIN_LEN == pytest.approx(length)
    bore = dia - 2.0 * spec.WALL_T
    tube = math.pi / 4.0 * (dia**2 - bore**2) * length
    assert recipe.V_PIN == pytest.approx(tube)
    # A hollow pin: the wall is well under the radius.
    assert 0.0 < recipe.PIN_ID < recipe.PIN_OD


def test_recipe_is_the_98296a027_section_in_a_longer_length() -> None:
    """98296A026 is a length row of MHA-145's pin: same section, longer."""
    assert recipe.PIN_OD == pytest.approx(strap_pin_recipe.PIN_OD)
    assert recipe.PIN_ID == pytest.approx(strap_pin_recipe.PIN_ID)
    assert recipe.PIN_LEN > strap_pin_recipe.PIN_LEN
    ratio = recipe.V_PIN / strap_pin_recipe.V_PIN
    assert ratio == pytest.approx(recipe.PIN_LEN / strap_pin_recipe.PIN_LEN)


def test_recommended_hole_window_holds_the_nominal_hole_and_pin() -> None:
    low, high = spec.HOLE_WINDOW
    assert low < high
    assert low <= spec.HOLE_DIA <= high
    assert low <= spec.PIN_DIA <= high


def test_functional_hole_band_stays_inside_the_recommended_hole() -> None:
    """R9-11: the core's hole is printed +0.05/0, inside the 0.062-0.065 in
    window the pin is sold to grip; the title block's drilled row would not."""
    low, high = spec.HOLE_WINDOW
    assert low <= spec.HOLE_DIA and spec.HOLE_MAX <= high
    drilled = _config.title_block("drilled_hole")
    assert spec.HOLE_DIA + drilled["plus_mm"] > high


def _end_inside_collar_od(pin_len: float, collar_od: float) -> float:
    """How far each end of a pin centred across the collar lies inside its O.D."""
    return (collar_od - pin_len) / 2.0


def test_pin_ends_stay_inside_the_collar_od() -> None:
    """Contract §1.3: the pin lies in the collar's rear slot, each end 1.606
    inside the Ø17.5 O.D. nominal and 1.366 at the smallest O.D. with the
    longest pin; 98296A029 (11/16) would stand proud."""
    import transgear_drive_collar_spec as collar

    smallest_od = collar.OD + min(collar.OD_BAND)
    assert _end_inside_collar_od(spec.PIN_LEN, collar.OD) == pytest.approx(
        1.606, abs=5e-4
    )
    worst = _end_inside_collar_od(spec.PIN_LEN_MAX, smallest_od)
    assert worst == pytest.approx(1.366, abs=5e-4)
    assert worst > 0.0
    # Negative control: the 11/16 length row stands proud at the same corner.
    eleven_sixteenths = 11.0 * spec.INCH / 16.0
    assert (
        _end_inside_collar_od(eleven_sixteenths + spec.PIN_LEN_BAND, smallest_od) < 0.0
    )


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_transgear_collar_cross_pin as drawing

    sheet = DRAWINGS_BY_NAME["transgear_collar_cross_pin"]
    assert drawing.SPEC is sheet
    assert sheet.script.name == "draw_transgear_collar_cross_pin.py"
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
