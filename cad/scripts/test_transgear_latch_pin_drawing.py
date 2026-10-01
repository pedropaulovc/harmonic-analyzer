"""Offline contracts for the MHA-169 transgear latch pin (McMaster 98381A474)."""

from __future__ import annotations

import asyncio
import re
from fractions import Fraction
from pathlib import Path

import pytest

import _config
import build_transgear_latch_pin as part
import transgear_latch_pin_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_fastener import STOCK_RECIPES
from diagnostics import diag_build_98381A474 as recipe
from diagnostics.diag_mcmaster_dowel import MM_PER_IN

STEM = "transgear-latch-pin"


def test_catalogue_row_is_the_registered_mcmaster_dowel() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert row["number"] == "MHA-169"
    metadata = STOCK_RECIPES[spec.SKU]
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_98381A474
    assert metadata.threaded is False


def test_standalone_recipe_run_is_catalog_only(monkeypatch) -> None:
    """R9-50: the 7/8 length has no vendor model yet, so the standalone run
    builds and saves the catalog recipe and never enters the replica path,
    which demands a vendor SLDPRT and its harvest."""
    from diagnostics.diag_build_mcmaster import REGISTRY

    assert spec.SKU not in REGISTRY
    assert not hasattr(recipe, "replica_main")
    seen: list = []

    async def fake_catalog(adapter, part_no):
        seen.append(part_no)
        return {}

    monkeypatch.setattr(recipe, "build_catalog", fake_catalog)
    asyncio.run(recipe._catalog(None))
    assert seen == [spec.SKU]


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

    section = dowel_section(spec.SKU)
    pressed_face = max(rad for rad, y in section if y == 0.0)
    lead_face = max(rad for rad, y in section if y == spec.LENGTH)
    assert pressed_face == pytest.approx(spec.ENDS.point_dia / 2.0)
    assert lead_face == pytest.approx(spec.DIA / 2.0 - spec.CROWN_R)
    assert (spec.DIA / 2.0, spec.CHAMFER_LEN) in section


def test_the_installation_note_states_the_proud_length() -> None:
    notes = _config.parts(STEM)["installation_notes"]
    assert f"{spec.PROUD:.1f} PROUD" in notes


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_transgear_latch_pin as drawing

    sheet = DRAWINGS_BY_NAME["transgear_latch_pin"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
