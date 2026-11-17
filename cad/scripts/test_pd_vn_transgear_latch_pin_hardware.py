"""Offline part, recipe and fit contracts for pd-vn-transgear-latch-pin.

Its purchase sheet retired for a HARDWARE.md row (#2886); these checks pin
the part the assemblies still build.
"""

from __future__ import annotations

import re
from fractions import Fraction
from pathlib import Path

import pytest

import _config
import build_pd_vn_transgear_latch_pin as part
import pd_vn_transgear_latch_pin_spec as spec
from _fastener_catalog import FASTENERS
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_98381A474 as recipe
from _mcmaster_98381a474 import DOWEL_SIZE, MM_PER_IN

STEM = "pd-vn-transgear-latch-pin"


def test_catalogue_row_is_the_registered_mcmaster_dowel() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert row["number"] == "MHA-PD-VN-58"
    metadata = discovered_recipes()[spec.SKU]
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_98381A474
    assert metadata.threaded is False


def test_no_vendor_model_of_the_new_pin_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob(f"cad/references/**/{spec.SKU}*.SLDPRT"))


def test_recipe_is_the_size_the_registry_names() -> None:
    text = _config.parts(STEM)["material_specification"]
    match = re.search(r"(\d+/\d+) x (\d+/\d+)", text)
    assert match, text
    dia, length = (float(Fraction(size)) * MM_PER_IN for size in match.groups())
    assert spec.DIA == pytest.approx(dia)
    assert spec.LENGTH == pytest.approx(length)


def test_pressed_and_proud_lengths_are_the_whole_pin() -> None:
    assert spec.PRESS_DEPTH + spec.PROUD == pytest.approx(spec.LENGTH)
    assert spec.PRESS_ENGAGEMENT_D >= spec.PRESS_ENGAGEMENT_MIN_D
    assert min(spec.DIA_BAND) > 0.0  # a press dowel is oversize, never under


def test_the_chamfered_end_is_the_pressed_end() -> None:
    from diagnostics.diag_mcmaster_dowel import dowel_section

    section = dowel_section(DOWEL_SIZE, spec.ENDS)
    pressed_face = max(rad for rad, y in section if y == 0.0)
    lead_face = max(rad for rad, y in section if y == spec.LENGTH)
    assert pressed_face == pytest.approx(spec.ENDS.point_dia / 2.0)
    assert lead_face == pytest.approx(spec.DIA / 2.0 - spec.CROWN_R)
    assert (spec.DIA / 2.0, spec.CHAMFER_LEN) in section
